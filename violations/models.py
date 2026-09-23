from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, URLValidator
from django.db import models
from django.db.models.functions import Lower
from django.conf import settings
from django.utils import timezone


class ViolationType(models.Model):
    code = models.CharField(max_length=50, unique=True, validators=[
        RegexValidator(r'^[A-Z0-9_]+$', 'Mã chỉ gồm chữ in hoa, số và dấu gạch dưới.'),
    ])
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [models.UniqueConstraint(Lower('code'), name='violation_type_code_ci_unique')]

    @staticmethod
    def normalize_code(value):
        return '_'.join(value.strip().upper().split())

    def save(self, *args, **kwargs):
        self.code = self.normalize_code(self.code)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} · {self.name}'


class Violation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Chờ xác nhận'
        APPROVED = 'APPROVED', 'Đã xác nhận'
        REJECTED = 'REJECTED', 'Đã từ chối'
        REVOKED = 'REVOKED', 'Đã thu hồi'

    class Severity(models.TextChoices):
        LOW = 'LOW', 'Thấp'
        MEDIUM = 'MEDIUM', 'Trung bình'
        HIGH = 'HIGH', 'Cao'

    session = models.ForeignKey('driving.DrivingSession', on_delete=models.PROTECT, related_name='violations')
    violation_type = models.ForeignKey(ViolationType, on_delete=models.PROTECT, related_name='violations')
    severity = models.CharField(max_length=10, choices=Severity.choices)
    detected_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-detected_at', '-pk']
        indexes = [models.Index(fields=['status', '-detected_at'], name='violation_status_detected_idx')]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['PENDING', 'APPROVED', 'REJECTED', 'REVOKED']), name='violation_valid_status'),
            models.CheckConstraint(condition=models.Q(severity__in=['LOW', 'MEDIUM', 'HIGH']), name='violation_valid_severity'),
        ]

    def __str__(self):
        return f'VP-{self.pk} · {self.violation_type}'


class Evidence(models.Model):
    class Type(models.TextChoices):
        IMAGE = 'IMAGE', 'Ảnh'
        VIDEO = 'VIDEO', 'Video'

    violation = models.ForeignKey(Violation, on_delete=models.CASCADE, related_name='evidences')
    type = models.CharField(max_length=5, choices=Type.choices)
    url = models.URLField(max_length=2000, validators=[URLValidator(schemes=['https'])])
    cloudinary_public_id = models.CharField(max_length=255, blank=True, default='')
    captured_at = models.DateTimeField()

    class Meta:
        ordering = ['captured_at', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(type__in=['IMAGE', 'VIDEO']), name='evidence_valid_type')]

    @property
    def safe_url(self):
        # Also protect rendering of records inserted without model validation.
        try:
            URLValidator(schemes=['https'])(self.url)
        except ValidationError:
            return ''
        return self.url

    def __str__(self):
        return f'{self.get_type_display()} · VP-{self.violation_id}'


class AppealQuerySet(models.QuerySet):
    def delete(self):
        count = self.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())
        return count, {self.model._meta.label: count}


class Appeal(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Chờ xử lý'
        APPROVED = 'APPROVED', 'Đã chấp nhận'
        REJECTED = 'REJECTED', 'Đã từ chối'

    violation = models.OneToOneField(Violation, on_delete=models.CASCADE, related_name='appeal')
    content = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    admin_response = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Keep archived rows in the manager and OneToOne constraint: deletion never
    # grants a second appeal. Cascade from a deleted violation still removes them.
    objects = AppealQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['PENDING', 'APPROVED', 'REJECTED']), name='appeal_valid_status')]

    def __str__(self):
        return f'Kháng cáo VP-{self.violation_id}'

    def delete(self, using=None, keep_parents=False):
        result = type(self).objects.using(using or self._state.db).filter(pk=self.pk).delete()
        self.refresh_from_db()
        return result


class ViolationReview(models.Model):
    class Action(models.TextChoices):
        APPROVE = 'approve', 'Xác nhận'
        REJECT = 'reject', 'Từ chối'
        REOPEN = 'reopen', 'Xem xét lại'

    violation = models.ForeignKey(Violation, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False)
    reviewer_name = models.CharField(max_length=150)
    action = models.CharField(max_length=10, choices=Action.choices)
    before = models.JSONField()
    after = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'VP-{self.violation_id} · {self.get_action_display()}'
