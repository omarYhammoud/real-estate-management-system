"""
Waad — Billing & Payments service functions.

Business logic that isn't tied to a specific HTTP request lives here rather
than in views.py
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.core.utils import generate_reference

from .models import Invoice, InvoiceLineItem, Payment, Receipt, RentSchedule

FREQUENCY_MONTHS = {'monthly': 1, 'quarterly': 3, 'annual': 12}


def _add_months(start: date, months: int) -> date:
    """Add a whole number of calendar months to `start`, clamping the day
    to the last valid day of the resulting month (e.g. Jan 31 + 1 month
    lands on Feb 28/29, not an invalid Feb 31)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def generate_rent_schedule(contract, frequency='monthly'):
    """
    Business rule (Waad): build one RentSchedule row per billing period
    from contract.start_date up to contract.end_date, using
    contract.monthly_rent as the base and scaling it for quarterly/annual
    periods. The last period is clipped to the contract's end_date even if
    it's shorter than a full period.

    Returns the list of created RentSchedule instances, in period order.
    """
    step = FREQUENCY_MONTHS.get(frequency, 1)
    schedules = []
    period_start = contract.start_date

    while period_start <= contract.end_date:
        period_end = _add_months(period_start, step) - timedelta(days=1)
        if period_end > contract.end_date:
            period_end = contract.end_date

        schedules.append(RentSchedule.objects.create(
            contract=contract,
            billing_period_start=period_start,
            billing_period_end=period_end,
            due_date=period_start,
            expected_amount=(contract.monthly_rent * step).quantize(Decimal('0.01')),
        ))
        period_start = _add_months(period_start, step)

    return schedules


def generate_invoice_from_schedule(schedule):
    """
    Business rule (Waad): turn one PENDING RentSchedule row into an Invoice
    with a single "Rent" line item, then mark the schedule INVOICED so the
    same period can never be billed twice.
    """
    if schedule.status != RentSchedule.Status.PENDING:
        raise ValidationError(
            f"This schedule period is '{schedule.get_status_display()}' — "
            "only a pending period can be invoiced."
        )

    contract = schedule.contract
    period_label = f"{schedule.billing_period_start:%b %Y}"

    invoice = Invoice.objects.create(
        contract=contract,
        tenant=contract.tenant,
        schedule=schedule,
        invoice_reference=generate_reference('INV'),
        billing_period=period_label,
        issue_date=schedule.billing_period_start,
        due_date=schedule.due_date,
    )
    InvoiceLineItem.objects.create(
        invoice=invoice,
        description=f"Rent — {period_label}",
        quantity=Decimal('1.00'),
        unit_amount=schedule.expected_amount,
        tax_rate=Decimal('0.00'),
    )
    invoice.recalculate_totals()

    schedule.status = RentSchedule.Status.INVOICED
    schedule.save(update_fields=['status'])

    return invoice


def record_payment(invoice, tenant, amount, payment_date, payment_method, recorded_by=None):
    """
    Business rule (Waad): create the Payment, then immediately auto-generate
    its Receipt (a strict one-to-one — every payment gets exactly one
    receipt, with no separate manual step). Saving the Payment also
    triggers Invoice.refresh_status() via Payment.save(), so the invoice's
    Unpaid / Partially Paid / Paid status is always in sync.
    """
    payment = Payment.objects.create(
        invoice=invoice,
        tenant=tenant,
        recorded_by=recorded_by,
        payment_reference=generate_reference('PMT'),
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
    )
    receipt = Receipt.objects.create(
        payment=payment,
        receipt_reference=generate_reference('RCT'),
        receipt_date=payment_date,
        amount=amount,
    )
    return payment, receipt