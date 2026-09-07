"""Waad — Billing & Payments views."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import RoleRequiredMixin
from apps.core.utils import generate_reference

from .forms import InvoiceForm, InvoiceLineItemFormSet, LateFeeForm, PaymentForm, RentScheduleGenerationForm
from .models import Invoice, Payment, Receipt, RentSchedule
from .services import generate_invoice_from_schedule, generate_rent_schedule, record_payment


User = get_user_model()


class BillingWriteAccessMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.ACCOUNTANT)


class BillingReadAccessMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.ACCOUNTANT, User.Role.TENANT)

    def scope_to_current_tenant(self, queryset, tenant_lookup='tenant'):
        if self.request.user.is_superuser or self.request.user.role != User.Role.TENANT:
            return queryset
        try:
            tenant = self.request.user.tenant_profile
        except User.tenant_profile.RelatedObjectDoesNotExist as exc:
            raise PermissionDenied('No tenant profile is linked to this account.') from exc
        return queryset.filter(**{tenant_lookup: tenant})


class RentScheduleListView(BillingWriteAccessMixin, View):
    template_name = 'billing/rent_schedule_list.html'

    def get_schedules(self):
        return RentSchedule.objects.select_related(
            'contract', 'contract__tenant', 'contract__unit', 'contract__unit__property'
        ).order_by('-contract__start_date', 'billing_period_start')

    def get(self, request):
        return render(request, self.template_name, {
            'schedules': self.get_schedules(), 'form': RentScheduleGenerationForm(),
        })

    def post(self, request):
        form = RentScheduleGenerationForm(request.POST)
        if form.is_valid():
            created = generate_rent_schedule(form.cleaned_data['contract'], form.cleaned_data['frequency'])
            messages.success(request, f'Generated {len(created)} rent schedule period(s).')
            return redirect('billing:rent_schedule_list')
        return render(request, self.template_name, {'schedules': self.get_schedules(), 'form': form})


class GenerateInvoiceView(BillingWriteAccessMixin, View):
    def post(self, request, schedule_id):
        schedule = get_object_or_404(RentSchedule, pk=schedule_id)
        try:
            invoice = generate_invoice_from_schedule(schedule)
        except ValidationError as exc:
            messages.error(request, exc.message if hasattr(exc, 'message') else str(exc))
            return redirect('billing:rent_schedule_list')
        messages.success(request, f'Invoice {invoice.invoice_reference} generated.')
        return redirect('billing:invoice_detail', pk=invoice.pk)


class InvoiceListView(BillingReadAccessMixin, ListView):
    model = Invoice
    template_name = 'billing/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        queryset = Invoice.objects.select_related('tenant', 'contract', 'contract__unit').order_by('-issue_date')
        queryset = self.scope_to_current_tenant(queryset)
        status = self.request.GET.get('status')
        if status in Invoice.Status.values:
            queryset = queryset.filter(status=status)
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(invoice_reference__icontains=search) | Q(tenant__full_name__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['search'] = self.request.GET.get('q', '')
        context['status_choices'] = Invoice.Status.choices
        return context


class InvoiceDetailView(BillingReadAccessMixin, DetailView):
    model = Invoice
    template_name = 'billing/invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        return self.scope_to_current_tenant(super().get_queryset())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payments'] = self.object.payments.order_by('-payment_date', '-created_at')
        context['late_fee_form'] = LateFeeForm()
        return context


class InvoiceCreateView(BillingWriteAccessMixin, View):
    template_name = 'billing/invoice_form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': InvoiceForm(), 'formset': InvoiceLineItemFormSet(instance=Invoice()),
        })

    def post(self, request):
        form = InvoiceForm(request.POST)
        formset = InvoiceLineItemFormSet(request.POST, instance=Invoice())
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.invoice_reference = generate_reference('INV')
            invoice.save()
            formset.instance = invoice
            formset.save()
            invoice.recalculate_totals()
            messages.success(request, f'Invoice {invoice.invoice_reference} created.')
            return redirect('billing:invoice_detail', pk=invoice.pk)
        return render(request, self.template_name, {'form': form, 'formset': formset})


class AddLateFeeView(BillingWriteAccessMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        form = LateFeeForm(request.POST)
        if form.is_valid():
            invoice.add_late_fee(form.cleaned_data['amount'], form.cleaned_data['reason'] or 'Late payment fee')
            messages.success(request, 'Late fee added to invoice.')
        else:
            messages.error(request, 'Could not add late fee — check the amount entered.')
        return redirect('billing:invoice_detail', pk=invoice.pk)


class PaymentCreateView(BillingWriteAccessMixin, View):
    template_name = 'billing/payment_form.html'

    def get_invoice(self):
        return get_object_or_404(Invoice, pk=self.kwargs['invoice_id'])

    def get(self, request, invoice_id):
        invoice = self.get_invoice()
        if invoice.status == Invoice.Status.PAID:
            messages.info(request, 'This invoice is already fully paid.')
            return redirect('billing:invoice_detail', pk=invoice.pk)
        return render(request, self.template_name, {'form': PaymentForm(invoice=invoice), 'invoice': invoice})

    def post(self, request, invoice_id):
        invoice = self.get_invoice()
        if invoice.status == Invoice.Status.PAID:
            messages.info(request, 'This invoice is already fully paid.')
            return redirect('billing:invoice_detail', pk=invoice.pk)
        form = PaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            payment, receipt = record_payment(
                invoice=invoice, tenant=invoice.tenant, amount=form.cleaned_data['amount'],
                payment_date=form.cleaned_data['payment_date'],
                payment_method=form.cleaned_data['payment_method'], recorded_by=request.user,
            )
            messages.success(request, f'Payment {payment.payment_reference} recorded.')
            return redirect('billing:receipt_detail', pk=receipt.pk)
        return render(request, self.template_name, {'form': form, 'invoice': invoice})


class PaymentHistoryView(BillingReadAccessMixin, ListView):
    model = Payment
    template_name = 'billing/payment_history.html'
    context_object_name = 'payments'
    paginate_by = 25

    def get_queryset(self):
        queryset = Payment.objects.select_related('invoice', 'tenant').order_by('-payment_date', '-created_at')
        queryset = self.scope_to_current_tenant(queryset)
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(payment_reference__icontains=search)
                | Q(invoice__invoice_reference__icontains=search)
                | Q(tenant__full_name__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search'] = self.request.GET.get('q', '')
        return context


class ReceiptDetailView(BillingReadAccessMixin, DetailView):
    model = Receipt
    template_name = 'billing/receipt_detail.html'
    context_object_name = 'receipt'

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'payment__invoice', 'payment__tenant', 'payment__recorded_by'
        )
        return self.scope_to_current_tenant(queryset, 'payment__tenant')
