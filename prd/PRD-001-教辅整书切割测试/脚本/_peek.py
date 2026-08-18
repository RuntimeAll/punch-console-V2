# -*- coding: utf-8 -*-
import sys, os, zipfile, re
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(ROOT,'原料','空白','四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
z = zipfile.ZipFile(src)
media = [n for n in z.namelist() if n.startswith('word/media/')]
from collections import Counter
print('media ext:', Counter(os.path.splitext(n)[1].lower() for n in media))
print('sections:', [n for n in z.namelist() if n.endswith('.xml')][:20])
xml = z.read('word/document.xml').decode('utf-8')
print('len xml', len(xml))
print('sectPr count', xml.count('<w:sectPr'), 'cols', re.findall(r'<w:cols[^>]*/>', xml)[:5])
# styles used
print('pStyle:', Counter(re.findall(r'<w:pStyle w:val="([^"]+)"', xml)).most_common(20))
# outlineLvl
print('outlineLvl:', Counter(re.findall(r'<w:outlineLvl w:val="(\d+)"', xml)).most_common())
