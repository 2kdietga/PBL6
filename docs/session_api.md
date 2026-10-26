# Phiên lái Raspberry Pi

Đã triển khai: mở phiên, kết thúc phiên và đọc phiên hiện tại. Chưa gồm nhận vi phạm/heartbeat. Dùng `Authorization: Bearer <device-api-key>` như [API nhận diện](raspberry_pi_api.md).

## Chuẩn bị

1. Chạy `python manage.py migrate` để thêm `DrivingSession.source_device`.
2. Xe ACTIVE, gắn thiết bị không MAINTENANCE; cấp khóa bằng `python manage.py rotate_device_key <device_code>`.
3. Tài xế hoạt động, hồ sơ và khuôn mặt APPROVED, GPLX ACTIVE còn hạn, ngày cấp hợp lệ.
4. Xác nhận hệ hạng GPLX trong form GPLX. Xe tải cần khối lượng toàn bộ theo thiết kế; xe khách cần số hành khách và thông tin giường nằm. API dùng quy tắc hạng đã có trong `vehicles/licensing.py`.
5. Đúng một phân công còn hiệu lực cho tài xế/xe. Xe chưa có phiên STARTED.
6. Cấu hình HF/ngưỡng cosine như API nhận diện và đồng bộ đồng hồ Pi.

Không tự duyệt hồ sơ cũ hay tự điền thông số xe. Thiếu dữ liệu thì API từ chối và trả thông báo cụ thể.

## Mở phiên

Pi chỉ cần gọi endpoint start một lần với ảnh; không cần gọi face-verifications trước.
Endpoint nhận diện riêng vẫn được giữ để tương thích client cũ/test.

Response start có thêm `data.verified`, `data.session_started`, `data.reason_code`.
Thành công: verified=true, session_started=true, reason_code=null cùng session data bên dưới.
Nhận diện không khớp: verified=false, session_started=false, session_id=null, driver=null.
Nhận diện đúng nhưng bị từ chối mở phiên: HTTP lỗi và ok=false, nhưng data vẫn chứa
verified=true, session_started=false, session_id=null, driver={id, full_name}, reason_code.
Không coi verified=true là quyền bắt đầu lái; chỉ SESSION_STARTED / HTTP 201 cho phép mở phiên.

`code=DRIVER_NOT_ELIGIBLE` có `data.reason_code` cụ thể:

| reason_code | Ý nghĩa |
|---|---|
| DRIVER_ACCOUNT_INACTIVE | Tài khoản bị khóa |
| DRIVER_PROFILE_NOT_APPROVED | Hồ sơ chưa được duyệt |
| DRIVER_PROFILE_INCOMPLETE | Thiếu thông tin hồ sơ |
| LICENSE_MISSING | Chưa có GPLX |
| LICENSE_EXPIRED | GPLX hết hạn |
| LICENSE_NOT_ACTIVE | GPLX chưa hoạt động/được duyệt |
| LICENSE_ISSUE_DATE_INVALID | Ngày cấp ở tương lai |
| FACE_PROFILE_NOT_APPROVED | Khuôn mặt chưa được duyệt |
| FACE_PROFILE_CHANGED | Embedding thay đổi sau khi nhận diện |
| VEHICLE_SPECIFICATIONS_MISSING | Thiếu thông số xe |
| LICENSE_STANDARD_UNSUPPORTED | Hệ hạng GPLX chưa được hỗ trợ/xác nhận |
| LICENSE_CLASS_INCOMPATIBLE | Hạng GPLX không phù hợp xe |

Các lỗi phân công/phiên đang mở giữ code hiện có và reason_code trùng code.
Nếu nhiều điều kiện sai, trả điều kiện đầu tiên gặp trong bước kiểm tra.
Lỗi trước khi nhận diện (token, ảnh, HF, trạng thái thiết bị/xe) vẫn trả data=null.
Khóa thiết bị bị thu hồi không được nhận thông tin tài xế.

`POST /api/v1/device/sessions/start/`, multipart gồm đúng frame (JPEG toàn cảnh, tối đa 1280×720, 2 MiB) và captured_at (ISO 8601 có timezone).

Ảnh phải mới trong 60 giây, cho phép nhanh tối đa 5 giây, kể cả khi DEVICE_API_CHECK_FRAME_AGE=false cho endpoint test nhận diện cũ. Frame được xử lý trong RAM theo pipeline hiện có, không lưu vào phiên.

Server nhận diện → kiểm tra quyền lái → tạo phiên trong transaction. Không nhận driver_id/vehicle_id/assignment_id do Pi cung cấp. Không gọi HF trong lúc giữ khóa database.

HTTP 201, envelope giữ ok/code/message/request_id/server_time/action/retry_after_seconds/data như API cũ. Code=SESSION_STARTED, data:

