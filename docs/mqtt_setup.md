# Triển khai MQTT SaveLife

## Phần đã có trong repository

- Menu **Thiết bị** (`/devices/`), dùng quyền ADMIN/superuser hiện tại.
- Tám ngưỡng và giới hạn theo `mqtt.md`; bộ ngưỡng lưu trong JSONField để dùng chung kiểm tra và payload. Snapshot đã áp dụng được lưu riêng.
- Phiên bản tăng trong transaction, khóa thiết bị, từ chối form mở từ phiên bản cũ.
- Worker riêng: TLS xác thực chứng chỉ, Paho callback API v2, reconnect 1–30 giây, keepalive 30 giây.
- Desired QoS 1/retained; trạng thái sent chỉ sau PUBACK. Pending/sent được thử lại sau mất ACK; khi worker reconnect, gửi lại cấu hình hiện hành để khôi phục retained trên broker.
- ACK đúng thiết bị và phiên bản mới xác nhận applied; heartbeat không phải ACK. ACK trùng và ACK cũ bị bỏ qua.
- WorkerHealth có thời hạn 15 giây; heartbeat Pi có thời hạn 60 giây. Retained heartbeat bị bỏ qua. Sau worker reconnect cần heartbeat mới để xác nhận online.
- Nhật ký thay đổi cấu hình/kết nối, polling 5 giây cả trạng thái, snapshot đã áp dụng và sự kiện. Nội dung form đang nhập được giữ nguyên; cảnh báo khi có phiên bản mới hơn.
- Khóa worker trong database có thời hạn 30 giây, ngăn hai worker cùng hoạt động. Khi process chết bất thường, worker mới có thể khởi động sau khi khóa hết hạn.

Mã thiết bị MQTT chỉ gồm `A-Z a-z 0-9 _ -`. Sau khi có cấu hình MQTT, không đổi mã thiết bị qua web/model: topic retained và phiên bản gắn với danh tính này.

## Cấu hình server

Cài `pip install -r requirements.txt`. Thêm biến môi trường cho cả web và worker (không commit mật khẩu):

```dotenv
MQTT_HOST=l9c60b66.ala.asia-southeast1.emqxsl.com
MQTT_PORT=8883
MQTT_USERNAME=your-worker-username
MQTT_PASSWORD=your-worker-password
MQTT_CLIENT_ID=savelife-web-worker
# MQTT_CA_CERT=/absolute/path/to/ca.pem
```

Nếu không chỉ định CA, dùng kho CA tin cậy của hệ điều hành. Không tắt kiểm tra TLS.

Sao lưu PostgreSQL theo quy trình triển khai của dự án, rồi chạy:

```sh
python manage.py migrate
python manage.py mqtt_check
python manage.py runserver
# Một terminal/process riêng:
python manage.py mqtt_worker
```

Render: chỉ cần một Web Service với start command `bash start.sh`. Script chạy migration rồi dùng `run_services.py` quản lý Gunicorn và MQTT worker như hai process riêng. Thêm các biến MQTT vào Environment của Web Service; `RUN_MQTT=true` là mặc định. Worker thoát sẽ được thử khởi động lại sau 5 giây, kể cả khi đang chờ khóa worker cũ trong rolling deploy. Khi web thoát thì cả service dừng; SIGTERM dừng cả hai process. Giữ một instance. Service ngủ thì MQTT tạm ngừng theo.

Nếu muốn dùng Background Worker riêng: đặt `RUN_MQTT=false` trên web, dùng `bash start-mqtt.sh` cho worker với cùng database và biến MQTT. Chỉ chọn một trong hai cách. Local vẫn dùng hai terminal `runserver` và `mqtt_worker` như trên. Không chạy MQTT trong AppConfig.ready hay thread của Gunicorn. Client ID phải khác Pi; UI hết hạn sức khỏe sau 15 giây.

`mqtt_check` dùng client ID tạm riêng, kiểm tra TLS, đăng nhập và SUBACK của các topic telemetry; không gửi cấu hình. SUBACK không chứng minh ACL publish hoặc Pi đang hoạt động. Muốn kiểm tra worker có thời hạn: `python manage.py mqtt_worker --run-seconds 15`. Chỉ chạy khi không có worker khác.

Migration chỉ thêm bảng mới trong schema hiện tại. Đã có lệnh chuyển dữ liệu từ schema cũ `savelife_device_config` theo cấu trúc `devices_device`/`devices_aiconfig` của web cũ:

```sh
python manage.py import_legacy_mqtt          # kiểm tra và xem trước
python manage.py import_legacy_mqtt --apply  # chuyển ngưỡng + desired_version
```

