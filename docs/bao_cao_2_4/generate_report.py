"""Generate report illustrations and a self-contained DOCX; no network or DB access."""
from pathlib import Path
from html import escape
from zipfile import ZipFile, ZIP_DEFLATED
import math
import re
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
IMG = ROOT / 'images'
SRC = ROOT / 'sources'
IMG.mkdir(exist_ok=True)
SRC.mkdir(exist_ok=True)
FONT = 'C:/Windows/Fonts/arial.ttf'
BOLD = 'C:/Windows/Fonts/arialbd.ttf'
INK, BLUE, PALE, GRAY = '#18334D', '#25638A', '#EDF5FA', '#627182'


class Figure:
    def __init__(self, name, title, subtitle, w=1600, h=1000):
        self.name, self.w, self.h = name, w, h
        self.im = Image.new('RGB', (w, h), 'white')
        self.d = ImageDraw.Draw(self.im)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/>']
        self.text(w/2, 48, title, 34, bold=True)
        self.text(w/2, 92, subtitle, 22, color=GRAY)

    def text(self, x, y, text, size=24, color=INK, bold=False):
        font = ImageFont.truetype(BOLD if bold else FONT, size)
        for i, line in enumerate(text.split('\n')):
            yy = y + i * (size + 9)
            self.d.text((x, yy), line, fill=color, font=font, anchor='mm')
            self.svg.append(f'<text x="{x}" y="{yy}" text-anchor="middle" dominant-baseline="central" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(line)}</text>')

    def line(self, points, arrow=True, dashed=False, color=BLUE):
        for a, b in zip(points, points[1:]):
            if dashed:
                dx, dy = b[0]-a[0], b[1]-a[1]
                length = math.hypot(dx, dy)
                for start in range(0, int(length), 16):
                    t1, t2 = start/length, min(start+8, length)/length
                    self.d.line((a[0]+dx*t1, a[1]+dy*t1, a[0]+dx*t2, a[1]+dy*t2), fill=color, width=3)
            else:
                self.d.line((a, b), fill=color, width=3)
        pts = ' '.join(f'{x},{y}' for x, y in points)
        dash = ' stroke-dasharray="8 8"' if dashed else ''
        self.svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="3"{dash}/>')
        if arrow:
            a, b = points[-2:]
            angle = math.atan2(b[1]-a[1], b[0]-a[0])
            tri = [b, (b[0]-15*math.cos(angle-.45), b[1]-15*math.sin(angle-.45)), (b[0]-15*math.cos(angle+.45), b[1]-15*math.sin(angle+.45))]
            self.d.polygon(tri, fill=color)
            self.svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in tri)}" fill="{color}"/>')

    def box(self, x, y, w, h, label, size=25, fill=PALE):
        self.d.rounded_rectangle((x,y,x+w,y+h), radius=15, fill=fill, outline=BLUE, width=3)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="15" fill="{fill}" stroke="{BLUE}" stroke-width="3"/>')
        lines = label.count('\n')+1
        self.text(x+w/2, y+h/2-(lines-1)*(size+9)/2, label, size)

    def save(self):
        self.text(self.w/2, self.h-30, 'SaveLife • Sơ đồ theo mã nguồn dự án • Dùng kèm mô tả phạm vi triển khai', 19, color=GRAY)
        self.im.save(IMG / f'{self.name}.png', dpi=(220,220))
        (IMG / f'{self.name}.svg').write_text('\n'.join(self.svg+['</svg>']), encoding='utf-8')


f = Figure('01_kien_truc', 'KIẾN TRÚC TỔNG THỂ PHẦN MỀM', 'Ứng dụng Django tập trung, tích hợp lưu trữ ảnh và dịch vụ nhận diện')
f.box(70,170,420,115,'Trình duyệt web\nQuản trị viên / Tài xế')
f.box(1090,170,420,115,'Raspberry Pi + Camera\nGửi ảnh nhận diện')
f.box(450,400,700,170,'MÁY CHỦ DJANGO\nGiao diện • Phân quyền • Nghiệp vụ\nAPI thiết bị • So khớp khuôn mặt',28)
f.line([(280,285),(280,350),(620,350),(620,400)])
f.text(370,322,'Yêu cầu web / biểu mẫu',22)
f.line([(1300,285),(1300,350),(990,350),(990,400)])
f.text(1210,322,'API + JPEG / JSON',22)
for x, label in [(70,'PostgreSQL\nDữ liệu quan hệ\nEmbedding JSON'),(590,'Cloudinary\nẢnh hồ sơ, GPLX\nURL + public ID'),(1110,'Face Embedding API\nẢnh → vector\nDịch vụ bên ngoài')]:
    f.box(x,740,420,150,label)
