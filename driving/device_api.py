from functools import wraps
from hashlib import sha256
from uuid import uuid4, UUID

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import (
    RequestDataTooBig,
    TooManyFieldsSent,
    TooManyFilesSent,
)
from django.http import JsonResponse
from django.http.multipartparser import MultiPartParserError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from vehicles.models import Device

from .device_protocol import (
    DeviceAPIError,
    FrameUploadHandler,
)

from .face_verification import (
    extract_single,
    matching_config,
    match_driver,
    validate_jpeg,
)


# ==========================================================
# RESPONSE
# ==========================================================

def reply(
    request,
    code,
    message,
    *,
    status=200,
    action='NONE',
    data=None,
    retry_after=None,
):
    response = JsonResponse(
        {
            'ok': status < 400,
            'code': code,
            'message': message,
            'request_id': request.device_request_id,
            'server_time': timezone.now().isoformat(),
            'action': action,
            'retry_after_seconds': retry_after,
            'data': data,
        },
        status=status,
        json_dumps_params={'ensure_ascii': False},
    )

    response['Cache-Control'] = 'no-store'

    if retry_after is not None:
        response['Retry-After'] = str(retry_after)

    if status == 401:
        response['WWW-Authenticate'] = 'Bearer'

    return response


# ==========================================================
# KIỂM TRA DEVICE
# ==========================================================

def check_device(device):

    if device.status == 'MAINTENANCE':
        raise DeviceAPIError(
            'DEVICE_MAINTENANCE',
            'Thiết bị đang bảo trì.',
            403,
            'CONTACT_ADMIN',
        )

    if device.vehicle.status != 'ACTIVE':
        raise DeviceAPIError(
            'VEHICLE_INACTIVE',
            'Phương tiện không hoạt động.',
            403,
            'CONTACT_ADMIN',
        )


# ==========================================================
# DEVICE AUTHENTICATION
# ==========================================================

def device_endpoint(method):

    def decorate(view):

        @csrf_exempt
        @wraps(view)
        def wrapped(request):

            request.device_request_id = str(uuid4())

            try:

                # ==================================================
                # 1. HTTP METHOD
                # ==================================================

                if request.method != method:

                    result = reply(
                        request,
                        'METHOD_NOT_ALLOWED',
                        'Phương thức HTTP không hợp lệ.',
                        status=405,
                        action='FIX_REQUEST',
                    )

                    result['Allow'] = method

                    return result

                # ==================================================
                # 2. HTTPS
                # Cho phép HTTP khi DEVICE_API_REQUIRE_HTTPS=false.
                # ==================================================

                if settings.DEVICE_API_REQUIRE_HTTPS and not request.is_secure():
                    raise DeviceAPIError(
                        'HTTPS_REQUIRED',
                        'Thiết bị phải kết nối bằng HTTPS.',
                        400,
                    )

                # ==================================================
                # 3. REQUEST ID
                # ==================================================

                request_id = request.headers.get(
                    'X-Request-ID'
                )

                if request_id:

                    try:

                        request.device_request_id = str(
                            UUID(request_id)
                        )

                    except ValueError:

                        raise DeviceAPIError(
                            'INVALID_REQUEST_ID',
                            'X-Request-ID phải là UUID.',
                        )

                # ==================================================
                # 4. AUTHORIZATION
                # ==================================================

                authorization = request.headers.get(
                    'Authorization',
                    '',
                )

                code = request.headers.get(
                    'X-Device-Code',
                    '',
                )

                device = None

                # ==================================================
                # 5. KIỂM TRA BEARER API KEY
                # ==================================================

                if (
                    authorization.startswith('Bearer ')
                    and 7 < len(authorization) <= 256
                    and len(code) <= 100
                ):

                    secret = authorization[7:]

                    devices = Device.objects.select_related(
                        'vehicle'
                    )

                    # --------------------------------------------------
                    # Tìm Device bằng SHA256 API key
                    # --------------------------------------------------

                    device = devices.filter(
                        api_key_digest=sha256(
                            secret.encode()
                        ).hexdigest()
                    ).first()

                    # --------------------------------------------------
                    # Fallback key cũ
                    # --------------------------------------------------

                    if device is None and code:

                        device = devices.filter(
                            device_code=code,
                            api_key_digest__isnull=True,
                        ).first()

                # ==================================================
                # 6. XÁC THỰC DEVICE
                # ==================================================

                if (
                    not device
                    or not device.api_key_hash
                    or (
                        code
                        and code != device.device_code
                    )
                    or not check_password(
                        authorization[7:],
                        device.api_key_hash,
                    )
                ):

                    raise DeviceAPIError(
                        'DEVICE_UNAUTHORIZED',
                        'Mã thiết bị hoặc khóa API không hợp lệ.',
                        401,
                        'CONTACT_ADMIN',
                    )

                # ==================================================
                # 7. KIỂM TRA DEVICE / VEHICLE
                # ==================================================

                check_device(device)

                # ==================================================
                # 8. LƯU DEVICE VÀO REQUEST
                # ==================================================

                request.device = device

                Device.objects.filter(
                    pk=device.pk
                ).update(
                    last_seen_at=timezone.now()
                )

                # ==================================================
                # 9. GỌI VIEW
                # ==================================================

                return view(request)

            except DeviceAPIError as exc:

                return reply(
                    request,
                    exc.code,
                    exc.message,
                    status=exc.status,
                    action=exc.action,
                    retry_after=exc.retry_after,
                )

            except (
                MultiPartParserError,
                RequestDataTooBig,
                TooManyFieldsSent,
                TooManyFilesSent,
            ):

                return reply(
                    request,
                    'INVALID_MULTIPART',
                    'Nội dung multipart không hợp lệ hoặc quá lớn.',
                    status=400,
                    action='FIX_REQUEST',
                )

        return wrapped

    return decorate