```json
{
  "session_id": 120,
  "status": "STARTED",
  "vehicle_id": 5,
  "driver": {"id": 12, "full_name": "Nguyễn Văn A"},
  "started_at": "2026-10-25T12:00:00+00:00",
  "ended_at": null
}
```

Pi chỉ coi mở phiên thành công khi HTTP 201 và code=SESSION_STARTED. Không khớp khuôn mặt vẫn trả HTTP 200, verified=false như API cũ và không tạo phiên.

| HTTP | Code | Cách xử lý |
|---|---|---|
| 403 | DRIVER_NOT_ELIGIBLE | Kiểm tra hồ sơ/GPLX/thông số xe |
| 403 | NO_ACTIVE_ASSIGNMENT | Admin phân công đúng xe/thời gian |
| 409 | ASSIGNMENT_AMBIGUOUS | Admin xử lý phân công trùng |
| 409 | SESSION_ALREADY_ACTIVE | Đọc context |
| 422 | STALE_FRAME | Chụp ảnh mới, kiểm tra đồng hồ |
| 401 | DEVICE_UNAUTHORIZED | Kiểm tra/cấp lại khóa |

Lỗi ảnh/HF/trạng thái thiết bị và xe giữ mã của API cũ. Sau HF, server kiểm tra lại khóa/thiết bị, hồ sơ và phân công trước khi tạo phiên.

## Context và timeout

`GET /api/v1/device/context/` thêm active_session (cấu trúc như data ở trên hoặc null), device_status và vehicle_status. Chỉ trả phiên do chính thiết bị mở.

Context vẫn đọc được khi xe INACTIVE, thiết bị MAINTENANCE hoặc matching chưa cấu hình, miễn token hợp lệ. Matching thiếu/sai thì threshold và ambiguity_margin trả null; không cho phép mở phiên vì thế.

Start timeout thì đọc context trước khi thử lại. Nếu có active_session, hiển thị tài xế/phiên và tiếp tục sau khi người vận hành xác nhận đúng phiên. X-Request-ID chỉ đối chiếu log, không chống trùng. Khóa xe và unique constraint bảo đảm mỗi xe tối đa một phiên STARTED.

## Kết thúc phiên

`POST /api/v1/device/sessions/120/end/`, body rỗng. Không gửi JSON `{}` hoặc ended_at.

HTTP 200, code=SESSION_ENDED, cùng cấu trúc session data với status=ENDED và ended_at do server đặt. Gửi lại trả cùng thời điểm kết thúc cũ.

- Chỉ thiết bị nguồn được kết thúc phiên; không tồn tại/không thuộc thiết bị trả 404 SESSION_NOT_FOUND.
- Vẫn cho kết thúc khi tài xế bị khóa, xe INACTIVE, thiết bị MAINTENANCE hoặc phân công hết hạn.
- Token bị thu hồi vẫn trả 401. Không tự kết thúc phiên khi mất mạng.

## Lịch sử và thiết bị

source_device là FK PROTECT, bất biến sau khi tạo. Không xóa thiết bị có lịch sử phiên. Không chuyển thiết bị sang xe khác khi xe cũ còn phiên STARTED; form/model đều kiểm tra. Không dùng QuerySet.update/bulk update để đổi liên kết vì bỏ qua validation.

Phiên cũ trước migration giữ source_device=null, không đoán thiết bị từ xe hiện tại. Pi không được đóng các phiên này; nếu còn STARTED thì admin cần đối soát trước demo. Migration không tự sửa hay kết thúc lịch sử.

## Client mẫu

`examples/raspberry_pi/face_client.py` thêm start_session/end_session, dùng requests/OpenCV trên Pi:

```python
client = FaceClient()
# full_frame và captured_at từ BestFrameSelector / camera loop hiện có.
status, body = client.start_session(full_frame, captured_at)
if status == 201 and body['code'] == 'SESSION_STARTED':
    session_id = body['data']['session_id']
    print(body['message'])
    # Khi người dùng bấm nút kết thúc:
    status, body = client.end_session(session_id)
```

Vòng điều khiển cần bắt requests.RequestException và ValueError khi mất mạng/response không phải JSON. Start timeout thì đọc context; end timeout gửi lại cùng session_id. Chỉ một request điều khiển đang chờ trên Pi.

## Kiểm thử

`python manage.py test driving frontend config accounts violations --settings=config.test_settings --noinput`

Test dùng SQLite trong RAM, mock HF. Chưa chứng minh khóa đồng thời trên PostgreSQL hoặc camera thật; nghiệm thu Pi cần thử mở/đóng, timeout, không có phân công và hai request start đồng thời trên PostgreSQL.
