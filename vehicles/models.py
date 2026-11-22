from django.db import models, transaction
from django.core.exceptions import ValidationError
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
    gross_vehicle_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_sleeper = models.BooleanField(default=False)

    @property
    def required_license_class(self):
        from .licensing import required_license_class
        return required_license_class(self.vehicle_type.category, self.gross_vehicle_weight,
                                      self.passenger_capacity, self.is_sleeper)

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
    def clean(self):
        super().clean()
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.device_code != self.device_code and hasattr(old, 'ai_config'):
                raise ValidationError({'device_code': 'Thiết bị đã có cấu hình MQTT: không được đổi mã để tránh nhầm topic và phiên bản.'})
            if old and old.vehicle_id != self.vehicle_id and old.vehicle.driving_sessions.filter(status='STARTED').exists():
                raise ValidationError({'vehicle': 'Cần kết thúc phiên lái trước khi chuyển thiết bị sang xe khác.'})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                type(self).objects.select_for_update().filter(pk=self.pk).first()
                self.clean()
            super().save(*args, **kwargs)

    # Only hashes are stored; web/CLI provisioning reveals the secret once.
    api_key_hash = models.CharField(max_length=128, blank=True, default='', editable=False)
    # Indexed fingerprint of the random token for identification without a device code.
    api_key_digest = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)

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
    def clean(self):
        super().clean()
        if not self.driver_id or not self.vehicle_id or not self.start_at:
            return
        if self.end_at and self.end_at <= self.start_at:
            raise ValidationError({'end_at': 'Thời gian kết thúc phải sau thời gian bắt đầu.'})
        old = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        # Allow narrowing legacy overlaps so an administrator can resolve them.
        if old and (old.driver_id, old.vehicle_id, old.start_at) == (self.driver_id, self.vehicle_id, self.start_at):
            if self.end_at == old.end_at or (self.end_at and (old.end_at is None or self.end_at <= old.end_at)):
                return
        overlaps = type(self).objects.filter(driver_id=self.driver_id, vehicle_id=self.vehicle_id).exclude(pk=self.pk)
        overlaps = overlaps.filter(models.Q(end_at__isnull=True) | models.Q(end_at__gt=self.start_at))
        if self.end_at:
            overlaps = overlaps.filter(start_at__lt=self.end_at)
        if overlaps.exists():
            raise ValidationError('Tài xế và xe này đã có phân công chồng thời gian. Hãy chỉnh thời hạn phân công cũ trước.')

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

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                old = type(self).objects.select_for_update().get(pk=self.pk)
                if old.driving_sessions.exists() and any(
                    getattr(old, field) != getattr(self, field)
                    for field in ('driver_id', 'vehicle_id', 'start_at')
                ):
                    raise ValidationError('Phân công đã có phiên lái: không được đổi tài xế, xe hoặc thời gian bắt đầu.')
                if old.shifts.exists():
                    if any(getattr(old, field) != getattr(self, field) for field in ('driver_id', 'vehicle_id', 'start_at')):
                        raise ValidationError('Phân công đã có lịch ca: không được đổi tài xế, xe hoặc ngày bắt đầu.')
                    if self.end_at and old.shifts.filter(cancelled=False, end_at__gt=self.end_at).exists():
                        raise ValidationError('Còn ca nằm ngoài ngày kết thúc mới. Cần xử lý các ca trước khi kết thúc phân công.')
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.driver.full_name} - {self.vehicle.license_plate}"
