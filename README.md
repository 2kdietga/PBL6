# Hệ thống quản lý và giám sát tài xế lái xe

## 1. Giới thiệu

Đồ án xây dựng hệ thống quản lý và giám sát tài xế cho một công ty vận tải.

Hệ thống cho phép:

- Quản lý tài khoản và hồ sơ tài xế.
- Quản lý 1 giấy phép lái xe (GPLX) cho mỗi tài xế.
- Lưu ảnh GPLX và ảnh khuôn mặt trên Cloudinary.
- Tích hợp API tạo và xác thực face embedding.
- Quản lý nhiều loại xe và phương tiện.
- Quản lý quyền tài xế được phép lái từng xe theo thời gian.
- Tạo phiên lái xe khi tài xế bắt đầu/kết thúc lái.
- Nhận dữ liệu vi phạm từ hệ thống AI chạy trên Raspberry Pi.
- Lưu bằng chứng vi phạm bằng hình ảnh/video.
- Cho Admin duyệt hoặc từ chối vi phạm.
- Cho tài xế xem vi phạm và gửi kháng cáo một lần.
- Hỗ trợ Admin theo dõi thiết bị Raspberry Pi.
- Có thể mở rộng livestream và cảnh báo bằng loa ở các giai đoạn sau.

> **Phạm vi đồ án:** tập trung vào Backend/Django, cơ sở dữ liệu, nghiệp vụ và tích hợp API. AI và Raspberry Pi là các thành phần cung cấp dữ liệu cho hệ thống, không phải phần phải tự xây dựng thuật toán AI từ đầu.

---

## 2. Mục tiêu

### 2.1. Mục tiêu chính

Xây dựng một backend có khả năng quản lý xuyên suốt quy trình:

```text
Đăng ký tài xế
      ↓
Duyệt hồ sơ
      ↓
Quản lý GPLX + khuôn mặt
      ↓
Quản lý xe + quyền được lái
      ↓
Xác thực trước khi lái
      ↓
Tạo phiên lái
      ↓
AI phát hiện vi phạm
      ↓
Lưu vi phạm + bằng chứng
      ↓
Admin duyệt
      ↓
Tài xế xem / kháng cáo
```

### 2.2. Mục tiêu kỹ thuật

- Thiết kế cơ sở dữ liệu quan hệ phù hợp nghiệp vụ.
- Xây dựng REST API bằng Django.
- Sử dụng PostgreSQL.
- Phân quyền `ADMIN` và `USER`.
- Tích hợp Cloudinary.
- Tích hợp Face Embedding API.
- Nhận dữ liệu từ hệ thống AI/Raspberry Pi.
- Áp dụng validation, constraint và business rule ở server.
- Thiết kế theo hướng có thể mở rộng nhưng không vượt quá phạm vi đồ án học kỳ.

---

# 3. Phạm vi hệ thống

## 3.1. Đối tượng sử dụng

Chỉ có 2 role:

| Role | Mô tả |
|---|---|
| `ADMIN` | Quản lý toàn bộ hệ thống |
| `USER` | Tài xế |

Hệ thống chỉ phục vụ **một công ty vận tải**.

---

## 3.2. Chức năng của tài xế

Tài xế có thể:

- Đăng ký tài khoản.
- Cập nhật hồ sơ cá nhân.
- Cập nhật GPLX.
- Upload ảnh trước/sau GPLX.
- Upload ảnh khuôn mặt.
- Xem trạng thái duyệt hồ sơ.
- Xem các xe hiện đang được giao quyền sử dụng.
- Bắt đầu phiên lái.
- Kết thúc phiên lái của chính mình.
- Xem các vi phạm của chính mình.
- Xem bằng chứng của vi phạm.
- Gửi kháng cáo cho vi phạm đã được Admin duyệt.
- Chỉ được kháng cáo một lần cho mỗi vi phạm.

---

## 3.3. Chức năng của Admin

Admin có thể:

- Quản lý tài khoản.
- Disable tài khoản.
- Duyệt hồ sơ tài xế.
- Duyệt thông tin/GPLX được cập nhật.
- Quản lý loại xe.
- Quản lý phương tiện.
- Quản lý thiết bị trên xe.
- Gán tài xế vào xe theo thời gian.
- Quản lý các phiên lái.
- Xem vi phạm.
- Duyệt/từ chối vi phạm.
- Ghi `admin_note` cho vi phạm.
- Quản lý loại vi phạm.
- Xem bằng chứng.
- Xử lý kháng cáo.
- Xem embedding của tài xế.
- Xem livestream thiết bị nếu tính năng này được triển khai.

---

# 4. Kiến trúc tổng quan

