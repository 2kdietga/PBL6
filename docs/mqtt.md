BÁO CÁO THIẾT KẾ VÀ TRIỂN KHAI

Tích hợp quản lý cấu hình AI và giám sát kết nối MQTT vào hệ thống SaveLife

Dự án: SaveLife – Hệ thống quản lý và giám sát hành vi tài xế khi lái xe

Phân hệ mới: IoT Device Management & AI Configuration

Phạm vi: Cấu hình AI từ xa, quản lý kết nối và tự phục hồi khi mất mạng

Trạng thái: Phương án thiết kế đã thống nhất, chuẩn bị triển khai

1. Tổng quan

1.1. Bối cảnh

Hệ thống SaveLife hiện tại gồm các thành phần chính:

Website Django quản lý tài xế, phương tiện, thiết bị, phiên lái và vi phạm.

PostgreSQL trên Render lưu dữ liệu hệ thống.

Raspberry Pi chạy chương trình AI nhận diện hành vi tài xế.

EMQX Cloud đóng vai trò MQTT Broker.

Trước đây, nhóm dự định xây dựng một website Django riêng để quản lý cấu hình AI. Tuy nhiên, việc tách thành hai website dẫn đến trùng lặp giao diện quản trị, danh sách thiết bị và công việc triển khai.

Vì vậy, phương án mới là tích hợp toàn bộ chức năng quản lý cấu hình AI và giám sát kết nối MQTT vào website quản trị SaveLife hiện có.

1.2. Mục tiêu

Phân hệ mới cần đáp ứng bốn mục tiêu chính:

Mục tiêu 1 – Cấu hình AI từ xa

Quản trị viên có thể thay đổi 8 ngưỡng AI của từng Raspberry Pi mà không cần truy cập trực tiếp thiết bị.

Mục tiêu 2 – Giám sát kết nối

Website hiển thị tình trạng kết nối của từng Raspberry Pi, bao gồm Online, Offline và Mất tín hiệu.

Mục tiêu 3 – Tự phục hồi khi mất mạng

Raspberry Pi phải tự kết nối lại EMQX, tiếp tục sử dụng cấu hình AI đã lưu và nhận lại cấu hình mới nhất sau khi khôi phục kết nối.

Mục tiêu 4 – Đồng bộ chính xác

Website chỉ hiển thị cấu hình đã áp dụng sau khi chương trình AI trên Raspberry Pi thực sự xác nhận sử dụng phiên bản mới.

1.3. Phạm vi hiện tại

Giai đoạn triển khai này bao gồm:

Quản lý cấu hình 8 ngưỡng AI.

Gửi và nhận cấu hình qua MQTT.

Theo dõi trạng thái MQTT của từng thiết bị.

Heartbeat và phát hiện mất tín hiệu.

MQTT Last Will and Testament.

Tự kết nối lại khi mất mạng.

Lưu và khôi phục cấu hình.

Hiển thị trạng thái trên dashboard quản trị.

Chưa triển khai: OTA Update, thay model ONNX, điều khiển camera từ xa, streaming video hoặc cấu hình AI nâng cao.

2. Kiến trúc hệ thống mới

2.1. Nguyên tắc thiết kế

Hệ thống chỉ sử dụng một dự án Django chính.

Dự án Django này vừa đảm nhiệm các chức năng quản lý SaveLife trước đây, vừa cung cấp chức năng quản lý thiết bị IoT mới.

Phần MQTT Worker vẫn là một tiến trình chạy độc lập, nhưng sử dụng chung mã nguồn, Django models và PostgreSQL với website chính.

