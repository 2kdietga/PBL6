from django.db import models

from vehicles.models import DriverVehicleAssignment


class DrivingSession(models.Model):
    class Status(models.TextChoices):
        STARTED = "STARTED", "Started"
        ENDED = "ENDED", "Ended"

    assignment = models.ForeignKey(
        DriverVehicleAssignment,
        on_delete=models.PROTECT,
        related_name="driving_sessions",
    )

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.STARTED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.assignment.driver.full_name} - "
            f"{self.assignment.vehicle.license_plate}"
        )