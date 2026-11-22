import threading
import uuid
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from device_control.mqtt_client import create_client


class Command(BaseCommand):
    help = 'Check MQTT TLS, authentication and telemetry subscriptions without changing device configuration.'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=15)

    def handle(self, *args, **options):
        if not 1 <= options['timeout'] <= 60:
            raise CommandError('Timeout must be between 1 and 60 seconds.')
        client = create_client(f'savelife-check-{uuid.uuid4().hex[:12]}')
        done = threading.Event()
        result = {'error': 'Timed out waiting for broker connection/subscription acknowledgement.'}

        def connected(client, userdata, flags, reason, properties):
            if reason.is_failure:
                result['error'] = f'Broker rejected authentication/connection: {reason}'
                done.set()
                return
            client.subscribe([(f'savelife/+/{suffix}', 1) for suffix in ('config/reported', 'status', 'heartbeat')])

        def subscribed(client, userdata, mid, reasons, properties):
            result['error'] = 'Broker denied telemetry subscriptions; check ACL.' if any(r.is_failure for r in reasons) else ''
            done.set()

        client.on_connect = connected
        client.on_subscribe = subscribed
        try:
            client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=30)
            client.loop_start()
            done.wait(options['timeout'])
        finally:
            client.disconnect()
            client.loop_stop()
        if result['error']:
            raise CommandError(result['error'])
        self.stdout.write(self.style.SUCCESS('MQTT OK: verified TLS, authenticated, telemetry subscriptions accepted. No configuration published.'))
