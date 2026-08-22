# -*- coding: utf-8 -*-
"""五上综合练习（用字母表示数 + 小数除法 + 平行四边形面积）出件器
===========================================================================
对标用户给的原卷结构，出**平行卷**：数字全换、题型与难度一一对齐。
🔴 题面/答案在本文件内成对定义，出件前**机器实算**：
   · 化简题 = 多组数值代入，原式与答案式恒等（专挡"化简写错"）；
   · 小数除法 = Fraction 精确除，商必须是有限小数；
   · 面积题 = 底×高实算，干扰数据登记在案（不参与计算）。
不入库（五上枝未铺，入库要先过 KG 挂载闸）——本器只出 HTML→Chrome→PDF 双卷。
用法：python 工具箱/dsl/五上综合_出件.py --out-dir 产物/专项/五上计算与平行四边形面积
"""
import argparse
import html
import re
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

CHROME = next((p for p in (
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe') if Path(p).exists()), None)

# ── 一、化简（24 题，4 列 × 6 行）：(题面, 答案) ────────────────────────────
SIMPLIFY = [
    ('5×b', '5b'),        ('c×0.4', '0.4c'),     ('1×k', 'k'),        ('n×1', 'n'),
    ('24×y', '24y'),      ('p×7', '7p'),         ('2.8×m', '2.8m'),   ('b×100', '100b'),
    ('6×x', '6x'),        ('a×h', 'ah'),         ('1×w', 'w'),        ('4×n+9', '4n+9'),
    ('y×1.5', '1.5y'),    ('s×t', 'st'),         ('x×x', 'x²'),       ('25-6×p', '25-6p'),
    ('7b+8b', '15b'),     ('9.4x-4.4x', '5x'),   ('m-0.35m', '0.65m'), ('0+12c', '12c'),
    ('5×y+4×y', '9y'),    ('6a×3+a', '19a'),     ('c+c', '2c'),       ('9²', '81'),
]
# ── 二、小数除法（8 题）：除数是小数，商为有限小数 ─────────────────────────
DIVIDE = ['9.66÷2.3', '7.35÷1.4', '0.18÷2.4', '0.72÷1.6',
          '4.08÷0.8', '0.91÷1.3', '0.15÷0.5', '3.36÷5.6']
# ── 三、平行四边形面积：(底, 高, 干扰值列表, 单位) ─────────────────────────
AREA = [(24, 7, [], 'cm'), (7, 4, [2.8], 'cm'), (7, 14, [5], 'cm'), (7.5, 2.6, [5.4], 'cm')]
# ── 四、求未知量：(面积, 已知量, 求什么, 单位) ─────────────────────────────
UNKNOWN = [(96, 7.5, '底', 'cm'), (126, 15, '高', 'm')]


# ══════════════════ 实算闸 ══════════════════
def to_py(e):
    """算式串 → python 表达式（× 换 *、² 换 **2、隐式乘法补 *）"""
    e = e.replace('×', '*').replace('÷', '/')
    e = re.sub(r'([a-z0-9])²', r'(\1)**2', e)
    e = re.sub(r'(\d(?:\.\d+)?)\s*([a-z])', r'\1*\2', e)          # 3a → 3*a
    e = re.sub(r'([a-z])\s*([a-z])', r'\1*\2', e)                 # st → s*t
    return e


def check_simplify():
    bad = []
    for src, ans in SIMPLIFY:
        vs = sorted(set(re.findall(r'[a-z]', src + ans)))
        for k in (2, 3, 5, 7):                                    # 多组数值代入验恒等
            env = {v: k + i * 0.5 for i, v in enumerate(vs)}
            try:
                lv, rv = eval(to_py(src), {}, env), eval(to_py(ans), {}, env)
            except Exception as ex:
                bad.append('%s 求值失败：%s' % (src, ex))
                break
            if abs(lv - rv) > 1e-9:
                bad.append('%s = %s 不恒等（代入 %s：%s ≠ %s）' % (src, ans, env, lv, rv))
                break
    return bad


def div_ans(e):
    a, b = e.split('÷')
    q = Fraction(a) / Fraction(b)
    d = q.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d != 1:
        raise ValueError('%s 商不是有限小数' % e)
    return ('%.10f' % float(q)).rstrip('0').rstrip('.')


def num(x):
    return '%g' % x


def run_checks():
    bad = check_simplify()
    for e in DIVIDE:
        try:
            div_ans(e)
        except ValueError as ex:
            bad.append(str(ex))
    if len(SIMPLIFY) != 24 or len(DIVIDE) != 8:
        bad.append('题量与原卷不齐（应 24 + 8）')
    for b, h, dis, _ in AREA:
        if set(dis) & {b, h}:
            bad.append('干扰值与底/高撞号：%s×%s 干扰%s' % (b, h, dis))
    for s, k, _, _ in UNKNOWN:
        v = Fraction(str(s)) / Fraction(str(k))
        d = v.denominator
        while d % 2 == 0:
            d //= 2
        while d % 5 == 0:
            d //= 5
        if d != 1:
            bad.append('求未知量 %s÷%s 结果不是有限小数' % (s, k))
    if bad:
        print('🔴 实算闸未过：')
        for x in bad:
            print('  ·', x)
        sys.exit(1)
    print('🟢 实算闸全绿：化简 %d 题恒等、竖式除法 %d 题商为有限小数、面积/反求 %d 题实算'
          % (len(SIMPLIFY), len(DIVIDE), len(AREA) + len(UNKNOWN)))


# ══════════════════ 图形（内联 SVG，无外链） ══════════════════
S = 'stroke="#000" stroke-width="1.7" fill="none"'
D = 'stroke="#000" stroke-width="1.4" fill="none" stroke-dasharray="5,4"'


def _t(x, y, s, sz=15):
    return ('<text x="%s" y="%s" style="font-family:Times New Roman,serif;font-style:italic;'
            'font-size:%spx" text-anchor="middle">%s</text>' % (x, y, sz, s))


def _ra(x, y, dx, dy):
    """直角标记：角点 (x,y)，两边朝 dx / dy"""
    s = 9
    return ('<path d="M %s %s L %s %s L %s %s" stroke="#000" stroke-width="1.2" fill="none"/>'
            % (x + dx * s, y, x + dx * s, y + dy * s, x, y + dy * s))


def fig1(b, h):
    """标准放置：底在下，高在内部"""
    return ('<svg viewBox="0 0 300 165" width="225">'
            '<path d="M 30 130 L 245 130 L 290 45 L 75 45 Z" %s/>'
            '<line x1="75" y1="45" x2="75" y2="130" %s/>%s%s%s</svg>'
            % (S, D, _ra(75, 130, 1, -1), _t(88, 92, num(h)), _t(137, 150, num(b))))


def fig2(b, h, dis):
    """上边为底、内部竖高；斜虚线是「以右斜边为底的高」——右斜边长未给 → 干扰
    四点 A(90,40) B(250,40) C(200,130) D(40,130)；斜虚线 A→BC 的垂足 (212.3,107.9)"""
    return ('<svg viewBox="0 0 300 165" width="225">'
            '<path d="M 90 40 L 250 40 L 200 130 L 40 130 Z" %s/>'
            '<line x1="170" y1="40" x2="170" y2="130" %s/>%s'
            '<line x1="90" y1="40" x2="212.3" y2="107.9" %s/>'
            '<path d="M 207.9 115.8 L 200.1 111.4 L 204.4 103.5" '
            'stroke="#000" stroke-width="1.2" fill="none"/>'
            '%s%s%s</svg>'
            % (S, D, _ra(170, 130, -1, -1), D,
               _t(170, 30, num(b)), _t(184, 116, num(h)), _t(130, 76, num(dis[0]))))


def fig3(side, h, dis):
    """长虚线 = 以右斜边 BC 为底对应的高（D→BC 垂足 190.5,55.7）；
    短虚线 = 以下边 CD 为底的高（B→CD 垂足 182.8,129.4），CD 长未给 → 干扰
    四点 A(30,55) B(175,42) C(265,122) D(120,135)"""
    return ('<svg viewBox="0 0 300 165" width="235">'
            '<path d="M 30 55 L 175 42 L 265 122 L 120 135 Z" %s/>'
            '<line x1="120" y1="135" x2="190.5" y2="55.7" %s/>'
            '<path d="M 197.2 61.7 L 191.2 68.4 L 184.5 62.4" '
            'stroke="#000" stroke-width="1.2" fill="none"/>%s'
            '<line x1="130" y1="46" x2="137.8" y2="133.4" %s/>'
            '<path d="M 128.8 134.2 L 128.0 125.3 L 137.0 124.4" '
            'stroke="#000" stroke-width="1.2" fill="none"/>%s%s</svg>'
            % (S, D, _t(160, 100, num(h)), D,
               _t(120, 68, num(dis[0])), _t(238, 72, num(side))))


def fig4(side, h, dis):
    """竖长形：右侧边为底，水平虚线为高，下边是干扰"""
    return ('<svg viewBox="0 0 300 175" width="195">'
            '<path d="M 95 25 L 155 32 L 185 155 L 122 148 Z" %s/>'
            '<line x1="108" y1="90" x2="170" y2="97" %s/>%s%s%s%s</svg>'
            % (S, D, _ra(108, 90, 1, -1), _t(139, 82, num(h)),
               _t(202, 97, num(side)), _t(142, 172, num(dis[0]))))


def fig5(known):
    """S 已知 + 高已知（水平虚线）→ 求左侧那条底"""
    return ('<svg viewBox="0 0 300 185" width="180">'
            '<path d="M 100 25 L 160 32 L 190 165 L 126 157 Z" %s/>'
            '<line x1="113" y1="92" x2="176" y2="99" %s/>%s%s%s</svg>'
            % (S, D, _ra(113, 92, 1, -1), _t(147, 84, '%s cm' % num(known)),
               _t(88, 100, '?', 17)))


def fig6(known):
    """S 已知 + 底已知（下边）→ 求高"""
    return ('<svg viewBox="0 0 300 165" width="230">'
            '<path d="M 35 130 L 240 130 L 285 45 L 80 45 Z" %s/>'
            '<line x1="105" y1="45" x2="105" y2="130" %s/>%s%s%s</svg>'
            % (S, D, _ra(105, 130, 1, -1), _t(93, 92, '?', 17),
               _t(137, 152, '%s m' % num(known))))


CSS = """
@page { size: A4; margin: 0; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"SimSun",serif; font-size:12pt; color:#000; }
.pg { width:210mm; height:283mm; padding:13mm 16mm; position:relative; page-break-after:always; }
.pg:last-child { page-break-after:auto; }
h1 { font-family:"SimHei",sans-serif; font-size:16pt; text-align:center; letter-spacing:1px; }
.info { text-align:center; font-size:10pt; color:#333; margin:2mm 0 4mm; }
.info span { display:inline-block; width:26mm; border-bottom:.3mm solid #666; margin:0 2mm; }
.sec { font-family:"SimHei",sans-serif; font-size:12.5pt; margin:4mm 0 3mm; }
.grid { display:grid; grid-template-columns:repeat(4,1fr); }
.grid.r6 > div { height:14mm; }
.grid.r2 > div { height:40mm; }
.it { font-family:"Times New Roman",serif; font-style:italic; font-size:13.5pt; }
.ans { font-family:"Times New Roman",serif; font-style:italic; font-size:13.5pt;
       color:#c00; font-weight:bold; margin-left:.15em; }
.figs { display:grid; grid-template-columns:1fr 1fr; row-gap:3mm; }
.fig { text-align:center; }
.fig .no { font-size:12pt; display:block; text-align:left; margin-left:5mm; }
.sol { font-family:"Times New Roman",serif; color:#c00; font-size:12.5pt; margin-top:1mm; }
.uk { display:grid; grid-template-columns:1fr 1fr; }
.uk .cap { font-family:"Times New Roman",serif; font-style:italic; font-size:12.5pt;
           display:block; text-align:left; margin-left:5mm; }
"""


def esc(s):
    return html.escape(s)


def build(withans):
    def A(s):
        return '<span class="ans">%s</span>' % s if withans else ''

    o = ['<!doctype html><meta charset="utf-8"><style>%s</style><body>' % CSS]
    # ---------- 第 1 页：计算 ----------
    o.append('<div class="pg"><h1>五年级上册·计算与平行四边形面积综合练习%s</h1>'
             % ('（答案）' if withans else ''))
    o.append('<div class="info">班级<span></span>姓名<span></span>得分<span></span></div>')
    o.append('<div class="sec">1. 直接写出得数或化简下面各式。</div><div class="grid r6">')
    for src, ans in SIMPLIFY:
        o.append('<div><span class="it">%s=</span>%s</div>' % (esc(src), A(esc(ans))))
    o.append('</div>')
    o.append('<div class="sec" style="margin-top:6mm">2. 用竖式计算下面各题。</div>'
             '<div class="grid r2">')
    for e in DIVIDE:
        o.append('<div><span class="it">%s=</span>%s</div>' % (esc(e), A(div_ans(e))))
    o.append('</div></div>')
    # ---------- 第 2 页：图形 ----------
    o.append('<div class="pg"><div class="sec">3. 计算下面平行四边形的面积。（单位：cm）</div>'
             '<div class="figs">')
    figs = [fig1(AREA[0][0], AREA[0][1]),
            fig2(AREA[1][0], AREA[1][1], AREA[1][2]),
            fig3(AREA[2][0], AREA[2][1], AREA[2][2]),
            fig4(AREA[3][0], AREA[3][1], AREA[3][2])]
    for i, (svg, (b, h, dis, _u)) in enumerate(zip(figs, AREA), 1):
        sol = '<div class="sol">%s×%s＝%s（cm²）</div>' % (num(b), num(h), num(b * h)) \
              if withans else ''
        o.append('<div class="fig"><span class="no">（%d）</span>%s%s</div>' % (i, svg, sol))
    o.append('</div>')
    o.append('<div class="sec" style="margin-top:8mm">4. 求下面平行四边形的未知量。</div>'
             '<div class="uk">')
    for i, ((s, k, what, u), fig) in enumerate(zip(UNKNOWN, (fig5, fig6)), 1):
        sol = '<div class="sol">%s÷%s＝%s（%s）</div>' % (num(s), num(k), num(s / k), u) \
              if withans else ''
        o.append('<div class="fig"><span class="cap">（%d）S＝%s %s²</span>%s%s</div>'
                 % (i, num(s), u, fig(k), sol))
    o.append('</div></div></body>')
    return ''.join(o)


def to_pdf(html_text, out_pdf):
    out_pdf = str(Path(out_pdf).resolve())          # 🔴 Chrome 按自己的 CWD 解析相对路径
    tmp = Path(tempfile.mkdtemp(prefix='wu5_'))
    src = tmp / 'p.html'
    src.write_text(html_text, encoding='utf-8')
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-proxy-server',
                    '--user-data-dir=%s' % (tmp / 'prof'), '--virtual-time-budget=15000',
                    '--print-to-pdf=%s' % out_pdf, '--no-pdf-header-footer',
                    src.as_uri()], capture_output=True, timeout=180)
    time.sleep(1.5)                                 # 🔴 落盘晚于进程退出
    if not Path(out_pdf).exists():
        sys.exit('🔴 PDF 没落盘：%s' % out_pdf)
    shutil.rmtree(tmp, ignore_errors=True)
    return Path(out_pdf).stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--name', default='五上计算与平行四边形面积综合练习')
    ap.add_argument('--check-only', action='store_true')
    a = ap.parse_args()
    run_checks()
    if a.check_only:
        return
    if not CHROME:
        sys.exit('🔴 找不到 Chrome/Edge')
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for tag, wa in (('', False), ('（答案）', True)):
        pdf = out / ('%s%s.pdf' % (a.name, tag))
        doc = build(wa)
        (out / ('_源%s.html' % (tag or '（题目）'))).write_text(doc, encoding='utf-8')
        print('🟢 %s　%d KB' % (pdf.name, to_pdf(doc, str(pdf)) // 1024))


if __name__ == '__main__':
    main()
