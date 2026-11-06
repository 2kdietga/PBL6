from django.db import transaction
from django.core.management.base import BaseCommand, CommandError

from vehicles.models import Device
from vehicles.device_keys import replace_key


class Command(BaseCommand):
    help = 'Issue or revoke a Raspberry Pi API key. Issuing immediately invalidates the old key.'

    def add_arguments(self, parser):
        parser.add_argument('device_code')
        parser.add_argument('--revoke', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            device = Device.objects.select_for_update().get(device_code=options['device_code'])
        except Device.DoesNotExist as exc:
            raise CommandError('Device does not exist; create it in the web interface first.') from exc
        secret = replace_key(device, revoke=options['revoke'])
        self.stdout.write(secret or 'API key revoked.')
