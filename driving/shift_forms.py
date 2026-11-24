from django import forms
from django.db.models import Q
from django.utils import timezone

from accounts.concurrency import revision
from vehicles.models import DriverVehicleAssignment
from .models import DrivingShift


class AssignmentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, assignment):
        start = timezone.localtime(assignment.start_at).strftime('%d/%m/%Y %H:%M')
        end = timezone.localtime(assignment.end_at).strftime('%d/%m/%Y %H:%M') if assignment.end_at else 'Không thời hạn'
        return f'{assignment.driver.full_name} · {assignment.vehicle.license_plate} · {start} → {end}'


class ShiftForm(forms.ModelForm):
    assignment = AssignmentChoiceField(queryset=DriverVehicleAssignment.objects.none(), label='Phân công tài xế / xe',
        help_text='Chỉ hiển thị phân công chưa hết hạn, gồm cả phân công sắp bắt đầu.')
    version = forms.CharField(widget=forms.HiddenInput, required=False)
    reason = forms.CharField(label='Lý do sửa lịch', required=False, max_length=2000)

    class Meta:
        model = DrivingShift
        fields = ('assignment', 'start_at', 'end_at', 'early_minutes', 'grace_minutes', 'note')
        labels = dict(assignment='Phân công tài xế / xe', start_at='Bắt đầu ca', end_at='Kết thúc ca',
                      early_minutes='Cho phép bắt đầu sớm (phút)', grace_minutes='Cho phép trễ (phút)', note='Ghi chú')
        widgets = {key: forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
                   for key in ('start_at', 'end_at')}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assignments = DriverVehicleAssignment.objects.select_related('driver', 'vehicle')
        if self.instance.pk:
            # Keep the historical assignment visible when inspecting an existing shift.
            assignments = assignments.filter(pk=self.instance.assignment_id)
        else:
            assignments = assignments.filter(Q(end_at__isnull=True) | Q(end_at__gt=timezone.now()))
        self.fields['assignment'].queryset = assignments.order_by('driver__full_name', 'start_at', 'pk')
        self.initial['version'] = revision(self.instance)
        self.fields['early_minutes'].max_value = 120
        self.fields['grace_minutes'].max_value = 60
        self.fields['note'].max_length = 2000
        if self.instance.pk:
            self.fields['assignment'].disabled = True
            self.fields['assignment'].help_text = 'Phân công gắn với ca này; không thể thay đổi.'
            self.fields['reason'].required = True

    def clean_start_at(self):
        value = self.cleaned_data['start_at']
        if value <= timezone.now():
            raise forms.ValidationError('Cần lên lịch trước giờ bắt đầu ca.')
        return value


class ShiftCorrectionForm(ShiftForm):
    def __init__(self, *args, original, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.replaces = original
        self.initial['version'] = revision(original)
        self.fields['reason'].required = True
        self.fields['reason'].label = 'Lý do nhầm phân công'
