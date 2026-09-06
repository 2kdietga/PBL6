# Frontend FleetCare

Chạy `python manage.py runserver`, mở http://127.0.0.1:8000/.
Frontend dùng Django template, CSS và JavaScript thuần; không cần npm hoặc CDN.

Đây là giao diện tương tác với dữ liệu mẫu trong bộ nhớ của tab. Tải lại trang sẽ đặt lại dữ liệu. Không ghi database, không upload ảnh lên Cloudinary, không xác thực tài khoản hoặc khuôn mặt. Không nhập mật khẩu thật vào biểu mẫu mẫu.

Chọn vai trò ở góc trên để xem Admin hoặc tài xế Nguyễn Văn Minh. Hai vai trò dùng chung dữ liệu mẫu trong tab để thử luồng duyệt/kháng cáo.

| Trang | URL |
| --- | --- |
| Tổng quan | /dashboard/ (hoặc /) |
| Đăng nhập / đăng ký mẫu | /login/, /register/ |
| Tài xế (Admin) | /drivers/ |
| Hồ sơ / GPLX / khuôn mặt (tài xế) | /profile/, /license/, /face/ |
| Phương tiện | /vehicles/ |
| Phân công (Admin) | /assignments/ |
| Phiên lái | /sessions/ |
| Vi phạm và chi tiết bằng chứng | /violations/ |
| Kháng cáo | /appeals/ |
| Thiết bị (Admin) | /devices/ |
| Loại xe / loại vi phạm (Admin) | /catalogs/ |
| Django Admin hiện có | /admin/ |

## Kiểm tra

```text
python manage.py check
python manage.py test config.test_frontend
node --experimental-vm-modules tests/frontend.test.cjs
```

## Khi nối backend

### Phiên lái được khởi tạo từ phần cứng

Luồng đã xác nhận: tài xế bấm nút trên thiết bị → camera chụp ảnh xác minh tài xế → hệ thống hoàn tất xác minh và các kiểm tra cần thiết → tự động tạo phiên lái.

Web chỉ theo dõi trạng thái và lịch sử phiên, không có thao tác tạo phiên. Các bước kiểm tra bổ sung, giao thức thiết bị và cách kết thúc phiên chưa được chốt; hiện không cung cấp nút kết thúc trên web. Đây là cập nhật nghiệp vụ mới, thay cho mô tả tài xế bắt đầu phiên trên web trước đây. Chưa triển khai tích hợp phần cứng/API.

- Thay dữ liệu từ `static/js/data/demo.js` và các thao tác trong `js/events/forms.js`, `js/events/actions.js` bằng lớp gọi API, có xử lý đang tải và lỗi mạng. Trạng thái dùng chung nằm ở `js/core/store.js`.
- Lấy vai trò từ phiên đăng nhập trên server; bộ chuyển vai trò hiện tại chỉ dành cho xem trước, không phải cơ chế phân quyền.
- Server phải kiểm tra quyền trên mọi thao tác, hạng GPLX theo thông số xe, thời hạn phân công, face verification và các ràng buộc phiên lái.
- Nối upload Cloudinary và bằng chứng thực tế. Hiện tại vùng bằng chứng hiển thị trạng thái chưa có dữ liệu; ảnh tải lên chỉ được xem trước.
- Biểu đồ tuần là minh họa độc lập; thay bằng thống kê từ API khi có backend.
- Việc sửa kết quả kháng cáo đã xử lý trong bản mẫu đồng bộ lại trạng thái vi phạm. Cần chốt quy tắc backend theo điểm còn mở trong README trước khi triển khai thật.

## Cấu trúc và nơi chỉnh sửa

Các file JavaScript dùng ES modules với `import` / `export` rõ ràng. Không cần bundler. `app.js` chỉ khởi tạo ứng dụng; `app.css` chỉ nạp các stylesheet theo thứ tự.

| Cần sửa | File / thư mục |
| --- | --- |
| Thêm hoặc đổi URL | `frontend/urls.py` |
| Cung cấp dữ liệu cấu hình từ Django | `frontend/views.py` |
| Layout HTML dùng chung | `templates/base.html` |
| Sidebar, header, footer, dialog | `templates/includes/` |
| Điểm vào template | `templates/index.html` |
| Khởi tạo JavaScript | `static/app.js` |
| Điều hướng, Back/Forward, URL | `static/js/core/router.js` |
| Chọn trang để hiển thị | `static/js/core/render.js` |
| Menu theo vai trò | `static/js/core/navigation.js` |
| Trạng thái và truy vấn dữ liệu mẫu | `static/js/core/store.js` |
| Dữ liệu mẫu ban đầu | `static/js/data/demo.js` |
| Tổng quan | `static/js/pages/dashboard.js` |
| Đăng nhập / đăng ký | `static/js/pages/auth.js` |
| Hồ sơ / GPLX / khuôn mặt | `static/js/pages/profile.js` |
| Bảng danh sách, tìm kiếm, bộ lọc dùng chung | `static/js/pages/list.js` |
| Cột và nội dung từng danh sách | `static/js/pages/lists/` (ví dụ `vehicles.js`, `violations.js`) |
| Thành phần giao diện dùng chung | `static/js/components/ui.js` |
| Biểu mẫu thêm/sửa và hộp chi tiết | `static/js/components/dialogs.js` |
| Xử lý nút bấm, bộ lọc, xem trước ảnh | `static/js/events/actions.js` |
| Xử lý gửi biểu mẫu, thay đổi dữ liệu | `static/js/events/forms.js` |
| CSS nền, layout, bảng, form, dialog, responsive | `static/css/` |

HTML của các trang tương tác vẫn do module trong `js/pages/` dựng; template Django chịu trách nhiệm layout và cung cấp cấu hình. Các trang danh sách dùng chung bộ render bảng để tránh lặp mã.

## Sử dụng đường dẫn

Trong Django template:

```django
{% url 'frontend:vehicles' %}
{% url 'frontend:violations' %}
```

Trong module JavaScript nằm dưới `js/pages/`:

```javascript
import { urlFor, navigate } from '../core/router.js';

const vehicleUrl = urlFor('vehicles');
navigate('violations');
```

Django sinh bảng URL qua `reverse()` và truyền an toàn bằng `json_script`. Không hard-code lại đường dẫn trong JavaScript. Khi thêm trang mới, khai báo tên ở `frontend/urls.py`, thêm mục menu và module render tương ứng.

Các URL có thể mở trực tiếp hoặc tải lại. Điều hướng nội bộ dùng History API để giữ dữ liệu mẫu; Ctrl/Cmd-click và mở tab mới vẫn là liên kết bình thường. Liên kết cũ dạng `/#vehicles` được chuyển sang URL mới khi mở. Vai trò mặc định khi tải lại là Admin; các trang riêng `/profile/`, `/license/`, `/face/` tự mở chế độ tài xế mẫu.
