from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.billing.models import Payment
from apps.operations.models import DepositRefund, Expense, SecurityDeposit

from .models import FinancialTransaction


def sync_transaction(*, reference, defaults, using):
    FinancialTransaction.objects.using(using).update_or_create(
        transaction_reference=reference,
        defaults=defaults,
    )


def delete_generated_transaction(*, reference, entity_type, entity_id, using):
    FinancialTransaction.objects.using(using).filter(
        transaction_reference=reference,
        related_entity_type=entity_type,
        related_entity_id=entity_id,
    ).delete()


def persisted_source(sender, instance, using):
    return sender._default_manager.using(using).get(pk=instance.pk)


@receiver(post_save, sender=Payment, dispatch_uid='finance.sync_payment')
def sync_payment(sender, instance, using, **kwargs):
    payment = persisted_source(sender, instance, using)
    sync_transaction(
        reference=f'PAY-{payment.pk}',
        defaults={
            'transaction_type': FinancialTransaction.TransactionType.RENT_INCOME,
            'amount': payment.amount,
            'transaction_date': payment.payment_date,
            'recorded_by_id': payment.recorded_by_id,
            'related_entity_type': 'payment',
            'related_entity_id': payment.pk,
        },
        using=using,
    )


@receiver(post_save, sender=Expense, dispatch_uid='finance.sync_expense')
def sync_expense(sender, instance, using, **kwargs):
    expense = persisted_source(sender, instance, using)
    reference = f'EXP-{expense.pk}'
    if expense.status == Expense.ExpenseStatus.CANCELLED:
        delete_generated_transaction(
            reference=reference,
            entity_type='expense',
            entity_id=expense.pk,
            using=using,
        )
        return

    sync_transaction(
        reference=reference,
        defaults={
            'transaction_type': FinancialTransaction.TransactionType.EXPENSE,
            'amount': expense.amount,
            'transaction_date': expense.expense_date,
            'recorded_by_id': expense.recorded_by_id,
            'related_entity_type': 'expense',
            'related_entity_id': expense.pk,
        },
        using=using,
    )


@receiver(
    post_save,
    sender=SecurityDeposit,
    dispatch_uid='finance.sync_security_deposit',
)
def sync_security_deposit(sender, instance, using, **kwargs):
    deposit = persisted_source(sender, instance, using)
    reference = f'DEP-{deposit.pk}'
    if deposit.received_amount <= 0 or deposit.received_date is None:
        FinancialTransaction.objects.using(using).filter(
            transaction_reference=reference,
        ).delete()
        return

    sync_transaction(
        reference=reference,
        defaults={
            'transaction_type': FinancialTransaction.TransactionType.DEPOSIT,
            'amount': deposit.received_amount,
            'transaction_date': deposit.received_date,
            'recorded_by': None,
            'related_entity_type': 'security_deposit',
            'related_entity_id': deposit.pk,
        },
        using=using,
    )


@receiver(post_save, sender=DepositRefund, dispatch_uid='finance.sync_deposit_refund')
def sync_deposit_refund(sender, instance, using, **kwargs):
    refund = persisted_source(sender, instance, using)
    sync_transaction(
        reference=f'REF-{refund.pk}',
        defaults={
            'transaction_type': FinancialTransaction.TransactionType.DEPOSIT_REFUND,
            'amount': refund.amount,
            'transaction_date': refund.refund_date,
            'recorded_by_id': refund.authorized_by_id,
            'related_entity_type': 'deposit_refund',
            'related_entity_id': refund.pk,
        },
        using=using,
    )


@receiver(post_delete, sender=Payment, dispatch_uid='finance.delete_payment_transaction')
def delete_payment_transaction(sender, instance, using, **kwargs):
    delete_generated_transaction(
        reference=f'PAY-{instance.pk}',
        entity_type='payment',
        entity_id=instance.pk,
        using=using,
    )


@receiver(post_delete, sender=Expense, dispatch_uid='finance.delete_expense_transaction')
def delete_expense_transaction(sender, instance, using, **kwargs):
    delete_generated_transaction(
        reference=f'EXP-{instance.pk}',
        entity_type='expense',
        entity_id=instance.pk,
        using=using,
    )


@receiver(
    post_delete,
    sender=SecurityDeposit,
    dispatch_uid='finance.delete_security_deposit_transaction',
)
def delete_security_deposit_transaction(sender, instance, using, **kwargs):
    delete_generated_transaction(
        reference=f'DEP-{instance.pk}',
        entity_type='security_deposit',
        entity_id=instance.pk,
        using=using,
    )


@receiver(
    post_delete,
    sender=DepositRefund,
    dispatch_uid='finance.delete_deposit_refund_transaction',
)
def delete_deposit_refund_transaction(sender, instance, using, **kwargs):
    delete_generated_transaction(
        reference=f'REF-{instance.pk}',
        entity_type='deposit_refund',
        entity_id=instance.pk,
        using=using,
    )
