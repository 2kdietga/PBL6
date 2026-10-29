# Raspberry Pi gửi vi phạm AI

Đã triển khai `POST /api/v1/device/violations/`. Vi phạm mới có trạng thái
`PENDING`, mức độ `MEDIUM`, hiển thị ngay trong danh sách Vi phạm hiện có để admin
xem ảnh và xác nhận/từ chối. Đây là vi phạm AI, không phải lỗi camera/model.

## Chuẩn bị

- Chạy `python manage.py migrate`.
- Cấu hình Cloudinary phía server; dùng API key thiết bị hiện có.
- Mở phiên qua `sessions/start/`, giữ `session_id` trả về.
- Tạo mã loại vi phạm trên web, ví dụ `DROWSINESS`. Mã phải khớp chính xác.

## Request

Header `Authorization: Bearer <device-api-key>`. `X-Request-ID` là UUID tùy chọn,
chỉ dùng đối chiếu request, không chống trùng.

Gửi multipart với đúng các trường sau:

| Trường | Nội dung |
|---|---|
| event_id | UUID riêng cho mỗi sự kiện; giữ nguyên khi gửi lại |
| session_id | ID phiên do chính thiết bị mở, thuộc xe hiện tại |
| violation_code | Mã loại vi phạm đã có trong database |
| detected_at | ISO 8601 có múi giờ, thời điểm AI phát hiện |
| confidence | Số hữu hạn từ 0 đến 1 |
| image | Một JPEG, MIME image/jpeg, tối đa 2 MiB và 1920×1080 |

Không gửi driver_id, vehicle_id, status, severity hoặc URL ảnh. Tổng request
không quá 2 MiB + 16 KiB, phải có Content-Length. Thư viện requests tự đặt các
header multipart; không tự đặt Content-Type.

Thời điểm phải nằm trong phiên, không cũ quá 24 giờ, không nhanh hơn server quá
5 giây. Phiên đã kết thúc vẫn nhận nếu thời điểm vi phạm nằm trong phiên.
Vẫn nhận bằng chứng khi thiết bị chuyển sang bảo trì hoặc xe ngừng hoạt động;
token phải còn hiệu lực, thiết bị phải còn thuộc xe của phiên.

## Ví dụ Pi

```python
import os
from datetime import datetime, timezone
from uuid import uuid4
import requests

# Tạo một lần khi phát hiện sự kiện, lưu cùng ảnh để có thể gửi lại.
event = {
    'event_id': str(uuid4()),
    'session_id': 120,  # ID thực tế từ sessions/start/
    'violation_code': 'DROWSINESS',
    'detected_at': datetime.now(timezone.utc).isoformat(),
    'confidence': 0.94,
}
with open('evidence.jpg', 'rb') as image:
    response = requests.post(
        os.environ['WEB_SERVER_URL'].rstrip('/') + '/api/v1/device/violations/',
        headers={'Authorization': 'Bearer ' + os.environ['DEVICE_API_KEY']},
        data=event,
        files={'image': ('evidence.jpg', image, 'image/jpeg')},
        timeout=(5, 90),
        allow_redirects=False,
    )
result = response.json()
print(response.status_code, result)
```

Trong vòng điều khiển Pi, bắt `requests.RequestException` và `ValueError` (response
không phải JSON). Mất mạng/5xx: giữ nguyên event_id, metadata và ảnh để gửi lại;
không tạo UUID mới cho lần thử lại. Cảnh báo tại chỗ không cần chờ server.

## Response

Envelope chung gồm ok/code/message/request_id/server_time/action/retry_after_seconds/data.

| HTTP | Code | Ý nghĩa |
|---|---|---|
| 201 | VIOLATION_RECORDED | Đã lưu cả vi phạm PENDING và ảnh |
| 200 | EVENT_ALREADY_RECORDED | Trả ID và trạng thái hiện tại của sự kiện đã lưu |
| 400 | INVALID_PAYLOAD | Sai/thiếu/thừa trường hoặc sai kiểu dữ liệu |
| 401 | DEVICE_UNAUTHORIZED | Token sai hoặc đã thu hồi |
| 404 | SESSION_NOT_FOUND | Không có phiên thuộc thiết bị và xe hiện tại |
| 409 | DEVICE_ASSIGNMENT_CHANGED | Thiết bị đổi xe trong lúc xử lý |
| 411 | CONTENT_LENGTH_REQUIRED | Thiếu độ dài request |
| 413 | IMAGE_TOO_LARGE | Quá giới hạn ảnh/request |
| 415 | INVALID_IMAGE / MULTIPART_REQUIRED | Ảnh hỏng/sai định dạng hoặc sai loại request |
| 422 | INVALID_EVENT_TIME / UNKNOWN_VIOLATION_CODE | Sai thời điểm hoặc mã vi phạm |
| 503 | STORAGE_UNAVAILABLE | Không lưu được ảnh; thử lại sau 5 giây |
| 503 | DATABASE_UNAVAILABLE | Chưa lưu được dữ liệu; gửi lại cùng event_id sau 5 giây |

Khi tạo mới: `data = {"violation_id": 501, "status": "PENDING"}`.
Khi gửi lại, server trả bản ghi cũ, không sửa dữ liệu kể cả admin đã duyệt.
Không tái sử dụng event_id cho sự kiện khác. Constraint theo thiết bị/event_id
và khóa database ngăn tạo trùng. Lỗi DB sau upload được rollback và dọn ảnh mới;
crash hoặc dọn ảnh thất bại có thể để lại ảnh mồ côi cần đối soát.

## Kiểm thử

`python manage.py test violations driving --settings=config.test_settings --noinput`

Test dùng SQLite trong RAM và mock Cloudinary. Cần nghiệm thu riêng Pi thật,
Cloudinary thật và các request đồng thời trên PostgreSQL. Heartbeat chưa triển khai.
