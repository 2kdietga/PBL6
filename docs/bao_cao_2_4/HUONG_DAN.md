# Bộ tài liệu mục 2.4 — Giải pháp phần mềm SaveLife

## Cách sử dụng

1. Bộ hình được cập nhật ngày 06/11/2026. Mở `xem_so_do.html` hoặc lấy bộ hình mới trong `So_do_SaveLife.zip`. Bản DOCX và ZIP báo cáo cũ chưa được cập nhật nội dung hoặc thay hình trong đợt này.
2. Chỉnh số hình, cỡ chữ và khoảng cách theo mẫu báo cáo của trường. Bỏ phần “Ghi chú biên tập” ở cuối khi nộp.
3. Nếu chỉ cần hình, mở `xem_so_do.html` để xem bộ hình, rồi lấy PNG trong `images`. Dùng SVG khi cần phóng to.
4. Hình PNG/SVG được dựng bố cục bằng `generate_figures.py`; các tệp Mermaid `.mmd` trong `sources` là bản mô tả tương ứng, không phải đầu vào trực tiếp của bộ dựng hình.

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
| 2.4-5 | Nhận diện và mở phiên lái | 05_nhan_dien |
| 2.4-6 | Tiếp nhận và xét duyệt vi phạm | 06_vi_pham |

Hình dữ liệu biểu diễn quan hệ tổng quát, gộp GPLX và khuôn mặt, lược bỏ tài khoản, bảng danh mục, kháng cáo và các quan hệ phụ; không thay thế ERD đầy đủ. Hình chức năng không phải sơ đồ use case UML. Các hình không phải ảnh chụp giao diện hoặc bằng chứng chạy thử.

## Phạm vi đối chiếu

Cập nhật hình ngày 06/11/2026 theo mã nguồn, `driving/device_urls.py`, `docs/session_api.md` và `docs/violation_api.md`. Không khẳng định đã kiểm chứng kết nối dịch vụ thật hoặc chạy thử toàn bộ hệ thống. Không sử dụng dữ liệu cá nhân hoặc khóa API thật trong hình.

API mở/kết thúc phiên và nhận vi phạm đã triển khai. API mở phiên nhận ảnh, nhận diện, kiểm tra quyền lái rồi tạo phiên; không cần gọi API nhận diện riêng trước. Giao diện kháng cáo chưa triển khai. Hình hồ sơ lược bỏ các trạng thái trung gian và lỗi nhập liệu; hình vi phạm lược bỏ lỗi tiếp nhận. Luồng xem xét lại chỉ áp dụng khi nghiệp vụ cho phép. Không bổ sung số liệu độ chính xác hoặc tốc độ khi chưa đo.

## Tạo lại tài liệu

Chạy từ thư mục gốc dự án:

```text
python docs/bao_cao_2_4/generate_figures.py
```

Script dùng Python, Pillow và phông Arial của Windows; không truy cập mạng hay cơ sở dữ liệu. Tạo PNG, SVG, Mermaid, ảnh tổng hợp, trang xem trước và ZIP hình. `generate_report.py` dùng chung bộ dựng hình này nhưng nội dung báo cáo Markdown cũ cần cập nhật trước khi tạo lại Word.
