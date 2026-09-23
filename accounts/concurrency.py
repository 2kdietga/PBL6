from django.core.exceptions import ValidationError


def revision(obj):
    """Opaque comparison value for the exact record displayed in a form."""
    if obj is None or not obj.pk:
        return 'new'
    return f'{obj._meta.label_lower}:{obj.pk}:{obj.updated_at.isoformat()}'


def require_revision(value, obj):
    if not value or value != revision(obj):
        raise ValidationError('Dữ liệu đã thay đổi hoặc biểu mẫu đã cũ. Vui lòng tải lại trang và kiểm tra trước khi lưu.')