2.2. Sơ đồ kiến trúc

              QUẢN TRỊ VIÊN
                    |
                    v
          DJANGO SAVELIFE ADMIN
                    |
          +---------+----------+
          |                    |
          v                    v
    Quản lý hiện tại      IoT Device Center
    - Tài xế             - Trạng thái thiết bị
    - Phương tiện        - Cấu hình 8 ngưỡng AI
    - Phiên lái          - Phiên bản cấu hình
    - Vi phạm            - Heartbeat / Last Seen
          |                    |
          +---------+----------+
                    |
                    v
             POSTGRESQL RENDER
                    ^
                    |
             DJANGO MQTT WORKER
                    |
                MQTT / TLS
                    |
                    v
                EMQX CLOUD
                    |
          +---------+----------+
          |                    |
          v                    v
     Raspberry Pi R01     Raspberry Pi R02
          |                    |
     MQTT Agent            MQTT Agent
          |                    |
     AI Runtime            AI Runtime

2.3. Phân chia trách nhiệm

Thành phần

Chức năng

Django Web

Giao diện quản trị, chỉnh ngưỡng và xem trạng thái

PostgreSQL Render

Lưu cấu hình, phiên bản và trạng thái thiết bị

Django MQTT Worker

Publish cấu hình, Subscribe phản hồi và heartbeat

EMQX Cloud

Trung chuyển thông điệp MQTT

Raspberry Pi MQTT Agent

Nhận cấu hình, báo trạng thái và xử lý mất kết nối

AI Runtime

Áp dụng ngưỡng mới vào thuật toán nhận diện

Nguyên tắc: Không thực hiện kết nối MQTT liên tục bên trong Django View hoặc AppConfig.ready().

3. Tổ chức lại dự án Django

3.1. Tái sử dụng website chính

Website SaveLife đã có danh sách thiết bị R01, R02... Vì vậy, phân hệ mới sẽ sử dụng trực tiếp danh sách thiết bị hiện có.

Theo cấu trúc source đã trao đổi, thông tin thiết bị đang được quản lý bởi model vehicles.Device, trong đó device_code là mã thiết bị.

Không tạo thêm một bảng danh sách thiết bị độc lập chứa R01, R02 như phương án hai website trước đây.

Mỗi thiết bị sẽ có một bộ cấu hình AI và một bản ghi trạng thái kết nối.

3.2. Tạo Django app mới

Đề xuất bổ sung app:

device_control

Cấu trúc dự kiến:

SaveLife/
|
├── accounts/
├── vehicles/
├── driving/
├── violations/
├── frontend/
|
├── device_control/
│ ├── models.py
│ ├── admin.py
│ ├── views.py
│ ├── urls.py
│ ├── forms.py
│ ├── services/
│ │ ├── config_service.py
│ │ ├── mqtt_protocol.py
│ │ └── status_service.py
│ ├── management/
│ │ └── commands/
│ │ └── mqtt_worker.py
│ └── migrations/
|
├── templates/
│ └── device_control/
│ ├── dashboard.html
│ ├── device_detail.html
│ └── config_form.html
|
├── config/
└── manage.py

Đây là cấu trúc đề xuất, sẽ điều chỉnh theo thư mục thực tế của dự án Django chính.

3.3. Database và schema

Phương án được đề xuất: Dùng PostgreSQL Render hiện tại và schema mà website SaveLife chính đang sử dụng, thường là public.

Lý do:

Chỉ còn một Django Project.

Không còn nguy cơ hai Django Project dùng chung bảng django_migrations nhưng quản lý hai hệ migrations khác nhau.

Các model mới có thể tạo quan hệ trực tiếp đến vehicles.Device.

Django ORM quản lý dữ liệu và migrations đơn giản hơn.

Không cần đồng bộ danh sách thiết bị giữa hai schema.

Các bảng mới được đặt tên riêng theo app device_control, tránh trùng các bảng trước đây.

Lưu ý chuyển đổi: Nếu schema savelife_device_config đã có dữ liệu cấu hình thật, phải sao lưu và chuyển dữ liệu sang các bảng mới trước khi ngừng sử dụng. Không xóa schema cũ ngay.

4. Thiết kế cơ sở dữ liệu

Đề xuất tạo hai model chính trong app device_control.

4.1. Model AIConfig

