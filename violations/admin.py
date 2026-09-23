from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .forms import ViolationTypeForm
from .models import Appeal, Evidence, Violation, ViolationType


@admin.register(ViolationType)
class ViolationTypeAdmin(admin.ModelAdmin):
    form = ViolationTypeForm
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Violation)
class ViolationAdmin(ReadOnlyAdmin):
    list_display = ('id', 'session', 'violation_type', 'severity', 'detected_at', 'status', 'review_link')
    list_filter = ('status', 'severity', 'violation_type')
    search_fields = ('session__assignment__driver__full_name', 'session__assignment__vehicle__license_plate')
    list_select_related = ('violation_type', 'session__assignment__driver', 'session__assignment__vehicle')

    @admin.display(description='Xem / xác nhận')
    def review_link(self, obj):
        return format_html('<a href="{}">Mở trang vi phạm</a>', reverse('frontend:violation-detail', args=[obj.pk]))


@admin.register(Evidence)
class EvidenceAdmin(ReadOnlyAdmin):
    list_display = ('id', 'violation_id', 'type', 'captured_at')
    list_filter = ('type',)


@admin.register(Appeal)
class AppealAdmin(ReadOnlyAdmin):
    list_display = ('id', 'violation_id', 'status', 'created_at', 'resolved_at')
    list_filter = ('status',)
