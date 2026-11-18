from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.concurrency import revision
from accounts.models import DriverProfile
from vehicles.models import Vehicle
from frontend.views import admin_required, is_admin, page
from .models import DrivingShift
from .shift_forms import ShiftForm
from .shift_services import attendance, monthly_summaries, save_shift, shift_action


def visible(user):
    rows = DrivingShift.objects.select_related('assignment__driver', 'assignment__vehicle').prefetch_related('sessions')
    return rows if is_admin(user) else rows.filter(assignment__driver__user=user)


@login_required
def calendar(request):
    try:
        day = date.fromisoformat(request.GET.get('week', ''))
    except (ValueError, TypeError):
        day = timezone.localdate()
    monday = day - timedelta(days=day.weekday())
    # Bound navigation to ordinary application dates.
    if not 2000 <= monday.year <= 2099:
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    start = timezone.make_aware(datetime.combine(monday, time.min))
    end = start + timedelta(days=7)
    rows = visible(request.user).filter(start_at__lt=end, end_at__gt=start)
    driver_id, vehicle_id = request.GET.get('driver', ''), request.GET.get('vehicle', '')
    if is_admin(request.user) and driver_id.isascii() and driver_id.isdecimal() and len(driver_id) <= 18:
        rows = rows.filter(assignment__driver_id=driver_id)
    if vehicle_id.isascii() and vehicle_id.isdecimal() and len(vehicle_id) <= 18:
        rows = rows.filter(assignment__vehicle_id=vehicle_id)
    shifts = [(shift, attendance(shift)) for shift in rows]
    days = []
    for offset in range(7):
        current = monday + timedelta(days=offset)
        days.append({'date': current, 'today': current == timezone.localdate(),
                     'items': [{'shift': s, 'attendance': a} for s, a in shifts
                               if timezone.localtime(s.start_at).date() <= current <= timezone.localtime(s.end_at-timedelta(microseconds=1)).date()]})
    return page(request, 'shift_calendar.html', title='Lịch lái', days=days, week=monday,
        previous=monday-timedelta(days=7), next_week=monday+timedelta(days=7),
        drivers=DriverProfile.objects.order_by('full_name') if is_admin(request.user) else [],
        vehicles=Vehicle.objects.filter(driver_assignments__driver__user=request.user).distinct() if not is_admin(request.user) else Vehicle.objects.order_by('license_plate'),
        selected_driver=driver_id, selected_vehicle=vehicle_id)


@admin_required
def edit(request, pk=None):
    shift = get_object_or_404(visible(request.user), pk=pk) if pk else None
    form = ShiftForm(request.POST or None, instance=shift)
    if request.method == 'POST' and form.is_valid():
        try:
            saved = save_shift(form, request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Đã lưu lịch ca lái.')
            return redirect('frontend:shift-detail', pk=saved.pk)
    return page(request, 'form.html', title='Sửa ca lái' if shift else 'Tạo ca lái', form=form,
                note='Ca phải nằm trong phân công và không trùng tài xế hoặc xe. Lịch khóa khi ca đã bắt đầu.')


@login_required
def detail(request, pk):
    shift = get_object_or_404(visible(request.user), pk=pk)
    actual = attendance(shift)
    return page(request, 'shift_detail.html', title=f'Ca lái #{shift.pk}', shift=shift, actual=actual,
                version=revision(shift), audits=shift.audits.all() if is_admin(request.user) else [],
                can_edit=not shift.cancelled and not shift.decision and shift.start_at > timezone.now() and not actual['count'],
                decisions=DrivingShift.Decision.choices)


@login_required
@require_POST
def action(request, pk):
    get_object_or_404(visible(request.user), pk=pk)
    try:
        shift_action(pk, request.POST, request.user)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        messages.success(request, 'Đã cập nhật ca lái.')
    return redirect('frontend:shift-detail', pk=pk)


@login_required
def report(request):
    try:
        month = datetime.strptime(request.GET.get('month', ''), '%Y-%m').date()
        if not 2000 <= month.year <= 2099:
            raise ValueError
    except (ValueError, TypeError):
        month = timezone.localdate().replace(day=1)
    rows = DriverProfile.objects.order_by('full_name')
    if not is_admin(request.user):
        rows = rows.filter(user=request.user)
    driver_id = request.GET.get('driver', '')
    if driver_id.isascii() and driver_id.isdecimal() and len(driver_id) <= 18:
        rows = rows.filter(pk=driver_id)
    from django.core.paginator import Paginator
    pagination = Paginator(rows, 20).get_page(request.GET.get('page'))
    drivers = list(pagination)
    summaries = monthly_summaries([driver.pk for driver in drivers], month)
    return page(request, 'shift_report.html', title='Chấp hành lịch lái', month=month, selected_driver=driver_id,
                pagination=pagination, reports=[{'driver': d, 'stats': summaries[d.pk]} for d in drivers])
