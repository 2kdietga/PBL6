"""Live-broker simulator check; all database writes stay in in-memory SQLite.

Run from the repository: python examples/mqtt_smoke_test.py
Uses a unique CHECK_* topic, removes its retained config afterwards, and never
publishes to real devices. Requires credentials with publish/subscribe access to
the test topic (the normal restricted worker account may not subscribe desired).
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.test_settings'
import django
django.setup()
import json
import queue
import threading
import time
import uuid
from django.conf import settings
from django.core.management import call_command
from vehicles.models import Device, Vehicle, VehicleType
from device_control.models import AIConfig, DeviceConnection
from device_control.services import save_config, handle_message
from device_control.protocol import defaults
from device_control.mqtt_client import create_client

call_command('migrate', verbosity=0)
code = 'CHECK_' + uuid.uuid4().hex[:12]
kind = VehicleType.objects.create(name='Temporary test', category='TRUCK')
vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate=code)
device = Device.objects.create(vehicle=vehicle, device_code=code, name='Isolated MQTT check')
config = save_config(device.pk, defaults(), 0)
server, pi = create_client(code + '_server'), create_client(code + '_pi')
server_ready, pi_ready = threading.Event(), threading.Event()
incoming = queue.Queue()
received = []
errors = []

def server_connect(client, userdata, flags, reason, properties):
    if reason.is_failure:
        errors.append(str(reason)); server_ready.set(); return
    client.subscribe([(f'savelife/{code}/{suffix}', 1) for suffix in ('config/reported', 'status', 'heartbeat')])

def pi_connect(client, userdata, flags, reason, properties):
    if reason.is_failure:
        errors.append(str(reason)); pi_ready.set(); return
    client.subscribe(f'savelife/{code}/config/desired', 1)

def suback(event):
    def callback(client, userdata, mid, reasons, properties):
        if any(reason.is_failure for reason in reasons): errors.append('ACL denied subscription')
        event.set()
    return callback

def pi_receive(client, userdata, message):
    if not message.payload:
        return
    payload = json.loads(message.payload)
    received.append(payload)
    if payload['device_id'] != code or payload['parameters'] != defaults():
        errors.append('Incorrect desired payload'); return
    # Simulator acknowledges only this temporary topic; never a real device.
    client.publish(f'savelife/{code}/config/reported', json.dumps({'device_id': code, 'config_version': payload['config_version'], 'result': 'applied'}), qos=1)
    client.publish(f'savelife/{code}/heartbeat', json.dumps({'device_id': code, 'config_version': payload['config_version'], 'ai_running': True}), qos=0)

server.on_connect = server_connect
server.on_subscribe = suback(server_ready)
server.on_message = lambda client, userdata, message: incoming.put((message.topic, message.payload, message.retain))
pi.on_connect = pi_connect
pi.on_subscribe = suback(pi_ready)
pi.on_message = pi_receive
try:
    server.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, 30)
    server.loop_start()
    assert server_ready.wait(15) and not errors, 'Server connection/subscriptions failed'
    payload = {'device_id': code, 'config_version': config.desired_version, 'parameters': config.parameters}
    info = server.publish(f'savelife/{code}/config/desired', json.dumps(payload), qos=1, retain=True)
    info.wait_for_publish(timeout=10)
    assert info.is_published(), 'Broker did not acknowledge desired config'
    # Pi connects AFTER publish: this also verifies retained config recovery.
    pi.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, 30)
    pi.loop_start()
    assert pi_ready.wait(15) and not errors, 'Pi simulation subscription failed'
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try: event = incoming.get(timeout=1)
        except queue.Empty: continue
        assert handle_message(*event), 'Backend rejected valid temporary message'
        config.refresh_from_db()
        if config.sync_status == 'applied' and DeviceConnection.objects.filter(device=device, ai_running=True).exists(): break
    config.refresh_from_db()
    assert config.applied_version == 1 and config.applied_parameters == defaults()
    assert DeviceConnection.objects.get(device=device).runtime_config_version == 1
    assert received and not errors
    print('PASS: TLS -> desired QoS1 PUBACK -> retained delivery after reconnect -> reported ACK -> applied database snapshot -> heartbeat. Database: isolated in-memory SQLite; no real device modified.')
finally:
    if server.is_connected():
        cleanup = server.publish(f'savelife/{code}/config/desired', b'', qos=1, retain=True)
        cleanup.wait_for_publish(timeout=5)
    pi.disconnect(); pi.loop_stop()
    server.disconnect(); server.loop_stop()
