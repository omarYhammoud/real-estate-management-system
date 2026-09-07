"""
Admin configuration for Alyousof's Deposits & Operations module.
"""
from django.contrib import admin
from .models import (
    SecurityDeposit,
    DepositDeduction,
    DepositRefund,
    MaintenanceRequest,
    Expense,
)


class DepositDeductionInline(admin.TabularInline):
    model = DepositDeduction
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('amount', 'reason', 'deduction_date', 'authorized_by', 'created_at')


class DepositRefundInline(admin.TabularInline):
    model = DepositRefund
    extra = 0
    readonly_fields = ('created_at',)
    fields = (
        'amount', 'refund_date', 'refund_method',
        'refund_reference', 'authorized_by', 'created_at',
    )


@admin.register(SecurityDeposit)
class SecurityDepositAdmin(admin.ModelAdmin):
    list_display = (
        'contract', 'required_amount', 'received_amount',
        'remaining_balance', 'status', 'received_date',
    )
    list_filter = ('status',)
    search_fields = ('contract__contract_reference',)
    readonly_fields = ('remaining_balance', 'created_at', 'updated_at')
    inlines = [DepositDeductionInline, DepositRefundInline]
    fieldsets = (
        (None, {
            'fields': ('contract', 'status'),
        }),
        ('Amounts', {
            'fields': ('required_amount', 'received_amount', 'received_date', 'remaining_balance'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(DepositDeduction)
class DepositDeductionAdmin(admin.ModelAdmin):
    list_display = ('deposit', 'amount', 'deduction_date', 'authorized_by', 'reason_short')
    list_filter = ('deduction_date',)
    search_fields = ('deposit__contract__contract_reference', 'reason')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Reason')
    def reason_short(self, obj):
        return obj.reason[:60] + '…' if len(obj.reason) > 60 else obj.reason


@admin.register(DepositRefund)
class DepositRefundAdmin(admin.ModelAdmin):
    list_display = (
        'refund_reference', 'deposit', 'amount',
        'refund_date', 'refund_method', 'authorized_by',
    )
    list_filter = ('refund_date', 'refund_method')
    search_fields = ('refund_reference', 'deposit__contract__contract_reference')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = (
        'property', 'unit', 'tenant', 'priority',
        'status', 'request_date', 'cost',
    )
    list_filter = ('priority', 'status', 'request_date')
    search_fields = ('property__name', 'issue')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('property', 'unit', 'tenant'),
        }),
        ('Request Details', {
            'fields': ('issue', 'priority', 'status', 'request_date', 'cost'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        'expense_reference', 'category', 'amount',
        'expense_date', 'status', 'property', 'unit',
    )
    list_filter = ('category', 'status', 'expense_date')
    search_fields = ('expense_reference', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('expense_reference', 'category', 'status'),
        }),
        ('Amounts & Dates', {
            'fields': ('amount', 'expense_date', 'description'),
        }),
        ('Links', {
            'fields': ('property', 'unit', 'recorded_by'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
