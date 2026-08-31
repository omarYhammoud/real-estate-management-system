"""
Owner: Chaheen — Authentication, Finance & Reports.

This app owns the custom User model (settings.AUTH_USER_MODEL points here)
so every other app should reference the user with
`settings.AUTH_USER_MODEL` / get_user_model(), never import this class
directly, to avoid circular imports.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Extends Django's built-in auth user with the role this project's ERD
    calls for (see FinancialTransaction.recorded_by, Payment.recorded_by,
    DepositRefund/DepositDeduction.authorized_by, Expense.recorded_by, etc.
    — all of those FKs point here).
    """

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        PROPERTY_MANAGER = 'property_manager', 'Property Manager'
        ACCOUNTANT = 'accountant', 'Accountant'
        OWNER = 'owner', 'Owner'
        TENANT = 'tenant', 'Tenant'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TENANT)

    def __str__(self):
        return self.get_full_name() or self.username
