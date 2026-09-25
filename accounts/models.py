from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        USER = "USER", "User"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER,
    )

    def __str__(self):
        return self.username

class DriverProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        INCOMPLETE = "INCOMPLETE", "Incomplete"
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="driver_profile",
    )

    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()

    phone = models.CharField(max_length=20)
    address = models.TextField()

    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.INCOMPLETE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name

    @property
    def missing_requirements(self):
        missing = []
        if not all((self.full_name.strip(), self.date_of_birth, self.phone.strip(), self.address.strip())):
            missing.append('thông tin cá nhân')
        license = DriverLicense.objects.filter(driver_id=self.pk).first() if self.pk else None
        face = FaceProfile.objects.filter(driver_id=self.pk).first() if self.pk else None
        if not license or not all((license.license_number, license.license_class, license.front_image_url, license.back_image_url)):
            missing.append('GPLX và ảnh hai mặt')
        if not face or not face.face_image_url or not face.embedding:
            missing.append('ảnh và dữ liệu khuôn mặt')
        return missing

    @property
    def can_approve(self):
        if self.missing_requirements:
            return False
        license = DriverLicense.objects.get(driver_id=self.pk)
        face = FaceProfile.objects.get(driver_id=self.pk)
        return license.is_valid and license.issued_date <= timezone.localdate() and face.approval_status == 'APPROVED'

    def save(self, *args, **kwargs):
        if self.missing_requirements:
            pending = self.pk and (
                DriverLicense.objects.filter(driver_id=self.pk, status='PENDING').exists()
                or FaceProfile.objects.filter(driver_id=self.pk, approval_status='PENDING').exists()
            )
            self.approval_status = self.ApprovalStatus.PENDING if pending else self.ApprovalStatus.INCOMPLETE
        elif self.approval_status == 'INCOMPLETE' or (self.approval_status == 'APPROVED' and not self.can_approve):
            self.approval_status = self.ApprovalStatus.PENDING
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'approval_status', 'updated_at'}
        super().save(*args, **kwargs)
    
class DriverLicense(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        REJECTED = "REJECTED", "Rejected"

    driver = models.OneToOneField(
        DriverProfile,
        on_delete=models.PROTECT,
        related_name="driver_license",
    )

    license_number = models.CharField(max_length=50, unique=True)
    license_class = models.CharField(max_length=20)

    issued_date = models.DateField()
    expiry_date = models.DateField()

    front_image_url = models.URLField()
    front_image_public_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    back_image_url = models.URLField()
    back_image_public_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.license_number} - {self.license_class}"

    @property
    def is_expired(self):
        return self.expiry_date <= timezone.localdate()

    @property
    def is_valid(self):
        return self.status == self.Status.ACTIVE and not self.is_expired

    @property
    def effective_status(self):
        if self.status == self.Status.ACTIVE and self.is_expired:
            return self.Status.EXPIRED
        return self.status

    def get_effective_status_display(self):
        return self.Status(self.effective_status).label

class FaceProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    driver = models.OneToOneField(
        DriverProfile,
        on_delete=models.PROTECT,
        related_name="face_profile",
    )

    face_image_url = models.URLField()
    cloudinary_public_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    embedding = models.JSONField()

    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FaceProfile - {self.driver.full_name}"
