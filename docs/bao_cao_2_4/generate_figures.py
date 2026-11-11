"""Generate concise report diagrams, Mermaid sources and preview; offline only."""
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
        if subtitle: self.text(w/2, 92, subtitle, 22, color=GRAY)

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
        self.text(self.w/2, self.h-26, 'SaveLife', 18, color=GRAY)
        self.im.save(IMG / f'{self.name}.png', dpi=(220,220))
        (IMG / f'{self.name}.svg').write_text('\n'.join(self.svg+['</svg>']), encoding='utf-8')


def figure(name, title, subtitle='', h=820):
    return Figure(name, title, subtitle, w=1600, h=h)


f = figure('01_kien_truc', 'KIẾN TRÚC PHẦN MỀM')
f.box(170,150,480,100,'Web quản trị / tài xế',30)
f.box(950,150,480,100,'Raspberry Pi',30)
f.box(520,350,560,120,'DJANGO\nWeb • Nghiệp vụ • API',30)
f.line([(410,250),(410,310),(650,310),(650,350)])
f.line([(1190,250),(1190,310),(950,310),(950,350)])
for x,label in [(80,'PostgreSQL\nDữ liệu'),(580,'Cloudinary\nẢnh'),(1080,'Face API\nĐặc trưng khuôn mặt')]:
    f.box(x,620,440,110,label,28)
    f.line([(800,470),(800,550),(x+220,550),(x+220,620)])
f.save()

f = figure('02_chuc_nang', 'CÁC NHÓM CHỨC NĂNG')
for x,title,items in [
    (60,'QUẢN TRỊ VIÊN',['Duyệt hồ sơ','Quản lý xe & phân công','Thiết bị, phiên & vi phạm']),
    (570,'TÀI XẾ',['Tài khoản & hồ sơ','GPLX & khuôn mặt','Tra cứu xe, phiên, vi phạm']),
    (1080,'RASPBERRY PI',['Nhận diện tài xế','Mở / kết thúc phiên','Gửi vi phạm & ảnh'])]:
    f.box(x,150,460,95,title,28, '#DCECF5')
    for i,label in enumerate(items):
        y=330+i*135
        f.box(x,y,460,90,label,27)
        f.line([(x+230,245),(x+230,285),(x-20,285),(x-20,y+45),(x,y+45)],arrow=False)
f.save()

f = figure('03_du_lieu', 'DỮ LIỆU CỐT LÕI', 'Quan hệ tổng quát • Lược bỏ các bảng danh mục', h=980)
for x,y,w,label in [
    (100,160,400,'Tài xế'),(1100,160,400,'Phương tiện'),
    (100,370,400,'GPLX & khuôn mặt'),(600,370,400,'Phân công'),
    (1100,370,400,'Thiết bị'),(600,580,400,'Phiên lái'),
    (600,790,400,'Vi phạm'),(100,790,400,'Bằng chứng'),
    (1100,790,400,'Lịch sử xét duyệt')]:
    f.box(x,y,w,90,label,29)
def relation(points,x,y,label):
    f.line(points,arrow=False)
    f.text(x,y,label,23)
relation([(300,250),(300,370)],370,305,'0..1 mỗi loại')
relation([(500,205),(800,205),(800,370)],680,178,'1 : N')
relation([(1300,250),(1300,300),(900,300),(900,370)],1060,275,'1 : N')
relation([(1300,250),(1300,370)],1380,310,'1 : 0..1')
relation([(800,460),(800,580)],865,520,'1 : N')
relation([(800,670),(800,790)],865,730,'1 : N')
relation([(500,835),(600,835)],550,800,'N : 1')
relation([(1000,835),(1100,835)],1050,800,'1 : N')
f.save()

