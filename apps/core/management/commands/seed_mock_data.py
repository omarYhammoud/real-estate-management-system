"""Create a small, linked demo portfolio without modifying existing records."""
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.properties.models import Owner, Property, Unit, Tenant, RentalContract
from apps.billing.models import RentSchedule, Invoice, InvoiceLineItem, Payment, Receipt
from apps.operations.models import SecurityDeposit, MaintenanceRequest, Expense
from apps.finance.models import FinancialTransaction


class Command(BaseCommand):
    help = "Add fictional demo data to the local development database (safe to rerun)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Validate data, then roll back all inserts.')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Mock data is only available with DEBUG=True.')
        self.created = Counter()
        today = timezone.localdate()
        anchor = RentalContract.objects.filter(contract_reference='DEMO-LEASE-11').first()
        if anchor:
            today = anchor.start_date + timedelta(days=180)
        with transaction.atomic():
            for p, (name, kind) in enumerate([
                ('Cedar Heights', 'residential'), ('Harbor Offices', 'commercial'),
                ('Garden Court', 'residential'), ('Maple Plaza', 'mixed_use'),
            ], 1):
                owner = self.add(Owner, {'email': f'owner{p}@rms-demo.example'},
                    full_name=f'Demo Owner {p}', address=f'{p} Example Avenue')
                self.link_owner_login(owner, p)
                prop = self.add(Property, {'name': f'[DEMO] {name}', 'owner': owner},
                    address=f'{p * 10} Example Avenue, Demo City', property_type=kind,
                    description='Fictional property created by seed_mock_data.')
                for u in range(1, 7):
                    rent = Decimal(500 + p * 150 + u * 75)
                    unit = self.add(Unit, {'property': prop, 'unit_number': str(100 + u)},
                        unit_type='Office' if kind == 'commercial' else 'Apartment',
                        size_details=f'{65 + u * 15} square metres', rent_amount=rent,
                        status='occupied' if u <= 3 else 'maintenance' if u == 6 else 'vacant')
                    if u > 4:
                        continue
                    tenant = self.add(Tenant, {'email': f'tenant{p}{u}@rms-demo.example'},
                        full_name=f'Demo {("Alex Morgan", "Sam Taylor", "Jamie Reed", "Casey Lane")[u-1]} {p}',
                        identification_number=f'DEMO-ID-{p}{u}',
                        status='inactive' if u == 4 else 'active')
                    start = today - timedelta(days=180 if u < 4 else 730)
                    end = today + timedelta(days=20 if u == 3 else 185) if u < 4 else today - timedelta(days=365)
                    contract = self.add(RentalContract, {'contract_reference': f'DEMO-LEASE-{p}{u}'},
                        tenant=tenant, unit=unit, start_date=start, end_date=end,
                        monthly_rent=rent, payment_due_rule='Due on the first of each month',
                        status='active' if u < 4 else 'expired')
                    if u == 4:
                        continue
                    deposit = self.add(SecurityDeposit, {'contract': contract},
                        required_amount=rent, received_amount=rent, received_date=start,
                        remaining_balance=rent, status='held')
                    self.ledger(f'DEMO-DEP-{p}{u}', 'deposit', rent, start, 'security_deposit', deposit.pk)
                    for period in range(3):
                        due = today - timedelta(days=65 - period * 30)
                        schedule = self.add(RentSchedule, {'contract': contract,
                            'billing_period_start': due, 'billing_period_end': due + timedelta(days=29)},
                            due_date=due, expected_amount=rent, status='invoiced')
                        invoice = self.add(Invoice, {'invoice_reference': f'DEMO-INV-{p}{u}-{period}'},
                            contract=contract, tenant=tenant, schedule=schedule,
                            billing_period=f'{due:%Y-%m-%d} to {due + timedelta(days=29):%Y-%m-%d}',
                            issue_date=due - timedelta(days=5), due_date=due)
                        self.add(InvoiceLineItem, {'invoice': invoice, 'description': 'Demo monthly rent'},
                            quantity=Decimal('1.00'), unit_amount=rent,
                            taxable_amount=rent, tax_amount=Decimal('0.00'), line_total=rent)
                        invoice.refresh_from_db()
                        paid = rent if period < 2 or u == 1 else rent / 2 if u == 2 else Decimal('0')
                        if paid:
                            payment = self.add(Payment, {'payment_reference': f'DEMO-PAY-{p}{u}-{period}'},
                                invoice=invoice, tenant=tenant, payment_date=due,
                                amount=paid, payment_method='bank_transfer')
                            self.add(Receipt, {'receipt_reference': f'DEMO-RCT-{p}{u}-{period}'},
                                payment=payment, receipt_date=due, amount=paid)
                            self.ledger(payment.payment_reference, 'rent_income', paid, due, 'payment', payment.pk)
                    self.add(MaintenanceRequest, {'property': prop, 'unit': unit,
                        'issue': '[DEMO] ' + ('Leaking kitchen tap', 'Air conditioner service', 'Replace hallway light')[u-1]},
                        tenant=tenant, priority=('high', 'medium', 'low')[u-1],
                        status=('open', 'in_progress', 'completed')[u-1],
                        request_date=today - timedelta(days=u * 2),
                        cost=Decimal('75.00') if u == 3 else None)
                expense = self.add(Expense, {'expense_reference': f'DEMO-EXP-{p}'},
                    property=prop, category='cleaning', amount=Decimal('150.00'),
                    expense_date=today - timedelta(days=7), description='Demo common-area cleaning', status='paid')
                self.ledger(f'DEMO-EXP-{p}', 'expense', expense.amount, expense.expense_date, 'expense', expense.pk)
            if options['dry_run']:
                transaction.set_rollback(True)
        prefix = 'Dry run: would create' if options['dry_run'] else 'Created'
        self.stdout.write(self.style.SUCCESS(f'{prefix} {sum(self.created.values())} records.'))
        for model, count in sorted(self.created.items()):
            self.stdout.write(f'  {model}: {count}')
        self.stdout.write('Existing records were preserved; unlinked demo owners received login accounts.')
        self.stdout.write('New demo logins: demo_owner1 through demo_owner4; password: DemoOwner2026!')
        self.stdout.write('Existing linked accounts and passwords are unchanged. Dry runs do not save accounts.')

    def link_owner_login(self, owner, number):
        if owner.user_id:
            return
        User = get_user_model()
        username = f'demo_owner{number}'
        if User.objects.filter(username=username).exists():
            raise CommandError(
                f'Cannot link {owner.email}: username {username} already exists. '
                'No changes were saved. Review and link the correct account manually.'
            )
        user = User(username=username, email=owner.email, first_name='Demo',
                    last_name=f'Owner {number}', role=User.Role.OWNER,
                    is_active=True, is_staff=False, is_superuser=False)
        user.set_password('DemoOwner2026!')
        user.full_clean()
        user.save()
        owner.user = user
        owner.full_clean()
        owner.save(update_fields=['user', 'updated_at'])
        self.created[User.__name__] += 1

    def add(self, model, lookup, **defaults):
        obj = model.objects.filter(**lookup).first()
        if obj is not None:
            return obj
        obj = model(**lookup, **defaults)
        # This nullable ledger field is required by forms, but no demo login is needed.
        obj.full_clean(exclude=['recorded_by'] if model is FinancialTransaction else None)
        obj.save()
        self.created[model.__name__] += 1
        return obj

    def ledger(self, reference, kind, amount, date, entity, entity_id):
        return self.add(FinancialTransaction, {'transaction_reference': reference},
            transaction_type=kind, amount=amount, transaction_date=date,
            related_entity_type=entity, related_entity_id=entity_id)
