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

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.properties.models import Owner, Property, RentalContract, Tenant, Unit

from .forms import PaymentForm
from .models import Invoice, InvoiceLineItem, Payment, Receipt, RentSchedule
from .services import generate_invoice_from_schedule, generate_rent_schedule, record_payment


User = get_user_model()


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


class BillingSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username='billing-admin', role=User.Role.ADMIN)
        cls.accountant = User.objects.create_user(username='billing-accountant', role=User.Role.ACCOUNTANT)
        cls.superuser = User.objects.create_superuser(username='billing-superuser', password='password')
        cls.property_manager = User.objects.create_user(username='billing-manager', role=User.Role.PROPERTY_MANAGER)
        cls.owner_user = User.objects.create_user(username='billing-owner', role=User.Role.OWNER)
        cls.tenant_user = User.objects.create_user(username='billing-tenant', role=User.Role.TENANT)
        cls.other_tenant_user = User.objects.create_user(username='billing-other-tenant', role=User.Role.TENANT)
        cls.owner = Owner.objects.create(full_name='Security Owner')
        cls.property = Property.objects.create(
            owner=cls.owner, name='Security Property', address='Security Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        cls.unit = Unit.objects.create(property=cls.property, unit_number='S1', rent_amount=Decimal('1000.00'))
        cls.other_unit = Unit.objects.create(property=cls.property, unit_number='S2', rent_amount=Decimal('900.00'))
        cls.tenant = Tenant.objects.create(user=cls.tenant_user, full_name='Scoped Tenant')
        cls.other_tenant = Tenant.objects.create(user=cls.other_tenant_user, full_name='Other Scoped Tenant')
        cls.contract = RentalContract.objects.create(
            tenant=cls.tenant, unit=cls.unit, contract_reference='SEC-CONTRACT-1',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1000.00'), status=RentalContract.Status.ACTIVE,
        )
        cls.other_contract = RentalContract.objects.create(
            tenant=cls.other_tenant, unit=cls.other_unit, contract_reference='SEC-CONTRACT-2',
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
            monthly_rent=Decimal('900.00'), status=RentalContract.Status.ACTIVE,
        )
        cls.invoice = Invoice.objects.create(
            contract=cls.contract, tenant=cls.tenant, invoice_reference='SEC-INVOICE-1',
            issue_date=date(2026, 1, 1), due_date=date(2026, 1, 10), total_amount=Decimal('1000.00'),
        )
        cls.other_invoice = Invoice.objects.create(
            contract=cls.other_contract, tenant=cls.other_tenant, invoice_reference='SEC-INVOICE-2',
            issue_date=date(2026, 1, 1), due_date=date(2026, 1, 10), total_amount=Decimal('900.00'),
        )
        cls.payment = Payment.objects.create(
            invoice=cls.invoice, tenant=cls.tenant, recorded_by=cls.accountant,
            payment_reference='SEC-PAYMENT-1', payment_date=date(2026, 1, 5),
            amount=Decimal('100.00'), payment_method=Payment.Method.CASH,
        )
        cls.other_payment = Payment.objects.create(
            invoice=cls.other_invoice, tenant=cls.other_tenant, recorded_by=cls.accountant,
            payment_reference='SEC-PAYMENT-2', payment_date=date(2026, 1, 5),
            amount=Decimal('100.00'), payment_method=Payment.Method.CASH,
        )
        cls.receipt = Receipt.objects.create(
            payment=cls.payment, receipt_reference='SEC-RECEIPT-1',
            receipt_date=date(2026, 1, 5), amount=cls.payment.amount,
        )
        cls.other_receipt = Receipt.objects.create(
            payment=cls.other_payment, receipt_reference='SEC-RECEIPT-2',
            receipt_date=date(2026, 1, 5), amount=cls.other_payment.amount,
        )
        cls.schedule = RentSchedule.objects.create(
            contract=cls.contract, billing_period_start=date(2026, 2, 1),
            billing_period_end=date(2026, 2, 28), due_date=date(2026, 2, 1),
            expected_amount=Decimal('1000.00'),
        )

    def test_anonymous_read_pages_redirect_to_login(self):
        urls = (
            reverse('billing:invoice_list'),
            reverse('billing:invoice_detail', args=[self.invoice.pk]),
            reverse('billing:payment_history'),
            reverse('billing:receipt_detail', args=[self.receipt.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_global_read_roles_do_not_require_tenant_profile(self):
        for user in (self.admin, self.accountant, self.superuser):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse('billing:invoice_list')).status_code, 200)
                self.assertEqual(self.client.get(reverse('billing:invoice_detail', args=[self.other_invoice.pk])).status_code, 200)

    def test_tenant_invoice_access_is_scoped_before_lookup(self):
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse('billing:invoice_list'))
        self.assertContains(response, self.invoice.invoice_reference)
        self.assertNotContains(response, self.other_invoice.invoice_reference)
        self.assertEqual(self.client.get(reverse('billing:invoice_detail', args=[self.invoice.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('billing:invoice_detail', args=[self.other_invoice.pk])).status_code, 404)

    def test_tenant_payment_and_receipt_access_is_scoped_before_lookup(self):
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse('billing:payment_history'))
        self.assertContains(response, self.payment.payment_reference)
        self.assertNotContains(response, self.other_payment.payment_reference)
        self.assertEqual(self.client.get(reverse('billing:receipt_detail', args=[self.receipt.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('billing:receipt_detail', args=[self.other_receipt.pk])).status_code, 404)

    def test_unlinked_tenant_fails_closed(self):
        user = User.objects.create_user(username='billing-unlinked', role=User.Role.TENANT)
        self.client.force_login(user)
        for url in (reverse('billing:invoice_list'), reverse('billing:payment_history')):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_non_finance_roles_cannot_use_mutation_views(self):
        mutation_requests = (
            ('get', reverse('billing:rent_schedule_list'), None),
            ('get', reverse('billing:invoice_create'), None),
            ('post', reverse('billing:generate_invoice', args=[self.schedule.pk]), {}),
            ('post', reverse('billing:invoice_add_late_fee', args=[self.invoice.pk]), {'amount': '10.00'}),
            ('get', reverse('billing:payment_create', args=[self.invoice.pk]), None),
        )
        for user in (self.tenant_user, self.property_manager, self.owner_user):
            self.client.force_login(user)
            for method, url, data in mutation_requests:
                with self.subTest(user=user.role, url=url):
                    response = getattr(self.client, method)(url, data or {})
                    self.assertEqual(response.status_code, 403)

    def test_anonymous_mutation_views_redirect_to_login(self):
        self.assertEqual(self.client.get(reverse('billing:invoice_create')).status_code, 302)
        self.assertEqual(self.client.post(reverse('billing:generate_invoice', args=[self.schedule.pk])).status_code, 302)

    def test_schedule_invoice_generation_requires_post(self):
        self.client.force_login(self.accountant)
        url = reverse('billing:generate_invoice', args=[self.schedule.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status, RentSchedule.Status.PENDING)
        self.assertFalse(Invoice.objects.filter(schedule=self.schedule).exists())

    def test_authorized_post_generates_invoice(self):
        self.client.force_login(self.accountant)
        response = self.client.post(reverse('billing:generate_invoice', args=[self.schedule.pk]))
        self.assertEqual(response.status_code, 302)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status, RentSchedule.Status.INVOICED)
        self.assertTrue(Invoice.objects.filter(schedule=self.schedule).exists())

    def test_payment_view_uses_authenticated_actor(self):
        self.client.force_login(self.accountant)
        response = self.client.post(reverse('billing:payment_create', args=[self.invoice.pk]), {
            'payment_date': '2026-01-06', 'amount': '50.00',
            'payment_method': Payment.Method.CARD, 'recorded_by': self.admin.pk,
        })
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(invoice=self.invoice, amount=Decimal('50.00'))
        self.assertEqual(payment.recorded_by, self.accountant)


class BillingModelRegressionTests(BillingTestCase):
    def test_zero_negative_and_overpayment_rejected_below_form_layer(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        for index, amount in enumerate((Decimal('0.00'), Decimal('-1.00'), Decimal('1000.01'))):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                Payment.objects.create(
                    invoice=invoice, tenant=self.tenant, payment_reference=f'MODEL-BAD-{index}',
                    payment_date=date(2026, 1, 5), amount=amount, payment_method=Payment.Method.CASH,
                )

    def test_overpayment_check_excludes_current_payment_on_edit(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        first = Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='MODEL-EDIT-1',
            payment_date=date(2026, 1, 5), amount=Decimal('400.00'), payment_method=Payment.Method.CASH,
        )
        Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='MODEL-EDIT-2',
            payment_date=date(2026, 1, 6), amount=Decimal('600.00'), payment_method=Payment.Method.CASH,
        )
        first.payment_date = date(2026, 1, 7)
        first.save(update_fields=['payment_date'])
        with self.assertRaises(ValidationError):
            first.amount = Decimal('401.00')
            first.save(update_fields=['amount'])

    def test_payment_tenant_consistency_and_deletion_status(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('0.00'))
        other_tenant = Tenant.objects.create(full_name='Model Other Tenant')
        with self.assertRaises(ValidationError):
            Payment.objects.create(
                invoice=invoice, tenant=other_tenant, payment_reference='MODEL-WRONG-TENANT',
                payment_date=date(2026, 1, 5), amount=Decimal('100.00'), payment_method=Payment.Method.CASH,
            )
        payment = Payment.objects.create(
            invoice=invoice, tenant=self.tenant, payment_reference='MODEL-DELETE',
            payment_date=date(2026, 1, 5), amount=Decimal('1000.00'), payment_method=Payment.Method.CASH,
        )
        payment.delete()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)

    def test_line_item_deletion_refreshes_totals(self):
        invoice = self.make_invoice(subtotal=Decimal('1000.00'), tax_rate=Decimal('10.00'))
        invoice.line_items.get().delete()
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal('0.00'))
        self.assertEqual(invoice.tax_total, Decimal('0.00'))
        self.assertEqual(invoice.total_amount, Decimal('0.00'))

    def test_rent_schedule_model_validation(self):
        with self.assertRaises(ValidationError):
            RentSchedule.objects.create(
                contract=self.contract, billing_period_start=date(2026, 3, 2),
                billing_period_end=date(2026, 3, 1), due_date=date(2026, 3, 2),
                expected_amount=Decimal('0.00'),
            )
        values = {
            'contract': self.contract, 'billing_period_start': date(2026, 4, 1),
            'billing_period_end': date(2026, 4, 30), 'due_date': date(2026, 4, 1),
            'expected_amount': Decimal('1000.00'),
        }
        RentSchedule.objects.create(**values)
        with self.assertRaises(ValidationError):
            RentSchedule.objects.create(**values)
