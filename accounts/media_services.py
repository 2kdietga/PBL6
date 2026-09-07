"""Cloudinary storage and the embedding contract from mẫu.ipynb."""
import logging
import math
from uuid import uuid4

import cloudinary
import cloudinary.uploader
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MediaError(Exception):
    pass


def extract_embedding(images):
    if not 1 <= len(images) <= 5:
        raise MediaError('Vui lòng chọn từ 1 đến 5 ảnh khuôn mặt.')
    files = []
    for image in images:
        image.seek(0)
        files.append(('files', (image.name, image, image.content_type)))
    try:
        response = requests.post(settings.FACE_EMBEDDING_URL, files=files, timeout=(10, 90))
        if response.status_code != 200:
            logger.warning(
                'Face embedding service returned HTTP %s from %s',
                response.status_code,
                settings.FACE_EMBEDDING_URL,
            )
            if response.status_code in (502, 503, 504):
                raise MediaError(
                    f'Dịch vụ nhận diện đang tạm ngừng (HTTP {response.status_code}). '
                    'Ảnh và hồ sơ chưa được lưu; vui lòng thử lại khi dịch vụ hoạt động.'
                )
            if response.status_code in (404, 405):
                raise MediaError(
                    f'Đường dẫn dịch vụ nhận diện không hợp lệ (HTTP {response.status_code}). '
                    'Vui lòng kiểm tra FACE_EMBEDDING_URL.'
                )
            if response.status_code in (400, 409, 415, 422):
                raise MediaError(
                    f'Dịch vụ không nhận diện được ảnh (HTTP {response.status_code}). '
                    'Hãy chọn ảnh rõ mặt, đúng định dạng và thử lại.'
                )
            raise MediaError(
                f'Dịch vụ nhận diện trả về lỗi HTTP {response.status_code}. '
                'Ảnh và hồ sơ chưa được lưu.'
            )
        vector = response.json().get('vector')
        if not isinstance(vector, list) or not 1 <= len(vector) <= 4096:
            raise ValueError('Invalid vector')
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector):
            raise ValueError('Invalid vector values')
        if not any(x != 0 for x in vector):
            raise ValueError('Zero vector')
        return vector
    except requests.RequestException as exc:
        raise MediaError('Không kết nối được dịch vụ nhận diện. Vui lòng thử lại sau.') from exc
    except (ValueError, AttributeError) as exc:
        raise MediaError('Dịch vụ nhận diện trả về vector không hợp lệ. Chưa lưu thay đổi.') from exc
    finally:
        for image in images:
            image.seek(0)


def cloud_config():
    values = settings.CLOUDINARY
    if not all(values.values()):
        raise MediaError('Chưa cấu hình đầy đủ Cloudinary trên máy chủ.')
    return values


def upload_image(image, folder):
    image.seek(0)
    try:
        result = cloudinary.uploader.upload(
            image, folder=f'savelife/{folder}', public_id=uuid4().hex,
            resource_type='image', overwrite=False, timeout=60,
            **cloud_config(),
        )
        if not result.get('secure_url', '').startswith('https://') or not result.get('public_id'):
            raise MediaError('Cloudinary chưa trả về thông tin ảnh hợp lệ.')
        return result['secure_url'], result['public_id']
    except MediaError:
        raise
    except Exception as exc:
        raise MediaError('Không tải được ảnh lên Cloudinary. Vui lòng thử lại.') from exc


def delete_images(public_ids):
    for public_id in public_ids:
        if public_id:
            try:
                cloudinary.uploader.destroy(public_id, resource_type='image', invalidate=True, timeout=30, **cloud_config())
            except Exception:
                # Do not roll back saved records because an old asset cannot be removed.
                logger.warning('Cloudinary image cleanup failed; retry required for %s', public_id)
