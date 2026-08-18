# -*- coding: utf-8 -*-
"""三上混合运算特训 · 版式层（一天一页四节；圈码题号；玉米水印）· 30 天全册"""
import base64
import os

from qbank import DAYS, build_all, ev, render, steps, tree_of_s4, verify

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WM_PNG = r'D:\workplace\ai-bkb\举一反三产物\_模板\玉米水印.png'
CN = '一二三四五六七八九十'
CIRC = '①②③④⑤⑥⑦⑧⑨⑩'

wm64 = base64.b64encode(open(WM_PNG, 'rb').read()).decode()

CSS = '''<meta charset="utf-8"><style>
@page{size:A4;margin:0}
body{margin:0;font-family:SimSun,serif;font-size:12pt;color:#000}
.card{width:186mm;height:266mm;margin:0 auto;padding:8mm 6mm 6mm;position:relative;
      display:flex;flex-direction:column;page-break-after:always}
.card:last-child{page-break-after:auto}
h1{font-family:SimHei;font-size:17pt;text-align:center;margin:0 0 3mm}
.info{text-align:center;font-size:10.5pt;margin-bottom:2mm}
.info span{display:inline-block;width:26mm;border-bottom:.35mm solid #000;margin:0 1mm}
.sec{font-family:SimHei;font-size:12pt;margin:2.5mm 0 1.5mm}
.row{display:flex}
.q{flex:1;padding:0 1mm}
.blank{flex:1}
.sp{height:42mm}
.m{font-family:"Times New Roman",SimSun,serif}
.pair{display:flex;align-items:center;margin-bottom:1mm}
.brace{font-size:26pt;font-family:SimSun;margin-right:1.5mm;font-weight:200}
.two{line-height:1.7}
.ansline{margin:1.5mm 0 2.5mm;font-size:11pt}
.ansline i{display:inline-block;width:52mm;border-bottom:.35mm solid #000;font-style:normal}
.stp{line-height:1.9;font-size:11.5pt}
.wm{position:absolute;right:6mm;bottom:4mm;font-family:SimHei;font-size:13pt;color:#525252}
.wm img{height:15pt;vertical-align:-3pt;margin-right:1mm}
svg text{font-family:"Times New Roman",SimSun,serif;font-size:13px}
</style>'''


def m(t_or_s):
    """树/文本 → 卷面数学串（全角运算符风格）"""
    s = t_or_s if isinstance(t_or_s, str) else render(t_or_s)
    return ('<span class="m">' +
            s.replace('-', '−').replace('+', '＋').replace('=', '＝') + '</span>')