f = figure('04_ho_so', 'CẬP NHẬT VÀ DUYỆT HỒ SƠ')
for x,label in [(70,'Tài xế\nCập nhật hồ sơ'),(610,'Hệ thống\nKiểm tra & lưu'),(1150,'Quản trị viên\nXét duyệt')]:
    f.box(x,200,380,120,label,29)
f.line([(450,260),(610,260)])
f.line([(990,260),(1150,260)])
f.box(820,540,320,95,'Được duyệt',29,'#E5F3EA')
f.box(1200,540,320,95,'Bị từ chối',29,'#FFF0E3')
f.line([(1340,320),(1340,440),(980,440),(980,540)])
f.line([(1340,440),(1360,440),(1360,540)])
f.line([(1360,635),(1360,710),(260,710),(260,320)],dashed=True)
f.text(610,682,'Cập nhật và gửi lại',25)
f.save()

f = figure('05_nhan_dien', 'NHẬN DIỆN VÀ MỞ PHIÊN LÁI', 'Luồng tổng quát của API mở phiên', h=940)
for x,y,label in [(80,180,'Raspberry Pi\nGửi ảnh'),(610,180,'Nhận diện\nFace API + so khớp'),
                  (1140,180,'Kiểm tra quyền lái'),(1140,560,'Mở phiên'),
                  (610,560,'Kết thúc phiên')]:
    f.box(x,y,380,120,label,29)
f.line([(460,240),(610,240)])
f.line([(990,240),(1140,240)])
f.line([(1330,300),(1330,560)])
f.text(1400,430,'Hợp lệ',24)
f.line([(1140,620),(990,620)])
f.text(1065,690,'Pi yêu cầu',23)
f.box(80,560,380,120,'Không mở phiên',29,'#FFF0E3')
f.line([(800,300),(800,420),(270,420),(270,560)],dashed=True)
f.text(520,390,'Không nhận diện được',23)
f.line([(1140,270),(1060,270),(1060,480),(390,480),(390,560)],dashed=True)
f.text(730,510,'Không đủ điều kiện',23)
f.text(800,820,'Quyền lái: hồ sơ • GPLX • phân công • xe',27,color=GRAY)
f.save()

f = figure('06_vi_pham', 'TIẾP NHẬN VÀ XÉT DUYỆT VI PHẠM', h=900)
for x,label in [(70,'Raspberry Pi\nSự kiện + ảnh'),(610,'Máy chủ\nKiểm tra & lưu'),(1150,'Vi phạm\nChờ xác nhận')]:
    f.box(x,170,380,120,label,29)
f.line([(450,230),(610,230)])
f.line([(990,230),(1150,230)])
f.box(1150,410,380,110,'Quản trị viên\nXem bằng chứng',29)
f.line([(1340,290),(1340,410)])
f.box(610,410,380,110,'Xác nhận / Từ chối',29)
f.line([(1150,465),(990,465)])
f.box(70,410,380,110,'Lưu lịch sử duyệt',29)
f.line([(610,465),(450,465)])
f.line([(800,520),(800,710),(1480,710),(1480,290)],dashed=True)
f.text(1130,680,'Xem xét lại khi được phép',25)
f.save()