```text
                         WEB
                          │
              ┌───────────┴───────────┐
              │                       │
           DRIVER                    ADMIN
              │                       │
              └───────────┬───────────┘
                          │
                    DJANGO SERVER
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
        PostgreSQL    Cloudinary    External APIs
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                    Face API                 AI / Raspberry Pi
                                                   │
                                                Camera
```

### Vai trò của các thành phần

#### Django Server

Là thành phần trung tâm:

- Authentication.
- Authorization.
- Business logic.
- REST API.
- Validation.
- Lưu dữ liệu.
- Nhận dữ liệu từ AI.
- Gọi Face API.
- Kiểm tra điều kiện trước khi cho phép lái.

#### PostgreSQL

Lưu:

- Tài khoản.
- Hồ sơ.
- GPLX.
- Face profile.
- Xe.
- Quyền sử dụng xe.
- Phiên lái.
- Vi phạm.
- Evidence metadata.
- Appeal.

#### Cloudinary

Lưu file:

- Ảnh GPLX.
- Ảnh khuôn mặt.
- Ảnh vi phạm.
- Video vi phạm.

Database chỉ lưu URL/public ID và metadata cần thiết.

#### Face API

Nhận ảnh khuôn mặt và trả về embedding.

Khi xác thực trước khi lái, hệ thống dùng embedding để kiểm tra người đang xác thực có đúng tài xế hay không.

#### Raspberry Pi + AI

- Camera thu hình.
- AI phát hiện hành vi vi phạm.
- Gửi thông tin vi phạm về Django.
- Có thể gửi bằng chứng.
- Có thể mở rộng thành thiết bị livestream.

---

# 5. Domain Model

Hệ thống hiện tại có các entity chính:

```text
1. User
2. DriverProfile
3. DriverLicense
4. FaceProfile
5. VehicleType
6. Vehicle
7. DriverVehicleAssignment
8. Device
9. DrivingSession
10. ViolationType
11. Violation
12. Evidence
13. Appeal
```

---

# 6. Quan hệ chính

```text
User
 │
 └── 0..1 DriverProfile
          │
          ├── N DriverLicense
          │
          ├── 1 FaceProfile
          │
          └── N DriverVehicleAssignment
                       │
                       └── Vehicle
                            │
                            ├── VehicleType
                            │
                            └── N Device

DriverVehicleAssignment
          │
          └── N DrivingSession
                    │
                    └── N Violation
                           │
                           ├── ViolationType
                           │
                           ├── N Evidence
                           │
                           └── 0..1 Appeal
```

---

# 7. Mô tả Entity

## 7.1. User

Tài khoản đăng nhập.

Thông tin chính:

```text
id
username
email
password
role
is_active
created_at
updated_at
```

Role:

```text
ADMIN
USER
```

`is_active = false` nghĩa là tài khoản bị disable và không được đăng nhập.

Django Custom User Model sẽ được sử dụng thay vì tự xây hệ thống authentication.

---

## 7.2. DriverProfile

Thông tin nghiệp vụ của tài xế.

```text
id
user_id
full_name
date_of_birth
phone
address
approval_status
created_at
updated_at
```

Quan hệ:

```text
User 1 ─── 0..1 DriverProfile
```

Trạng thái hồ sơ:

```text
PENDING
APPROVED
```

Chỉ những thông tin quan trọng của hồ sơ mới cần Admin duyệt lại. Ví dụ `full_name`, `date_of_birth` là thông tin quan trọng; `phone`, `address` có thể cập nhật trực tiếp.

Nếu thông tin quan trọng được cập nhật:

```text
APPROVED
    ↓
PENDING
    ↓
Admin review
    ↓
APPROVED / REJECTED
```

Khi bị `REJECTED`, thông tin mới vẫn được giữ lại để tài xế có thể sửa và gửi lại.

---

## 7.3. DriverLicense

Mỗi tài xế chỉ có **1 GPLX** trong hệ thống.

```text
id
driver_id
license_number
license_class
issued_date
expiry_date
front_image
back_image
status
created_at
updated_at
```

Quan hệ:

```text
Driver 1 ─── 1 DriverLicense
```

Trạng thái:

```text
PENDING
ACTIVE
EXPIRED
REJECTED
```

Khi tài xế cập nhật GPLX, vẫn sử dụng **record GPLX hiện tại**, không tạo record mới. Thông tin cập nhật chuyển về `PENDING` và phải được Admin duyệt lại.

Nếu bị `REJECTED`, thông tin mới vẫn được giữ lại để tài xế có thể sửa và gửi lại.

Ảnh được lưu trên Cloudinary.

---

## 7.4. FaceProfile

Lưu thông tin khuôn mặt hiện tại của tài xế.

