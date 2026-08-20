# -*- coding: utf-8 -*-
"""印刷级图题重画器（确定性 / 零 LLM / spec 驱动）

用途：把试卷里"拍照裁图"的糊图，按 spec 用 PIL 重画成干净的白底黑线印刷级 PNG。
用法：python 工具箱/渲染/draw_figures.py          # 全量重生成 + 写清单
     python 工具箱/渲染/draw_figures.py --only 卷3-3   # 只重画一张（调 spec 用）

改图 = 改本文件尾部 SPECS 里那一条 spec 再重跑，不留手工痕迹。

坐标系：每条 spec 的几何量都写在"原裁图像素坐标系"里（照原图实测），
       view=(x0,y0,x1,y1) 圈定取景框，pad 四周留白，渲染时统一平移+缩放。
渲染：先按 SS=4 倍超采样画，再 LANCZOS 缩到 OUT_W 宽 —— 线宽落地恰好 LW=3px。
字体：变量字母 Times 斜体 / 数字与符号 Times 正体 / 中文 宋体；负号一律 U+2212。
"""
import sys

sys.stdout.reconfigure(encoding='utf-8')

import argparse
import hashlib
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- 常量

V2_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT_DIR = os.path.join(V2_ROOT, '试验场', '2026-08-20-图题重画')
MANIFEST = os.path.join(OUT_DIR, '重画清单.json')

FONT_FILES = {
    'ti': r'C:\Windows\Fonts\timesi.ttf',   # 变量字母：Times 斜体
    'tr': r'C:\Windows\Fonts\times.ttf',    # 数字/符号：Times 正体
    'cn': r'C:\Windows\Fonts\simsun.ttc',   # 中文：宋体
}

OUT_W = 1500   # 成品宽（≥1400）
SS = 4         # 超采样倍数
LW = 3.0       # 落地线宽（px）
MINUS = '\u2212'

INK = 0        # 黑
GRAY_FILL = 198
GRAY_EDGE = 118

_font_cache = {}


def fnt(key, size_px):
    size_px = max(1, int(round(size_px)))
    ck = (key, size_px)
    if ck not in _font_cache:
        _font_cache[ck] = ImageFont.truetype(FONT_FILES[key], size_px)
    return _font_cache[ck]


def runs_of(text):
    """按字符路由字体：中文→宋体，ASCII 字母→Times 斜体，其余→Times 正体；'-'→U+2212。"""
    out = []
    for ch in text:
        if ch == '-':
            ch = MINUS
        if '\u4e00' <= ch <= '\u9fff' or ch in '，。、（）':
            key = 'cn'
        elif ('a' <= ch <= 'z') or ('A' <= ch <= 'Z'):
            key = 'ti'
        else:
            key = 'tr'
        if out and out[-1][1] == key:
            out[-1][0] += ch
        else:
            out.append([ch, key])
    return [(t, k) for t, k in out]


# ---------------------------------------------------------------- 画布

