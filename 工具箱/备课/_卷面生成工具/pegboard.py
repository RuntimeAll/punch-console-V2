# -*- coding: utf-8 -*-
"""钉板（geoboard）渲染器 —— 配合实物钉板教具出卷面图。

坐标：(x, y)，x 向右、y 向上，(0,0) = 左下角那颗钉子（与学生看板子的方位一致）。
用法：
    draw_board(3, polys=[[(0,1),(1,0),(2,1),(1,2)]])      # 3×3 板上围一个斜正方形
    draw_board(3, marks=[(0.5,1),(1,0.5)])                # 标出对角线交点（可为半格坐标）
"""
from PIL import Image, ImageDraw, ImageFont

SS = 3            # 超采样
CELL = 46         # 钉距（px，超采样前）
PAD = 22
PEG_R = 4.2       # 钉子半径
BAND_W = 3.2      # 橡皮筋线宽
EDGE = (25, 25, 25)
PEG = (70, 70, 70)
FILL = (232, 240, 248)


def _font(size, ss=1):
    """ss=SS 时给超采样画布用；ss=1 给已缩回原尺寸的画布用（grid 标签走这个）。"""
    for p in (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
        try:
            return ImageFont.truetype(p, int(size * ss))
        except OSError:
            continue
    return None


def draw_board(nx, ny=None, polys=None, marks=None, cell=CELL, band=BAND_W, fill=True, skew=0.0):
    """nx×ny 钉板。polys=[[(x,y),...]] 橡皮筋围的多边形；marks=[(x,y)] 额外标记（可半格）。
    skew≠0 → 整块板「推斜」成平行四边形阵（x' = x + skew·y），用于「推斜后还剩几个」那类题。"""
    ny = ny or nx
    w = ((nx - 1) + abs(skew) * (ny - 1)) * cell + 2 * PAD
    h = (ny - 1) * cell + 2 * PAD
    img = Image.new("RGB", (int(w * SS), int(h * SS)), "white")
    dr = ImageDraw.Draw(img)
    x_off = PAD + (abs(skew) * (ny - 1) * cell if skew < 0 else 0)

    def P(x, y):
        return ((x_off + (x + skew * y) * cell) * SS, (PAD + (ny - 1 - y) * cell) * SS)

    for poly in (polys or []):
        pts = [P(*p) for p in poly]
        if fill:
            dr.polygon(pts, fill=FILL)
        dr.line(pts + [pts[0]], fill=EDGE, width=int(band * SS), joint="curve")

    for x in range(nx):
        for y in range(ny):
            cx, cy = P(x, y)
            r = PEG_R * SS
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PEG, outline=PEG)

    for m in (marks or []):
        cx, cy = P(*m)
        r = (PEG_R + 2.6) * SS
        dr.line([cx - r, cy - r, cx + r, cy + r], fill=(200, 0, 0), width=int(2 * SS))
        dr.line([cx - r, cy + r, cx + r, cy - r], fill=(200, 0, 0), width=int(2 * SS))

    return img.resize((int(w), int(h)), Image.LANCZOS)


def draw_lattice(m, n=None, skew=0.0, cell=CELL, hi=None, band=BAND_W, dots=False):
    """方格纸 / 斜格纸：m×n 个小格（→ (m+1)×(n+1) 个格点）。
    skew≠0 → 竖线变斜线（x' = x + skew·y），得到**平行四边形网格**。
    hi = [(x0,y0,x1,y1)] 要加粗描出的子矩形（格坐标），用于示意某一个长方形/平四。"""
    n = n or m
    x_span = m + abs(skew) * n
    w = x_span * cell + 2 * PAD
    h = n * cell + 2 * PAD
    img = Image.new("RGB", (int(w * SS), int(h * SS)), "white")
    dr = ImageDraw.Draw(img)
    x0 = PAD + (abs(skew) * n * cell if skew < 0 else 0)

    def P(x, y):
        return ((x0 + (x + skew * y) * cell) * SS, (PAD + (n - y) * cell) * SS)

    thin = max(1, int(1.6 * SS))
    for j in range(n + 1):                       # 横线（斜格里仍是水平的）
        dr.line([P(0, j), P(m, j)], fill=PEG, width=thin)
    for i in range(m + 1):                       # 竖线 / 斜线
        dr.line([P(i, 0), P(i, n)], fill=PEG, width=thin)
    for (ax, ay, bx, by) in (hi or []):
        dr.line([P(ax, ay), P(bx, ay), P(bx, by), P(ax, by), P(ax, ay)],
                fill=EDGE, width=int(band * SS), joint="curve")
    if dots:
        for i in range(m + 1):
            for j in range(n + 1):
                cx, cy = P(i, j)
                r = PEG_R * SS
                dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PEG)
    return img.resize((int(w), int(h)), Image.LANCZOS)