Lệnh ghép theo device_id → device_code, chỉ dùng thiết bị đã có trong SaveLife, không ghi đè cấu hình mới, không xóa/sửa schema cũ. Nếu thiếu thiết bị hoặc ngưỡng không hợp lệ thì rollback toàn bộ. Phiên bản mong muốn được giữ nguyên để không lùi phiên bản trên Pi; trạng thái chuyển về pending và yêu cầu ACK mới, không sao chép trạng thái applied không có bằng chứng runtime. Dừng worker web cũ trước khi chuyển quyền điều khiển sang worker mới.

## EMQX authentication / ACL

Tạo tài khoản worker và tài khoản riêng từng Pi. HTTP device API key của SaveLife không thay thế thông tin đăng nhập MQTT.

| Client | Publish | Subscribe |
| --- | --- | --- |
| Worker | `savelife/+/config/desired` | `savelife/+/config/reported`, `savelife/+/status`, `savelife/+/heartbeat` |
| R01 | `savelife/R01/config/reported`, `savelife/R01/status`, `savelife/R01/heartbeat` | `savelife/R01/config/desired` |

Mặc định từ chối topic khác. Áp dụng tương tự từng thiết bị. Payload device_id/topic được kiểm tra tại server, nhưng ACL broker mới ngăn thiết bị giả mạo thiết bị khác.

Khi thu hồi/xóa thiết bị: thu hồi tài khoản broker và xóa retained desired/status (publish payload rỗng, retain=true) theo đúng topic. Không tái sử dụng mã thiết bị khi retained và cấu hình cục bộ cũ còn tồn tại.

## Hợp đồng phía Raspberry Pi

Mã AI thực tế chưa có trong workspace. Server đã sẵn sàng theo payload của `mqtt.md`; tích hợp Pi cần:

1. Khởi động AI bằng `applied_config.json` đã được kiểm tra; không đợi mạng.
2. Kết nối TLS với client ID và tài khoản riêng. Đăng ký LWT offline QoS 1 retained trước connect; reconnect 1–30 giây.
3. Subscribe desired sau mỗi connect; publish online QoS 1 retained. Heartbeat mỗi 15 giây, QoS 0, không retained, báo sức khỏe runtime thực tế.
4. Kiểm tra đúng device_id, version nguyên dương và đủ tám ngưỡng hữu hạn trong giới hạn. Bỏ phiên bản nhỏ hơn bản đã áp dụng. Cùng version nhưng khác tham số phải từ chối.
5. Ghi desired JSON bằng file tạm + fsync + atomic replace. Đưa cấu hình vào runtime tại ranh giới frame; cập nhật các đối tượng đã cache ngưỡng và trạng thái đếm thời gian liên quan.
6. Chỉ khi runtime xác nhận đang sử dụng cấu hình mới mới lưu applied JSON bền vững rồi gửi ACK applied. Không ACK chỉ vì nhận hoặc ghi JSON. Nếu lỗi, giữ/khôi phục cấu hình đang hoạt động và gửi rejected kèm reason.
7. Khi nhận lại version đã áp dụng, gửi lại ACK nếu runtime thật sự còn dùng version đó. Khi reconnect gửi lại ACK của runtime; không giả định file trên đĩa chứng minh AI đang chạy.
8. Dừng bình thường: publish offline và chờ PUBACK trước disconnect. Dùng systemd tự restart agent/runtime sau crash và reboot.

## Kiểm thử

```sh
python manage.py test device_control --settings=config.test_settings
# Tùy chọn: test broker thật với thiết bị giả lập CHECK_* riêng, DB SQLite bộ nhớ:
python examples/mqtt_smoke_test.py
```

Unit test dùng SQLite trong bộ nhớ và MQTT client giả lập, không kết nối broker/PostgreSQL thật. Smoke test dùng broker thật và hai client giả lập; tài khoản test cần quyền publish/subscribe topic CHECK_* (không mở rộng ACL tài khoản worker production chỉ để chạy test). Test gửi desired retained trước khi client Pi kết nối, nhận ACK/PUBACK, cập nhật snapshot và heartbeat trong database bộ nhớ, rồi xóa retained test. Đây chưa phải kiểm chứng AI trên Pi thật.

Cần nghiệm thu thiết bị thực tế: R01/R02 phân tách topic, mất mạng khi gửi cấu hình, mất ACK, Pi reboot, worker restart/mất mạng, AI dừng nhưng MQTT còn kết nối, ACL từ chối cross-device.

Paho API tham chiếu: https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html
