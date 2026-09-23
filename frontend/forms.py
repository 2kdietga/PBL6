from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from accounts.models import User, DriverProfile, DriverLicense
from vehicles.models import Vehicle, VehicleType, Device, DriverVehicleAssignment
from accounts.concurrency import revision, require_revision


class UploadImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
        super().__init__(*args, **kwargs)

    def to_python(self, data):
        if data and data.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Mỗi ảnh tối đa 5 MB.')
        image = super().to_python(data)
        if image and image.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('Chỉ nhận ảnh JPG, PNG hoặc WebP.')
        if image and image.image.width * image.image.height > 20_000_000:
            raise forms.ValidationError('Ảnh tối đa 20 megapixel. Vui lòng giảm kích thước ảnh.')
        return image


class MultiImageInput(forms.FileInput):
    allow_multiple_selected = True


class ExtraImagesField(UploadImageField):
    def __init__(self, **kwargs):
        super().__init__(widget=MultiImageInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}), **kwargs)

    def clean(self, data, initial=None):
        images = data if isinstance(data, (list, tuple)) else [data] if data else []
        if len(images) > 4:
            raise forms.ValidationError('Chọn tối đa 4 ảnh bổ sung.')
        return [super(ExtraImagesField, self).clean(image) for image in images]


class RegisterForm(UserCreationForm):
    email = forms.EmailField(label='Email', required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')


class VersionedModelForm(forms.ModelForm):
    version = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['version'] = revision(self.instance)

    def clean(self):
        values = super().clean()
        require_revision(values.get('version'), self.instance)
        return values


class ProfileForm(VersionedModelForm):
    avatar = UploadImageField(label='Ảnh đại diện / khuôn mặt', required=False)
    extra_images = ExtraImagesField(label='Ảnh góc mặt bổ sung (tối đa 4)', required=False)

    def clean(self):
        values = super().clean()
        if values.get('extra_images') and not values.get('avatar'):
            self.add_error('avatar', 'Chọn ảnh đại diện cùng các ảnh bổ sung để tạo lại vector.')
        return values
    class Meta:
        model = DriverProfile
        fields = ('full_name', 'date_of_birth', 'phone', 'address')
        labels = dict(full_name='Họ và tên', date_of_birth='Ngày sinh', phone='Số điện thoại', address='Địa chỉ')
        widgets = {'date_of_birth': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

    def clean_date_of_birth(self):
        value = self.cleaned_data['date_of_birth']
        if value >= timezone.localdate():
            raise forms.ValidationError('Ngày sinh phải trước ngày hiện tại.')
        return value


class LicenseForm(VersionedModelForm):
    front_image = UploadImageField(label='Ảnh GPLX mặt trước', required=False)
    back_image = UploadImageField(label='Ảnh GPLX mặt sau', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['front_image'].required = not bool(self.instance.front_image_url)
        self.fields['back_image'].required = not bool(self.instance.back_image_url)

    class Meta:
        model = DriverLicense
        fields = ('license_number', 'license_class', 'issued_date', 'expiry_date')
        labels = dict(license_number='Số GPLX', license_class='Hạng GPLX', issued_date='Ngày cấp', expiry_date='Ngày hết hạn', front_image_url='URL ảnh mặt trước', back_image_url='URL ảnh mặt sau')
        widgets = {key: forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d') for key in ('issued_date', 'expiry_date')}

    def clean(self):
        values = super().clean()
        issued, expiry = values.get('issued_date'), values.get('expiry_date')
        if issued and issued > timezone.localdate():
            self.add_error('issued_date', 'Ngày cấp không được ở tương lai.')
        if expiry and (expiry <= timezone.localdate() or (issued and expiry <= issued)):
            self.add_error('expiry_date', 'GPLX phải còn hạn và ngày hết hạn phải sau ngày cấp.')
        return values


class VehicleTypeForm(forms.ModelForm):
    class Meta:
        model = VehicleType
        fields = ('name', 'category', 'description')
        labels = dict(name='Tên loại xe', category='Nhóm xe', description='Mô tả')

    def clean_category(self):
        value = self.cleaned_data['category']
        if self.instance.pk and self.instance.vehicles.exists() and VehicleType.objects.get(pk=self.instance.pk).category != value:
            raise forms.ValidationError('Loại xe đã được sử dụng; không thể đổi nhóm xe.')
        return value


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ('license_plate', 'vehicle_type', 'brand', 'model', 'manufacture_year', 'load_capacity', 'passenger_capacity', 'status', 'description')
        labels = dict(license_plate='Biển số', vehicle_type='Loại xe', brand='Hãng xe', model='Mẫu xe', manufacture_year='Năm sản xuất', load_capacity='Khối lượng (kg)', passenger_capacity='Số hành khách', status='Trạng thái', description='Mô tả')

    def clean(self):
        values = super().clean()
        kind = values.get('vehicle_type')
        if kind:
            key = 'load_capacity' if kind.category == 'TRUCK' else 'passenger_capacity'
            other = 'passenger_capacity' if kind.category == 'TRUCK' else 'load_capacity'
            if not values.get(key) or values[key] <= 0:
                self.add_error(key, 'Thông số phải lớn hơn 0.')
            values[other] = None
        year = values.get('manufacture_year')
        if year and not 1900 <= year <= timezone.localdate().year:
            self.add_error('manufacture_year', 'Năm sản xuất không hợp lệ.')
        return values


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = DriverVehicleAssignment
        fields = ('driver', 'vehicle', 'start_at', 'end_at')
        labels = dict(driver='Tài xế', vehicle='Phương tiện', start_at='Bắt đầu', end_at='Kết thúc (không bắt buộc)')
        widgets = {key: forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M') for key in ('start_at', 'end_at')}

    def clean(self):
        values = super().clean()
        start, end = values.get('start_at'), values.get('end_at')
        if start and end and end <= start:
            self.add_error('end_at', 'Thời gian kết thúc phải sau thời gian bắt đầu.')
        vehicle, driver = values.get('vehicle'), values.get('driver')
        old = DriverVehicleAssignment.objects.filter(pk=self.instance.pk).first() if self.instance.pk else None
        same_assignment = bool(old and driver and vehicle and old.driver_id == driver.pk
                               and old.vehicle_id == vehicle.pk and old.start_at == start)
        # Ending/shortening an existing assignment must remain possible after suspension.
        closing = same_assignment and end is not None and (old.end_at is None or end <= old.end_at)
        if not closing and vehicle and vehicle.status != 'ACTIVE':
            self.add_error('vehicle', 'Chỉ phân công xe đang hoạt động.')
        if not closing and driver and (not driver.user.is_active or driver.approval_status != 'APPROVED'):
            self.add_error('driver', 'Tài xế phải đang hoạt động và hồ sơ đã được duyệt.')
        if self.instance.pk and self.instance.driving_sessions.exists():
            if driver and vehicle and (old.driver_id != driver.pk or old.vehicle_id != vehicle.pk or old.start_at != start):
                raise forms.ValidationError('Phân công đã có phiên lái: chỉ cập nhật thời gian kết thúc để giữ lịch sử.')
        return values


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ('device_code', 'name', 'vehicle', 'status')
        labels = dict(device_code='Mã thiết bị', name='Tên thiết bị', vehicle='Phương tiện', status='Trạng thái')
