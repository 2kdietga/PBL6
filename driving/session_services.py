"""Small device session lifecycle; no network calls while holding database locks."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User, DriverProfile, DriverLicense, FaceProfile
from vehicles.models import Device, Vehicle, DriverVehicleAssignment
from vehicles.licensing import assignment_license_error
from .device_protocol import DeviceAPIError
from .models import DrivingSession


def deny_driver(reason, message):
    error = DeviceAPIError('DRIVER_NOT_ELIGIBLE', message, 403, 'CONTACT_ADMIN')
    error.reason_code = reason
    raise error


def session_data(session):
    return {
        'session_id': session.pk,
        'status': session.status,
        'vehicle_id': session.vehicle_id,
        'driver': {'id': session.assignment.driver_id, 'full_name': session.assignment.driver.full_name},
        'started_at': session.started_at.isoformat(),
        'ended_at': session.ended_at.isoformat() if session.ended_at else None,
    }


def locked_device(original, *, require_ready):
    from .device_api import check_device
    device = Device.objects.select_for_update().filter(pk=original.pk).first()
    if (device is None or device.api_key_hash != original.api_key_hash
            or device.api_key_digest != original.api_key_digest):
        raise DeviceAPIError('DEVICE_UNAUTHORIZED', 'Khóa API đã thay đổi hoặc bị thu hồi.', 401, 'CONTACT_ADMIN')
    if device.vehicle_id != original.vehicle_id:
        raise DeviceAPIError('DEVICE_ASSIGNMENT_CHANGED', 'Thiết bị đã chuyển xe. Hãy đọc lại context.', 409, 'RETRY_LATER', 1)
    device.vehicle = Vehicle.objects.select_for_update().get(pk=device.vehicle_id)
    if require_ready:
        check_device(device)
    return device


@transaction.atomic
def start_session(original_device, matched_driver):
    # Same order as profile approval/upload: user -> driver -> license -> face.
    user = User.objects.select_for_update().filter(pk=matched_driver.user_id).first()
    driver = DriverProfile.objects.select_for_update().filter(pk=matched_driver.pk).first()
    if driver is None or user is None:
        raise DeviceAPIError('DRIVER_NOT_ELIGIBLE', 'Hồ sơ tài xế không còn tồn tại.', 403, 'CONTACT_ADMIN')
    license = DriverLicense.objects.select_for_update().filter(driver=driver).first()
    face = FaceProfile.objects.select_for_update().filter(driver=driver).first()
    if not user.is_active:
        deny_driver('DRIVER_ACCOUNT_INACTIVE', 'Tài khoản tài xế đã bị khóa.')
    if driver.approval_status != 'APPROVED':
        deny_driver('DRIVER_PROFILE_NOT_APPROVED', 'Hồ sơ tài xế chưa được duyệt.')
    if not license:
        deny_driver('LICENSE_MISSING', 'Tài xế chưa có GPLX.')
    if license.is_expired:
        deny_driver('LICENSE_EXPIRED', 'GPLX đã hết hạn.')
    if license.status != 'ACTIVE':
        deny_driver('LICENSE_NOT_ACTIVE', 'GPLX chưa được duyệt hoặc không hoạt động.')
    if license.issued_date > timezone.localdate():
        deny_driver('LICENSE_ISSUE_DATE_INVALID', 'Ngày cấp GPLX nằm trong tương lai.')
    if not face or face.approval_status != 'APPROVED':
        deny_driver('FACE_PROFILE_NOT_APPROVED', 'Hồ sơ khuôn mặt chưa được duyệt.')
    if face.embedding != matched_driver.face_profile.embedding:
        deny_driver('FACE_PROFILE_CHANGED', 'Dữ liệu khuôn mặt đã thay đổi. Cần nhận diện lại.')
    if not driver.can_approve:
        deny_driver('DRIVER_PROFILE_INCOMPLETE', 'Hồ sơ tài xế còn thiếu thông tin bắt buộc.')
    device = locked_device(original_device, require_ready=True)
    if DrivingSession.objects.filter(vehicle=device.vehicle, status='STARTED').exists():
        raise DeviceAPIError('SESSION_ALREADY_ACTIVE', 'Xe đã có phiên lái. Hãy đọc lại context.', 409)
    error = assignment_license_error(driver, device.vehicle)
    if error:
        reason = ('VEHICLE_SPECIFICATIONS_MISSING' if device.vehicle.required_license_class is None
                  else 'LICENSE_STANDARD_UNSUPPORTED' if license.license_standard != 'VN_2025'
                  else 'LICENSE_CLASS_INCOMPATIBLE')
        deny_driver(reason, error)
    now = timezone.now()
    assignments = list(DriverVehicleAssignment.objects.select_for_update().filter(
        driver=driver, vehicle=device.vehicle, start_at__lte=now,
    ).filter(Q(end_at__isnull=True) | Q(end_at__gt=now)).order_by('pk')[:2])
    if not assignments:
        raise DeviceAPIError('NO_ACTIVE_ASSIGNMENT', 'Tài xế chưa được phân công xe tại thời điểm này.', 403, 'CONTACT_ADMIN')
    if len(assignments) != 1:
        raise DeviceAPIError('ASSIGNMENT_AMBIGUOUS', 'Có nhiều phân công trùng thời gian. Cần admin kiểm tra.', 409, 'CONTACT_ADMIN')
    return DrivingSession.objects.create(assignment=assignments[0], source_device=device, started_at=now)


@transaction.atomic
def end_session(original_device, pk):
    device = locked_device(original_device, require_ready=False)
    # Lock assignment before session, matching DrivingSession.save's lock order.
    assignment_id = DrivingSession.objects.filter(pk=pk, source_device=device).values_list('assignment_id', flat=True).first()
    if assignment_id is None:
        raise DeviceAPIError('SESSION_NOT_FOUND', 'Không tìm thấy phiên lái của thiết bị.', 404)
    DriverVehicleAssignment.objects.select_for_update().get(pk=assignment_id)
    session = DrivingSession.objects.select_for_update().get(pk=pk, source_device=device)
    if session.status == 'STARTED':
        session.status = 'ENDED'
        session.ended_at = max(timezone.now(), session.started_at)
        session.save(update_fields=['status', 'ended_at', 'updated_at'])
    return session
