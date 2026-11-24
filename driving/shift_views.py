from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q, Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.concurrency import revision
from accounts.models import DriverProfile
from vehicles.models import Vehicle
from frontend.views import admin_required, is_admin, page
from .models import DrivingShift, DrivingSession
from .shift_forms import ShiftForm, ShiftCorrectionForm
from .shift_services import attendance, monthly_summaries, save_shift, shift_action, correct_shift


def visible(user):
    rows = DrivingShift.objects.select_related('assignment__driver', 'assignment__vehicle',
        'second_assignment__driver', 'replacement__assignment__driver', 'replacement__second_assignment__driver').prefetch_related(
            Prefetch('sessions', queryset=DrivingSession.objects.select_related('assignment__driver').order_by('started_at', 'pk')))
    return rows if is_admin(user) else rows.filter(Q(assignment__driver__user=user) | Q(second_assignment__driver__user=user))


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
        rows = rows.filter(Q(assignment__driver_id=driver_id) | Q(second_assignment__driver_id=driver_id))
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
                note='Một ca có một hoặc hai tài xế cùng xe. Ca phải nằm trong thời hạn phân công của cả hai và không trùng ca khác. Kết thúc phiên của người đang lái trước khi người còn lại xác thực để nhận lượt. Lịch khóa khi ca đã bắt đầu.')


@login_required
def detail(request, pk):
    shift = get_object_or_404(visible(request.user), pk=pk)
    actual = attendance(shift)
    second_driver = bool(shift.second_assignment_id and shift.second_assignment.driver.user_id == request.user.pk)
    return page(request, 'shift_detail.html', title=f'Ca lái #{shift.pk}', shift=shift, actual=actual,
                version=revision(shift), audits=shift.audits.all() if is_admin(request.user) else [],
                my_acknowledged_at=shift.second_acknowledged_at if second_driver else shift.acknowledged_at,
                my_explanation=shift.second_explanation if second_driver else shift.explanation,
                can_correct=not shift.cancelled and not shift.decision and not actual['active'],
                can_edit=not shift.cancelled and not shift.decision and shift.start_at > timezone.now() and not actual['count'],
                decisions=DrivingShift.Decision.choices)


@admin_required
def correct(request, pk):
    original = get_object_or_404(visible(request.user), pk=pk)
    form = ShiftCorrectionForm(request.POST or None, original=original,
        initial={field: getattr(original, field) for field in
                 ('assignment', 'second_assignment', 'start_at', 'end_at', 'early_minutes', 'grace_minutes', 'note')})
    if request.method == 'POST' and form.is_valid():
        try:
            new = correct_shift(pk, form, request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Đã điều chỉnh lịch do nhầm phân công và tạo ca thay thế.')
            return redirect('frontend:shift-detail', pk=new.pk)
    return page(request, 'form.html', title=f'Điều chỉnh lịch do nhầm phân công · ca #{pk}', form=form,
        back_url=reverse('frontend:shift-detail', args=[pk]),
        note='Kết thúc tất cả phiên lái trước khi điều chỉnh. Ca cũ và các phiên được giữ lại, ca cũ không tính đánh giá chấp hành. Chọn phân công và thời gian mới trong tương lai để tạo ca thay thế; bắt buộc nhập lý do.')


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