for x in [280,800,1320]:
    f.line([(800,570),(800,650),(x,650),(x,740)])
for x, label in [(280, 'Django ORM'), (800, 'SDK / API'), (1320, 'HTTP API')]:
    f.text(x,697,label,22)
f.save()

f = Figure('02_chuc_nang','PHÂN RÃ CHỨC NĂNG THEO TÁC NHÂN','Nhóm chức năng; không biểu diễn quan hệ include/extend của UML')
for x,title,body in [
    (60,'QUẢN TRỊ VIÊN','Quản lý và duyệt hồ sơ\nQuản lý xe, loại xe\nPhân công tài xế\nQuản lý thiết bị\nTra cứu phiên lái\nXét duyệt vi phạm'),
    (560,'TÀI XẾ','Đăng ký, đăng nhập\nĐổi mật khẩu\nCập nhật hồ sơ, GPLX\nCập nhật ảnh khuôn mặt\nXem xe được phân công\nXem phiên lái, vi phạm'),
    (1060,'RASPBERRY PI','Xác thực bằng khóa API\nLấy ngữ cảnh thiết bị\nGửi ảnh JPEG\nNhận kết quả danh tính\nNhận mã lỗi / yêu cầu\nchụp lại khi cần')]:
    f.box(x,180,480,90,title,27)
    f.line([(x+240,270),(x+240,330)])
    f.box(x,330,480,370,body,26)
f.box(200,790,1200,100,'Hướng hoàn thiện: tự mở/kết thúc phiên • Nhận vi phạm AI • Kháng cáo',25, '#FFF5E5')
f.save()

f = Figure('03_du_lieu','QUAN HỆ DỮ LIỆU CỐT LÕI','Nhãn 1 : N nghĩa là một–nhiều; nhãn 1 : 0..1 nghĩa là tối đa một',1800,1150)
boxes = {
'u':(60,180,300,80,'User'), 'd':(60,370,300,80,'DriverProfile'),
'l':(470,240,300,80,'DriverLicense'), 'f':(470,450,300,80,'FaceProfile'),
't':(1390,180,330,80,'VehicleType'), 'v':(1390,370,330,80,'Vehicle'),
'a':(580,650,640,90,'DriverVehicleAssignment'),
's':(690,830,420,80,'DrivingSession'),
'i':(690,1000,420,80,'Violation'),
'e':(60,1000,300,80,'Evidence'), 'r':(1390,1000,330,80,'ViolationReview'),
'dev':(1390,650,330,80,'Device')}
for x,y,w,h,label in boxes.values(): f.box(x,y,w,h,label,25)
def rel(points,x,y,label):
    f.line(points,arrow=False)
    f.text(x,y,label,22)
rel([(210,260),(210,370)],280,313,'1 : 0..1')
rel([(360,410),(410,410),(410,280),(470,280)],420,218,'1 : 0..1')
rel([(360,410),(410,410),(410,490),(470,490)],420,550,'1 : 0..1')
rel([(1555,260),(1555,370)],1620,315,'1 : N')
rel([(210,450),(210,695),(580,695)],390,670,'1 : N')
rel([(1555,450),(1555,570),(1100,570),(1100,650)],1280,550,'1 : N')
rel([(1555,450),(1760,450),(1760,690),(1720,690)],1665,610,'1 : 0..1')
rel([(900,740),(900,830)],973,785,'1 : N')
rel([(900,910),(900,1000)],973,955,'1 : N')
rel([(690,1040),(360,1040)],520,1008,'1 : N')
rel([(1110,1040),(1390,1040)],1250,1008,'1 : N')
f.text(400,880,'Lược bớt: ViolationType, Appeal;\nquan hệ xe–phiên, người duyệt–lịch sử.\nXem ERD đầy đủ trong sources.',21,color=GRAY)
f.save()

