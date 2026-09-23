"""Generate model documentation using Python's standard library only."""
import ast
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
descriptions = {
    'User': 'Tài khoản đăng nhập; kế thừa cơ chế xác thực và phân quyền của Django AbstractUser.',
    'DriverProfile': 'Hồ sơ cá nhân và trạng thái duyệt của tài xế.',
    'DriverLicense': 'Giấy phép lái xe hiện tại, thời hạn và thông tin ảnh hai mặt.',
    'FaceProfile': 'Ảnh khuôn mặt và embedding dạng JSON phục vụ nhận diện.',
    'VehicleType': 'Loại phương tiện, phân nhóm TRUCK hoặc BUS.',
    'Vehicle': 'Phương tiện, biển số, thông số kỹ thuật và trạng thái sử dụng.',
    'Device': 'Thiết bị gắn với phương tiện và thời điểm ghi nhận hoạt động gần nhất.',
    'DriverVehicleAssignment': 'Lớp liên kết tài xế với phương tiện theo khoảng thời gian phân công.',
    'DrivingSession': 'Phiên lái thuộc một phân công; lưu thời điểm bắt đầu, kết thúc và trạng thái.',
    'ViolationType': 'Danh mục loại vi phạm; mã được chuẩn hóa và không trùng.',
    'Violation': 'Vi phạm thuộc phiên lái; lưu mức độ, thời điểm phát hiện và kết quả xác nhận.',
    'Evidence': 'Metadata ảnh/video bằng chứng và URL HTTPS.',
    'Appeal': 'Kháng cáo duy nhất của vi phạm; lưu trữ bằng deleted_at khi xóa riêng.',
    'ViolationReview': 'Lịch sử xử lý vi phạm: người xử lý, thời điểm và dữ liệu trước/sau.',
}
models = []
methods = {}
for app in ('accounts', 'vehicles', 'driving', 'violations'):
    path = ROOT / app / 'models.py'
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if not isinstance(node, ast.ClassDef) or not any(ast.unparse(base) in ('models.Model', 'AbstractUser') for base in node.bases):
            continue
        fields, enums = [], []
        methods[node.name] = [member.name for member in node.body if isinstance(member, ast.FunctionDef)]
        for member in node.body:
            if isinstance(member, ast.ClassDef) and any(ast.unparse(base) == 'models.TextChoices' for base in member.bases):
                enums.append((member.name, [ast.literal_eval(x.value)[0] for x in member.body if isinstance(x, ast.Assign)]))
            if isinstance(member, ast.Assign) and isinstance(member.value, ast.Call):
                call = member.value
                if not isinstance(call.func, ast.Attribute):
                    continue
                if not ast.unparse(call.func).startswith('models.'):
                    continue
                fields.append((member.targets[0].id, call.func.attr, {kw.arg: ast.unparse(kw.value) for kw in call.keywords}, [ast.unparse(x) for x in call.args]))
        models.append((node.name, app, fields, enums))

types = {'CharField': 'String', 'TextField': 'Text', 'DateField': 'Date', 'DateTimeField': 'DateTime', 'URLField': 'URL', 'JSONField': 'JSON', 'PositiveIntegerField': 'Integer', 'DecimalField': 'Decimal'}
lines = ['classDiagram', 'direction LR', '%% Sơ đồ lớp miền nghiệp vụ theo mã nguồn hiện tại.', '%% Dấu + biểu diễn thuộc tính/phương thức công khai; NULL xem tài liệu.', 'class AbstractUser {', '    <<abstract>>', '    +String username', '    +String password', '    +String email', '    +String first_name', '    +String last_name', '    +Boolean is_active', '    +Boolean is_staff', '    +Boolean is_superuser', '    +DateTime last_login', '    +DateTime date_joined', '}', 'AbstractUser <|-- User']
relations = []
for name, app, fields, enums in models:
    lines += [f'class {name} {{', '    +BigInt id']
    for field, kind, kw, args in fields:
        if kind in ('ForeignKey', 'OneToOneField'):
            lines.append(f'    +BigInt {field}_id')
            target = args[0] if args else kw['to']
            target = 'User' if target == 'settings.AUTH_USER_MODEL' else target.strip("'\"").split('.')[-1]
            many = '0..1' if kind == 'OneToOneField' else '0..*'
            relations.append((target, name, many, field, kw['on_delete'].split('.')[-1], kw.get('related_name', '')))
        else:
            lines.append(f'    +{types[kind]} {field}')
    lines += [f'    +{method}()' for method in methods[name]] + ['}']
