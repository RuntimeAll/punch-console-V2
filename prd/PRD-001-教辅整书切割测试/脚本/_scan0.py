# -*- coding: utf-8 -*-
import sys, os, zipfile, re, glob
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(ROOT,'原料','**','*.*'), recursive=True))
for f in files:
    with open(f,'rb') as fh: magic = fh.read(8)
    ext = os.path.splitext(f)[1].lower()
    kind = 'ZIP(docx/xlsx)' if magic[:2]==b'PK' else ('OLE2(真.doc)' if magic[:4]==b'\xd0\xcf\x11\xe0' else ('PDF' if magic[:4]==b'%PDF' else repr(magic[:4])))
    rel = os.path.relpath(f, ROOT)
    line = f'{kind:16s} {os.path.getsize(f)/1024:9.0f}KB  {rel}'
    if magic[:2]==b'PK':
        try:
            z = zipfile.ZipFile(f)
            media = [n for n in z.namelist() if n.startswith('word/media/')]
            xml = z.read('word/document.xml').decode('utf-8','ignore')
            txt = re.sub(r'<[^>]+>','', xml)
            omml = xml.count('<m:oMath')
            tbl  = xml.count('<w:tbl>')
            kw = {k: txt.count(k) for k in ['平行四边形','三角形','梯形','考点','典例','变式','巩固','例题']}
            line += f'\n{"":16s} media={len(media):4d} omml={omml:5d} tbl={tbl:4d} chars={len(txt):7d} kw={kw}'
        except Exception as e:
            line += f'  ERR {e}'
    print(line)
