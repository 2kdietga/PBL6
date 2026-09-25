from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def update_pending_profiles(apps, schema_editor):
    Driver = apps.get_model('accounts', 'DriverProfile')
    Driver.objects.using(schema_editor.connection.alias).filter(
        Q(driver_license__status='PENDING') | Q(face_profile__approval_status='PENDING'),
        approval_status='INCOMPLETE',
    ).update(approval_status='PENDING', updated_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [('accounts', '0007_alter_driverprofile_approval_status')]
    operations = [migrations.RunPython(update_pending_profiles, migrations.RunPython.noop)]