for target, name, many, field, delete, reverse in relations:
    lines.append(f'{target} "1" -- "{many}" {name} : {field}')
mermaid = '\n'.join(lines) + '\n'
(OUT / 'so_do_lop.mmd').write_text(mermaid, encoding='utf-8')

body = []
def p(text, style=None):
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    body.append(f'<w:p>{props}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>')

def table(headers, rows):
    xml = '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>'
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        xml += f'<w:{edge} w:val="single" w:sz="4" w:color="CBD5E1"/>'
    xml += '</w:tblBorders></w:tblPr>'
    for i, row in enumerate([headers] + rows):
        xml += '<w:tr>' + ('<w:trPr><w:tblHeader/></w:trPr>' if i == 0 else '')
        for cell in row:
            bold = '<w:rPr><w:b/></w:rPr>' if i == 0 else ''
            xml += f'<w:tc><w:p><w:r>{bold}<w:t xml:space="preserve">{escape(str(cell))}</w:t></w:r></w:p></w:tc>'
        xml += '</w:tr>'
    body.append(xml + '</w:tbl>')
    p('')

p('SƠ ĐỒ LỚP VÀ MÔ TẢ MÔ HÌNH DỮ LIỆU', 'Title')
p('Hệ thống quản lý và giám sát tài xế lái xe — PBL6')
p('Cập nhật: 23/09/2026. Nguồn đối chiếu: các model, form, dịch vụ và README trong dự án.')
p('1. Phạm vi và cách đọc', 'Heading1')
p(f'Tài liệu mô tả {len(models)} lớp model đã triển khai trong accounts, vehicles, driving và violations. AbstractUser là lớp cha của Django, không tính vào số model nghiệp vụ. Không liệt kê toàn bộ lớp form/view/admin hoặc QuerySet.')
p('Mã Mermaid đầy đủ nằm trong so_do_lop.mmd và phụ lục cuối tài liệu. Sao chép toàn bộ nội dung file .mmd vào trình biên tập Mermaid để vẽ sơ đồ.')
p('1: đúng một; 0..1: có thể chưa có, tối đa một; 0..*: không hoặc nhiều. Đường liền biểu diễn association, mũi tên tam giác biểu diễn kế thừa. Không suy diễn composition chỉ từ on_delete. Các trường liên kết được viết dạng tên_id trên sơ đồ để phản ánh khóa ngoại trong cơ sở dữ liệu; trong Python tên thuộc tính là user, driver, vehicle, vehicle_type hoặc assignment.')
p('2. Danh sách lớp', 'Heading1')
table(['Lớp', 'Module', 'Vai trò'], [(name, app, descriptions[name]) for name, app, _, _ in models])
p('3. Chi tiết thuộc tính và phương thức', 'Heading1')
p('Mỗi model có khóa chính id tự tăng kiểu BigAutoField. User dùng date_joined; Evidence dùng captured_at; ViolationReview chỉ có created_at. Các model còn lại có created_at và updated_at. Các trường auth kế thừa được liệt kê chọn lọc trên sơ đồ.')
p('null=True cho phép NULL trong cơ sở dữ liệu; blank=True cho phép để trống khi kiểm tra biểu mẫu/model. choices là tập lựa chọn của Django, không tự đồng nghĩa với CHECK constraint tại database. Các lựa chọn trạng thái bên dưới không khẳng định hệ thống đã có đầy đủ luồng chuyển trạng thái.')
for name, app, fields, enums in models:
    p(name, 'Heading2')
    p(descriptions[name] + f' Nguồn: {app}/models.py.')
    rows = [('id', 'BigAutoField', 'Khóa chính tự tăng')]
    for field, kind, kw, args in fields:
        details = ([f'Đích: {args[0]}'] if args else []) + [f'{key}={value}' for key, value in kw.items()]
        rows.append((field, kind, '; '.join(details) or 'null=False; blank=False (mặc định)'))
    table(['Thuộc tính', 'Kiểu Django', 'Ràng buộc / cấu hình'], rows)
    for enum, values in enums:
        p(f'{name}.{enum}: ' + ', '.join(values) + '.')
    p('Phương thức/thuộc tính tính toán khai báo trong model: ' + ', '.join(methods[name]) + '.')
