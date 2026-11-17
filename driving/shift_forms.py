from django import forms
from django.utils import timezone

from accounts.concurrency import revision
from vehicles.models import DriverVehicleAssignment
from .models import DrivingShift


class ShiftForm(forms.ModelForm):
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
        self.fields['assignment'].queryset = DriverVehicleAssignment.objects.select_related('driver', 'vehicle').order_by('driver__full_name')
        self.initial['version'] = revision(self.instance)
        self.fields['early_minutes'].max_value = 120
        self.fields['grace_minutes'].max_value = 60
        self.fields['note'].max_length = 2000
        if self.instance.pk:
            self.fields['assignment'].disabled = True
            self.fields['reason'].required = True

    def clean_start_at(self):
        value = self.cleaned_data['start_at']
        if value <= timezone.now():
            raise forms.ValidationError('Cần lên lịch trước giờ bắt đầu ca.')
        return value
