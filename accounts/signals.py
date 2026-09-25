from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import DriverProfile, DriverLicense, FaceProfile


@receiver(post_save, sender=DriverLicense)
@receiver(post_save, sender=FaceProfile)
@receiver(post_delete, sender=DriverLicense)
@receiver(post_delete, sender=FaceProfile)
def refresh_profile_status(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    with transaction.atomic():
        driver = DriverProfile.objects.select_for_update().filter(pk=instance.driver_id).first()
        if driver:
            # Also invalidate a previously loaded approval form when evidence changes.
            driver.save(update_fields=['approval_status', 'updated_at'])
