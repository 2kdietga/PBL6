from django.contrib.auth.models import AbstractUser
from django.db import models


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
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="driver_profile",
    )

    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()

    phone = models.CharField(max_length=20)
    address = models.TextField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name
    
class DriverLicense(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        REJECTED = "REJECTED", "Rejected"

    driver = models.OneToOneField(
        DriverProfile,
        on_delete=models.CASCADE,
        related_name="driver_license",
    )

    license_number = models.CharField(max_length=50, unique=True)
    license_class = models.CharField(max_length=20)

    issued_date = models.DateField()
    expiry_date = models.DateField()

    front_image_url = models.URLField()
    back_image_url = models.URLField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.license_number} - {self.license_class}"
