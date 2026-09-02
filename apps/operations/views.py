"""
Alyousof — Deposits & Operations views.
All views require login (LoginRequiredMixin).
Pattern: Django class-based generic views.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView,
)

from .models import SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense
from .forms import (
    SecurityDepositForm, DepositDeductionForm, DepositRefundForm,
    MaintenanceRequestForm, ExpenseForm,
)


# ---------------------------------------------------------------------------
# Security Deposits
# ---------------------------------------------------------------------------

class SecurityDepositListView(LoginRequiredMixin, ListView):
    model = SecurityDeposit
    template_name = 'operations/deposit_list.html'
    context_object_name = 'deposits'
    paginate_by = 20


class SecurityDepositDetailView(LoginRequiredMixin, DetailView):
    model = SecurityDeposit
    template_name = 'operations/deposit_detail.html'
    context_object_name = 'deposit'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['deductions'] = self.object.deductions.select_related('authorized_by')
        ctx['refunds'] = self.object.refunds.select_related('authorized_by')
        return ctx


class SecurityDepositCreateView(LoginRequiredMixin, CreateView):
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


class SecurityDepositUpdateView(LoginRequiredMixin, UpdateView):
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

class DepositDeductionCreateView(LoginRequiredMixin, CreateView):
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
        messages.success(self.request, 'Deduction added successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('operations:deposit_detail', kwargs={'pk': self.kwargs['deposit_pk']})


# ---------------------------------------------------------------------------
# Deposit Refunds
# ---------------------------------------------------------------------------

class DepositRefundCreateView(LoginRequiredMixin, CreateView):
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
        messages.success(self.request, 'Refund recorded successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('operations:deposit_detail', kwargs={'pk': self.kwargs['deposit_pk']})


# ---------------------------------------------------------------------------
# Maintenance Requests
# ---------------------------------------------------------------------------

class MaintenanceListView(LoginRequiredMixin, ListView):
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


class MaintenanceDetailView(LoginRequiredMixin, DetailView):
    model = MaintenanceRequest
    template_name = 'operations/maintenance_detail.html'
    context_object_name = 'maintenance'


class MaintenanceCreateView(LoginRequiredMixin, CreateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'operations/maintenance_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Maintenance request created successfully.')
        return reverse_lazy('operations:maintenance_detail', kwargs={'pk': self.object.pk})


class MaintenanceUpdateView(LoginRequiredMixin, UpdateView):
    model = MaintenanceRequest
    form_class = MaintenanceRequestForm
    template_name = 'operations/maintenance_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Maintenance request updated successfully.')
        return reverse_lazy('operations:maintenance_detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

class ExpenseListView(LoginRequiredMixin, ListView):
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


class ExpenseDetailView(LoginRequiredMixin, DetailView):
    model = Expense
    template_name = 'operations/expense_detail.html'
    context_object_name = 'expense'


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'operations/expense_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Expense recorded successfully.')
        return reverse_lazy('operations:expense_detail', kwargs={'pk': self.object.pk})


class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'operations/expense_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Expense updated successfully.')
        return reverse_lazy('operations:expense_detail', kwargs={'pk': self.object.pk})
