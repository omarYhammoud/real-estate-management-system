"""
Owner: Waad — Billing & Payments.
Models: RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt.
"""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
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

    def clean(self):
        super().clean()
        errors = {}
        if self.expected_amount is not None and self.expected_amount <= Decimal('0.00'):
            errors['expected_amount'] = 'Expected amount must be positive.'
        if (
            self.billing_period_start
            and self.billing_period_end
            and self.billing_period_start > self.billing_period_end
        ):
            errors['billing_period_end'] = (
                'Billing period end cannot precede its start.'
            )
        if errors:
            raise ValidationError(errors)
        if self.contract_id and self.billing_period_start and self.billing_period_end:
            duplicate = type(self).objects.filter(
                contract_id=self.contract_id,
                billing_period_start=self.billing_period_start,
                billing_period_end=self.billing_period_end,
            ).exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError(
                    'A rent schedule already exists for this contract and period.'
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

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

    @property
    def is_overdue(self):
        """Not a stored field — computed each time from status + due_date,
        so it can never drift out of sync the way a cached flag could."""
        from django.utils import timezone
        return self.status != self.Status.PAID and self.due_date < timezone.localdate()

    def add_late_fee(self, amount, reason='Late payment fee'):
        """Business rule (Waad): record a late fee as an invoice line item
        (0% tax) and immediately recompute totals + status."""
        InvoiceLineItem.objects.create(
            invoice=self,
            description=reason,
            quantity=Decimal('1.00'),
            unit_amount=amount,
            tax_rate=Decimal('0.00'),
        )
        self.recalculate_totals()
        self.refresh_status()

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


# Late fees are deliberately NOT a separate field on Invoice. Adding one as
# an ordinary InvoiceLineItem means it flows through the exact same
# subtotal/tax/total calculation as rent or any other charge, instead of
# needing its own parallel set of rules. See Invoice.add_late_fee() below.


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
        CARD = 'card', 'Card'
        CHEQUE = 'cheque', 'Cheque'

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='payments')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_payments')
    payment_reference = models.CharField(max_length=50, unique=True)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=Method.choices)

    def clean(self):
        super().clean()
        if self.amount is not None and self.amount <= Decimal('0.00'):
            raise ValidationError({'amount': 'Payment amount must be positive.'})
        if self.invoice_id and self.tenant_id != self.invoice.tenant_id:
            raise ValidationError({
                'tenant': 'Payment tenant must match the invoice tenant.'
            })
        if self.invoice_id and self.amount is not None:
            already_paid = (
                type(self).objects.filter(invoice_id=self.invoice_id)
                .exclude(pk=self.pk)
                .aggregate(total=models.Sum('amount'))['total']
                or Decimal('0.00')
            )
            if already_paid + self.amount > self.invoice.total_amount:
                raise ValidationError({
                    'amount': 'Payment amount exceeds the outstanding invoice balance.'
                })

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        original_values = {}
        excluded_fields = []
        old_invoice_id = None

        if not self._state.adding:
            persisted = type(self).objects.get(pk=self.pk)
            old_invoice_id = persisted.invoice_id
            if update_fields is not None:
                update_fields = set(update_fields)
                for field in self._meta.concrete_fields:
                    if field.name not in update_fields and field.attname not in update_fields:
                        excluded_fields.append(field.name)
                        original_values[field.attname] = getattr(self, field.attname)
                        setattr(self, field.attname, getattr(persisted, field.attname))

        try:
            self.full_clean(exclude=excluded_fields)
        finally:
            for field_name, value in original_values.items():
                setattr(self, field_name, value)

        super().save(*args, **kwargs)
        saved = type(self).objects.get(pk=self.pk)
        saved.invoice.refresh_status()
        if old_invoice_id and old_invoice_id != saved.invoice_id:
            Invoice.objects.get(pk=old_invoice_id).refresh_status()

    def __str__(self):
        return self.payment_reference


class Receipt(TimeStampedModel):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name='receipt')
    receipt_reference = models.CharField(max_length=50, unique=True)
    receipt_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.receipt_reference


@receiver(post_save, sender=InvoiceLineItem, dispatch_uid='billing.refresh_invoice_totals_on_line_save')
def refresh_invoice_totals_on_line_save(sender, instance, **kwargs):
    instance.invoice.recalculate_totals()


@receiver(post_delete, sender=InvoiceLineItem, dispatch_uid='billing.refresh_invoice_totals_on_line_delete')
def refresh_invoice_totals_on_line_delete(sender, instance, using, **kwargs):
    invoice = Invoice.objects.using(using).get(pk=instance.invoice_id)
    invoice.recalculate_totals()


@receiver(post_delete, sender=Payment, dispatch_uid='billing.refresh_invoice_status_on_payment_delete')
def refresh_invoice_status_on_payment_delete(sender, instance, using, **kwargs):
    invoice = Invoice.objects.using(using).get(pk=instance.invoice_id)
    invoice.refresh_status()
