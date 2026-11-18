"""Scheduling and attendance. All mutations use the same driver/vehicle/assignment lock order."""
import math
from datetime import datetime, time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Min
from django.utils import timezone

from accounts.concurrency import require_revision
from accounts.models import DriverProfile
from vehicles.models import Vehicle, DriverVehicleAssignment
from .models import DrivingShift, ShiftAudit
from .device_protocol import DeviceAPIError


def attendance(shift, now=None):
    now = now or timezone.now()
    sessions = list(shift.sessions.all())
    first = min((s.started_at for s in sessions), default=None)
    last = max((s.ended_at for s in sessions if s.ended_at), default=None)
    active = any(s.status == 'STARTED' for s in sessions)
    late = max(0, math.ceil((first - shift.start_at).total_seconds() / 60)) if first else 0
    punctuality = 'LATE' if first and first > shift.start_at + timedelta(minutes=shift.grace_minutes) else 'ON_TIME'
    if shift.cancelled:
        label = 'Đã hủy'
    elif shift.decision:
        label = shift.get_decision_display()
    elif first:
        label = 'Đi muộn' if punctuality == 'LATE' else 'Đúng giờ'
    elif now < shift.start_at:
        label = 'Sắp đến ca'
    elif now < shift.end_at:
        label = 'Chưa bắt đầu'
    else:
        label = 'Nghi vắng · chờ xác nhận'
    if shift.cancelled:
        activity = 'Đã hủy'
    elif active:
        activity = 'Quá giờ · phiên chưa kết thúc' if now >= shift.end_at else 'Đang lái'
    elif now < shift.end_at:
        activity = 'Chưa đến giờ' if now < shift.start_at and not first else 'Đang nghỉ / chưa mở phiên'
    elif last and last < shift.end_at:
        activity = f'Kết thúc sớm {math.ceil((shift.end_at-last).total_seconds()/60)} phút · cần xem xét'
    else:
        activity = 'Đã kết thúc' if last else 'Chưa có dữ liệu phiên'
    return dict(label=label, activity=activity, first=first, last=last, late_minutes=late,
                punctuality=punctuality if first else 'ABSENT', count=len(sessions), active=active,
                can_review=not shift.cancelled and not shift.decision and now >= shift.end_at and not active)


def snapshot(shift):
    return {field: (value.isoformat() if hasattr(value, 'isoformat') else value)
            for field in ('assignment_id', 'start_at', 'end_at', 'early_minutes', 'grace_minutes', 'note',
                          'cancelled', 'decision', 'admin_response', 'explanation', 'acknowledged_at')
            for value in [getattr(shift, field)]}


def audit(shift, user, action, before, reason=''):
    ShiftAudit.objects.create(shift=shift, actor=user, actor_name=user.username, action=action,
                              reason=reason, before=before, after=snapshot(shift))


def require_admin(user):
    if not user.is_authenticated or not user.is_active or not (user.is_superuser or user.role == 'ADMIN'):
        raise PermissionDenied


def lock_assignment(pk):
    original = DriverVehicleAssignment.objects.get(pk=pk)
    DriverProfile.objects.select_for_update().get(pk=original.driver_id)
    Vehicle.objects.select_for_update().get(pk=original.vehicle_id)
    assignment = DriverVehicleAssignment.objects.select_for_update().get(pk=pk)
    if (assignment.driver_id, assignment.vehicle_id) != (original.driver_id, original.vehicle_id):
        raise ValidationError('Phân công đã thay đổi. Vui lòng tải lại.')
    return assignment


@transaction.atomic
def save_shift(form, user):
    require_admin(user)
    assignment = lock_assignment(form.cleaned_data['assignment'].pk)
    shift = form.save(commit=False)
    before = {}
    if shift.pk:
        old = DrivingShift.objects.select_for_update().get(pk=shift.pk)
        require_revision(form.cleaned_data.get('version'), old)
        if old.assignment_id != assignment.pk:
            raise ValidationError('Không đổi phân công của ca. Hãy hủy và tạo ca mới.')
        if old.cancelled or old.decision or old.start_at <= timezone.now() or old.sessions.exists():
            raise ValidationError('Ca đã bắt đầu hoặc đã xử lý không được sửa lịch. Hãy dùng giải trình để ghi nhận ngoại lệ.')
        before = snapshot(old)
        shift.acknowledged_at = None
    if shift.start_at <= timezone.now():
        raise ValidationError('Cần lên lịch trước giờ bắt đầu ca.')
    shift.assignment = assignment
    shift.full_clean()
    shift.save()
    audit(shift, user, 'Cập nhật lịch' if before else 'Tạo ca', before, form.cleaned_data.get('reason', ''))
    return shift


