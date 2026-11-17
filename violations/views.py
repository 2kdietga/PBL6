from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from frontend.views import admin_required, display_date, is_admin, page
from .forms import ViolationReviewForm, AppealForm, AppealReviewForm
from .models import Violation, Appeal
from .services import review_violation, submit_appeal, resolve_appeal
from accounts.concurrency import revision
from accounts.templatetags.status_tags import status_badge


def visible_violations(user):
    rows = Violation.objects.select_related('violation_type', 'session__assignment__driver', 'session__assignment__vehicle')
    if is_admin(user):
        return rows
    return rows.filter(session__assignment__driver__user=user).filter(
        Q(status__in=['PENDING', 'APPROVED']) | Q(status='REVOKED', appeal__isnull=False))


@login_required
def listing(request):
    rows = visible_violations(request.user)
    query = request.GET.get('q', '').strip()
    if query:
        rows = rows.filter(
            Q(violation_type__name__icontains=query) | Q(violation_type__code__icontains=query)
            | Q(session__assignment__driver__full_name__icontains=query)
            | Q(session__assignment__vehicle__license_plate__icontains=query)
        )
    choices = Violation.Status.choices if is_admin(request.user) else [
        (value, label) for value, label in Violation.Status.choices if value in ('PENDING', 'APPROVED', 'REVOKED')
    ]
    state = request.GET.get('status', '')
    if state in dict(choices):
        rows = rows.filter(status=state)
    pagination = Paginator(rows, 20).get_page(request.GET.get('page'))
    result = [{
        'cells': [f'VP-{obj.pk}', obj.session.assignment.driver.full_name,
                  obj.session.assignment.vehicle.license_plate, obj.violation_type.name,
                  obj.get_severity_display(), display_date(obj.detected_at), status_badge(obj.status, obj.get_status_display())],
        'url': reverse('frontend:violation-detail', args=[obj.pk]),
    } for obj in pagination]
    return page(request, 'list.html', title='Vi phạm' if is_admin(request.user) else 'Vi phạm của tôi',
                key='violations', columns=['Mã', 'Tài xế', 'Xe', 'Loại vi phạm', 'Mức độ', 'Phát hiện lúc', 'Trạng thái'],
                rows=result, pagination=pagination, query=query, choices=choices, selected_status=state)


def detail_page(request, violation, form=None, appeal_form=None, appeal_review_form=None):
    if form is None and is_admin(request.user):
        form = ViolationReviewForm(instance=violation)
    appeal = Appeal.objects.filter(violation=violation).first()
    return page(request, 'violation_detail.html', title=f'Vi phạm VP-{violation.pk}',
                appeal=appeal, appeal_form=appeal_form if appeal_form is not None else AppealForm(),
                appeal_review_form=appeal_review_form if appeal_review_form is not None else AppealReviewForm(),
                can_appeal=not is_admin(request.user) and violation.status == 'APPROVED' and appeal is None,
                can_review_appeal=bool(appeal and not appeal.deleted_at and appeal.status == 'PENDING' and violation.status == 'APPROVED'),
                violation=violation, evidences=violation.evidences.all(), form=form, version=revision(violation),
                reviews=violation.reviews.all() if is_admin(request.user) else [],
                can_reopen=violation.status != 'PENDING' and not hasattr(violation, 'appeal'))


@login_required
def detail(request, pk):
    return detail_page(request, get_object_or_404(visible_violations(request.user), pk=pk))


@admin_required
@require_POST
def review(request, pk):
    violation = get_object_or_404(visible_violations(request.user), pk=pk)
    try:
        form = review_violation(pk, request.POST, request.user)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        if form is not None:
            return detail_page(request, violation, form)
        messages.success(request, 'Đã cập nhật trạng thái vi phạm.')
    return redirect('frontend:violation-detail', pk=pk)


@login_required
@require_POST
def appeal_submit(request, pk):
    violation = get_object_or_404(visible_violations(request.user).filter(
        session__assignment__driver__user=request.user), pk=pk)
    try:
        form = submit_appeal(pk, request.POST, request.user)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        if form is not None:
            return detail_page(request, violation, appeal_form=form)
        messages.success(request, 'Đã gửi kháng cáo. Vui lòng chờ quản trị viên xem xét.')
    return redirect('frontend:violation-detail', pk=pk)


@admin_required
@require_POST
def appeal_review(request, pk):
    violation = get_object_or_404(visible_violations(request.user), pk=pk)
    try:
        form = resolve_appeal(pk, request.POST, request.user)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        if form is not None:
            return detail_page(request, violation, appeal_review_form=form)
        messages.success(request, 'Đã xử lý kháng cáo và lưu phản hồi cho tài xế.')
    return redirect('frontend:violation-detail', pk=pk)


@login_required
def appeals(request):
    rows = Appeal.objects.filter(deleted_at__isnull=True, violation__in=visible_violations(request.user)).select_related(
        'violation__session__assignment__driver', 'violation__violation_type')
    query = request.GET.get('q', '').strip()
    if query:
        rows = rows.filter(Q(content__icontains=query) | Q(violation__session__assignment__driver__full_name__icontains=query)
                           | Q(violation__violation_type__name__icontains=query))
    state = request.GET.get('status', '')
    if state in dict(Appeal.Status.choices):
        rows = rows.filter(status=state)
    pagination = Paginator(rows, 20).get_page(request.GET.get('page'))
    result = [{'cells': [f'KC-{obj.pk}', f'VP-{obj.violation_id}', obj.violation.session.assignment.driver.full_name,
                        obj.violation.violation_type.name, display_date(obj.created_at),
                        status_badge(obj.status, obj.get_status_display())],
               'url': reverse('frontend:violation-detail', args=[obj.violation_id])} for obj in pagination]
    return page(request, 'list.html', title='Kháng cáo' if is_admin(request.user) else 'Kháng cáo của tôi',
                columns=['Mã', 'Vi phạm', 'Tài xế', 'Loại vi phạm', 'Ngày gửi', 'Trạng thái'],
                rows=result, pagination=pagination, query=query, choices=Appeal.Status.choices, selected_status=state)
