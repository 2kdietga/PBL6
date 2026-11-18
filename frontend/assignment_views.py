from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import DriverProfile
from accounts.templatetags.status_tags import status_badge
from vehicles.models import DriverVehicleAssignment, Vehicle
from .views import admin_required, display_date, page


@admin_required
def listing(request):
    now = timezone.now()
    filters = {
        'active': Q(start_at__lte=now) & (Q(end_at__isnull=True) | Q(end_at__gt=now)),
        'upcoming': Q(start_at__gt=now),
        'ended': Q(end_at__lte=now),
        'all': Q(),
    }
    state = request.GET.get('status', 'active')
    if state not in filters:
        state = 'active'
    rows = DriverVehicleAssignment.objects.select_related('driver', 'vehicle')
    query = request.GET.get('q', '').strip()
    if query:
        rows = rows.filter(Q(driver__full_name__icontains=query) | Q(vehicle__license_plate__icontains=query))
    driver, vehicle = request.GET.get('driver', ''), request.GET.get('vehicle', '')
    if driver.isascii() and driver.isdecimal() and len(driver) <= 18:
        rows = rows.filter(driver_id=driver)
    if vehicle.isascii() and vehicle.isdecimal() and len(vehicle) <= 18:
        rows = rows.filter(vehicle_id=vehicle)
    counts = rows.aggregate(**{key: Count('pk', filter=value) for key, value in filters.items()})
    labels = {'active': 'Đang hiệu lực', 'upcoming': 'Sắp bắt đầu', 'ended': 'Đã kết thúc', 'all': 'Tất cả'}
    tabs = []
    for key, label in labels.items():
        params = request.GET.copy()
        params['status'] = key
        params.pop('page', None)
        tabs.append({'label': label, 'count': counts[key], 'active': state == key, 'query': params.urlencode()})
    ordering = ('start_at', 'pk') if state == 'upcoming' else ('-start_at', '-pk')
    pagination = Paginator(rows.filter(filters[state]).order_by(*ordering), 20).get_page(request.GET.get('page'))
    result = []
    for obj in pagination:
        code = 'ended' if obj.end_at and obj.end_at <= now else 'upcoming' if obj.start_at > now else 'active'
        result.append({'cells': [obj.driver.full_name, obj.vehicle.license_plate, display_date(obj.start_at),
            display_date(obj.end_at) if obj.end_at else 'Không thời hạn',
            status_badge({'active': 'ACTIVE', 'upcoming': 'PENDING', 'ended': 'ENDED'}[code], labels[code])],
            'url': reverse('frontend:edit', args=['assignments', obj.pk])})
    params = request.GET.copy()
    params['status'] = state
    params.pop('page', None)
    return page(request, 'list.html', title='Phân công xe', key='assignments',
        columns=['Tài xế', 'Xe', 'Bắt đầu', 'Kết thúc', 'Trạng thái'], rows=result, pagination=pagination,
        query=query, selected_status=state, can_add=True, assignment_tabs=tabs,
        assignment_drivers=DriverProfile.objects.order_by('full_name', 'pk'),
        assignment_vehicles=Vehicle.objects.order_by('license_plate'), selected_driver=driver, selected_vehicle=vehicle,
        pagination_query=params.urlencode())
