from django.db import models

class Vehicle(models.Model):
    name = models.CharField(max_length=100)
    license_plate = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=17, unique=True)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField()
    is_disabled = models.BooleanField(default=False)

    def __str__(self):
        return self.name