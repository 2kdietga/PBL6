# AI/Pi ↔ Server — thiết kế đơn giản cho đồ án

Ngày: 25/10/2026. Phần phiên lái đã triển khai; [session_api.md](session_api.md) mô tả chính xác API hiện tại. Vi phạm và heartbeat bên dưới vẫn là đề xuất; phần phiên lái bên dưới là phác thảo ban đầu.

## 1. Phạm vi

Luồng demo: nhận diện tài xế → mở phiên → AI phát hiện vi phạm → gửi thông tin và ảnh → server lưu → admin duyệt.

- Pi chạy AI, gửi cảnh báo tới esp32 phát ra loa
- Django kiểm tra dữ liệu, upload Cloudinary, lưu PostgreSQL, trả JSON.
- Pi gửi heartbeat mỗi 30 giây để báo kết nối và lỗi camera/model.
- AI chỉ tạo vi phạm PENDING. Admin xác nhận hoặc từ chối sau.

Dùng HTTP trong mạng LAN để demo, HTTPS khi triển khai Internet. Giữ API key thiết bị hiện có. Không cần MQTT, WebSocket, broker, worker hoặc hàng đợi lệnh.

Thông báo hai chiều ở bản này là request từ Pi và response từ server. Chưa có server chủ động đẩy lệnh xuống Pi. Cảnh báo tại chỗ không chờ mạng.

## 2. API

Base URL: `/api/v1/device/`. Header: `Authorization: Bearer <device-api-key>`.

| Method | Endpoint            | Chức năng                             | Hiện trạng |
| ------ | ------------------- | ------------------------------------- | ---------- |
| GET    | context/            | Thông tin thiết bị/xe                 | Đã có      |
| POST   | face-verifications/ | Nhận diện danh tính                   | Đã có      |
| POST   | sessions/start/     | Nhận diện, kiểm tra quyền và mở phiên | Đã có      |
| POST   | sessions/{id}/end/  | Kết thúc phiên                        | Đã có      |
| POST   | violations/         | Gửi vi phạm kèm ảnh                   | Cần làm    |
| POST   | heartbeat/          | Báo kết nối/lỗi hiện tại              | Cần làm    |

Server suy ra thiết bị và xe từ token; không tin driver_id/vehicle_id do Pi tự khai.

## 3. Phiên lái

Nhận diện hiện tại chưa kiểm tra quyền lái. Endpoint start dùng lại hàm nhận diện và kiểm tra tài khoản hoạt động, hồ sơ/khuôn mặt đã duyệt, GPLX hợp lệ/phù hợp xe, phân công còn hiệu lực. Pi chỉ cần gọi start khi bắt đầu lái.

`POST sessions/start/`: multipart gồm frame và captured_at theo [API nhận diện hiện có](raspberry_pi_api.md). Không có hoặc có nhiều phân công phù hợp thì từ chối, admin xử lý.

Server khóa xe trong transaction và dùng ràng buộc một phiên STARTED/xe. Trả SESSION_STARTED với data:

```json
{
  "session_id": 120,
  "driver_name": "Nguyễn Văn A",
  "started_at": "2026-10-25T12:00:00Z"
}
```

Đã có phiên thì trả 409 SESSION_ALREADY_ACTIVE. Nếu timeout, Pi đọc context mở rộng với active_session (id và tên tài xế) để kiểm tra server đã mở phiên chưa.

`POST sessions/120/end/`: không cần payload. Server kiểm tra quyền thiết bị, đặt ended_at bằng giờ server và chuyển ENDED. Gọi lại trả SESSION_ENDED, không sửa thời gian cũ. Không tự kết thúc phiên khi mất heartbeat.

Giới hạn demo: không chuyển thiết bị sang xe khác khi còn dữ liệu pending. Server chặn đổi liên kết thiết bị–xe khi xe có phiên đang mở. Lịch sử chuyển thiết bị để giai đoạn sau.

## 4. Gửi vi phạm và ảnh trong một request

`POST violations/`, multipart/form-data:

