# Sơ đồ tuần tự

Các sơ đồ dưới đây mô tả luồng web đã triển khai, đối chiếu ngày 11/09/2026 với `frontend/views.py`, `frontend/forms.py`, `frontend/urls.py`, `accounts/profile_services.py` và `accounts/media_services.py`. Mỗi sơ đồ có file `.mmd` riêng trong `docs/sequence/`; sao chép nội dung file vào trình biên tập Mermaid để vẽ.

Quy ước: mũi tên liền là lời gọi/yêu cầu, mũi tên đứt là phản hồi; `alt` là nhánh điều kiện, `opt` là bước tùy chọn, `loop` là vòng lặp. Các truy vấn ORM được gom theo mục đích nghiệp vụ. DB biểu diễn cơ sở dữ liệu qua Django ORM. Các URL là đường dẫn trong `frontend/urls.py`.

Các luồng yêu cầu đăng nhập dùng session Django; chưa đăng nhập sẽ được chuyển tới trang đăng nhập. Luồng quản trị chỉ cho phép tài khoản có `role=ADMIN` hoặc `is_superuser=True`; sai quyền trả về 403. Các POST chịu kiểm tra CSRF của Django. Những bước bảo vệ chung này được lược bớt trong sơ đồ nghiệp vụ.

## 1. Đăng ký tài khoản

File: [01_dang_ky.mmd](sequence/01_dang_ky.mmd). Nguồn: `register`, `RegisterForm`.

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant V as register view
    participant F as RegisterForm
    participant A as Django Auth
    participant DB as Database
    U->>V: POST /register/ (username, email, mật khẩu)
    alt Đã đăng nhập
        V-->>U: 302 tới dashboard
    else Chưa đăng nhập
        V->>F: is_valid()
        F->>DB: Kiểm tra username và ràng buộc model
        DB-->>F: Kết quả kiểm tra
        F-->>V: Hợp lệ hoặc lỗi nhập liệu
        alt Form không hợp lệ
            V-->>U: Hiển thị auth.html cùng lỗi
        else Form hợp lệ
            V->>F: save(commit=False)
            F-->>V: User với mật khẩu đã băm
            V->>DB: Lưu User với role=USER
            DB-->>V: Tài khoản được tạo
            V->>A: login(request, user)
            A-->>V: Thiết lập trạng thái đăng nhập
            V-->>U: Thông báo thành công và 302 tới /profile/
        end
    end
```

Đăng ký chỉ tạo User; DriverProfile được tạo khi người dùng lưu hồ sơ.

## 2. Đăng nhập và đăng xuất

File: [02_dang_nhap_dang_xuat.mmd](sequence/02_dang_nhap_dang_xuat.mmd). Nguồn: `SignIn(LoginView)`, `SignOut(LogoutView)`. Sơ đồ gom các bước xác thực và quản lý session do Django cung cấp.

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant V as SignIn / SignOut
    participant A as Django Auth và Session
    participant DB as Database
    U->>V: POST /login/ (username, password)
    V->>A: Kiểm tra thông tin đăng nhập
    A->>DB: Tra cứu User
    DB-->>A: Dữ liệu tài khoản
    A->>A: Kiểm tra mật khẩu và quyền đăng nhập
    alt Thông tin sai hoặc tài khoản không hoạt động
        A-->>V: Lỗi xác thực
        V-->>U: Hiển thị form đăng nhập cùng lỗi
    else Đăng nhập hợp lệ
        A-->>V: User đã xác thực
        V->>A: login(request, user)
        A-->>V: Thiết lập session
        V-->>U: 302 tới next hợp lệ hoặc URL mặc định
        opt Người dùng đăng xuất sau đó
            U->>V: POST /logout/
            V->>A: logout(request)
            A->>A: Xóa session đăng nhập hiện tại
            V-->>U: 302 tới /login/
        end
    end
```

## 3. Lưu hồ sơ và tạo embedding khuôn mặt

File: [03_luu_ho_so.mmd](sequence/03_luu_ho_so.mmd). Nguồn: `profile`, `ProfileForm`, `save_profile`, `extract_embedding`, `upload_image`, `delete_images`. Điều kiện: người dùng đã đăng nhập và không phải quản trị viên.