class Canvas:
    """逻辑坐标（原裁图像素） → 超采样画布像素。"""

    def __init__(self, view, pad):
        x0, y0, x1, y1 = view
        self.ox, self.oy = x0 - pad, y0 - pad
        self.lw_logical = (x1 - x0) + 2 * pad
        self.lh_logical = (y1 - y0) + 2 * pad
        self.k = SS * OUT_W / float(self.lw_logical)
        w = int(round(self.lw_logical * self.k))
        h = int(round(self.lh_logical * self.k))
        self.im = Image.new('L', (w, h), 255)
        self.d = ImageDraw.Draw(self.im)

    # -- 单位换算
    def P(self, x, y):
        return ((x - self.ox) * self.k, (y - self.oy) * self.k)

    def w(self, final_px):
        """落地像素 → 画布像素（线宽用）。"""
        return max(1, int(round(final_px * SS)))

    def s(self, logical):
        return logical * self.k

    # -- 图元
    def line(self, x0, y0, x1, y1, width=LW, fill=INK):
        self.d.line([self.P(x0, y0), self.P(x1, y1)], fill=fill, width=self.w(width))

    def polyline(self, pts, width=LW, fill=INK):
        self.d.line([self.P(*p) for p in pts], fill=fill, width=self.w(width), joint='curve')

    def dot(self, x, y, r):
        cx, cy = self.P(x, y)
        rr = self.s(r)
        self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=INK)

    def ellipse(self, cx, cy, rx, ry, fill=GRAY_FILL, outline=GRAY_EDGE, width=LW):
        a, b = self.P(cx - rx, cy - ry)
        c, e = self.P(cx + rx, cy + ry)
        self.d.ellipse([a, b, c, e], fill=fill, outline=outline, width=self.w(width))

    def rrect(self, x0, y0, x1, y1, radius, width=LW):
        a, b = self.P(x0, y0)
        c, e = self.P(x1, y1)
        self.d.rounded_rectangle([a, b, c, e], radius=self.s(radius),
                                 outline=INK, width=self.w(width))

    def arrow(self, x0, y0, x1, y1, length, half, width=LW):
        """从 (x0,y0) 指到 (x1,y1)，箭尖落在 (x1,y1)，实心三角头。"""
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        bx, by = x1 - ux * length, y1 - uy * length          # 三角底边中点
        sx, sy = x1 - ux * length * 0.62, y1 - uy * length * 0.62  # 杆止于头内
        self.line(x0, y0, sx, sy, width=width)
        px, py = -uy, ux
        self.d.polygon([self.P(x1, y1),
                        self.P(bx + px * half, by + py * half),
                        self.P(bx - px * half, by - py * half)], fill=INK)

    def dashed(self, pts, dash, gap, width=LW):
        """沿折线走虚线（dash/gap 为逻辑长度）。"""
        pen = 0.0
        on = True
        for i in range(len(pts) - 1):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            seg = math.hypot(bx - ax, by - ay)
            t = 0.0
            while t < seg:
                need = (dash if on else gap) - pen
                step = min(need, seg - t)
                if on and step > 0:
                    f0, f1 = t / seg, (t + step) / seg
                    self.line(ax + (bx - ax) * f0, ay + (by - ay) * f0,
                              ax + (bx - ax) * f1, ay + (by - ay) * f1, width=width)
                t += step
                pen += step
                if pen >= (dash if on else gap) - 1e-9:
                    pen = 0.0
                    on = not on

    # -- 文字（多字体混排，共基线）
    def text(self, cx, baseline, s, size, align='center'):
        runs = runs_of(s)
        total = sum(fnt(k, self.s(size)).getlength(t) for t, k in runs)
        if align == 'center':
            x = self.P(cx, baseline)[0] - total / 2.0
        elif align == 'right':
            x = self.P(cx, baseline)[0] - total
        else:
            x = self.P(cx, baseline)[0]
        y = self.P(cx, baseline)[1]
        for t, k in runs:
            f = fnt(k, self.s(size))
            self.d.text((x, y), t, font=f, fill=INK, anchor='ls')
            x += f.getlength(t)

    def cap(self, size, key='tr', ref='0'):
        """参考字高（逻辑单位）：用于把不同标签压到同一基线。"""
        f = fnt(key, self.s(size))
        return -f.getbbox(ref, anchor='ls')[1] / self.k

    def finish(self):
        return self.im.resize((OUT_W, max(1, int(round(self.im.size[1] / SS)))),
                              Image.LANCZOS)


# ---------------------------------------------------------------- 渲染器

def _axis(c, sp):
    """主数轴：水平线 + 右实心箭头。"""
    ax = sp['axis']
    font = sp.get('font', 24)
    alen = sp.get('arrow_len', 0.80 * font)
    ahalf = sp.get('arrow_half', 0.26 * font)
    c.arrow(ax['x0'], ax['y'], ax['x1'], ax['y'], alen, ahalf)


