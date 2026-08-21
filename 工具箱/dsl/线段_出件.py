# -*- coding: utf-8 -*-
"""线段专项卷出件器（render-pack → 题目卷 / 答案卷双 PDF）
==============================================================================
🔴 渲染从库读：吃 `工具箱/组卷/paper_tool.py render-pack` 导出的包，
   题面/答案/解析一律取 question.blocks_json，本文件**不碰题目内容**（无第二载荷）。

版式（按用户 2026-08-22 令定）：
  · 一节一页；节首印一张**答题技巧**卡（一句话，题目卷/答案卷都印）；
  · 类型①~④ 每页 5 题、类型⑤ 每页 2 题——题量由组卷决定，本器按题数自动分配留白；
  · 题目卷：只有题面 + 作答留白；答案卷：题面 + 答案 + 简解。

用法：
  python render_专项.py <render-pack.json> --out-dir <目录> [--only-ord 1,26]
"""
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

CHROME = next((p for p in (
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe') if Path(p).exists()), None)

CSS = """
@page { size: A4; margin: 0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"SimSun",serif; font-size:11.5pt; line-height:1.6; color:#000; }
/* 🔴 页框做得比 A4(297) 矮一截 → 内容再涨也溢不到下一页，杜绝"夹空白页/串页"
   （2026-08-22 实抓：锁 297mm 会页页微溢出，10 页里 5 页是空的） */
.pg { width:210mm; height:268mm; padding:12mm 15mm; position:relative;
      page-break-after:always; overflow:visible; }
body.ans .pg { height:auto; }
.pg:last-child { page-break-after:auto; }
h1 { font-family:"SimHei",sans-serif; font-size:15pt; text-align:center; margin-bottom:1mm; }
.info { text-align:center; font-size:9.5pt; color:#333; margin-bottom:3mm; }
.info span { display:inline-block; width:24mm; border-bottom:.3mm solid #666; margin:0 1.5mm; }
.tip { border:.4mm solid #000; border-left:2.2mm solid #000; padding:2.2mm 3mm;
       margin-bottom:4mm; font-size:10.5pt; background:#fafafa; }
.tip b { font-family:"SimHei",sans-serif; margin-right:.4em; }
.q { margin-bottom:2mm; }
/* 🔴 留白用 flex 分剩余空间，不用写死 mm——写死会被长题面撑破整页（2026-08-22 机检实抓） */
/* 留白高度由出件器按题面长度算（见 page_html），不交给 CSS 猜 */
.qn { font-family:"SimHei",sans-serif; margin-right:.3em; }
.blank { border-bottom:0; }
.ans { margin:1.5mm 0 0; padding:1.6mm 2.5mm; background:#f2f2f2; font-size:10.5pt; }
.ans .lb { font-family:"SimHei",sans-serif; }
.sol { margin-top:1mm; font-size:10pt; color:#222; }
.sol div { margin:.3mm 0; }
.wm { position:absolute; right:12mm; bottom:7mm; font-size:8.5pt; color:#999; }
.pn { position:absolute; left:0; right:0; bottom:7mm; text-align:center;
      font-size:9pt; color:#666; }
"""

MJ = """<script>window.MathJax={tex:{inlineMath:[['$','$'],['\\\\(','\\\\)']]},
svg:{fontCache:'global'}};</script>
<script id="MathJax-script" src="__MJ__"></script>"""


def md2html(md):
    """题面 md（内联 $…$）→ HTML。

    🔴 **整串转义，公式段也不例外**：题面里有 `$AC<CB$` 这种不等号，
    只转义公式外会被浏览器当成 HTML 标签，把后面整段吞掉、DOM 结构破坏
    （2026-08-22 实抓：双中点第 1 题只剩半句，且整册串页）。
    MathJax 读的是 DOM textContent，实体会被解码回原字符，所以转义不影响公式。
    """
    s = html.escape(md, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    return s.replace(chr(10), '<br>')


def first_md(blocks, role=None):
    if not blocks:
        return ''
    for row in blocks.get('rows', []):
        for cell in row.get('cells', []):
            if cell.get('type') == 'text' and (role is None or cell.get('role') == role):
                return cell.get('md', '')
    return ''


AVAIL_MM = 214.0          # 页框 268 − 上下 padding 24 − 页眉/信息栏/技巧卡 ≈ 30
CHARS_PER_LINE = 46       # 11.5pt SimSun 在 180mm 版心的容字量（实测）
LINE_MM = 6.4


def est_mm(md):
    """题面估高：按可见字数折行（公式按 1.6 倍字宽计）。"""
    vis = len(re.sub(r'\s+', '', md))
    return max(1, -(-vis // CHARS_PER_LINE)) * LINE_MM + 2.0


def page_html(sec, qs, title, with_ans, pno):
    if not with_ans:
        used = sum(est_mm(first_md(q['blocks'])) for q in qs)
        gap = max(8.0, (AVAIL_MM - used) / max(len(qs), 1))
    else:
        gap = 0.0
    parts = [f'<div class="pg"><h1>{html.escape(title)}</h1>',
             '<div class="info">姓名<span></span>日期<span></span>用时<span></span></div>',
             f'<div class="tip"><b>答题技巧</b>{md2html(sec["tip"])}</div>']
    for i, q in enumerate(qs, 1):
        parts.append(f'<div class="q"><span class="qn">{i}．</span>'
                     f'{md2html(first_md(q["blocks"]))}</div>')
        if with_ans:
            a = first_md(q.get('answer_blocks'))
            s = first_md(q.get('analysis_blocks'))
            if a:
                parts.append(f'<div class="ans"><span class="lb">答案：</span>{md2html(a)}</div>')
            if s:
                lines = ''.join(f'<div>{md2html(x)}</div>' for x in s.split('\n') if x.strip())
                parts.append(f'<div class="sol">{lines}</div>')
        else:
            parts.append(f'<div style="height:{gap:.1f}mm"></div>')
    parts.append(f'<div class="wm">玉米训练营</div><div class="pn">第 {pno} 页</div></div>')
    return ''.join(parts)


def build(papers, with_ans, mj_src):
    """papers = render-pack 的卷列表（item 里内嵌 question）。一节一页。"""
    body, pno = [], 0
    for p in papers:
        by_sec = {}
        for it in p['items']:
            by_sec.setdefault(it['section'], []).append(it['question'])
        for sec in p['layout']['sections']:
            qs = by_sec.get(sec['name'], [])
            if not qs:
                continue
            pno += 1
            title = p['title'] if len(p['layout']['sections']) == 1 else                 f"{p['title']}　{sec['name']}"
            body.append(page_html(sec, qs, title, with_ans, pno))
    head = f'<meta charset="utf-8"><style>{CSS}</style>' + MJ.replace('__MJ__', mj_src)
    cls = ' class="ans"' if with_ans else ''
    return (f'<!doctype html><html><head>{head}</head>'
            f'<body{cls}>{"".join(body)}</body></html>')


def to_pdf(html_text, out_pdf):
    # 🔴 Chrome 的 --print-to-pdf 按**它自己的 CWD**解析相对路径 → 必须给绝对路径
    out_pdf = str(Path(out_pdf).resolve())
    tmp = Path(tempfile.mkdtemp(prefix='seg_'))
    src = tmp / 'p.html'
    src.write_text(html_text, encoding='utf-8')
    prof = tmp / 'prof'
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-proxy-server',
                    f'--user-data-dir={prof}', '--virtual-time-budget=20000',
                    f'--print-to-pdf={out_pdf}', '--no-pdf-header-footer',
                    src.as_uri()], capture_output=True, timeout=180)
    time.sleep(1.2)                                  # 🔴 Chrome 三坑之一：落盘晚于退出
    if not Path(out_pdf).exists():
        sys.exit(f'🔴 PDF 没落盘：{out_pdf}（Chrome 无头三坑：临时 profile/sleep/目检）')
    shutil.rmtree(tmp, ignore_errors=True)
    return Path(out_pdf).stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pack')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--group', action='append', default=None,
                    help='一册一组：「起ord-止ord:册名」，可多次；缺省=每卷各出一册')
    ap.add_argument('--mathjax', default=None)
    a = ap.parse_args()
    if not CHROME:
        sys.exit('🔴 找不到 Chrome/Edge')
    pack = json.loads(Path(a.pack).read_text(encoding='utf-8'))
    # 🔴 本地件（与 punchkit 同一份），不依赖网络
    mj = a.mathjax or ('file:///' + str((Path(__file__).resolve().parents[2] /
         '工具箱' / '渲染' / 'mathjax' / 'es5' / 'tex-mml-chtml.js').as_posix()))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    by_ord = {p['ord']: p for p in pack['papers']}

    groups = []
    if a.group:
        for g in a.group:
            rng, name = g.split(':', 1)
            lo, hi = (int(x) for x in rng.split('-'))
            groups.append(([by_ord[o] for o in range(lo, hi + 1) if o in by_ord], name))
    else:
        groups = [([p], p['title']) for p in pack['papers']]

    made = []
    for papers, stem in groups:
        for tag, wa in (('', False), ('（答案）', True)):
            pdf = out / f'{stem}{tag}.pdf'
            sz = to_pdf(build(papers, wa, mj), str(pdf))
            made.append((pdf.name, sz))
            print(f'🟢 {pdf.name}　{sz // 1024} KB')
    print(f'共出件 {len(made)} 个 PDF → {out}')


if __name__ == '__main__':
    main()
