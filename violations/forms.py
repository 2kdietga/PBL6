from django import forms

from .models import Violation, ViolationType


class ViolationTypeForm(forms.ModelForm):
    class Meta:
        model = ViolationType
        fields = ('code', 'name', 'description')
        labels = dict(code='Mã loại vi phạm', name='Tên loại vi phạm', description='Mô tả')

    def clean_code(self):
        return ViolationType.normalize_code(self.cleaned_data['code'])


class ViolationReviewForm(forms.ModelForm):
    class Meta:
        model = Violation
        fields = ('violation_type', 'severity', 'admin_note')
        labels = dict(violation_type='Loại vi phạm', severity='Mức độ', admin_note='Ghi chú của quản trị viên')
