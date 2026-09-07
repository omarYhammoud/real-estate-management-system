"""
Waad — Billing & Payments tests.

Covers:
  * invoice totals (subtotal + tax = total)
  * invoice status transitions across partial / multiple / full payments
  * late fee line items
  * rent schedule generation from a contract
  * invoice generation from a rent schedule period (and double-invoicing guard)
  * payment -> receipt auto-generation
  * payment form validation (no overpayment)
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.properties.models import Owner, Property, RentalContract, Tenant, Unit

from .forms import PaymentForm
from .models import Invoice, InvoiceLineItem, Payment, Receipt, RentSchedule
from .services import generate_invoice_from_schedule, generate_rent_schedule, record_payment


class BillingTestCase(TestCase):
    """Shared fixtures: one owner -> property -> unit -> tenant -> active
    12-month contract, matching the ERD's rental workflow."""

    def setUp(self):
        self.owner = Owner.objects.create(full_name='J. Karam', email='owner@example.com')
        self.property = Property.objects.create(
            owner=self.owner, name='Cedar Court', address='123 Cedar St',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        self.unit = Unit.objects.create(
            property=self.property, unit_number='4B', rent_amount=Decimal('1450.00'),
        )
        self.tenant = Tenant.objects.create(full_name='R. Haddad', email='tenant@example.com')
        self.contract = RentalContract.objects.create(
            tenant=self.tenant, unit=self.unit, contract_reference='LC-2024-118',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1450.00'), status=RentalContract.Status.ACTIVE,
        )

    def make_invoice(self, subtotal=Decimal('1000.00'), tax_rate=Decimal('10.00')):
        invoice = Invoice.objects.create(
            contract=self.contract, tenant=self.tenant,
            invoice_reference='INV-TEST-0001',
            issue_date=date(2026, 1, 1), due_date=date(2026, 1, 15),
        )
        InvoiceLineItem.objects.create(
            invoice=invoice, description='Rent', quantity=Decimal('1.00'),
            unit_amount=subtotal, tax_rate=tax_rate,
        )
        invoice.recalculate_totals()
        invoice.refresh_from_db()
        return invoice


class InvoiceTotalCalculationTests(BillingTestCase):
    def test_total_equals_subtotal_plus_tax(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('10.00'))
        self.assertEqual(invoice.subtotal, Decimal('1000.00'))
        self.assertEqual(invoice.tax_total, Decimal('100.00'))
        self.assertEqual(invoice.total_amount, Decimal('1100.00'))

    def test_totals_recalculate_after_adding_a_second_line_item(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        InvoiceLineItem.objects.create(
            invoice=invoice, description='Parking', quantity=Decimal('1.00'),
            unit_amount=Decimal('50.00'), tax_rate=Decimal('0.00'),
        )
        invoice.recalculate_totals()
        invoice.refresh_from_db()
        self.assertEqual(invoice.total_amount, Decimal('1050.00'))

    def test_new_invoice_defaults_to_unpaid(self):
        invoice = self.make_invoice()
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)
        self.assertEqual(invoice.amount_paid, Decimal('0.00'))
        self.assertEqual(invoice.outstanding_balance, invoice.total_amount)


class PaymentStatusTransitionTests(BillingTestCase):
    def test_partial_payment_sets_status_partially_paid(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='PMT-0001',
            payment_date=date(2026, 1, 10), amount=Decimal('400.00'),
            payment_method=Payment.Method.CASH,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.assertEqual(invoice.amount_paid, Decimal('400.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('600.00'))

    def test_multiple_payments_sum_and_reach_paid_in_full(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='PMT-0002',
            payment_date=date(2026, 1, 5), amount=Decimal('600.00'),
            payment_method=Payment.Method.BANK_TRANSFER,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)

        Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='PMT-0003',
            payment_date=date(2026, 1, 20), amount=Decimal('400.00'),
            payment_method=Payment.Method.CASH,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal('1000.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('0.00'))
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_full_payment_in_one_go_sets_status_paid(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='PMT-0004',
            payment_date=date(2026, 1, 2), amount=Decimal('1000.00'),
            payment_method=Payment.Method.CARD,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)


class LateFeeTests(BillingTestCase):
    def test_add_late_fee_increases_total_and_creates_line_item(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        invoice.add_late_fee(Decimal('25.00'), reason='Late payment fee — August')
        invoice.refresh_from_db()

        self.assertEqual(invoice.line_items.count(), 2)
        self.assertEqual(invoice.total_amount, Decimal('1025.00'))
        self.assertTrue(invoice.line_items.filter(description__icontains='Late payment fee').exists())

    def test_late_fee_after_full_payment_recomputes_status(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='PMT-0005',
            payment_date=date(2026, 1, 10), amount=Decimal('1000.00'),
            payment_method=Payment.Method.CASH,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

        invoice.add_late_fee(Decimal('50.00'))
        invoice.refresh_from_db()
        # Adding a fee after the invoice was fully paid should drop it back
        # to partially paid, since the new total now exceeds amount_paid.
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.assertEqual(invoice.outstanding_balance, Decimal('50.00'))


class RentScheduleGenerationTests(BillingTestCase):
    def test_generates_twelve_monthly_periods_for_a_one_year_contract(self):
        schedules = generate_rent_schedule(self.contract, frequency='monthly')
        self.assertEqual(len(schedules), 12)
        self.assertEqual(schedules[0].billing_period_start, date(2026, 1, 1))
        self.assertEqual(schedules[0].billing_period_end, date(2026, 1, 31))
        self.assertEqual(schedules[-1].billing_period_start, date(2026, 12, 1))
        self.assertEqual(schedules[-1].billing_period_end, date(2026, 12, 31))
        self.assertTrue(all(s.expected_amount == Decimal('1450.00') for s in schedules))
        self.assertTrue(all(s.status == RentSchedule.Status.PENDING for s in schedules))

    def test_quarterly_frequency_generates_four_periods_with_scaled_amount(self):
        schedules = generate_rent_schedule(self.contract, frequency='quarterly')
        self.assertEqual(len(schedules), 4)
        self.assertEqual(schedules[0].expected_amount, Decimal('4350.00'))  # 1450 * 3


class InvoiceGenerationFromScheduleTests(BillingTestCase):
    def test_generate_invoice_creates_rent_line_item_and_marks_schedule_invoiced(self):
        schedule = RentSchedule.objects.create(
            contract=self.contract, billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31), due_date=date(2026, 1, 1),
            expected_amount=Decimal('1450.00'),
        )
        invoice = generate_invoice_from_schedule(schedule)
        schedule.refresh_from_db()

        self.assertEqual(invoice.total_amount, Decimal('1450.00'))
        self.assertEqual(invoice.tenant, self.tenant)
        self.assertEqual(invoice.line_items.count(), 1)
        self.assertEqual(schedule.status, RentSchedule.Status.INVOICED)

    def test_cannot_invoice_the_same_schedule_period_twice(self):
        schedule = RentSchedule.objects.create(
            contract=self.contract, billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31), due_date=date(2026, 1, 1),
            expected_amount=Decimal('1450.00'),
        )
        generate_invoice_from_schedule(schedule)
        with self.assertRaises(ValidationError):
            generate_invoice_from_schedule(schedule)


class ReceiptAutoGenerationTests(BillingTestCase):
    def test_recording_a_payment_auto_creates_a_receipt(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        payment, receipt = record_payment(
            invoice=invoice, tenant=self.tenant, amount=Decimal('1000.00'),
            payment_date=date(2026, 1, 5), payment_method=Payment.Method.CASH,
        )
        self.assertIsInstance(receipt, Receipt)
        self.assertEqual(receipt.payment, payment)
        self.assertEqual(receipt.amount, Decimal('1000.00'))
        self.assertEqual(Receipt.objects.filter(payment=payment).count(), 1)


class PaymentFormValidationTests(BillingTestCase):
    def test_payment_form_rejects_amount_over_outstanding_balance(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        form = PaymentForm(
            data={'payment_date': '2026-01-05', 'amount': '1500.00', 'payment_method': Payment.Method.CASH},
            invoice=invoice,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_payment_form_accepts_amount_within_outstanding_balance(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        form = PaymentForm(
            data={'payment_date': '2026-01-05', 'amount': '400.00', 'payment_method': Payment.Method.CASH},
            invoice=invoice,
        )
        self.assertTrue(form.is_valid())