| Trường         | Kiểu                 | Ý nghĩa                            |
| -------------- | -------------------- | ---------------------------------- |
| event_id       | UUID                 | ID sự kiện, giữ nguyên khi gửi lại |
| session_id     | Số nguyên            | Phiên được cấp khi bắt đầu lái     |
| violation_code | Chuỗi                | Mã loại vi phạm có trong database  |
| detected_at    | ISO 8601 có timezone | Thời điểm phát hiện                |
| confidence     | Số 0–1               | Điểm AI tham khảo                  |
| image          | JPEG                 | Một ảnh, tối đa 2 MiB và 1920×1080 |

Ví dụ phần text; thực tế gửi multipart cùng file image, không gửi ảnh base64:

```json
{
  "event_id": "c5e15bac-956e-45e2-913a-25ad82748001",
  "session_id": 120,
  "violation_code": "DROWSINESS",
  "detected_at": "2026-10-25T12:05:00Z",
  "confidence": 0.94
}
```

DROWSINESS (buồn ngủ), PHONE_USE (dùng điện thoại) là mã minh họa. Tạo trước các loại mà model thực sự hỗ trợ bằng giao diện quản lý loại vi phạm.

Server xử lý:

1. Kiểm tra token, phiên thuộc xe của thiết bị, loại vi phạm tồn tại và confidence hữu hạn trong [0,1].
2. event_id đã được thiết bị gửi thành công thì trả violation_id cũ. Pi không tái sử dụng ID cho sự kiện khác.
3. Kiểm tra thời gian trong phiên. Cho phép gửi trễ tối đa 24 giờ, tương lai tối đa 5 giây. Phiên đã kết thúc vẫn nhận nếu detected_at nằm giữa started_at và ended_at.
4. Kiểm tra JPEG và kích thước, upload Cloudinary; không nhận URL ảnh do Pi tự cung cấp.
5. Tạo Violation và Evidence trong transaction. status=PENDING, severity=MEDIUM mặc định; admin có thể chỉnh mức độ khi duyệt.
6. Chỉ trả thành công sau khi lưu đầy đủ vi phạm và bằng chứng.

Thêm unique constraint `(source_device, event_id)` để chống trùng cả khi gửi đồng thời. Nếu conflict sau upload, rollback phần tạo mới, dọn ảnh dư và trả bản ghi cũ. Mỗi lần upload dùng public ID riêng, tránh xóa ảnh của request đã thành công.

Cloudinary lỗi thì chưa tạo vi phạm, trả lỗi để gửi lại. DB lỗi sau upload thì cố gắng dọn ảnh mới, ghi log nếu dọn thất bại. Crash giữa upload và lưu DB có thể để lại ảnh mồ côi; đồ án chấp nhận đối soát thủ công.

## 5. Response

Giữ envelope hiện có. Ví dụ HTTP 201:

```json
{
  "ok": true,
  "code": "VIOLATION_RECORDED",
  "message": "Đã ghi nhận vi phạm, chờ quản trị viên xác nhận.",
  "request_id": "cc57f9f4-524c-4609-a589-77625caa8001",
  "server_time": "2026-10-25T12:05:02Z",
  "action": "NONE",
  "retry_after_seconds": null,
  "data": { "violation_id": 501, "status": "PENDING" }
}
```

| HTTP    | Code                                        | Pi xử lý                                      |
| ------- | ------------------------------------------- | --------------------------------------------- |
| 200/201 | EVENT_ALREADY_RECORDED / VIOLATION_RECORDED | Đã nhận, không gửi lại                        |
| 400     | INVALID_PAYLOAD                             | Sửa dữ liệu                                   |
| 401     | DEVICE_UNAUTHORIZED                         | Kiểm tra/cấp lại token                        |
| 403     | DRIVER_NOT_ELIGIBLE                         | Báo chưa đủ điều kiện mở phiên                |
| 404     | SESSION_NOT_FOUND                           | Phiên không tồn tại hoặc không thuộc thiết bị |
| 409     | SESSION_ALREADY_ACTIVE                      | Đọc context                                   |
| 413/415 | IMAGE_TOO_LARGE / INVALID_IMAGE             | Sửa ảnh                                       |
| 422     | INVALID_EVENT_TIME / UNKNOWN_VIOLATION_CODE | Kiểm tra thời gian/mã loại                    |
| 503     | STORAGE_UNAVAILABLE                         | Retry sau 5 giây                              |

