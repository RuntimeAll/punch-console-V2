# -*- coding: utf-8 -*-
"""观察物体图形渲染器 —— 等距立方体堆 + 视图方格图。

坐标系（单位立方体，整数格）：
    x 轴 → 屏幕右下   y 轴 → 屏幕左下   z 轴 → 屏幕正上
观察者在 (+x, +y, +z) 方向俯视 ⇒ 可见三面 = 顶面(z+1) / 左面(x+1，画面右下)
/ 前面(y+1，画面左下)；深度 d = x+y+z，d 越大越靠近观察者（画家算法按 d 升序绘制）。

物体方位约定（与画面一致）：**前 = +y，后 = -y，右 = +x，左 = -x，上 = +z**。
（屏幕右 = u × f = (1,-1,0)；站在前面 (+y) 朝 -y 看时，观察者的右手方向 = +x，与画面一致。）
三视图口径（人教/学而思课本第一角投影）：
    从前面看：列 = x 正序（右在右），行 = z 倒序（高在上）
    从左面看：列 = y 正序（🔴 物体的「前」在右侧，课本定则），行 = z 倒序
    从上面看：列 = x 正序，行 = y 正序（🔴 上方是「后」，下方是「前」）

用法：
    cells = {(0,0,0), (1,0,0), (0,0,1)}
    img = draw_solid(cells)
    img.save("a.png")
"""
from PIL import Image, ImageDraw

# ── 等距投影参数（放大 2 倍再缩，抗锯齿）──
SS = 3                 # 超采样倍数
W = 26                 # x/y 方向半宽（屏幕水平位移）
H = 15                 # x/y 方向垂直位移
Z = 30                 # z 方向高度
LINE = 2               # 线宽（超采样前）
PAD = 10

FACE_TOP = (252, 252, 252)
FACE_RIGHT = (232, 232, 232)
FACE_FRONT = (243, 243, 243)
EDGE = (30, 30, 30)


def _proj(x, y, z):
    return ((x - y) * W, (x + y) * H - z * Z)


def _cube_faces(x, y, z):
    """返回三个可见面 [(4个3D角点, 填充色)]：前面(+y) / 左面(+x) / 顶面(+z)。"""
    top = [(x, y, z + 1), (x + 1, y, z + 1), (x + 1, y + 1, z + 1), (x, y + 1, z + 1)]
    front = [(x, y + 1, z), (x + 1, y + 1, z), (x + 1, y + 1, z + 1), (x, y + 1, z + 1)]   # +y 面（左下）
    side = [(x + 1, y, z), (x + 1, y + 1, z), (x + 1, y + 1, z + 1), (x + 1, y, z + 1)]    # +x 面（右下）
    return [(front, FACE_FRONT), (side, FACE_RIGHT), (top, FACE_TOP)]


def fully_hidden(cells):
    """🔴 等距投影下 (x,y,z) 与 (x+1,y+1,z+1) 屏幕位置完全重合，后者把前者整块盖住。
    返回所有「被完全盖住」的方块。实心堆内部有若干这样的块是正常的。"""
    cells = set(cells)
    return {c for c in cells if (c[0] + 1, c[1] + 1, c[2] + 1) in cells}


def hidden_tops(cells):
    """🔴 硬伤检测：某一摞的**顶部方块**被完全盖住 ⇒ 看图数不出这一摞，图不可用于出题。
    出题用的立体图必须 hidden_tops(cells) == set()。"""
    cells = set(cells)
    tops = {}
    for (x, y, z) in cells:
        if (x, y) not in tops or z > tops[(x, y)]:
            tops[(x, y)] = z
    return {(x, y, z) for (x, y), z in tops.items() if (x + 1, y + 1, z + 1) in cells}


def assert_readable(cells, name=""):
    """🔴 出题前闸：每一摞的顶部方块都必须看得见，否则学生看图数不出块数。
    （层数多的堆，让后排比前排高一层，纵深最好读；这是排版建议，不作硬闸——
      平铺形状前后排等高也是可读的，因为在等距图里两排本来就错开。）"""
    bad = hidden_tops(cells)
    if bad:
        raise ValueError(f"[{name}] 摞顶被完全遮挡，看图数不出块数：{sorted(bad)}")
    return True


