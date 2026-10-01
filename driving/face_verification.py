
import math

from io import BytesIO
from urllib.parse import urlsplit

import requests
from PIL import Image, UnidentifiedImageError

from django.conf import settings

from .device_protocol import DeviceAPIError

from accounts.models import DriverProfile


# ==========================================================
# NORMALIZE VECTOR
# ==========================================================

def normalized_vector(vector):

    if not isinstance(vector, list) or len(vector) != 512:
        raise ValueError('Expected 512 dimensions')

    if any(
        isinstance(x, bool)
        or not isinstance(x, (float, int))
        or not math.isfinite(x)
        for x in vector
    ):
        raise ValueError('Expected finite numeric vector')

    # Scale first to avoid overflow
    scale = max(abs(x) for x in vector)

    if not scale:
        raise ValueError('Zero vector')

    scaled = [x / scale for x in vector]

    norm = math.sqrt(
        math.fsum(x * x for x in scaled)
    )

    return [
        x / norm
        for x in scaled
    ]


# ==========================================================
# COSINE SIMILARITY
# ==========================================================

def cosine_similarity(left, right):

    return max(
        -1.0,
        min(
            1.0,
            math.fsum(
                a * b
                for a, b in zip(
                    normalized_vector(left),
                    normalized_vector(right),
                )
            ),
        ),
    )


# ==========================================================
# MATCHING CONFIG
# ==========================================================

def matching_config():

    try:

        threshold = float(
            settings.FACE_COSINE_THRESHOLD
        )

        margin = float(
            settings.FACE_COSINE_MARGIN
        )

        if (
            not math.isfinite(threshold)
            or not 0 < threshold <= 1
        ):
            raise ValueError()

        if (
            not math.isfinite(margin)
            or not 0 <= margin <= 2
        ):
            raise ValueError()

    except (ValueError, TypeError):

        raise DeviceAPIError(
            'MATCHING_NOT_CONFIGURED',
            'Máy chủ chưa cấu hình ngưỡng xác thực.',
            503,
            'CONTACT_ADMIN',
        )

    return threshold, margin


# ==========================================================
# VALIDATE JPEG
# ==========================================================

def validate_jpeg(data):

    try:

        with Image.open(BytesIO(data)) as image:

            if image.format != 'JPEG':

                raise DeviceAPIError(
                    'UNSUPPORTED_IMAGE',
                    'Chỉ chấp nhận ảnh JPEG đã encode.',
                    415,
                )

            if (
                image.width > 1280
                or image.height > 720
            ):

                raise DeviceAPIError(
                    'INVALID_RESOLUTION',
                    'Ảnh toàn cảnh phải có kích thước tối đa 1280×720.',
                )

            image.verify()

        # Decode again to detect truncated/corrupt data
        with Image.open(BytesIO(data)) as image:
            image.load()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:

        raise DeviceAPIError(
            'INVALID_JPEG',
            'Ảnh JPEG bị hỏng. Vui lòng chụp lại.',
            400,
            'CAPTURE_AGAIN',
        ) from exc


# ==========================================================
# EXTRACT FACE EMBEDDING
# ==========================================================

