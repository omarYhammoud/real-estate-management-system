"""
ModelForms for Alyousof's Deposits & Operations module.
Validation enforces:
  - Deduction/Refund amounts must be positive.
  - Deduction/Refund amounts must not exceed remaining deposit balance.
"""
from decimal import Decimal
from django import forms
from django.db.models import Sum
from .models import SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense


class SecurityDepositForm(forms.ModelForm):
    class Meta:
        model = SecurityDeposit
        fields = ['contract', 'required_amount', 'received_amount', 'received_date', 'status']
        widgets = {
            'received_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_received_amount(self):
        amount = self.cleaned_data.get('received_amount')
        if amount is not None and amount < Decimal('0.00'):
            raise forms.ValidationError('Received amount cannot be negative.')
        return amount

    def clean_required_amount(self):
        amount = self.cleaned_data.get('required_amount')
        if amount is not None and amount < Decimal('0.00'):
            raise forms.ValidationError('Required amount cannot be negative.')
        return amount


class DepositDeductionForm(forms.ModelForm):
    """
    The deposit FK is injected by the view (not shown in form).
    Pass deposit instance via __init__ to enforce the remaining-balance rule.
    """

    class Meta:
        model = DepositDeduction
        fields = ['amount', 'reason', 'deduction_date', 'authorized_by']
        widgets = {
            'deduction_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, deposit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._deposit = deposit

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            return amount
        if amount <= Decimal('0.00'):
            raise forms.ValidationError('Deduction amount must be positive.')
        if self._deposit is not None:
            current_pk = self.instance.pk
            deducted = (
                self._deposit.deductions.exclude(pk=current_pk)
                .aggregate(total=Sum('amount'))['total']
                or Decimal('0.00')
            )
            refunded = (
                self._deposit.refunds
                .aggregate(total=Sum('amount'))['total']
                or Decimal('0.00')
            )
            available = self._deposit.received_amount - deducted - refunded
            if amount > available:
                raise forms.ValidationError(
                    f'Deduction amount ({amount}) exceeds the available balance ({available}).'
                )
        return amount


class DepositRefundForm(forms.ModelForm):
    """
    The deposit FK is injected by the view (not shown in form).
    Pass deposit instance via __init__ to enforce the remaining-balance rule.
    """

    class Meta:
        model = DepositRefund
        fields = ['amount', 'refund_date', 'refund_method', 'refund_reference', 'authorized_by']
        widgets = {
            'refund_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, deposit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._deposit = deposit

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            return amount
        if amount <= Decimal('0.00'):
            raise forms.ValidationError('Refund amount must be positive.')
        if self._deposit is not None:
            current_pk = self.instance.pk
            deducted = (
                self._deposit.deductions
                .aggregate(total=Sum('amount'))['total']
                or Decimal('0.00')
            )
            refunded = (
                self._deposit.refunds.exclude(pk=current_pk)
                .aggregate(total=Sum('amount'))['total']
                or Decimal('0.00')
            )
            available = self._deposit.received_amount - deducted - refunded
            if amount > available:
                raise forms.ValidationError(
                    f'Refund amount ({amount}) exceeds the available balance ({available}).'
                )
        return amount


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = ['property', 'unit', 'tenant', 'issue', 'priority', 'status', 'request_date', 'cost']
        widgets = {
            'request_date': forms.DateInput(attrs={'type': 'date'}),
            'issue': forms.Textarea(attrs={'rows': 4}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'property', 'unit', 'recorded_by',
            'expense_reference', 'category', 'amount',
            'expense_date', 'description', 'status',
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= Decimal('0.00'):
            raise forms.ValidationError('Expense amount must be positive.')
        return amount
