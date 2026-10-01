from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('vehicles', '0009_device_api_key_hash')]

    operations = [
        migrations.AddField(
            model_name='device',
            name='api_key_digest',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
    ]
