from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.properties.models import Owner, Property, RentalContract, Tenant, Unit

from .models import Invoice, InvoiceLineItem, Payment, Receipt, RentSchedule


User = get_user_model()


class BillingModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(
            username='billing-accountant',
            role=User.Role.ACCOUNTANT,
        )
        owner = Owner.objects.create(full_name='Billing Owner')
        property_object = Property.objects.create(
            owner=owner,
            name='Billing Property',
            address='Billing Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        cls.unit = Unit.objects.create(
            property=property_object,
            unit_number='B1',
            rent_amount=Decimal('1000.00'),
        )
        cls.tenant = Tenant.objects.create(full_name='Billing Tenant')
        cls.other_tenant = Tenant.objects.create(full_name='Other Tenant')
        cls.contract = RentalContract.objects.create(
            tenant=cls.tenant,
            unit=cls.unit,
            contract_reference='BILLING-CONTRACT',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1000.00'),
        )

    def create_invoice(self, reference='BILLING-INVOICE', total=Decimal('1000.00')):
        return Invoice.objects.create(
            contract=self.contract,
            tenant=self.tenant,
            invoice_reference=reference,
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            total_amount=total,
        )

    def create_payment(self, invoice, reference, amount):
        return Payment.objects.create(
            invoice=invoice,
            tenant=invoice.tenant,
            recorded_by=self.user,
            payment_reference=reference,
            payment_date=date(2026, 1, 5),
            amount=amount,
            payment_method=Payment.Method.BANK_TRANSFER,
        )

    def test_rent_schedule_keeps_contract_dates_and_amount(self):
        schedule = RentSchedule.objects.create(
            contract=self.contract,
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 5),
            expected_amount=Decimal('1000.00'),
        )
        self.assertEqual(schedule.contract, self.contract)
        self.assertEqual(schedule.due_date, date(2026, 1, 5))
        self.assertEqual(schedule.expected_amount, Decimal('1000.00'))

    def test_rent_schedule_rejects_duplicate_contract_period(self):
        values = {
            'contract': self.contract,
            'billing_period_start': date(2026, 1, 1),
            'billing_period_end': date(2026, 1, 31),
            'due_date': date(2026, 1, 5),
            'expected_amount': Decimal('1000.00'),
        }
        RentSchedule.objects.create(**values)

        with self.assertRaises(ValidationError):
            RentSchedule.objects.create(**values)

    def test_rent_schedule_rejects_invalid_period_and_amount(self):
        schedule = RentSchedule(
            contract=self.contract,
            billing_period_start=date(2026, 2, 1),
            billing_period_end=date(2026, 1, 31),
            due_date=date(2026, 2, 5),
            expected_amount=Decimal('0.00'),
        )

        with self.assertRaises(ValidationError) as error:
            schedule.save()

        self.assertIn('billing_period_end', error.exception.message_dict)
        self.assertIn('expected_amount', error.exception.message_dict)

    def test_line_item_save_and_delete_refresh_invoice_totals(self):
        invoice = self.create_invoice(total=Decimal('0.00'))
        line = InvoiceLineItem.objects.create(
            invoice=invoice,
            description='Rent',
            quantity=Decimal('2.00'),
            unit_amount=Decimal('100.00'),
            taxable_amount=Decimal('0.00'),
            tax_rate=Decimal('10.00'),
            tax_amount=Decimal('0.00'),
            line_total=Decimal('0.00'),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        self.assertEqual(invoice.tax_total, Decimal('20.00'))
        self.assertEqual(invoice.total_amount, Decimal('220.00'))

        line.delete()
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal('0.00'))
        self.assertEqual(invoice.tax_total, Decimal('0.00'))
        self.assertEqual(invoice.total_amount, Decimal('0.00'))

    def test_partial_full_and_multiple_payments_refresh_status_and_balances(self):
        invoice = self.create_invoice()
        self.create_payment(invoice, 'PARTIAL-PAYMENT', Decimal('400.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.assertEqual(invoice.amount_paid, Decimal('400.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('600.00'))

        self.create_payment(invoice, 'FINAL-PAYMENT', Decimal('600.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(invoice.amount_paid, Decimal('1000.00'))
        self.assertEqual(invoice.outstanding_balance, Decimal('0.00'))
        self.assertEqual(invoice.payments.count(), 2)

    def test_zero_and_negative_payments_are_rejected(self):
        invoice = self.create_invoice()
        for amount in (Decimal('0.00'), Decimal('-1.00')):
            with self.subTest(amount=amount):
                with self.assertRaises(ValidationError):
                    self.create_payment(invoice, f'INVALID-{amount}', amount)
        self.assertFalse(invoice.payments.exists())

    def test_payment_tenant_must_match_invoice(self):
        invoice = self.create_invoice()
        payment = Payment(
            invoice=invoice,
            tenant=self.other_tenant,
            recorded_by=self.user,
            payment_reference='WRONG-TENANT',
            payment_date=date(2026, 1, 5),
            amount=Decimal('100.00'),
            payment_method=Payment.Method.CASH,
        )
        with self.assertRaises(ValidationError):
            payment.save()

    def test_payment_delete_refreshes_invoice_status(self):
        invoice = self.create_invoice()
        payment = self.create_payment(invoice, 'DELETE-PAYMENT', Decimal('1000.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

        payment.delete()

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)
        self.assertEqual(invoice.amount_paid, Decimal('0.00'))

    def test_partial_payment_save_uses_persisted_omitted_values(self):
        invoice = self.create_invoice()
        payment = self.create_payment(invoice, 'PARTIAL-SAVE', Decimal('100.00'))
        payment.amount = Decimal('-5.00')
        payment.payment_date = date(2026, 1, 6)

        payment.save(update_fields=['payment_date'])

        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertEqual(payment.payment_date, date(2026, 1, 6))

    def test_receipt_links_to_payment_and_invoice(self):
        invoice = self.create_invoice()
        payment = self.create_payment(invoice, 'RECEIPT-PAYMENT', Decimal('100.00'))
        receipt = Receipt.objects.create(
            payment=payment,
            receipt_reference='RECEIPT-1',
            receipt_date=date(2026, 1, 5),
            amount=payment.amount,
        )
        self.assertEqual(receipt.payment, payment)
        self.assertEqual(receipt.payment.invoice, invoice)
        self.assertEqual(str(receipt), 'RECEIPT-1')

    def test_payment_view_sets_actor_and_generates_displayable_receipt(self):
        invoice = self.create_invoice()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('billing:payment_create', kwargs={'invoice_pk': invoice.pk}),
            {
                'payment_reference': 'VIEW-PAYMENT',
                'payment_date': '2026-01-05',
                'amount': '250.00',
                'payment_method': Payment.Method.CARD,
                'recorded_by': User.objects.create(username='impersonated').pk,
            },
        )

        payment = Payment.objects.get(payment_reference='VIEW-PAYMENT')
        receipt = payment.receipt
        self.assertRedirects(
            response,
            reverse('billing:receipt_detail', kwargs={'pk': receipt.pk}),
        )
        self.assertEqual(payment.recorded_by, self.user)
        self.assertEqual(payment.tenant, invoice.tenant)
        self.assertEqual(receipt.amount, payment.amount)
        self.assertContains(
            self.client.get(reverse('billing:payment_history')),
            payment.payment_reference,
        )

    def test_billing_pages_require_finance_role(self):
        invoice = self.create_invoice()
        urls = [
            reverse('billing:invoice_list'),
            reverse('billing:invoice_detail', kwargs={'pk': invoice.pk}),
            reverse('billing:payment_create', kwargs={'invoice_pk': invoice.pk}),
            reverse('billing:payment_history'),
        ]

        for role, expected in (
            (User.Role.ADMIN, 200),
            (User.Role.ACCOUNTANT, 200),
            (User.Role.PROPERTY_MANAGER, 403),
            (User.Role.OWNER, 403),
        ):
            with self.subTest(role=role):
                user = User.objects.create(username=f'matrix-{role}', role=role)
                self.client.force_login(user)
                for url in urls:
                    self.assertEqual(self.client.get(url).status_code, expected)
                self.client.logout()

        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)


class TenantBillingAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant_user = User.objects.create_user(
            username='tenant-self-service',
            password='test-password',
            role=User.Role.TENANT,
        )
        owner = Owner.objects.create(full_name='Billing Access Owner')
        property_object = Property.objects.create(
            owner=owner,
            name='Billing Access Property',
            address='Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        unit = Unit.objects.create(
            property=property_object,
            unit_number='ACCESS-1',
            rent_amount=Decimal('1000.00'),
        )
        other_unit = Unit.objects.create(
            property=property_object,
            unit_number='ACCESS-2',
            rent_amount=Decimal('900.00'),
        )
        cls.tenant = Tenant.objects.create(
            user=cls.tenant_user,
            full_name='Linked Tenant',
        )
        cls.other_tenant = Tenant.objects.create(full_name='Other Tenant')
        contract = RentalContract.objects.create(
            tenant=cls.tenant,
            unit=unit,
            contract_reference='TENANT-ACCESS-CONTRACT',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1000.00'),
        )
        other_contract = RentalContract.objects.create(
            tenant=cls.other_tenant,
            unit=other_unit,
            contract_reference='OTHER-ACCESS-CONTRACT',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('900.00'),
        )
        cls.invoice = Invoice.objects.create(
            contract=contract,
            tenant=cls.tenant,
            invoice_reference='TENANT-ACCESS-INVOICE',
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            total_amount=Decimal('1000.00'),
        )
        cls.other_invoice = Invoice.objects.create(
            contract=other_contract,
            tenant=cls.other_tenant,
            invoice_reference='OTHER-ACCESS-INVOICE',
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            total_amount=Decimal('900.00'),
        )
        actor = User.objects.create(username='billing-actor', role=User.Role.ACCOUNTANT)
        cls.payment = Payment.objects.create(
            invoice=cls.invoice,
            tenant=cls.tenant,
            recorded_by=actor,
            payment_reference='TENANT-ACCESS-PAYMENT',
            payment_date=date(2026, 1, 5),
            amount=Decimal('100.00'),
            payment_method=Payment.Method.CASH,
        )
        cls.other_payment = Payment.objects.create(
            invoice=cls.other_invoice,
            tenant=cls.other_tenant,
            recorded_by=actor,
            payment_reference='OTHER-ACCESS-PAYMENT',
            payment_date=date(2026, 1, 5),
            amount=Decimal('100.00'),
            payment_method=Payment.Method.CASH,
        )
        cls.receipt = Receipt.objects.create(
            payment=cls.payment,
            receipt_reference='TENANT-ACCESS-RECEIPT',
            receipt_date=date(2026, 1, 5),
            amount=cls.payment.amount,
        )
        cls.other_receipt = Receipt.objects.create(
            payment=cls.other_payment,
            receipt_reference='OTHER-ACCESS-RECEIPT',
            receipt_date=date(2026, 1, 5),
            amount=cls.other_payment.amount,
        )

    def setUp(self):
        self.client.force_login(self.tenant_user)

    def test_tenant_invoice_list_and_detail_are_scoped(self):
        response = self.client.get(reverse('billing:invoice_list'))
        self.assertContains(response, self.invoice.invoice_reference)
        self.assertNotContains(response, self.other_invoice.invoice_reference)
        self.assertEqual(
            self.client.get(reverse('billing:invoice_detail', args=[self.invoice.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('billing:invoice_detail', args=[self.other_invoice.pk])).status_code,
            404,
        )

    def test_tenant_payment_history_and_receipt_are_scoped(self):
        response = self.client.get(reverse('billing:payment_history'))
        self.assertContains(response, self.payment.payment_reference)
        self.assertNotContains(response, self.other_payment.payment_reference)
        self.assertEqual(
            self.client.get(reverse('billing:receipt_detail', args=[self.receipt.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('billing:receipt_detail', args=[self.other_receipt.pk])).status_code,
            404,
        )

    def test_tenant_cannot_record_payment(self):
        self.assertEqual(
            self.client.get(
                reverse('billing:payment_create', kwargs={'invoice_pk': self.invoice.pk})
            ).status_code,
            403,
        )

    def test_unlinked_tenant_fails_safely(self):
        self.client.force_login(User.objects.create_user(
            username='unlinked-tenant', role=User.Role.TENANT
        ))
        self.assertEqual(self.client.get(reverse('billing:invoice_list')).status_code, 403)