Lưu các ngưỡng AI và trạng thái đồng bộ cấu hình.

Trường

Chức năng

device

OneToOne đến thiết bị SaveLife hiện tại

8 trường ngưỡng AI

Giá trị cấu hình mong muốn

desired_version

Phiên bản mới nhất trên Django

applied_version

Phiên bản Pi đã xác nhận

sync_status

pending / sent / applied / rejected

last_error

Nguyên nhân lỗi

updated_at

Lần thay đổi gần nhất

applied_at

Thời gian xác nhận áp dụng

Mỗi thiết bị có một bộ cấu hình AI hiện hành.

4.2. Model DeviceConnection

Lưu trạng thái kết nối và hoạt động của Raspberry Pi.

Trường

Chức năng

device

OneToOne đến thiết bị hiện tại

connection_state

online / offline / unknown

last_heartbeat_at

Lần gần nhất hệ thống nhận heartbeat

last_online_at

Thời gian nhận thông báo online

last_offline_at

Thời gian nhận thông báo offline

ai_running

AI có đang hoạt động hay không

runtime_config_version

Phiên bản AI đang báo sử dụng

updated_at

Lần cập nhật trạng thái gần nhất

Không sử dụng lại trường status của model thiết bị cũ để lưu Online/Offline, bởi trường đó có thể đang phục vụ nghiệp vụ quản lý thiết bị hoặc phương tiện.

Trạng thái kết nối mạng và trạng thái quản lý thiết bị là hai khái niệm khác nhau.

4.3. Nhật ký sự kiện (tùy chọn)

Có thể bổ sung bảng DeviceEventLog để ghi các sự kiện:

Kết nối thành công.

Mất kết nối.

Kết nối lại.

Đã áp dụng cấu hình.

Từ chối cấu hình.

Giai đoạn đầu chỉ cần lưu những sự kiện quan trọng, không cần lưu từng heartbeat vào database.

5. Quản lý 8 ngưỡng AI

5.1. Nhóm buồn ngủ

Tham số

Mặc định

Khoảng chỉnh đề xuất

DROWSY_CLOSED_SECONDS

1.5 s

1.0–3.0 s

YAWN_MIN_SECONDS

0.7 s

0.5–1.5 s

5.2. Nhóm mất tập trung

Tham số

Mặc định

Khoảng chỉnh đề xuất

YAW_AWAY_DEG

35°

25–50°

PITCH_AWAY_DOWN_DEG

30°

20–45°

LOOK_AWAY_SECONDS

2.0 s

1.5–4.0 s

5.3. Nhóm điện thoại và vật thể

Tham số

Mặc định

Khoảng chỉnh đề xuất

OBJECT_PHONE_NEAR_SECONDS

0.9 s

0.6–2.0 s

PHONE_INTERACTION_MIN_SECONDS

1.2 s

0.8–2.5 s

OBJECT_CONF

0.30

0.25–0.60

Tám ngưỡng này là tập cấu hình đã chọn dựa trên mã nguồn AI của nhóm.

Các khoảng chỉnh là giới hạn thử nghiệm đề xuất. Chúng cần được kiểm chứng trên thiết bị thật, không được xem là thông số an toàn giao thông đã được xác nhận.

5.4. Quy trình lưu cấu hình

Khi quản trị viên nhấn Lưu:

Django kiểm tra giá trị các ngưỡng.

Cập nhật bản ghi AIConfig.

Tăng desired_version.

Đặt sync_status = pending.

MQTT Worker nhận biết cấu hình mới.

Worker gửi bộ 8 ngưỡng đến Raspberry Pi.

Việc tăng phiên bản và lưu cấu hình cần thực hiện trong một transaction để tránh xung đột khi nhiều quản trị viên cùng chỉnh một thiết bị.

6. Thiết kế MQTT

6.1. MQTT Broker

Sử dụng EMQX Cloud:

Host: l9c60b66.ala.asia-southeast1.emqxsl.com

Port: 8883