@transaction.atomic
def shift_action(pk, data, user):
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied
    original = DrivingShift.objects.get(pk=pk)
    assignment = lock_assignment(original.assignment_id)
    shift = DrivingShift.objects.select_for_update().get(pk=pk)
    require_revision(data.get('version'), shift)
    before = snapshot(shift)
    action = data.get('action')
    if action in ('acknowledge', 'explain'):
        if assignment.driver.user_id != user.pk:
            raise PermissionDenied
        if shift.cancelled or shift.decision:
            raise ValidationError('Ca đã được xử lý, không thể thay đổi.')
        if action == 'acknowledge':
            if shift.acknowledged_at:
                raise ValidationError('Bạn đã nhận lịch này.')
            shift.acknowledged_at = timezone.now()
        else:
            content = (data.get('explanation') or '').strip()
            if not content or len(content) > 5000:
                raise ValidationError('Nhập giải trình từ 1 đến 5000 ký tự.')
            shift.explanation = content
            shift.explained_at = timezone.now()
    else:
        require_admin(user)
        reason = (data.get('response') or '').strip()
        if not reason or len(reason) > 5000:
            raise ValidationError('Cần nhập lý do hoặc phản hồi từ 1 đến 5000 ký tự.')
        if action == 'cancel':
            if shift.cancelled or shift.decision or shift.sessions.exists():
                raise ValidationError('Không thể hủy ca đã có phiên hoặc đã được xử lý.')
            shift.cancelled = True
            shift.admin_response = reason
        elif action == 'review':
            actual = attendance(shift)
            if not actual['can_review']:
                raise ValidationError('Chỉ chốt đánh giá khi ca đã hết giờ, không còn phiên mở và chưa xử lý.')
            decision = data.get('decision')
            if decision not in (actual['punctuality'], 'EXCUSED'):
                raise ValidationError('Kết luận phải khớp dữ liệu giờ bắt đầu hoặc chọn miễn đánh giá có lý do.')
            shift.decision, shift.admin_response = decision, reason
            shift.reviewed_at, shift.reviewer = timezone.now(), user
        else:
            raise ValidationError('Thao tác không hợp lệ.')
    shift.save()
    labels = {'acknowledge': 'Nhận lịch', 'explain': 'Gửi giải trình', 'cancel': 'Hủy ca', 'review': 'Chốt đánh giá'}
    audit(shift, user, labels[action], before, shift.admin_response if action in ('cancel', 'review') else '')
    return shift


def select_shift(assignment, now):
    rows = list(DrivingShift.objects.select_for_update().filter(assignment=assignment, cancelled=False,
                decision='', end_at__gt=now, start_at__lte=now + timedelta(minutes=120)).order_by('start_at', 'pk'))
    current = [s for s in rows if s.start_at <= now]
    candidates = current or [s for s in rows if now >= s.start_at - timedelta(minutes=s.early_minutes)]
    if not candidates:
        raise DeviceAPIError('NO_SCHEDULED_SHIFT', 'Ngoài ca lái được giao. Vui lòng kiểm tra lịch hoặc liên hệ quản trị viên.', 403, 'CONTACT_ADMIN')
    if len(candidates) > 1:
        raise DeviceAPIError('SHIFT_AMBIGUOUS', 'Có nhiều ca phù hợp. Cần quản trị viên kiểm tra.', 409, 'CONTACT_ADMIN')
    return candidates[0]


def monthly_summary(driver, month):
    return monthly_summaries([driver.pk], month)[driver.pk]


def monthly_summaries(driver_ids, month):
    start = timezone.make_aware(datetime.combine(month.replace(day=1), time.min))
    next_month = start.replace(year=start.year+1, month=1) if start.month == 12 else start.replace(month=start.month+1)
    result = {pk: dict(total=0, due=0, performed=0, pending=0, ON_TIME=0, LATE=0, ABSENT=0, EXCUSED=0, late_minutes=0)
              for pk in driver_ids}
    rows = DrivingShift.objects.filter(assignment__driver_id__in=driver_ids, cancelled=False,
        start_at__gte=start, start_at__lt=next_month).order_by().values(
            'pk', 'assignment__driver_id', 'start_at', 'end_at', 'decision').annotate(
                first_start=Min('sessions__started_at'), session_count=Count('sessions'))
    now = timezone.now()
    for shift in rows:
        counts = result[shift['assignment__driver_id']]
        counts['total'] += 1
        if shift['end_at'] > now:
            continue
        counts['due'] += 1
        if shift['session_count']:
            counts['performed'] += 1
        if shift['decision']:
            counts[shift['decision']] += 1
            if shift['decision'] == 'LATE' and shift['first_start']:
                counts['late_minutes'] += max(0, math.ceil((shift['first_start']-shift['start_at']).total_seconds()/60))
        else:
            counts['pending'] += 1
    for counts in result.values():
        assessed = counts['ON_TIME'] + counts['LATE'] + counts['ABSENT']
        counts['assessed'] = assessed
        counts['rate'] = round(counts['ON_TIME'] * 100 / assessed, 1) if assessed else None
    return result
