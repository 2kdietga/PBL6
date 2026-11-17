from django.core.exceptions import ValidationError
from django.db import models, transaction

from vehicles.models import DriverVehicleAssignment


class DrivingSession(models.Model):
    shift = models.ForeignKey('DrivingShift', null=True, blank=True, on_delete=models.PROTECT,
                              related_name='sessions', editable=False)
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
        if self.shift_id and self.shift.assignment_id != self.assignment_id:
            raise ValidationError('Ca lái phải thuộc cùng phân công với phiên lái.')
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
                if old.shift_id != self.shift_id:
                    raise ValidationError('Không được đổi ca của phiên lái đã tạo.')
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


class DrivingShift(models.Model):
    class Decision(models.TextChoices):
        ON_TIME = 'ON_TIME', 'Đúng giờ'
        LATE = 'LATE', 'Đi muộn'
        ABSENT = 'ABSENT', 'Vắng không phép'
        EXCUSED = 'EXCUSED', 'Được miễn đánh giá'

    assignment = models.ForeignKey(DriverVehicleAssignment, on_delete=models.PROTECT, related_name='shifts')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    early_minutes = models.PositiveSmallIntegerField(default=15)
    grace_minutes = models.PositiveSmallIntegerField(default=5)
    note = models.TextField(blank=True)
    cancelled = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    explanation = models.TextField(blank=True)
    explained_at = models.DateTimeField(null=True, blank=True)
    decision = models.CharField(max_length=10, choices=Decision.choices, blank=True)
    admin_response = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_at', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(end_at__gt=models.F('start_at')), name='shift_end_after_start')]

    def clean(self):
        super().clean()
        if not self.start_at or not self.end_at or not self.assignment_id:
            return
        if self.end_at <= self.start_at:
            raise ValidationError('Giờ kết thúc phải sau giờ bắt đầu.')
        if self.early_minutes > 120 or self.grace_minutes > 60:
            raise ValidationError('Cho phép sớm tối đa 120 phút, trễ tối đa 60 phút.')
        if self.cancelled:
            return
        assignment = self.assignment
        if self.start_at < assignment.start_at or (assignment.end_at and self.end_at > assignment.end_at):
            raise ValidationError('Ca phải nằm trong thời gian phân công xe.')
        conflicts = type(self).objects.filter(cancelled=False, start_at__lt=self.end_at, end_at__gt=self.start_at).exclude(pk=self.pk)
        if conflicts.filter(models.Q(assignment__driver_id=assignment.driver_id) | models.Q(assignment__vehicle_id=assignment.vehicle_id)).exists():
            raise ValidationError('Tài xế hoặc xe đã có ca trùng thời gian.')

    def __str__(self):
        return f'Ca #{self.pk} · {self.assignment}'


class ShiftAudit(models.Model):
    shift = models.ForeignKey(DrivingShift, on_delete=models.PROTECT, related_name='audits')
    actor = models.ForeignKey('accounts.User', null=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150)
    action = models.CharField(max_length=30)
    reason = models.TextField(blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