Giao thức: MQTT qua TLS.

Thư viện: Paho MQTT.

Tài khoản xác thực: Cung cấp qua biến môi trường.

Django MQTT Worker và từng Raspberry Pi có MQTT Client ID riêng.

6.2. Quy tắc MQTT Topic

Với thiết bị R01:

Topic

Hướng

Mục đích

savelife/R01/config/desired

Server → Pi

Yêu cầu cập nhật cấu hình

savelife/R01/config/reported

Pi → Server

Kết quả áp dụng

savelife/R01/status

Pi → Server

Online / Offline

savelife/R01/heartbeat

Pi → Server

Báo thiết bị còn hoạt động

R02 có các topic tương tự, chỉ thay R01 bằng R02.

MQTT Worker dùng wildcard + để nhận phản hồi và trạng thái của nhiều thiết bị.

6.3. Payload cấu hình

Ví dụ Django gửi đến R01:

{
"device_id": "R01",
"config_version": 4,
"parameters": {
"DROWSY_CLOSED_SECONDS": 2.0,
"YAWN_MIN_SECONDS": 0.7,
"YAW_AWAY_DEG": 35.0,
"PITCH_AWAY_DOWN_DEG": 30.0,
"LOOK_AWAY_SECONDS": 2.0,
"OBJECT_PHONE_NEAR_SECONDS": 0.9,
"PHONE_INTERACTION_MIN_SECONDS": 1.2,
"OBJECT_CONF": 0.30
}
}

Đề xuất sử dụng:

QoS 1.

Retain = true.

Gửi đầy đủ 8 ngưỡng.

6.4. Payload phản hồi

Sau khi AI thực sự áp dụng cấu hình:

{
"device_id": "R01",
"config_version": 4,
"result": "applied"
}

Nếu thất bại:

{
"device_id": "R01",
"config_version": 4,
"result": "rejected",
"reason": "Invalid AI configuration"
}

Django chỉ xử lý phản hồi khi Device ID và phiên bản đều khớp với cấu hình mong muốn hiện tại.

Một phản hồi MQTT trùng lặp không được làm thay đổi sai trạng thái.

7. Giám sát và khắc phục tình trạng mất kết nối

Đây là chức năng mới được bổ sung vào hệ thống.

Mục tiêu không phải ngăn tuyệt đối việc mất Wi-Fi hoặc mất nguồn, mà là:

Phát hiện sự cố.

Thông báo cho quản trị viên.

Duy trì hoạt động AI khi mất mạng.

Tự kết nối lại.

Khôi phục việc đồng bộ cấu hình.

7.1. MQTT Last Will and Testament

Khi Raspberry Pi kết nối EMQX, thiết bị đăng ký trước một Last Will Message.

Ví dụ:

Topic:

savelife/R01/status

Payload:

{
"device_id": "R01",
"state": "offline",
"reason": "unexpected_disconnect"
}

Khi kết nối MQTT mất bất thường, Broker sẽ phát thông điệp offline theo cơ chế LWT.

Đề xuất sử dụng QoS 1 và Retain = true.

Nếu Raspberry Pi dừng chương trình đúng quy trình, thiết bị tự publish offline trước khi disconnect; LWT không được kích hoạt bởi một lần ngắt kết nối hợp lệ.

7.2. Keep Alive

Đề xuất cấu hình:

keepalive = 30 giây

Keep Alive giúp EMQX phát hiện một kết nối MQTT không còn phản hồi.

Thời điểm phát hiện không phải tức thời. Với Keep Alive 30 giây, Broker thường có thể xác định một kết nối im lặng sau khoảng 45 giây, tùy thời điểm mất mạng và cấu hình thực tế.

7.3. Auto Reconnect

MQTT Agent trên Pi phải tự kết nối lại.

Đề xuất:

Thời gian thử lại ban đầu: 1 giây.

Tăng dần khi liên tục thất bại.

Thời gian thử lại tối đa: 30 giây.

