# Hạng GPLX yêu cầu và phân công xe

Áp dụng hệ hạng từ 2025 theo [Điều 57 Luật 36/2024/QH15, giới thiệu trên Cổng thông tin Chính phủ](https://xaydungchinhsach.chinhphu.vn/tu-1-1-2025-co-nhung-hang-giay-phep-lai-xe-nao-119240812165630751.htm).

| Xe | Thông số | Hạng yêu cầu |
|---|---|---|
| Tải | Khối lượng toàn bộ theo thiết kế ≤ 3.500 kg | B |
| Tải | Trên 3.500 đến 7.500 kg | C1 |
| Tải | Trên 7.500 kg | C |
| Khách | Đến 8 hành khách | B |
| Khách | 9–16 hành khách | D1 |
| Khách | 17–29 hành khách | D2 |
| Khách | Từ 30 hành khách hoặc xe giường nằm | D |

Số hành khách không kể tài xế. Khối lượng toàn bộ theo thiết kế khác trọng tải hàng: nhập riêng từ giấy tờ xe. Phạm vi hiện tại là xe tải và xe khách thông thường, không tính rơ moóc nặng, đầu kéo/sơ mi rơ moóc, xe nối toa hoặc xe cải tạo giảm số chỗ. Chưa hỗ trợ hệ hạng GPLX cũ.

`Vehicle.required_license_class` tính từ thông số hiện tại, không lưu một bản sao có thể lỗi thời. Form xem trước bằng JavaScript; server tính độc lập và bỏ qua hạng do client gửi. Danh sách xe và lựa chọn xe trong form phân công hiển thị hạng yêu cầu.

Form phân công mới/gia hạn kiểm tra xe ACTIVE, tài khoản hoạt động, hồ sơ APPROVED, GPLX đã duyệt/còn hạn, khuôn mặt đã duyệt, hệ GPLX `VN_2025` và quyền lái tương ứng. Thứ tự bao gồm quyền lái xe thông thường là B → C1 → C → D1 → D2 → D. Bằng có hậu tố E được đối chiếu theo hạng gốc trong phạm vi xe không kéo rơ moóc nặng.

Chặn phân công và hiển thị lý do khi thiếu thông số hoặc không đủ hạng. Vẫn cho kết thúc/rút ngắn phân công cũ khi tài xế không còn đủ điều kiện. Kiểm tra này chạy tại form web; không tự sửa phân công lịch sử khi thông số xe hoặc GPLX thay đổi. Script nhập dữ liệu phải gọi kiểm tra tương ứng thay vì ghi thẳng bằng ORM/bulk update.

Sau migration, xe cũ chưa có khối lượng toàn bộ phải được cập nhật; không suy ra bằng cách sao chép trọng tải hàng. GPLX cũ giữ nguyên dữ liệu và có hệ hạng chưa xác nhận: tài xế cập nhật hệ hạng và gửi duyệt lại. Không tự chuyển bằng cũ thành bằng mới. API Pi giữ nguyên luồng nhận diện hiện có.