def render_numline(c, sp):
    ax = sp['axis']
    y = ax['y']
    font = sp['font']
    _axis(c, sp)

    # 墨迹（画在轴之上遮住轴）
    for ink in sp.get('inks', []):
        c.ellipse(ink['cx'], y, ink['rx'], ink['ry'])

    # 刻度
    up = sp.get('tick_up', 10)
    dn = sp.get('tick_dn', 0)
    for x in sp.get('ticks', []):
        c.line(x, y - up, x, y + dn)

    # 实心点
    r = sp.get('dot_r', 0.22 * font)
    for x in sp.get('dots', []):
        c.dot(x, y, r)

    # 标签
    gb = sp.get('gap_below', 0.28 * font)
    ga = sp.get('gap_above', 0.45 * font)
    cap = c.cap(font)
    for lab in sp.get('labels', []):
        x, s, side = lab[0], lab[1], lab[2]
        if side == 'below':
            c.text(x, y + gb + cap, s, font)
        else:
            c.text(x, y - ga, s, font)

    # 上方虚线弧 + 标注
    for arc in sp.get('arcs', []):
        x0, x1 = arc['x0'], arc['x1']
        ye, h = arc['y_end'], arc['h']
        pts = []
        n = 200
        for i in range(n + 1):
            t = i / float(n)
            pts.append((x0 + (x1 - x0) * t, ye - 4.0 * h * t * (1 - t)))
        c.dashed(pts, arc.get('dash', 6), arc.get('gap', 4), width=arc.get('lw', LW * 0.85))
        if arc.get('label'):
            apex_y = ye - h
            c.text(arc.get('label_x', (x0 + x1) / 2.0),
                   apex_y - arc.get('label_gap', 0.12 * font),
                   arc['label'], font)


def render_grid(c, sp):
    """n×n 虚线方格网 + 格点实心点 + 字母标签。"""
    x0, y0, cell, n = sp['x0'], sp['y0'], sp['cell'], sp['n']
    nd = sp.get('dashes_per_cell', 3)
    ratio = sp.get('dash_gap_ratio', 0.55)
    dash = cell / (nd + (nd + 1) * ratio)
    gap = dash * ratio
    lw = sp.get('grid_lw', LW * 0.85)
    for i in range(n + 1):
        gy = y0 + i * cell
        gx = x0 + i * cell
        for j in range(n):                       # 逐格走虚线：格点处留缺口
            a = x0 + j * cell
            c.dashed([(a, gy), (a + cell, gy)], dash, gap, width=lw)
            c.dashed([(gx, y0 + j * cell), (gx, y0 + (j + 1) * cell)], dash, gap, width=lw)
    font = sp['font']
    r = sp.get('dot_r', 0.20 * font)
    ox, oy = sp.get('label_off', (0.41 * cell, -0.41 * cell))
    cap = c.cap(font, 'ti', 'A')
    for p in sp['points']:
        px = x0 + p['col'] * cell
        py = y0 + p['row'] * cell
        c.dot(px, py, r)
        c.text(px + ox, py + oy + cap / 2.0, p['name'], font)


def render_flow(c, sp):
    """横向流程图：圆角方框 + 右箭头 + 框内中文。"""
    font = sp['font']
    y0, y1 = sp['y0'], sp['y1']
    cy = (y0 + y1) / 2.0
    cap = c.cap(font, 'cn', '国')
    boxes = sp['boxes']
    for b in boxes:
        c.rrect(b['x0'], y0, b['x1'], y1, sp.get('radius', 0.30 * font))
        c.text((b['x0'] + b['x1']) / 2.0, cy + cap / 2.0, b['text'], font)
    alen = sp.get('arrow_len', 0.85 * font)
    ahalf = sp.get('arrow_half', 0.30 * font)
    inset = sp.get('arrow_inset', 0.55 * font)
    for i in range(len(boxes) - 1):
        a = boxes[i]['x1'] + inset
        b = boxes[i + 1]['x0'] - inset
        c.arrow(a, cy, b, cy, alen, ahalf)


RENDERERS = {'numline': render_numline, 'grid': render_grid, 'flow': render_flow}


def render(sp):
    c = Canvas(sp['view'], sp.get('pad', 12))
    RENDERERS[sp['type']](c, sp)
    return c.finish()


# ---------------------------------------------------------------- 工具

def evenly(start, step, n):
    return [start + i * step for i in range(n)]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None, help='只画某张，如 卷3-3 / 卷2-5-C')
    args = ap.parse_args()

    rows = []
    for sp in SPECS:
        key = sp['key']
        if args.only and args.only != key:
            continue
        out = os.path.join(OUT_DIR, sp['vol'], sp['name'] + '.png')
        os.makedirs(os.path.dirname(out), exist_ok=True)
        img = render(sp)
        img.save(out, 'PNG', optimize=True)
        rel = os.path.relpath(out, V2_ROOT).replace('\\', '/')
        rows.append({
            'qid': sp['qid'], 'vol': sp['vol'], 'qno': sp['qno'], 'slot': sp.get('slot'),
            'old_hash': sp['old_hash'], 'file': rel, 'sha256': sha256_of(out),
            'width': sp['width'], 'px': list(img.size), 'kind': sp['kind'],
        })
        print(f"[ok] {rel}  {img.size[0]}x{img.size[1]}")

    if not args.only:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(MANIFEST, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"[manifest] {MANIFEST}  n={len(rows)}")


