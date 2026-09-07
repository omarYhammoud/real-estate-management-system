"""
Waad — Billing & Payments forms.

- RentScheduleGenerationForm: "Rent Schedule" page — pick an active
  contract and generate its full schedule.
- InvoiceForm + InvoiceLineItemFormSet: "Create Invoice" page — a manual /
  ad-hoc invoice (e.g. a one-off charge) that isn't tied to a generated
  rent schedule row.
- PaymentForm: "Record Payment" page — apply a full or partial payment to
  one invoice.
- LateFeeForm: small form used from the Invoice Detail page to add a late
  fee as a line item.
"""
from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.properties.models import RentalContract

from .models import Invoice, InvoiceLineItem, Payment


class RentScheduleGenerationForm(forms.Form):
    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('annual', 'Annual'),
    ]

    contract = forms.ModelChoiceField(
        queryset=RentalContract.objects.filter(status=RentalContract.Status.ACTIVE).select_related('tenant', 'unit'),
        help_text='Only active contracts without an existing schedule are listed.',
    )
    frequency = forms.ChoiceField(choices=FREQUENCY_CHOICES, initial='monthly')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide contracts that already have a schedule — regenerating isn't
        # supported here to avoid duplicate/overlapping periods.
        self.fields['contract'].queryset = self.fields['contract'].queryset.exclude(rent_schedules__isnull=False)

    def clean_contract(self):
        contract = self.cleaned_data['contract']
        if contract.rent_schedules.exists():
            raise forms.ValidationError(
                'A rent schedule already exists for this contract.'
            )
        return contract


class InvoiceForm(forms.ModelForm):
    """Manual invoice header. invoice_reference is generated in the view,
    not entered here, so numbering stays consistent (e.g. INV-3F2A9C1D)."""

    class Meta:
        model = Invoice
        fields = ['contract', 'tenant', 'schedule', 'billing_period', 'issue_date', 'due_date']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['schedule'].required = False

    def clean(self):
        cleaned = super().clean()
        contract = cleaned.get('contract')
        tenant = cleaned.get('tenant')
        if contract and tenant and contract.tenant_id != tenant.id:
            raise forms.ValidationError('The selected tenant is not the tenant on this contract.')
        return cleaned


InvoiceLineItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceLineItem,
    fields=['description', 'quantity', 'unit_amount', 'tax_rate'],
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_date', 'amount', 'payment_method']
        widgets = {'payment_date': forms.DateInput(attrs={'type': 'date'})}

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        if invoice is not None:
            self.fields['amount'].initial = invoice.outstanding_balance

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError('Payment amount must be greater than zero.')
        if self.invoice is not None and amount > self.invoice.outstanding_balance:
            raise forms.ValidationError(
                f'Payment of {amount} exceeds the outstanding balance of '
                f'{self.invoice.outstanding_balance}.'
            )
        return amount


class LateFeeForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    reason = forms.CharField(max_length=255, required=False, initial='Late payment fee')