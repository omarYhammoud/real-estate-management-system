from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    OwnerForm,
    PropertyForm,
    UnitForm,
    TenantForm,
    RentalContractForm,
)
from .models import (
    Owner,
    Property,
    Unit,
    Tenant,
    RentalContract,
)


# =========================
# OWNER VIEWS
# =========================

def owner_list(request):
    owners = Owner.objects.all()

    return render(
        request,
        "properties/owner_list.html",
        {"owners": owners},
    )


def owner_create(request):
    if request.method == "POST":
        form = OwnerForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Owner created successfully.")
            return redirect("properties:owner_list")
    else:
        form = OwnerForm()

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Add Owner",
        },
    )


def owner_update(request, pk):
    owner = get_object_or_404(Owner, pk=pk)

    if request.method == "POST":
        form = OwnerForm(request.POST, instance=owner)

        if form.is_valid():
            form.save()
            messages.success(request, "Owner updated successfully.")
            return redirect("properties:owner_list")
    else:
        form = OwnerForm(instance=owner)

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Edit Owner",
        },
    )


def owner_delete(request, pk):
    owner = get_object_or_404(Owner, pk=pk)

    if request.method == "POST":
        owner.delete()
        messages.success(request, "Owner deleted successfully.")
        return redirect("properties:owner_list")

    return render(
        request,
        "properties/confirm_delete.html",
        {
            "object": owner,
            "title": "Delete Owner",
        },
    )


# =========================
# PROPERTY VIEWS
# =========================

def property_list(request):
    properties = Property.objects.select_related("owner").all()

    return render(
        request,
        "properties/property_list.html",
        {"properties": properties},
    )


def property_create(request):
    if request.method == "POST":
        form = PropertyForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Property created successfully.")
            return redirect("properties:property_list")
    else:
        form = PropertyForm()

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Add Property",
        },
    )


def property_update(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)

    if request.method == "POST":
        form = PropertyForm(request.POST, instance=property_obj)

        if form.is_valid():
            form.save()
            messages.success(request, "Property updated successfully.")
            return redirect("properties:property_list")
    else:
        form = PropertyForm(instance=property_obj)

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Edit Property",
        },
    )


def property_delete(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)

    if request.method == "POST":
        property_obj.delete()
        messages.success(request, "Property deleted successfully.")
        return redirect("properties:property_list")

    return render(
        request,
        "properties/confirm_delete.html",
        {
            "object": property_obj,
            "title": "Delete Property",
        },
    )


# =========================
# UNIT VIEWS
# =========================

def unit_list(request):
    units = Unit.objects.select_related("property").all()

    return render(
        request,
        "properties/unit_list.html",
        {"units": units},
    )


def unit_create(request):
    if request.method == "POST":
        form = UnitForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Unit created successfully.")
            return redirect("properties:unit_list")
    else:
        form = UnitForm()

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Add Unit",
        },
    )


def unit_update(request, pk):
    unit = get_object_or_404(Unit, pk=pk)

    if request.method == "POST":
        form = UnitForm(request.POST, instance=unit)

        if form.is_valid():
            form.save()
            messages.success(request, "Unit updated successfully.")
            return redirect("properties:unit_list")
    else:
        form = UnitForm(instance=unit)

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Edit Unit",
        },
    )


def unit_delete(request, pk):
    unit = get_object_or_404(Unit, pk=pk)

    if request.method == "POST":
        unit.delete()
        messages.success(request, "Unit deleted successfully.")
        return redirect("properties:unit_list")

    return render(
        request,
        "properties/confirm_delete.html",
        {
            "object": unit,
            "title": "Delete Unit",
        },
    )


# =========================
# TENANT VIEWS
# =========================

def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)

    contracts = tenant.contracts.select_related(
        "unit",
        "unit__property",
    ).all()

    return render(
        request,
        "properties/tenant_detail.html",
        {
            "tenant": tenant,
            "contracts": contracts,
        },
    )

def tenant_list(request):
    tenants = Tenant.objects.all()

    return render(
        request,
        "properties/tenant_list.html",
        {"tenants": tenants},
    )

def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)

    contracts = tenant.contracts.select_related(
        "unit",
        "unit__property",
    ).all()

    return render(
        request,
        "properties/tenant_detail.html",
        {
            "tenant": tenant,
            "contracts": contracts,
        },
    )


def tenant_create(request):
    if request.method == "POST":
        form = TenantForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Tenant created successfully.")
            return redirect("properties:tenant_list")
    else:
        form = TenantForm()

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Add Tenant",
        },
    )


def tenant_update(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)

    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)

        if form.is_valid():
            form.save()
            messages.success(request, "Tenant updated successfully.")
            return redirect("properties:tenant_list")
    else:
        form = TenantForm(instance=tenant)

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Edit Tenant",
        },
    )


def tenant_delete(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)

    if request.method == "POST":
        tenant.delete()
        messages.success(request, "Tenant deleted successfully.")
        return redirect("properties:tenant_list")

    return render(
        request,
        "properties/confirm_delete.html",
        {
            "object": tenant,
            "title": "Delete Tenant",
        },
    )


# =========================
# RENTAL CONTRACT VIEWS
# =========================

def contract_list(request):
    contracts = RentalContract.objects.select_related(
        "tenant",
        "unit",
        "unit__property",
    ).all()

    return render(
        request,
        "properties/contract_list.html",
        {"contracts": contracts},
    )


def contract_detail(request, pk):
    contract = get_object_or_404(
        RentalContract.objects.select_related(
            "tenant",
            "unit",
            "unit__property",
        ),
        pk=pk,
    )

    return render(
        request,
        "properties/contract_detail.html",
        {"contract": contract},
    )


def contract_create(request):
    if request.method == "POST":
        form = RentalContractForm(request.POST)

        if form.is_valid():
            contract = form.save()

            messages.success(
                request,
                "Rental contract created successfully.",
            )

            return redirect(
                "properties:contract_detail",
                pk=contract.pk,
            )
    else:
        form = RentalContractForm()

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Create Rental Contract",
        },
    )


def contract_update(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)

    if request.method == "POST":
        form = RentalContractForm(
            request.POST,
            instance=contract,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Rental contract updated successfully.",
            )

            return redirect(
                "properties:contract_detail",
                pk=contract.pk,
            )
    else:
        form = RentalContractForm(instance=contract)

    return render(
        request,
        "properties/form.html",
        {
            "form": form,
            "title": "Edit Rental Contract",
        },
    )


def contract_delete(request, pk):
    contract = get_object_or_404(RentalContract, pk=pk)

    if request.method == "POST":
        contract.delete()

        messages.success(
            request,
            "Rental contract deleted successfully.",
        )

        return redirect("properties:contract_list")

    return render(
        request,
        "properties/confirm_delete.html",
        {
            "object": contract,
            "title": "Delete Rental Contract",
        },
    )