# ================================================================ SPECS
# 每条 = 一张图。几何量照原裁图实测（刻度数、标签、点位、箭头方向），
# 改图只改这里再整体重跑。

SPECS = [

    # ---- 卷1 ----
    dict(key='卷1-14', qid='q20260820ae991a3a', vol='卷1', qno=14, slot=None,
         old_hash='b45842db0a1305dc0916d324f068c644139ec6796ece66fe2df3a9c2f28651c1',
         width='56%', kind='数轴：12 刻度无数字，A 在第4刻度、B 在第8刻度（相距 4 格）',
         name='题14', type='numline',
         view=(14, 18, 660, 58), pad=14, font=30,
         axis=dict(x0=14, y=28, x1=660), tick_up=10,
         ticks=evenly(42.5, 52.27, 12),
         labels=[(42.5 + 3 * 52.27, 'A', 'below'), (42.5 + 7 * 52.27, 'B', 'below')],
         gap_below=9),

    dict(key='卷1-16', qid='q20260820fd06499c', vol='卷1', qno=16, slot=None,
         old_hash='940317f7c484d0e262962b626bbda5733b2c13f6258eb117f942409f071b0620',
         width='70%', kind='流程图五框：输入 x → 平方 → 乘以 3 → 减去 10 → 输出',
         name='题16', type='flow',
         view=(14, 14, 965, 73), pad=18, font=27,
         y0=14.5, y1=72.5,
         boxes=[dict(x0=14.5, x1=123.5, text='输入 x'),
                dict(x0=212.5, x1=321.5, text='平方'),
                dict(x0=428.5, x1=537.5, text='乘以 3'),
                dict(x0=637.5, x1=768.5, text='减去 10'),
                dict(x0=855.5, x1=964.5, text='输出')]),

    dict(key='卷1-19', qid='q20260820e57a8117', vol='卷1', qno=19, slot=None,
         old_hash='31c4eac89b1f084058fbf3346f1b37e374b0279d5de4c908f0efd704d42415b1',
         width='69%', kind='数轴：10 刻度标 −5~4，空白待填',
         name='题19', type='numline',
         view=(14, 14, 818, 61), pad=16, font=34,
         axis=dict(x0=14, y=26, x1=818), tick_up=12,
         ticks=evenly(94, 69.67, 10),
         labels=[(94 + i * 69.67, s, 'below') for i, s in
                 enumerate(['-5', '-4', '-3', '-2', '-1', '0', '1', '2', '3', '4'])],
         gap_below=9),

    dict(key='卷1-23', qid='q20260820b130eef5', vol='卷1', qno=23, slot=None,
         old_hash='579a50463e0246189a816554df305c2e582a8147797370e14b054218f456bddf',
         width='40%', kind='数轴 −4~4：A 在 −3、B 在 −1、C 在 4（实心点+上方字母）',
         name='题23', type='numline',
         view=(15, 14, 408, 70), pad=13, font=21,
         axis=dict(x0=15, y=46, x1=408), tick_up=9,
         ticks=[206.75 + v * 43.56 for v in range(-4, 5)],
         dots=[206.75 - 3 * 43.56, 206.75 - 1 * 43.56, 206.75 + 4 * 43.56],
         dot_r=5,
         labels=[(206.75 + v * 43.56, str(v).replace('-', '-'), 'below') for v in range(-4, 5)]
                + [(206.75 - 3 * 43.56, 'A', 'above'),
                   (206.75 - 1 * 43.56, 'B', 'above'),
                   (206.75 + 4 * 43.56, 'C', 'above')],
         gap_below=9, gap_above=11),

    dict(key='卷1-5', qid='q20260820a4d27efd', vol='卷1', qno=5, slot=None,
         old_hash='a3e718371c0ed51c0fa8296c506b7a7a52d0cd5c559303c9faf5bf9f9175e4ea',
         width='46%', kind='数轴：11 刻度无数字，A 在第4刻度、B 在第8刻度（相距 4 格）',
         name='题5', type='numline',
         view=(14, 13, 546, 52), pad=13, font=28,
         axis=dict(x0=14, y=23, x1=546), tick_up=10,
         ticks=evenly(18.5, 47.2, 11),
         labels=[(18.5 + 3 * 47.2, 'A', 'below'), (18.5 + 7 * 47.2, 'B', 'below')],
         gap_below=8),

    # ---- 卷2 ----
    dict(key='卷2-15', qid='q202608209e54dfef', vol='卷2', qno=15, slot=None,
         old_hash='def0cdb2a5e3ea75456729d2a9701ff93b91ab789aba373780739ae11606885c',
         width='40%', kind='数轴：A、原点0、B 三实心点等距（A/B 关于原点对称）',
         name='题15', type='numline',
         view=(14, 14, 283, 74), pad=13, font=26,
         axis=dict(x0=14, y=44, x1=283),
         dots=[59.5, 143.5, 228.5], dot_r=6,
         labels=[(59.5, 'A', 'above'), (228.5, 'B', 'above'), (143.5, '0', 'below')],
         gap_below=12, gap_above=12),

    dict(key='卷2-18', qid='q20260820b5f1d825', vol='卷2', qno=18, slot=None,
         old_hash='6393b9c63b0f3abf998ef4b517945de4e44f5e48d8b718f51c4a910628724066',
         width='40%', kind='数轴 + 灰色椭圆墨迹遮盖，两端刻度外标 −109.2 / 10.5',
         name='题18', type='numline',
         view=(15, 11, 378, 57), pad=13, font=22,
         axis=dict(x0=23, y=30, x1=378),
         inks=[dict(cx=192.5, rx=107, ry=17.5)],
         ticks=[85.5, 299.5], tick_up=6, tick_dn=10,
         labels=[(46, '-109.2', 'below'), (326, '10.5', 'below')],
         gap_below=9),

    dict(key='卷2-21', qid='q20260820b43ec4df', vol='卷2', qno=21, slot=None,
         old_hash='9ac6da2d34783fc6da9409e9e64469a24e1c9293ebd6ce719442fac0d03f83e8',
         width='54%', kind='不完整数轴：11 刻度，仅正中第6刻度标 0',
         name='题21', type='numline',
         view=(14, 14, 635, 61), pad=14, font=27,
         axis=dict(x0=14, y=26, x1=635), tick_up=12,
         ticks=evenly(50, 54.4, 11),
         labels=[(50 + 5 * 54.4, '0', 'below')],
         gap_below=10),

    dict(key='卷2-22', qid='q20260820de47d958', vol='卷2', qno=22, slot=None,
         old_hash='e97dc53eb7ff87746f99d7e148741db8a9da4a5fa276d48f342863a2b18b4845',
         width='57%', kind='数轴：11 刻度标 −5~5，空白作答',
         name='题22', type='numline',
         view=(14, 14, 672, 50), pad=14, font=27,
         axis=dict(x0=14, y=23, x1=672), tick_up=9,
         ticks=evenly(60, 53.4, 11),
         labels=[(60 + i * 53.4, s, 'below') for i, s in
                 enumerate(['-5', '-4', '-3', '-2', '-1', '0', '1', '2', '3', '4', '5'])],
         gap_below=6),

    dict(key='卷2-24', qid='q2026082047f8538e', vol='卷2', qno=24, slot=None,
         old_hash='58101d18f5a15d1b67c3f89c781b764e0ef861c0eb24a2c2e411d7637fbf7d6d',
         width='40%', kind='5×5 虚线方格网：A 左下角、B(1,2)、C(2,1)、D(3,3) 四格点',
         name='题24', type='grid',
         view=(12.5, 14, 199, 201.5), pad=13, font=26,
         x0=17.5, y0=15, cell=36.2, n=5, dot_r=5,
         points=[dict(name='A', col=0, row=5), dict(name='B', col=1, row=2),
                 dict(name='C', col=2, row=1), dict(name='D', col=3, row=3)]),

    # 卷2 题5 四选项：四张独立小图，统一版式（同画布尺度，摆一起才好比）
    dict(key='卷2-5-A', qid='q20260820f4cec0cd', vol='卷2', qno=5, slot='A',
         old_hash='2583629b9815315ca576a9441d26bb128eb82d75e5f3d191cf0e2e8b43e95ebf',
         width='40%', kind='选项A：只一条刻度标 0（缺方向/单位对照）',
         name='题5-选项A', type='numline',
         view=(12, 12, 196, 53), pad=8, font=26,
         axis=dict(x0=18, y=26, x1=190), tick_up=12,
         ticks=[96], labels=[(96, '0', 'below')], gap_below=8),

    dict(key='卷2-5-B', qid='q20260820f4cec0cd', vol='卷2', qno=5, slot='B',
         old_hash='3dfc7f5eae0d2be6c3221652478449721b5361ae25e665680c97fc36a5bc7867',
         width='40%', kind='选项B：三刻度自左至右标 3 2 1（正方向反了）',
         name='题5-选项B', type='numline',
         view=(12, 12, 196, 53), pad=8, font=26,
         axis=dict(x0=18, y=26, x1=190), tick_up=12,
         ticks=[45, 99, 153],
         labels=[(45, '3', 'below'), (99, '2', 'below'), (153, '1', 'below')],
         gap_below=8),

    dict(key='卷2-5-C', qid='q20260820f4cec0cd', vol='卷2', qno=5, slot='C',
         old_hash='d38e2501e497dd8404933b4a1eb51acb90e7675f64b3c5a9917f27c9a4dc278d',
         width='40%', kind='选项C：三刻度自左至右标 −1 0 1（正确）',
         name='题5-选项C', type='numline',
         view=(12, 12, 196, 53), pad=8, font=26,
         axis=dict(x0=18, y=26, x1=190), tick_up=12,
         ticks=[45, 99, 153],
         labels=[(45, '-1', 'below'), (99, '0', 'below'), (153, '1', 'below')],
         gap_below=8),

    dict(key='卷2-5-D', qid='q20260820f4cec0cd', vol='卷2', qno=5, slot='D',
         old_hash='edf5cfc8f839bef6634defb06612c102724b319d532c09ffa3d81ad58bbade4d',
         width='40%', kind='选项D：三刻度自左至右标 1 0 −1（正方向反了）',
         name='题5-选项D', type='numline',
         view=(12, 12, 196, 53), pad=8, font=26,
         axis=dict(x0=18, y=26, x1=190), tick_up=12,
         ticks=[45, 99, 153],
         labels=[(45, '1', 'below'), (99, '0', 'below'), (153, '-1', 'below')],
         gap_below=8),

    dict(key='卷2-8', qid='q202608209d4d91da', vol='卷2', qno=8, slot=None,
         old_hash='6513685a2d2a070efb758a4759336a5d2f0425c8f93b69b17d023024555a89b7',
         width='40%', kind='数轴：0 与 1 两实心点，A 标在 1 的上方',
         name='题8', type='numline',
         view=(14, 14, 428, 80), pad=14, font=26,
         axis=dict(x0=14, y=50, x1=428),
         dots=[189.5, 258.5], dot_r=6,
         labels=[(189.5, '0', 'below'), (258.5, '1', 'below'), (258.5, 'A', 'above')],
         gap_below=12, gap_above=15),

    # ---- 卷3 ----
    dict(key='卷3-21', qid='q202608201109eb9a', vol='卷3', qno=21, slot=None,
         old_hash='8db1a3ead9b8904932fbb39399be105fe2c3ab2ba20ec04d68c702e2ea8295ac',
         width='40%', kind='数轴：五等距刻度自左至右 b、a、0、c、2（b<a<0<c<2）',
         name='题21', type='numline',
         view=(32, 13, 383, 45), pad=13, font=24,
         axis=dict(x0=32, y=21, x1=383), tick_up=7,
         ticks=evenly(45, 70.6, 5),
         labels=[(45 + i * 70.6, s, 'below') for i, s in
                 enumerate(['b', 'a', '0', 'c', '2'])],
         gap_below=6),

    dict(key='卷3-3', qid='q20260820b2b3ae52', vol='卷3', qno=3, slot=None,
         old_hash='459c9bde21e55dcd49051a5538a68597afac434cea0da7308e63568a1457a0c0',
         width='40%', kind='数轴：a 在原点左远处、b 在原点右近处（a<0<b 且 |a|>|b|）',
         name='题3', type='numline',
         view=(11, 8, 264, 34), pad=10, font=21,
         axis=dict(x0=11, y=15, x1=264), tick_up=6,
         ticks=[73.5, 160, 212.5],
         labels=[(73.5, 'a', 'below'), (160, '0', 'below'), (212.5, 'b', 'below')],
         gap_below=5),

    # ---- 卷4 ----
    dict(key='卷4-10', qid='q20260820c0b25cbe', vol='卷4', qno=10, slot=None,
         old_hash='3ca18f965f31f9325596cef3e46fff2d491afd8d8fd2c4986f9ebaf12f019299',
         width='43%', kind='数轴：a 在原点左远处、b 在原点右近处（a<0<b 且 |a|>|b|）',
         name='题10', type='numline',
         view=(8, 10, 507, 51), pad=14, font=26,
         axis=dict(x0=8, y=24, x1=507), tick_up=13,
         ticks=[125, 323, 394],
         labels=[(125, 'a', 'below'), (323, '0', 'below'), (394, 'b', 'below')],
         gap_below=9),

    # ---- 卷5 ----
    dict(key='卷5-13', qid='q202608208afba2dd', vol='卷5', qno=13, slot=None,
         old_hash='bd2eca89d74a70032026d8eb8605b04048dfac310fd849b30853479395acbfda',
         width='40%', kind='数轴：四标点自左至右 c、b、0、a（c<b<0<a 且 |b|>|a|）',
         name='题13', type='numline',
         view=(16, 8, 275, 36), pad=10, font=19,
         axis=dict(x0=16, y=15, x1=275), tick_up=6,
         ticks=[46, 103, 187, 229],
         labels=[(46, 'c', 'below'), (103, 'b', 'below'),
                 (187, '0', 'below'), (229, 'a', 'below')],
         gap_below=6),

    dict(key='卷5-20', qid='q20260820249a62f9', vol='卷5', qno=20, slot=None,
         old_hash='071f62d6a92466bcbe72e4c38b8f659baef667aad2d7d5d5eb9faa69a60fb5ca',
         width='40%', kind='数轴：A/B/C/D 四等距实心点 + A→D 上方虚线弧标 6',
         name='题20', type='numline',
         view=(12, 8, 296, 82), pad=13, font=22,
         axis=dict(x0=12, y=76, x1=296),
         dots=evenly(23.5, 81.83, 4), dot_r=5,
         labels=[(23.5, 'A', 'above'), (105.33, 'B', 'above'),
                 (187.17, 'C', 'above'), (269, 'D', 'above')],
         gap_above=5,
         arcs=[dict(x0=23.5, x1=269, y_end=74, h=47, dash=6, gap=4,
                    label='6', label_x=153, label_gap=3)]),

    dict(key='卷5-6', qid='q202608201dc1dc6a', vol='卷5', qno=6, slot=None,
         old_hash='b1e4e5b8f9eea8ed953866ea3d517414888136115040068337ccd6a7fb3c2351',
         width='40%', kind='数轴：六刻度自左至右 −1、b、0、1、a、2（−1<b<0<1<a<2）',
         name='题6', type='numline',
         view=(12, 5, 197, 44), pad=10, font=20,
         axis=dict(x0=12, y=17, x1=197), tick_up=10,
         ticks=[26.5, 54, 73, 119, 140.5, 165],
         labels=[(26.5, '-1', 'below'), (54, 'b', 'below'), (73, '0', 'below'),
                 (119, '1', 'below'), (140.5, 'a', 'below'), (165, '2', 'below')],
         gap_below=10),

    # ================================================================
    # 收尾战役·图预制（2026-08-20）：卷7 / 卷8 尚未入库，无 qid、无旧裁图，
    # 故 qid / old_hash 记 None；几何量照原扫描页实测（页尺寸卷7 1080×162x、卷8 1280×1811）。
    # ================================================================

    # ---- 卷7（第1章 有理数 综合检测卷）----
    dict(key='j7_t6', qid=None, vol='卷7', qno=6, slot=None, old_hash=None,
         width='40%', kind='数轴：A/B/C 三实心点，A—B 相距 2 格、B—C 相距 4 格（A 与 C 相距 6 格），字母标在点下方',
         name='j7_t6', type='numline',
         view=(430, 888, 700, 916), pad=12, font=20,
         axis=dict(x0=430, y=894, x1=700), tick_up=4,
         ticks=[481, 554, 591, 628],
         dots=[443.5, 517.5, 664.5], dot_r=3,
         labels=[(443.5, 'A', 'below'), (517.5, 'B', 'below'), (664.5, 'C', 'below')],
         gap_below=8),

    dict(key='j7_t11', qid=None, vol='卷7', qno=11, slot=None, old_hash=None,
         width='40%', kind='数轴 + 椭圆墨迹遮盖，两端实心点外侧标 −109.2 / 10.5',
         name='j7_t11', type='numline',
         view=(405, 202, 677, 237), pad=12, font=21,
         axis=dict(x0=421, y=218, x1=677),
         inks=[dict(cx=542, rx=78, ry=14)],
         dots=[464, 620], dot_r=2.8,
         labels=[(434.5, '-109.2', 'below'), (636.5, '10.5', 'below')],
         gap_below=4),

    dict(key='j7_t16', qid=None, vol='卷7', qno=16, slot=None, old_hash=None,
         width='40%', kind='数轴 −3~3：实心点 A 在 −3、B 在 0、C 在 2，字母标在点上方',
         name='j7_t16', type='numline',
         view=(745, 1000, 1032, 1044), pad=12, font=21,
         axis=dict(x0=745, y=1025, x1=1032), tick_up=5,
         ticks=[811, 850, 930, 1009],
         dots=[771, 890, 969.5], dot_r=2.8,
         labels=[(771 + i * 39.67, s, 'below') for i, s in
                 enumerate(['-3', '-2', '-1', '0', '1', '2', '3'])]
                + [(771, 'A', 'above'), (890, 'B', 'above'), (969.5, 'C', 'above')],
         gap_below=4, gap_above=9),

    dict(key='j7_t17', qid=None, vol='卷7', qno=17, slot=None, old_hash=None,
         width='48%', kind='空白数轴 −5~5：11 刻度全标数字、无描点（供学生描点作答）',
         name='j7_t17', type='numline',
         view=(589, 242, 1040, 269), pad=13, font=22,
         axis=dict(x0=589, y=249, x1=1040), tick_up=5,
         ticks=evenly(620, 39.6, 11),
         labels=[(620 + i * 39.6, s, 'below') for i, s in
                 enumerate(['-5', '-4', '-3', '-2', '-1', '0', '1', '2', '3', '4', '5'])],
         gap_below=4),

    dict(key='j7_t18', qid=None, vol='卷7', qno=18, slot=None, old_hash=None,
         width='40%', kind='数轴 + 两块墨迹：左块 −6.3 至 −2 与 −1 之间，右块 0 与 1 之间至 4.1；−1、0、5、6 露在墨迹外',
         name='j7_t18', type='numline',
         view=(738, 454, 1040, 487), pad=13, font=19,
         axis=dict(x0=755, y=467, x1=1040),
         inks=[dict(cx=813.3, rx=46.7, ry=11), dict(cx=942.6, rx=38.1, ry=11)],
         ticks=[875.7, 896.3, 999.2, 1019.8], tick_up=7,
         dots=[766.6, 980.7], dot_r=2.8,
         labels=[(758, '-6.3', 'below'), (875.7, '-1', 'below'), (896.3, '0', 'below'),
                 (974, '4.1', 'below'), (999.2, '5', 'below'), (1019.8, '6', 'below')],
         gap_below=4),

    # ---- 卷8（第2章 有理数的运算单元测试卷 B卷提升篇）----
    dict(key='j8_t6', qid=None, vol='卷8', qno=6, slot=None, old_hash=None,
         width='40%', kind='数轴 −1/0/1 三刻度：实心点 A 在 −1 与 0 之间偏靠 0（标 a）、实心点 B 在 1 右侧（标 b）',
         name='j8_t6', type='numline',
         view=(145, 158, 430, 206), pad=13, font=24,
         axis=dict(x0=145, y=184, x1=430), tick_up=7,
         ticks=[225, 287, 349],
         dots=[266, 373], dot_r=5,
         labels=[(225, '-1', 'below'), (287, '0', 'below'), (349, '1', 'below'),
                 (266, 'a', 'below'), (373, 'b', 'below'),
                 (266, 'A', 'above'), (373, 'B', 'above')],
         gap_below=5, gap_above=8),
]


if __name__ == '__main__':
    main()
