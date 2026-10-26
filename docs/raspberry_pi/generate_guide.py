"""Build the Raspberry Pi handoff guide with standard-library OOXML only."""
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Raspberry_Pi_Giao_tiep_Server.docx'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
parts = []


def p(text='', style='Normal', bold=False):
    runs = []
    for i, line in enumerate(text.split('\n')):
        if i:
            runs.append('<w:r><w:br/></w:r>')
        runs.append(f'<w:r>{"<w:rPr><w:b/></w:rPr>" if bold else ""}<w:t xml:space="preserve">{escape(line)}</w:t></w:r>')
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{"".join(runs)}</w:p>'


def para(text, style='Normal'):
    parts.append(p(text, style))


def heading(text):
    para(text, 'Heading1')


def sub(text):
    para(text, 'Heading2')


def code(text, lang=None):
    if lang == 'json':
        json.loads(text)
    if lang == 'python':
        ast.parse(text)
    for line in text.splitlines():
        para(line, 'Code')


def table(headers, rows, widths):
    border = ''.join(f'<w:{side} w:val="single" w:sz="4" w:color="D9D9D9"/>' for side in ('top','left','bottom','right','insideH','insideV'))
    xml = f'<w:tbl><w:tblPr><w:tblW w:w="{sum(widths)}" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblBorders>{border}</w:tblBorders><w:tblCellMar><w:top w:w="75" w:type="dxa"/><w:bottom w:w="75" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
    xml += '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{width}"/>' for width in widths) + '</w:tblGrid>'
    for index, row in enumerate([headers] + rows):
        xml += '<w:tr><w:trPr><w:cantSplit/>' + ('<w:tblHeader/>' if index == 0 else '') + '</w:trPr>'
        for cell, width in zip(row, widths):
            fill = 'DCE6F1' if index == 0 else ('F7F9FB' if index % 2 == 0 else 'FFFFFF')
            xml += f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/><w:shd w:fill="{fill}"/><w:vAlign w:val="center"/></w:tcPr>{p(cell, "TableText", index == 0)}</w:tc>'
        xml += '</w:tr>'
    parts.append(xml + '</w:tbl>')
    para('', 'Spacer')


def page():
    parts.append('<w:p><w:pPr><w:spacing w:after="0" w:before="0"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>')


para('Hướng dẫn Raspberry Pi\ngiao tiếp với server SaveLife', 'Title')
para('Tài liệu tích hợp cho nhóm AI và thiết bị', 'Subtitle')
para('Phiên bản 1.0  |  Ngày 25/10/2026  |  Phạm vi đồ án học kỳ', 'Small')
para('Dùng tài liệu này để kết nối Pi với server Django, mở và kết thúc phiên lái, đọc kết quả nhận diện và xử lý lỗi mạng. Luồng session đã có trong mã nguồn; nhóm Pi có thể tích hợp theo các ví dụ bên dưới.')
para('Ghi nhận vi phạm và heartbeat chưa có endpoint hoạt động. Phần cuối chỉ mô tả hướng chuẩn bị, không dùng các payload đó để kiểm thử server hiện tại.')
heading('1 Luồng tích hợp và việc cần chuẩn bị')
table(['Thành phần', 'Trách nhiệm'], [
    ['Raspberry Pi', 'Camera, chọn frame, chạy AI, gửi request và đọc response. Khi cần cảnh báo, Pi gửi sang ESP32 để phát loa.'],
    ['Server Django', 'Xác thực thiết bị, gọi HF để lấy embedding, kiểm tra quyền lái và lưu phiên.'],
    ['ESP32', 'Nhận tín hiệu cảnh báo từ Pi và phát loa. Giao thức Pi với ESP32 được chốt riêng, không thuộc API server.'],
], [2200, 7438])
sub('Nhóm server cung cấp')
para('Địa chỉ server truy cập được từ Pi; API key riêng của thiết bị; thiết bị gắn đúng xe; tài xế đã được duyệt; GPLX còn hiệu lực và phù hợp xe; đúng một phân công còn hiệu lực. HF và ngưỡng cosine phải được cấu hình trước khi mở phiên.')
sub('Nhóm Pi chuẩn bị')
para('Pi và máy server kết nối được qua mạng; đồng hồ Pi đúng; camera xuất được JPEG; cài requests và OpenCV nếu dùng client camera mẫu. Token chỉ nằm trên thiết bị, không ghi vào mã nguồn hoặc log.')
code('export WEB_SERVER_URL="http://<IP_SERVER>:8000"\nexport DEVICE_API_KEY="<KHOA_DO_NHOM_SERVER_CAP>"')
para('Đây là lệnh shell trên Pi. Không dùng localhost để trỏ đến máy server khác. Nhóm server chạy Django bằng python manage.py runserver 0.0.0.0:8000 khi demo LAN và cho phép kết nối tới cổng 8000.', 'Small')
page()

