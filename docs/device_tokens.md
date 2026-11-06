# Cấp token thiết bị trên web

1. Đăng nhập bằng tài khoản quản trị viên.
2. Mở **Thiết bị**, tạo thiết bị gắn với xe nếu chưa có.
3. Chọn thiết bị trong danh sách để mở trang cập nhật.
4. Trong mục **Khóa API**, chọn **Cấp token**.
5. Chọn **Sao chép token**, lưu vào `DEVICE_API_KEY` trên Pi rồi về trang thiết bị.

Khi đã có khóa, dùng **Cấp lại token** để thay khóa, hoặc **Thu hồi** để ngừng
cho phép thiết bị gọi API. Cả hai thao tác vô hiệu hóa khóa cũ ngay lập tức.
Khóa mới chỉ xuất hiện trong phản hồi cấp khóa; không thể xem lại trên web.
Nếu làm mất khóa hoặc mất kết nối ngay khi cấp, quay lại thiết bị và cấp lại.
Nếu trình duyệt không cho phép sao chép tự động, nút sẽ chọn token để bạn nhấn
Ctrl+C hoặc Command+C.

Pi gửi `Authorization: Bearer <token>` khi gọi API. Token thuộc database của
server đang mở: nếu dùng Render, cấp trên web Render để Pi gọi đúng server đó.
Không đưa token vào Git hoặc chia sẻ ảnh chụp màn hình có token.

Lệnh `python manage.py rotate_device_key <device_code>` vẫn được hỗ trợ và dùng
cùng cơ chế cấp khóa với giao diện. Không cần migration cho tính năng này.