f = Figure('04_ho_so','CẬP NHẬT VÀ XÉT DUYỆT HỒ SƠ','Luồng nghiệp vụ tổng quát; trạng thái được tính theo các thành phần hồ sơ',1600,1180)
steps=[(520,150,'Tài xế đăng ký / đăng nhập'),(520,310,'Nhập thông tin, GPLX\nvà chọn ảnh khuôn mặt'),(520,490,'Kiểm tra dữ liệu và ảnh\nUpload Cloudinary / tạo embedding'),(520,670,'Lưu dữ liệu và tính trạng thái\nThành phần mới → chờ duyệt'),(520,850,'Admin duyệt GPLX, khuôn mặt\nKiểm tra hồ sơ tổng thể')]
for x,y,label in steps: f.box(x,y,580,100,label,25)
for a,b in zip(steps,steps[1:]): f.line([(810,a[1]+100),(810,b[1])])
f.box(50,490,360,115,'Lỗi dữ liệu / dịch vụ\nThông báo để sửa lại',23,'#FFF5E5')
f.line([(520,540),(410,540)])
f.line([(230,490),(230,360),(520,360)],dashed=True)
f.box(1150,670,400,115,'Thiếu thành phần: INCOMPLETE\nCó mục chờ duyệt: PENDING',21)
f.line([(1100,720),(1150,720)])
f.box(280,1020,400,80,'Đạt điều kiện: APPROVED',24)
f.box(950,1020,400,80,'Từ chối: REJECTED',24, '#FFF5E5')
f.line([(810,950),(810,980),(480,980),(480,1020)])
f.line([(810,950),(810,980),(1150,980),(1150,1020)])
f.save()

f = Figure('05_nhan_dien','TUẦN TỰ NHẬN DIỆN TÀI XẾ','Luồng thành công; ảnh nhận diện được xử lý trong bộ nhớ',1800,1160)
xs=[190,670,1160,1600]
for x,label in zip(xs,['Raspberry Pi','Django API','Face API','PostgreSQL']):
    f.box(x-150,160,300,85,label,26)
    f.line([(x,245),(x,980)],arrow=False,dashed=True,color=GRAY)
def msg(a,b,y,label,reply=False):
    f.line([(xs[a],y),(xs[b],y)],dashed=reply)
    f.text((xs[a]+xs[b])/2,y-25,label,22)
msg(0,1,320,'1. Khóa API + ảnh JPEG')
f.box(490,360,360,80,'2. Kiểm tra thiết bị,\nxe và dữ liệu đầu vào',22)
msg(1,2,490,'3. POST /extract_single')
msg(2,1,590,'4. Trả vector đặc trưng',True)
msg(1,3,690,'5. Đọc hồ sơ có embedding')
msg(3,1,780,'6. Trả dữ liệu hồ sơ',True)
f.box(480,825,380,80,'7. So khớp cosine\nKiểm tra ngưỡng và biên',22)
msg(1,0,960,'8. Trả JSON nhận diện',True)
f.box(160,1030,1480,70,'Chưa kiểm tra quyền lái theo phân công; chưa tự tạo phiên lái trong luồng này.',24,'#FFF5E5')
f.save()

f = Figure('06_vi_pham','XÉT DUYỆT VI PHẠM','Luồng đã triển khai cho các bản ghi vi phạm có sẵn trong cơ sở dữ liệu',1600,1120)
f.box(560,150,480,85,'Vi phạm PENDING',28)
f.box(560,320,480,100,'Admin xem chi tiết\nvà bằng chứng',26)
f.line([(800,235),(800,320)])
f.box(150,520,480,120,'Xác nhận\nCó ≥ 1 bằng chứng\nMetadata hợp lệ',25)
f.box(970,520,480,120,'Từ chối\nGhi nhận quyết định\nvà thông tin xử lý',25)
f.line([(800,420),(800,470),(390,470),(390,520)])
f.line([(800,420),(800,470),(1210,470),(1210,520)])
f.box(150,730,480,85,'APPROVED',28)
f.box(970,730,480,85,'REJECTED',28)
f.line([(390,640),(390,730)])
f.line([(1210,640),(1210,730)])
f.box(550,900,500,85,'Ghi ViolationReview\nCùng giao dịch với cập nhật',24)
f.line([(390,815),(390,940),(550,940)])
f.line([(1210,815),(1210,940),(1050,940)])
f.line([(150,770),(60,770),(60,190),(560,190)],dashed=True)
f.text(300,275,'Xem xét lại → PENDING\nChỉ khi chưa có kháng cáo',22)
f.line([(1450,770),(1530,770),(1530,190),(1040,190)],dashed=True)
f.text(1280,275,'Xem xét lại → PENDING\nChỉ khi chưa có kháng cáo',22)
f.text(800,1040,'REVOKED có trong mô hình; quy trình xử lý kháng cáo chưa được triển khai.',23,color=GRAY)
f.save()