Sau khi kết nối lại, Pi phải subscribe lại topic cấu hình và gửi thông báo Online.

7.4. Heartbeat

Mỗi Raspberry Pi gửi heartbeat định kỳ để Django biết chương trình còn hoạt động.

Topic:

savelife/R01/heartbeat

Payload ví dụ:

{
"device_id": "R01",
"timestamp": "2026-11-22T10:00:00Z",
"ai_running": true,
"config_version": 4
}

Thông số đề xuất:

Chu kỳ gửi: 15 giây.

QoS 0.

Retain = false.

Mốc cảnh báo mất tín hiệu: 60 giây.

Django lưu thời điểm server nhận heartbeat, thay vì chỉ phụ thuộc đồng hồ của Raspberry Pi.

Trường ai_running phải được xác định từ tình trạng thật của chương trình AI; không được luôn gửi true theo mặc định.

7.5. Quy tắc trạng thái thiết bị

Đề xuất giao diện quản trị hiển thị:

Trạng thái

Điều kiện

Online

Kết nối được xác nhận và heartbeat còn mới

Offline

Nhận LWT hoặc thông báo ngắt kết nối hợp lệ

Mất tín hiệu

Không có heartbeat mới sau 60 giây

Không xác định

MQTT Worker của server mất kết nối hoặc chưa đủ dữ liệu

Trạng thái Online/Offline không đồng nghĩa với trạng thái AI Running/Stopped.

Một Raspberry Pi có thể kết nối MQTT bình thường nhưng chương trình AI đã bị treo.

Khi MQTT Worker của Django mất kết nối EMQX, không được tự động kết luận tất cả Raspberry Pi đều Offline.

Các retained status message có thể là trạng thái cũ. Do đó, dashboard không nên chỉ dựa vào một bản retained online; phải kiểm tra heartbeat và tình trạng kết nối của Worker.

7.6. Khôi phục cấu hình sau mất mạng

Giả sử R01 đang sử dụng phiên bản 4 và Django gửi phiên bản 5 đúng lúc Pi mất Internet.

Quy trình:

Django lưu version 5 vào PostgreSQL.

Worker publish version 5 dưới dạng retained message.

Pi mất mạng, tiếp tục sử dụng cấu hình version 4.

Khi mạng trở lại, Agent tự kết nối EMQX.

Pi subscribe lại và nhận version 5.

AI áp dụng version 5.

Pi publish applied cho version 5.

Django cập nhật trạng thái Đã áp dụng.

Nếu Pi đã áp dụng nhưng chưa gửi được ACK, thiết bị cần gửi lại xác nhận sau khi kết nối lại.

MQTT QoS 1 và Retained Message không thay thế việc lưu cấu hình bền vững trong Raspberry Pi. Thiết bị vẫn cần lưu cấu hình hợp lệ cục bộ.

7.7. Tự phục hồi khi chương trình lỗi

Ngoài Auto Reconnect của MQTT, Raspberry Pi nên sử dụng systemd để tự khởi động lại MQTT Agent khi tiến trình bị crash.

Nếu mất điện hoàn toàn, các cơ chế MQTT không thể duy trì thiết bị đang chạy. Khi được cấp nguồn lại, systemd giúp dịch vụ tự khởi động và phục hồi kết nối.

8. Thiết kế giao diện quản trị SaveLife

Phân hệ mới được tích hợp vào giao diện quản trị hiện tại, sử dụng chung tài khoản và quyền truy cập.

Đề xuất bổ sung một mục menu:

Thiết bị IoT

Bên trong gồm hai màn hình chính.

8.1. Màn hình tổng quan thiết bị

Hiển thị bảng danh sách R01, R02, R03...

Thiết bị

Kết nối

AI

Cấu hình

Heartbeat cuối

R01

Online

Đang chạy

v4 – Đã áp dụng

5 giây trước

R02

Offline

Không xác định

v2 – Đã áp dụng trước đó

3 phút trước

R03

Mất tín hiệu

