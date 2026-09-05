"""
Alyousof — Deposits & Operations views.
All views enforce role-based access through RoleRequiredMixin.
Pattern: Django class-based generic views.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView,
)

from apps.core.mixins import RoleRequiredMixin

from .models import SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense
from .forms import (
    SecurityDepositForm, DepositDeductionForm, DepositRefundForm,
    MaintenanceRequestForm, ExpenseForm,
)


User = get_user_model()


class FinancialOperationsMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.ACCOUNTANT)


class MaintenanceOperationsMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.PROPERTY_MANAGER)


# ---------------------------------------------------------------------------
# Security Deposits
# ---------------------------------------------------------------------------

class SecurityDepositListView(FinancialOperationsMixin, ListView):
    model = SecurityDeposit
    template_name = 'operations/deposit_list.html'
    context_object_name = 'deposits'
    paginate_by = 20


class SecurityDepositDetailView(FinancialOperationsMixin, DetailView):
    model = SecurityDeposit
    template_name = 'operations/deposit_detail.html'
    context_object_name = 'deposit'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['deductions'] = self.object.deductions.select_related('authorized_by')
        ctx['refunds'] = self.object.refunds.select_related('authorized_by')
        return ctx


class SecurityDepositCreateView(FinancialOperationsMixin, CreateView):
    model = SecurityDeposit
    form_class = SecurityDepositForm
    template_name = 'operations/deposit_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Security deposit created successfully.')
        return reverse_lazy('operations:deposit_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        # Initialise remaining_balance to received_amount on creation
        self.object.recalc_remaining_balance()
        return response


class SecurityDepositUpdateView(FinancialOperationsMixin, UpdateView):
    model = SecurityDeposit
    form_class = SecurityDepositForm
    template_name = 'operations/deposit_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Security deposit updated successfully.')
        return reverse_lazy('operations:deposit_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.recalc_remaining_balance()
        return response


# ---------------------------------------------------------------------------
# Deposit Deductions
# ---------------------------------------------------------------------------

class DepositDeductionListView(FinancialOperationsMixin, ListView):
    model = DepositDeduction
    template_name = 'operations/deduction_list.html'
    context_object_name = 'deductions'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related(
            'deposit__contract',
            'deposit__contract__tenant',
            'authorized_by',
        )


class DepositDeductionDetailView(FinancialOperationsMixin, DetailView):
    model = DepositDeduction
    template_name = 'operations/deduction_detail.html'
    context_object_name = 'deduction'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'deposit__contract',
            'deposit__contract__tenant',
            'authorized_by',
        )


class DepositDeductionCreateView(FinancialOperationsMixin, CreateView):
    model = DepositDeduction
    form_class = DepositDeductionForm
    template_name = 'operations/deduction_form.html'

    def _get_deposit(self):
        return get_object_or_404(SecurityDeposit, pk=self.kwargs['deposit_pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['deposit'] = self._get_deposit()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['deposit'] = self._get_deposit()
        return ctx

    def form_valid(self, form):
        form.instance.deposit = self._get_deposit()
        form.instance.authorized_by = self.request.user
        messages.success(self.request, 'Deduction added successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('operations:deposit_detail', kwargs={'pk': self.kwargs['deposit_pk']})


# ---------------------------------------------------------------------------
# Deposit Refunds
# ---------------------------------------------------------------------------

class DepositRefundListView(FinancialOperationsMixin, ListView):
    model = DepositRefund
    template_name = 'operations/refund_list.html'
    context_object_name = 'refunds'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().select_related(
            'deposit__contract',
            'deposit__contract__tenant',
            'authorized_by',
        )


class DepositRefundDetailView(FinancialOperationsMixin, DetailView):
    model = DepositRefund
    template_name = 'operations/refund_detail.html'
    context_object_name = 'refund'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'deposit__contract',
            'deposit__contract__tenant',
            'authorized_by',
        )


class DepositRefundCreateView(FinancialOperationsMixin, CreateView):
    model = DepositRefund
    form_class = DepositRefundForm
    template_name = 'operations/refund_form.html'

    def _get_deposit(self):
        return get_object_or_404(SecurityDeposit, pk=self.kwargs['deposit_pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['deposit'] = self._get_deposit()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['deposit'] = self._get_deposit()
        return ctx

    def form_valid(self, form):
        form.instance.deposit = self._get_deposit()
        form.instance.authorized_by = self.request.user
        messages.success(self.request, 'Refund recorded successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('operations:deposit_detail', kwargs={'pk': self.kwargs['deposit_pk']})


# ---------------------------------------------------------------------------
# Maintenance Requests
# ---------------------------------------------------------------------------

class MaintenanceListView(MaintenanceOperationsMixin, ListView):
    model = MaintenanceRequest
    template_name = 'operations/maintenance_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('property', 'unit', 'tenant')
        status = self.request.GET.get('status')
        priority = self.request.GET.get('priority')
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = MaintenanceRequest.Status.choices
        ctx['priority_choices'] = MaintenanceRequest.Priority.choices
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_priority'] = self.request.GET.get('priority', '')
        return ctx


class MaintenanceDetailView(MaintenanceOperationsMixin, DetailView):
    model = MaintenanceRequest
    template_name = 'operations/maintenance_detail.html'
    context_object_name = 'maintenance'


class MaintenanceCreateView(MaintenanceOperationsMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'operations/maintenance_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Maintenance request created successfully.')
        return reverse_lazy('operations:maintenance_detail', kwargs={'pk': self.object.pk})


class MaintenanceUpdateView(MaintenanceOperationsMixin, UpdateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'operations/maintenance_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Maintenance request updated successfully.')
        return reverse_lazy('operations:maintenance_detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

class ExpenseListView(FinancialOperationsMixin, ListView):
    model = Expense
    template_name = 'operations/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('property', 'unit', 'recorded_by')
        category = self.request.GET.get('category')
        status = self.request.GET.get('status')
        if category:
            qs = qs.filter(category=category)
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['category_choices'] = Expense.Category.choices
        ctx['status_choices'] = Expense.ExpenseStatus.choices
        ctx['current_category'] = self.request.GET.get('category', '')
        ctx['current_status'] = self.request.GET.get('status', '')
        return ctx


class ExpenseDetailView(FinancialOperationsMixin, DetailView):
    model = Expense
    template_name = 'operations/expense_detail.html'
    context_object_name = 'expense'


class ExpenseCreateView(FinancialOperationsMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'operations/expense_form.html'

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, 'Expense recorded successfully.')
        return reverse_lazy('operations:expense_detail', kwargs={'pk': self.object.pk})


class ExpenseUpdateView(FinancialOperationsMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'operations/expense_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Expense updated successfully.')
        return reverse_lazy('operations:expense_detail', kwargs={'pk': self.object.pk})
