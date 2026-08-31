"""
Owner: Waad — Billing & Payments.
Models: RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt.
"""
from decimal import Decimal
from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel
from apps.properties.models import RentalContract, Tenant


class RentSchedule(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        INVOICED = 'invoiced', 'Invoiced'
        CANCELLED = 'cancelled', 'Cancelled'

    contract = models.ForeignKey(RentalContract, on_delete=models.CASCADE, related_name='rent_schedules')
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    due_date = models.DateField()
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    def __str__(self):
        return f"Schedule {self.contract.contract_reference} ({self.billing_period_start} – {self.billing_period_end})"


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PARTIALLY_PAID = 'partially_paid', 'Partially Paid'
        PAID = 'paid', 'Paid'

    contract = models.ForeignKey(RentalContract, on_delete=models.PROTECT, related_name='invoices')
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='invoices')
    schedule = models.ForeignKey(RentSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    invoice_reference = models.CharField(max_length=50, unique=True)
    billing_period = models.CharField(max_length=50, blank=True)
    issue_date = models.DateField()
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)

    def recalculate_totals(self, save=True):
        """subtotal/tax/total derived from line items — call after line items change."""
        lines = self.line_items.all()
        self.subtotal = sum((l.taxable_amount for l in lines), Decimal('0.00'))
        self.tax_total = sum((l.tax_amount for l in lines), Decimal('0.00'))
        self.total_amount = self.subtotal + self.tax_total
        if save:
            self.save(update_fields=['subtotal', 'tax_total', 'total_amount'])

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def outstanding_balance(self):
        return self.total_amount - self.amount_paid

    def refresh_status(self, save=True):
        """Business rule (Waad): status derives from amount_paid vs total_amount."""
        if self.amount_paid <= 0:
            self.status = self.Status.UNPAID
        elif self.amount_paid < self.total_amount:
            self.status = self.Status.PARTIALLY_PAID
        else:
            self.status = self.Status.PAID
        if save:
            self.save(update_fields=['status'])

    def __str__(self):
        return self.invoice_reference


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'))
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.taxable_amount = self.quantity * self.unit_amount
        self.tax_amount = (self.taxable_amount * self.tax_rate / Decimal('100')).quantize(Decimal('0.01'))
        self.line_total = self.taxable_amount + self.tax_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.description} ({self.invoice.invoice_reference})"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        CARD = 'card', 'Card'
        CHEQUE = 'cheque', 'Cheque'

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='payments')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_payments')
    payment_reference = models.CharField(max_length=50, unique=True)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=Method.choices)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Keep invoice status in sync (full / partial / multiple payments supported).
        self.invoice.refresh_status()

    def __str__(self):
        return self.payment_reference


class Receipt(TimeStampedModel):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name='receipt')
    receipt_reference = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.receipt_reference
