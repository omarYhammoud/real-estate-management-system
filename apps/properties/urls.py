from django.urls import path

from . import views


app_name = "properties"


urlpatterns = [
    # Owners
    path(
        "owners/",
        views.owner_list,
        name="owner_list",
    ),
    path(
        "owners/add/",
        views.owner_create,
        name="owner_create",
    ),
    path(
        "owners/<int:pk>/edit/",
        views.owner_update,
        name="owner_update",
    ),
    path(
        "owners/<int:pk>/delete/",
        views.owner_delete,
        name="owner_delete",
    ),

    # Properties
    path(
        "properties/",
        views.property_list,
        name="property_list",
    ),
    path(
        "properties/add/",
        views.property_create,
        name="property_create",
    ),
    path(
        "properties/<int:pk>/edit/",
        views.property_update,
        name="property_update",
    ),
    path(
        "properties/<int:pk>/delete/",
        views.property_delete,
        name="property_delete",
    ),

    # Units
    path(
        "units/",
        views.unit_list,
        name="unit_list",
    ),
    path(
        "units/add/",
        views.unit_create,
        name="unit_create",
    ),
    path(
        "units/<int:pk>/edit/",
        views.unit_update,
        name="unit_update",
    ),
    path(
        "units/<int:pk>/delete/",
        views.unit_delete,
        name="unit_delete",
    ),

    # Tenants

    path(
        "tenants/",
        views.tenant_list,
        name="tenant_list",
    ),

    path(
        "tenants/add/",
        views.tenant_create,
        name="tenant_create",
    ),

    path(
        "tenants/<int:pk>/",
        views.tenant_detail,
        name="tenant_detail",
    ),

    path(
        "tenants/<int:pk>/edit/",
        views.tenant_update,
        name="tenant_update",
    ),

    path(
        "tenants/<int:pk>/delete/",
        views.tenant_delete,
        name="tenant_delete",
    ),

    # Rental Contracts
    path(
        "contracts/",
        views.contract_list,
        name="contract_list",
    ),
    path(
        "contracts/add/",
        views.contract_create,
        name="contract_create",
    ),
    path(
        "contracts/<int:pk>/",
        views.contract_detail,
        name="contract_detail",
    ),
    path(
        "contracts/<int:pk>/edit/",
        views.contract_update,
        name="contract_update",
    ),
    path(
        "contracts/<int:pk>/delete/",
        views.contract_delete,
        name="contract_delete",
    ),
    
]   