Không xác định

v5 – Chờ xác nhận

75 giây trước

Có thể hiển thị thêm các chỉ số tổng quan:

Tổng số thiết bị.

Số thiết bị Online.

Số thiết bị Offline.

Số thiết bị mất tín hiệu.

Số thiết bị có cấu hình chưa đồng bộ.

8.2. Màn hình chi tiết thiết bị

Khi bấm vào R01, hiển thị:

Khu vực 1 – Thông tin thiết bị

Mã thiết bị.

Tên thiết bị.

Phương tiện đang gắn.

Tình trạng kết nối.

Lần heartbeat gần nhất.

Khu vực 2 – Cấu hình AI

Biểu mẫu chỉnh 8 ngưỡng, chia theo ba nhóm:

Buồn ngủ.

Mất tập trung.

Điện thoại và vật thể.

Khu vực 3 – Đồng bộ

Desired Version.

Applied Version.

Trạng thái Pending / Sent / Applied / Rejected.

Lần cập nhật gần nhất.

Thông báo lỗi, nếu có.

Khu vực 4 – Hoạt động

Kết nối.

Mất kết nối.

Kết nối lại.

Cập nhật cấu hình thành công hoặc thất bại.

Dashboard có thể sử dụng JavaScript polling mỗi 5 giây để cập nhật trạng thái. Giai đoạn này chưa bắt buộc dùng WebSocket giữa trình duyệt và Django.

9. MQTT Worker phía Django

9.1. Nhiệm vụ

MQTT Worker là một Django management command chạy độc lập với Web Server.

Nó đảm nhiệm:

Kết nối EMQX Cloud qua TLS.

Subscribe topic config/reported.

Subscribe topic status.

Subscribe topic heartbeat.

Kiểm tra cấu hình mới trong PostgreSQL.

Publish cấu hình theo đúng Device ID.

Xử lý phản hồi và cập nhật database.

Tự kết nối lại khi mất kết nối EMQX.

9.2. Cách chạy

Trong môi trường phát triển, có hai tiến trình:

Tiến trình 1 – Django Web

python manage.py runserver

Tiến trình 2 – MQTT Worker

python manage.py mqtt_worker

Khi triển khai lên server, MQTT Worker phải được chạy bằng một dịch vụ hoặc trình quản lý tiến trình độc lập, có khả năng restart.

Không chỉ chạy MQTT Worker trong terminal của laptop nếu muốn thiết bị tiếp tục được quản lý khi laptop tắt.

Không chạy nhiều Worker cùng Client ID. Nếu cần nhiều Worker, phải bổ sung cơ chế phối hợp để tránh gửi và xử lý trùng.

9.3. Độ tin cậy dữ liệu

Worker phải phân biệt:

Đã publish: Broker xác nhận nhận thông điệp.

Đã áp dụng: AI trên Raspberry Pi xác nhận sử dụng cấu hình.

Hai sự kiện này không giống nhau.

Các phản hồi cũ hoặc không khớp phiên bản phải bị bỏ qua.

10. Công việc phía Raspberry Pi

Phía Raspberry Pi cần triển khai một MQTT Agent và một cơ chế cấu hình động trong AI.

10.1. MQTT Agent

Chịu trách nhiệm:

Kết nối EMQX.

Đăng ký Last Will.

Subscribe cấu hình.

Gửi Online / Offline.

Gửi Heartbeat.

Tự Reconnect.

Lưu JSON.

Gửi ACK.

10.2. AI Runtime Configuration

Chịu trách nhiệm:

Nhận bộ 8 tham số mới từ Agent.

Kiểm tra giới hạn.

Áp dụng vào các thành phần AI đang chạy.

Xử lý lại trạng thái theo thời gian nếu cần.

Xác nhận phiên bản đã áp dụng.

Trong mã nguồn AI hiện tại, có những ngưỡng được đọc lúc khởi tạo đối tượng hoặc import module. Phía Pi cần sửa cơ chế này để cập nhật nóng thực sự.

