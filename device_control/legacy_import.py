from django.core.management.base import CommandError
from django.db import transaction
from vehicles.models import Device
from .models import AIConfig, DeviceEvent
from .protocol import validate_parameters, valid_device_code, valid_version


@transaction.atomic
def import_configs(records, apply=False):
    results = []
    for record in records:
        code, version, parameters = record['code'], record['version'], record['parameters']
        if not valid_device_code(code) or not valid_version(version) or version < 1:
            raise CommandError('Legacy record has an invalid MQTT device code/version.')
        try:
            validate_parameters(parameters)
        except ValueError as exc:
            raise CommandError(f'{code}: {exc}') from exc
        device = Device.objects.select_for_update().filter(device_code=code).first()
        if device is None:
            raise CommandError(f'{code}: no matching SaveLife device; import aborted without changes.')
        if AIConfig.objects.filter(device=device).exists():
            results.append(f'{code}: skipped (already configured in SaveLife)')
            continue
        if apply:
            AIConfig.objects.create(device=device, parameters=parameters, desired_version=version, sync_status='pending')
            DeviceEvent.objects.create(device=device, message=f'Đã chuyển cấu hình v{version} từ schema cũ; chờ Pi xác nhận lại.')
        results.append(f'{code}: {"imported" if apply else "ready to import"} v{version}; fresh Pi ACK required')
    return results
