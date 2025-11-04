from django.db import models

class Vehicle(models.Model):
    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('en_route', 'En Route'),
        ('maintenance', 'Maintenance'),
    ]
    name = models.CharField(max_length=100)
    license_plate = models.CharField(max_length=20, unique=True)
    vin = models.CharField(max_length=17, unique=True)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveIntegerField()
    is_disabled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)
    driver_name = models.CharField(max_length=100, blank=True, default='')
    driver_phone = models.CharField(max_length=20, blank=True, default='')
    driver_license = models.CharField(max_length=50, blank=True, default='')

    def __str__(self):
        return self.name