```text
id
driver_id
image_url
cloudinary_public_id
embedding
approval_status
created_at
updated_at
```

Quan hệ:

```text
DriverProfile 1 ─── 1 FaceProfile
```

Mỗi tài xế chỉ có **1 FaceProfile hiện tại**. Khi cập nhật khuôn mặt, cập nhật profile hiện tại, không lưu lịch sử FaceProfile trong Core.

Face mới phải được Admin duyệt trước khi được sử dụng để xác thực.

Embedding được lưu trong PostgreSQL bằng pgvector.

Số chiều của vector phải khớp với Face API thực tế.

---

## 7.5. VehicleType

Định nghĩa nhóm phương tiện.

```text
id
name
category
description
created_at
updated_at
```

`category` chỉ có 2 loại trong Core:

```text
TRUCK
BUS
```

Thông số dùng để xác định hạng GPLX thuộc về từng `Vehicle` cụ thể, không thuộc `VehicleType`.

Chưa tạo entity `LicenseClass` riêng trong phiên bản đầu.

---

## 7.6. Vehicle

Một phương tiện cụ thể.

```text
id
vehicle_type_id
license_plate
brand
model
manufacture_year
load_capacity
passenger_capacity
status
description
created_at
updated_at
```

`VehicleType` xác định xe là `TRUCK` hay `BUS`.

Thông số thực tế của từng xe:

- `TRUCK` → dùng `load_capacity` để xác định hạng GPLX cần thiết.
- `BUS` → dùng `passenger_capacity` (số chỗ ngồi/nằm) để xác định hạng GPLX cần thiết.

Hạng GPLX cần thiết được xác định bằng business logic của server, không lưu cố định thành một field trong `VehicleType`.

Trạng thái:

```text
ACTIVE
INACTIVE
LIQUIDATED
```

`LIQUIDATED` nghĩa là xe đã thanh lý và không còn được phép phát sinh nghiệp vụ sử dụng mới. Dữ liệu lịch sử của xe vẫn được giữ trong database.

---

## 7.7. DriverVehicleAssignment

Biểu diễn quyền tài xế được phép sử dụng xe trong một khoảng thời gian.

```text
id
driver_id
vehicle_id
start_at
end_at
created_at
updated_at
```

Quan hệ:

```text
Driver N ─── N Vehicle
       thông qua
DriverVehicleAssignment
```

Một tài xế có thể được giao nhiều xe.

Một xe có thể được giao cho nhiều tài xế, kể cả trong cùng một khoảng thời gian.

`end_at` có thể là `NULL`. Khi đó tài xế được giao xe nhưng **chưa có ngày kết thúc**.

Assignment hết hạn không bị xóa để giữ lịch sử.

Server xác định Assignment còn hiệu lực bằng:

```text
start_at <= current_time
AND
(end_at IS NULL OR current_time <= end_at)
```

Không lưu `is_active` để tránh trạng thái mâu thuẫn với thời gian.

---

## 7.8. Device

Thiết bị Raspberry Pi/camera trên xe.

```text
id
vehicle_id
device_code
name
status
last_seen_at
created_at
updated_at
```

Quan hệ:

```text
Vehicle 1 ─── 0..1 Device
```

Một xe có tối đa **1 Device**. Khi tạo xe không bắt buộc phải có Device; Admin có thể gắn Device sau.

Trạng thái:

```text
ONLINE
OFFLINE
MAINTENANCE
```

Trong Core không cần lưu lịch sử thay thế Device.

---

## 7.9. DrivingSession

Một lần tài xế thực sự lái xe.

```text
id
assignment_id
started_at
ended_at
status
created_at
updated_at
```

Trạng thái:

```text
STARTED
ENDED
```

Session được tạo sau khi server kiểm tra đủ điều kiện.

Chỉ chính tài xế đang có Session `STARTED` mới được phép kết thúc Session đó.

Session đã `ENDED` không được sửa hoặc xóa, nhằm giữ lịch sử chính xác.

---

## 7.10. ViolationType

Danh mục loại lỗi.

```text
id
code
name
description
created_at
updated_at
```

Ví dụ:

```text
DROWSINESS
SLEEPING
PHONE_USAGE
DISTRACTION
LOOKING_BACK
```

Nếu AI gửi loại lỗi mới chưa tồn tại, Server có thể tạo thêm `ViolationType`.

`code` phải được chuẩn hóa và unique.

---

## 7.11. Violation

Một lỗi do AI phát hiện trong một DrivingSession đang `STARTED`.

```text
id
session_id
violation_type_id
severity
detected_at
status
admin_note
created_at
updated_at
```

Trạng thái:

```text
PENDING
APPROVED
REJECTED
REVOKED
```

