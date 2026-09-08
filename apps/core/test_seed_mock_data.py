from decimal import Decimal

from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase, override_settings

from apps.billing.models import Invoice, Payment, Receipt, RentSchedule
from apps.finance.models import FinancialTransaction
from apps.operations.models import Expense, MaintenanceRequest, SecurityDeposit
from apps.properties.models import Owner, Property, RentalContract, Tenant, Unit


@override_settings(DEBUG=True)
class SeedMockDataLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_mock_data', verbosity=0)

    def test_each_payment_has_one_canonical_ledger_transaction(self):
        payments = Payment.objects.filter(payment_reference__startswith='DEMO-PAY-')
        self.assertEqual(payments.count(), 32)
        for payment in payments:
            transactions = FinancialTransaction.objects.filter(
                transaction_reference=f'PAY-{payment.pk}',
                transaction_type=FinancialTransaction.TransactionType.RENT_INCOME,
                related_entity_type='payment',
                related_entity_id=payment.pk,
            )
            self.assertEqual(transactions.count(), 1)
        self.assertFalse(
            FinancialTransaction.objects.filter(transaction_reference__startswith='DEMO-PAY-').exists()
        )

    def test_each_expense_has_one_canonical_ledger_transaction(self):
        expenses = Expense.objects.filter(
            expense_reference__startswith='DEMO-EXP-'
        ).exclude(status=Expense.ExpenseStatus.CANCELLED)
        self.assertEqual(expenses.count(), 4)
        for expense in expenses:
            transactions = FinancialTransaction.objects.filter(
                transaction_reference=f'EXP-{expense.pk}',
                transaction_type=FinancialTransaction.TransactionType.EXPENSE,
                related_entity_type='expense',
                related_entity_id=expense.pk,
            )
            self.assertEqual(transactions.count(), 1)
        self.assertFalse(
            FinancialTransaction.objects.filter(transaction_reference__startswith='DEMO-EXP-').exists()
        )

    def test_each_received_deposit_has_one_canonical_ledger_transaction(self):
        deposits = SecurityDeposit.objects.filter(
            contract__contract_reference__startswith='DEMO-LEASE-',
            received_amount__gt=0,
            received_date__isnull=False,
        )
        self.assertEqual(deposits.count(), 12)
        for deposit in deposits:
            transactions = FinancialTransaction.objects.filter(
                transaction_reference=f'DEP-{deposit.pk}',
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT,
                related_entity_type='security_deposit',
                related_entity_id=deposit.pk,
            )
            self.assertEqual(transactions.count(), 1)
        self.assertFalse(
            FinancialTransaction.objects.filter(transaction_reference__startswith='DEMO-DEP-').exists()
        )

    def test_seeded_source_and_ledger_totals_match(self):
        payment_total = Payment.objects.filter(
            payment_reference__startswith='DEMO-PAY-'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expense_total = Expense.objects.filter(
            expense_reference__startswith='DEMO-EXP-'
        ).exclude(status=Expense.ExpenseStatus.CANCELLED).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        deposit_total = SecurityDeposit.objects.filter(
            contract__contract_reference__startswith='DEMO-LEASE-',
            received_amount__gt=0,
            received_date__isnull=False,
        ).aggregate(total=Sum('received_amount'))['total'] or Decimal('0.00')

        self.assertEqual(
            payment_total,
            FinancialTransaction.objects.filter(
                transaction_type=FinancialTransaction.TransactionType.RENT_INCOME
            ).aggregate(total=Sum('amount'))['total'],
        )
        self.assertEqual(
            expense_total,
            FinancialTransaction.objects.filter(
                transaction_type=FinancialTransaction.TransactionType.EXPENSE
            ).aggregate(total=Sum('amount'))['total'],
        )
        self.assertEqual(
            deposit_total,
            FinancialTransaction.objects.filter(
                transaction_type=FinancialTransaction.TransactionType.DEPOSIT
            ).aggregate(total=Sum('amount'))['total'],
        )

    def test_second_run_preserves_sources_canonical_ledger_and_totals(self):
        models = (
            Owner, Property, Unit, Tenant, RentalContract, RentSchedule,
            Invoice, Payment, Receipt, SecurityDeposit, MaintenanceRequest,
            Expense, FinancialTransaction,
        )
        counts_before = {model: model.objects.count() for model in models}
        totals_before = list(
            FinancialTransaction.objects.values('transaction_type')
            .annotate(total=Sum('amount')).order_by('transaction_type')
        )

        call_command('seed_mock_data', verbosity=0)

        self.assertEqual(
            {model: model.objects.count() for model in models}, counts_before
        )
        self.assertEqual(
            list(
                FinancialTransaction.objects.values('transaction_type')
                .annotate(total=Sum('amount')).order_by('transaction_type')
            ),
            totals_before,
        )