p('4. Quan hệ và quy tắc xóa', 'Heading1')
table(['Quan hệ (cha → con)', 'Bội số', 'Trường ở con / truy cập ngược', 'on_delete'], [(f'{a} → {b}', f'1 → {m}', f'{f} / {r}', d) for a, b, m, f, d, r in relations])
p('OneToOneField bắt buộc mỗi đối tượng con có đúng một cha, nhưng không bắt buộc cha đã có con. Vì vậy DriverProfile có thể chưa có DriverLicense hoặc FaceProfile; User có thể chưa có DriverProfile; Vehicle có thể chưa có Device.')
p('CASCADE: khi xóa cha qua Django, đối tượng con liên quan cũng bị xóa. PROTECT: chặn xóa cha nếu vẫn còn đối tượng con tham chiếu. Ví dụ, xóa User kéo theo DriverProfile nhưng có thể bị chặn nếu hồ sơ đang được DriverLicense, FaceProfile hoặc DriverVehicleAssignment bảo vệ. Đây là chính sách on_delete của ORM Django.')
p('DriverProfile và Vehicle có quan hệ nhiều–nhiều về nghiệp vụ thông qua DriverVehicleAssignment. Lớp trung gian có id riêng cùng start_at/end_at; mã nguồn không khai báo ManyToManyField trực tiếp và không có ràng buộc duy nhất cho cặp driver–vehicle. Có thể có nhiều lần phân công cho cùng một cặp.')
p('DrivingSession tham chiếu Assignment và lưu vehicle_id lấy từ phân công để database đảm bảo mỗi xe chỉ có một phiên STARTED. save() kiểm tra xe khớp phân công; phân công đã có phiên không được đổi tài xế/xe/start_at qua form hoặc save(). Không dùng bulk update để thay đổi các liên kết lịch sử.')
p('5. Quy tắc nghiệp vụ đã quan sát trong mã nguồn', 'Heading1')
for text in [
    'frontend/forms.py — ProfileForm: ngày sinh phải trước ngày hiện tại. LicenseForm: ngày cấp không ở tương lai; ngày hết hạn sau ngày cấp và phải còn hạn.',
    'frontend/forms.py — VehicleForm: xe TRUCK yêu cầu load_capacity > 0, xe BUS yêu cầu passenger_capacity > 0; thông số của nhóm còn lại được đặt None. Năm sản xuất nằm từ 1900 đến năm hiện tại.',
    'frontend/forms.py — AssignmentForm: khi giao mới/gia hạn, xe phải ACTIVE, tài xế hoạt động và hồ sơ APPROVED. Vẫn được kết thúc/rút ngắn phân công cũ khi tài xế/xe không còn đủ điều kiện. Không đổi tài xế/xe/start_at khi đã có phiên.',
    'accounts/profile_services.py — save_profile(form, user): lưu hồ sơ và ảnh/embedding; hồ sơ mới hoặc đổi họ tên/ngày sinh được đặt PENDING; ảnh khuôn mặt mới đặt FaceProfile về PENDING.',
    'accounts/profile_services.py — save_license(form, driver): lưu GPLX và ảnh hai mặt, đặt trạng thái PENDING; dùng transaction và xử lý ảnh Cloudinary. Đây là hàm dịch vụ, không phải phương thức của model.',
    'ProfileForm/LicenseForm và thao tác duyệt dùng version của bản ghi; dịch vụ kiểm tra lại dưới khóa transaction để từ chối cập nhật từ trang cũ. DriverProfile hỗ trợ PENDING/APPROVED/REJECTED.',
    'DrivingSession có CHECK khớp trạng thái/thời gian và UNIQUE có điều kiện trên vehicle khi STARTED. save() ngăn sửa phiên ENDED. Phân công trùng thời gian giữa nhiều tài xế vẫn được cho phép theo thiết kế.',
    'DriverLicense.effective_status hiển thị EXPIRED khi GPLX ACTIVE đã hết hạn; is_valid kiểm tra cả trạng thái và ngày. Không sửa database chỉ vì người dùng mở trang.',
]:
    p(text)
