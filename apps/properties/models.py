"""
Owner: Omar — Property & Rental Management.
Models: Owner, Property, Unit, Tenant, RentalContract.
"""
from django.db import models
from apps.core.models import TimeStampedModel


class Owner(TimeStampedModel):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='active')

    def __str__(self):
        return self.full_name


class Property(TimeStampedModel):
    class PropertyType(models.TextChoices):
        RESIDENTIAL = 'residential', 'Residential'
        COMMERCIAL = 'commercial', 'Commercial'
        MIXED_USE = 'mixed_use', 'Mixed Use'

    owner = models.ForeignKey(Owner, on_delete=models.PROTECT, related_name='properties')
    name = models.CharField(max_length=150)
    address = models.TextField()
    property_type = models.CharField(max_length=20, choices=PropertyType.choices)
    status = models.CharField(max_length=20, default='active')
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Unit(TimeStampedModel):
    class Status(models.TextChoices):
        VACANT = 'vacant', 'Vacant'
        OCCUPIED = 'occupied', 'Occupied'
        MAINTENANCE = 'maintenance', 'Under Maintenance'

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=30)
    unit_type = models.CharField(max_length=50, blank=True)
    size_details = models.CharField(max_length=100, blank=True)
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.VACANT)

    class Meta:
        unique_together = ('property', 'unit_number')

    def __str__(self):
        return f"{self.property.name} — Unit {self.unit_number}"


class Tenant(TimeStampedModel):
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    identification_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, default='active')

    def __str__(self):
        return self.full_name


class RentalContract(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        TERMINATED = 'terminated', 'Terminated'

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='contracts')
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='contracts')
    contract_reference = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=12, decimal_places=2)
    payment_due_rule = models.CharField(max_length=100, blank=True, help_text="e.g. 'due on the 1st of each month'")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    def clean(self):
        """Business rule (Omar): no two active contracts may overlap for the same unit."""
        from django.core.exceptions import ValidationError
        if self.status == self.Status.ACTIVE:
            overlapping = RentalContract.objects.filter(
                unit=self.unit, status=self.Status.ACTIVE,
                start_date__lte=self.end_date, end_date__gte=self.start_date,
            ).exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("This unit already has an overlapping active contract.")

    def __str__(self):
        return self.contract_reference
