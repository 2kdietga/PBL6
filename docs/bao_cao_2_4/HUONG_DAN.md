# Bộ tài liệu mục 2.4 — Giải pháp phần mềm SaveLife

## Cách sử dụng

1. Mở `2_4_Giai_phap_phan_mem_SaveLife.docx`. Bản Word chứa nội dung, bảng và 6 hình đã chèn, có thể sao chép vào báo cáo nhóm.
2. Chỉnh số hình, cỡ chữ và khoảng cách theo mẫu báo cáo của trường. Bỏ phần “Ghi chú biên tập” ở cuối khi nộp.
3. Nếu chỉ cần hình, mở `xem_so_do.html` để xem bộ hình, rồi lấy PNG trong `images`. Dùng SVG khi cần phóng to.
4. Nếu muốn chỉnh cấu trúc sơ đồ, dùng các tệp Mermaid `.mmd` trong `sources`. Hình PNG/SVG được dựng bố cục bằng `generate_report.py`; Mermaid là bản mô tả ngữ nghĩa tương ứng, không phải đầu vào trực tiếp của bộ dựng hình này.

## Sườn đề xuất

- 2.4.1. Mục tiêu và phạm vi giải pháp.
- 2.4.2. Kiến trúc tổng thể.
- 2.4.3. Công nghệ và tổ chức mã nguồn.
- 2.4.4. Phân rã chức năng và phân quyền.
- 2.4.5. Thiết kế dữ liệu.
- 2.4.6. Các luồng xử lý chính: hồ sơ, nhận diện, vi phạm.
- 2.4.7. Bảo vệ dữ liệu và xử lý lỗi.
- 2.4.8. Phạm vi đã triển khai và hướng hoàn thiện.

## Danh sách hình

| Hình tạm | Nội dung | Tên tệp |
| --- | --- | --- |
| 2.4-1 | Kiến trúc tổng thể | 01_kien_truc |
| 2.4-2 | Nhóm chức năng theo tác nhân | 02_chuc_nang |
| 2.4-3 | Quan hệ dữ liệu cốt lõi | 03_du_lieu |
| 2.4-4 | Cập nhật và xét duyệt hồ sơ | 04_ho_so |
| 2.4-5 | Tuần tự nhận diện tài xế | 05_nhan_dien |
| 2.4-6 | Xét duyệt vi phạm | 06_vi_pham |

Hình dữ liệu được rút gọn để dễ đọc trong báo cáo. `sources/03_du_lieu.mmd` có đủ 14 thực thể và 15 quan hệ. Hình phân rã chức năng không phải sơ đồ use case UML hình thức. Các hình không phải ảnh chụp giao diện hoặc bằng chứng chạy thử.

## Phạm vi đối chiếu

Biên soạn ngày 15/10/2026 từ mã nguồn trong workspace. Phần hiện trạng mô tả những chức năng được thể hiện trong mã, không khẳng định đã kiểm chứng kết nối dịch vụ thật hoặc chạy thử toàn bộ hệ thống. Không sử dụng dữ liệu cá nhân, khóa API hoặc thông tin tài khoản thật trong hình.

Các tính năng tự mở/kết thúc phiên từ thiết bị, nhận vi phạm AI và giao diện kháng cáo được đánh dấu chưa triển khai. Nhận diện danh tính hiện chưa phải kiểm tra quyền lái xe. Không bổ sung số liệu độ chính xác hoặc tốc độ khi chưa có kết quả đo.

## Tạo lại tài liệu

Chạy từ thư mục gốc dự án:

```text
python docs/bao_cao_2_4/generate_report.py
```

Script dùng Python, Pillow và phông Arial của Windows; không truy cập mạng hay cơ sở dữ liệu. Nội dung Word lấy từ `2_4_giai_phap_phan_mem.md`. Sơ đồ và nguồn Mermaid được định nghĩa trong script. Không cần cài thêm thư viện vào dự án hiện tại để chạy script này.
