from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel


class FinancialTransaction(TimeStampedModel):
    """
    A unified ledger row. `related_entity_type` + `related_entity_id` point
    generically at the source record (Invoice, Payment, Expense, DepositRefund,
    ...) instead of a hard FK, so this app doesn't need to import every other
    app's models. Create one of these whenever billing/operations records
    money moving.
    """
    class TransactionType(models.TextChoices):
        RENT_INCOME = 'rent_income', 'Rent Income'
        DEPOSIT = 'deposit', 'Deposit'
        DEPOSIT_REFUND = 'deposit_refund', 'Deposit Refund'
        EXPENSE = 'expense', 'Expense'
        OTHER = 'other', 'Other'

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='financial_transactions')
    transaction_reference = models.CharField(max_length=50, unique=True)
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_date = models.DateField()
    related_entity_type = models.CharField(max_length=50, blank=True, help_text="e.g. 'invoice', 'payment', 'expense'")
    related_entity_id = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.transaction_reference