heading('2 Quy ước kết nối và kiểm tra context')
para('Base URL gồm địa chỉ máy server và /api/v1/device/. Giữ dấu / ở cuối endpoint. Demo LAN dùng HTTP; khi triển khai Internet dùng HTTPS. Không gửi cookie đăng nhập web hoặc CSRF token từ Pi.')
code('Authorization: Bearer <device-api-key>\nX-Request-ID: <UUID cua lan goi HTTP>')
para('X-Request-ID là tùy chọn để đối chiếu lỗi. ID này không chống gửi trùng. X-Device-Code chỉ cần cho khóa cũ chưa được cấp lại; ưu tiên khóa mới nhận diện thiết bị chỉ bằng Bearer token.')
table(['Method', 'Endpoint', 'Dùng khi'], [
    ['GET', 'context/', 'Khởi động Pi hoặc cần biết phiên hiện tại'],
    ['POST', 'sessions/start/', 'Bắt đầu lái với ảnh camera mới'],
    ['POST', 'sessions/{id}/end/', 'Kết thúc phiên đã được server cấp'],
    ['POST', 'face-verifications/', 'Chỉ thử nhận diện, không mở phiên'],
], [1000, 3900, 4738])
sub('GET context')
para('Không có body. Server trả HTTP 200, code DEVICE_READY. Ví dụ trích phần data khi chưa có phiên; response thực còn có giới hạn ảnh và cấu hình matching:')
code('''{
  "device_code": "PI-001",
  "vehicle": {"id": 5, "license_plate": "43C-12345"},
  "device_status": "OFFLINE",
  "vehicle_status": "ACTIVE",
  "active_session": null
}''', 'json')
para('OFFLINE là trạng thái quản trị hiện có, không chứng minh Pi vừa mất mạng. Request API hiện chỉ cập nhật last_seen_at, không tự đổi trạng thái này. MAINTENANCE hoặc xe không ACTIVE chặn mở phiên, nhưng vẫn đọc context và kết thúc phiên được.')
para('Nếu active_session khác null, Pi đọc session_id và driver để hiển thị phiên đang có. Context chỉ trả phiên do chính thiết bị mở. Matching chưa cấu hình thì threshold và ambiguity_margin có thể null; context vẫn đọc được nhưng start chưa thể thành công.')
page()

heading('3 Mở phiên bằng ảnh camera')
code('POST /api/v1/device/sessions/start/')
para('Gửi multipart/form-data với đúng hai trường sau. Để requests tự tạo Content-Type có boundary và Content-Length; không tự ghi header multipart bằng tay.')
table(['Trường', 'Nội dung bắt buộc'], [
    ['frame', 'Một file JPEG, MIME image/jpeg, toàn cảnh, tối đa 1280 × 720 và 2 MiB.'],
    ['captured_at', 'Thời điểm chụp ISO 8601 có timezone, ví dụ 2026-10-25T12:00:00Z.'],
], [1900, 7738])
para('Ảnh mới trong 60 giây, cho phép đồng hồ nhanh tối đa 5 giây. Start luôn kiểm tra độ mới, kể cả khi API nhận diện cũ được cấu hình bỏ qua tuổi ảnh. Tổng request tối đa 2 MiB + 16 KiB. Không gửi RGB thô, base64, driver_id, vehicle_id hoặc session_id.')
para('Server tự nhận diện, kiểm tra tài khoản, hồ sơ, khuôn mặt, GPLX, phân công và phiên đang mở. Khi đủ điều kiện, server đặt thời gian bắt đầu và lưu phiên gắn với thiết bị nguồn.')
sub('Response mở phiên thành công')
code('''{
  "ok": true,
  "code": "SESSION_STARTED",
  "message": "Đã bắt đầu phiên lái.",
  "request_id": "cc57f9f4-524c-4609-a589-77625caa8001",
  "server_time": "2026-10-25T12:00:02+00:00",
  "action": "NONE",
  "retry_after_seconds": null,
  "data": {
    "session_id": 120,
    "status": "STARTED",
    "vehicle_id": 5,
    "driver": {"id": 12, "full_name": "Nguyễn Văn A"},
    "started_at": "2026-10-25T12:00:02+00:00",
    "ended_at": null
  }
}''', 'json')
para('Điều kiện chuyển Pi sang trạng thái đang lái: HTTP 201 và code SESSION_STARTED. Lưu session_id để kết thúc phiên. Không dùng chỉ ok=true hoặc HTTP 200 để kết luận đã mở phiên.', 'Normal')
page()

