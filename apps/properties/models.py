from builtins import property as python_property

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


# =========================================================
# OWNER
# =========================================================

class Owner(TimeStampedModel):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    full_name = models.CharField(
        max_length=255
    )

    phone = models.CharField(
        max_length=50,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    address = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    def __str__(self):
        return self.full_name


# =========================================================
# PROPERTY
# =========================================================

class Property(TimeStampedModel):

    class PropertyType(models.TextChoices):
        RESIDENTIAL = "residential", "Residential"
        COMMERCIAL = "commercial", "Commercial"
        MIXED_USE = "mixed_use", "Mixed Use"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    owner = models.ForeignKey(
        Owner,
        on_delete=models.PROTECT,
        related_name="properties"
    )

    name = models.CharField(
        max_length=255
    )

    address = models.TextField()

    property_type = models.CharField(
        max_length=30,
        choices=PropertyType.choices
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    description = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.name


# =========================================================
# UNIT
# =========================================================

class Unit(TimeStampedModel):

    class Status(models.TextChoices):
        VACANT = "vacant", "Vacant"
        OCCUPIED = "occupied", "Occupied"
        MAINTENANCE = "maintenance", "Under Maintenance"

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="units"
    )

    unit_number = models.CharField(
        max_length=50
    )

    unit_type = models.CharField(
        max_length=100,
        blank=True
    )

    size_details = models.CharField(
        max_length=255,
        blank=True
    )

    rent_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.VACANT
    )

    class Meta:
        unique_together = (
            "property",
            "unit_number",
        )

    def __str__(self):
        return f"{self.property.name} - Unit {self.unit_number}"

    def is_available_between(self, start_date, end_date):

        overlapping_contracts = self.contracts.filter(
            status=RentalContract.Status.ACTIVE,
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        return not overlapping_contracts.exists()

    @python_property
    def is_currently_occupied(self):

        today = timezone.localdate()

        return self.contracts.filter(
            status=RentalContract.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        ).exists()


# =========================================================
# TENANT
# =========================================================

class Tenant(TimeStampedModel):

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    full_name = models.CharField(
        max_length=255
    )

    phone = models.CharField(
        max_length=50,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    identification_number = models.CharField(
        max_length=100,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    def __str__(self):
        return self.full_name


# =========================================================
# RENTAL CONTRACT
# =========================================================

class RentalContract(TimeStampedModel):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        TERMINATED = "terminated", "Terminated"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        related_name="contracts"
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="contracts"
    )

    contract_reference = models.CharField(
        max_length=100,
        unique=True
    )

    start_date = models.DateField()

    end_date = models.DateField()

    monthly_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    payment_due_rule = models.CharField(
        max_length=255,
        blank=True,
        help_text="Example: due on the 1st of each month"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    def __str__(self):
        return self.contract_reference

    def clean(self):

        # End date must be after start date
        if self.start_date and self.end_date:

            if self.end_date <= self.start_date:

                raise ValidationError({
                    "end_date":
                        "End date must be after the start date."
                })

        # Prevent overlapping active contracts
        if (
            self.unit_id
            and self.start_date
            and self.end_date
            and self.status == self.Status.ACTIVE
        ):

            overlapping = RentalContract.objects.filter(
                unit=self.unit,
                status=self.Status.ACTIVE,
                start_date__lte=self.end_date,
                end_date__gte=self.start_date,
            ).exclude(
                pk=self.pk
            )

            if overlapping.exists():

                raise ValidationError(
                    "This unit already has an overlapping active contract."
                )