```mermaid
sequenceDiagram
    autonumber
    actor U as Tài xế
    participant V as profile view
    participant F as ProfileForm
    participant S as save_profile
    participant M as media_services
    participant API as Face API
    participant C as Cloudinary
    participant DB as Database
    U->>V: POST /profile/ (thông tin, ảnh tùy chọn)
    V->>DB: Đọc DriverProfile và FaceProfile hiện tại
    DB-->>V: Đối tượng hiện tại hoặc chưa có
    V->>F: Kiểm tra thông tin và các ảnh
    F-->>V: Kết quả validation
    alt Form không hợp lệ
        V-->>U: Hiển thị form cùng lỗi
    else Form hợp lệ
        V->>S: save_profile(form, user)
        opt Có avatar mới
            S->>M: extract_embedding(avatar và ảnh bổ sung)
            M->>API: POST multipart (1 đến 5 ảnh)
            API-->>M: HTTP response và vector
            M->>M: Kiểm tra vector số hữu hạn, không toàn 0
            M-->>S: Vector hoặc phát sinh MediaError
            S->>M: upload_image(avatar, faces)
            M->>C: Upload avatar
            C-->>M: secure_url và public_id
            M-->>S: Thông tin ảnh hoặc MediaError
        end
        Note over S,DB: Chỉ tiếp tục lưu nếu các bước ảnh thành công
        alt Các bước ảnh thành công hoặc không có avatar mới
            S->>DB: BEGIN atomic, khóa User và hồ sơ hiện có
            S->>DB: Lưu DriverProfile
            Note over S,DB: PENDING nếu mới hoặc đổi full_name/date_of_birth
            opt Có avatar mới
                S->>DB: Khóa và tạo/cập nhật FaceProfile
                S->>DB: Lưu URL, public_id, embedding, PENDING
                S->>S: Đăng ký on_commit xóa avatar cũ
            end
            alt Lưu database thành công
                S->>DB: COMMIT
                opt Có ảnh cũ cần xóa
                    S->>M: delete_images(public_id cũ) sau commit
                    M->>C: Yêu cầu xóa ảnh cũ
                end
                S-->>V: DriverProfile đã lưu
                V-->>U: Thông báo thành công, 302 tới /profile/
            else Exception khi lưu database
                S->>DB: ROLLBACK
                S->>M: Dọn ảnh mới đã nhận public_id
                M->>C: Yêu cầu xóa ảnh mới
                S-->>V: Ném lại exception
                Note over V,U: Lỗi ngoài MediaError không được view này bắt
            end
        else MediaError trong xử lý ảnh
            S->>M: Dọn ảnh mới đã nhận public_id nếu có
            S-->>V: Ném lại MediaError
            V-->>U: Hiển thị form cùng thông báo lỗi
        end
    end
```

Nếu Face API lỗi, luồng dừng trước upload avatar và trước transaction lưu hồ sơ. Các mũi tên sau phản hồi lỗi trong nhóm xử lý ảnh không được thực thi. `delete_images` ghi log khi xóa thất bại, không ném lỗi để hoàn tác dữ liệu đã lưu; sơ đồ không cam kết Cloudinary luôn được dọn sạch.

## 4. Thêm hoặc cập nhật giấy phép lái xe

File: [04_luu_gplx.mmd](sequence/04_luu_gplx.mmd). Nguồn: `license_page`, `LicenseForm`, `save_license`. Điều kiện: tài xế đã đăng nhập.

