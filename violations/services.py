from django.core.exceptions import ValidationError
from django.db import transaction

from .forms import ViolationReviewForm
from .models import Violation


@transaction.atomic
def review_violation(pk, data):
    violation = Violation.objects.select_for_update().get(pk=pk)
    action = data.get('action')
    if action == 'reopen':
        if violation.status == Violation.Status.PENDING:
            raise ValidationError('Vi phạm đã ở trạng thái chờ xác nhận.')
        # Reopening a record with an appeal needs rules for the existing appeal.
        if hasattr(violation, 'appeal'):
            raise ValidationError('Chưa hỗ trợ xem xét lại vi phạm đã có kháng cáo.')
        violation.status = Violation.Status.PENDING
        violation.save(update_fields=['status', 'updated_at'])
        return
    if action not in ('approve', 'reject'):
        raise ValidationError('Thao tác không hợp lệ.')
    if violation.status != Violation.Status.PENDING:
        raise ValidationError('Vi phạm đã được xử lý. Hãy tải lại trang hoặc chọn xem xét lại.')
    form = ViolationReviewForm(data, instance=violation)
    if not form.is_valid():
        return form
    if action == 'approve' and not violation.evidences.exists():
        form.add_error(None, 'Cần có ít nhất một bằng chứng trước khi xác nhận vi phạm.')
        return form
    violation = form.save(commit=False)
    violation.status = Violation.Status.APPROVED if action == 'approve' else Violation.Status.REJECTED
    violation.save(update_fields=['violation_type', 'severity', 'admin_note', 'status', 'updated_at'])