def tree_svg(spec, answered=False):
    """树状图 SVG。spec=(顶树,op,other,side)；answered=答案版填空"""
    top, op, other, side = spec
    tv, total = ev(top), ev(tree_of_s4(spec))
    a, b = top[1], top[2]
    topop = top[0]
    fill = lambda v: str(v) if answered else ''
    # side='l'：顶行居左上、空框在中层左；side='r' 镜像
    if side == 'l':
        ax, bx, mx, ox = 30, 102, 66, 150
    else:
        ax, bx, mx, ox = 116, 188, 152, 68
    bx_c, ax_c = bx + 22, ax + 22
    mid_cx, o_cx = mx + 22, ox + 22
    bot_x = (mx + ox) // 2
    box = lambda x, y, v: (f'<rect x="{x}" y="{y}" width="44" height="24" fill="none" stroke="#000" stroke-width="1.2"/>'
                           f'<text x="{x+22}" y="{y+17}" text-anchor="middle">{v}</text>')
    opt = lambda x, y, o: f'<text x="{x}" y="{y}" text-anchor="middle" font-size="14">{o.replace("-","−").replace("+","＋")}</text>'
    line = lambda x1, y1, x2, y2: f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#000" stroke-width="1"/>'
    s = f'<svg viewBox="0 0 264 150" width="82mm" height="47mm">'
    s += box(ax, 6, a) + opt((ax_c + bx_c) // 2, 24, topop) + box(bx, 6, b)
    s += line(ax_c, 30, mid_cx - 8, 54) + line(bx_c, 30, mid_cx + 8, 54)
    s += box(mx, 54, fill(tv)) + opt((mid_cx + o_cx) // 2, 72, op) + box(ox, 54, other)
    lcx, rcx = sorted((mid_cx, o_cx))
    s += line(lcx, 78, bot_x + 14, 104) + line(rcx, 78, bot_x + 30, 104)
    s += box(bot_x, 104, fill(total)) + '</svg>'
    return s


def day_no(n):
    """1-30 → 中文序号（一…十, 十一…二十, 二十一…三十）"""
    if n <= 10:
        return CN[n - 1]
    if n < 20:
        return '十' + CN[n - 11]
    if n == 20:
        return '二十'
    if n < 30:
        return '二十' + CN[n - 21]
    return '三十'


def build_card(kind, dayno, d):
    ans = kind == '答案'
    h = '<div class="card">'
    h += f'<h1>三上混合运算每日特训（第{day_no(dayno)}天）</h1>'
    h += '<div class="info">姓名：<span></span>　日期：<span></span>　用时：<span></span></div>'
    # 一、二 脱式
    for si, (key, title) in enumerate([('s1', '脱式计算（无括号）'), ('s2', '脱式计算（含括号）')]):
        h += f'<div class="sec">{CN[si]}、{title}</div><div class="row">'
        for i, t in enumerate(d[key]):
            h += f'<div class="q">{CIRC[i]} {m(t)}'
            if ans:
                h += '<div class="stp">' + ''.join(f'＝ {m(render_step)}<br/>'.replace('render_step', '')
                                                   for render_step in [])
                h += ''.join(f'＝ {m(s)}<br/>' for s in steps(t)) + '</div>'
            else:
                h += '<div class="sp"></div>'
            h += '</div>'
        h += '</div>'
    # 三 二合一
    h += f'<div class="sec">{CN[2]}、把两个算式合并成一个综合算式</div><div class="row" style="flex-wrap:wrap">'
    for i, (t1, t2, tc) in enumerate(d['s3']):
        h += ('<div style="width:50%;box-sizing:border-box;padding:0 2mm 1mm 0">'
              f'<div class="pair">（{i+1}）<span class="brace">{{</span>'
              f'<span class="two">{m(render(t1))}＝{ev(t1)}<br/>{m(render(t2))}＝{ev(t2)}</span></div>'
              f'<div class="ansline">综合算式：<i>{(m(render(tc)) + "＝" + str(ev(tc))) if ans else ""}</i></div></div>')
    h += '</div>'
    # 四 树状图
    h += f'<div class="sec">{CN[3]}、先填空，再列综合算式</div><div class="row">'
    for i, spec in enumerate(d['s4']):
        tc = tree_of_s4(spec)
        h += (f'<div class="q" style="text-align:center">{tree_svg(spec, ans)}'
              f'<div class="ansline" style="text-align:left">综合算式：'
              f'<i>{(m(render(tc)) + "＝" + str(ev(tc))) if ans else ""}</i></div></div>')
    h += '</div>'
    h += f'<div class="wm"><img src="data:image/png;base64,{wm64}"/>玉米训练营</div>'
    h += '</div>'
    return h


def build_book(kind, book):
    return CSS + '<body>' + ''.join(
        build_card(kind, n, d) for n, d in enumerate(book, 1)) + '</body>'


if __name__ == '__main__':
    book = build_all()
    verify(book)
    for kind in ('题目', '答案'):
        p = os.path.join(OUT, '_源', f'_全册_{kind}.html')
        open(p, 'w', encoding='utf-8').write(build_book(kind, book))
        print('OK', p)
    p1 = os.path.join(OUT, '_源', '_第1天_题目.html')      # 单天样张留档
    open(p1, 'w', encoding='utf-8').write(CSS + '<body>' + build_card('题目', 1, book[0]) + '</body>')
    p2 = os.path.join(OUT, '_源', '_第1天_答案.html')
    open(p2, 'w', encoding='utf-8').write(CSS + '<body>' + build_card('答案', 1, book[0]) + '</body>')
    print(f'OK 单天样张；全册 {DAYS} 天')
