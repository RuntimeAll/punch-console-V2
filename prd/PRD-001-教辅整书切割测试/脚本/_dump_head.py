# -*- coding: utf-8 -*-
import sys, os, re, json
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'D:\workplace\ai-bkb-v2\切割测试-20260817')
import importlib.util
spec = importlib.util.spec_from_file_location('cutter', r'D:\workplace\ai-bkb-v2\切割测试-20260817\切割.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
import docx
from lxml import etree

src = os.path.join(ROOT,'原料','空白','四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
C.IMGDIR = os.path.join(ROOT,'_tmp_img'); os.makedirs(C.IMGDIR, exist_ok=True)
d = docx.Document(src); body = d.element.body; part = d.part
rows=[]
for i,ch in enumerate(body.iterchildren()):
    if not isinstance(ch.tag,str): continue
    ln = etree.QName(ch).localname
    if ln=='p':
        spans = C.para_to_spans(ch, part)
        txt = C.spans_to_flat([s for s in spans if s['k']!='fig'])
        nfig = sum(1 for s in spans if s['k']=='fig')
        style = ch.find(C.w('pPr'))
        st = ''
        if style is not None:
            ps = style.find(C.w('pStyle'))
            st = ps.get(C.w('val')) if ps is not None else ''
        rows.append({'i':len(rows),'kind':'p','t':txt,'fig':nfig,'st':st})
    elif ln=='tbl':
        rows.append({'i':len(rows),'kind':'tbl','t':'[表格]','fig':0,'st':''})
with open(os.path.join(ROOT,'_para_dump.json'),'w',encoding='utf-8') as f:
    json.dump(rows,f,ensure_ascii=False,indent=1)
print('paras:',len(rows))
# 打印所有像标题的行
pat = re.compile(r'^\s*(?:【|第[一二三四五六七八九十\d]+单元|考点|典型例题|对应练习|变式|例\s*\d|方法点拨|课后|练习|一、|二、|三、)')
n=0
for r in rows:
    t=r['t'].strip()
    if not t: continue
    if pat.match(t) or (len(t)<28 and r['st']):
        print(f"{r['i']:5d} [{r['st'] or '-':>3}] fig{r['fig']} | {t[:70]}")
        n+=1
print('head-ish lines:', n)