def draw_solid(cells, scale=1.0, pad=PAD):
    """cells = 可迭代的 (x,y,z) 整数三元组集合 → PIL.Image（白底黑线立体图）。"""
    cells = sorted(set(cells))
    if not cells:
        raise ValueError("cells 不能为空")

    # 先算包围盒
    pts = []
    for (x, y, z) in cells:
        for face, _ in _cube_faces(x, y, z):
            pts += [_proj(*p) for p in face]
    minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)

    w = int((maxx - minx + 2 * pad) * SS * scale)
    h = int((maxy - miny + 2 * pad) * SS * scale)
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)

    def sp(p3):
        sx, sy = _proj(*p3)
        return ((sx - minx + pad) * SS * scale, (sy - miny + pad) * SS * scale)

    # 画家算法：远 → 近。观察者在 (+x,+y,+z)，深度 d = x+y+z 越大越靠前，故 d 升序绘制
    for (x, y, z) in sorted(cells, key=lambda c: (c[0] + c[1] + c[2], c[2], c[0], c[1])):
        for face, color in _cube_faces(x, y, z):
            dr.polygon([sp(p) for p in face], fill=color,
                       outline=EDGE, width=int(LINE * SS * scale))

    out_w = max(1, int(w / SS)); out_h = max(1, int(h / SS))
    return img.resize((out_w, out_h), Image.LANCZOS)


# ── 三视图（方格图）──
CELL = 40
GLINE = 2


def views_of(cells):
    """由积木集合算三视图，返回 {'top':set((col,row)), 'front':..., 'left':...}
    坐标一律 (col, row)，row 从 0 起、0 = 图形最上面一行。"""
    cells = set(cells)
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]; zs = [c[2] for c in cells]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    z0, z1 = min(zs), max(zs)

    front = {(x - x0, (z1 - z)) for (x, y, z) in cells}          # 列=x 正序（右在右），行=z 倒序
    left = {(y - y0, (z1 - z)) for (x, y, z) in cells}           # 列=y 正序（前在右），行=z 倒序
    top = {(x - x0, (y - y0)) for (x, y, z) in cells}            # 列=x 正序，行=y 正序（后在上）
    return {"top": top, "front": front, "left": left}


def draw_view(filled, cols=None, rows=None, cell=CELL):
    """filled = {(col,row)} → 方格视图（只画有的格，白底黑框）。"""
    filled = set(filled)
    if not filled:
        raise ValueError("filled 不能为空")
    cols = cols or max(c for c, r in filled) + 1
    rows = rows or max(r for c, r in filled) + 1
    w = cols * cell * SS + 2 * SS
    h = rows * cell * SS + 2 * SS
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)
    for (c, r) in sorted(filled):
        x0 = c * cell * SS + SS; y0 = r * cell * SS + SS
        dr.rectangle([x0, y0, x0 + cell * SS, y0 + cell * SS],
                     fill="white", outline=EDGE, width=GLINE * SS)
    return img.resize((max(1, w // SS), max(1, h // SS)), Image.LANCZOS)


def draw_net(net, cell=CELL, font_size=26):
    """展开图：net = {(row, col): '标签'} → 方格图，格内居中写标签。"""
    from PIL import ImageFont
    rows = max(r for r, c in net) + 1
    cols = max(c for r, c in net) + 1
    w = cols * cell * SS + 2 * SS
    h = rows * cell * SS + 2 * SS
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)
    ft = None
    for p in (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
        try:
            ft = ImageFont.truetype(p, font_size * SS)
            break
        except OSError:
            continue
    for (r, c), lab in sorted(net.items()):
        x0 = c * cell * SS + SS; y0 = r * cell * SS + SS
        dr.rectangle([x0, y0, x0 + cell * SS, y0 + cell * SS],
                     fill="white", outline=EDGE, width=GLINE * SS)
        t = str(lab)
        if ft:
            bb = dr.textbbox((0, 0), t, font=ft)
            dr.text((x0 + (cell * SS - (bb[2] - bb[0])) / 2 - bb[0],
                     y0 + (cell * SS - (bb[3] - bb[1])) / 2 - bb[1]),
                    t, fill=(20, 20, 20), font=ft)
    return img.resize((max(1, w // SS), max(1, h // SS)), Image.LANCZOS)


def hstack(images, gap=28, labels=None, font=None):
    """把多张图横排成一张（可选每张下方文字标签）。"""
    from PIL import ImageFont
    if font is None:
        for p in (r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
            try:
                font = ImageFont.truetype(p, 20)
                break
            except OSError:
                continue
    lab_h = 28 if labels else 0
    h = max(im.height for im in images) + lab_h
    w = sum(im.width for im in images) + gap * (len(images) - 1)
    out = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(out)
    x = 0
    for i, im in enumerate(images):
        out.paste(im, (x, (h - lab_h - im.height) // 2))
        if labels and font:
            t = labels[i]
            tw = dr.textlength(t, font=font)
            dr.text((x + (im.width - tw) / 2, h - lab_h + 4), t, fill=(20, 20, 20), font=font)
        x += im.width + gap
    return out
