import json
import logging
import queue
import signal
import threading
import time
import uuid
from datetime import timedelta

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from device_control.models import AIConfig, WorkerHealth
from device_control.protocol import valid_device_code, validate_parameters
from device_control.services import handle_message
from device_control.mqtt_client import create_client
from device_control import worker_lease

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the single SaveLife MQTT worker (TLS, QoS 1, retained desired config).'

    def add_arguments(self, parser):
        parser.add_argument('--run-seconds', type=int, default=0, help='Stop gracefully after this duration; zero runs continuously.')

    def handle(self, *args, **options):
        if options['run_seconds'] < 0:
            raise CommandError('--run-seconds must be nonnegative.')
        client = create_client()
        events = queue.Queue(maxsize=10000)
        ready = threading.Event()
        stop = threading.Event()
        resync = threading.Event()

        def on_connect(client, userdata, flags, reason_code, properties):
            ready.clear()
            if reason_code.is_failure:
                logger.warning('MQTT connection refused: %s', reason_code)
                return
            client.subscribe([(f'savelife/+/{suffix}', 1) for suffix in ('config/reported', 'status', 'heartbeat')])

        def on_subscribe(client, userdata, mid, reason_codes, properties):
            if any(code.is_failure for code in reason_codes):
                logger.error('MQTT subscription denied; check broker ACL.')
                client.disconnect()
                return
            resync.set()
            ready.set()
            logger.info('MQTT connected; telemetry subscriptions accepted.')

        def on_disconnect(client, userdata, flags, reason_code, properties):
            ready.clear()
            logger.info('MQTT disconnected: %s', reason_code)

        def on_message(client, userdata, message):
            if len(message.payload) <= 16384:
                try:
                    events.put_nowait((message.topic, message.payload, message.retain))
                except queue.Full:
                    logger.error('MQTT receive queue full; reports will be retried via desired config.')

        client.on_connect = on_connect
        client.on_subscribe = on_subscribe
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.enable_logger(logger)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())
        owner = uuid.uuid4().hex
        worker_lease.acquire(owner)
        pending = {}
        replay = set()
        connected_at = None
        deadline = time.monotonic() + options['run_seconds'] if options['run_seconds'] else None
        try:
            client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=30)
            client.loop_start()
            while not stop.is_set():
                if deadline and time.monotonic() >= deadline:
                    break
                close_old_connections()
                now = timezone.now()
                if resync.is_set():
                    resync.clear()
                    connected_at = now
                    replay = set(AIConfig.objects.values_list('pk', flat=True))
                worker_lease.renew(owner, ready.is_set(), connected_at)
                for _ in range(500):
                    try:
                        event = events.get_nowait()
                    except queue.Empty:
                        break
                    handle_message(*event)
                for key, (info, version, started) in list(pending.items()):
                    if info.is_published():
                        AIConfig.objects.filter(pk=key, desired_version=version, sync_status__in=['pending', 'sent']).update(sync_status='sent', last_sent_at=now)
                        pending.pop(key)
                        replay.discard(key)
                    elif time.monotonic() - started > 30:
                        pending.pop(key)
                if ready.is_set():
                    configs = AIConfig.objects.select_related('device').filter(
                        Q(sync_status='pending') | Q(sync_status='sent', last_sent_at__lt=now - timedelta(seconds=30)) | Q(pk__in=replay)
                    ).order_by('last_sent_at', 'pk')[:100]
                    for config in configs:
                        if config.pk in pending:
                            continue
                        if not valid_device_code(config.device.device_code):
                            AIConfig.objects.filter(pk=config.pk, desired_version=config.desired_version).update(sync_status='rejected', last_error='Mã thiết bị không hợp lệ cho MQTT.')
                            replay.discard(config.pk)
                            continue
                        try:
                            validate_parameters(config.parameters)
                        except ValueError as exc:
                            AIConfig.objects.filter(pk=config.pk, desired_version=config.desired_version).update(sync_status='rejected', last_error=str(exc))
                            replay.discard(config.pk)
                            continue
                        payload = json.dumps({'device_id': config.device.device_code, 'config_version': config.desired_version, 'parameters': config.parameters}, allow_nan=False)
                        info = client.publish(f'savelife/{config.device.device_code}/config/desired', payload, qos=1, retain=True)
                        if info.rc == mqtt.MQTT_ERR_SUCCESS:
                            pending[config.pk] = (info, config.desired_version, time.monotonic())
                stop.wait(1)
        finally:
            client.disconnect()
            client.loop_stop()
            worker_lease.release(owner)
