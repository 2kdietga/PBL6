# Deploy SaveLife lên Render

## 1. Web Service dùng database đã có

Push code lên GitHub, tạo Render **Web Service**, runtime **Python**.
Chọn cùng region và workspace với database `pbl6_o3ry` đã có.
Không cần tạo database mới. Internal URL chỉ dùng từ dịch vụ Render có kết nối
mạng nội bộ tới database; không dùng URL này để kết nối từ máy local.

| Cấu hình | Giá trị |
| --- | --- |
| Root Directory | Thư mục chứa manage.py; `src` nếu repo chứa src/manage.py, để trống nếu manage.py ở gốc |
| Build Command | `bash build.sh` |
| Start Command | `bash start.sh` |

`.python-version` chọn Python 3.12. Nếu dashboard đã đặt PYTHON_VERSION thì biến
đó được ưu tiên; bỏ biến cũ hoặc chọn bản Python 3.12 đầy đủ phù hợp.

## 2. Environment trên Render

Không upload .env. Nhập các giá trị trong tab Environment:

| Biến | Giá trị |
| --- | --- |
| DATABASE_URL | Toàn bộ Internal Database URL của database pbl6_o3ry, lấy từ Dashboard; không đặt trong Git |
| DJANGO_SECRET_KEY | Chuỗi ngẫu nhiên riêng cho production, không thay đổi mỗi deploy |
| DJANGO_DEBUG | false |
| CLOUDINARY_CLOUD_NAME | Cloud name đang dùng |
| CLOUDINARY_API_KEY | API key đang dùng |
| CLOUDINARY_API_SECRET | API secret đang dùng |
| FACE_EMBEDDING_URL | URL dịch vụ embedding truy cập được từ Internet |
| FACE_SINGLE_EMBEDDING_URL | URL extract_single truy cập được từ Internet |
| FACE_COSINE_THRESHOLD | Ngưỡng đã hiệu chỉnh cho model đang dùng |
| FACE_COSINE_MARGIN | Ngưỡng chênh lệch đang dùng; mặc định 0.05 |
| HF_API_TOKEN | Chỉ cần nếu dịch vụ yêu cầu token |
| DEVICE_API_REQUIRE_HTTPS | true |
| DEVICE_API_CHECK_FRAME_AGE | true |

Nếu endpoint nhận diện dùng tên trường file khác `file`, đặt FACE_SINGLE_FILE_FIELD.
Render cung cấp RENDER_EXTERNAL_HOSTNAME; settings tự thêm host và CSRF origin.
Nếu dùng tên miền riêng, thêm DJANGO_ALLOWED_HOSTS (tên miền) và
DJANGO_CSRF_TRUSTED_ORIGINS (https://tên-miền), phân cách bằng dấu phẩy.

Tạo secret ở máy local rồi dán vào Render (không chia sẻ kết quả):

```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. Build và khởi động

Build cài dependencies, gom/nén static, chạy Django check. Start chạy migration
trước khi mở Gunicorn. Nếu migration lỗi, service không khởi động để tránh dùng
schema chưa hoàn chỉnh. Không tự seed dữ liệu, xóa database hoặc tạo mật khẩu admin.

Cách này dành cho một instance demo. Khi tăng nhiều instance, chuyển migration
sang Pre-deploy Command (`python manage.py migrate --noinput`) nếu gói hỗ trợ,
và bỏ dòng migrate khỏi start.sh. Với database có dữ liệu quan trọng, backup trước
khi deploy migration thay đổi schema.

## 4. Tạo quản trị viên

Trong Render Shell nếu gói hỗ trợ:

```bash
python manage.py createsuperuser
```

Nếu không có Shell: dùng terminal riêng trên máy local, đặt DATABASE_URL bằng
**External Database URL** trong phiên terminal (không lưu vào Git), bảo đảm
DJANGO_SECRET_KEY đã có trong .env local, rồi chạy cùng lệnh createsuperuser.
Chỉ cho phép IP cần thiết trong cấu hình truy cập database. Đóng terminal sau đó.
Không đưa mật khẩu admin vào build.sh hoặc start.sh.

Database mới chỉ có schema sau migration, không có dữ liệu local. Tạo tài xế,
xe, thiết bị, phân công và loại vi phạm trên giao diện hoặc chuyển dữ liệu riêng.

## 5. Nghiệm thu

1. Mở URL HTTPS: giao diện và CSS/JS hiển thị đúng khi DEBUG=false.
2. Đăng nhập admin; kiểm tra form không báo CSRF.
3. Upload ảnh: xác nhận ảnh xuất hiện trên Cloudinary.
4. Nhận diện và mở phiên lái qua Pi; đồng bộ đồng hồ Pi.
5. Gửi vi phạm: nhận 201, xem ảnh trên web; gửi lại cùng event_id nhận 200.
6. Kiểm tra tab Logs: access log Gunicorn và warning/error từ Django.

Trên Pi đặt WEB_SERVER_URL=https://<service>.onrender.com và API key thiết bị
được cấp từ database production. Giữ dữ liệu pending khi timeout hoặc 5xx.
Ảnh nằm trên Cloudinary, dữ liệu trên PostgreSQL; không dựa vào ổ đĩa tạm Render.

## Công dụng các thay đổi

- DATABASE_URL: dùng database Render sẵn có, giữ DB_* cho local.
- Secret/env, DEBUG=false, hosts, CSRF, proxy HTTPS và cookie secure: cấu hình
  Django cho domain production và nhận đúng HTTPS qua proxy Render.
- WhiteNoise và STATICFILES_DIRS: gom cả CSS/JS của dự án và Django admin.
- Gunicorn: chạy WSGI production; timeout 180 giây hỗ trợ lời gọi AI/ảnh chậm.
- Console logging: xem lỗi lưu vi phạm và dọn ảnh trong Render Logs.
- .gitattributes: giữ shell scripts ở định dạng LF khi commit từ Windows.
- .env.example: danh sách cấu hình mẫu, không chứa thông tin xác thực thật.

Tài liệu chính thức:
- https://render.com/docs/deploy-django
- https://render.com/docs/python-version
- https://render.com/docs/free

Gói free có cơ chế ngủ khi không có traffic và database có thời hạn; kiểm tra
giới hạn hiện tại trước khi chọn cho demo hoặc lưu dữ liệu lâu dài.

## Kết quả kiểm tra chuẩn bị deploy

- collectstatic thành công; smoke check DEBUG=false đạt cho đăng nhập admin,
  chuyển HTTP sang HTTPS, static admin và CSS dự án, đọc DATABASE_URL.
- Bộ test SQLite: 130/135 đạt. Năm test trong vehicles.test_licensing thất bại
  và tái hiện với settings cũ từ Git HEAD; cần xử lý riêng nghiệp vụ GPLX/phân công.
- check --deploy còn security.W005 và security.W021: chưa bật HSTS cho toàn bộ
  subdomain hoặc đăng ký preload. Chỉ bật khi đã xác minh chính sách tên miền;
  HTTPS và secure cookies cho service Render đã bật.
- Kiểm tra local dùng Python 3.10; Render được cấu hình Python 3.12.
  Chưa chạy Gunicorn trên Windows, chưa kết nối database Render hoặc dịch vụ AI/
  Cloudinary thật. Xác nhận lại trên Render sau deploy.