def extract_single(data):

    url = settings.FACE_SINGLE_EMBEDDING_URL

    parsed_url = urlsplit(url)

    if (
        parsed_url.scheme != 'https'
        or not parsed_url.netloc
    ):

        raise DeviceAPIError(
            'HF_NOT_CONFIGURED',
            'Chưa cấu hình dịch vụ nhận diện HTTPS.',
            503,
            'CONTACT_ADMIN',
        )

    headers = (
        {
            'Authorization':
                f'Bearer {settings.HF_API_TOKEN}'
        }
        if settings.HF_API_TOKEN
        else {}
    )

    try:

        with requests.post(
            url,
            files={
                settings.FACE_SINGLE_FILE_FIELD:
                    (
                        'frame.jpg',
                        data,
                        'image/jpeg',
                    )
            },
            headers=headers,
            timeout=(5, 30),
            allow_redirects=False,
        ) as response:

            if response.status_code in (
                400,
                422,
            ):

                raise DeviceAPIError(
                    'FACE_NOT_USABLE',
                    'Không trích xuất được khuôn mặt. Nhìn thẳng và chụp lại.',
                    422,
                    'CAPTURE_AGAIN',
                )

            if (
                response.status_code == 429
                or response.status_code >= 500
            ):

                raise DeviceAPIError(
                    'HF_UNAVAILABLE',
                    'Dịch vụ nhận diện đang bận. Vui lòng thử lại sau.',
                    503,
                    'RETRY_LATER',
                    5,
                )

            if response.status_code != 200:

                raise DeviceAPIError(
                    'HF_CONTRACT_ERROR',
                    'Dịch vụ nhận diện chưa được cấu hình đúng.',
                    502,
                    'CONTACT_ADMIN',
                )

            payload = response.json()

            vector = payload.get('vector')

            normalized_vector(vector)

            return vector

    except requests.Timeout as exc:

        raise DeviceAPIError(
            'HF_TIMEOUT',
            'Dịch vụ nhận diện phản hồi quá lâu. Vui lòng thử lại.',
            504,
            'RETRY_LATER',
            5,
        ) from exc

    except requests.exceptions.JSONDecodeError as exc:

        raise DeviceAPIError(
            'INVALID_EMBEDDING',
            'Dịch vụ nhận diện trả về JSON không hợp lệ.',
            502,
            'CONTACT_ADMIN',
        ) from exc

    except requests.RequestException as exc:

        raise DeviceAPIError(
            'HF_UNAVAILABLE',
            'Không kết nối được dịch vụ nhận diện.',
            503,
            'RETRY_LATER',
            5,
        ) from exc

    except (
        ValueError,
        TypeError,
        AttributeError,
        OverflowError,
    ) as exc:

        raise DeviceAPIError(
            'INVALID_EMBEDDING',
            'Dịch vụ nhận diện trả về embedding không hợp lệ.',
            502,
            'CONTACT_ADMIN',
        ) from exc


# ==========================================================
# MATCH DriverProfile
#
# TÌM TRONG TOÀN BỘ DriverProfile
#
# KHÔNG CÒN:
# - DriverVehicleAssignment
# - eligible_assignments()
# - vehicle assignment
# ==========================================================

def match_driver(vector, threshold, margin):

    # ------------------------------------------------------
    # Lấy toàn bộ tài xế
    # ------------------------------------------------------

    drivers = DriverProfile.objects.select_related(
        'face_profile'
    ).all()

    ranked = []

    # ------------------------------------------------------
    # So sánh khuôn mặt
    # ------------------------------------------------------

    for driver in drivers:

        # Tài xế chưa có face profile
        if not hasattr(driver, 'face_profile'):

            continue

        face_profile = driver.face_profile

        if not face_profile:

            continue

        # Không có embedding
        if not face_profile.embedding:

            continue

        try:

            score = cosine_similarity(
                vector,
                face_profile.embedding,
            )

        except (
            ValueError,
            TypeError,
            OverflowError,
        ) as exc:

            raise DeviceAPIError(
                'PROFILE_EMBEDDING_INVALID',
                'Embedding hồ sơ tài xế không hợp lệ; cần tạo lại hồ sơ.',
                409,
                'CONTACT_ADMIN',
            ) from exc

        ranked.append(
            (
                score,
                driver,
            )
        )

    # ------------------------------------------------------
    # Không có tài xế nào có embedding
    # ------------------------------------------------------

    if not ranked:

        return (
            'DRIVER_NOT_FOUND',
            'Chưa có tài xế có dữ liệu khuôn mặt.',
            None,
            0.0,
        )

    # ------------------------------------------------------
    # Sắp xếp score giảm dần
    # ------------------------------------------------------

    ranked.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_score, best_driver = ranked[0]

    # ------------------------------------------------------
    # Không đạt threshold
    # ------------------------------------------------------

    if best_score < threshold:

        return (
            'FACE_NOT_MATCHED',
            'Khuôn mặt không khớp với tài xế nào.',
            None,
            best_score,
        )

    # ------------------------------------------------------
    # Kiểm tra ambiguity
    #
    # Nếu có 2 người có score quá gần nhau
    # thì không xác định được chính xác.
    # ------------------------------------------------------

    if len(ranked) > 1:

        second_score = ranked[1][0]

        difference = (
            best_score - second_score
        )

        if difference <= margin:

            return (
                'FACE_AMBIGUOUS',
                'Chưa phân biệt được tài xế. Vui lòng nhìn thẳng và chụp lại.',
                None,
                best_score,
            )

    # ------------------------------------------------------
    # XÁC THỰC THÀNH CÔNG
    # ------------------------------------------------------

    return (
        'DRIVER_VERIFIED',
        'Xác thực tài xế thành công.',
        best_driver,
        best_score,
    )
