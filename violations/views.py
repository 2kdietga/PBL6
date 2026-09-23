from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from frontend.views import admin_required, display_date, is_admin, page
from .forms import ViolationReviewForm
from .models import Violation
from .services import review_violation


def visible_violations(user):
    rows = Violation.objects.select_related('violation_type', 'session__assignment__driver', 'session__assignment__vehicle')
    if is_admin(user):
        return rows
    return rows.filter(session__assignment__driver__user=user, status__in=['PENDING', 'APPROVED'])


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
        (value, label) for value, label in Violation.Status.choices if value in ('PENDING', 'APPROVED')
    ]
    state = request.GET.get('status', '')
    if state in dict(choices):
        rows = rows.filter(status=state)
    pagination = Paginator(rows, 20).get_page(request.GET.get('page'))
    result = [{
        'cells': [f'VP-{obj.pk}', obj.session.assignment.driver.full_name,
                  obj.session.assignment.vehicle.license_plate, obj.violation_type.name,
                  obj.get_severity_display(), display_date(obj.detected_at), obj.get_status_display()],
        'url': reverse('frontend:violation-detail', args=[obj.pk]),
    } for obj in pagination]
    return page(request, 'list.html', title='Vi phạm' if is_admin(request.user) else 'Vi phạm của tôi',
                key='violations', columns=['Mã', 'Tài xế', 'Xe', 'Loại vi phạm', 'Mức độ', 'Phát hiện lúc', 'Trạng thái'],
                rows=result, pagination=pagination, query=query, choices=choices, selected_status=state)


def detail_page(request, violation, form=None):
    if form is None and is_admin(request.user):
        form = ViolationReviewForm(instance=violation)
    return page(request, 'violation_detail.html', title=f'Vi phạm VP-{violation.pk}',
                violation=violation, evidences=violation.evidences.all(), form=form,
                can_reopen=violation.status != 'PENDING' and not hasattr(violation, 'appeal'))


@login_required
def detail(request, pk):
    return detail_page(request, get_object_or_404(visible_violations(request.user), pk=pk))


@admin_required
@require_POST
def review(request, pk):
    violation = get_object_or_404(visible_violations(request.user), pk=pk)
    try:
        form = review_violation(pk, request.POST)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        if form is not None:
            return detail_page(request, violation, form)
        messages.success(request, 'Đã cập nhật trạng thái vi phạm.')
    return redirect('frontend:violation-detail', pk=pk)
