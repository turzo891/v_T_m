from django import forms
from .models import Vehicle

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = (
            'name', 'license_plate', 'vin', 'make', 'model', 'year', 
            'status', 'driver_name', 'driver_phone', 'driver_license', 'is_disabled'
        )
