from django import forms

from apps.properties.models import Property, Tenant

from .models import FinancialTransaction


class DateRangeForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError('Start date cannot be after end date.')
        return cleaned_data


class TransactionFilterForm(DateRangeForm):
    transaction_type = forms.ChoiceField(
        required=False,
        choices=(('', 'All transaction types'),) + tuple(FinancialTransaction.TransactionType.choices),
    )


class TenantStatementFilterForm(DateRangeForm):
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.order_by('full_name'),
        required=False,
        empty_label='Select a tenant',
    )


class PropertyPerformanceFilterForm(DateRangeForm):
    property = forms.ModelChoiceField(
        queryset=Property.objects.order_by('name'),
        required=False,
        empty_label='All properties',
    )
