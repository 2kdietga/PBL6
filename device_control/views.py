from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from frontend.views import admin_required, page
from vehicles.models import Device
from .forms import AIConfigForm
from .models import AIConfig, WorkerHealth
from .services import connection_label, save_config, worker_available


def device_rows(device_id=None):
    health = WorkerHealth.objects.filter(pk=1).first()
    now = timezone.now()
    rows = []
    devices = Device.objects.select_related('vehicle', 'ai_config', 'mqtt_connection').order_by('device_code')
    if device_id is not None:
        devices = devices.filter(pk=device_id)
    for device in devices:
        config = getattr(device, 'ai_config', None)
        connection = getattr(device, 'mqtt_connection', None)
        label = connection_label(connection, health, now)
        rows.append({'id': device.pk, 'code': device.device_code, 'name': device.name,
            'vehicle': device.vehicle.license_plate, 'connection': label,
            'ai': ('Đang chạy' if connection.ai_running else 'Đã dừng') if label == 'Online' else 'Không xác định',
            'heartbeat': connection.last_heartbeat_at.isoformat() if connection and connection.last_heartbeat_at else '—',
            'desired': config.desired_version if config else 0, 'applied': config.applied_version if config else 0,
            'sync': config.get_sync_status_display() if config else 'Chưa cấu hình',
            'error': config.last_error if config else '',
            'applied_at': config.applied_at.isoformat() if config and config.applied_at else None,
            'updated_at': config.updated_at.isoformat() if config else None,
            'runtime': connection.runtime_config_version if connection else 0})
    return rows, worker_available(health, now)


@admin_required
@require_GET
@never_cache
def dashboard(request):
    rows, available = device_rows()
    query = request.GET.get('q', '').strip()
    if query:
        rows = [row for row in rows if query.casefold() in ' '.join((row['code'], row['name'], row['vehicle'])).casefold()]
    return page(request, 'device_control/dashboard.html', title='Thiết bị', rows=rows, available=available, query=query)


@admin_required
@require_GET
@never_cache
def status(request, pk=None):
    if pk is not None:
        device = get_object_or_404(Device, pk=pk)
    rows, available = device_rows(pk)
    data = {'devices': rows, 'worker_available': available}
    if pk is not None:
        config = AIConfig.objects.filter(device=device).first()
        data['applied_parameters'] = config.applied_parameters if config else {}
        data['events'] = list(device.mqtt_events.order_by('-created_at').values('message', 'created_at')[:30])
    return JsonResponse(data)


@admin_required
@require_http_methods(['GET', 'POST'])
@never_cache
def detail(request, pk):
    device = get_object_or_404(Device.objects.select_related('vehicle'), pk=pk)
    config = AIConfig.objects.filter(device=device).first() or AIConfig(device=device, desired_version=0)
    form = AIConfigForm(request.POST if request.method == 'POST' else None,
        initial={'version': config.desired_version, **config.parameters})
    if request.method == 'POST' and form.is_valid():
        try:
            save_config(device.pk, form.parameters(), form.cleaned_data['version'])
        except (ValidationError, ValueError) as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Đã lưu cấu hình. Chờ Raspberry Pi xác nhận áp dụng.')
            return redirect('frontend:iot-detail', pk=pk)
    return page(request, 'device_control/detail.html', title=f'Thiết bị · {device.device_code}',
        device=device, config=config, form=form, events=device.mqtt_events.order_by('-created_at')[:30])