# ==========================================================
# GET /api/v1/device/context/
# ==========================================================

@device_endpoint('GET')
def context(request):

    device = request.device

    threshold, margin = matching_config()

    return reply(
        request,
        'DEVICE_READY',
        'Thiết bị sẵn sàng.',
        data={
            'device_code': device.device_code,

            'vehicle': {
                'id': device.vehicle_id,
                'license_plate': device.vehicle.license_plate,
            },

            'frame': {
                'field': 'frame',
                'format': 'JPEG',
                'quality': 85,
                'full_frame': True,
                'max_width': 1280,
                'max_height': 720,
                'max_bytes': settings.DEVICE_FRAME_MAX_BYTES,
            },

            'max_frame_age_seconds':
                settings.DEVICE_FRAME_MAX_AGE_SECONDS,

            'matching': {
                'metric': 'cosine_similarity',
                'threshold': threshold,
                'ambiguity_margin': margin,
            },
        },
    )


# ==========================================================
# POST /api/v1/device/face-verifications/
#
# FLOW:
#
# Pi
#  ↓
# Gửi ảnh
#  ↓
# Device authentication
#  ↓
# Validate JPEG
#  ↓
# Extract face embedding
#  ↓
# Tìm tài xế trong database
#  ↓
# Nếu đúng → trả thông tin tài xế
#
# KHÔNG:
# - eligible_assignments
# - kiểm tra assignment
# - yêu cầu tài xế thuộc xe
# - kiểm tra tài xế được phân công
# ==========================================================

@device_endpoint('POST')
def verify_face(request):

    # ==================================================
    # 1. Kiểm tra multipart/form-data
    # ==================================================

    if request.content_type != 'multipart/form-data':

        raise DeviceAPIError(
            'MULTIPART_REQUIRED',
            'Gửi ảnh bằng multipart/form-data.',
            415,
            'FIX_REQUEST',
        )

    # ==================================================
    # 2. Kiểm tra Content-Length
    # ==================================================

    try:

        content_length = int(
            request.META.get(
                'CONTENT_LENGTH',
                '',
            )
        )

    except (ValueError, TypeError):

        raise DeviceAPIError(
            'CONTENT_LENGTH_REQUIRED',
            'Cần Content-Length cho request ảnh.',
            411,
            'FIX_REQUEST',
        )

    if content_length <= 0:

        raise DeviceAPIError(
            'CONTENT_LENGTH_REQUIRED',
            'Cần Content-Length cho request ảnh.',
            411,
            'FIX_REQUEST',
        )

    if content_length > settings.DEVICE_REQUEST_MAX_BYTES:

        raise DeviceAPIError(
            'FRAME_TOO_LARGE',
            'Request ảnh vượt quá giới hạn cho phép.',
            413,
            'FIX_REQUEST',
        )

    # ==================================================
    # 3. Upload handler
    # ==================================================

    request.upload_handlers = [
        FrameUploadHandler(
            request,
            settings.DEVICE_FRAME_MAX_BYTES,
        )
    ]

    try:

        return verify_uploaded_frame(request)

    finally:

        for handler in request.upload_handlers:

            if hasattr(handler, 'buffer'):

                handler.buffer.close()


# ==========================================================
# XỬ LÝ FRAME
# ==========================================================

