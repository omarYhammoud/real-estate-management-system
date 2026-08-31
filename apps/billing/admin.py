from django.contrib import admin
from .models import RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_reference', 'tenant', 'total_amount', 'status', 'due_date')
    list_filter = ('status',)
    inlines = [InvoiceLineItemInline]


admin.site.register(RentSchedule)
admin.site.register(Payment)
admin.site.register(Receipt)
