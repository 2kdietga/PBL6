import secrets
from hashlib import sha256

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from vehicles.models import Device


class Command(BaseCommand):
    help = 'Issue or revoke a Raspberry Pi API key. Issuing immediately invalidates the old key.'

    def add_arguments(self, parser):
        parser.add_argument('device_code')
        parser.add_argument('--revoke', action='store_true')

    def handle(self, *args, **options):
        try:
            device = Device.objects.get(device_code=options['device_code'])
        except Device.DoesNotExist as exc:
            raise CommandError('Device does not exist; create it in the web interface first.') from exc
        secret = '' if options['revoke'] else secrets.token_urlsafe(32)
        device.api_key_hash = make_password(secret) if secret else ''
        device.api_key_digest = sha256(secret.encode()).hexdigest() if secret else None
        device.save(update_fields=['api_key_hash', 'api_key_digest', 'updated_at'])
        self.stdout.write(secret or 'API key revoked.')