mermaids = {
'01_kien_truc': '''flowchart TB
 W[Trình duyệt: Admin / Tài xế] -->|Yêu cầu web| D[Django: giao diện, nghiệp vụ, API]
 P[Raspberry Pi + Camera] -->|API thiết bị + JPEG| D
 D -->|ORM| DB[(PostgreSQL)]
 D -->|Ảnh hồ sơ, GPLX| C[Cloudinary]
 D -->|Ảnh| F[Face Embedding API]
 F -->|Vector| D
 D -->|Kết quả nhận diện| P
''',
'02_chuc_nang': '''flowchart LR
 A[Quản trị viên] --> A1[Quản lý, duyệt hồ sơ và GPLX]
 A --> A2[Quản lý xe, thiết bị, phân công]
 A --> A3[Tra cứu phiên và xét duyệt vi phạm]
 U[Tài xế] --> U1[Tài khoản, cập nhật hồ sơ và GPLX]
 U --> U2[Xem xe, phiên lái, vi phạm được phép]
 P[Raspberry Pi] --> P1[Lấy ngữ cảnh, gửi ảnh, nhận danh tính]
''',
'03_du_lieu': '''erDiagram
 User ||--o| DriverProfile : user
 DriverProfile ||--o| DriverLicense : driver
 DriverProfile ||--o| FaceProfile : driver
 VehicleType ||--o{ Vehicle : vehicle_type
 Vehicle ||--o| Device : vehicle
 DriverProfile ||--o{ DriverVehicleAssignment : driver
 Vehicle ||--o{ DriverVehicleAssignment : vehicle
 DriverVehicleAssignment ||--o{ DrivingSession : assignment
 Vehicle ||--o{ DrivingSession : vehicle
 DrivingSession ||--o{ Violation : session
 ViolationType ||--o{ Violation : violation_type
 Violation ||--o{ Evidence : violation
 Violation ||--o| Appeal : violation
 Violation ||--o{ ViolationReview : violation
 User ||--o{ ViolationReview : reviewer
''',
'04_ho_so': '''flowchart TD
 A[Đăng ký / đăng nhập] --> B[Nhập hồ sơ, GPLX, ảnh]
 B --> C[Kiểm tra dữ liệu, upload và tạo embedding]
 C -->|Lỗi| B
 C -->|Thành công| D[Lưu dữ liệu và tính trạng thái]
 D --> E[Admin duyệt GPLX, khuôn mặt và hồ sơ]
 E -->|Đạt điều kiện| F[APPROVED]
 E -->|Từ chối| G[REJECTED]
 D --- N[Thiếu: INCOMPLETE; có mục chờ duyệt: ưu tiên PENDING]
''',
'05_nhan_dien': '''sequenceDiagram
 participant P as Raspberry Pi
 participant D as Django API
 participant F as Face API
 participant B as PostgreSQL
 P->>D: Khóa API + JPEG
 Note over D: Kiểm tra thiết bị, xe và dữ liệu
 D->>F: POST /extract_single
 F-->>D: Vector
 D->>B: Đọc hồ sơ có embedding
 B-->>D: Danh sách hồ sơ
 Note over D: So khớp cosine, kiểm tra ngưỡng và biên
 D-->>P: JSON nhận diện hoặc yêu cầu chụp lại
 Note over P,D: Chưa kiểm tra phân công; chưa tạo phiên lái
''',
'06_vi_pham': '''flowchart TD
 P[PENDING] --> R[Admin xem thông tin và bằng chứng]
 R --> A[Xác nhận: có bằng chứng, metadata hợp lệ]
 R --> X[Từ chối]
 A --> AP[APPROVED]
 X --> RJ[REJECTED]
 AP --> L[Ghi ViolationReview cùng giao dịch]
 RJ --> L
 AP -. Xem xét lại khi chưa có kháng cáo .-> P
 RJ -. Xem xét lại khi chưa có kháng cáo .-> P
'''}
for name, source in mermaids.items():
    (SRC / f'{name}.mmd').write_text(source,encoding='utf-8')

# Standard-library Open XML writer: headings, paragraphs, tables and embedded PNGs.
NS = 'http://schemas.openxmlformats.org/'
W = NS + 'wordprocessingml/2006/main'
R = NS + 'officeDocument/2006/relationships'
body, rels, media = [], [], []
def run(text, bold=False):
    return f'<w:r>{"<w:rPr><w:b/></w:rPr>" if bold else ""}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
def para(text, style=None):
    prop = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{prop}{run(text)}</w:p>'