10.3. Lưu cấu hình cục bộ

Đề xuất duy trì:

desired_config.json: cấu hình mới đã tiếp nhận.

applied_config.json: cấu hình AI đã xác nhận áp dụng.

Khi khởi động, Pi sử dụng cấu hình hợp lệ đã lưu thay vì phụ thuộc vào việc EMQX có kết nối được ngay hay không.

11. Kế hoạch triển khai

Giai đoạn A – Chuẩn bị tích hợp Django

Công việc:

Sao lưu mã nguồn và database hiện tại.

Tạo nhánh Git riêng để phát triển.

Kiểm tra model thiết bị và giao diện admin hiện có.

Tạo app device_control.

Thiết kế model cấu hình và trạng thái.

Chạy migrations và kiểm tra quan hệ với thiết bị R01/R02.

Kết quả: Django chính quản lý được dữ liệu cấu hình và trạng thái của thiết bị mà không phải tạo lại thiết bị.

Giai đoạn B – Giao diện quản trị

Công việc:

Bổ sung menu Thiết bị IoT.

Xây dựng trang tổng quan.

Xây dựng trang cấu hình 8 ngưỡng.

Áp dụng quyền truy cập của hệ thống quản trị hiện tại.

Thêm kiểm tra dữ liệu và phiên bản.

Kết quả: Quản trị viên chỉnh được cấu hình R01 trực tiếp trên website SaveLife.

Giai đoạn C – MQTT và đồng bộ cấu hình

Công việc:

Đưa MQTT Worker vào Django chính.

Kết nối EMQX.

Publish cấu hình theo topic R01/R02.

Subscribe phản hồi.

Cập nhật trạng thái đồng bộ.

Kiểm tra bằng MQTTX trước khi kết nối Pi.

Kết quả: Django gửi đúng JSON và nhận đúng phản hồi theo phiên bản.

Giai đoạn D – Giám sát kết nối

Công việc:

Pi đăng ký LWT.

Pi publish Online / Offline.

Pi publish Heartbeat.

Worker lưu trạng thái và thời điểm nhận.

Dashboard hiển thị kết nối.

Xử lý trường hợp heartbeat quá hạn.

Kiểm tra mất kết nối ở phía Worker.

Kết quả: Quản trị viên theo dõi được trạng thái kết nối của R01/R02.

Giai đoạn E – Tích hợp AI Runtime

Công việc:

Pi tiếp nhận 8 ngưỡng.

Cập nhật trực tiếp thuật toán AI.

Xác nhận áp dụng.

Lưu cấu hình bền vững.

Khởi phục cấu hình sau reboot.

Kết quả: Thay ngưỡng trên web làm thay đổi hành vi xử lý của AI thật.

Giai đoạn F – Kiểm thử độ ổn định

Công việc:

Ngắt Wi-Fi khi đang chạy.

Ngắt mạng giữa lúc nhận cấu hình.

Khôi phục kết nối.

Khởi động lại Raspberry Pi.

Tắt tiến trình MQTT Agent bất thường.

Tắt tiến trình AI nhưng giữ MQTT Agent.

Thử cấu hình không hợp lệ.

Thử nhiều thiết bị đồng thời.

Kết quả: Hệ thống tự phục hồi và không báo sai trạng thái đã áp dụng.

12. Tiêu chí nghiệm thu

STT

Tình huống

Kết quả mong đợi

1

Admin mở danh sách thiết bị

R01/R02 hiện từ database SaveLife

2

Admin thay ngưỡng R01

Django tạo phiên bản mới

3

R01 nhận cấu hình

R02 không nhận nhầm

4

AI áp dụng ngưỡng

Pi gửi ACK đúng version

5

Pi mới nhận JSON nhưng AI chưa cập nhật

Django chưa báo Applied

6

R01 mất mạng đột ngột

EMQX phát LWT Offline

7

R01 kết nối lại

Dashboard cập nhật Online

