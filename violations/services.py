from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.utils import timezone

from .forms import ViolationReviewForm, AppealForm, AppealReviewForm
from .models import Violation, ViolationReview, Appeal
from accounts.concurrency import require_revision


def review_snapshot(violation):
    return dict(status=violation.status, severity=violation.severity,
                type_id=violation.violation_type_id, type_code=violation.violation_type.code,
                type_name=violation.violation_type.name, admin_note=violation.admin_note)


@transaction.atomic
def review_violation(pk, data, reviewer):
    if not reviewer.is_authenticated or not reviewer.is_active or not (reviewer.is_superuser or reviewer.role == 'ADMIN'):
        raise PermissionDenied
    violation = Violation.objects.select_for_update().get(pk=pk)
    require_revision(data.get('version'), violation)
    before = review_snapshot(violation)
    action = data.get('action')
    if action == 'reopen':
        if violation.status == Violation.Status.PENDING:
            raise ValidationError('Vi phạm đã ở trạng thái chờ xác nhận.')
        # Reopening a record with an appeal needs rules for the existing appeal.
        if hasattr(violation, 'appeal'):
            raise ValidationError('Chưa hỗ trợ xem xét lại vi phạm đã có kháng cáo.')
        violation.status = Violation.Status.PENDING
        violation.save(update_fields=['status', 'updated_at'])
        ViolationReview.objects.create(violation=violation, reviewer=reviewer, reviewer_name=reviewer.username,
                                       action=action, before=before, after=review_snapshot(violation))
        return
    if action not in ('approve', 'reject'):
        raise ValidationError('Thao tác không hợp lệ.')
    if violation.status != Violation.Status.PENDING:
        raise ValidationError('Vi phạm đã được xử lý. Hãy tải lại trang hoặc chọn xem xét lại.')
    form = ViolationReviewForm(data, instance=violation)
    if not form.is_valid():
        return form
    if action == 'approve':
        evidences = list(violation.evidences.select_for_update())
        if not evidences:
            form.add_error(None, 'Cần có ít nhất một bằng chứng trước khi xác nhận vi phạm.')
            return form
        for evidence in evidences:
            try:
                evidence.full_clean()
            except ValidationError:
                form.add_error(None, 'Bằng chứng có thông tin hoặc đường dẫn không hợp lệ. Chưa thể xác nhận vi phạm.')
                return form
    violation = form.save(commit=False)
    violation.status = Violation.Status.APPROVED if action == 'approve' else Violation.Status.REJECTED
    violation.save(update_fields=['violation_type', 'severity', 'admin_note', 'status', 'updated_at'])
    ViolationReview.objects.create(violation=violation, reviewer=reviewer, reviewer_name=reviewer.username,
                                   action=action, before=before, after=review_snapshot(violation))


@transaction.atomic
def submit_appeal(pk, data, user):
    violation = Violation.objects.select_for_update().get(pk=pk)
    if not user.is_authenticated or not user.is_active or violation.session.assignment.driver.user_id != user.pk:
        raise PermissionDenied
    require_revision(data.get('version'), violation)
    if violation.status != Violation.Status.APPROVED:
        raise ValidationError('Chỉ được kháng cáo vi phạm đã được xác nhận.')
    if Appeal.objects.filter(violation=violation).exists():
        raise ValidationError('Vi phạm này đã được gửi kháng cáo.')
    form = AppealForm(data)
    if not form.is_valid():
        return form
    Appeal.objects.create(violation=violation, content=form.cleaned_data['content'])
    violation.save(update_fields=['updated_at'])


@transaction.atomic
def resolve_appeal(pk, data, reviewer):
    if not reviewer.is_authenticated or not reviewer.is_active or not (reviewer.is_superuser or reviewer.role == 'ADMIN'):
        raise PermissionDenied
    violation = Violation.objects.select_for_update().get(pk=pk)
    require_revision(data.get('version'), violation)
    appeal = Appeal.objects.select_for_update().filter(violation=violation, deleted_at__isnull=True).first()
    if not appeal or appeal.status != Appeal.Status.PENDING or violation.status != Violation.Status.APPROVED:
        raise ValidationError('Kháng cáo không còn ở trạng thái chờ xử lý. Vui lòng tải lại trang.')
    action = data.get('action')
    if action not in ('appeal_approve', 'appeal_reject'):
        raise ValidationError('Thao tác không hợp lệ.')
    form = AppealReviewForm(data)
    if not form.is_valid():
        return form
    before = review_snapshot(violation)
    before['appeal_status'] = appeal.status
    appeal.status = Appeal.Status.APPROVED if action == 'appeal_approve' else Appeal.Status.REJECTED
    appeal.admin_response = form.cleaned_data['admin_response']
    appeal.resolved_at = timezone.now()
    appeal.save(update_fields=['status', 'admin_response', 'resolved_at', 'updated_at'])
    if action == 'appeal_approve':
        violation.status = Violation.Status.REVOKED
    violation.save(update_fields=['status', 'updated_at'])
    after = review_snapshot(violation)
    after.update(appeal_status=appeal.status, admin_response=appeal.admin_response, appeal_id=appeal.pk)
    ViolationReview.objects.create(violation=violation, reviewer=reviewer, reviewer_name=reviewer.username,
                                   action=action, before=before, after=after)