heading('4 Kết thúc phiên và xử lý timeout')
code('POST /api/v1/device/sessions/120/end/')
para('Gửi body rỗng, không gửi JSON {} và không gửi ended_at. Server kiểm tra thiết bị nguồn, đặt thời gian kết thúc và trả HTTP 200 với code SESSION_ENDED. data có cùng cấu trúc session ở trang trước, status=ENDED và ended_at khác null.')
para('Gửi lại cùng session_id trả kết quả đã kết thúc, giữ nguyên ended_at. Chỉ thiết bị đã mở phiên được đóng phiên đó. Phiên không tồn tại hoặc thuộc thiết bị khác đều trả 404 SESSION_NOT_FOUND.')
para('Vẫn được kết thúc khi tài xế bị khóa, xe ngừng hoạt động, thiết bị bảo trì hoặc phân công hết hạn, miễn API key còn hợp lệ. Mất mạng không tự kết thúc phiên trên server.')
sub('Các trạng thái Pi nên quản lý')
table(['Trạng thái', 'Hành động'], [
    ['Chưa có phiên', 'Cho phép bấm bắt đầu. Chụp frame mới và gọi start.'],
    ['Đang gọi start', 'Khóa nút gửi lặp, giữ vòng camera chạy. Chỉ một request điều khiển đang chờ.'],
    ['Đang lái', 'Giữ session_id, chạy AI và cảnh báo Pi → ESP32 khi cần.'],
    ['Đang gọi end', 'Giữ session_id đến khi nhận SESSION_ENDED.'],
    ['Chưa rõ kết quả', 'Mạng timeout không đồng nghĩa thất bại. Đọc context để đối soát.'],
], [2550, 7088])
sub('Start bị timeout hoặc Pi vừa khởi động lại')
para('Gọi context. Nếu active_session có giá trị, hiển thị đúng tài xế và phiên để người vận hành kiểm tra trước khi tiếp tục. Nếu null, không tự coi là đã được phép lái; khi người dùng bắt đầu lại, chụp ảnh mới và gửi start. Nếu không đọc được context, giữ trạng thái chưa xác định và báo lỗi kết nối.')
sub('End bị timeout')
para('Giữ session_id và gửi lại end cùng ID. Không xóa ID chỉ vì timeout. Chỉ bỏ phiên cục bộ khi nhận SESSION_ENDED hoặc sau bước đối soát rõ ràng. Nếu bị 401 thì liên hệ nhóm server cấp lại khóa, không gửi dồn dập.')
para('Phiên lịch sử trước khi bổ sung source_device không thuộc thiết bị nào. Nếu phiên cũ còn STARTED chặn xe, nhóm server cần đối soát trước demo; Pi không tự đóng hoặc đoán quyền sở hữu.', 'Small')
page()