AI cung cấp thông tin Violation gồm:

```text
session_id
driver_id
vehicle_id
violation_type
severity
detected_at
evidence
```

Server phải đối chiếu `session_id`, `driver_id` và `vehicle_id`. Session tương ứng phải đang `STARTED`; nếu Session đã `ENDED` thì từ chối tạo Violation.

`detected_at` do AI cung cấp và được lưu nguyên giá trị. Không cần đối chiếu `detected_at` với `end_at` của Session.

Hiện tại severity có thể dùng:

```text
LOW
MEDIUM
HIGH
```

Danh sách severity có thể được bổ sung thêm trong tương lai.

Việc tạo Violation không triển khai idempotency/fingerprint trong Core. Nếu AI gửi trùng request, hệ thống hiện tại chấp nhận khả năng tạo Violation trùng.

Admin khi review có thể:

- Sửa `violation_type`.
- Sửa `severity`.
- Ghi `admin_note` hoặc để `NULL`.
- Approve.
- Reject.

Admin không được sửa `detected_at`.

Admin có thể xóa thủ công Violation ở **mọi trạng thái**. Khi xóa Violation, các Evidence và Appeal thuộc Violation đó cũng được xóa theo.

Violation `REJECTED` có thể được Admin chọn `Xem xét lại` để đưa về `PENDING`. Violation `APPROVED` và `REVOKED` cũng có thể được `Xem xét lại`; `PENDING` không cần action này.

---

## 7.12. Evidence

Bằng chứng của một vi phạm. Một Violation bắt buộc phải có ít nhất một Evidence.

```text
id
violation_id
type
url
cloudinary_public_id
captured_at
```

Loại:

```text
IMAGE
VIDEO
```

Một Violation có thể có nhiều Evidence, gồm nhiều ảnh, video, hoặc kết hợp cả hai.

`captured_at` là thời điểm Evidence được ghi nhận. Không cần `created_at` cho Evidence trong Core.

Evidence không cho Admin sửa/xóa trong Core. Nếu Violation bị `REJECTED`, Evidence vẫn được giữ. Chỉ khi Violation bị Admin xóa thủ công thì Evidence liên quan mới bị xóa theo.

Khi tạo Violation, flow ưu tiên tạo Violation trước rồi mới upload/tạo Evidence. Nếu upload Evidence thất bại, Violation `PENDING` vẫn được giữ lại; chưa thiết kế tiếp cách bổ sung/retry Evidence ở giai đoạn này.

Ví dụ:

```text
Violation
 ├── Image
 ├── Image
 └── Video
```

---

## 7.13. Appeal

Kháng cáo của tài xế.

```text
id
violation_id
content
status
admin_response
created_at
updated_at
resolved_at
```

Trạng thái:

```text
PENDING
APPROVED
REJECTED
```

Một Violation chỉ được Appeal **một lần**.

Database phải đảm bảo:

```text
UNIQUE(violation_id)
```

Tài xế chỉ được kháng cáo Violation đã được Admin `APPROVED`. Sau khi Appeal đã được tạo, Driver không được sửa `content`. Admin cũng không được sửa `content`.

`admin_response` có thể `NULL`. Khi Admin xử lý Appeal, Server ghi thời điểm vào `resolved_at`. Appeal đã xử lý vẫn có thể được Admin sửa thủ công `status` và `admin_response`. Việc thay đổi Appeal sau khi xử lý chưa quy định cách tự động đồng bộ lại trạng thái Violation.

Admin có thể xóa Appeal thủ công. Việc xóa Appeal không làm thay đổi trạng thái Violation và không mở lại quyền Appeal lần nữa.

Nếu Appeal được `APPROVED`, Violation chuyển từ `APPROVED` sang `REVOKED`. Nếu Appeal bị `REJECTED`, Violation vẫn `APPROVED`. Khi Violation `REVOKED`, Driver không còn nhìn thấy Violation, Evidence hoặc Appeal; Admin vẫn xem được dữ liệu.

Việc Appeal thành công làm Violation `REVOKED`, nhưng hiện tại Violation `REVOKED` vẫn có thể được Admin `Xem xét lại` để đưa về `PENDING`; cách xử lý Appeal cũ trong trường hợp này sẽ được chốt sau.

---

# 8. Các Business Rule chính

## BR-01 — Tài khoản

`is_active = false` → không được đăng nhập.

## BR-02 — Hồ sơ

Driver phải có `DriverProfile` và hồ sơ phải `APPROVED` trước khi lái.

## BR-03 — GPLX

GPLX phải:

- Được Admin duyệt.
- Chưa hết hạn.
- Đủ hạng để điều khiển loại xe.

Hạng GPLX cần thiết được server xác định dựa trên thông số của từng Vehicle:

- `TRUCK` → dựa trên `load_capacity`.
- `BUS` → dựa trên `passenger_capacity`.

Server áp dụng logic phân cấp hạng GPLX để xác định Driver có đủ điều kiện hay không.

## BR-04 — Quyền lái

Driver chỉ được lái Vehicle nếu có Assignment còn hiệu lực.

## BR-05 — Vehicle

Vehicle phải ở trạng thái `ACTIVE` mới được bắt đầu Session.

Vehicle `INACTIVE` hoặc `LIQUIDATED` không được phát sinh nghiệp vụ sử dụng mới.

Vehicle `LIQUIDATED` vẫn giữ toàn bộ dữ liệu lịch sử.

## BR-06 — Face

FaceProfile phải được Admin duyệt và Face verification phải thành công trước khi bắt đầu Session.

## BR-07 — Session

Một Vehicle không được có hai DrivingSession đang `STARTED` đồng thời.

## BR-08 — Violation

Violation do AI tạo luôn bắt đầu ở `PENDING` và phải thuộc một DrivingSession đang `STARTED`.

## BR-09 — Evidence

Mỗi Violation bắt buộc có ít nhất một Evidence. Evidence có hai loại `IMAGE` và `VIDEO`. File được lưu trên Cloudinary, PostgreSQL lưu metadata/reference.

## BR-10 — Appeal

Chỉ Violation đã `APPROVED` mới được kháng cáo và mỗi Violation chỉ được Appeal một lần.

## BR-11 — Violation Review

Admin có thể chỉnh `violation_type`, `severity` và `admin_note` khi review. `detected_at` không được chỉnh. `admin_note` có thể `NULL`.

Admin có thể `Xem xét lại` Violation ở `APPROVED`, `REJECTED` hoặc `REVOKED` để đưa về `PENDING`. `PENDING` không cần action `Xem xét lại`.

## BR-12 — Violation Delete

Admin có thể xóa thủ công Violation ở mọi trạng thái. Khi xóa, Evidence và Appeal liên quan cũng được xóa theo.

## BR-13 — Appeal Review

Appeal có các trạng thái `PENDING`, `APPROVED`, `REJECTED`. Khi xử lý, Server ghi `resolved_at`. `admin_response` có thể `NULL`.

Nếu Appeal `APPROVED` → Violation `REVOKED`. Nếu Appeal `REJECTED` → Violation giữ `APPROVED`.

## BR-14 — Quyền xem của Driver

Driver chỉ xem được Violation của chính mình ở trạng thái `PENDING` và `APPROVED`, kèm Evidence tương ứng.

Driver không xem được Violation `REJECTED` hoặc `REVOKED`. Khi `REVOKED`, Driver cũng không xem Appeal liên quan.

## BR-15 — AI data

AI gửi:

```text
session_id
driver_id
vehicle_id
violation_type
severity
detected_at
evidence
```

Server đối chiếu `session_id`, `driver_id`, `vehicle_id`; Session phải đang `STARTED`. `detected_at` lấy từ AI. Không triển khai idempotency/fingerprint trong Core.

Nếu AI gửi `ViolationType` chưa tồn tại, Server tự động tạo từ `code`, `name`, `description` mà AI cung cấp. `code` phải unique.

## BR-16 — ViolationType

Admin được sửa `code`, `name`, `description` của ViolationType. `code` vẫn phải unique.

Admin chỉ được xóa ViolationType nếu chưa có Violation nào sử dụng. Nếu đã được sử dụng thì không được xóa. Violation tham chiếu theo `violation_type_id`, vì vậy khi ViolationType được sửa, các Violation đang tham chiếu sẽ sử dụng thông tin mới.

## BR-17 — Assignment

Assignment hết hạn không bị xóa.

`end_at = NULL` nghĩa là Assignment chưa có ngày kết thúc.

Server kiểm tra thời gian để xác định quyền hiện tại.

---

# 9. State Machine

## Driver Profile

```text
PENDING
   ↓
APPROVED
```

## Driver License

```text
PENDING
   ├──→ ACTIVE
   └──→ REJECTED

ACTIVE
   ↓
EXPIRED
```

## Driving Session

```text
STARTED
   ↓
ENDED
```

## Violation

```text
              ┌──────────────┐
              │    PENDING   │
              └──────┬───────┘
                 APPROVE│REJECT
                       ↓
              ┌────────┴────────┐
              ↓                 ↓
          APPROVED           REJECTED
              │                 │
              │            Xem xét lại
              │                 │
              └───────┬─────────┘
                      ↓
                   PENDING

APPROVED ── Appeal APPROVED ──→ REVOKED
REVOKED  ── Xem xét lại ──────→ PENDING
```