```mermaid
sequenceDiagram
    autonumber
    actor U as Tài xế
    participant V as license_page
    participant F as LicenseForm
    participant S as save_license
    participant M as media_services
    participant C as Cloudinary
    participant DB as Database
    U->>V: POST /license/ (thông tin và ảnh hai mặt)
    V->>DB: Tìm DriverProfile của tài khoản
    DB-->>V: Hồ sơ hoặc chưa có
    alt Chưa có hồ sơ
        V-->>U: Thông báo và 302 tới /profile/
    else Đã có hồ sơ
        V->>DB: Đọc GPLX hiện tại
        DB-->>V: GPLX hoặc chưa có
        V->>F: Kiểm tra số GPLX, ngày cấp, hạn và ảnh
        F-->>V: Kết quả validation
        alt Form không hợp lệ
            V-->>U: Hiển thị form cùng lỗi
        else Form hợp lệ
            V->>S: save_license(form, driver)
            loop Mỗi mặt có ảnh mới, dừng nếu phát sinh lỗi
                S->>M: upload_image(image, licenses)
                M->>C: Upload ảnh
                C-->>M: URL và public_id hoặc lỗi
                M-->>S: Thông tin ảnh hoặc MediaError
            end
            alt Upload thành công hoặc không có ảnh mới
                S->>DB: BEGIN atomic, khóa DriverProfile và GPLX hiện tại
                S->>S: Giữ ảnh cũ ở mặt không có ảnh mới
                S->>DB: Lưu GPLX với status=PENDING
                S->>S: Đăng ký on_commit xóa ảnh được thay thế
                alt Lưu thành công
                    S->>DB: COMMIT
                    S->>M: delete_images(ảnh cũ được thay thế)
                    M->>C: Yêu cầu xóa các ảnh cũ nếu có
                    S-->>V: GPLX đã lưu
                    V-->>U: Thông báo thành công, 302 tới /license/
                else Exception khi lưu
                    S->>DB: ROLLBACK
                    S->>M: Dọn các ảnh mới đã nhận public_id
                    M->>C: Yêu cầu xóa ảnh mới
                    S-->>V: Ném lại exception
                    Note over V,U: View chỉ xử lý MediaError thành lỗi form
                end
            else Upload phát sinh MediaError
                S->>M: Dọn các ảnh mới đã upload trước lỗi
                M->>C: Yêu cầu xóa ảnh nếu có
                S-->>V: Ném lại MediaError
                V-->>U: Hiển thị form cùng thông báo lỗi
            end
        end
    end
```

Form yêu cầu ảnh cho mặt chưa có URL, ngày cấp không ở tương lai và GPLX còn hạn. Dọn ảnh là thao tác cố gắng thực hiện; lỗi dọn ảnh được ghi log.

## 5. Quản trị duyệt hồ sơ, khuôn mặt, GPLX và khóa tài khoản

File: [05_duyet_tai_xe.mmd](sequence/05_duyet_tai_xe.mmd). Nguồn: `driver_action`. Điều kiện: đã qua `admin_required` và request là POST; tài nguyên không tồn tại trả 404.

```mermaid
sequenceDiagram
    autonumber
    actor A as Quản trị viên
    participant V as driver_action
    participant DB as Database
    A->>V: POST /drivers/pk/action/ (action)
    V->>DB: BEGIN atomic, khóa DriverProfile
    DB-->>V: Hồ sơ tài xế
    alt action = approve
        V->>DB: DriverProfile.approval_status = APPROVED
    else action = enable hoặc disable
        V->>DB: Khóa User của tài xế
        DB-->>V: User
        alt Là chính người thao tác hoặc tài khoản quản trị
            V->>DB: ROLLBACK khi PermissionDenied
            V-->>A: 403, dừng xử lý
        else Tài khoản được phép cập nhật
            V->>DB: Lưu is_active theo action
        end
    else action = face-approve hoặc face-reject
        V->>DB: Khóa và đọc FaceProfile
        DB-->>V: Hồ sơ khuôn mặt
        alt Không có embedding
            V->>V: Ghi thông báo lỗi, không đổi trạng thái
        else Có embedding
            V->>DB: Lưu APPROVED hoặc REJECTED
        end
    else action = license-approve hoặc license-reject
        V->>DB: Khóa và đọc DriverLicense
        DB-->>V: GPLX
        alt Duyệt GPLX có expiry_date không sau hôm nay
            V->>V: Ghi thông báo lỗi, không đổi trạng thái
        else Được phép thực hiện action
            V->>DB: Lưu ACTIVE hoặc REJECTED
        end
    else action không được hỗ trợ
        V->>DB: ROLLBACK khi PermissionDenied
        V-->>A: 403, dừng xử lý
    end
    opt Không phát sinh exception
        V->>DB: COMMIT khi rời atomic
        V-->>A: 302 tới chi tiết tài xế với thông báo kết quả
    end
```

Trong nhánh thiếu embedding hoặc GPLX hết hạn khi duyệt, view trả về sớm với thông báo lỗi và không ghi thông báo thành công. `face-reject` cũng yêu cầu embedding theo mã hiện tại.

## 6. Quản trị tạo hoặc cập nhật dữ liệu quản lý

File: [06_quan_ly_du_lieu.mmd](sequence/06_quan_ly_du_lieu.mmd). Nguồn: `edit`, `ENTITIES` và các ModelForm. Áp dụng cho `vehicles`, `catalogs`, `assignments`, `devices`; sơ đồ có nhánh kiểm tra phân công xe.

