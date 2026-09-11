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
}
models = []
for app in ('accounts', 'vehicles', 'driving'):
    path = ROOT / app / 'models.py'
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if not isinstance(node, ast.ClassDef):
            continue
        fields, enums = [], []
        for member in node.body:
            if isinstance(member, ast.ClassDef):
                enums.append((member.name, [ast.literal_eval(x.value)[0] for x in member.body if isinstance(x, ast.Assign)]))
            if isinstance(member, ast.Assign) and isinstance(member.value, ast.Call):
                call = member.value
                if not isinstance(call.func, ast.Attribute):
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
            target = args[0]
            many = '0..1' if kind == 'OneToOneField' else '0..*'
            relations.append((target, name, many, field, kw['on_delete'].split('.')[-1], kw.get('related_name', '')))
        else:
            lines.append(f'    +{types[kind]} {field}')
    lines += ['    +__str__() String', '}']
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
p('Ngày lập: 09/09/2026. Nguồn đối chiếu: các model, form, dịch vụ và README trong dự án.')
p('1. Phạm vi và cách đọc', 'Heading1')
p('Tài liệu mô tả 9 lớp model đã triển khai trong accounts, vehicles và driving. AbstractUser được thể hiện để giải thích kế thừa, không tính là lớp nghiệp vụ tự xây dựng. Đây là sơ đồ lớp miền nghiệp vụ, không liệt kê toàn bộ lớp form, view, admin hoặc lớp nội bộ Django.')
p('Mã Mermaid đầy đủ nằm trong so_do_lop.mmd và phụ lục cuối tài liệu. Sao chép toàn bộ nội dung file .mmd vào trình biên tập Mermaid để vẽ sơ đồ.')
p('1: đúng một; 0..1: có thể chưa có, tối đa một; 0..*: không hoặc nhiều. Đường liền biểu diễn association, mũi tên tam giác biểu diễn kế thừa. Không suy diễn composition chỉ từ on_delete. Các trường liên kết được viết dạng tên_id trên sơ đồ để phản ánh khóa ngoại trong cơ sở dữ liệu; trong Python tên thuộc tính là user, driver, vehicle, vehicle_type hoặc assignment.')
p('2. Danh sách lớp', 'Heading1')
table(['Lớp', 'Module', 'Vai trò'], [(name, app, descriptions[name]) for name, app, _, _ in models])
p('3. Chi tiết thuộc tính và phương thức', 'Heading1')
p('Mỗi model có khóa chính id tự tăng kiểu BigAutoField theo config/settings.py. Các lớp trừ User có created_at (auto_now_add) và updated_at (auto_now). User dùng date_joined của Django, không có created_at/updated_at trong mã hiện tại. Các trường auth kế thừa được liệt kê chọn lọc trên sơ đồ; groups và user_permissions thuộc hệ thống phân quyền Django được lược bỏ.')
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
    p('Phương thức khai báo: __str__() trả về chuỗi hiển thị đối tượng. Các phương thức ORM như save() và delete() được kế thừa từ Django; model không khai báo phương thức nghiệp vụ riêng.')