mermaids = {
'01_kien_truc': '''flowchart TB
 W[Web quản trị / tài xế] --> D[Django: Web · Nghiệp vụ · API]
 P[Raspberry Pi] --> D
 D --> DB[(PostgreSQL)]
 D --> C[Cloudinary]
 D --> F[Face API]
''',
'02_chuc_nang': '''flowchart TB
 A[Quản trị viên] --- A1[Duyệt hồ sơ]
 A --- A2[Quản lý xe & phân công]
 A --- A3[Thiết bị, phiên & vi phạm]
 U[Tài xế] --- U1[Tài khoản & hồ sơ]
 U --- U2[GPLX & khuôn mặt]
 U --- U3[Tra cứu xe, phiên, vi phạm]
 P[Raspberry Pi] --- P1[Nhận diện tài xế]
 P --- P2[Mở / kết thúc phiên]
 P --- P3[Gửi vi phạm & ảnh]
''',
'03_du_lieu': '''flowchart TB
 D[Tài xế] ---|0..1 mỗi loại| F[GPLX & khuôn mặt]
 D ---|1:N| A[Phân công]
 V[Phương tiện] ---|1:N| A
 V ---|1:0..1| DE[Thiết bị]
 A ---|1:N| S[Phiên lái]
 S ---|1:N| I[Vi phạm]
 I ---|1:N| E[Bằng chứng]
 I ---|1:N| R[Lịch sử xét duyệt]
''',
'04_ho_so': '''flowchart LR
 U[Tài xế cập nhật hồ sơ] --> S[Kiểm tra & lưu] --> A[Quản trị viên xét duyệt]
 A --> Y[Được duyệt]
 A --> N[Bị từ chối]
 N -. Cập nhật và gửi lại .-> U
''',
'05_nhan_dien': '''flowchart LR
 P[Pi gửi ảnh] --> F[Nhận diện: Face API + so khớp] --> C[Kiểm tra quyền lái]
 C -->|Hợp lệ| S[Mở phiên]
 S -->|Pi yêu cầu| E[Kết thúc phiên]
 F -. Không nhận diện được .-> N[Không mở phiên]
 C -. Không đủ điều kiện .-> N
''',
'06_vi_pham': '''flowchart LR
 P[Pi: sự kiện + ảnh] --> S[Kiểm tra & lưu] --> V[Chờ xác nhận]
 V --> A[Admin xem bằng chứng] --> R[Xác nhận / Từ chối] --> H[Lưu lịch sử duyệt]
 R -. Xem xét lại khi được phép .-> V
'''}
for name, source in mermaids.items():
    (SRC / f'{name}.mmd').write_text(source, encoding='utf-8')

gallery = '''<!doctype html><html lang="vi"><meta charset="utf-8">
<title>Sơ đồ SaveLife</title><style>body{font:18px Arial;max-width:1100px;margin:40px auto;padding:0 20px;color:#18334d}img{width:100%;border:1px solid #ddd}figure{margin:40px 0}figcaption{margin:12px 0}a{color:#25638a}</style>
<h1>Sơ đồ tổng quan SaveLife</h1><p>Bản cập nhật 06/11/2026 · PNG để chèn Word, SVG để phóng to.</p>'''
for name in mermaids:
    gallery += f'<figure><img src="images/{name}.png" alt="{name}"><figcaption>{name} · <a href="images/{name}.png">PNG</a> · <a href="images/{name}.svg">SVG</a> · <a href="sources/{name}.mmd">Mermaid</a></figcaption></figure>'
(ROOT / 'xem_so_do.html').write_text(gallery + '</html>', encoding='utf-8')

previews = []
for name in mermaids:
    with Image.open(IMG / f'{name}.png') as im:
        thumb = im.copy()
        thumb.thumbnail((800,490))
        tile = Image.new('RGB',(820,510),'#e5e9ee')
        tile.paste(thumb,((820-thumb.width)//2,(510-thumb.height)//2))
        previews.append(tile)
sheet = Image.new('RGB',(1640,1530),'white')
for i, tile in enumerate(previews):
    sheet.paste(tile,((i%2)*820,(i//2)*510))
sheet.save(ROOT / 'kiem_tra_so_do.png')
with ZipFile(ROOT / 'So_do_SaveLife.zip', 'w', ZIP_DEFLATED) as archive:
    for name in mermaids:
        for folder, ext in [(IMG,'png'),(IMG,'svg'),(SRC,'mmd')]:
            path = folder / f'{name}.{ext}'
            archive.write(path,path.relative_to(ROOT))
    archive.write(ROOT / 'xem_so_do.html','xem_so_do.html')
print('Generated 6 PNG/SVG diagrams, Mermaid sources, gallery and figure ZIP.')