`APPROVED`, `REJECTED` và `REVOKED` đều có thể được Admin `Xem xét lại` để đưa về `PENDING`. `PENDING` không cần action này.

## Appeal

```text
PENDING
   ├──→ APPROVED
   └──→ REJECTED
```

Mỗi Violation chỉ được Appeal một lần.

---

# 10. Quy trình bắt đầu lái

```text
Driver nhấn START
        ↓
Kiểm tra User.is_active
        ↓
Kiểm tra DriverProfile
        ↓
Kiểm tra Assignment
        ↓
Kiểm tra Vehicle
        ↓
Kiểm tra GPLX
        ↓
Kiểm tra hạng GPLX
        ↓
Face Verification
        ↓
       OK?
      /   \
    NO     YES
    ↓       ↓
 Từ chối   Tạo DrivingSession
```

---

# 11. Quy trình AI tạo vi phạm

```text
Camera
   ↓
Raspberry Pi
   ↓
AI
   ↓
Phát hiện vi phạm
   ↓
Gửi API Django
   ↓
Validate request
   ↓
Đối chiếu session_id + driver_id + vehicle_id
   ↓
Kiểm tra DrivingSession = STARTED
   ↓
Tìm / tự tạo ViolationType
   ↓
Create Violation
   ↓
PENDING
   ↓
Upload / Create Evidence
```

AI request hiện tại gồm:

```text
session_id
driver_id
vehicle_id
violation_type
severity
detected_at
evidence
```

`detected_at` được lấy từ AI. Không đối chiếu với `end_at` của Session.

Nếu upload Evidence thất bại, Violation `PENDING` vẫn được giữ lại. Cơ chế bổ sung/retry Evidence sẽ quyết định sau.

Core hiện tại chưa triển khai idempotency/fingerprint để chống AI gửi trùng.

---

# 12. Quy trình Admin duyệt lỗi

```text
Violation PENDING
       ↓
Admin xem:
- Loại lỗi
- Mức độ
- Thời điểm
- Hình ảnh / Video
       ↓
Admin có thể chỉnh:
- violation_type
- severity
- admin_note (có thể NULL)
       ↓
   ┌───┴────┐
   ↓        ↓
APPROVED  REJECTED
   │          │
   │          └── Có thể Xem xét lại → PENDING
   │
   └── Driver xem + có thể Appeal

APPROVED / REJECTED / REVOKED
        ↓
Admin có thể Xem xét lại
        ↓
      PENDING
```

---

# 13. Quy trình kháng cáo

```text
Violation APPROVED
        ↓
Driver gửi Appeal
        ↓
Appeal PENDING
        ↓
Admin xử lý
      /   \
     /     \
APPROVED  REJECTED
    ↓          ↓
Violation    Violation
= REVOKED    vẫn APPROVED
```

Mỗi Violation chỉ được Appeal một lần.

Khi Appeal được `APPROVED`, Driver không còn nhìn thấy Violation, Evidence và Appeal tương ứng.

`resolved_at` được ghi khi Admin xử lý Appeal. `admin_response` có thể `NULL`.

Admin có thể sửa thủ công `status` và `admin_response` của Appeal sau khi xử lý; `content` không được sửa. Cách đồng bộ trạng thái Violation nếu Appeal đã xử lý bị sửa lại sẽ quyết định sau.

Admin có thể xóa Appeal thủ công; việc này không làm thay đổi Violation và không mở lại quyền Appeal.

---

# 14. Những thứ KHÔNG nằm trong Core

Để tránh vượt scope, phiên bản đầu tiên không yêu cầu:

- Multi-company.
- Nhiều role ngoài Admin/User.
- Audit log phức tạp.
- Lịch sử Assignment riêng.
- Lịch sử Face Embedding.
- Hệ thống Penalty riêng.
- GPS tracking.
- Quản lý nhiên liệu.
- Tính lương tài xế.
- Route planning.
- Tự phát triển AI.
- Tự phát triển Face Recognition.
- Hệ thống notification phức tạp.
- Livestream production.
- Hệ thống camera riêng biệt.
- Mobile application.

Các chức năng này chỉ xem xét sau khi Core hoàn thành.

---

# 15. Lộ trình phát triển

Nguyên tắc:

> **Làm cái đơn giản chạy được trước → sau đó thêm nghiệp vụ → tích hợp → nâng cấp.**

Không làm tất cả cùng lúc.

---

## Phase 0 — Chuẩn bị

### Mục tiêu

Tạo project có thể chạy.

Cần hoàn thành:

- Git repository.
- Django project.
- PostgreSQL.
- Environment variables.
- Django REST Framework.
- Custom User Model.
- Cấu hình database.
- Cấu hình Cloudinary.
- Cấu hình CORS nếu cần.
- API health check.