heading('5 Đọc lỗi và thông báo cho người dùng')
para('Pi lập trình theo code và action; message dùng hiển thị. Log tối thiểu: HTTP status, code, request_id và thời điểm. Không log token, byte ảnh hoặc vector khuôn mặt.')
table(['HTTP và code', 'Pi xử lý'], [
    ['200 FACE_NOT_MATCHED\n200 FACE_AMBIGUOUS', 'Chưa mở phiên. Yêu cầu nhìn thẳng và chụp ảnh mới.'],
    ['200 DRIVER_NOT_FOUND', 'Chưa có hồ sơ khuôn mặt để đối chiếu; liên hệ server.'],
    ['401 DEVICE_UNAUTHORIZED', 'Kiểm tra API key, cấp lại nếu cần; dừng retry liên tục.'],
    ['403 DEVICE_MAINTENANCE\n403 VEHICLE_INACTIVE', 'Không mở phiên; kiểm tra trạng thái thiết bị/xe.'],
    ['403 DRIVER_NOT_ELIGIBLE', 'Admin kiểm tra hồ sơ, GPLX, hệ hạng và thông số xe.'],
    ['403 NO_ACTIVE_ASSIGNMENT', 'Admin kiểm tra phân công đúng tài xế, xe và thời gian.'],
    ['409 ASSIGNMENT_AMBIGUOUS', 'Admin xử lý các phân công trùng thời gian.'],
    ['409 SESSION_ALREADY_ACTIVE', 'Đọc context, không tự gọi start liên tục.'],
    ['409 DEVICE_ASSIGNMENT_CHANGED', 'Đọc lại context, chờ theo response rồi chụp mới.'],
    ['404 SESSION_NOT_FOUND', 'Kiểm tra session_id và thiết bị nguồn; không đổi ID để thử.'],
    ['422 STALE_FRAME\n422 FACE_NOT_USABLE', 'Chụp ảnh mới; kiểm tra đồng hồ, ánh sáng và khuôn mặt.'],
    ['400 INVALID_FIELDS\n400 INVALID_CAPTURE_TIME', 'Sửa tên trường và timestamp có timezone.'],
    ['400 INVALID_JPEG\n400 INVALID_RESOLUTION', 'Encode JPEG đúng kích thước, không gửi base64.'],
    ['413 FRAME_TOO_LARGE\n415 UNSUPPORTED_IMAGE', 'Giảm ảnh về giới hạn, gửi MIME image/jpeg.'],
    ['503 MATCHING_NOT_CONFIGURED\n503 HF_NOT_CONFIGURED', 'Nhóm server cấu hình matching hoặc HF.'],
    ['503 HF_UNAVAILABLE\n504 HF_TIMEOUT', 'Đợi retry_after_seconds rồi chụp frame mới để thử lại.'],
    ['502 HF_CONTRACT_ERROR\n502 INVALID_EMBEDDING', 'Nhóm server kiểm tra dịch vụ embedding.'],
], [4500, 5138])
para('Proxy có thể trả HTML hoặc lỗi không đúng envelope. Bắt cả lỗi kết nối lẫn lỗi parse JSON. Timeout gợi ý: connect 5 giây, đọc start 45 giây; context/end 10 giây. Không retry mọi mã lỗi bằng cùng một quy tắc.', 'Small')
page()

heading('6 Mã Python để thử giao tiếp')
para('Ví dụ dùng requests và một file JPEG vừa chụp để kiểm tra đường truyền. Đặt biến môi trường như trang 1. Với camera thật, timestamp phải là thời điểm lấy frame, không thay timestamp mới cho ảnh cũ.')
code('''import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import requests

BASE = os.environ["WEB_SERVER_URL"].rstrip("/")
http = requests.Session()
http.headers["Authorization"] = (
    "Bearer " + os.environ["DEVICE_API_KEY"]
)

def call(method, endpoint, **kwargs):
    response = http.request(
        method, BASE + "/api/v1/device/" + endpoint,
        headers={"X-Request-ID": str(uuid4())},
        timeout=(5, 45), allow_redirects=False, **kwargs
    )
    body = response.json()  # ValueError nếu không phải JSON
    print(response.status_code, body.get("code"),
          body.get("message"), body.get("request_id"))
    return response.status_code, body

def get_context():
    return call("GET", "context/")

def start_session(jpeg_bytes, captured_at):
    return call("POST", "sessions/start/",
        data={"captured_at": captured_at},
        files={"frame": ("frame.jpg", jpeg_bytes, "image/jpeg")})

def end_session(session_id):
    # Không truyền json={}, data hoặc ended_at.
    return call("POST", f"sessions/{session_id}/end/")

try:
    status, body = get_context()
    # Sau khi camera vừa chụp frame.jpg:
    captured_at = datetime.now(timezone.utc).isoformat()
    status, body = start_session(
        Path("frame.jpg").read_bytes(), captured_at
    )
    if status == 201 and body.get("code") == "SESSION_STARTED":
        session_id = body["data"]["session_id"]
        print("Phiên đã mở:", session_id)
        # Chỉ gọi khi người dùng bấm kết thúc:
        # status, body = end_session(session_id)
except (requests.RequestException, ValueError) as exc:
    print("Chưa xác định được kết quả:", type(exc).__name__)
    # Đọc context khi kết nối lại; không tự coi start đã thất bại.
finally:
    http.close()
''', 'python')
para('Đây là script thử một lần, không thay thế vòng điều khiển camera. Nếu context báo phiên đang chạy, kiểm tra phiên đó trước khi thực hiện start trong ví dụ.', 'Small')
page()