def verify_uploaded_frame(request):

    # ==================================================
    # 1. Kiểm tra captured_at
    # ==================================================

    if (
        set(request.POST) != {'captured_at'}
        or len(
            request.POST.getlist(
                'captured_at'
            )
        ) != 1
    ):

        raise DeviceAPIError(
            'INVALID_FIELDS',
            'Chỉ gửi captured_at và một file frame.',
            400,
            'FIX_REQUEST',
        )

    raw_time = request.POST[
        'captured_at'
    ]

    try:

        captured_at = (
            parse_datetime(raw_time)
            if len(raw_time) <= 40
            else None
        )

    except ValueError:

        captured_at = None

    if (
        captured_at is None
        or timezone.is_naive(captured_at)
    ):

        raise DeviceAPIError(
            'INVALID_CAPTURE_TIME',
            'captured_at phải là ISO 8601 có múi giờ.',
            400,
            'FIX_REQUEST',
        )

    # ==================================================
    # Bật bằng DEVICE_API_CHECK_FRAME_AGE=true khi cần kiểm tra ảnh mới.
    # ==================================================

    if settings.DEVICE_API_CHECK_FRAME_AGE:
        age = (
            timezone.now() - captured_at
        ).total_seconds()

        if (
            age < -5
            or age > settings.DEVICE_FRAME_MAX_AGE_SECONDS
        ):
            raise DeviceAPIError(
                'STALE_FRAME',
                'Ảnh đã cũ hoặc đồng hồ Pi sai.',
                422,
                'CAPTURE_AGAIN',
            )

    # ==================================================
    # 2. Kiểm tra frame
    # ==================================================

    if (
        set(request.FILES) != {'frame'}
        or len(
            request.FILES.getlist(
                'frame'
            )
        ) != 1
    ):

        raise DeviceAPIError(
            'INVALID_FRAME',
            'Chỉ gửi một ảnh JPEG trong trường frame.',
            400,
            'FIX_REQUEST',
        )

    frame = request.FILES[
        'frame'
    ]

    data = frame.read()

    # ==================================================
    # 3. Validate JPEG
    # ==================================================

    validate_jpeg(data)

    # ==================================================
    # 4. Extract face embedding
    # ==================================================

    vector = extract_single(
        data
    )

    # HF có thể phản hồi chậm; đọc lại thiết bị trước khi trả danh tính.
    device = Device.objects.select_related('vehicle').filter(pk=request.device.pk).first()
    if (
        device is None
        or device.api_key_hash != request.device.api_key_hash
        or device.api_key_digest != request.device.api_key_digest
    ):
        raise DeviceAPIError(
            'DEVICE_UNAUTHORIZED', 'Khóa API đã bị thay đổi hoặc thu hồi.',
            401, 'CONTACT_ADMIN',
        )
    if device.vehicle_id != request.device.vehicle_id:
        raise DeviceAPIError(
            'DEVICE_ASSIGNMENT_CHANGED', 'Thiết bị đã được chuyển sang xe khác.',
            409, 'RETRY_LATER', 1,
        )
    check_device(device)

    # ==================================================
    # 5. FACE MATCHING
    #
    # TÌM TRONG TOÀN BỘ TÀI XẾ
    #
    # KHÔNG dùng:
    # eligible_assignments()
    # ==================================================

    threshold, margin = matching_config()

    (
        code,
        message,
        driver,
        score,
    ) = match_driver(
        vector,
        threshold,
        margin,
    )

    # ==================================================
    # 6. Không nhận diện được
    # ==================================================

    if driver is None:

        return reply(
            request,
            code,
            message,
            status=200,
            action='CAPTURE_AGAIN',
            data={
                'verified': False,

                'similarity': round(
                    score,
                    6,
                ),

                'threshold': threshold,

                'driver': None,

                'vehicle_id':
                    request.device.vehicle_id,

                'device_code':
                    request.device.device_code,
            },
        )

    # ==================================================
    # 7. Nhận diện thành công
    # ==================================================

    # ==================================================
    # 8. Trả thông tin tài xế về Pi
    # ==================================================

    return reply(
        request,
        'DRIVER_VERIFIED',
        'Xác thực tài xế thành công.',
        status=200,
        action='NONE',
        data={
            'verified': True,

            'similarity': round(
                score,
                6,
            ),

            'threshold': threshold,

            'driver': {
                'id': driver.pk,
                'full_name': driver.full_name,
            },

            'vehicle_id':
                request.device.vehicle_id,

            'device_code':
                request.device.device_code,
        },
    )
