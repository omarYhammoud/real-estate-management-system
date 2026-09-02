from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse

from apps.properties.models import Owner, Property, Unit, Tenant, RentalContract
from apps.operations.models import (
    SecurityDeposit,
    DepositDeduction,
    DepositRefund,
    MaintenanceRequest,
    Expense,
)
from apps.operations.forms import DepositDeductionForm, DepositRefundForm

User = get_user_model()


class OperationsBaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='password123',
            email='test@example.com'
        )
        self.owner = Owner.objects.create(
            full_name='John Owner',
            phone='+1234567890',
            email='owner@example.com',
            address='123 Main St'
        )
        self.property = Property.objects.create(
            owner=self.owner,
            name='Sunset Heights',
            address='456 Elm St',
            property_type=Property.PropertyType.RESIDENTIAL
        )
        self.unit = Unit.objects.create(
            property=self.property,
            unit_number='101',
            rent_amount=Decimal('1500.00'),
            status=Unit.Status.OCCUPIED
        )
        self.tenant = Tenant.objects.create(
            full_name='Alice Tenant',
            phone='+9876543210',
            email='alice@example.com'
        )
        self.contract = RentalContract.objects.create(
            tenant=self.tenant,
            unit=self.unit,
            contract_reference='RC-2026-001',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1500.00'),
            status=RentalContract.Status.ACTIVE
        )


