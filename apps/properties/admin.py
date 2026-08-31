from django.contrib import admin
from .models import Owner, Property, Unit, Tenant, RentalContract

admin.site.register(Owner)
admin.site.register(Property)
admin.site.register(Unit)
admin.site.register(Tenant)
admin.site.register(RentalContract)
