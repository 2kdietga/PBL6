from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction

from .forms import ViolationReviewForm
from .models import Violation, ViolationReview
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
