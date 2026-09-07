from django.contrib import admin

from .models import Owner, Property, Unit, Tenant, RentalContract


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "phone",
        "status",
        "created_at",
    )

    search_fields = (
        "full_name",
        "email",
        "phone",
    )

    list_filter = (
        "status",
    )


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "property_type",
        "status",
        "created_at",
    )

    list_filter = (
        "property_type",
        "status",
    )

    search_fields = (
        "name",
        "owner__full_name",
        "address",
    )


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = (
        "unit_number",
        "property",
        "unit_type",
        "rent_amount",
        "status",
    )

    list_filter = (
        "status",
        "property",
    )

    search_fields = (
        "unit_number",
        "unit_type",
        "property__name",
    )


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "phone",
        "identification_number",
        "status",
        "created_at",
    )

    search_fields = (
        "full_name",
        "email",
        "phone",
        "identification_number",
    )

    list_filter = (
        "status",
    )


@admin.register(RentalContract)
class RentalContractAdmin(admin.ModelAdmin):
    list_display = (
        "contract_reference",
        "tenant",
        "unit",
        "start_date",
        "end_date",
        "monthly_rent",
        "status",
    )

    list_filter = (
        "status",
        "start_date",
        "end_date",
    )

    search_fields = (
        "contract_reference",
        "tenant__full_name",
        "unit__unit_number",
        "unit__property__name",
    )