from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Driver(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, unique=True)
    license_number = models.CharField(max_length=64, unique=True)
    license_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.full_name


class Vehicle(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    callsign = models.CharField(max_length=50, unique=True)
    vin = models.CharField(max_length=32, unique=True)
    license_plate = models.CharField(max_length=20, unique=True)
    vehicle_type = models.CharField(max_length=64)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    year = models.PositiveIntegerField(null=True, blank=True)
    telematics_device_id = models.CharField(max_length=64, unique=True)
    last_known_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_known_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_reported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["callsign"]

    def __str__(self) -> str:
        return self.callsign


class VehicleAssignment(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="assignments"
    )
    driver = models.ForeignKey(
        Driver, on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle"],
                condition=Q(released_at__isnull=True),
                name="uniq_vehicle_active_assignment",
            ),
            models.UniqueConstraint(
                fields=["driver"],
                condition=Q(released_at__isnull=True),
                name="uniq_driver_active_assignment",
            ),
        ]

    @property
    def is_active(self) -> bool:
        return self.released_at is None

    def __str__(self) -> str:
        status = "active" if self.is_active else "ended"
        return f"{self.vehicle} → {self.driver} ({status})"


class Route(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    color_hex = models.CharField(max_length=7, default="#2563eb")
    encoded_polyline = models.TextField(blank=True)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    average_travel_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RouteLeg(models.Model):
    id = models.BigAutoField(primary_key=True)
    route = models.ForeignKey(
        Route, on_delete=models.CASCADE, related_name="legs"
    )
    sequence_no = models.PositiveIntegerField()
    origin_label = models.CharField(max_length=255)
    origin_lat = models.DecimalField(max_digits=9, decimal_places=6)
    origin_lng = models.DecimalField(max_digits=9, decimal_places=6)
    destination_label = models.CharField(max_length=255)
    destination_lat = models.DecimalField(max_digits=9, decimal_places=6)
    destination_lng = models.DecimalField(max_digits=9, decimal_places=6)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["route", "sequence_no"]
        unique_together = ("route", "sequence_no")

    def __str__(self) -> str:
        return f"{self.route} leg {self.sequence_no}"


class VehicleJourney(TimeStampedModel):
    class JourneyStatus(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="journeys"
    )
    driver_assignment = models.ForeignKey(
        VehicleAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="journeys",
    )
    route = models.ForeignKey(
        Route, on_delete=models.SET_NULL, null=True, blank=True, related_name="journeys"
    )
    status = models.CharField(
        max_length=32, choices=JourneyStatus.choices, default=JourneyStatus.PLANNED
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    estimated_arrival_at = models.DateTimeField(null=True, blank=True)
    distance_km = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    average_speed_kmh = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    max_speed_kmh = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["vehicle", "started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.vehicle} journey {self.id}"


class LocationPing(models.Model):
    id = models.BigAutoField(primary_key=True)
    journey = models.ForeignKey(
        VehicleJourney, on_delete=models.CASCADE, related_name="pings"
    )
    recorded_at = models.DateTimeField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kmh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    heading_deg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    satellite_count = models.PositiveIntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["recorded_at"]
        indexes = [
            models.Index(fields=["journey", "recorded_at"]),
            models.Index(fields=["recorded_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.journey_id} @ {self.recorded_at.isoformat()}"


class TrafficSnapshot(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=255)
    captured_at = models.DateTimeField(default=timezone.now)
    features = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["captured_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.source} @ {self.captured_at.isoformat()}"
