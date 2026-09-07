# SaveLife — các trang động Django

Chạy `python manage.py runserver`, mở http://127.0.0.1:8000/.
Các trang hiện đọc và ghi database cấu hình trong `.env`. Không tạo dữ liệu mẫu, không cần npm.

## Đã hoạt động

| Trang | URL | Chức năng |
| --- | --- | --- |
| Đăng nhập, đăng ký | `/login/`, `/register/` | Xác thực Django session; đăng ký chỉ tạo tài khoản USER |
| Tổng quan | `/dashboard/` | Thống kê và phiên gần đây từ database theo quyền |
| Tài xế | `/drivers/` | Admin tìm kiếm, xem hồ sơ/GPLX, duyệt và vô hiệu hóa tài khoản |
| Hồ sơ | `/profile/` | Cập nhật thông tin, chọn avatar và tối đa 4 ảnh góc mặt; tạo vector và lưu FaceProfile |
| GPLX | `/license/` | Chọn file ảnh hai mặt, upload Cloudinary; cập nhật chuyển về PENDING |
| Phương tiện | `/vehicles/` | Admin thêm/sửa xe; tài xế chỉ xem xe có phân công còn hiệu lực |
| Loại xe | `/catalogs/` | Admin quản lý nhóm TRUCK/BUS |
| Phân công | `/assignments/` | Admin phân công tài xế đã duyệt cho xe đang hoạt động |
| Thiết bị | `/devices/` | Admin quản lý thiết bị, mỗi xe tối đa một thiết bị |
| Phiên lái | `/sessions/` | Chỉ đọc lịch sử từ database; tài xế chỉ xem phiên của mình |

Danh sách có tìm kiếm, bộ lọc trạng thái phù hợp và phân trang 20 bản ghi. Các thao tác ghi dùng POST, CSRF và kiểm tra quyền ở server. Không có bộ chuyển vai trò trên giao diện.

Admin là tài khoản có `role=ADMIN` hoặc superuser. Có thể dùng tài khoản hiện có; nếu cần tạo quản trị viên, chạy `python manage.py createsuperuser`. Tài khoản `is_staff` đơn thuần không tự có quyền ADMIN trên web.

## Phạm vi để sau

- Đã tạo embedding hồ sơ; việc so khớp khuôn mặt khi bấm nút phần cứng vẫn triển khai sau.
- Vi phạm/kháng cáo chưa có model nên chưa làm nghiệp vụ; các URL cũ hiển thị thông báo chưa triển khai.
- Thiết bị hiện cập nhật trạng thái thủ công; không giả lập heartbeat hoặc tự cập nhật `last_seen_at`.
- Phiên lái: bấm nút phần cứng → camera xác minh → hoàn tất kiểm tra → hệ thống tạo phiên. Web không tạo/sửa/kết thúc phiên. Giao thức thiết bị và quy trình kết thúc sẽ chốt sau.
- Không xóa xe, phân công hay lịch sử. Xe có thể chuyển trạng thái. Phân công đã có phiên lái không đổi tài xế/xe/thời gian bắt đầu.

## Cấu trúc đang sử dụng

| Cần sửa | File |
| --- | --- |
| URL và tên route | `frontend/urls.py` |
| Truy vấn dữ liệu, phân quyền, xử lý trang | `frontend/views.py` |
| Biểu mẫu và validation | `frontend/forms.py` |
| Upload Cloudinary và gọi API embedding | `accounts/media_services.py` |
| Lưu hồ sơ/ảnh/vector và dọn ảnh thay thế | `accounts/profile_services.py` |
| Layout và sidebar | `templates/base.html`, `templates/includes/sidebar.html` |
| Đăng nhập/đăng ký | `templates/auth.html` |
| Tổng quan | `templates/dashboard.html` |
| Danh sách dùng chung | `templates/list.html` |
| Biểu mẫu dùng chung | `templates/form.html`, `templates/includes/fields.html` |
| Chi tiết và duyệt tài xế/GPLX | `templates/driver_detail.html` |
| CSS | `static/app.css`, `static/css/` |
| Menu mobile và xác nhận thao tác | `static/server.js` |
| Kiểm thử nghiệp vụ | `frontend/tests.py` |

Các module `static/js/`, `static/app.js` và bộ kiểm thử Node cũ là mã prototype còn giữ lại để tham khảo; các trang động không nạp hay sử dụng chúng. `templates/index.html` và các include header/dialog cũ cũng không thuộc luồng trang động hiện tại.

Đường dẫn trong template dùng `{% url 'frontend:vehicles' %}`. Trong Python dùng `reverse('frontend:vehicles')`. Thêm/sửa dùng route `frontend:create` và `frontend:edit`, nhận khóa tương ứng (`vehicles`, `catalogs`, `assignments`, `devices`).

## Kiểm tra

```text
python manage.py check
python manage.py test frontend.tests frontend.test_uploads config.test_frontend --settings=config.test_settings
```

Bộ test dùng SQLite trong bộ nhớ, không thay đổi database PostgreSQL hiện tại. Không cần migration mới cho thay đổi giao diện này.

## Upload và embedding

Cài thư viện bằng `python -m pip install -r requirements.txt`. Cloudinary đọc các biến đã có trong `.env`: `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`. Các giá trị này chỉ dùng ở server.

Sau khi đăng ký, tài xế được chuyển đến trang hồ sơ để điền thông tin và chọn avatar. Ảnh đầu tiên lưu làm ảnh đại diện trong `FaceProfile.face_image_url`; có thể chọn thêm tối đa 4 ảnh để cải thiện vector. Cả 1–5 ảnh gửi đến API theo notebook `mẫu.ipynb`: POST multipart với tên trường lặp lại `files`, lấy mảng `vector` trong JSON. Ảnh góc mặt bổ sung chỉ phục vụ tạo vector, không lưu lâu dài; model hiện có một ảnh khuôn mặt hiện tại.

Endpoint mặc định là `https://aiwho-embeddingresnet34.hf.space/extract_profile`, có thể đổi qua `FACE_EMBEDDING_URL` trong môi trường. Mỗi ảnh phải là JPG/PNG/WebP thực, tối đa 5 MB và 20 megapixel. Không nhận vector do trình duyệt gửi lên; server tự gọi API. Vector lưu vào JSONField có sẵn, chưa chuyển sang pgvector.

Thay avatar sẽ tạo lại vector và đưa FaceProfile về PENDING. Không chọn ảnh mới thì giữ ảnh/vector cũ. Admin xem ảnh và vector, duyệt/từ chối tại chi tiết tài xế. GPLX lần đầu cần đủ hai mặt; lần sau có thể chỉ thay một mặt. Database lưu cả HTTPS URL và public ID của Cloudinary.

Lỗi upload/embedding hiển thị ngay trong biểu mẫu và không ghi đè dữ liệu cũ. Ảnh mới upload dở được dọn khi lưu thất bại; ảnh cũ chỉ xóa sau khi transaction thành công. Nếu Cloudinary không thể xóa, server ghi log public ID để xử lý lại. Khi có lỗi, trình duyệt yêu cầu chọn lại file ảnh.

Các test tích hợp dùng mock Cloudinary và API embedding, kiểm tra hợp đồng request, lưu vector, giới hạn ảnh, rollback và dọn ảnh lỗi; không gửi ảnh cá nhân tới dịch vụ thật trong quá trình chạy test.