```mermaid
sequenceDiagram
    autonumber
    actor A as Quản trị viên
    participant V as edit view
    participant F as ModelForm tương ứng
    participant DB as Database
    A->>V: POST /manage/key/new/ hoặc /manage/key/pk/
    V->>V: Kiểm tra key và form trong ENTITIES
    alt Key không hỗ trợ chỉnh sửa
        V-->>A: 403
    else Key hợp lệ
        V->>DB: BEGIN atomic
        opt Cập nhật bản ghi hiện có
            V->>DB: select_for_update theo pk
            DB-->>V: Bản ghi hoặc 404 nếu không có
        end
        V->>F: Khởi tạo form với POST và instance
        V->>F: is_valid()
        F->>DB: Đọc đối tượng liên quan và kiểm tra ràng buộc
        DB-->>F: Dữ liệu kiểm tra
        opt Là AssignmentForm
            F->>F: Kiểm tra end_at sau start_at nếu có
            F->>F: Xe ACTIVE, tài xế hoạt động và APPROVED
            F->>DB: Kiểm tra phân công đã có driving_sessions chưa
            DB-->>F: Kết quả
            F->>F: Nếu đã có phiên, cấm đổi driver, vehicle, start_at
        end
        F-->>V: Kết quả validation
        alt Form hợp lệ
            V->>F: save()
            F->>DB: INSERT hoặc UPDATE model
            DB-->>F: Đã lưu
            V->>DB: COMMIT khi rời atomic
            V-->>A: Thông báo thành công, 302 tới danh sách
        else Form không hợp lệ
            V->>DB: Kết thúc atomic, không lưu form
            V-->>A: Hiển thị form cùng lỗi
        end
    end
```

`VehicleForm` kiểm tra thông số theo nhóm TRUCK/BUS và năm sản xuất. `VehicleTypeForm` không cho đổi nhóm của loại xe đang được dùng. `DeviceForm` dùng kiểm tra ModelForm, gồm tính duy nhất mã thiết bị và liên kết một–một với xe. Luồng phân công hiện không kiểm tra trùng khoảng thời gian. Nếu phát sinh exception trong atomic thì transaction bị rollback; sơ đồ chỉ triển khai chi tiết nhánh validation thông thường.

## 7. Xem danh sách theo quyền người dùng

File: [07_xem_danh_sach.mmd](sequence/07_xem_danh_sach.mmd). Nguồn: `listing`, `scoped`. Điều kiện: đã đăng nhập.

```mermaid
sequenceDiagram
    autonumber
    actor U as Người dùng
    participant V as listing view
    participant S as scoped
    participant DB as Database
    U->>V: GET danh sách (q, status, page tùy chọn)
    alt Danh sách vehicles hoặc sessions
        V->>S: scoped(request, model)
        alt Là quản trị viên
            S-->>V: QuerySet toàn bộ bản ghi
        else Tài xế xem vehicles
            S-->>V: QuerySet xe được phân công cho user trong thời gian hiện hành
        else Tài xế xem sessions
            S-->>V: QuerySet phiên có assignment.driver.user là user hiện tại
        end
    else Danh sách khác và là quản trị viên
        V->>V: Chọn toàn bộ bản ghi của model
    else Danh sách khác và không phải quản trị viên
        V-->>U: 403, dừng xử lý
    end
    opt Được quyền xem danh sách
        V->>V: Thêm bộ lọc tìm kiếm và trạng thái hợp lệ
        V->>DB: Truy vấn select_related, sắp pk giảm dần, phân trang 20
        DB-->>V: Tổng số và bản ghi của trang
        V->>V: Tạo các ô hiển thị và liên kết theo quyền
        V-->>U: Render list.html
    end
```

Phân công hiện hành có `start_at <= now` và (`end_at IS NULL` hoặc `end_at > now`). Danh sách xe tài xế dùng `distinct()`. Danh sách phiên của tài xế không giới hạn theo thời hạn phân công. `QuerySet` được xây dựng trước và thực thi khi lấy dữ liệu/phân trang; các mũi tên truy vấn thể hiện mức khái quát.

## Phạm vi chưa triển khai

Chưa vẽ luồng bắt đầu/kết thúc phiên lái, xác thực khuôn mặt trước khi lái, nhận vi phạm từ AI, duyệt vi phạm hoặc gửi/xử lý kháng cáo như chức năng đang hoạt động. `DrivingSession` hiện được dùng để xem dữ liệu; `/violations/` và `/appeals/` trỏ tới trang `deferred`. Tạo embedding khi lưu hồ sơ ở sơ đồ 3 không phải là xác thực danh tính trước phiên lái.
