from django import forms

from .models import (
    Owner,
    Property,
    Unit,
    Tenant,
    RentalContract,
)


class OwnerForm(forms.ModelForm):

    class Meta:
        model = Owner
        fields = "__all__"


class PropertyForm(forms.ModelForm):

    class Meta:
        model = Property
        fields = "__all__"


class UnitForm(forms.ModelForm):

    class Meta:
        model = Unit
        fields = "__all__"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Occupied is calculated automatically from active contracts.
        # Users only manage whether a unit is usable or under maintenance.
        self.fields["status"].choices = [
            (Unit.Status.VACANT, "Vacant"),
            (Unit.Status.MAINTENANCE, "Under Maintenance"),
        ]


class TenantForm(forms.ModelForm):

    class Meta:
        model = Tenant
        fields = "__all__"


class RentalContractForm(forms.ModelForm):

    class Meta:
        model = RentalContract
        fields = "__all__"

        widgets = {

            "start_date": forms.DateInput(
                attrs={
                    "type": "date"
                }
            ),

            "end_date": forms.DateInput(
                attrs={
                    "type": "date"
                }
            ),
        }