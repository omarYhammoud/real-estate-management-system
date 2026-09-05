"""
Waad: build views for Rent Schedule, Invoices, Invoice Details, Create
Invoice, Record Payment, Payment History, and Receipt here.
"""
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView

from apps.core.mixins import RoleRequiredMixin

from .forms import PaymentForm
from .models import Invoice, Payment, Receipt


User = get_user_model()


class BillingAccessMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.ACCOUNTANT)


class InvoiceListView(BillingAccessMixin, ListView):
    model = Invoice
    template_name = 'billing/invoice_list.html'
    context_object_name = 'invoices'


class InvoiceDetailView(BillingAccessMixin, DetailView):
    model = Invoice
    template_name = 'billing/invoice_detail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payments'] = self.object.payments.select_related('receipt')
        return context


class PaymentCreateView(BillingAccessMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'billing/payment_form.html'

    def get_invoice(self):
        return get_object_or_404(Invoice, pk=self.kwargs['invoice_pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = self.get_invoice()
        return context

    def form_valid(self, form):
        invoice = self.get_invoice()
        form.instance.invoice = invoice
        form.instance.tenant = invoice.tenant
        form.instance.recorded_by = self.request.user
        self.object = form.save()
        Receipt.objects.create(
            payment=self.object,
            receipt_reference=f'REC-{self.object.pk}',
            receipt_date=self.object.payment_date,
            amount=self.object.amount,
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('billing:receipt_detail', kwargs={'pk': self.object.receipt.pk})


class PaymentHistoryView(BillingAccessMixin, ListView):
    model = Payment
    template_name = 'billing/payment_history.html'
    context_object_name = 'payments'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related(
            'invoice', 'tenant', 'recorded_by', 'receipt'
        ).order_by('-payment_date', '-pk')


class ReceiptDetailView(BillingAccessMixin, DetailView):
    model = Receipt
    template_name = 'billing/receipt_detail.html'
    context_object_name = 'receipt'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'payment__invoice', 'payment__tenant', 'payment__recorded_by'
        )
