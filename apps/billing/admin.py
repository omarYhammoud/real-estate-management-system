from django.contrib import admin
from .models import RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1
    readonly_fields = ('taxable_amount', 'tax_amount', 'line_total')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_reference', 'tenant', 'total_amount', 'amount_paid', 'outstanding_balance', 'status', 'due_date')
    list_filter = ('status',)
    search_fields = ('invoice_reference', 'tenant__full_name')
    inlines = [InvoiceLineItemInline]


@admin.register(RentSchedule)
class RentScheduleAdmin(admin.ModelAdmin):
    list_display = ('contract', 'billing_period_start', 'billing_period_end', 'due_date', 'expected_amount', 'status')
    list_filter = ('status',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_reference', 'invoice', 'tenant', 'amount', 'payment_method', 'payment_date')
    list_filter = ('payment_method',)
    search_fields = ('payment_reference', 'invoice__invoice_reference')


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_reference', 'payment', 'amount', 'receipt_date')