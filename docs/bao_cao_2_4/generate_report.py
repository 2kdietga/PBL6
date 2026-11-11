"""Build report using the current figure generator."""
from generate_figures import *

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
