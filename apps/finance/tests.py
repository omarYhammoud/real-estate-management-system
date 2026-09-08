from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.billing.models import Invoice, Payment, Receipt, RentSchedule
from apps.operations.models import DepositRefund, Expense, SecurityDeposit
from apps.properties.models import Owner, Property, RentalContract, Tenant, Unit

from .models import FinancialTransaction


User = get_user_model()


class DashboardAuthorizationTests(TestCase):
    def test_authorized_roles_can_access_dashboard(self):
        allowed_roles = (
            User.Role.ADMIN,
            User.Role.PROPERTY_MANAGER,
            User.Role.ACCOUNTANT,
            User.Role.OWNER,
        )

        for role in allowed_roles:
            with self.subTest(role=role):
                user = User.objects.create_user(
                    username=role,
                    password='test-password',
                    role=role,
                )
                if role == User.Role.OWNER:
                    Owner.objects.create(user=user, full_name='Authorized Owner')
                self.client.force_login(user)
                response = self.client.get(reverse('finance:dashboard'))
                self.assertEqual(response.status_code, 200)
                self.client.logout()

    def test_tenant_receives_403(self):
        tenant = User.objects.create_user(
            username='tenant',
            password='test-password',
            role=User.Role.TENANT,
        )
        self.client.force_login(tenant)

        self.assertEqual(
            self.client.get(reverse('finance:dashboard')).status_code,
            403,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('finance:dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('finance:dashboard')}",
            fetch_redirect_response=False,
        )


class DashboardKPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='dashboard-accountant',
            password='test-password',
            role=User.Role.ACCOUNTANT,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def dashboard_context(self):
        return self.client.get(reverse('finance:dashboard')).context

    def create_portfolio(self):
        owner = Owner.objects.create(full_name='Dashboard Owner')
        property_object = Property.objects.create(
            owner=owner,
            name='Dashboard Property',
            address='Dashboard Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        occupied_unit = Unit.objects.create(
            property=property_object,
            unit_number='A',
            rent_amount=Decimal('1000.00'),
            status=Unit.Status.OCCUPIED,
        )
        Unit.objects.create(
            property=property_object,
            unit_number='B',
            rent_amount=Decimal('900.00'),
            status=Unit.Status.VACANT,
        )
        tenant = Tenant.objects.create(full_name='Dashboard Tenant')
        contract = RentalContract.objects.create(
            tenant=tenant,
            unit=occupied_unit,
            contract_reference='DASH-CONTRACT',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1000.00'),
            status=RentalContract.Status.ACTIVE,
        )
        return property_object, tenant, contract

    def create_invoice(self, contract, tenant, reference, amount):
        return Invoice.objects.create(
            contract=contract,
            tenant=tenant,
            invoice_reference=reference,
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            total_amount=amount,
        )

    def test_empty_database_returns_zero_kpis(self):
        context = self.dashboard_context()

        self.assertEqual(context['total_properties'], 0)
        self.assertEqual(context['total_units'], 0)
        self.assertEqual(context['occupied_units'], 0)
        self.assertEqual(context['occupancy_rate'], Decimal('0.00'))
        for key in (
            'rent_due',
            'collected_rent',
            'outstanding_rent',
            'total_expenses',
            'revenue',
            'profit_loss',
        ):
            self.assertEqual(context[key], Decimal('0.00'))

    def test_portfolio_counts_occupancy_active_contracts_and_due_rent(self):
        _, _, contract = self.create_portfolio()
        RentSchedule.objects.create(
            contract=contract,
            billing_period_start=date(2026, 1, 1),
            billing_period_end=date(2026, 1, 31),
            due_date=date(2026, 1, 5),
            expected_amount=Decimal('1000.00'),
            status=RentSchedule.Status.PENDING,
        )
        RentSchedule.objects.create(
            contract=contract,
            billing_period_start=date(2026, 2, 1),
            billing_period_end=date(2026, 2, 28),
            due_date=date(2026, 2, 5),
            expected_amount=Decimal('1000.00'),
            status=RentSchedule.Status.CANCELLED,
        )

        context = self.dashboard_context()

        self.assertEqual(context['total_properties'], 1)
        self.assertEqual(context['total_units'], 2)
        self.assertEqual(context['occupied_units'], 1)
        self.assertEqual(context['occupancy_rate'], Decimal('50'))
        self.assertEqual(context['active_contracts'], 1)
        self.assertEqual(context['rent_due'], Decimal('1000.00'))

    def test_financial_kpis_exclude_deposits_from_revenue_and_profit(self):
        transactions = (
            ('RENT-1', FinancialTransaction.TransactionType.RENT_INCOME,
             Decimal('1200.00')),
            ('EXPENSE-1', FinancialTransaction.TransactionType.EXPENSE,
             Decimal('300.00')),
            ('DEPOSIT-1', FinancialTransaction.TransactionType.DEPOSIT,
             Decimal('500.00')),
            ('REFUND-1', FinancialTransaction.TransactionType.DEPOSIT_REFUND,
             Decimal('100.00')),
        )
        for reference, transaction_type, amount in transactions:
            FinancialTransaction.objects.create(
                transaction_reference=reference,
                transaction_type=transaction_type,
                amount=amount,
                transaction_date=date(2026, 1, 1),
            )

        context = self.dashboard_context()

        self.assertEqual(context['collected_rent'], Decimal('1200.00'))
        self.assertEqual(context['revenue'], Decimal('1200.00'))
        self.assertEqual(context['total_expenses'], Decimal('300.00'))
        self.assertEqual(context['profit_loss'], Decimal('900.00'))

    def test_partial_payment_reduces_outstanding_rent(self):
        _, tenant, contract = self.create_portfolio()
        invoice = self.create_invoice(
            contract, tenant, 'PARTIAL-INVOICE', Decimal('1000.00')
        )
        Payment.objects.create(
            invoice=invoice,
            tenant=tenant,
            recorded_by=self.user,
            payment_reference='PARTIAL-PAYMENT',
            payment_date=date(2026, 1, 5),
            amount=Decimal('400.00'),
            payment_method=Payment.Method.CASH,
        )

        self.assertEqual(
            self.dashboard_context()['outstanding_rent'],
            Decimal('600.00'),
        )

    def test_fully_paid_invoice_contributes_zero_outstanding(self):
        _, tenant, contract = self.create_portfolio()
        invoice = self.create_invoice(
            contract, tenant, 'PAID-INVOICE', Decimal('1000.00')
        )
        Payment.objects.create(
            invoice=invoice,
            tenant=tenant,
            recorded_by=self.user,
            payment_reference='FULL-PAYMENT',
            payment_date=date(2026, 1, 5),
            amount=Decimal('1000.00'),
            payment_method=Payment.Method.CARD,
        )

        self.assertEqual(
            self.dashboard_context()['outstanding_rent'],
            Decimal('0.00'),
        )


class FinancialReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='report-accountant',
            password='test-password',
            role=User.Role.ACCOUNTANT,
        )
        owner = Owner.objects.create(full_name='Report Owner')
        cls.property = Property.objects.create(
            owner=owner,
            name='Report Property',
            address='Report Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        cls.other_property = Property.objects.create(
            owner=owner,
            name='Other Property',
            address='Other Address',
            property_type=Property.PropertyType.COMMERCIAL,
        )
        cls.unit = Unit.objects.create(
            property=cls.property,
            unit_number='R1',
            rent_amount=Decimal('1000.00'),
            status=Unit.Status.OCCUPIED,
        )
        cls.other_unit = Unit.objects.create(
            property=cls.other_property,
            unit_number='O1',
            rent_amount=Decimal('800.00'),
        )
        cls.tenant = Tenant.objects.create(full_name='Report Tenant')
        cls.other_tenant = Tenant.objects.create(full_name='Other Tenant')
        cls.contract = RentalContract.objects.create(
            tenant=cls.tenant,
            unit=cls.unit,
            contract_reference='REPORT-CONTRACT',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1000.00'),
            status=RentalContract.Status.ACTIVE,
        )
        cls.other_contract = RentalContract.objects.create(
            tenant=cls.other_tenant,
            unit=cls.other_unit,
            contract_reference='OTHER-CONTRACT',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('800.00'),
        )

    def setUp(self):
        self.client.force_login(self.user)

    def create_transaction(self, reference, transaction_type, amount, transaction_date):
        return FinancialTransaction.objects.create(
            transaction_reference=reference,
            transaction_type=transaction_type,
            amount=amount,
            transaction_date=transaction_date,
        )

    def create_invoice(self, reference, amount, tenant=None, contract=None):
        return Invoice.objects.create(
            contract=contract or self.contract,
            tenant=tenant or self.tenant,
            invoice_reference=reference,
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            total_amount=amount,
        )

    def create_payment(self, invoice, reference, amount, payment_date=date(2026, 1, 5)):
        return Payment.objects.create(
            invoice=invoice,
            tenant=invoice.tenant,
            recorded_by=self.user,
            payment_reference=reference,
            payment_date=payment_date,
            amount=amount,
            payment_method=Payment.Method.BANK_TRANSFER,
        )

    def test_report_index_authorization(self):
        self.client.logout()
        self.assertRedirects(
            self.client.get(reverse('finance:reports')),
            f"{reverse('accounts:login')}?next={reverse('finance:reports')}",
            fetch_redirect_response=False,
        )
        for role in (User.Role.ADMIN, User.Role.ACCOUNTANT, User.Role.OWNER):
            with self.subTest(role=role):
                user = User.objects.create_user(username=f'authorized-{role}', role=role)
                if role == User.Role.OWNER:
                    Owner.objects.create(user=user, full_name='Report Authorized Owner')
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse('finance:reports')).status_code, 200)
                self.client.logout()
        for role in (User.Role.PROPERTY_MANAGER, User.Role.TENANT):
            with self.subTest(role=role):
                user = User.objects.create_user(username=f'denied-{role}', role=role)
                self.client.force_login(user)
                self.assertEqual(
                    self.client.get(reverse('finance:reports')).status_code,
                    403,
                )
                self.client.logout()

    def test_profit_loss_types_and_date_filtering(self):
        self.create_transaction('PL-RENT', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('1000.00'), date(2026, 2, 1))
        self.create_transaction('PL-OLD', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('200.00'), date(2026, 1, 1))
        self.create_transaction('PL-EXP', FinancialTransaction.TransactionType.EXPENSE, Decimal('250.00'), date(2026, 2, 2))
        self.create_transaction('PL-DEP', FinancialTransaction.TransactionType.DEPOSIT, Decimal('500.00'), date(2026, 2, 2))
        self.create_transaction('PL-REF', FinancialTransaction.TransactionType.DEPOSIT_REFUND, Decimal('100.00'), date(2026, 2, 2))

        context = self.client.get(reverse('finance:report_profit_loss'), {'start_date': '2026-02-01'}).context

        self.assertEqual(context['revenue'], Decimal('1000.00'))
        self.assertEqual(context['expenses'], Decimal('250.00'))
        self.assertEqual(context['profit_loss'], Decimal('750.00'))

    def test_invalid_date_filter_fails_closed(self):
        self.create_transaction('INVALID-DATE', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('300.00'), date(2026, 1, 1))

        response = self.client.get(reverse('finance:report_revenue'), {'start_date': 'not-a-date'})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['filter_form'].is_valid())
        self.assertEqual(response.context['total_revenue'], Decimal('0.00'))
        self.assertEqual(response.context['transaction_count'], 0)

    def test_reversed_date_range_fails_closed(self):
        self.create_transaction('REVERSED-DATE', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('300.00'), date(2026, 1, 1))

        response = self.client.get(reverse('finance:report_revenue'), {
            'start_date': '2026-02-01',
            'end_date': '2026-01-01',
        })

        self.assertFalse(response.context['filter_form'].is_valid())
        self.assertEqual(response.context['total_revenue'], Decimal('0.00'))
        self.assertEqual(response.context['transaction_count'], 0)

    def test_valid_empty_date_range_returns_no_unrelated_records(self):
        self.create_transaction('OUTSIDE-RANGE', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('300.00'), date(2026, 1, 1))

        context = self.client.get(reverse('finance:report_revenue'), {
            'start_date': '2026-03-01',
            'end_date': '2026-03-31',
        }).context

        self.assertEqual(context['total_revenue'], Decimal('0.00'))
        self.assertEqual(context['transaction_count'], 0)

    def test_revenue_summary_only_counts_rent_income_in_date_range(self):
        self.create_transaction('REV-IN', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('600.00'), date(2026, 3, 1))
        self.create_transaction('REV-OUT', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('400.00'), date(2026, 1, 1))
        self.create_transaction('REV-DEP', FinancialTransaction.TransactionType.DEPOSIT, Decimal('900.00'), date(2026, 3, 1))

        context = self.client.get(reverse('finance:report_revenue'), {'start_date': '2026-02-01', 'end_date': '2026-03-31'}).context

        self.assertEqual(context['total_revenue'], Decimal('600.00'))
        self.assertEqual(context['transaction_count'], 1)

    def test_expense_summary_total_categories_and_date_filter(self):
        Expense.objects.create(property=self.property, recorded_by=self.user, expense_reference='ELEC-1', category=Expense.Category.ELECTRICITY, amount=Decimal('100.00'), expense_date=date(2026, 2, 1))
        Expense.objects.create(property=self.property, recorded_by=self.user, expense_reference='MAINT-1', category=Expense.Category.MAINTENANCE, amount=Decimal('250.00'), expense_date=date(2026, 2, 2))
        Expense.objects.create(property=self.property, recorded_by=self.user, expense_reference='OLD-EXP', category=Expense.Category.ELECTRICITY, amount=Decimal('50.00'), expense_date=date(2026, 1, 1))

        context = self.client.get(reverse('finance:report_expenses'), {'start_date': '2026-02-01'}).context

        self.assertEqual(context['total_expenses'], Decimal('350.00'))
        self.assertEqual(context['expense_count'], 2)
        totals = {row['category']: row['total'] for row in context['category_breakdown']}
        self.assertEqual(totals[Expense.Category.ELECTRICITY], Decimal('100.00'))
        self.assertEqual(totals[Expense.Category.MAINTENANCE], Decimal('250.00'))

    def test_cancelled_expenses_are_excluded_from_expense_reports(self):
        Expense.objects.create(property=self.property, recorded_by=self.user, expense_reference='ACTIVE-REPORT-EXP', category=Expense.Category.MAINTENANCE, amount=Decimal('100.00'), expense_date=date(2026, 2, 1))
        Expense.objects.create(property=self.property, recorded_by=self.user, expense_reference='CANCELLED-REPORT-EXP', category=Expense.Category.MAINTENANCE, amount=Decimal('900.00'), expense_date=date(2026, 2, 1), status=Expense.ExpenseStatus.CANCELLED)

        expense_context = self.client.get(reverse('finance:report_expenses')).context
        property_context = self.client.get(
            reverse('finance:report_property_performance'),
            {'property': self.property.pk},
        ).context

        self.assertEqual(expense_context['total_expenses'], Decimal('100.00'))
        self.assertEqual(expense_context['expense_count'], 1)
        self.assertEqual(property_context['total_expenses'], Decimal('100.00'))

    def test_receivables_include_open_balances_and_exclude_paid(self):
        unpaid = self.create_invoice('UNPAID', Decimal('1000.00'))
        partial = self.create_invoice('PARTIAL', Decimal('800.00'))
        paid = self.create_invoice('PAID', Decimal('500.00'))
        self.create_payment(partial, 'PARTIAL-PAY', Decimal('300.00'))
        self.create_payment(paid, 'PAID-PAY', Decimal('500.00'))

        context = self.client.get(reverse('finance:report_receivables')).context
        balances = {row['invoice'].pk: row['outstanding_balance'] for row in context['receivables']}

        self.assertEqual(balances[unpaid.pk], Decimal('1000.00'))
        self.assertEqual(balances[partial.pk], Decimal('500.00'))
        self.assertNotIn(paid.pk, balances)
        self.assertEqual(context['total_outstanding'], Decimal('1500.00'))

    def test_receivables_use_balances_when_invoice_status_is_stale(self):
        stale_paid = self.create_invoice('STALE-PAID', Decimal('100.00'))
        stale_paid.status = Invoice.Status.PAID
        stale_paid.save(update_fields=['status'])
        partial = self.create_invoice('STALE-PARTIAL', Decimal('100.00'))
        self.create_payment(partial, 'STALE-PARTIAL-PAY', Decimal('40.00'))
        overpaid = self.create_invoice('OVERPAID', Decimal('100.00'))
        legacy_payment = self.create_payment(overpaid, 'OVERPAYMENT', Decimal('100.00'))
        Payment.objects.filter(pk=legacy_payment.pk).update(amount=Decimal('125.00'))

        context = self.client.get(reverse('finance:report_receivables')).context
        balances = {
            row['invoice'].pk: row['outstanding_balance']
            for row in context['receivables']
        }

        self.assertEqual(balances[stale_paid.pk], Decimal('100.00'))
        self.assertEqual(balances[partial.pk], Decimal('60.00'))
        self.assertNotIn(overpaid.pk, balances)
        self.assertEqual(context['total_outstanding'], Decimal('160.00'))

    def test_payment_deletion_refreshes_invoice_and_exposes_balance(self):
        invoice = self.create_invoice('DELETED-PAYMENT-INVOICE', Decimal('100.00'))
        payment = self.create_payment(
            invoice,
            'DELETED-PAYMENT',
            Decimal('100.00'),
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

        payment.delete()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)

        report_context = self.client.get(
            reverse('finance:report_receivables')
        ).context
        dashboard_context = self.client.get(reverse('finance:dashboard')).context

        balances = {
            row['invoice'].pk: row['outstanding_balance']
            for row in report_context['receivables']
        }
        self.assertEqual(balances[invoice.pk], Decimal('100.00'))
        self.assertEqual(
            dashboard_context['outstanding_rent'],
            Decimal('100.00'),
        )

    def test_payment_report_filters_total_and_exposes_relations(self):
        invoice = self.create_invoice('PAY-REPORT-INVOICE', Decimal('1000.00'))
        included = self.create_payment(invoice, 'PAY-IN', Decimal('400.00'), date(2026, 4, 1))
        self.create_payment(invoice, 'PAY-OUT', Decimal('100.00'), date(2026, 1, 1))

        context = self.client.get(reverse('finance:report_payments'), {'start_date': '2026-04-01'}).context

        self.assertEqual(context['total_payments'], Decimal('400.00'))
        self.assertEqual(list(context['payments']), [included])
        self.assertEqual(included.tenant, self.tenant)
        self.assertEqual(included.invoice, invoice)
        self.assertEqual(included.payment_method, Payment.Method.BANK_TRANSFER)

    def test_transaction_report_filters_date_and_type(self):
        included = self.create_transaction('TX-IN', FinancialTransaction.TransactionType.EXPENSE, Decimal('75.00'), date(2026, 5, 1))
        self.create_transaction('TX-WRONG-TYPE', FinancialTransaction.TransactionType.RENT_INCOME, Decimal('100.00'), date(2026, 5, 1))
        self.create_transaction('TX-WRONG-DATE', FinancialTransaction.TransactionType.EXPENSE, Decimal('50.00'), date(2026, 1, 1))

        context = self.client.get(reverse('finance:report_transactions'), {'start_date': '2026-05-01', 'transaction_type': FinancialTransaction.TransactionType.EXPENSE}).context

        self.assertEqual(context['transaction_count'], 1)
        self.assertEqual(list(context['transactions']), [included])

    def test_tenant_statement_handles_multiple_invoices_and_payments(self):
        first = self.create_invoice('STATEMENT-1', Decimal('1000.00'))
        second = self.create_invoice('STATEMENT-2', Decimal('500.00'))
        first_payment = self.create_payment(first, 'STATEMENT-PAY-1', Decimal('400.00'))
        self.create_payment(second, 'STATEMENT-PAY-2', Decimal('500.00'))
        Receipt.objects.create(payment=first_payment, receipt_reference='STATEMENT-RECEIPT', receipt_date=date(2026, 1, 5), amount=Decimal('400.00'))

        context = self.client.get(reverse('finance:report_tenant_statement'), {'tenant': self.tenant.pk}).context

        self.assertEqual(context['selected_tenant'], self.tenant)
        self.assertEqual(context['total_invoiced'], Decimal('1500.00'))
        self.assertEqual(context['total_paid'], Decimal('900.00'))
        self.assertEqual(context['period_net_balance'], Decimal('600.00'))
        self.assertEqual(len(context['invoice_rows']), 2)
        self.assertEqual(context['receipts'].count(), 1)

    def test_tenant_statement_cross_period_semantics_and_boundaries(self):
        invoice = self.create_invoice('CROSS-PERIOD', Decimal('100.00'))
        invoice.issue_date = date(2026, 1, 10)
        invoice.save(update_fields=['issue_date'])
        payment = self.create_payment(
            invoice,
            'CROSS-PERIOD-PAYMENT',
            Decimal('100.00'),
            date(2026, 2, 10),
        )
        Receipt.objects.create(
            payment=payment,
            receipt_reference='CROSS-PERIOD-RECEIPT',
            receipt_date=date(2026, 2, 11),
            amount=Decimal('100.00'),
        )
        url = reverse('finance:report_tenant_statement')

        january = self.client.get(url, {
            'tenant': self.tenant.pk,
            'start_date': '2026-01-10',
            'end_date': '2026-01-10',
        }).context
        self.assertEqual(january['total_invoiced'], Decimal('100.00'))
        self.assertEqual(january['total_paid'], Decimal('0.00'))
        self.assertEqual(january['period_net_balance'], Decimal('100.00'))
        self.assertEqual(january['invoice_rows'][0]['period_paid'], Decimal('0.00'))
        self.assertEqual(january['invoice_rows'][0]['period_invoice_net'], Decimal('100.00'))
        self.assertEqual(list(january['payments']), [])
        self.assertEqual(list(january['receipts']), [])

        february = self.client.get(url, {
            'tenant': self.tenant.pk,
            'start_date': '2026-02-10',
            'end_date': '2026-02-10',
        }).context
        self.assertEqual(february['total_invoiced'], Decimal('0.00'))
        self.assertEqual(february['total_paid'], Decimal('100.00'))
        self.assertEqual(february['period_net_balance'], Decimal('-100.00'))
        self.assertEqual(february['invoice_rows'], [])
        self.assertEqual(list(february['payments']), [payment])
        self.assertEqual(february['receipts'].count(), 1)

        full_history = self.client.get(url, {'tenant': self.tenant.pk}).context
        self.assertEqual(full_history['total_invoiced'], Decimal('100.00'))
        self.assertEqual(full_history['total_paid'], Decimal('100.00'))
        self.assertEqual(full_history['period_net_balance'], Decimal('0.00'))
        self.assertEqual(full_history['invoice_rows'][0]['period_paid'], Decimal('100.00'))
        self.assertEqual(full_history['receipts'].count(), 1)

        start_only = self.client.get(url, {
            'tenant': self.tenant.pk,
            'start_date': '2026-02-10',
        }).context
        self.assertEqual(start_only['total_invoiced'], Decimal('0.00'))
        self.assertEqual(start_only['total_paid'], Decimal('100.00'))
        self.assertEqual(start_only['period_net_balance'], Decimal('-100.00'))
        self.assertEqual(start_only['receipts'].count(), 1)

        end_only = self.client.get(url, {
            'tenant': self.tenant.pk,
            'end_date': '2026-01-10',
        }).context
        self.assertEqual(end_only['total_invoiced'], Decimal('100.00'))
        self.assertEqual(end_only['total_paid'], Decimal('0.00'))
        self.assertEqual(end_only['period_net_balance'], Decimal('100.00'))
        self.assertEqual(end_only['receipts'].count(), 0)

    def test_property_performance_attributes_only_related_sources(self):
        invoice = self.create_invoice('PROPERTY-INVOICE', Decimal('1000.00'))
        other_invoice = self.create_invoice('OTHER-PROPERTY-INVOICE', Decimal('800.00'), self.other_tenant, self.other_contract)
        self.create_payment(invoice, 'PROPERTY-PAY', Decimal('700.00'))
        self.create_payment(other_invoice, 'OTHER-PROPERTY-PAY', Decimal('600.00'))
        Expense.objects.create(property=self.property, recorded_by=self.user, expense_reference='PROPERTY-EXP', category=Expense.Category.OTHER, amount=Decimal('200.00'), expense_date=date(2026, 1, 6))
        Expense.objects.create(property=self.other_property, recorded_by=self.user, expense_reference='OTHER-PROPERTY-EXP', category=Expense.Category.OTHER, amount=Decimal('50.00'), expense_date=date(2026, 1, 6))

        context = self.client.get(reverse('finance:report_property_performance'), {'property': self.property.pk}).context

        self.assertEqual(len(context['property_rows']), 1)
        row = context['property_rows'][0]
        self.assertEqual(row['property'], self.property)
        self.assertEqual(row['revenue'], Decimal('700.00'))
        self.assertEqual(row['expenses'], Decimal('200.00'))
        self.assertEqual(row['profit_loss'], Decimal('500.00'))
        self.assertEqual(row['property'].unit_count, 1)
        self.assertEqual(row['property'].occupied_count, 1)


class LedgerSynchronizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(
            username='ledger-accountant',
            role=User.Role.ACCOUNTANT,
        )
        owner = Owner.objects.create(full_name='Test Owner')
        cls.property = Property.objects.create(
            owner=owner,
            name='Test Property',
            address='Test Address',
            property_type=Property.PropertyType.RESIDENTIAL,
        )
        unit = Unit.objects.create(
            property=cls.property,
            unit_number='1A',
            rent_amount=Decimal('1000.00'),
        )
        cls.tenant = Tenant.objects.create(full_name='Test Tenant')
        cls.contract = RentalContract.objects.create(
            tenant=cls.tenant,
            unit=unit,
            contract_reference='CONTRACT-1',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            monthly_rent=Decimal('1000.00'),
        )
        cls.invoice = Invoice.objects.create(
            contract=cls.contract,
            tenant=cls.tenant,
            invoice_reference='INVOICE-1',
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            total_amount=Decimal('1000.00'),
        )

    def create_payment(self, reference='PAYMENT-1', **overrides):
        values = {
            'invoice': self.invoice,
            'tenant': self.tenant,
            'recorded_by': self.user,
            'payment_reference': reference,
            'payment_date': date(2026, 1, 5),
            'amount': Decimal('400.00'),
            'payment_method': Payment.Method.BANK_TRANSFER,
        }
        values.update(overrides)
        return Payment.objects.create(**values)

    def create_expense(self, reference='EXPENSE-1', **overrides):
        values = {
            'property': self.property,
            'recorded_by': self.user,
            'expense_reference': reference,
            'category': Expense.Category.MAINTENANCE,
            'amount': Decimal('125.00'),
            'expense_date': date(2026, 1, 6),
        }
        values.update(overrides)
        return Expense.objects.create(**values)

    def create_deposit(self, **overrides):
        values = {
            'contract': self.contract,
            'required_amount': Decimal('500.00'),
            'received_amount': Decimal('500.00'),
            'received_date': date(2026, 1, 2),
            'remaining_balance': Decimal('500.00'),
        }
        values.update(overrides)
        return SecurityDeposit.objects.create(**values)

    def test_payment_creation_populates_ledger_fields(self):
        payment = self.create_payment()

        transaction = FinancialTransaction.objects.get(
            transaction_reference=f'PAY-{payment.pk}'
        )
        self.assertEqual(
            transaction.transaction_type,
            FinancialTransaction.TransactionType.RENT_INCOME,
        )
        self.assertEqual(transaction.amount, payment.amount)
        self.assertEqual(transaction.transaction_date, payment.payment_date)
        self.assertEqual(transaction.recorded_by, self.user)
        self.assertEqual(transaction.related_entity_type, 'payment')
        self.assertEqual(transaction.related_entity_id, payment.pk)

    def test_payment_repeated_save_and_edit_update_one_row(self):
        payment = self.create_payment()
        payment.amount = Decimal('450.00')
        payment.payment_date = date(2026, 1, 7)
        payment.save()

        transactions = FinancialTransaction.objects.filter(
            transaction_reference=f'PAY-{payment.pk}'
        )
        self.assertEqual(transactions.count(), 1)
        transaction = transactions.get()
        self.assertEqual(transaction.amount, Decimal('450.00'))
        self.assertEqual(transaction.transaction_date, date(2026, 1, 7))

    def test_payment_partial_update_uses_persisted_values(self):
        payment = self.create_payment()
        original_amount = payment.amount
        payment.amount = Decimal('999.00')
        payment.payment_date = date(2026, 1, 12)
        payment.save(update_fields=['payment_date'])

        transaction = FinancialTransaction.objects.get(
            transaction_reference=f'PAY-{payment.pk}'
        )
        payment.refresh_from_db()
        self.assertEqual(payment.amount, original_amount)
        self.assertEqual(transaction.amount, original_amount)
        self.assertEqual(transaction.transaction_date, date(2026, 1, 12))

    def test_expense_creation_and_edit_update_one_row(self):
        expense = self.create_expense()
        expense.amount = Decimal('150.00')
        expense.expense_date = date(2026, 1, 8)
        expense.save()

        transactions = FinancialTransaction.objects.filter(
            transaction_reference=f'EXP-{expense.pk}'
        )
        self.assertEqual(transactions.count(), 1)
        transaction = transactions.get()
        self.assertEqual(
            transaction.transaction_type,
            FinancialTransaction.TransactionType.EXPENSE,
        )
        self.assertEqual(transaction.amount, Decimal('150.00'))
        self.assertEqual(transaction.transaction_date, date(2026, 1, 8))
        self.assertEqual(transaction.recorded_by, self.user)
        self.assertEqual(transaction.related_entity_type, 'expense')
        self.assertEqual(transaction.related_entity_id, expense.pk)

    def test_expense_partial_update_uses_persisted_values(self):
        expense = self.create_expense()
        original_amount = expense.amount
        expense.amount = Decimal('999.00')
        expense.expense_date = date(2026, 1, 12)
        expense.save(update_fields=['expense_date'])

        transaction = FinancialTransaction.objects.get(
            transaction_reference=f'EXP-{expense.pk}'
        )
        expense.refresh_from_db()
        self.assertEqual(expense.amount, original_amount)
        self.assertEqual(transaction.amount, original_amount)
        self.assertEqual(transaction.transaction_date, date(2026, 1, 12))

    def test_unreceived_deposit_does_not_create_transaction(self):
        deposit = self.create_deposit(
            received_amount=Decimal('0.00'),
            received_date=None,
        )

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=f'DEP-{deposit.pk}'
            ).exists()
        )

    def test_received_deposit_creates_and_updates_one_deposit_row(self):
        deposit = self.create_deposit()
        deposit.received_amount = Decimal('550.00')
        deposit.received_date = date(2026, 1, 3)
        deposit.save()

        transactions = FinancialTransaction.objects.filter(
            transaction_reference=f'DEP-{deposit.pk}'
        )
        self.assertEqual(transactions.count(), 1)
        transaction = transactions.get()
        self.assertEqual(
            transaction.transaction_type,
            FinancialTransaction.TransactionType.DEPOSIT,
        )
        self.assertNotEqual(
            transaction.transaction_type,
            FinancialTransaction.TransactionType.RENT_INCOME,
        )
        self.assertEqual(transaction.amount, Decimal('550.00'))
        self.assertEqual(transaction.transaction_date, date(2026, 1, 3))
        self.assertIsNone(transaction.recorded_by)
        self.assertEqual(transaction.related_entity_type, 'security_deposit')
        self.assertEqual(transaction.related_entity_id, deposit.pk)

    def test_deposit_partial_update_uses_persisted_values(self):
        deposit = self.create_deposit()
        original_amount = deposit.received_amount
        deposit.received_amount = Decimal('999.00')
        deposit.received_date = date(2026, 1, 12)
        deposit.save(update_fields=['received_date'])

        transaction = FinancialTransaction.objects.get(
            transaction_reference=f'DEP-{deposit.pk}'
        )
        deposit.refresh_from_db()
        self.assertEqual(deposit.received_amount, original_amount)
        self.assertEqual(transaction.amount, original_amount)
        self.assertEqual(transaction.transaction_date, date(2026, 1, 12))

    def test_deposit_changed_to_unreceived_removes_transaction(self):
        deposit = self.create_deposit()
        deposit.received_amount = Decimal('0.00')
        deposit.received_date = None
        deposit.save()

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=f'DEP-{deposit.pk}'
            ).exists()
        )

    def test_refund_creation_and_edit_update_one_row(self):
        deposit = self.create_deposit()
        refund = DepositRefund.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 1, 9),
            amount=Decimal('100.00'),
            refund_method='bank_transfer',
            refund_reference='REFUND-1',
        )
        refund.amount = Decimal('125.00')
        refund.refund_date = date(2026, 1, 10)
        refund.save()

        transactions = FinancialTransaction.objects.filter(
            transaction_reference=f'REF-{refund.pk}'
        )
        self.assertEqual(transactions.count(), 1)
        transaction = transactions.get()
        self.assertEqual(
            transaction.transaction_type,
            FinancialTransaction.TransactionType.DEPOSIT_REFUND,
        )
        self.assertEqual(transaction.amount, Decimal('125.00'))
        self.assertEqual(transaction.transaction_date, date(2026, 1, 10))
        self.assertEqual(transaction.recorded_by, self.user)
        self.assertEqual(transaction.related_entity_type, 'deposit_refund')
        self.assertEqual(transaction.related_entity_id, refund.pk)

    def test_refund_partial_update_uses_persisted_values(self):
        deposit = self.create_deposit()
        refund = DepositRefund.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 1, 9),
            amount=Decimal('100.00'),
            refund_reference='PARTIAL-UPDATE-REFUND',
        )
        refund.amount = Decimal('999.00')
        refund.refund_date = date(2026, 1, 12)
        refund.save(update_fields=['refund_date'])

        transaction = FinancialTransaction.objects.get(
            transaction_reference=f'REF-{refund.pk}'
        )
        refund.refresh_from_db()
        self.assertEqual(refund.amount, Decimal('100.00'))
        self.assertEqual(transaction.amount, Decimal('100.00'))
        self.assertEqual(transaction.transaction_date, date(2026, 1, 12))

    def test_payment_delete_removes_generated_transaction(self):
        payment = self.create_payment()
        reference = f'PAY-{payment.pk}'

        payment.delete()

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=reference
            ).exists()
        )

    def test_expense_delete_removes_generated_transaction(self):
        expense = self.create_expense()
        reference = f'EXP-{expense.pk}'

        expense.delete()

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=reference
            ).exists()
        )

    def test_security_deposit_delete_removes_generated_transaction(self):
        deposit = self.create_deposit()
        reference = f'DEP-{deposit.pk}'

        deposit.delete()

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=reference
            ).exists()
        )

    def test_deposit_refund_delete_removes_generated_transaction(self):
        deposit = self.create_deposit()
        refund = DepositRefund.objects.create(
            deposit=deposit,
            authorized_by=self.user,
            refund_date=date(2026, 1, 9),
            amount=Decimal('100.00'),
            refund_reference='DELETE-REFUND',
        )
        reference = f'REF-{refund.pk}'

        refund.delete()

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=reference
            ).exists()
        )

    def test_source_delete_preserves_other_and_manual_transactions(self):
        payment = self.create_payment()
        expense = self.create_expense()
        manual = FinancialTransaction.objects.create(
            transaction_reference='MANUAL-ENTRY',
            transaction_type=FinancialTransaction.TransactionType.OTHER,
            amount=Decimal('25.00'),
            transaction_date=date(2026, 1, 15),
        )

        payment.delete()

        self.assertTrue(
            FinancialTransaction.objects.filter(
                transaction_reference=f'EXP-{expense.pk}'
            ).exists()
        )
        self.assertTrue(
            FinancialTransaction.objects.filter(pk=manual.pk).exists()
        )

    def test_cancelled_expense_does_not_create_transaction(self):
        expense = self.create_expense(
            status=Expense.ExpenseStatus.CANCELLED,
        )

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=f'EXP-{expense.pk}'
            ).exists()
        )

    def test_active_expense_changed_to_cancelled_removes_transaction(self):
        expense = self.create_expense()
        reference = f'EXP-{expense.pk}'

        expense.status = Expense.ExpenseStatus.CANCELLED
        expense.save(update_fields=['status'])

        self.assertFalse(
            FinancialTransaction.objects.filter(
                transaction_reference=reference
            ).exists()
        )

    def test_cancelled_expense_restored_recreates_transaction(self):
        expense = self.create_expense(
            status=Expense.ExpenseStatus.CANCELLED,
        )
        expense.status = Expense.ExpenseStatus.APPROVED
        expense.save(update_fields=['status'])

        transaction = FinancialTransaction.objects.get(
            transaction_reference=f'EXP-{expense.pk}'
        )
        self.assertEqual(
            transaction.transaction_type,
            FinancialTransaction.TransactionType.EXPENSE,
        )
        self.assertEqual(transaction.amount, expense.amount)

    def test_cancelled_expenses_are_excluded_from_dashboard_and_profit_loss(self):
        self.create_expense(reference='ACTIVE-EXPENSE')
        self.create_expense(
            reference='CANCELLED-EXPENSE',
            amount=Decimal('75.00'),
            status=Expense.ExpenseStatus.CANCELLED,
        )
        self.client.force_login(self.user)

        dashboard = self.client.get(reverse('finance:dashboard')).context
        report = self.client.get(reverse('finance:report_profit_loss')).context

        self.assertEqual(dashboard['total_expenses'], Decimal('125.00'))
        self.assertEqual(report['expenses'], Decimal('125.00'))

    def test_different_sources_have_unique_deterministic_references(self):
        first_payment = self.create_payment()
        second_payment = self.create_payment(reference='PAYMENT-2')
        expense = self.create_expense()

        references = set(
            FinancialTransaction.objects.values_list(
                'transaction_reference', flat=True
            )
        )
        self.assertEqual(
            references,
            {
                f'PAY-{first_payment.pk}',
                f'PAY-{second_payment.pk}',
                f'EXP-{expense.pk}',
            },
        )


class FinanceOwnershipScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner_user = User.objects.create_user(username='scoped-owner', role=User.Role.OWNER)
        cls.owner = Owner.objects.create(user=cls.owner_user, full_name='Scoped Owner')
        cls.other_owner = Owner.objects.create(full_name='Other Owner')
        cls.property = Property.objects.create(owner=cls.owner, name='Scoped Property', address='Scoped Address', property_type=Property.PropertyType.RESIDENTIAL)
        cls.other_property = Property.objects.create(owner=cls.other_owner, name='Other Property', address='Other Address', property_type=Property.PropertyType.COMMERCIAL)
        cls.unit = Unit.objects.create(property=cls.property, unit_number='OWN-1', rent_amount=Decimal('1000.00'), status=Unit.Status.OCCUPIED)
        cls.other_unit = Unit.objects.create(property=cls.other_property, unit_number='OTHER-1', rent_amount=Decimal('2000.00'), status=Unit.Status.OCCUPIED)
        cls.tenant_user = User.objects.create_user(username='scoped-tenant', role=User.Role.TENANT)
        cls.tenant = Tenant.objects.create(user=cls.tenant_user, full_name='Scoped Tenant')
        cls.other_tenant = Tenant.objects.create(full_name='Other Tenant')
        cls.contract = RentalContract.objects.create(tenant=cls.tenant, unit=cls.unit, contract_reference='OWN-CONTRACT', start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=Decimal('1000.00'), status=RentalContract.Status.ACTIVE)
        cls.other_contract = RentalContract.objects.create(tenant=cls.other_tenant, unit=cls.other_unit, contract_reference='OTHER-OWNER-CONTRACT', start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), monthly_rent=Decimal('2000.00'), status=RentalContract.Status.ACTIVE)
        cls.invoice = Invoice.objects.create(contract=cls.contract, tenant=cls.tenant, invoice_reference='OWN-INVOICE', issue_date=date(2026, 1, 1), due_date=date(2026, 1, 10), total_amount=Decimal('1000.00'))
        cls.other_invoice = Invoice.objects.create(contract=cls.other_contract, tenant=cls.other_tenant, invoice_reference='OTHER-OWNER-INVOICE', issue_date=date(2026, 1, 1), due_date=date(2026, 1, 10), total_amount=Decimal('2000.00'))
        accountant = User.objects.create_user(username='scope-accountant', role=User.Role.ACCOUNTANT)
        cls.payment = Payment.objects.create(invoice=cls.invoice, tenant=cls.tenant, recorded_by=accountant, payment_reference='OWN-PAYMENT', payment_date=date(2026, 1, 5), amount=Decimal('400.00'), payment_method=Payment.Method.CASH)
        cls.other_payment = Payment.objects.create(invoice=cls.other_invoice, tenant=cls.other_tenant, recorded_by=accountant, payment_reference='OTHER-OWNER-PAYMENT', payment_date=date(2026, 1, 5), amount=Decimal('800.00'), payment_method=Payment.Method.CASH)
        Expense.objects.create(property=cls.property, recorded_by=accountant, expense_reference='OWN-EXPENSE', category=Expense.Category.MAINTENANCE, amount=Decimal('100.00'), expense_date=date(2026, 1, 6))
        Expense.objects.create(property=cls.other_property, recorded_by=accountant, expense_reference='OTHER-OWNER-EXPENSE', category=Expense.Category.MAINTENANCE, amount=Decimal('300.00'), expense_date=date(2026, 1, 6))

    def test_owner_dashboard_is_scoped_to_owned_properties(self):
        self.client.force_login(self.owner_user)
        context = self.client.get(reverse('finance:dashboard')).context
        self.assertEqual(context['total_properties'], 1)
        self.assertEqual(context['total_units'], 1)
        self.assertEqual(context['active_contracts'], 1)
        self.assertEqual(context['revenue'], Decimal('400.00'))
        self.assertEqual(context['total_expenses'], Decimal('100.00'))
        self.assertEqual(context['outstanding_rent'], Decimal('600.00'))

    def test_owner_reports_exclude_other_owner_data(self):
        self.client.force_login(self.owner_user)
        self.assertEqual(self.client.get(reverse('finance:report_revenue')).context['total_revenue'], Decimal('400.00'))
        self.assertEqual(self.client.get(reverse('finance:report_expenses')).context['total_expenses'], Decimal('100.00'))
        self.assertEqual(self.client.get(reverse('finance:report_receivables')).context['total_outstanding'], Decimal('600.00'))
        self.assertEqual(self.client.get(reverse('finance:report_payments')).context['total_payments'], Decimal('400.00'))
        response = self.client.get(reverse('finance:report_transactions'))
        self.assertEqual(response.context['transaction_count'], 2)
        self.assertNotContains(response, f'PAY-{self.other_payment.pk}')

    def test_owner_property_filter_cannot_select_other_owner_property(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse('finance:report_property_performance'), {'property': self.other_property.pk})
        self.assertFalse(response.context['filter_form'].is_valid())
        self.assertEqual([row['property'] for row in response.context['property_rows']], [self.property])

    def test_owner_property_performance_counts_unit_only_expense(self):
        Expense.objects.create(
            property=None,
            unit=self.unit,
            expense_reference='OWN-UNIT-ONLY-EXPENSE',
            category=Expense.Category.REPAIRS,
            amount=Decimal('50.00'),
            expense_date=date(2026, 1, 7),
        )
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse('finance:report_property_performance'))
        row = response.context['property_rows'][0]
        self.assertEqual(row['expenses'], Decimal('150.00'))
        self.assertEqual(response.context['total_expenses'], Decimal('150.00'))

    def test_tenant_statement_forces_linked_tenant(self):
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse('finance:report_tenant_statement'), {'tenant': self.other_tenant.pk})
        self.assertEqual(response.context['selected_tenant'], self.tenant)
        self.assertContains(response, self.invoice.invoice_reference)
        self.assertNotContains(response, self.other_invoice.invoice_reference)

    def test_unlinked_owner_and_tenant_fail_safely(self):
        self.client.force_login(User.objects.create_user(username='unlinked-owner', role=User.Role.OWNER))
        self.assertEqual(self.client.get(reverse('finance:dashboard')).status_code, 403)
        self.client.force_login(User.objects.create_user(username='unlinked-statement-tenant', role=User.Role.TENANT))
        self.assertEqual(self.client.get(reverse('finance:report_tenant_statement')).status_code, 403)

    def test_admin_and_accountant_still_see_global_finance_data(self):
        for role in (User.Role.ADMIN, User.Role.ACCOUNTANT):
            with self.subTest(role=role):
                self.client.force_login(User.objects.create_user(username=f'global-{role}', role=role))
                context = self.client.get(reverse('finance:dashboard')).context
                self.assertEqual(context['total_properties'], 2)
                self.assertEqual(context['revenue'], Decimal('1200.00'))
                self.client.logout()
