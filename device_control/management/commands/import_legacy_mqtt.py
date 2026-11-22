from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from device_control.legacy_import import import_configs
from device_control.protocol import PARAMETERS


class Command(BaseCommand):
    help = 'Copy legacy savelife_device_config thresholds into existing SaveLife devices; never overwrite or delete source data.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the import. Without this flag only validate and preview.')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Legacy schema import requires PostgreSQL.')
        # Identifiers come exclusively from the fixed protocol constants, never CLI input.
        columns = ', '.join('a.' + connection.ops.quote_name(key.lower()) for key in PARAMETERS)
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT d.device_id, a.desired_version, ' + columns +
                ' FROM savelife_device_config.devices_aiconfig a'
                ' JOIN savelife_device_config.devices_device d ON d.id = a.device_id'
                ' ORDER BY d.device_id')
            records = [{'code': row[0], 'version': row[1], 'parameters': dict(zip(PARAMETERS, row[2:]))} for row in cursor.fetchall()]
        for result in import_configs(records, apply=options['apply']):
            self.stdout.write(result)
        self.stdout.write(f'{len(records)} source records checked. Legacy schema unchanged.')