heading('7 Ghép camera và kiểm thử tích hợp')
sub('Dùng client có sẵn trong dự án')
para('File examples/raspberry_pi/face_client.py có FaceClient và BestFrameSelector. Selector nhận frame BGR và boxes khuôn mặt từ NanoDet, chọn một frame toàn cảnh rõ nét; client resize và encode JPEG trong RAM.')
code('''from face_client import FaceClient, BestFrameSelector

client = FaceClient()
selector = BestFrameSelector(stable_frames=6)
# Trong camera loop, chỉ khi người dùng muốn bắt đầu:
selected = selector.update(frame_bgr, face_boxes)
if selected is not None:
    frame, captured_at = selected
    status, body = client.start_session(frame, captured_at)
    if status == 201 and body["code"] == "SESSION_STARTED":
        session_id = body["data"]["session_id"]
''', 'python')
para('Các biến frame_bgr, face_boxes và thao tác nút do chương trình Pi cung cấp. Chạy request trong worker hoặc cách xử lý không khóa camera/loa; giữ tối đa một request start/end đang chờ. Bắt lỗi mạng như trang 6. Gọi client.close() khi chương trình dừng.')
sub('Phân biệt nhận diện và mở phiên')
para('client.verify() gọi face-verifications/, chỉ trả danh tính và verified. Endpoint này có thể nhận diện tài xế chưa được phân công hoặc chưa đủ điều kiện lái. client.start_session() mới kiểm tra quyền và cấp session_id; không cần gọi verify trước start.')
sub('Checklist demo phía Pi')
table(['Ca thử', 'Kết quả cần thấy'], [
    ['Token đúng và sai', 'Context thành công; token sai trả 401.'],
    ['Tài xế đủ điều kiện', 'Start trả 201 và session_id, web có phiên STARTED.'],
    ['Không phân công / GPLX không hợp lệ', 'Start bị từ chối, không tạo phiên.'],
    ['Ảnh cũ / không khớp', 'Yêu cầu chụp lại, không cấp session_id.'],
    ['Bấm bắt đầu lần hai', 'Không có phiên trùng; context trả phiên đang có.'],
    ['Kết thúc hai lần', 'Cùng ended_at, web chỉ có một phiên ENDED.'],
    ['Thiết bị khác gọi end', 'Trả 404, phiên gốc không bị thay đổi.'],
    ['Tắt mạng / Pi khởi động lại', 'Báo chưa rõ kết quả và đọc context khi kết nối lại.'],
], [4100, 5538])
page()

