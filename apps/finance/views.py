"""
Chaheen: build the Dashboard (KPIs) and the report views here (Profit & Loss,
Revenue Summary, Expense Summary, Outstanding Receivables, Payment Report,
Transaction Report, Tenant Statement, Property Financial Performance).
Restrict each view to the correct roles using apps.core.mixins.RoleRequiredMixin.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.views.generic import TemplateView

from apps.billing.models import Invoice, Payment, Receipt, RentSchedule
from apps.core.mixins import RoleRequiredMixin
from apps.operations.models import DepositRefund, Expense, SecurityDeposit
from apps.properties.models import Property, RentalContract, Tenant, Unit

from .forms import (
    DateRangeForm,
    PropertyPerformanceFilterForm,
    TenantStatementFilterForm,
    TransactionFilterForm,
)
from .models import FinancialTransaction


User = get_user_model()
ZERO = Decimal('0.00')


def receivable_rows(queryset, include_zero=False):
    invoices = queryset.annotate(
        paid_amount=Coalesce(Sum('payments__amount'), ZERO)
    ).select_related('tenant', 'contract')
    rows = []
    for invoice in invoices:
        outstanding = max(invoice.total_amount - invoice.paid_amount, ZERO)
        if include_zero or outstanding > ZERO:
            rows.append({'invoice': invoice, 'outstanding_balance': outstanding})
    return rows


class OwnerFinanceScopeMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == User.Role.OWNER:
            try:
                request.user.owner_profile
            except User.owner_profile.RelatedObjectDoesNotExist as exc:
                raise PermissionDenied('No owner profile is linked to this account.') from exc
        return super().dispatch(request, *args, **kwargs)

    def owner_properties(self):
        if self.request.user.role == User.Role.OWNER:
            return Property.objects.filter(owner=self.request.user.owner_profile)
        return Property.objects.all()

    def scope_units(self, queryset):
        if self.request.user.role == User.Role.OWNER:
            return queryset.filter(property__owner=self.request.user.owner_profile)
        return queryset

    def scope_contracts(self, queryset):
        if self.request.user.role == User.Role.OWNER:
            return queryset.filter(unit__property__owner=self.request.user.owner_profile)
        return queryset

    def scope_invoices(self, queryset):
        if self.request.user.role == User.Role.OWNER:
            return queryset.filter(
                contract__unit__property__owner=self.request.user.owner_profile
            )
        return queryset

    def scope_payments(self, queryset):
        if self.request.user.role == User.Role.OWNER:
            return queryset.filter(
                invoice__contract__unit__property__owner=self.request.user.owner_profile
            )
        return queryset

    def scope_expenses(self, queryset):
        if self.request.user.role == User.Role.OWNER:
            owner = self.request.user.owner_profile
            return queryset.filter(
                Q(property__owner=owner) | Q(unit__property__owner=owner)
            ).distinct()
        return queryset

    def scope_transactions(self, queryset):
        if self.request.user.role != User.Role.OWNER:
            return queryset
        owner = self.request.user.owner_profile
        payment_ids = Payment.objects.filter(
            invoice__contract__unit__property__owner=owner
        ).values('pk')
        expense_ids = Expense.objects.filter(
            Q(property__owner=owner) | Q(unit__property__owner=owner)
        ).values('pk')
        deposit_ids = SecurityDeposit.objects.filter(
            contract__unit__property__owner=owner
        ).values('pk')
        refund_ids = DepositRefund.objects.filter(
            deposit__contract__unit__property__owner=owner
        ).values('pk')
        return queryset.filter(
            Q(related_entity_type='payment', related_entity_id__in=payment_ids)
            | Q(related_entity_type='expense', related_entity_id__in=expense_ids)
            | Q(
                related_entity_type='security_deposit',
                related_entity_id__in=deposit_ids,
            )
            | Q(
                related_entity_type='deposit_refund',
                related_entity_id__in=refund_ids,
            )
        )


class FinancialReportMixin(OwnerFinanceScopeMixin, RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.ACCOUNTANT, User.Role.OWNER)


class DateFilteredReportMixin(FinancialReportMixin):
    filter_form_class = DateRangeForm

    def get_filter_form(self):
        if not hasattr(self, '_filter_form'):
            self._filter_form = self.filter_form_class(self.request.GET or None)
            self._filter_form.is_valid()
        return self._filter_form

    def filter_by_date(self, queryset, field_name):
        form = self.get_filter_form()
        if not form.is_bound:
            return queryset
        if not form.is_valid():
            return queryset.none()
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        if start_date:
            queryset = queryset.filter(**{f'{field_name}__gte': start_date})
        if end_date:
            queryset = queryset.filter(**{f'{field_name}__lte': end_date})
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.get_filter_form()
        return context


class DashboardView(OwnerFinanceScopeMixin, RoleRequiredMixin, TemplateView):
    template_name = 'finance/dashboard.html'
    allowed_roles = (
        User.Role.ADMIN,
        User.Role.PROPERTY_MANAGER,
        User.Role.ACCOUNTANT,
        User.Role.OWNER,
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        zero = Decimal('0.00')

        properties = self.owner_properties()
        units = self.scope_units(Unit.objects.all())
        contracts = self.scope_contracts(RentalContract.objects.all())
        unit_counts = units.aggregate(
            total=Count('pk'),
            occupied=Count('pk', filter=Q(status=Unit.Status.OCCUPIED)),
        )
        total_units = unit_counts['total']
        occupied_units = unit_counts['occupied']
        occupancy_rate = (
            (Decimal(occupied_units) / Decimal(total_units) * Decimal('100'))
            if total_units
            else zero
        )

        rent_schedules = RentSchedule.objects.all()
        if self.request.user.role == User.Role.OWNER:
            rent_schedules = rent_schedules.filter(
                contract__unit__property__owner=self.request.user.owner_profile
            )
        rent_due = rent_schedules.filter(
            status__in=(RentSchedule.Status.PENDING, RentSchedule.Status.INVOICED),
            due_date__lte=timezone.localdate(),
        ).aggregate(total=Sum('expected_amount'))['total'] or zero

        transactions = self.scope_transactions(FinancialTransaction.objects.all())
        transaction_totals = transactions.aggregate(
            rent_income=Sum(
                'amount',
                filter=Q(
                    transaction_type=FinancialTransaction.TransactionType.RENT_INCOME
                ),
            ),
            expenses=Sum(
                'amount',
                filter=Q(
                    transaction_type=FinancialTransaction.TransactionType.EXPENSE
                ),
            ),
        )
        collected_rent = transaction_totals['rent_income'] or zero
        total_expenses = transaction_totals['expenses'] or zero

        invoice_balances = self.scope_invoices(Invoice.objects.all()).annotate(
            paid_amount=Coalesce(Sum('payments__amount'), zero)
        ).values_list('total_amount', 'paid_amount')
        outstanding_rent = sum(
            (max(total_amount - paid_amount, zero)
             for total_amount, paid_amount in invoice_balances),
            zero,
        )

        revenue = collected_rent
        context.update({
            'total_properties': properties.count(),
            'total_units': total_units,
            'occupied_units': occupied_units,
            'occupancy_rate': occupancy_rate,
            'active_contracts': contracts.filter(
                status=RentalContract.Status.ACTIVE
            ).count(),
            'rent_due': rent_due,
            'collected_rent': collected_rent,
            'outstanding_rent': outstanding_rent,
            'total_expenses': total_expenses,
            'revenue': revenue,
            'profit_loss': revenue - total_expenses,
            'recent_transactions': transactions.order_by(
                '-transaction_date', '-pk'
            )[:5],
        })
        return context


class ReportIndexView(FinancialReportMixin, TemplateView):
    template_name = 'finance/reports/index.html'


class ProfitLossReportView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/profit_loss.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transactions = self.filter_by_date(
            self.scope_transactions(FinancialTransaction.objects.all()),
            'transaction_date',
        )
        totals = transactions.aggregate(
            revenue=Sum('amount', filter=Q(transaction_type=FinancialTransaction.TransactionType.RENT_INCOME)),
            expenses=Sum('amount', filter=Q(transaction_type=FinancialTransaction.TransactionType.EXPENSE)),
        )
        revenue = totals['revenue'] or ZERO
        expenses = totals['expenses'] or ZERO
        context.update({'revenue': revenue, 'expenses': expenses, 'profit_loss': revenue - expenses})
        return context


class RevenueSummaryView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/revenue.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transactions = self.filter_by_date(
            self.scope_transactions(FinancialTransaction.objects.filter(
                transaction_type=FinancialTransaction.TransactionType.RENT_INCOME
            )), 'transaction_date'
        ).select_related('recorded_by')
        summary = transactions.aggregate(total=Sum('amount'), count=Count('pk'))
        context.update({
            'transactions': transactions.order_by('-transaction_date', '-pk'),
            'total_revenue': summary['total'] or ZERO,
            'transaction_count': summary['count'],
            'monthly_revenue': transactions.annotate(month=TruncMonth('transaction_date')).values('month').annotate(total=Sum('amount')).order_by('month'),
        })
        return context


class ExpenseSummaryView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/expenses.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expenses = self.filter_by_date(
            self.scope_expenses(Expense.objects.exclude(
                status=Expense.ExpenseStatus.CANCELLED
            )).select_related('property', 'unit', 'recorded_by'),
            'expense_date',
        )
        summary = expenses.aggregate(total=Sum('amount'), count=Count('pk'))
        labels = dict(Expense.Category.choices)
        breakdown = list(expenses.values('category').annotate(total=Sum('amount'), count=Count('pk')).order_by('category'))
        for row in breakdown:
            row['label'] = labels.get(row['category'], row['category'])
        context.update({
            'expenses': expenses.order_by('-expense_date', '-pk'),
            'total_expenses': summary['total'] or ZERO,
            'expense_count': summary['count'],
            'category_breakdown': breakdown,
        })
        return context


class OutstandingReceivablesView(FinancialReportMixin, TemplateView):
    template_name = 'finance/reports/receivables.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = receivable_rows(
            self.scope_invoices(Invoice.objects.all()).order_by('due_date')
        )
        context.update({'receivables': rows, 'total_outstanding': sum((row['outstanding_balance'] for row in rows), ZERO)})
        return context


class PaymentReportView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/payments.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payments = self.filter_by_date(
            self.scope_payments(Payment.objects.all()).select_related(
                'tenant', 'invoice', 'recorded_by'
            ),
            'payment_date',
        )
        context.update({'payments': payments.order_by('-payment_date', '-pk'), 'total_payments': payments.aggregate(total=Sum('amount'))['total'] or ZERO})
        return context


class TransactionReportView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/transactions.html'
    filter_form_class = TransactionFilterForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transactions = self.filter_by_date(
            self.scope_transactions(FinancialTransaction.objects.all()).select_related(
                'recorded_by'
            ),
            'transaction_date',
        )
        form = self.get_filter_form()
        if form.is_valid() and form.cleaned_data.get('transaction_type'):
            transactions = transactions.filter(transaction_type=form.cleaned_data['transaction_type'])
        context.update({
            'transactions': transactions.order_by('-transaction_date', '-pk'),
            'transaction_count': transactions.count(),
            'type_totals': transactions.values('transaction_type').annotate(total=Sum('amount'), count=Count('pk')).order_by('transaction_type'),
        })
        return context


class TenantStatementView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/tenant_statement.html'
    filter_form_class = TenantStatementFilterForm
    allowed_roles = (
        User.Role.ADMIN,
        User.Role.ACCOUNTANT,
        User.Role.OWNER,
        User.Role.TENANT,
    )

    def get_filter_form(self):
        if hasattr(self, '_filter_form'):
            return self._filter_form

        data = self.request.GET.copy()
        kwargs = {}
        if self.request.user.role == User.Role.TENANT:
            try:
                tenant = self.request.user.tenant_profile
            except User.tenant_profile.RelatedObjectDoesNotExist as exc:
                raise PermissionDenied(
                    'No tenant profile is linked to this account.'
                ) from exc
            data['tenant'] = tenant.pk
            kwargs.update(
                tenant_queryset=Tenant.objects.filter(pk=tenant.pk),
                fixed_tenant=tenant,
            )
        elif self.request.user.role == User.Role.OWNER:
            kwargs['tenant_queryset'] = Tenant.objects.filter(
                contracts__unit__property__owner=self.request.user.owner_profile
            ).distinct()

        self._filter_form = self.filter_form_class(data or None, **kwargs)
        self._filter_form.is_valid()
        return self._filter_form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_filter_form()
        tenant = form.cleaned_data.get('tenant') if form.is_valid() else None
        context['selected_tenant'] = tenant
        if not tenant:
            return context
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        payment_period = Q()
        if start_date:
            payment_period &= Q(payments__payment_date__gte=start_date)
        if end_date:
            payment_period &= Q(payments__payment_date__lte=end_date)
        invoices = self.filter_by_date(
            self.scope_invoices(Invoice.objects.filter(tenant=tenant)),
            'issue_date',
        )
        period_invoices = invoices.annotate(
            period_paid=Coalesce(
                Sum('payments__amount', filter=payment_period),
                ZERO,
            )
        ).select_related('contract').order_by('issue_date')
        rows = [
            {
                'invoice': invoice,
                'period_paid': invoice.period_paid,
                'period_invoice_net': invoice.total_amount - invoice.period_paid,
            }
            for invoice in period_invoices
        ]
        payments = self.filter_by_date(
            self.scope_payments(Payment.objects.filter(tenant=tenant)).select_related(
                'invoice', 'recorded_by'
            ),
            'payment_date',
        )
        receipts = Receipt.objects.filter(payment__in=payments).select_related('payment')
        total_invoiced = invoices.aggregate(total=Sum('total_amount'))['total'] or ZERO
        total_paid = payments.aggregate(total=Sum('amount'))['total'] or ZERO
        context.update({
            'contracts': self.scope_contracts(tenant.contracts.all()).select_related(
                'unit', 'unit__property'
            ),
            'invoice_rows': rows,
            'payments': payments.order_by('payment_date'),
            'receipts': receipts.order_by('receipt_date'),
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'period_net_balance': total_invoiced - total_paid,
            'has_date_filter': bool(start_date or end_date),
        })
        return context


class PropertyPerformanceView(DateFilteredReportMixin, TemplateView):
    template_name = 'finance/reports/property_performance.html'
    filter_form_class = PropertyPerformanceFilterForm

    def get_filter_form(self):
        if not hasattr(self, '_filter_form'):
            properties = self.owner_properties().order_by('name')
            self._filter_form = self.filter_form_class(
                self.request.GET or None,
                property_queryset=properties,
            )
            self._filter_form.is_valid()
        return self._filter_form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_filter_form()
        selected_property = form.cleaned_data.get('property') if form.is_valid() else None
        properties = self.owner_properties().annotate(
            unit_count=Count('units', distinct=True),
            occupied_count=Count('units', filter=Q(units__status=Unit.Status.OCCUPIED), distinct=True),
            active_contract_count=Count('units__contracts', filter=Q(units__contracts__status=RentalContract.Status.ACTIVE), distinct=True),
        ).order_by('name')
        if selected_property:
            properties = properties.filter(pk=selected_property.pk)
        property_ids = list(properties.values_list('pk', flat=True))
        payments = self.filter_by_date(Payment.objects.filter(invoice__contract__unit__property_id__in=property_ids), 'payment_date')
        expenses = self.filter_by_date(
            Expense.objects.filter(
                Q(property_id__in=property_ids)
                | Q(property__isnull=True, unit__property_id__in=property_ids)
            ).exclude(
                status=Expense.ExpenseStatus.CANCELLED
            ).annotate(
                performance_property_id=Coalesce('property_id', 'unit__property_id')
            ),
            'expense_date',
        )
        revenue_map = dict(payments.values('invoice__contract__unit__property_id').annotate(total=Sum('amount')).values_list('invoice__contract__unit__property_id', 'total'))
        expense_map = dict(expenses.values('performance_property_id').annotate(total=Sum('amount')).values_list('performance_property_id', 'total'))
        rows = []
        for property_object in properties:
            revenue = revenue_map.get(property_object.pk, ZERO)
            expense_total = expense_map.get(property_object.pk, ZERO)
            occupancy_rate = (Decimal(property_object.occupied_count) / Decimal(property_object.unit_count) * Decimal('100')) if property_object.unit_count else ZERO
            rows.append({'property': property_object, 'revenue': revenue, 'expenses': expense_total, 'profit_loss': revenue - expense_total, 'occupancy_rate': occupancy_rate})
        context.update({'selected_property': selected_property, 'property_rows': rows, 'total_revenue': sum((row['revenue'] for row in rows), ZERO), 'total_expenses': sum((row['expenses'] for row in rows), ZERO), 'total_profit_loss': sum((row['profit_loss'] for row in rows), ZERO)})
        return context
