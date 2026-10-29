"""Authenticated Pi events: bounded JPEG upload and retry-safe pending violations."""
import math
import logging
from io import BytesIO
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadhandler import FileUploadHandler
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.media_services import MediaError, upload_image, delete_images
from driving.device_api import device_endpoint, reply
from driving.device_protocol import DeviceAPIError
from driving.models import DrivingSession
from driving.session_services import locked_device
from .models import Evidence, Violation, ViolationType

MAX_IMAGE_BYTES = 2 * 1024 * 1024
FIELDS = {'event_id', 'session_id', 'violation_code', 'detected_at', 'confidence'}
logger = logging.getLogger(__name__)


class EvidenceUploadHandler(FileUploadHandler):
    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        if hasattr(self, 'buffer') or self.field_name != 'image':
            raise DeviceAPIError('INVALID_PAYLOAD', 'Chỉ gửi một file image.')
        if self.content_type != 'image/jpeg':
            raise DeviceAPIError('INVALID_IMAGE', 'Ảnh phải là JPEG.', 415)
        self.buffer = BytesIO()

    def receive_data_chunk(self, raw_data, start):
        if self.buffer.tell() + len(raw_data) > MAX_IMAGE_BYTES:
            raise DeviceAPIError('IMAGE_TOO_LARGE', 'Ảnh vượt quá 2 MiB.', 413)
        self.buffer.write(raw_data)
        return None

    def file_complete(self, file_size):
        self.buffer.seek(0)
        return InMemoryUploadedFile(self.buffer, 'image', 'evidence.jpg', 'image/jpeg', file_size, None)


def validate_image(upload):
    try:
        with Image.open(upload) as image:
            if image.format != 'JPEG' or image.width > 1920 or image.height > 1080:
                raise DeviceAPIError('INVALID_IMAGE', 'Cần JPEG tối đa 1920×1080.', 415)
            image.verify()
        upload.seek(0)
        with Image.open(upload) as image:
            image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DeviceAPIError('INVALID_IMAGE', 'Ảnh JPEG bị hỏng.', 415) from exc
    finally:
        upload.seek(0)


def event_response(request, violation, *, created=False):
    return reply(request, 'VIOLATION_RECORDED' if created else 'EVENT_ALREADY_RECORDED',
        'Đã ghi nhận vi phạm, chờ quản trị viên xác nhận.' if created else 'Sự kiện đã được ghi nhận.',
        status=201 if created else 200,
        data={'violation_id': violation.pk, 'status': violation.status})


def check_session(device, session_id, detected_at, *, lock=False):
    rows = DrivingSession.objects
    if lock:
        rows = rows.select_for_update()
    session = rows.filter(pk=session_id, source_device=device, vehicle_id=device.vehicle_id).first()
    if session is None:
        raise DeviceAPIError('SESSION_NOT_FOUND', 'Không tìm thấy phiên lái của thiết bị.', 404)
    age = (timezone.now() - detected_at).total_seconds()
    if (age < -5 or age > 24 * 3600 or detected_at < session.started_at
            or (session.ended_at is not None and detected_at > session.ended_at)):
        raise DeviceAPIError('INVALID_EVENT_TIME', 'Thời điểm vi phạm phải nằm trong phiên và không cũ quá 24 giờ.', 422)
    return session


def process_event(request):
    if (set(request.POST) != FIELDS or any(len(request.POST.getlist(key)) != 1 for key in FIELDS)
            or set(request.FILES) != {'image'} or len(request.FILES.getlist('image')) != 1):
        raise DeviceAPIError('INVALID_PAYLOAD', 'Gửi event_id, session_id, violation_code, detected_at, confidence và một image.')
    try:
        event_id = UUID(request.POST['event_id'])
        raw_session = request.POST['session_id']
        if not raw_session.isascii() or not raw_session.isdecimal() or len(raw_session) > 18:
            raise ValueError()
        session_id = int(raw_session)
        confidence = float(request.POST['confidence'])
        raw_time = request.POST['detected_at']
        detected_at = parse_datetime(raw_time) if len(raw_time) <= 40 else None
        if (session_id <= 0 or not math.isfinite(confidence) or not 0 <= confidence <= 1
                or detected_at is None or timezone.is_naive(detected_at)):
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise DeviceAPIError('INVALID_PAYLOAD', 'UUID, session_id, thời gian có múi giờ hoặc confidence không hợp lệ.')
    # A successful event ID is immutable; retries return its existing result, even after review.
    existing = Violation.objects.filter(source_device=request.device, event_id=event_id).first()
    if existing:
        return event_response(request, existing)
    session = check_session(request.device, session_id, detected_at)
    kind = ViolationType.objects.filter(code=request.POST['violation_code']).first()
    if kind is None:
        raise DeviceAPIError('UNKNOWN_VIOLATION_CODE', 'Mã loại vi phạm chưa được khai báo.', 422)
    image = request.FILES['image']
    validate_image(image)
    try:
        url, public_id = upload_image(image, 'violations')
    except MediaError as exc:
        raise DeviceAPIError('STORAGE_UNAVAILABLE', 'Không lưu được ảnh bằng chứng. Hãy gửi lại.', 503, 'RETRY_LATER', 5) from exc
    saved = False
    try:
        with transaction.atomic():
            # Serialize requests from one device after upload; never hold locks during network I/O.
            device = locked_device(request.device, require_ready=False)
            existing = Violation.objects.filter(source_device=device, event_id=event_id).first()
            if existing:
                result = event_response(request, existing)
            else:
                session = check_session(device, session_id, detected_at, lock=True)
                violation = Violation.objects.create(session=session, source_device=device,
                    event_id=event_id, confidence=confidence, violation_type=kind,
                    detected_at=detected_at, severity='MEDIUM', status='PENDING')
                Evidence.objects.create(violation=violation, type='IMAGE', url=url,
                    cloudinary_public_id=public_id, captured_at=detected_at)
                result = event_response(request, violation, created=True)
        saved = existing is None
        return result
    finally:
        if not saved:
            delete_images([public_id])


@device_endpoint('POST', require_ready=False)
def record(request):
    # Accept delayed evidence even when the device/vehicle has since been disabled.
    if request.content_type != 'multipart/form-data':
        raise DeviceAPIError('MULTIPART_REQUIRED', 'Gửi multipart/form-data kèm ảnh.', 415)
    try:
        length = int(request.META.get('CONTENT_LENGTH', ''))
    except (ValueError, TypeError):
        length = 0
    if length <= 0:
        raise DeviceAPIError('CONTENT_LENGTH_REQUIRED', 'Cần Content-Length.', 411)
    if length > MAX_IMAGE_BYTES + 16 * 1024:
        raise DeviceAPIError('IMAGE_TOO_LARGE', 'Request vượt quá giới hạn cho phép.', 413)
    handler = EvidenceUploadHandler(request)
    request.upload_handlers = [handler]
    try:
        return process_event(request)
    except DatabaseError as exc:
        logger.error('Could not persist device violation; request_id=%s', request.device_request_id)
        raise DeviceAPIError('DATABASE_UNAVAILABLE', 'Chưa lưu được vi phạm. Hãy gửi lại cùng event_id.',
                             503, 'RETRY_LATER', 5) from exc
    finally:
        if hasattr(handler, 'buffer'):
            handler.buffer.close()