Kết quả:

```text
GET /api/health/
→ 200 OK
```

---

# Phase 1 — Authentication

### Mục tiêu

Có thể đăng ký và đăng nhập.

Làm:

- User.
- Role.
- Login.
- Register.
- JWT/session authentication.
- `is_active`.
- Permission Admin/User.

Chưa làm:

- GPLX.
- Face.
- Vehicle.
- AI.

Kết quả:

```text
Register
   ↓
Login
   ↓
Authenticated API
```

---

# Phase 2 — Driver Profile

### Mục tiêu

Quản lý hồ sơ tài xế.

Làm:

- DriverProfile.
- CRUD/update profile.
- Approval status.
- Admin duyệt hồ sơ.

Sau phase này:

```text
Driver đăng ký
    ↓
Tạo Profile
    ↓
PENDING
    ↓
Admin approve
    ↓
APPROVED
```

---

# Phase 3 — GPLX

Làm:

- DriverLicense.
- Upload ảnh.
- Cloudinary.
- Một GPLX hiện tại cho mỗi tài xế.
- Admin duyệt.
- Expiry validation.

Chưa cần face.

---

# Phase 4 — Vehicle

Làm:

- VehicleType (`TRUCK` / `BUS`).
- Vehicle.
- Thông số xe theo từng phương tiện.
- Vehicle status.
- Admin CRUD.

Kết quả:

```text
VehicleType
    ↓
Vehicle
```

---

# Phase 5 — Assignment

Làm:

- DriverVehicleAssignment.
- Gán tài xế vào xe.
- `start_at`.
- `end_at`.
- Kiểm tra Assignment hiện hành.

Demo:

```text
Driver A
    ↓
Vehicle X
01/09 → 30/09
```

---

# Phase 6 — Driving Session

Làm:

- Start Session.
- Stop Session.
- Eligibility check cơ bản.
- Không cho xe có hai session đang chạy.

Ban đầu có thể **chưa tích hợp Face API**.

Flow:

```text
START
 ↓
Check permission
 ↓
Create Session
```

Sau khi flow này ổn mới thêm Face.

---

# Phase 7 — Face Verification

Làm:

- FaceProfile.
- Upload ảnh.
- Cloudinary.
- Admin duyệt Face.
- Gọi Face Embedding API.
- Lưu embedding bằng pgvector.
- Verify trước khi Start Session.

Flow:

```text
Start
 ↓
Permission Check
 ↓
Face Verify
 ↓
Create Session
```

---

# Phase 8 — Violation

Làm API nhận dữ liệu AI.

Ban đầu **không cần Raspberry Pi thật**.

Có thể dùng Postman:

```text
POST /api/violations/
```

Gửi:

```json
{
  "session_id": 1,
  "type": "DROWSINESS",
  "severity": "HIGH",
  "detected_at": "2026-08-28T10:30:00Z"
}
```

Server tạo:

```text
Violation
PENDING
```

---

# Phase 9 — Evidence

Thêm:

- Upload image.
- Upload video.
- Cloudinary.
- Evidence metadata.

Sau phase này:

```text
Violation
 ├── Image
 ├── Image
 └── Video
```

---

# Phase 10 — Admin Review

Làm:

- Danh sách violation pending.
- Xem evidence.
- Approve.
- Reject.
- `admin_note`.

---

# Phase 11 — Appeal

Làm:

- Driver xem violation.
- Driver gửi appeal.
- Chỉ được appeal một lần.
- Admin xử lý appeal.

Đến đây **Core Business System hoàn thành**.

---

# Phase 12 — Raspberry Pi / AI Integration

Sau khi backend ổn định:

```text
Raspberry Pi
     ↓
AI
     ↓
POST Django API
```

Thay vì Postman giả lập.

---

# Phase 13 — Device Management

Làm:

- Device.
- Device status.
- `last_seen_at`.
- Device → Vehicle.
- API authentication cho device nếu cần.

---

# Phase 14 — Livestream

Chỉ làm sau cùng.

```text
Raspberry Pi
     ↓
Camera
     ↓
Streaming
     ↓
Admin
```

Đây là **tính năng nâng cao/bonus**, không được để ảnh hưởng Core.

---

# 16. Thứ tự ưu tiên

Nếu thời gian bị thiếu:

```text
★★★★★ Authentication
★★★★★ Driver
★★★★★ License
★★★★★ Vehicle
★★★★★ Assignment
★★★★★ Driving Session
★★★★★ Violation
★★★★★ Evidence
★★★★★ Admin Review
★★★★★ Appeal

★★★★☆ Face API

★★★☆☆ Raspberry Pi integration

★★☆☆☆ Device monitoring

★☆☆☆☆ Livestream
```

