from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.core.mixins import RoleRequiredMixin

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


User = get_user_model()


class PropertyManagementRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN, User.Role.PROPERTY_MANAGER)


def property_management_required(view_function):
    """Run an existing function view through the shared role mixin."""
    class ProtectedFunctionView(PropertyManagementRequiredMixin, View):
        def get(self, request, *args, **kwargs):
            return view_function(request, *args, **kwargs)

        def post(self, request, *args, **kwargs):
            return view_function(request, *args, **kwargs)

    return ProtectedFunctionView.as_view()


class TenantSelfServiceMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.TENANT,)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        try:
            self.tenant_profile = request.user.tenant_profile
        except User.tenant_profile.RelatedObjectDoesNotExist as exc:
            raise PermissionDenied('No tenant profile is linked to this account.') from exc
        return super().dispatch(request, *args, **kwargs)


class OwnerSelfServiceMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.OWNER,)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        try:
            self.owner_profile = request.user.owner_profile
        except User.owner_profile.RelatedObjectDoesNotExist as exc:
            raise PermissionDenied('No owner profile is linked to this account.') from exc
        return super().dispatch(request, *args, **kwargs)


class TenantProfileView(TenantSelfServiceMixin, TemplateView):
    template_name = 'properties/tenant_self_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.tenant_profile
        return context


class TenantContractListView(TenantSelfServiceMixin, ListView):
    template_name = 'properties/tenant_self_contracts.html'
    context_object_name = 'contracts'

    def get_queryset(self):
        return self.tenant_profile.contracts.select_related(
            'unit', 'unit__property'
        ).order_by('-start_date', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context['current_contract'] = self.get_queryset().filter(
            status=RentalContract.Status.ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        ).first()
        return context


class OwnerPropertyListView(OwnerSelfServiceMixin, ListView):
    template_name = 'properties/owner_self_property_list.html'
    context_object_name = 'properties'

    def get_queryset(self):
        return self.owner_profile.properties.annotate(
            unit_count=models.Count('units')
        ).order_by('name')


class OwnerPropertyDetailView(OwnerSelfServiceMixin, DetailView):
    template_name = 'properties/owner_self_property_detail.html'
    context_object_name = 'property'

    def get_queryset(self):
        return self.owner_profile.properties.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['units'] = self.object.units.order_by('unit_number')
        context['contracts'] = RentalContract.objects.filter(
            unit__property=self.object
        ).select_related('tenant', 'unit').order_by('-start_date')
        return context


# =========================
# OWNER VIEWS
# =========================

@property_management_required
def owner_list(request):
    owners = Owner.objects.all()

    return render(
        request,
        "properties/owner_list.html",
        {"owners": owners},
    )


@property_management_required
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


@property_management_required
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


@property_management_required
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

@property_management_required
def property_list(request):
    properties = Property.objects.select_related("owner").all()

    return render(
        request,
        "properties/property_list.html",
        {"properties": properties},
    )


@property_management_required
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


@property_management_required
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


@property_management_required
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

@property_management_required
def unit_list(request):
    units = Unit.objects.select_related("property").all()

    return render(
        request,
        "properties/unit_list.html",
        {"units": units},
    )


@property_management_required
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


@property_management_required
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


@property_management_required
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

@property_management_required
def tenant_list(request):
    tenants = Tenant.objects.all()

    return render(
        request,
        "properties/tenant_list.html",
        {"tenants": tenants},
    )

@property_management_required
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


@property_management_required
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


@property_management_required
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


@property_management_required
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

@property_management_required
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


@property_management_required
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


@property_management_required
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


@property_management_required
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


@property_management_required
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