class SecurityDepositModelTests(OperationsBaseTestCase):
    def test_create_security_deposit_and_initial_balance(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        self.assertEqual(deposit.remaining_balance, Decimal('1500.00'))
        self.assertEqual(str(deposit), f"Deposit for {self.contract.contract_reference}")

    def test_deduction_reduces_remaining_balance(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        deduction = DepositDeduction.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            amount=Decimal('300.00'),
            reason='Broken window repair',
            deduction_date=date(2026, 2, 1)
        )
        deposit.refresh_from_db()
        self.assertEqual(deposit.remaining_balance, Decimal('1200.00'))
        self.assertIn('300.00', str(deduction))

    def test_refund_reduces_remaining_balance(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        refund = DepositRefund.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 6, 1),
            amount=Decimal('500.00'),
            refund_method='Bank Transfer',
            refund_reference='REF-001'
        )
        deposit.refresh_from_db()
        self.assertEqual(deposit.remaining_balance, Decimal('1000.00'))
        self.assertEqual(str(refund), 'REF-001')

    def test_deduction_and_refund_combined_balance(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        DepositDeduction.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            amount=Decimal('200.00'),
            reason='Key replacement',
            deduction_date=date(2026, 2, 1)
        )
        DepositRefund.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 3, 1),
            amount=Decimal('400.00'),
            refund_method='Cash',
            refund_reference='REF-002'
        )
        deposit.refresh_from_db()
        self.assertEqual(deposit.remaining_balance, Decimal('900.00'))

    def test_reject_deduction_exceeding_balance(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        deduction = DepositDeduction(
            deposit=deposit,
            authorized_by=self.user,
            amount=Decimal('1600.00'),
            reason='Extensive renovation',
            deduction_date=date(2026, 2, 1)
        )
        with self.assertRaises(ValidationError):
            deduction.clean()

    def test_reject_refund_exceeding_balance(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        refund = DepositRefund(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 2, 1),
            amount=Decimal('2000.00'),
            refund_method='Bank Transfer',
            refund_reference='REF-OVER'
        )
        with self.assertRaises(ValidationError):
            refund.clean()

    def test_reject_negative_or_zero_deduction(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        d_zero = DepositDeduction(
            deposit=deposit,
            authorized_by=self.user,
            amount=Decimal('0.00'),
            reason='Zero',
            deduction_date=date(2026, 2, 1)
        )
        with self.assertRaises(ValidationError):
            d_zero.clean()

        d_neg = DepositDeduction(
            deposit=deposit,
            authorized_by=self.user,
            amount=Decimal('-50.00'),
            reason='Negative',
            deduction_date=date(2026, 2, 1)
        )
        with self.assertRaises(ValidationError):
            d_neg.clean()

    def test_reject_negative_or_zero_refund(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        r_zero = DepositRefund(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 2, 1),
            amount=Decimal('0.00'),
            refund_reference='REF-ZERO'
        )
        with self.assertRaises(ValidationError):
            r_zero.clean()


class MaintenanceAndExpenseModelTests(OperationsBaseTestCase):
    def test_create_maintenance_request(self):
        maint = MaintenanceRequest.objects.create(
            property=self.property,
            unit=self.unit,
            tenant=self.tenant,
            issue='Leaking faucet in kitchen',
            priority=MaintenanceRequest.Priority.HIGH,
            status=MaintenanceRequest.Status.OPEN,
            request_date=date(2026, 3, 15),
            cost=Decimal('120.00')
        )
        self.assertEqual(maint.status, MaintenanceRequest.Status.OPEN)
        self.assertEqual(maint.priority, MaintenanceRequest.Priority.HIGH)
        self.assertIn('Sunset Heights', str(maint))

    def test_create_expense(self):
        expense = Expense.objects.create(
            property=self.property,
            unit=self.unit,
            recorded_by=self.user,
            expense_reference='EXP-2026-001',
            category=Expense.Category.MAINTENANCE,
            amount=Decimal('120.00'),
            expense_date=date(2026, 3, 16),
            description='Faucet replacement parts',
            status=Expense.ExpenseStatus.APPROVED
        )
        self.assertEqual(expense.expense_reference, 'EXP-2026-001')
        self.assertEqual(expense.category, Expense.Category.MAINTENANCE)
        self.assertEqual(str(expense), 'EXP-2026-001')


class OperationsFormValidationTests(OperationsBaseTestCase):
    def test_deduction_form_validation(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1000.00'),
            received_amount=Decimal('1000.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1000.00'),
            status=SecurityDeposit.Status.HELD
        )
        # Invalid amount exceeding balance
        form_invalid = DepositDeductionForm(
            data={
                'amount': '1500.00',
                'reason': 'Major damage',
                'deduction_date': '2026-02-01',
            },
            deposit=deposit
        )
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('amount', form_invalid.errors)

        # Valid amount
        form_valid = DepositDeductionForm(
            data={
                'amount': '250.00',
                'reason': 'Cleaning fee',
                'deduction_date': '2026-02-01',
            },
            deposit=deposit
        )
        self.assertTrue(form_valid.is_valid())

    def test_refund_form_validation(self):
        deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1000.00'),
            received_amount=Decimal('1000.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1000.00'),
            status=SecurityDeposit.Status.HELD
        )
        # Exceeding refund
        form_invalid = DepositRefundForm(
            data={
                'amount': '1200.00',
                'refund_date': '2026-02-01',
                'refund_method': 'Bank Transfer',
                'refund_reference': 'REF-EXCEED',
            },
            deposit=deposit
        )
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('amount', form_invalid.errors)

        # Valid refund
        form_valid = DepositRefundForm(
            data={
                'amount': '500.00',
                'refund_date': '2026-02-01',
                'refund_method': 'Bank Transfer',
                'refund_reference': 'REF-VALID',
            },
            deposit=deposit
        )
        self.assertTrue(form_valid.is_valid())


class OperationsViewsTests(OperationsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1500.00'),
            received_amount=Decimal('1500.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1500.00'),
            status=SecurityDeposit.Status.HELD
        )
        self.maintenance = MaintenanceRequest.objects.create(
            property=self.property,
            unit=self.unit,
            tenant=self.tenant,
            issue='AC repair',
            priority=MaintenanceRequest.Priority.URGENT,
            status=MaintenanceRequest.Status.OPEN,
            request_date=date(2026, 4, 1),
        )
        self.expense = Expense.objects.create(
            property=self.property,
            unit=self.unit,
            recorded_by=self.user,
            expense_reference='EXP-VIEW-01',
            category=Expense.Category.ELECTRICITY,
            amount=Decimal('85.50'),
            expense_date=date(2026, 4, 5),
        )

    def test_anonymous_user_redirected_to_login(self):
        urls = [
            reverse('operations:deposit_list'),
            reverse('operations:deposit_create'),
            reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}),
            reverse('operations:deposit_edit', kwargs={'pk': self.deposit.pk}),
            reverse('operations:deduction_add', kwargs={'deposit_pk': self.deposit.pk}),
            reverse('operations:refund_add', kwargs={'deposit_pk': self.deposit.pk}),
            reverse('operations:maintenance_list'),
            reverse('operations:maintenance_create'),
            reverse('operations:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            reverse('operations:maintenance_edit', kwargs={'pk': self.maintenance.pk}),
            reverse('operations:expense_list'),
            reverse('operations:expense_create'),
            reverse('operations:expense_detail', kwargs={'pk': self.expense.pk}),
            reverse('operations:expense_edit', kwargs={'pk': self.expense.pk}),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"Expected 302 redirect for unauthenticated user on {url}")

    def test_authenticated_user_can_access_views(self):
        self.client.login(username='testuser', password='password123')

        urls_and_expected = [
            (reverse('operations:deposit_list'), 200),
            (reverse('operations:deposit_create'), 200),
            (reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}), 200),
            (reverse('operations:deposit_edit', kwargs={'pk': self.deposit.pk}), 200),
            (reverse('operations:deduction_add', kwargs={'deposit_pk': self.deposit.pk}), 200),
            (reverse('operations:refund_add', kwargs={'deposit_pk': self.deposit.pk}), 200),
            (reverse('operations:maintenance_list'), 200),
            (reverse('operations:maintenance_create'), 200),
            (reverse('operations:maintenance_detail', kwargs={'pk': self.maintenance.pk}), 200),
            (reverse('operations:maintenance_edit', kwargs={'pk': self.maintenance.pk}), 200),
            (reverse('operations:expense_list'), 200),
            (reverse('operations:expense_create'), 200),
            (reverse('operations:expense_detail', kwargs={'pk': self.expense.pk}), 200),
            (reverse('operations:expense_edit', kwargs={'pk': self.expense.pk}), 200),
        ]
        for url, expected_status in urls_and_expected:
            response = self.client.get(url)
            self.assertEqual(response.status_code, expected_status, f"Failed on URL: {url}")