heading('8 Chuẩn bị bước gửi vi phạm sau session')
para('Phần này là thiết kế tương lai, chưa có trong route server tại thời điểm 25/10/2026. Nhóm Pi có thể chuẩn bị cấu trúc dữ liệu nhưng không gọi để kiểm thử như API đã hoạt động.')
sub('Vi phạm kèm ảnh')
para('Dự kiến POST violations/ dạng multipart: event_id UUID giữ nguyên khi retry, session_id do server cấp, violation_code theo catalog, detected_at có timezone, confidence và file image JPEG. Không gửi từng frame; gom một đợt hành vi thành một sự kiện.')
code('''{
  "event_id": "c5e15bac-956e-45e2-913a-25ad82748001",
  "session_id": 120,
  "violation_code": "DROWSINESS",
  "detected_at": "2026-10-25T12:05:00Z",
  "confidence": 0.94
}''', 'json')
para('Ví dụ chỉ thể hiện phần text, file image đi kèm multipart. Mã loại và giới hạn bằng chứng sẽ chốt khi triển khai. Dữ liệu AI tạo vi phạm PENDING để admin duyệt, không tự coi là vi phạm đã xác nhận.')
sub('Heartbeat và lỗi thiết bị')
para('Dự kiến POST heartbeat/ mỗi 30 giây với camera_ok, model_ok, error_message. Lỗi camera/model là lỗi kỹ thuật, không phải vi phạm tài xế. Hiện server chưa nhận heartbeat, chưa tự đánh giá mất kết nối theo chu kỳ này.')
code('{"camera_ok": false, "model_ok": true,\n "error_message": "Không đọc được camera"}', 'json')
sub('Cảnh báo ESP32')
para('Pi phát hiện hành vi thì có thể gửi tín hiệu cho ESP32 để phát loa ngay. Không chờ admin duyệt hoặc response server mới cảnh báo. Tài liệu này không quy định UART, Wi-Fi, MQTT hay payload Pi–ESP32; hai bên phần cứng cần thống nhất riêng.')
sub('Tài liệu và mã nguồn đối chiếu')
para('Hợp đồng session: docs/session_api.md.\nHợp đồng nhận diện: docs/raspberry_pi_api.md.\nPhác thảo vi phạm và heartbeat: docs/ai_server_protocol.md.\nClient Pi: examples/raspberry_pi/face_client.py.\nRoute và xử lý server: driving/device_urls.py, driving/session_api.py, driving/device_api.py.')
para('API được đối chiếu với mã nguồn hiện tại. Ví dụ IP, tên, ID và thời gian chỉ minh họa; không phải thông tin truy cập thật. Cần nghiệm thu trên Pi/camera và mạng thực tế trước khi demo chính thức.', 'Small')


styles = f'''<w:styles xmlns:w="{W}">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Arial"/><w:sz w:val="21"/><w:color w:val="000000"/><w:lang w:val="vi-VN"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="110" w:line="270" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:pPr><w:widowControl/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:after="180" w:line="560" w:lineRule="auto"/></w:pPr><w:rPr><w:b/><w:sz w:val="38"/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/></w:pPr><w:rPr><w:sz w:val="24"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="140"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="29"/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="130" w:after="90"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="23"/><w:color w:val="000000"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="220" w:lineRule="exact"/><w:widowControl w:val="0"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Small"><w:name w:val="Small"/><w:basedOn w:val="Normal"/><w:rPr><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Spacer"><w:name w:val="Spacer"/><w:pPr><w:spacing w:after="20" w:line="60" w:lineRule="exact"/></w:pPr><w:rPr><w:sz w:val="4"/></w:rPr></w:style>
</w:styles>'''
sect = '<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/><w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1020" w:right="1134" w:bottom="1020" w:left="1134" w:header="450" w:footer="450"/></w:sectPr>'
document = f'<w:document xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>{"".join(parts)}{sect}</w:body></w:document>'
header = f'<w:hdr xmlns:w="{W}">{p("SAVELIFE   |   HƯỚNG DẪN TÍCH HỢP RASPBERRY PI", "Small")}</w:hdr>'
footer = f'<w:ftr xmlns:w="{W}"><w:p><w:pPr><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t>SaveLife  •  Trang </w:t></w:r><w:fldSimple w:instr="PAGE"/></w:p></w:ftr>'
content_types = '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/><Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'''
rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>'
doc_rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/><Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>'
core = '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Hướng dẫn Raspberry Pi giao tiếp với server SaveLife</dc:title><dc:creator>SaveLife</dc:creator><dc:description>Hướng dẫn tích hợp session và xử lý giao tiếp dành cho nhóm Raspberry Pi</dc:description></cp:coreProperties>'
with ZipFile(OUT, 'w', ZIP_DEFLATED) as z:
    for name, data in {'[Content_Types].xml': content_types, '_rels/.rels': rels,
                       'word/document.xml': document, 'word/styles.xml': styles,
                       'word/_rels/document.xml.rels': doc_rels,
                       'word/header1.xml': header, 'word/footer1.xml': footer,
                       'docProps/core.xml': core}.items():
        z.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + data)
print(OUT)
