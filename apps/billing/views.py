"""
Waad — Billing & Payments views.

Pages: Rent Schedule, Invoices, Invoice Details, Create Invoice, Record
Payment, Payment History, Receipt.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView

from apps.core.utils import generate_reference

from .forms import InvoiceForm, InvoiceLineItemFormSet, LateFeeForm, PaymentForm, RentScheduleGenerationForm
from .models import Invoice, Payment, Receipt, RentSchedule
from .services import generate_invoice_from_schedule, generate_rent_schedule, record_payment


# ---------------------------------------------------------------------------
# Rent Schedule
# ---------------------------------------------------------------------------

@login_required
def rent_schedule_list(request):
    """Every rent schedule row across every contract, plus a form to
    generate a schedule for an active contract that doesn't have one yet."""
    schedules = (
        RentSchedule.objects
        .select_related('contract', 'contract__tenant', 'contract__unit', 'contract__unit__property')
        .order_by('-contract__start_date', 'billing_period_start')
    )

    if request.method == 'POST':
        form = RentScheduleGenerationForm(request.POST)
        if form.is_valid():
            created = generate_rent_schedule(form.cleaned_data['contract'], form.cleaned_data['frequency'])
            messages.success(request, f'Generated {len(created)} rent schedule period(s).')
            return redirect('billing:rent_schedule_list')
    else:
        form = RentScheduleGenerationForm()

    return render(request, 'billing/rent_schedule_list.html', {'schedules': schedules, 'form': form})


@login_required
def generate_invoice(request, schedule_id):
    schedule = get_object_or_404(RentSchedule, pk=schedule_id)
    try:
        invoice = generate_invoice_from_schedule(schedule)
    except ValidationError as exc:
        messages.error(request, exc.message if hasattr(exc, 'message') else str(exc))
        return redirect('billing:rent_schedule_list')
    messages.success(request, f'Invoice {invoice.invoice_reference} generated.')
    return redirect('billing:invoice_detail', pk=invoice.pk)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

class InvoiceListView(ListView):
    """Rent Invoices page: searchable, filterable by status."""
    model = Invoice
    template_name = 'billing/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        qs = Invoice.objects.select_related('tenant', 'contract', 'contract__unit').order_by('-issue_date')
        status = self.request.GET.get('status')
        if status in Invoice.Status.values:
            qs = qs.filter(status=status)
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(Q(invoice_reference__icontains=search) | Q(tenant__full_name__icontains=search))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_filter'] = self.request.GET.get('status', '')
        ctx['search'] = self.request.GET.get('q', '')
        ctx['status_choices'] = Invoice.Status.choices
        return ctx


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = 'billing/invoice_detail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payments'] = self.object.payments.order_by('-payment_date', '-created_at')
        ctx['late_fee_form'] = LateFeeForm()
        return ctx


@login_required
def invoice_create(request):
    """Manual / ad-hoc invoice — for a one-off charge that isn't tied to a
    generated rent schedule period (those go through generate_invoice())."""
    if request.method == 'POST':
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
    else:
        form = InvoiceForm()
        formset = InvoiceLineItemFormSet(instance=Invoice())

    return render(request, 'billing/invoice_form.html', {'form': form, 'formset': formset})


@login_required
def add_late_fee(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = LateFeeForm(request.POST)
        if form.is_valid():
            invoice.add_late_fee(form.cleaned_data['amount'], form.cleaned_data['reason'] or 'Late payment fee')
            messages.success(request, 'Late fee added to invoice.')
        else:
            messages.error(request, 'Could not add late fee — check the amount entered.')
    return redirect('billing:invoice_detail', pk=invoice.pk)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@login_required
def payment_create(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    if invoice.status == Invoice.Status.PAID:
        messages.info(request, 'This invoice is already fully paid.')
        return redirect('billing:invoice_detail', pk=invoice.pk)

    if request.method == 'POST':
        form = PaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            payment, receipt = record_payment(
                invoice=invoice,
                tenant=invoice.tenant,
                amount=form.cleaned_data['amount'],
                payment_date=form.cleaned_data['payment_date'],
                payment_method=form.cleaned_data['payment_method'],
                recorded_by=request.user if request.user.is_authenticated else None,
            )
            messages.success(request, f'Payment {payment.payment_reference} recorded.')
            return redirect('billing:receipt_detail', pk=receipt.pk)
    else:
        form = PaymentForm(invoice=invoice)

    return render(request, 'billing/payment_form.html', {'form': form, 'invoice': invoice})


class PaymentHistoryView(ListView):
    model = Payment
    template_name = 'billing/payment_history.html'
    context_object_name = 'payments'
    paginate_by = 25

    def get_queryset(self):
        qs = Payment.objects.select_related('invoice', 'tenant').order_by('-payment_date', '-created_at')
        search = self.request.GET.get('q')
        if search:
            qs = qs.filter(
                Q(payment_reference__icontains=search)
                | Q(invoice__invoice_reference__icontains=search)
                | Q(tenant__full_name__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search'] = self.request.GET.get('q', '')
        return ctx


def receipt_detail(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk)
    return render(request, 'billing/receipt_detail.html', {'receipt': receipt})