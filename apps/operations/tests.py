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
from apps.operations.forms import DepositDeductionForm, DepositRefundForm, ExpenseForm

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


class SecurityDepositBalanceIntegrityTests(OperationsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.deposit = SecurityDeposit.objects.create(
            contract=self.contract,
            required_amount=Decimal('1000.00'),
            received_amount=Decimal('1000.00'),
            received_date=date(2026, 1, 1),
            remaining_balance=Decimal('1000.00'),
            status=SecurityDeposit.Status.HELD,
        )

    def add_deduction(self, amount=Decimal('300.00')):
        return DepositDeduction.objects.create(
            deposit=self.deposit,
            authorized_by=self.user,
            amount=amount,
            reason='Damage charge',
            deduction_date=date(2026, 2, 1),
        )

    def add_refund(self, amount=Decimal('200.00')):
        return DepositRefund.objects.create(
            deposit=self.deposit,
            authorized_by=self.user,
            amount=amount,
            refund_date=date(2026, 3, 1),
            refund_reference='BALANCE-REFUND',
        )

    def test_lowering_received_amount_below_used_balance_is_rejected(self):
        self.add_deduction()
        self.add_refund()
        self.deposit.received_amount = Decimal('499.99')

        with self.assertRaises(ValidationError) as error:
            self.deposit.save(update_fields=['received_amount'])

        self.assertIn('received_amount', error.exception.message_dict)
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.received_amount, Decimal('1000.00'))

    def test_lowering_received_amount_to_used_balance_is_allowed(self):
        self.add_deduction()
        self.add_refund()
        self.deposit.received_amount = Decimal('500.00')

        self.deposit.save(update_fields=['received_amount'])
        self.deposit.recalc_remaining_balance()
        self.deposit.refresh_from_db()

        self.assertEqual(self.deposit.received_amount, Decimal('500.00'))
        self.assertEqual(self.deposit.remaining_balance, Decimal('0.00'))

    def test_increasing_received_amount_is_allowed(self):
        self.add_deduction()
        self.deposit.received_amount = Decimal('1200.00')

        self.deposit.save(update_fields=['received_amount'])

        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.received_amount, Decimal('1200.00'))

    def test_update_without_deductions_or_refunds_is_allowed(self):
        self.deposit.received_amount = Decimal('250.00')

        self.deposit.save(update_fields=['received_amount'])

        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.received_amount, Decimal('250.00'))

    def test_existing_deduction_prevents_invalid_reduction(self):
        self.add_deduction(Decimal('300.00'))
        self.deposit.received_amount = Decimal('299.99')

        with self.assertRaises(ValidationError):
            self.deposit.save()

    def test_existing_refund_prevents_invalid_reduction(self):
        self.add_refund(Decimal('200.00'))
        self.deposit.received_amount = Decimal('199.99')

        with self.assertRaises(ValidationError):
            self.deposit.save()

    def test_deduction_and_refund_totals_are_combined(self):
        self.add_deduction(Decimal('300.00'))
        self.add_refund(Decimal('200.00'))
        self.deposit.received_amount = Decimal('400.00')

        with self.assertRaises(ValidationError):
            self.deposit.save()

    def test_remaining_balance_never_becomes_negative_after_valid_saves(self):
        self.add_deduction(Decimal('300.00'))
        self.add_refund(Decimal('200.00'))
        self.deposit.received_amount = Decimal('500.00')

        self.deposit.save()
        self.deposit.recalc_remaining_balance()
        self.deposit.refresh_from_db()

        self.assertGreaterEqual(self.deposit.remaining_balance, Decimal('0.00'))


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
        self.deduction = DepositDeduction.objects.create(
            deposit=self.deposit,
            authorized_by=self.user,
            amount=Decimal('100.00'),
            reason='Standalone deduction record',
            deduction_date=date(2026, 4, 6),
        )
        self.refund = DepositRefund.objects.create(
            deposit=self.deposit,
            authorized_by=self.user,
            amount=Decimal('100.00'),
            refund_date=date(2026, 4, 7),
            refund_method='Bank Transfer',
            refund_reference='STANDALONE-REFUND',
        )

        self.financial_urls = [
            reverse('operations:deposit_list'),
            reverse('operations:deposit_create'),
            reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}),
            reverse('operations:deposit_edit', kwargs={'pk': self.deposit.pk}),
            reverse('operations:deduction_add', kwargs={'deposit_pk': self.deposit.pk}),
            reverse('operations:deduction_list'),
            reverse('operations:deduction_detail', kwargs={'pk': self.deduction.pk}),
            reverse('operations:refund_add', kwargs={'deposit_pk': self.deposit.pk}),
            reverse('operations:refund_list'),
            reverse('operations:refund_detail', kwargs={'pk': self.refund.pk}),
            reverse('operations:expense_list'),
            reverse('operations:expense_create'),
            reverse('operations:expense_detail', kwargs={'pk': self.expense.pk}),
            reverse('operations:expense_edit', kwargs={'pk': self.expense.pk}),
        ]
        self.maintenance_urls = [
            reverse('operations:maintenance_list'),
            reverse('operations:maintenance_create'),
            reverse('operations:maintenance_detail', kwargs={'pk': self.maintenance.pk}),
            reverse('operations:maintenance_edit', kwargs={'pk': self.maintenance.pk}),
        ]

    def create_user(self, username, role, **kwargs):
        return User.objects.create_user(
            username=username,
            password='password123',
            role=role,
            **kwargs,
        )

    def assert_status_for_urls(self, urls, expected_status):
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, expected_status)

    def test_anonymous_user_redirected_to_login(self):
        self.assert_status_for_urls(self.financial_urls + self.maintenance_urls, 302)

    def test_admin_can_access_all_operations_views(self):
        self.client.force_login(self.create_user('admin', User.Role.ADMIN))
        self.assert_status_for_urls(self.financial_urls + self.maintenance_urls, 200)

    def test_accountant_can_access_financial_views_only(self):
        self.client.force_login(
            self.create_user('accountant', User.Role.ACCOUNTANT)
        )
        self.assert_status_for_urls(self.financial_urls, 200)
        self.assert_status_for_urls(self.maintenance_urls, 403)

    def test_property_manager_can_access_maintenance_views_only(self):
        self.client.force_login(
            self.create_user('property-manager', User.Role.PROPERTY_MANAGER)
        )
        self.assert_status_for_urls(self.financial_urls, 403)
        self.assert_status_for_urls(self.maintenance_urls, 200)

    def test_owner_cannot_access_operations_management(self):
        self.client.force_login(self.create_user('role-owner', User.Role.OWNER))
        self.assert_status_for_urls(self.financial_urls + self.maintenance_urls, 403)

    def test_tenant_cannot_access_operations_management(self):
        self.client.force_login(self.user)
        self.assert_status_for_urls(self.financial_urls + self.maintenance_urls, 403)

    def test_superuser_can_access_all_operations_views(self):
        superuser = self.create_user(
            'superuser',
            User.Role.TENANT,
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(superuser)
        self.assert_status_for_urls(self.financial_urls + self.maintenance_urls, 200)

    def test_financial_forms_do_not_expose_actor_fields(self):
        self.assertNotIn('authorized_by', DepositDeductionForm().fields)
        self.assertNotIn('authorized_by', DepositRefundForm().fields)
        self.assertNotIn('recorded_by', ExpenseForm().fields)

    def test_financial_actions_store_authenticated_actor(self):
        accountant = self.create_user('acting-accountant', User.Role.ACCOUNTANT)
        impersonated_user = self.create_user('impersonated-admin', User.Role.ADMIN)
        self.client.force_login(accountant)

        deduction_response = self.client.post(
            reverse('operations:deduction_add', kwargs={'deposit_pk': self.deposit.pk}),
            {
                'amount': '100.00',
                'reason': 'Cleaning',
                'deduction_date': '2026-04-10',
                'authorized_by': impersonated_user.pk,
            },
        )
        refund_response = self.client.post(
            reverse('operations:refund_add', kwargs={'deposit_pk': self.deposit.pk}),
            {
                'amount': '100.00',
                'refund_date': '2026-04-11',
                'refund_method': 'Bank Transfer',
                'refund_reference': 'AUTH-REFUND',
                'authorized_by': impersonated_user.pk,
            },
        )
        expense_response = self.client.post(
            reverse('operations:expense_create'),
            {
                'property': self.property.pk,
                'unit': self.unit.pk,
                'recorded_by': impersonated_user.pk,
                'expense_reference': 'AUTH-EXPENSE',
                'category': Expense.Category.CLEANING,
                'amount': '75.00',
                'expense_date': '2026-04-12',
                'description': 'Common-area cleaning',
                'status': Expense.ExpenseStatus.RECORDED,
            },
        )

        self.assertEqual(deduction_response.status_code, 302)
        self.assertEqual(refund_response.status_code, 302)
        self.assertEqual(expense_response.status_code, 302)
        self.assertEqual(
            DepositDeduction.objects.get(reason='Cleaning').authorized_by,
            accountant,
        )
        self.assertEqual(
            DepositRefund.objects.get(refund_reference='AUTH-REFUND').authorized_by,
            accountant,
        )
        self.assertEqual(
            Expense.objects.get(expense_reference='AUTH-EXPENSE').recorded_by,
            accountant,
        )

    def test_deduction_record_appears_on_list_with_detail_and_deposit_links(self):
        self.client.force_login(
            self.create_user('deduction-accountant', User.Role.ACCOUNTANT)
        )

        response = self.client.get(reverse('operations:deduction_list'))

        self.assertContains(response, 'Standalone deduction record')
        self.assertContains(
            response,
            reverse('operations:deduction_detail', kwargs={'pk': self.deduction.pk}),
        )
        self.assertContains(
            response,
            reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}),
        )

    def test_deduction_detail_shows_only_requested_record_and_deposit_context(self):
        other = DepositDeduction.objects.create(
            deposit=self.deposit,
            authorized_by=self.user,
            amount=Decimal('50.00'),
            reason='Other deduction record',
            deduction_date=date(2026, 4, 8),
        )
        self.client.force_login(
            self.create_user('deduction-detail-admin', User.Role.ADMIN)
        )

        response = self.client.get(
            reverse('operations:deduction_detail', kwargs={'pk': self.deduction.pk})
        )

        self.assertEqual(response.context['deduction'], self.deduction)
        self.assertContains(response, self.deduction.reason)
        self.assertNotContains(response, other.reason)
        self.assertContains(response, self.contract.contract_reference)
        self.assertContains(
            response,
            reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}),
        )

    def test_refund_record_appears_on_list_with_detail_and_deposit_links(self):
        self.client.force_login(
            self.create_user('refund-accountant', User.Role.ACCOUNTANT)
        )

        response = self.client.get(reverse('operations:refund_list'))

        self.assertContains(response, self.refund.refund_reference)
        self.assertContains(
            response,
            reverse('operations:refund_detail', kwargs={'pk': self.refund.pk}),
        )
        self.assertContains(
            response,
            reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}),
        )

    def test_refund_detail_shows_only_requested_record_and_deposit_context(self):
        other = DepositRefund.objects.create(
            deposit=self.deposit,
            authorized_by=self.user,
            amount=Decimal('50.00'),
            refund_date=date(2026, 4, 8),
            refund_reference='OTHER-STANDALONE-REFUND',
        )
        self.client.force_login(
            self.create_user('refund-detail-admin', User.Role.ADMIN)
        )

        response = self.client.get(
            reverse('operations:refund_detail', kwargs={'pk': self.refund.pk})
        )

        self.assertEqual(response.context['refund'], self.refund)
        self.assertContains(response, self.refund.refund_reference)
        self.assertNotContains(response, other.refund_reference)
        self.assertContains(response, self.contract.contract_reference)
        self.assertContains(
            response,
            reverse('operations:deposit_detail', kwargs={'pk': self.deposit.pk}),
        )
