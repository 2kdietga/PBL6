from django.contrib import admin
from django import forms

from .models import DrivingSession


class DrivingSessionForm(forms.ModelForm):
    class Meta:
        model = DrivingSession
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        assignment = cleaned.get('assignment')
        if assignment:
            self.instance.vehicle_id = assignment.vehicle_id
        return cleaned


@admin.register(DrivingSession)
class DrivingSessionAdmin(admin.ModelAdmin):
    form = DrivingSessionForm
    list_display = ('id', 'assignment', 'vehicle', 'source_device', 'status', 'started_at', 'ended_at')
    list_filter = ('status',)
    search_fields = ('assignment__driver__full_name', 'vehicle__license_plate', 'source_device__device_code')
    autocomplete_fields = ('assignment',)
    readonly_fields = ('vehicle', 'source_device', 'created_at', 'updated_at')
    list_select_related = ('assignment__driver', 'assignment__vehicle', 'vehicle', 'source_device')

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj:
            fields += ('assignment',)
            if obj.status == 'ENDED':
                fields += ('status', 'started_at', 'ended_at')
        return fields
