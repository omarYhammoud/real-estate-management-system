from django.contrib import admin
from .models import FinancialTransaction


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_reference',
        'transaction_type',
        'amount',
        'transaction_date',
        'recorded_by',
        'related_entity_type',
        'related_entity_id',
    )
    list_filter = ('transaction_type', 'transaction_date')
    search_fields = ('transaction_reference',)
