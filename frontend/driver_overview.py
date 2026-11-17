"""Read-only driver activity summaries with explicit time and status scopes."""
from datetime import timedelta

from django.db.models import Count, DurationField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone

from driving.models import DrivingSession
from vehicles.models import DriverVehicleAssignment
from violations.models import Appeal, Violation


def driver_overview(driver, period='all', now=None):
    now = now or timezone.now()
    period = period if period in ('all', '30', '90') else 'all'
    since = now - timedelta(days=int(period)) if period != 'all' else None
    sessions = DrivingSession.objects.filter(assignment__driver=driver, started_at__lte=now)
    violations = Violation.objects.filter(session__assignment__driver=driver, detected_at__lte=now)
    if since:
        sessions = sessions.filter(started_at__gte=since)
        violations = violations.filter(detected_at__gte=since)
    session_stats = sessions.aggregate(
        total=Count('pk'), ended=Count('pk', filter=Q(status='ENDED')),
        started=Count('pk', filter=Q(status='STARTED')),
        vehicles=Count('vehicle_id', distinct=True),
        duration=Sum(ExpressionWrapper(F('ended_at') - F('started_at'), output_field=DurationField()),
                     filter=Q(status='ENDED')))
    minutes = int((session_stats.pop('duration') or timedelta()).total_seconds() // 60)
    session_stats['duration_label'] = f'{minutes // 60} giờ {minutes % 60} phút'
    counts = dict(violations.values('status').annotate(total=Count('pk')).values_list('status', 'total'))
    violation_stats = {status: counts.get(status, 0) for status in Violation.Status.values}
    violation_stats['total'] = sum(counts.values())
    confirmed = violations.filter(status='APPROVED')
    assignments = DriverVehicleAssignment.objects.filter(driver=driver).select_related('vehicle__vehicle_type')
    current = assignments.filter(start_at__lte=now).filter(Q(end_at__isnull=True) | Q(end_at__gt=now))
    assignment_counts = assignments.aggregate(total=Count('pk'), vehicles=Count('vehicle_id', distinct=True),
        upcoming=Count('pk', filter=Q(start_at__gt=now)))
    appeals = Appeal.objects.filter(violation__in=violations, deleted_at__isnull=True)
    appeal_counts = dict(appeals.values('status').annotate(total=Count('pk')).values_list('status', 'total'))
    observations = []
    if not session_stats['total']:
        observations.append('Chưa có phiên bắt đầu trong khoảng đã chọn; chưa đủ dữ liệu đánh giá hoạt động.')
    if violation_stats['APPROVED']:
        observations.append(f"Có {violation_stats['APPROVED']} vi phạm đã xác nhận còn hiệu lực trong khoảng đã chọn.")
    elif session_stats['total']:
        observations.append('Chưa ghi nhận vi phạm đã xác nhận còn hiệu lực trong khoảng đã chọn.')
    if violation_stats['PENDING']:
        observations.append(f"Có {violation_stats['PENDING']} sự kiện chờ xác nhận, chưa tính là lỗi đã xác nhận.")
    if session_stats['started']:
        observations.append(f"Có {session_stats['started']} phiên chưa kết thúc trong khoảng đã chọn; cần kiểm tra nếu chuyến đi thực tế đã xong.")
    return {
        'period': period, 'since': since, 'as_of': now, 'sessions': session_stats,
        'violations': violation_stats, 'observations': observations,
        'high_severity': confirmed.filter(severity='HIGH').count(),
        'appeals': {status: appeal_counts.get(status, 0) for status in Appeal.Status.values},
        'top_types': list(confirmed.values('violation_type__name').annotate(total=Count('pk')).order_by('-total', 'violation_type__name')[:5]),
        'current_assignments': list(current.order_by('vehicle__license_plate', '-start_at')),
        'assignment_counts': assignment_counts,
        'recent_assignments': list(assignments.order_by('-start_at', '-pk')[:8]),
        'recent_sessions': list(sessions.select_related('vehicle').order_by('-started_at', '-pk')[:8]),
        'recent_violations': list(violations.select_related('violation_type', 'session__vehicle').order_by('-detected_at', '-pk')[:8]),
    }
