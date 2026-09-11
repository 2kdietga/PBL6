# Sơ đồ lớp theo mã nguồn hiện tại

9 model nghiệp vụ; AbstractUser là lớp cha của Django. Các lớp vi phạm trong README chưa được triển khai. Chi tiết thuộc tính, quan hệ và quy tắc nghiệp vụ: `mo_ta_so_do_lop.docx`.

Sao chép nội dung `so_do_lop.mmd` vào trình biên tập Mermaid, hoặc xem khối dưới đây trên trình đọc Markdown hỗ trợ Mermaid.

```mermaid
classDiagram
direction LR
%% Sơ đồ lớp miền nghiệp vụ theo mã nguồn hiện tại.
%% Dấu + biểu diễn thuộc tính/phương thức công khai; NULL xem tài liệu.
class AbstractUser {
    <<abstract>>
    +String username
    +String password
    +String email
    +String first_name
    +String last_name
    +Boolean is_active
    +Boolean is_staff
    +Boolean is_superuser
    +DateTime last_login
    +DateTime date_joined
}
AbstractUser <|-- User
class User {
    +BigInt id
    +String role
    +__str__() String
}
class DriverProfile {
    +BigInt id
    +BigInt user_id
    +String full_name
    +Date date_of_birth
    +String phone
    +Text address
    +String approval_status
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class DriverLicense {
    +BigInt id
    +BigInt driver_id
    +String license_number
    +String license_class
    +Date issued_date
    +Date expiry_date
    +URL front_image_url
    +String front_image_public_id
    +URL back_image_url
    +String back_image_public_id
    +String status
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class FaceProfile {
    +BigInt id
    +BigInt driver_id
    +URL face_image_url
    +String cloudinary_public_id
    +JSON embedding
    +String approval_status
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class VehicleType {
    +BigInt id
    +String name
    +String category
    +Text description
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class Vehicle {
    +BigInt id
    +BigInt vehicle_type_id
    +String license_plate
    +String brand
    +String model
    +Integer manufacture_year
    +Decimal load_capacity
    +Integer passenger_capacity
    +String status
    +Text description
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class Device {
    +BigInt id
    +BigInt vehicle_id
    +String device_code
    +String name
    +String status
    +DateTime last_seen_at
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class DriverVehicleAssignment {
    +BigInt id
    +BigInt driver_id
    +BigInt vehicle_id
    +DateTime start_at
    +DateTime end_at
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
class DrivingSession {
    +BigInt id
    +BigInt assignment_id
    +DateTime started_at
    +DateTime ended_at
    +String status
    +DateTime created_at
    +DateTime updated_at
    +__str__() String
}
User "1" -- "0..1" DriverProfile : user
DriverProfile "1" -- "0..1" DriverLicense : driver
DriverProfile "1" -- "0..1" FaceProfile : driver
VehicleType "1" -- "0..*" Vehicle : vehicle_type
Vehicle "1" -- "0..1" Device : vehicle
DriverProfile "1" -- "0..*" DriverVehicleAssignment : driver
Vehicle "1" -- "0..*" DriverVehicleAssignment : vehicle
DriverVehicleAssignment "1" -- "0..*" DrivingSession : assignment
```

Tạo lại tài liệu từ thư mục gốc dự án: `python docs/generate_class_docs.py`.
