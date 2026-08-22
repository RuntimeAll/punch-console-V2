# -*- coding: utf-8 -*-
"""配图防盗贴纸（2026-08-22 用户令）
==============================================================================
需求原话：「加一个无法去除的水印，发布的图片里面加在中间，跟贴纸贴上去的一样，
贴纸就用玉米训练营，加一个图标，然后无法抹去，而且是直接看不到一些字，
不需要全部都有，每隔一张加一个，第一页不加」

🔴 实现要点（这三条决定它"抹不掉"）：
  1. **不透明**：贴纸是实心色块，盖住的正文像素**被丢弃**，不是叠加半透明——
     抠图/去水印工具只能修复"叠加型"水印，实心遮挡区的原字无从还原；
  2. **贴在正中**：正中间是题干最密的地方，遮住的是内容不是留白，裁掉贴纸=裁掉题目；
  3. **隔张贴**：第 1 张（首图）干净负责吸引点击，之后偶数张各贴一张——
     想白嫖的人拼不出完整一份，买家拿到的网盘件是无水印正本。

用法：
    python 贴纸水印.py <图目录> [--every 2] [--skip-first] [--out <目录>]
"""
import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

BRAND = '玉米训练营'
# 品牌色：玉米黄底 + 深褐字，贴纸感（实心+描边+投影）
FILL = (255, 199, 44)
EDGE = (120, 74, 12)
TEXT = (90, 52, 6)
FONTS = (r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc',
         r'C:\Windows\Fonts\simhei.ttf')


def load_font(px):
    for f in FONTS:
        if Path(f).exists():
            try:
                return ImageFont.truetype(f, px)
            except Exception:
                continue
    return ImageFont.load_default()


def corn_icon(size):
    """画一个玉米图标（矢量画，不依赖 emoji 字体——emoji 在无头环境常渲成豆腐块）。"""
    S = size * 4                                   # 4 倍超采样再缩，边缘干净
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # 两片叶子
    d.polygon([(S * .50, S * .92), (S * .12, S * .66), (S * .40, S * .60)], fill=(76, 145, 60))
    d.polygon([(S * .50, S * .92), (S * .88, S * .66), (S * .60, S * .60)], fill=(101, 173, 78))
    # 穗体
    d.ellipse([S * .28, S * .06, S * .72, S * .82], fill=(247, 181, 30), outline=EDGE,
              width=max(2, S // 40))
    # 籽粒网格
    for r in range(6):
        for c in range(3):
            x = S * .36 + c * S * .13 + (S * .065 if r % 2 else 0)
            y = S * .16 + r * S * .105
            if (x - S * .5) ** 2 / (S * .2) ** 2 + (y - S * .44) ** 2 / (S * .36) ** 2 <= 1:
                d.ellipse([x - S * .045, y - S * .035, x + S * .045, y + S * .035],
                          fill=(255, 214, 92), outline=(198, 141, 22), width=max(1, S // 90))
    return im.resize((size, size), Image.LANCZOS)


# 底色不透明度（用户 2026-08-22：「背景淡一点、透明一点，字保持原样」）
# 🔴 只有**底色**半透明：图标与「玉米训练营」五个字仍是实心，压住的笔画照样丢失。
BG_ALPHA = 110
EDGE_ALPHA = 190
SHADOW_ALPHA = 45


def make_sticker(width_px, bg_alpha=BG_ALPHA):
    """一张贴纸（RGBA，含描边与投影），宽度 = width_px。"""
    pad = int(width_px * 0.055)
    fs = int(width_px * 0.135)
    font = load_font(fs)
    icon = int(fs * 1.5)
    gap = int(fs * 0.42)
    dummy = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    tw = int(dummy.textlength(BRAND, font=font))
    th = int(fs * 1.28)
    w = pad * 2 + icon + gap + tw
    h = pad * 2 + max(icon, th)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(h * 0.26)
    # 底色半透明（能透出题目），描边与文字仍然实心 —— 贴纸感留住、遮挡力留在字上
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=FILL + (bg_alpha,),
                        outline=EDGE + (EDGE_ALPHA,), width=max(3, int(h * 0.045)))
    im.paste(icon_img := corn_icon(icon), (pad, (h - icon) // 2), icon_img)
    d.text((pad + icon + gap, (h - th) // 2 + int(fs * 0.06)), BRAND, font=font,
           fill=TEXT + (255,))
    return im


def stamp(src, dst, ratio=0.46, angle=-11, bg_alpha=BG_ALPHA):
    im = Image.open(src).convert('RGBA')
    W, H = im.size
    st = make_sticker(int(W * ratio), bg_alpha)
    # 投影：贴纸感的关键
    sh = Image.new('RGBA', st.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([0, 0, st.size[0] - 1, st.size[1] - 1],
                                         radius=int(st.size[1] * 0.26),
                                         fill=(0, 0, 0, SHADOW_ALPHA))
    off = max(3, int(W * 0.004))
    layer = Image.new('RGBA', (st.size[0] + off * 2, st.size[1] + off * 2), (0, 0, 0, 0))
    layer.paste(sh, (off * 2, off * 2), sh)
    layer.paste(st, (0, 0), st)
    rot = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    im.alpha_composite(rot, ((W - rot.size[0]) // 2, (H - rot.size[1]) // 2))
    im.convert('RGB').save(dst, quality=95)
    return rot.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--every', type=int, default=2, help='每隔几张贴一张（2=隔一张）')
    ap.add_argument('--skip-first', action='store_true', default=True)
    ap.add_argument('--ratio', type=float, default=0.46)
    ap.add_argument('--bg-alpha', type=int, default=BG_ALPHA,
                    help='底色不透明度 0~255（越小越透，字与图标不受影响）')
    a = ap.parse_args()
    files = sorted(Path(a.dir).glob('*.png'))
    if not files:
        sys.exit('🔴 目录里没有 png')
    done = []
    for i, f in enumerate(files, 1):
        if i == 1 and a.skip_first:
            print(f'  [{i:>2}] 跳过（首图保持干净）  {f.name}')
            continue
        if i % a.every:
            print(f'  [{i:>2}] 不贴              {f.name}')
            continue
        sz = stamp(f, f, a.ratio, bg_alpha=a.bg_alpha)
        done.append(f.name)
        print(f'  [{i:>2}] 🟢 贴纸 {sz[0]}×{sz[1]}   {f.name}')
    print(f'\n共 {len(files)} 张，贴了 {len(done)} 张（首图不贴，每 {a.every} 张贴 1 张）')


if __name__ == '__main__':
    main()
