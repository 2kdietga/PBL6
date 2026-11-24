"""Durable, bounded per-driver uploads; network work never holds database locks."""
import logging
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import User, DriverProfile, FaceProfile, FaceProcessingJob, FaceProcessingImage
from .media_services import extract_embedding, upload_image, delete_images, MediaError

logger = logging.getLogger(__name__)
LEASE = timedelta(minutes=30)
MAX_ATTEMPTS = 3


def enqueue_face(profile, avatar, extras, clear_extras):
    # Caller holds the user/driver locks in its profile-save transaction.
    job, _ = FaceProcessingJob.objects.select_for_update().get_or_create(driver=profile)
    old_ids = job.uploaded_ids
    job.token = uuid.uuid4()
    job.status, job.attempts, job.error = 'QUEUED', 0, ''
    job.replace_avatar = bool(avatar)
    job.replace_extras = bool(extras or clear_extras)
    job.available_at, job.lease_until = timezone.now(), None
    job.uploaded_ids = old_ids
    job.save()
    job.images.all().delete()
    for image, is_avatar in ([(avatar, True)] if avatar else []) + [(item, False) for item in extras]:
        image.seek(0)
        FaceProcessingImage.objects.create(job=job, is_avatar=is_avatar, name=image.name[:255],
            content_type=image.content_type, data=image.read())
        image.seek(0)
    return job


def claim_job():
    now = timezone.now()
    eligible = Q(status='QUEUED', available_at__lte=now) | Q(status='RUNNING', lease_until__lte=now)
    # Compare-and-swap also works with SQLite and concurrent workers.
    for pk in FaceProcessingJob.objects.filter(eligible).order_by('available_at').values_list('pk', flat=True)[:20]:
        token = uuid.uuid4()
        with transaction.atomic():
            if not FaceProcessingJob.objects.filter(pk=pk).filter(eligible).update(
                    status='RUNNING', token=token, lease_until=now+LEASE, updated_at=now):
                continue
            job = FaceProcessingJob.objects.get(pk=pk)
            job.attempts += 1
            job.save(update_fields=['attempts', 'updated_at'])
            images = list(job.images.order_by('pk'))
        return job, images
    return None


class Superseded(Exception):
    pass


def still_owned(job, **changes):
    if not FaceProcessingJob.objects.filter(pk=job.pk, token=job.token, status='RUNNING').update(
            lease_until=timezone.now()+LEASE, updated_at=timezone.now(), **changes):
        raise Superseded


def process_next_face_job():
    claimed = claim_job()
    if claimed is None:
        return False
    job, images = claimed
    new_ids, results = [], []
    try:
        delete_images(job.uploaded_ids)
        still_owned(job, uploaded_ids=[])
        if job.attempts > MAX_ATTEMPTS:
            raise MediaError('Xử lý ảnh bị gián đoạn nhiều lần. Vui lòng thử lại.')
        for stored in images:
            image = SimpleUploadedFile(stored.name, bytes(stored.data), content_type=stored.content_type)
            vector = extract_embedding([image])
            still_owned(job)
            url, public_id = upload_image(image, 'faces')
            new_ids.append(public_id)
            still_owned(job, uploaded_ids=new_ids)
            results.append((stored.is_avatar, dict(url=url, public_id=public_id, embedding=vector)))
        with transaction.atomic():
            user_id = DriverProfile.objects.get(pk=job.driver_id).user_id
            User.objects.select_for_update().get(pk=user_id)
            driver = DriverProfile.objects.select_for_update().get(pk=job.driver_id)
            current = FaceProcessingJob.objects.select_for_update().get(pk=job.pk)
            if current.token != job.token or current.status != 'RUNNING':
                raise Superseded
            face = FaceProfile.objects.select_for_update().filter(driver=driver).first()
            old_ids = []
            if face is None:
                face = FaceProfile(driver=driver)
            if job.replace_avatar:
                avatar = next(value for is_avatar, value in results if is_avatar)
                old_ids.append(face.cloudinary_public_id)
                face.face_image_url, face.cloudinary_public_id, face.embedding = avatar['url'], avatar['public_id'], avatar['embedding']
            if not face.face_image_url:
                raise MediaError('Cần tải lên ảnh đại diện trước khi xử lý ảnh bổ sung.')
            if job.replace_extras:
                old_ids.extend(item['public_id'] for item in face.extra_images)
                face.extra_images = [value for is_avatar, value in results if not is_avatar]
            face.approval_status = 'PENDING'
            face.save()
            current.status, current.error, current.uploaded_ids = 'DONE', '', []
            current.lease_until = None
            current.save()
            current.images.all().delete()
            transaction.on_commit(lambda: delete_images(old_ids))
    except Superseded:
        delete_images(new_ids)
    except Exception as exc:
        delete_images(new_ids)
        if not isinstance(exc, MediaError):
            logger.exception('Face processing failed for job %s', job.pk)
        message = str(exc) if isinstance(exc, MediaError) else 'Chưa xử lý được ảnh. Vui lòng thử lại sau.'
        FaceProcessingJob.objects.filter(pk=job.pk, token=job.token, status='RUNNING').update(
            status='FAILED' if job.attempts >= MAX_ATTEMPTS else 'QUEUED', error=message,
            available_at=timezone.now()+timedelta(seconds=30*job.attempts), lease_until=None,
            uploaded_ids=[], updated_at=timezone.now())
    return True


@transaction.atomic
def retry_face_job(driver_id, token):
    driver = DriverProfile.objects.get(pk=driver_id)
    User.objects.select_for_update().get(pk=driver.user_id)
    DriverProfile.objects.select_for_update().get(pk=driver_id)
    job = FaceProcessingJob.objects.select_for_update().get(driver_id=driver_id)
    if job.status != 'FAILED' or str(job.token) != str(token):
        raise ValidationError('Yêu cầu xử lý ảnh đã thay đổi. Vui lòng tải lại trang.')
    job.status, job.attempts, job.error = 'QUEUED', 0, ''
    job.available_at, job.lease_until = timezone.now(), None
    job.token = uuid.uuid4()
    job.save()