p('6. Phạm vi vi phạm hiện tại', 'Heading1')
p('Đã có model và giao diện danh sách/chi tiết/xác nhận/từ chối/xem xét lại. Xác nhận kiểm tra metadata Evidence hợp lệ; mỗi quyết định lưu ViolationReview trong cùng transaction. Lịch sử giữ người xử lý và bản chụp thông tin trước/sau.')
p('Appeal dùng OneToOne và xóa mềm qua deleted_at khi xóa riêng để không mở lại quyền kháng cáo. Xóa Violation qua ORM vẫn xóa cascade Appeal/Evidence/ViolationReview. Chưa mở giao diện gửi/xử lý kháng cáo hoặc xóa vi phạm; chưa có API nhận dữ liệu AI hay upload bằng chứng.')
p('README mô tả embedding theo hướng pgvector ở lộ trình, còn FaceProfile.embedding thực tế là JSONField. Ưu tiên mã nguồn khi mô tả hiện trạng.')
p('7. Phụ lục: mã Mermaid', 'Heading1')
for line in lines:
    p(line, 'Code')

document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + ''.join(body) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1000" w:right="850" w:bottom="1000" w:left="850"/></w:sectPr></w:body></w:document>'
styles = '<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100"/></w:pPr></w:pPrDefault></w:docDefaults>'
for name, size in [('Title', 34), ('Heading1', 28), ('Heading2', 25), ('Code', 16)]:
    styles += f'<w:style w:type="paragraph" w:styleId="{name}"><w:name w:val="{name}"/><w:pPr><w:keepNext w:val="{0 if name == "Code" else 1}"/></w:pPr><w:rPr><w:sz w:val="{size}"/>' + ('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>' if name == 'Code' else '<w:b/>') + '</w:rPr></w:style>'
styles += '</w:styles>'
with ZipFile(OUT / 'mo_ta_so_do_lop.docx', 'w', ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    z.writestr('word/document.xml', document)
    z.writestr('word/styles.xml', styles)
(OUT / 'so_do_lop.md').write_text(f'# Sơ đồ lớp theo mã nguồn hiện tại\n\n{len(models)} model nghiệp vụ trong accounts, vehicles, driving và violations; AbstractUser là lớp cha của Django. Chi tiết thuộc tính, quan hệ và quy tắc nghiệp vụ: `mo_ta_so_do_lop.docx`.\n\nSao chép nội dung `so_do_lop.mmd` vào trình biên tập Mermaid, hoặc xem khối dưới đây trên trình đọc Markdown hỗ trợ Mermaid.\n\n```mermaid\n' + mermaid + '```\n\nTạo lại tài liệu từ thư mục gốc dự án: `python docs/generate_class_docs.py`.\n', encoding='utf-8')
print(f'Generated documentation for {len(models)} models and {len(relations)} associations.')
