import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from vehicles.models import Device
from .models import AIConfig, DeviceConnection, DeviceEvent
from .protocol import validate_parameters, valid_device_code, valid_version


@transaction.atomic
def save_config(device_id, parameters, expected_version):
    validate_parameters(parameters)
    device = Device.objects.select_for_update().get(pk=device_id)
    if not valid_device_code(device.device_code):
        raise ValidationError('Mã MQTT chỉ được chứa chữ ASCII, số, dấu gạch ngang và gạch dưới.')
    config = AIConfig.objects.filter(device=device).first()
    if config is None:
        config = AIConfig(device=device, desired_version=0)
    if config.desired_version != expected_version:
        raise ValidationError('Cấu hình đã thay đổi. Hãy tải lại trang trước khi lưu.')
    if config.desired_version >= 2147483647:
        raise ValidationError('Đã đạt giới hạn phiên bản.')
    config.parameters = parameters
    config.desired_version += 1
    config.sync_status = 'pending'
    config.last_error = ''
    config.save()
    DeviceEvent.objects.create(device=device, message=f'Đã lưu cấu hình v{config.desired_version}')
    return config


@transaction.atomic
def handle_message(topic, raw, retained=False):
    if len(raw) > 16384:
        return False
    parts = topic.split('/')
    if len(parts) < 3 or parts[0] != 'savelife' or not valid_device_code(parts[1]):
        return False
    suffix = '/'.join(parts[2:])
    if suffix not in ('config/reported', 'status', 'heartbeat'):
        return False
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        return False
    if not isinstance(payload, dict) or payload.get('device_id') != parts[1]:
        return False
    device = Device.objects.select_for_update().filter(device_code=parts[1]).first()
    if device is None:
        return False
    now = timezone.now()
    if suffix == 'config/reported':
        version = payload.get('config_version')
        result = payload.get('result')
        if not valid_version(version) or result not in ('applied', 'rejected'):
            return False
        config = AIConfig.objects.filter(device=device).first()
        if not config or version != config.desired_version or config.sync_status == 'applied':
            return False
        if result == 'rejected' and config.sync_status == 'rejected':
            return False
        config.sync_status = result
        config.last_error = str(payload.get('reason', 'Pi từ chối cấu hình'))[:512] if result == 'rejected' else ''
        if result == 'applied':
            config.applied_version = version
            config.applied_parameters = config.parameters.copy()
            config.applied_at = now
        config.save()
        DeviceEvent.objects.create(device=device, message=f'v{version}: {result}')
        return True
    if suffix == 'heartbeat':
        if retained or type(payload.get('ai_running')) is not bool or not valid_version(payload.get('config_version')):
            return False
    elif payload.get('state') not in ('online', 'offline'):
        return False
    connection, _ = DeviceConnection.objects.get_or_create(device=device)
    old_state = connection.connection_state
    if suffix == 'heartbeat':
        connection.connection_state = 'online'
        connection.last_heartbeat_at = now
        connection.ai_running = payload['ai_running']
        connection.runtime_config_version = payload['config_version']
    else:
        connection.connection_state = payload['state']
        if payload['state'] == 'online':
            connection.last_online_at = now
            # Retained online cannot supply evidence of a fresh heartbeat.
            if retained:
                connection.last_heartbeat_at = None
        else:
            connection.last_offline_at = now
            connection.last_heartbeat_at = None
    connection.save()
    if old_state != connection.connection_state:
        DeviceEvent.objects.create(device=device, message=connection.connection_state)
    return True


def worker_available(health, now):
    return bool(health and health.connected and health.last_seen_at and (now - health.last_seen_at).total_seconds() <= 15)


def connection_label(connection, health, now):
    if not worker_available(health, now) or connection is None:
        return 'Không xác định'
    if connection.connection_state == 'offline':
        return 'Offline'
    beat = connection.last_heartbeat_at
    if not beat or (health.connected_at and beat < health.connected_at):
        return 'Không xác định'
    return 'Online' if (now - beat).total_seconds() <= 60 else 'Mất tín hiệu'
