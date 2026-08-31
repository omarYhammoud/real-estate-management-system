"""
Owner: Alyousof — Deposits & Operations.
Models: SecurityDeposit, DepositDeduction, DepositRefund, MaintenanceRequest, Expense.
"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel
from apps.properties.models import RentalContract, Property, Unit, Tenant


class SecurityDeposit(TimeStampedModel):
    class Status(models.TextChoices):
        HELD = 'held', 'Held'
        PARTIALLY_REFUNDED = 'partially_refunded', 'Partially Refunded'
        REFUNDED = 'refunded', 'Refunded'

    contract = models.OneToOneField(RentalContract, on_delete=models.PROTECT, related_name='security_deposit')
    required_amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    received_date = models.DateField(null=True, blank=True)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.HELD)

    def recalc_remaining_balance(self, save=True):
        deducted = self.deductions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        refunded = self.refunds.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        self.remaining_balance = self.received_amount - deducted - refunded
        if save:
            self.save(update_fields=['remaining_balance'])

    def __str__(self):
        return f"Deposit for {self.contract.contract_reference}"


class DepositDeduction(TimeStampedModel):
    deposit = models.ForeignKey(SecurityDeposit, on_delete=models.CASCADE, related_name='deductions')
    authorized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='authorized_deductions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    deduction_date = models.DateField()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.deposit.recalc_remaining_balance()

    def __str__(self):
        return f"Deduction {self.amount} — {self.deposit}"


class DepositRefund(TimeStampedModel):
    deposit = models.ForeignKey(SecurityDeposit, on_delete=models.CASCADE, related_name='refunds')
    authorized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='authorized_refunds')
    refund_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_method = models.CharField(max_length=30, blank=True)
    refund_reference = models.CharField(max_length=50, unique=True)

    def clean(self):
        """Business rule (Alyousof): Deposit Refund <= Remaining Deposit."""
        from django.core.exceptions import ValidationError
        if self.amount and self.amount > self.deposit.remaining_balance:
            raise ValidationError("Refund amount cannot exceed the remaining deposit balance.")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.deposit.recalc_remaining_balance()

    def __str__(self):
        return self.refund_reference


class MaintenanceRequest(TimeStampedModel):
    class Priority(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        URGENT = 'urgent', 'Urgent'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED = 'closed', 'Closed'

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='maintenance_requests')
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_requests')
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_requests')
    issue = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    request_date = models.DateField()
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.property.name} — {self.issue[:40]}"


class Expense(TimeStampedModel):
    class Category(models.TextChoices):
        MAINTENANCE = 'maintenance', 'Maintenance'
        UTILITIES = 'utilities', 'Utilities'
        INSURANCE = 'insurance', 'Insurance'
        TAXES = 'taxes', 'Taxes'
        OTHER = 'other', 'Other'

    property = models.ForeignKey(Property, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_expenses')
    expense_reference = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='recorded')

    def __str__(self):
        return self.expense_reference