p('4. Quan hệ và quy tắc xóa', 'Heading1')
table(['Quan hệ (cha → con)', 'Bội số', 'Trường ở con / truy cập ngược', 'on_delete'], [(f'{a} → {b}', f'1 → {m}', f'{f} / {r}', d) for a, b, m, f, d, r in relations])
p('OneToOneField bắt buộc mỗi đối tượng con có đúng một cha, nhưng không bắt buộc cha đã có con. Vì vậy DriverProfile có thể chưa có DriverLicense hoặc FaceProfile; User có thể chưa có DriverProfile; Vehicle có thể chưa có Device.')
p('CASCADE: khi xóa cha qua Django, đối tượng con liên quan cũng bị xóa. PROTECT: chặn xóa cha nếu vẫn còn đối tượng con tham chiếu. Ví dụ, xóa User kéo theo DriverProfile nhưng có thể bị chặn nếu hồ sơ đang được DriverLicense, FaceProfile hoặc DriverVehicleAssignment bảo vệ. Đây là chính sách on_delete của ORM Django.')
p('DriverProfile và Vehicle có quan hệ nhiều–nhiều về nghiệp vụ thông qua DriverVehicleAssignment. Lớp trung gian có id riêng cùng start_at/end_at; mã nguồn không khai báo ManyToManyField trực tiếp và không có ràng buộc duy nhất cho cặp driver–vehicle. Có thể có nhiều lần phân công cho cùng một cặp.')
p('DrivingSession tham chiếu Assignment. Tài xế và xe của phiên được truy xuất qua session.assignment.driver và session.assignment.vehicle; không có khóa ngoại trực tiếp từ phiên tới User hoặc Device.')
p('5. Quy tắc nghiệp vụ đã quan sát trong mã nguồn', 'Heading1')
for text in [
    'frontend/forms.py — ProfileForm: ngày sinh phải trước ngày hiện tại. LicenseForm: ngày cấp không ở tương lai; ngày hết hạn sau ngày cấp và phải còn hạn.',
    'frontend/forms.py — VehicleForm: xe TRUCK yêu cầu load_capacity > 0, xe BUS yêu cầu passenger_capacity > 0; thông số của nhóm còn lại được đặt None. Năm sản xuất nằm từ 1900 đến năm hiện tại.',
    'frontend/forms.py — AssignmentForm: end_at phải sau start_at nếu được nhập; xe phải ACTIVE; tài khoản tài xế đang hoạt động và hồ sơ APPROVED. Khi đã có phiên lái, không cho đổi tài xế, xe hoặc start_at qua form này.',
    'accounts/profile_services.py — save_profile(form, user): lưu hồ sơ và ảnh/embedding; hồ sơ mới hoặc đổi họ tên/ngày sinh được đặt PENDING; ảnh khuôn mặt mới đặt FaceProfile về PENDING.',
    'accounts/profile_services.py — save_license(form, driver): lưu GPLX và ảnh hai mặt, đặt trạng thái PENDING; dùng transaction và xử lý ảnh Cloudinary. Đây là hàm dịch vụ, không phải phương thức của model.',
    'Các kiểm tra form chỉ áp dụng khi chạy luồng form tương ứng; không nên coi là ràng buộc database. Model chưa khai báo CheckConstraint/UniqueConstraint để chống phân công trùng thời gian hoặc nhiều phiên STARTED đồng thời. Không có logic trong model tự chuyển GPLX sang EXPIRED theo thời gian.',
]:
    p(text)
p('6. Phần thiết kế trong README chưa có model', 'Heading1')
p('violations/models.py hiện chỉ chứa import và chú thích. ViolationType, Violation, Evidence và Appeal được nêu trong README nhưng chưa có lớp model; không đưa vào sơ đồ hiện trạng.')
table(['Lớp dự kiến', 'Vai trò theo README'], [('ViolationType', 'Danh mục loại vi phạm.'), ('Violation', 'Sự kiện vi phạm thuộc phiên lái và loại vi phạm.'), ('Evidence', 'Metadata ảnh/video bằng chứng của vi phạm.'), ('Appeal', 'Kháng cáo đối với vi phạm.')])
p('Quan hệ định hướng trong README: DrivingSession 1 → 0..* Violation; ViolationType 1 → 0..* Violation; Violation 1 → 0..* Evidence; Violation 1 → 0..1 Appeal. Đây là diễn giải thiết kế dự kiến; chưa có khóa ngoại/on_delete được triển khai để kiểm chứng.')
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
(OUT / 'so_do_lop.md').write_text('# Sơ đồ lớp theo mã nguồn hiện tại\n\n9 model nghiệp vụ; AbstractUser là lớp cha của Django. Các lớp vi phạm trong README chưa được triển khai. Chi tiết thuộc tính, quan hệ và quy tắc nghiệp vụ: `mo_ta_so_do_lop.docx`.\n\nSao chép nội dung `so_do_lop.mmd` vào trình biên tập Mermaid, hoặc xem khối dưới đây trên trình đọc Markdown hỗ trợ Mermaid.\n\n```mermaid\n' + mermaid + '```\n\nTạo lại tài liệu từ thư mục gốc dự án: `python docs/generate_class_docs.py`.\n', encoding='utf-8')
print(f'Generated documentation for {len(models)} models and {len(relations)} associations.')
