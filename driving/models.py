from django.core.exceptions import ValidationError
from django.db import models, transaction

from vehicles.models import DriverVehicleAssignment


class DrivingSession(models.Model):
    # Historical rows remain unowned; do not guess their device from today's vehicle.
    source_device = models.ForeignKey('vehicles.Device', null=True, blank=True,
                                     on_delete=models.PROTECT, related_name='driving_sessions', editable=False)
    class Status(models.TextChoices):
        STARTED = "STARTED", "Started"
        ENDED = "ENDED", "Ended"

    assignment = models.ForeignKey(
        DriverVehicleAssignment,
        on_delete=models.PROTECT,
        related_name="driving_sessions",
    )
    # Stored to enforce one active session per vehicle across different assignments.
    vehicle = models.ForeignKey('vehicles.Vehicle', on_delete=models.PROTECT,
                                related_name='driving_sessions', editable=False)

    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.STARTED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(status='STARTED', ended_at__isnull=True)
                           | models.Q(status='ENDED', ended_at__isnull=False, ended_at__gte=models.F('started_at'))),
                name='session_consistent_times_status'),
            models.UniqueConstraint(fields=['vehicle'], condition=models.Q(status='STARTED'),
                                    name='one_started_session_per_vehicle'),
        ]

    def clean(self):
        super().clean()
        if self.assignment_id and self.vehicle_id != self.assignment.vehicle_id:
            raise ValidationError('Xe của phiên lái phải khớp với phân công.')
        if not self.pk and self.source_device_id and self.source_device.vehicle_id != self.vehicle_id:
            raise ValidationError('Thiết bị phải thuộc xe của phiên lái.')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            assignment = DriverVehicleAssignment.objects.select_for_update().get(pk=self.assignment_id)
            self.vehicle_id = assignment.vehicle_id
            if self.pk:
                old = type(self).objects.select_for_update().get(pk=self.pk)
                if old.assignment_id != self.assignment_id or old.vehicle_id != self.vehicle_id:
                    raise ValidationError('Không được đổi phân công hoặc xe của phiên lái đã tạo.')
                if old.source_device_id != self.source_device_id:
                    raise ValidationError('Không được đổi thiết bị nguồn của phiên lái.')
                if old.status == self.Status.ENDED and any(
                    getattr(old, field) != getattr(self, field)
                    for field in ('started_at', 'ended_at', 'status')
                ):
                    raise ValidationError('Không được thay đổi phiên lái đã kết thúc.')
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.assignment.driver.full_name} - "
            f"{self.assignment.vehicle.license_plate}"
        )