Nguyên tắc:

> **Không được hy sinh Core để chạy theo livestream/AI.**

---

# 17. Definition of Done

Core được xem là hoàn thành khi demo được:

```text
1. Driver đăng ký
2. Driver đăng nhập
3. Driver tạo hồ sơ
4. Admin duyệt hồ sơ
5. Driver thêm GPLX
6. Admin duyệt GPLX
7. Admin tạo loại xe
8. Admin tạo xe
9. Admin giao xe cho Driver
10. Driver bắt đầu Session
11. Server kiểm tra điều kiện
12. AI/Postman gửi Violation
13. Server lưu Violation
14. Server lưu Evidence
15. Admin duyệt Violation
16. Driver xem Violation
17. Driver gửi Appeal
18. Admin xử lý Appeal
```

Nếu 18 bước này chạy ổn, **đồ án đã có một workflow hoàn chỉnh**.

---

# 18. Nguyên tắc thiết kế

### Không over-engineering

Không tạo entity chỉ vì:

> "Production có thể cần."

Entity phải có nghiệp vụ rõ ràng.

### Không xóa dữ liệu nghiệp vụ quan trọng

Ví dụ:

```text
Assignment hết hạn
→ không DELETE
```

```text
Vehicle thanh lý
→ LIQUIDATED
```

```text
Violation bị AI nhận nhầm
→ REJECTED
```

### Không duplicate dữ liệu

Ví dụ Violation không cần lưu lại:

```text
driver_id
vehicle_id
```

nếu đã có:

```text
Violation
 → DrivingSession
    → Assignment
       → Driver + Vehicle
```

### Business rule nằm ở Server

Database lưu dữ liệu và enforce constraint quan trọng.

Django Service/API layer xử lý nghiệp vụ.

---

# 19. Trạng thái hiện tại của dự án

### Đã thiết kế

- [x] Phạm vi đồ án
- [x] Actor
- [x] Kiến trúc tổng quan
- [x] Domain entities
- [x] Quan hệ chính
- [x] Driver workflow
- [x] Vehicle workflow
- [x] Assignment
- [x] Driving Session
- [x] Violation
- [x] Evidence
- [x] Appeal
- [x] State machine
- [x] Business rules cơ bản
- [x] Roadmap phát triển

### Chưa triển khai

- [ ] Django Models
- [ ] Database migration
- [ ] REST API
- [ ] Authentication
- [ ] Cloudinary integration
- [ ] Face API integration
- [ ] pgvector
- [ ] AI API
- [ ] Raspberry Pi
- [ ] Device API
- [ ] Livestream

---

# 20. Nguyên tắc phát triển từ đây

Mỗi phase phải đạt:

```text
Thiết kế
   ↓
Implement
   ↓
Migration
   ↓
API
   ↓
Test
   ↓
Demo
   ↓
Git commit
   ↓
Mới sang phase tiếp theo
```

Không làm kiểu:

```text
Tạo hết 13 Model
       ↓
Viết 50 API
       ↓
Cuối cùng mới chạy thử
```

Mà làm **từng lát dọc (vertical slice)** để luôn có một hệ thống đang chạy được.

---

# 21. Milestone đề xuất

```text
M0 — Project chạy được
 ↓
M1 — Authentication
 ↓
M2 — Driver Management
 ↓
M3 — License Management
 ↓
M4 — Vehicle Management
 ↓
M5 — Assignment
 ↓
M6 — Driving Session
 ↓
M7 — Face Verification
 ↓
M8 — Violation
 ↓
M9 — Evidence
 ↓
M10 — Admin Review
 ↓
M11 — Appeal
 ↓
M12 — AI/Raspberry Pi
 ↓
M13 — Device
 ↓
M14 — Bonus/Livestream
 ↓
FINAL
```

**Mục tiêu của giai đoạn đầu chỉ là M0 → M6.** Khi đến đó, bạn đã có một backend nghiệp vụ cơ bản chạy được. Sau đó mới tích hợp AI/Face/Raspberry Pi từng thứ một.

---

## 22. Việc đầu tiên cần làm

**Chưa viết Model ngay.**

Theo roadmap, bước đầu tiên là:

### M0 — Project Foundation

Ta sẽ chuẩn bị:

```text
project/
├── .env
├── .gitignore
├── README.md
├── requirements.txt
├── manage.py
│
├── config/
│   ├── settings/
│   ├── urls.py
│   └── ...
│
└── apps/
```

Sau đó mới sang:

> **M1 — Custom User + Authentication**

và từ M1 trở đi mới bắt đầu tạo database schema từng phần.