8

Không có heartbeat quá 60 giây

Dashboard hiển thị Mất tín hiệu

9

MQTT Worker mất kết nối

Không kết luận toàn bộ Pi Offline

10

R01 offline khi Django gửi cấu hình

Cấu hình mới được lưu retained

11

R01 kết nối lại

Nhận và áp dụng cấu hình mới nhất

12

R01 khởi động lại

Giữ cấu hình hợp lệ trước đó

13

R01 nhận cấu hình sai

Không làm hỏng cấu hình đang chạy

14

Hai thiết bị hoạt động đồng thời

Trạng thái và cấu hình không bị lẫn

13. Các rủi ro cần lưu ý

Rủi ro 1 – Gộp hai Django làm ảnh hưởng website cũ

Giải pháp: Thêm app mới vào dự án hiện tại, tránh sửa trực tiếp logic tài xế, phương tiện và vi phạm nếu không cần thiết.

Rủi ro 2 – Mất dữ liệu cấu hình từ website độc lập

Giải pháp: Giữ schema và source cũ cho đến khi kiểm tra xong việc chuyển dữ liệu. Chỉ ngừng Worker cũ sau khi Worker mới hoạt động đúng.

Rủi ro 3 – MQTT báo đã gửi nhưng Pi chưa áp dụng

Giải pháp: Chỉ chuyển trạng thái Applied khi có ACK đúng phiên bản từ AI.

Rủi ro 4 – Broker vẫn lưu trạng thái Online cũ

Giải pháp: Không chỉ dựa vào retained status; sử dụng heartbeat, thời gian nhận và trạng thái kết nối của Worker.

Rủi ro 5 – AI hoạt động nhưng không cập nhật ngưỡng

Giải pháp: Phải bổ sung Runtime Configuration vào các thành phần AI đang dùng các ngưỡng.

Rủi ro 6 – Ghi trùng dữ liệu vi phạm

Giải pháp: Tiếp tục sử dụng luồng lưu vi phạm của SaveLife hiện có. Giai đoạn này chỉ thêm trạng thái thiết bị và cấu hình, không tạo thêm một hệ thống lưu vi phạm song song.

14. Phân công triển khai

Thành phần

Người phụ trách

Tích hợp Django app

Backend Web

Database và migrations

Backend Web

Giao diện quản trị

Frontend / Backend Web

MQTT Worker

Backend Web

MQTT Agent

Raspberry Pi

LWT, Heartbeat, Reconnect

Raspberry Pi và Backend Web

Cập nhật 8 ngưỡng vào AI

Raspberry Pi / AI

Kiểm thử tích hợp

Cả hai bên

15. Kết luận

Phương án tích hợp AI Configuration và MQTT Connection Monitoring vào website SaveLife hiện tại giúp hệ thống có một giao diện quản trị thống nhất, tái sử dụng danh sách thiết bị và tài khoản quản trị sẵn có.

Phân hệ mới cho phép quản trị viên chỉnh thông số AI từ xa, biết thiết bị nào đang kết nối, phát hiện các trường hợp mất mạng và theo dõi quá trình tự phục hồi.

Hệ thống sử dụng PostgreSQL Render để lưu cấu hình và trạng thái, EMQX Cloud để truyền thông, Django MQTT Worker để xử lý thông điệp và Raspberry Pi MQTT Agent để nhận lệnh, báo trạng thái.

Kết quả cần đạt cuối cùng:

Quản trị viên mở website SaveLife → chọn R01 → chỉnh ngưỡng AI → Django gửi MQTT → Raspberry Pi áp dụng → Django xác nhận thành công.

Đồng thời, khi R01 mất mạng hoặc mất nguồn, hệ thống phát hiện tình trạng kết nối, hiển thị cảnh báo và tự đồng bộ lại cấu hình khi thiết bị hoạt động trở lại.

Đây là phạm vi triển khai của phân hệ SaveLife IoT Device Management – Giai đoạn 1.
