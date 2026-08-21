# -*- coding: utf-8 -*-
"""苏俊宇课时卷生成模板（定版工艺，2026-07-14）
用法：复制本文件为 make_l<N>.py，改 LESSON/DATE/三段题目数据，跑完用 Edge 无头转 PDF：
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --headless --disable-gpu \
    --no-pdf-header-footer --print-to-pdf="<out>.pdf" "file:///<out>.html"
定版纪律：
  1) 卷面无学生姓名（只留日期）；2) 竖式必须用 vs() 表格逐列对齐，禁止字符 rjust；
  3) 三段结构=【思维题】1道 /【奥数专项】(学而思,★分层) /【课内同步】(同步典例考点讲义)；
  4) 题目卷+答案卷成对出（答案卷蓝底红字【答案】【解析】框）。
"""
import os

LESSON = '第N课 · 专题名'
DATE = '2026年M月D日'
OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第N课-专题-日期'
os.makedirs(OUT, exist_ok=True)

CELL = 26  # 竖式每列宽 px

def vs(*rows):
    """竖式表格。row = (op, 'A B C') 或 'HR'（横线）。数字右对齐入列，运算符在最左列。
    部分积左移用 ▢ 占位符补在行尾。"""
    parsed = []
    width = 0
    for r in rows:
        if r == 'HR':
            parsed.append('HR'); continue
        op, s = r
        toks = s.split()
        width = max(width, len(toks))
        parsed.append((op, toks))
    html = [f'<table class="vt" style="--w:{CELL}px">']
    for r in parsed:
        if r == 'HR':
            html.append(f'<tr><td colspan="{width+1}" class="hr"></td></tr>')
        else:
            op, toks = r
            pad = [''] * (width - len(toks))
            cells = [f'<td class="op">{op}</td>'] + [f'<td>{t}</td>' for t in pad + toks]
            html.append('<tr>' + ''.join(cells) + '</tr>')
    html.append('</table>')
    return ''.join(html)

def vpair(a, b):
    return f'<div class="vrow">{a}{b}</div>'

# ============ 三段题目数据：dict(d=难度1-4, stem=题干, fig=vs(...)或'', answer=, analyze=) ============
SIWEI = []   # 思维题 1 道
ZX = []      # 奥数专项（学而思）
TB = []      # 课内同步（同步典例考点讲义）

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 12pt; line-height: 1.8; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 19pt; margin: 4mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 5mm; }
.sec { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 13.5pt; margin: 7mm 0 2.5mm; page-break-after: avoid; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.star { color: #b8860b; font-size: 10pt; margin-right: 1.5mm; }
table.vt { border-collapse: collapse; display: inline-table; margin: 2mm 10mm 2mm 6mm; vertical-align: top; }
table.vt td { width: var(--w); min-width: var(--w); height: 26px; text-align: center; font-family: "SimSun",serif;
              font-size: 13pt; padding: 0; }
table.vt td.op { width: 30px; min-width: 30px; text-align: left; }
table.vt td.hr { border-top: 2px solid #111; height: 2px; }
.vrow { display: block; }
.sp { height: 14mm; } .sps { height: 4mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 2mm 3mm; margin: 1.5mm 0 4mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
.foot { text-align: center; color: #999; font-size: 9pt; margin-top: 6mm; }
"""

def emit(qs, with_answers, h, spacer='sp'):
    i = 0
    for q in qs:
        i += 1
        h.append(f'<div class="q"><span class="no">{i}．</span><span class="star">{"★"*q["d"]}</span>{q["stem"]}</div>')
        if q.get('fig'):
            h.append(q['fig'])
        if with_answers:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}</p><p><span class="lab">【解析】</span>{q["analyze"]}</p></div>')
        else:
            h.append(f'<div class="{spacer}"></div>')

def build(with_answers):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{LESSON}</title><style>{CSS}</style></head><body><div class="doc">']
    h.append(f'<h1>{LESSON}</h1>')
    h.append(f'<div class="sub">{DATE}{"（教师用·含答案解析）" if with_answers else ""}</div>')
    h.append('<div class="sec">&#128214; 【思维题】开场热身</div>')
    emit(SIWEI, with_answers, h)
    h.append('<div class="sec">&#128214; 【奥数专项】</div>')
    emit(ZX, with_answers, h)
    h.append('<div class="sec">&#128214; 【课内同步】</div>')
    emit(TB, with_answers, h, spacer='sps')
    h.append('<div class="foot">— 完 —</div></div></body></html>')
    return '\n'.join(h)

if __name__ == '__main__':
    with open(os.path.join(OUT, '题目卷.html'), 'w', encoding='utf-8') as f: f.write(build(False))
    with open(os.path.join(OUT, '答案卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
    print('HTML done:', OUT)
