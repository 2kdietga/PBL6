from functools import wraps
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from accounts.media_services import MediaError
from accounts.profile_services import save_profile, save_license
from driving.models import DrivingSession
from vehicles.models import Vehicle, VehicleType, DriverVehicleAssignment, Device
from violations.models import ViolationType
from violations.forms import ViolationTypeForm
from .forms import RegisterForm, ProfileForm, LicenseForm, VehicleForm, VehicleTypeForm, AssignmentForm, DeviceForm


def is_admin(user):
    return user.is_authenticated and (user.role == 'ADMIN' or user.is_superuser)


def admin_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user): raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


ADMIN_MENU = [('dashboard', 'Tổng quan'), ('drivers', 'Tài xế'), ('vehicles', 'Phương tiện'), ('assignments', 'Phân công'), ('sessions', 'Phiên lái'), ('violations', 'Vi phạm'), ('devices', 'Thiết bị'), ('catalogs', 'Loại xe'), ('violation-types', 'Loại vi phạm')]
DRIVER_MENU = [('dashboard', 'Tổng quan'), ('profile', 'Hồ sơ cá nhân'), ('license', 'Giấy phép lái xe'), ('vehicles', 'Xe được giao'), ('sessions', 'Phiên lái của tôi'), ('violations', 'Vi phạm của tôi')]


def page(request, template, **context):
    admin = is_admin(request.user)
    context.update(is_admin=admin, navigation=ADMIN_MENU if admin else DRIVER_MENU)
    return render(request, template, context)


class SignIn(LoginView):
    template_name = 'auth.html'
    redirect_authenticated_user = True
    extra_context = {'title': 'Đăng nhập'}


class SignOut(LogoutView):
    next_page = 'frontend:login'


