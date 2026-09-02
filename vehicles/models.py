from django.db import models


class VehicleType(models.Model):
    code = models.CharField(
        max_length=20,
        unique=True,
    )

    name = models.CharField(
        max_length=100,
    )

    description = models.TextField(
        blank=True,
    )

    def __str__(self):
        return self.name