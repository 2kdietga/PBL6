from django.db import models
from accounts.models import DriverProfile

class VehicleType(models.Model):
    class Category(models.TextChoices):
        TRUCK = "TRUCK", "Truck"
        BUS = "BUS", "Bus"

    name = models.CharField(max_length=100)

    category = models.CharField(
        max_length=10,
        choices=Category.choices,
    )

    description = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name

class Vehicle(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        LIQUIDATED = "LIQUIDATED", "Liquidated"

    vehicle_type = models.ForeignKey(
        VehicleType,
        on_delete=models.PROTECT,
        related_name="vehicles",
    )

    license_plate = models.CharField(
        max_length=20,
        unique=True,
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
    )

    model = models.CharField(
        max_length=100,
        blank=True,
    )

    manufacture_year = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    load_capacity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    passenger_capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    description = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.license_plate


class Device(models.Model):
    class Status(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        OFFLINE = "OFFLINE", "Offline"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    vehicle = models.OneToOneField(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="device",
    )

    device_code = models.CharField(
        max_length=100,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.OFFLINE,
    )

    last_seen_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.device_code

class DriverVehicleAssignment(models.Model):
    driver = models.ForeignKey(
        DriverProfile,
        on_delete=models.PROTECT,
        related_name="vehicle_assignments",
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.PROTECT,
        related_name="driver_assignments",
    )

    start_at = models.DateTimeField()

    end_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.driver.full_name} - {self.vehicle.license_plate}"