def table(rows):
    out=['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>']
    for edge in ['top','left','bottom','right','insideH','insideV']:
        out.append(f'<w:{edge} w:val="single" w:sz="4" w:color="BBBBBB"/>')
    out.append('</w:tblBorders></w:tblPr>')
    for i,row in enumerate(rows):
        out.append('<w:tr>')
        for cell in row:
            out.append('<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr><w:p>'+run(cell,bold=i==0)+'</w:p></w:tc>')
        out.append('</w:tr>')
    return ''.join(out)+'</w:tbl>'
text = (ROOT/'2_4_giai_phap_phan_mem.md').read_text(encoding='utf-8')
rows=[]
for line in text.splitlines()+['']:
    if line.startswith('|'):
        cells=[s.strip() for s in line.strip('|').split('|')]
        if not all(re.fullmatch(r'[-: ]+',s) for s in cells): rows.append(cells)
        continue
    if rows:
        body.append(table(rows)); rows=[]
    if not line.strip(): continue
    m=re.match(r'!\[(.*?)\]\((.*?)\)',line)
    if m:
        caption,path=m.groups(); p=ROOT/path
        n=len(media)+1; rid=f'rIdImage{n}'
        with Image.open(p) as im: width,height=im.size
        cx=5_900_000; cy=round(cx*height/width)
        media.append(p)
        rels.append(f'<Relationship Id="{rid}" Type="{R}/image" Target="media/{p.name}"/>')
        body.append(f'''<w:p><w:pPr><w:jc w:val="center"/><w:keepNext/></w:pPr><w:r><w:drawing><wp:inline xmlns:wp="{NS}drawingml/2006/wordprocessingDrawing"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{n}" name="{p.stem}"/><a:graphic xmlns:a="{NS}drawingml/2006/main"><a:graphicData uri="{NS}drawingml/2006/picture"><pic:pic xmlns:pic="{NS}drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{n}" name="{p.name}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>''')
        body.append(para(caption,'Caption'))
    elif line.startswith('#'):
        level=len(line)-len(line.lstrip('#'))
        body.append(para(line.lstrip('# ').strip(),f'Heading{min(level,3)}'))
    else:
        body.append(para('• '+line[2:] if line.startswith('- ') else line))
sect='<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1417"/></w:sectPr>'
doc=f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{"".join(body)}{sect}</w:body></w:document>'
styles=f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="26"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'''
for level,size in [(1,32),(2,28),(3,26)]:
    styles+=f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:name w:val="heading {level}"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:outlineLvl w:val="{level-1}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{size}"/></w:rPr></w:style>'
styles+='<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:i/><w:sz w:val="24"/></w:rPr></w:style></w:styles>'
pkgrel=NS+'package/2006/relationships'
with ZipFile(ROOT/'2_4_Giai_phap_phan_mem_SaveLife.docx','w',ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml',f'<Types xmlns="{NS}package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
    z.writestr('_rels/.rels',f'<Relationships xmlns="{pkgrel}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>')
    z.writestr('word/document.xml',doc)
    z.writestr('word/styles.xml',styles)
    z.writestr('word/_rels/document.xml.rels',f'<Relationships xmlns="{pkgrel}"><Relationship Id="rIdStyles" Type="{R}/styles" Target="styles.xml"/>{"".join(rels)}</Relationships>')
    for p in media: z.write(p,'word/media/'+p.name)

# HTML is a convenient local figure gallery, independent of Word.
gallery='<!doctype html><html lang="vi"><meta charset="utf-8"><title>Sơ đồ SaveLife</title><style>body{font:18px Arial;max-width:1100px;margin:40px auto;color:#18334d}img{width:100%;border:1px solid #ddd}figure{margin:45px 0}figcaption{margin:12px 0}a{color:#25638a}</style><h1>Bộ sơ đồ mục 2.4 – SaveLife</h1><p>Mở bản Word để lấy nội dung và hình đã chèn. PNG dùng trực tiếp; SVG có thể phóng to; Mermaid dùng để chỉnh sửa.</p>'
for p in sorted(IMG.glob('*.png')):
    gallery+=f'<figure><img src="images/{p.name}" alt="{p.stem}"><figcaption>{p.stem} — <a href="images/{p.name}">PNG</a> · <a href="images/{p.stem}.svg">SVG</a> · <a href="sources/{p.stem}.mmd">Mermaid</a></figcaption></figure>'
(ROOT/'xem_so_do.html').write_text(gallery+'</html>',encoding='utf-8')
print('Generated 6 PNGs, 6 SVGs, 6 Mermaid sources, DOCX and HTML gallery.')