def draw_trap_layers(layers=4, top=2.0, bottom=6.0, cell=CELL):
    """等腰梯形被 layers-1 条平行于底的线分成 layers 层（数梯形题用）。"""
    h_units = layers
    w = bottom * cell + 2 * PAD
    h = h_units * cell + 2 * PAD
    img = Image.new("RGB", (int(w * SS), int(h * SS)), "white")
    dr = ImageDraw.Draw(img)
    cx = (PAD + bottom * cell / 2) * SS

    def row(j):
        """第 j 条线（j=0 最下＝下底，j=layers 最上＝上底）的两端。"""
        wj = bottom + (top - bottom) * j / layers
        y = (PAD + (h_units - j) * cell) * SS
        return (cx - wj * cell * SS / 2, y), (cx + wj * cell * SS / 2, y)

    for j in range(layers + 1):
        a, b = row(j)
        wide = int(BAND_W * SS) if j in (0, layers) else max(1, int(1.6 * SS))
        dr.line([a, b], fill=EDGE if j in (0, layers) else PEG, width=wide)
    (la, _), (ra, _) = (row(0)[0], None), (row(0)[1], None)
    lb, rb = row(layers)
    dr.line([row(0)[0], lb], fill=EDGE, width=int(BAND_W * SS))
    dr.line([row(0)[1], rb], fill=EDGE, width=int(BAND_W * SS))
    return img.resize((int(w), int(h)), Image.LANCZOS)


def draw_stick_rows(counts, stick_w=7, stick_h=26, gap=13, row_gap=36,
                    outline=False, label=False):
    """小棒阵：counts=[每行根数]，每行居中排列 → 行数递增时整体轮廓就是一个**梯形**。
    outline=True 画虚线梯形轮廓；label=True 标出「上底／下底／高」（答案卷用，题目卷别开）。"""
    n = len(counts)
    mx = max(counts)
    body = mx * stick_w + (mx - 1) * gap          # 最长一行的宽度
    # 🔴 label 时左右要留够写标注的位置，否则文字会被画布切掉（实测踩过）
    lpad, rpad = (105, 235) if label else (16, 16)
    vpad = 30 if label else 16
    w = lpad + body + rpad
    h = n * stick_h + (n - 1) * (row_gap - stick_h) + 2 * vpad
    img = Image.new("RGB", (int(w * SS), int(h * SS)), "white")
    dr = ImageDraw.Draw(img)
    cx = (lpad + body / 2) * SS
    pad = vpad

    def row_span(i):
        """第 i 行（0-based）左右端 x 与顶部 y（超采样坐标）。"""
        c = counts[i]
        total = c * stick_w + (c - 1) * gap
        x0 = cx - total * SS / 2
        y = (pad + i * row_gap) * SS
        return x0, x0 + total * SS, y

    if outline:
        _, _, ytop = row_span(0)
        l0, r0, _ = row_span(0)
        l1, r1, ylast = row_span(n - 1)
        yb = ylast + stick_h * SS
        m = 4 * SS
        for a, b in ((( l0 - m, ytop - m), (r0 + m, ytop - m)),
                     ((l1 - m, yb + m), (r1 + m, yb + m)),
                     ((l0 - m, ytop - m), (l1 - m, yb + m)),
                     ((r0 + m, ytop - m), (r1 + m, yb + m))):
            _dash(dr, a, b, width=int(2 * SS))

    for i in range(n):
        x0, _, y = row_span(i)
        for k in range(counts[i]):
            x = x0 + k * (stick_w + gap) * SS
            dr.rectangle([x, y, x + stick_w * SS, y + stick_h * SS],
                         fill=(40, 40, 40), outline=(40, 40, 40))

    if label:
        ft = _font(15, SS)
        l0, r0, ytop = row_span(0)
        l1, r1, ylast = row_span(n - 1)
        yb = ylast + stick_h * SS
        if ft:
            dr.text((r0 + 14 * SS, ytop - 6 * SS), f"上底＝第1行 {counts[0]} 根",
                    fill=(160, 0, 0), font=ft)
            dr.text((r1 + 14 * SS, yb - 18 * SS), f"下底＝第{n}行 {counts[-1]} 根",
                    fill=(160, 0, 0), font=ft)
            dr.text((l1 - 30 * SS, (ytop + yb) / 2), f"高＝{n} 行",
                    fill=(160, 0, 0), font=ft, anchor="rm")
    return img.resize((int(w), int(h)), Image.LANCZOS)


def _dash(dr, a, b, width=2, on=9, off=7):
    """虚线段（PIL 没有原生虚线）。"""
    import math
    (x0, y0), (x1, y1) = a, b
    d = math.hypot(x1 - x0, y1 - y0)
    if d == 0:
        return
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    t = 0.0
    step = (on + off) * SS
    while t < d:
        e = min(t + on * SS, d)
        dr.line([x0 + ux * t, y0 + uy * t, x0 + ux * e, y0 + uy * e],
                fill=(170, 0, 0), width=width)
        t += step


def grid(images, cols=4, gap=18, labels=None, label_size=15):
    """把多张同尺寸小图排成 cols 列的网格（用于展示「一共几个」的枚举结果）。"""
    ft = _font(label_size)          # 网格画布未超采样，字号按原尺寸
    lab_h = int(label_size * 1.6) if labels else 0
    # 🔴 列宽要同时容下图和标签，否则长标签会串到隔壁列
    lab_w = 0
    if labels and ft:
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        lab_w = max(probe.textlength(t, font=ft) for t in labels)
    cw = int(max(max(im.width for im in images), lab_w) + gap)
    ch = max(im.height for im in images) + gap + lab_h
    rows = (len(images) + cols - 1) // cols
    out = Image.new("RGB", (cw * min(cols, len(images)), ch * rows), "white")
    dr = ImageDraw.Draw(out)
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        x = c * cw + (cw - gap - im.width) // 2 + gap // 2
        y = r * ch + gap // 2
        out.paste(im, (x, y))
        if labels and ft:
            t = labels[i]
            tw = dr.textlength(t, font=ft)
            dr.text((c * cw + (cw - tw) / 2, y + im.height + 2), t, fill=(40, 40, 40), font=ft)
    return out
