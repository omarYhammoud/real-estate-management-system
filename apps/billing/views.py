"""
Waad: build views for Rent Schedule, Invoices, Invoice Details, Create
Invoice, Record Payment, Payment History, and Receipt here.
"""
from django.views.generic import ListView, DetailView
from .models import Invoice


class InvoiceListView(ListView):
    model = Invoice
    template_name = 'billing/invoice_list.html'
    context_object_name = 'invoices'


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = 'billing/invoice_detail.html'
    context_object_name = 'invoice'
