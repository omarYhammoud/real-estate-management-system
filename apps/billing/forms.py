from django import forms
from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_reference', 'payment_date', 'amount', 'payment_method']
        widgets = {'payment_date': forms.DateInput(attrs={'type': 'date'})}