def register(request):
    if request.user.is_authenticated: return redirect('frontend:dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.role = 'USER'
        user.save()
        login(request, user)
        messages.success(request, 'Đã tạo tài khoản. Vui lòng bổ sung hồ sơ tài xế.')
        return redirect('frontend:profile')
    return page(request, 'auth.html', title='Đăng ký tài xế', form=form, register=True)


def scoped(request, model):
    rows = model.objects.all()
    if is_admin(request.user): return rows
    if model is Vehicle:
        now = timezone.now()
        return rows.filter(Q(driver_assignments__end_at__isnull=True) | Q(driver_assignments__end_at__gt=now), driver_assignments__driver__user=request.user, driver_assignments__start_at__lte=now).distinct()
    if model is DrivingSession: return rows.filter(assignment__driver__user=request.user)
    raise PermissionDenied


@login_required
def dashboard(request):
    vehicles, sessions = scoped(request, Vehicle), scoped(request, DrivingSession)
    stats = [('Phương tiện', vehicles.count()), ('Phiên đang lái', sessions.filter(status='STARTED').count()), ('Phiên đã kết thúc', sessions.filter(status='ENDED').count())]
    if is_admin(request.user): stats.append(('Hồ sơ chờ duyệt', DriverProfile.objects.filter(approval_status='PENDING').count()))
    return page(request, 'dashboard.html', title='Tổng quan', stats=stats, sessions=sessions.select_related('assignment__driver', 'assignment__vehicle').order_by('-started_at')[:10])


ENTITIES = {
    'violation-types': (ViolationType, ViolationTypeForm, 'Loại vi phạm', ['Mã', 'Tên loại', 'Mô tả'], ['code', 'name', 'description']),
    'vehicles': (Vehicle, VehicleForm, 'Phương tiện', ['Biển số', 'Loại xe', 'Hãng xe', 'Trạng thái'], ['license_plate', 'vehicle_type__name', 'brand']),
    'catalogs': (VehicleType, VehicleTypeForm, 'Loại xe', ['Tên loại', 'Nhóm', 'Mô tả'], ['name', 'description']),
    'assignments': (DriverVehicleAssignment, AssignmentForm, 'Phân công xe', ['Tài xế', 'Phương tiện', 'Bắt đầu', 'Kết thúc'], ['driver__full_name', 'vehicle__license_plate']),
    'devices': (Device, DeviceForm, 'Thiết bị', ['Mã', 'Tên', 'Xe', 'Trạng thái', 'Kết nối gần nhất'], ['device_code', 'name', 'vehicle__license_plate']),
    'drivers': (DriverProfile, None, 'Tài xế', ['Họ tên', 'Điện thoại', 'Hồ sơ', 'Tài khoản'], ['full_name', 'phone', 'user__username']),
    'sessions': (DrivingSession, None, 'Phiên lái xe', ['Mã', 'Tài xế', 'Xe', 'Bắt đầu', 'Kết thúc', 'Trạng thái'], ['assignment__driver__full_name', 'assignment__vehicle__license_plate']),
}


def display_date(value):
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M') if value else '—'


def cells(key, obj):
    if key == 'violation-types': return [obj.code, obj.name, obj.description]
    if key == 'vehicles': return [obj.license_plate, obj.vehicle_type.name, obj.brand, obj.get_status_display()]
    if key == 'catalogs': return [obj.name, obj.get_category_display(), obj.description]
    if key == 'assignments': return [obj.driver.full_name, obj.vehicle.license_plate, display_date(obj.start_at), display_date(obj.end_at)]
    if key == 'devices': return [obj.device_code, obj.name, obj.vehicle.license_plate, obj.get_status_display(), display_date(obj.last_seen_at)]
    if key == 'drivers': return [obj.full_name, obj.phone, obj.get_approval_status_display(), 'Hoạt động' if obj.user.is_active else 'Đã vô hiệu hóa']
    return [obj.pk, obj.assignment.driver.full_name, obj.assignment.vehicle.license_plate, display_date(obj.started_at), display_date(obj.ended_at), obj.get_status_display()]


@login_required
def listing(request, key):
    model, form, title, columns, fields = ENTITIES[key]
    rows = scoped(request, model) if key in ('vehicles', 'sessions') else model.objects.all() if is_admin(request.user) else None
    if rows is None: raise PermissionDenied
    query = request.GET.get('q', '').strip()
    if query:
        condition = Q()
        for field in fields: condition |= Q(**{field + '__icontains': query})
        rows = rows.filter(condition)
    state_field = 'approval_status' if key == 'drivers' else 'status'
    choices = model._meta.get_field(state_field).choices if key in ('vehicles', 'devices', 'drivers', 'sessions') else []
    state = request.GET.get('status', '')
    if state and state in dict(choices): rows = rows.filter(**{state_field: state})
    pagination = Paginator(rows.select_related().order_by('-pk'), 20).get_page(request.GET.get('page'))
    result = []
    for obj in pagination:
        url = reverse('frontend:driver-detail', args=[obj.pk]) if key == 'drivers' else reverse('frontend:edit', args=[key, obj.pk]) if form and is_admin(request.user) else ''
        result.append({'cells': cells(key, obj), 'url': url})
    return page(request, 'list.html', title=title, key=key, columns=columns, rows=result, pagination=pagination, query=query, choices=choices, selected_status=state, can_add=bool(form and is_admin(request.user)))


@admin_required
def edit(request, key, pk=None):
    if key not in ENTITIES or ENTITIES[key][1] is None: raise PermissionDenied
    model, form_class, title, *_ = ENTITIES[key]
    with transaction.atomic():
        obj = get_object_or_404(model.objects.select_for_update(), pk=pk) if pk else None
        form = form_class(request.POST or None, instance=obj)
        if request.method == 'POST' and form.is_valid():
            form.save()
            messages.success(request, 'Đã lưu dữ liệu.')
            return redirect('frontend:' + key)
    return page(request, 'form.html', title=('Cập nhật · ' if pk else 'Thêm · ') + title, form=form)


@login_required
def profile(request):
    if is_admin(request.user): raise PermissionDenied
    obj = DriverProfile.objects.filter(user=request.user).first()
    face = FaceProfile.objects.filter(driver=obj).first() if obj else None
    form = ProfileForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        try:
            save_profile(form, request.user)
            messages.success(request, 'Đã lưu hồ sơ.' + (' Đã tạo vector khuôn mặt và gửi chờ duyệt.' if form.cleaned_data.get('avatar') else ''))
            return redirect('frontend:profile')
        except MediaError as exc:
            form.add_error(None, str(exc))
    return page(request, 'form.html', title='Hồ sơ cá nhân', form=form, face=face, status=obj.get_approval_status_display() if obj else 'Chưa có hồ sơ', note='Ảnh đầu tiên là avatar. Có thể thêm 4 góc mặt. Ảnh được gửi đến dịch vụ nhận diện để tạo vector; avatar lưu trên Cloudinary. Đổi ảnh sẽ cần duyệt khuôn mặt lại. Mỗi ảnh tối đa 5 MB.')


@login_required
def license_page(request):
    if is_admin(request.user): raise PermissionDenied
    driver = DriverProfile.objects.filter(user=request.user).first()
    if not driver:
        messages.info(request, 'Vui lòng tạo hồ sơ trước khi thêm GPLX.')
        return redirect('frontend:profile')
    obj = DriverLicense.objects.filter(driver=driver).first()
    form = LicenseForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        try:
            save_license(form, driver)
            messages.success(request, 'Đã lưu GPLX và gửi chờ duyệt.')
            return redirect('frontend:license')
        except MediaError as exc:
            form.add_error(None, str(exc))
    return page(request, 'form.html', title='Giấy phép lái xe', form=form, license=obj, status=obj.get_status_display() if obj else 'Chưa có GPLX', note='Chọn ảnh JPG, PNG hoặc WebP từ máy, tối đa 5 MB/ảnh. Ảnh được lưu trên Cloudinary. Khi cập nhật có thể giữ ảnh cũ bằng cách không chọn ảnh mới.')


@admin_required
def driver_detail(request, pk):
    driver = get_object_or_404(DriverProfile.objects.select_related('user'), pk=pk)
    return page(request, 'driver_detail.html', title=driver.full_name, driver=driver, license=DriverLicense.objects.filter(driver=driver).first(), face=FaceProfile.objects.filter(driver=driver).first())


@admin_required
@require_POST
def driver_action(request, pk):
    with transaction.atomic():
        driver = get_object_or_404(DriverProfile.objects.select_for_update(), pk=pk)
        action = request.POST.get('action')
        if action == 'approve':
            driver.approval_status = 'APPROVED'
            driver.save(update_fields=['approval_status', 'updated_at'])
        elif action in ('enable', 'disable'):
            user = User.objects.select_for_update().get(pk=driver.user_id)
            if user.pk == request.user.pk or is_admin(user): raise PermissionDenied
            user.is_active = action == 'enable'
            user.save(update_fields=['is_active'])
        elif action in ('face-approve', 'face-reject'):
            face = get_object_or_404(FaceProfile.objects.select_for_update(), driver=driver)
            if not face.embedding:
                messages.error(request, 'Hồ sơ chưa có vector khuôn mặt.')
                return redirect('frontend:driver-detail', pk=pk)
            face.approval_status = 'APPROVED' if action == 'face-approve' else 'REJECTED'
            face.save(update_fields=['approval_status', 'updated_at'])
        elif action in ('license-approve', 'license-reject'):
            obj = get_object_or_404(DriverLicense.objects.select_for_update(), driver=driver)
            if action == 'license-approve' and obj.expiry_date <= timezone.localdate():
                messages.error(request, 'Không thể duyệt GPLX đã hết hạn.')
                return redirect('frontend:driver-detail', pk=pk)
            obj.status = 'ACTIVE' if action == 'license-approve' else 'REJECTED'
            obj.save(update_fields=['status', 'updated_at'])
        else: raise PermissionDenied
    messages.success(request, 'Đã cập nhật trạng thái.')
    return redirect('frontend:driver-detail', pk=pk)


@login_required
def deferred(request, title):
    return page(request, 'deferred.html', title=title)