Lỗi có cùng envelope, ok=false, data=null; action FIX_REQUEST/CONTACT_ADMIN/RETRY_LATER phù hợp. Mã nhận diện giữ như API cũ. Pi xử lý theo code, hiển thị message. Nhận diện vẫn phải kiểm tra verified, không chỉ ok.

## 6. Heartbeat và lỗi kỹ thuật

`POST heartbeat/` mỗi 30 giây:

```json
{ "camera_ok": true, "model_ok": true, "error_message": "" }
```

Camera lỗi thì camera_ok=false, error_message="Không đọc được camera". Message tối đa 200 ký tự, không gửi token/traceback/ảnh. Server lưu trạng thái gần nhất, cập nhật last_heartbeat_at bằng giờ server, trả HEARTBEAT_RECEIVED.

Web hiển thị mất liên lạc sau 90 giây; null nghĩa là chưa có heartbeat. Dùng trường riêng vì last_seen_at hiện được API khác cập nhật. Không ghi đè MAINTENANCE do admin đặt; thiết bị bảo trì vẫn gửi heartbeat nếu token hợp lệ.

Lỗi kỹ thuật hiển thị ở trang thiết bị, không tạo Violation. Không cần bảng lịch sử DeviceEvent.

## 7. Retry đơn giản

- Không gửi từng frame; cooldown ban đầu 10 giây cho cùng loại hành vi, điều chỉnh khi demo.
- Timeout/mất mạng/5xx: gửi lại tối đa 3 lần, cách nhau 5 giây, giữ nguyên event_id và ảnh.
- Vẫn lỗi: giữ ảnh và metadata JSON ở thư mục pending trên Pi để gửi lại thủ công. Không giữ heartbeat cũ.
- Chỉ xóa pending khi server trả thành công. 4xx cần sửa/đối soát, không retry liên tục.
- Cảnh báo tại chỗ vẫn chạy khi mất mạng. Chưa mở phiên mới offline.

Chưa tự phục hồi đầy đủ sau mất mạng dài hoặc reboot; đây là giới hạn của bản đồ án.

## 8. Thay đổi tối thiểu và demo

| Thành phần               | Bổ sung                                                                                 |
| ------------------------ | --------------------------------------------------------------------------------------- |
| Violation                | source_device (FK được bảo vệ), event_id (UUID), confidence; unique theo thiết bị/event |
| Device                   | last_heartbeat_at, camera_ok, model_ok, error_message                                   |
| driving/device_api.py    | Start/end phiên, heartbeat; context thêm active_session                                 |
| violations/device_api.py | Nhận vi phạm + ảnh                                                                      |
| driving/device_urls.py   | Route mới                                                                               |
| Trang thiết bị           | Kết nối/lỗi gần nhất                                                                    |
| Client Pi                | Multipart, heartbeat, retry, lưu pending                                                |

Trường mới cho dữ liệu lịch sử cho phép null; request mới phải đủ trường. Giữ model Evidence và quy trình admin duyệt. Không cần DeviceCommand, DeviceOperation, EvidenceUpload.

Thứ tự: mở/đóng phiên → gửi ảnh vi phạm và duyệt trên web → gửi lại không trùng → heartbeat → thử mất mạng.

Test token sai, phiên xe khác, ảnh hỏng, event trùng, upload lỗi và thời gian ngoài phiên. Mock Cloudinary/HF trong test, nghiệm thu riêng bằng Pi thật.

Hướng mở rộng: video, push thời gian thực, lệnh có ACK, queue tự phục hồi, lịch sử lỗi và chuyển thiết bị giữa nhiều xe.
