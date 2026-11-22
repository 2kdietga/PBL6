import json
import signal
from unittest.mock import Mock, patch
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from vehicles.models import Device, Vehicle, VehicleType
from .forms import AIConfigForm
from .models import AIConfig, DeviceConnection, DeviceEvent, WorkerHealth
from .protocol import defaults, validate_parameters
from .services import save_config, handle_message, connection_label
from . import worker_lease
from django.core.management.base import CommandError


class MQTTTests(TestCase):
    def setUp(self):
        kind = VehicleType.objects.create(name='Truck', category='TRUCK')
        vehicle = Vehicle.objects.create(vehicle_type=kind, license_plate='TEST-01')
        self.device = Device.objects.create(vehicle=vehicle, device_code='R01', name='Pi')
        self.config = AIConfig.objects.create(device=self.device)
        self.admin = User.objects.create_user(username='admin', role='ADMIN')

    def report(self, version=1, result='applied', **extra):
        return handle_message('savelife/R01/config/reported', json.dumps(dict(device_id='R01', config_version=version, result=result, **extra)).encode())

    def test_versions_and_stale_editor(self):
        saved = save_config(self.device.pk, defaults(), 1)
        self.assertEqual(saved.desired_version, 2)
        with self.assertRaises(ValidationError):
            save_config(self.device.pk, defaults(), 1)
        self.assertFalse(self.report(1))
        self.assertTrue(self.report(2))
        self.assertFalse(self.report(2))
        self.assertFalse(self.report(2, 'rejected'))
        saved.refresh_from_db()
        self.assertEqual(saved.applied_version, 2)
        self.assertEqual(saved.applied_parameters, defaults())

    def test_rejected_preserves_applied_snapshot(self):
        self.report()
        params = defaults()
        params['OBJECT_CONF'] = 0.5
        save_config(self.device.pk, params, 1)
        self.report(2, 'rejected', reason='runtime failed')
        self.config.refresh_from_db()
        self.assertEqual(self.config.applied_parameters['OBJECT_CONF'], 0.3)
        self.assertEqual(self.config.applied_version, 1)
        self.assertEqual(self.config.last_error, 'runtime failed')

    def test_invalid_messages(self):
        for raw in (b'null', b'[]', b'bad', b'\xff', b'{}', b'x' * 16385):
            self.assertFalse(handle_message('savelife/R01/heartbeat', raw))
        self.assertFalse(self.report(True))
        self.assertFalse(self.report(2))
        self.assertFalse(handle_message('savelife/R02/status', b'{"device_id":"R01","state":"online"}'))
        self.assertFalse(handle_message('savelife/R01/status', b'{"device_id":"R01","state":"invalid"}'))

    def test_heartbeat_never_applies_config_and_retained_is_ignored(self):
        raw = b'{"device_id":"R01","ai_running":true,"config_version":1}'
        self.assertFalse(handle_message('savelife/R01/heartbeat', raw, True))
        self.assertTrue(handle_message('savelife/R01/heartbeat', raw))
        self.config.refresh_from_db()
        self.assertEqual(self.config.sync_status, 'pending')
        self.assertEqual(DeviceConnection.objects.get(device=self.device).runtime_config_version, 1)

    def test_connection_health_and_timeout(self):
        now = timezone.now()
        health = WorkerHealth(connected=True, last_seen_at=now, connected_at=now - timedelta(seconds=100))
        connection = DeviceConnection(connection_state='online', last_heartbeat_at=now)
        self.assertEqual(connection_label(connection, health, now), 'Online')
        connection.last_heartbeat_at = now - timedelta(seconds=61)
        self.assertEqual(connection_label(connection, health, now), 'Mất tín hiệu')
        health.connected = False
        self.assertEqual(connection_label(connection, health, now), 'Không xác định')
        health.connected = True
        health.connected_at = now
        self.assertEqual(connection_label(connection, health, now), 'Không xác định')
        connection.connection_state = 'offline'
        self.assertEqual(connection_label(connection, health, now), 'Offline')
        health.last_seen_at = now - timedelta(seconds=16)
        self.assertEqual(connection_label(connection, health, now), 'Không xác định')

    def test_retained_online_is_not_fresh_evidence(self):
        handle_message('savelife/R01/heartbeat', b'{"device_id":"R01","ai_running":true,"config_version":1}')
        handle_message('savelife/R01/status', b'{"device_id":"R01","state":"online"}', True)
        self.assertIsNone(DeviceConnection.objects.get(device=self.device).last_heartbeat_at)

    def test_parameter_limits(self):
        for value in (float('nan'), float('inf'), True, 0.1, '0.3'):
            params = {**defaults(), 'OBJECT_CONF': value}
            with self.assertRaises(ValueError):
                validate_parameters(params)
        self.assertFalse(AIConfigForm({'version': 1, **defaults(), 'OBJECT_CONF': 'nan'}).is_valid())

    def test_web_permissions_and_render(self):
        paths = [reverse('frontend:iot'), reverse('frontend:iot-status'), reverse('frontend:iot-detail', args=[self.device.pk])]
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 302)
        driver = User.objects.create_user(username='driver')
        self.client.force_login(driver)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.client.force_login(self.admin)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.post(paths[-1], {'version': 1, **defaults()})
        self.assertEqual(response.status_code, 302)
        self.config.refresh_from_db()
        self.assertEqual(self.config.desired_version, 2)
        response = self.client.post(paths[-1], {'version': 1, **defaults()})
        self.assertContains(response, 'Cấu hình đã thay đổi')

    def test_unknown_device_is_not_created(self):
        self.assertFalse(handle_message('savelife/R99/status', b'{"device_id":"R99","state":"online"}'))
        self.assertEqual(Device.objects.count(), 1)

    def test_device_topic_identity_is_stable(self):
        self.device.device_code = 'R02'
        with self.assertRaises(ValidationError):
            self.device.save()

    def test_first_configuration_starts_at_version_one(self):
        self.config.delete()
        self.client.force_login(self.admin)
        response = self.client.post(reverse('frontend:iot-detail', args=[self.device.pk]), {'version': 0, **defaults()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AIConfig.objects.get(device=self.device).desired_version, 1)

    def test_detail_poll_includes_applied_snapshot_and_events(self):
        self.report()
        self.client.force_login(self.admin)
        data = self.client.get(reverse('frontend:iot-device-status', args=[self.device.pk])).json()
        self.assertEqual(data['applied_parameters'], defaults())
        self.assertEqual(data['events'][0]['message'], 'v1: applied')

    def test_devices_menu_combines_management_and_configuration(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('frontend:devices'))
        self.assertContains(response, reverse('frontend:iot-detail', args=[self.device.pk]))
        self.assertContains(response, reverse('frontend:edit', args=['devices', self.device.pk]))
        self.assertNotContains(response, 'href="/iot/"')
        self.assertContains(response, 'aria-current="page"')
        response = self.client.get(reverse('frontend:devices'), {'q': 'unmatched-device'})
        self.assertContains(response, 'Không có thiết bị phù hợp')

    def test_worker_lease_prevents_parallel_workers(self):
        worker_lease.acquire('first')
        with self.assertRaises(CommandError):
            worker_lease.acquire('second')
        worker_lease.renew('first', True, timezone.now())
        worker_lease.release('second')
        self.assertEqual(WorkerHealth.objects.get(pk=1).owner, 'first')
        WorkerHealth.objects.filter(pk=1).update(lease_until=timezone.now() - timedelta(seconds=1))
        worker_lease.acquire('second')
        with self.assertRaises(CommandError):
            worker_lease.renew('first', True, timezone.now())
        worker_lease.release('second')
        self.assertFalse(WorkerHealth.objects.get(pk=1).connected)

    def test_legacy_import_preserves_versions_and_never_overwrites(self):
        from .legacy_import import import_configs
        self.config.delete()
        record = {'code': 'R01', 'version': 3, 'parameters': defaults()}
        import_configs([record])
        self.assertFalse(AIConfig.objects.exists())
        import_configs([record], apply=True)
        config = AIConfig.objects.get(device=self.device)
        self.assertEqual(config.desired_version, 3)
        self.assertEqual(config.applied_version, 0)
        self.assertEqual(config.sync_status, 'pending')
        import_configs([{**record, 'version': 9}], apply=True)
        config.refresh_from_db()
        self.assertEqual(config.desired_version, 3)

    def test_legacy_import_rolls_back_if_a_device_is_unmatched(self):
        from .legacy_import import import_configs
        self.config.delete()
        with self.assertRaises(CommandError):
            import_configs([{'code': code, 'version': 1, 'parameters': defaults()} for code in ('R01', 'UNKNOWN')], apply=True)
        self.assertFalse(AIConfig.objects.exists())

    @override_settings(MQTT_USERNAME='worker', MQTT_PASSWORD='test-only')
    def test_worker_broker_ack_marks_sent_but_not_applied(self):
        from device_control.management.commands import mqtt_worker
        client = Mock()
        handlers = {}
        reason = Mock(is_failure=False)
        info = Mock(rc=0)

        def network_start():
            client.on_connect(client, None, None, reason, None)
            client.on_subscribe(client, None, 1, [reason], None)

        def acknowledge():
            handlers[signal.SIGTERM]()
            return True

        info.is_published.side_effect = acknowledge
        client.publish.return_value = info
        client.loop_start.side_effect = network_start
        with patch.object(mqtt_worker.mqtt, 'Client', return_value=client), patch.object(mqtt_worker.signal, 'signal', side_effect=lambda sig, fn: handlers.update({sig: fn})):
            call_command('mqtt_worker')
        client.tls_set.assert_called_once()
        args, kwargs = client.publish.call_args
        self.assertEqual(args[0], 'savelife/R01/config/desired')
        self.assertEqual(json.loads(args[1])['parameters'], defaults())
        self.assertEqual(kwargs, {'qos': 1, 'retain': True})
        self.config.refresh_from_db()
        self.assertEqual(self.config.sync_status, 'sent')
        self.assertEqual(self.config.applied_version, 0)
        self.assertFalse(WorkerHealth.objects.get(pk=1).connected)
