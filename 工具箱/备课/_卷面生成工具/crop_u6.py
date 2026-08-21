# -*- coding: utf-8 -*-
"""从原书 PDF 裁出第六单元「条形统计图」最后 4 题（考点七·统计图表综合应用）。

条形统计图题的图表又大又密，重排文字必失真 → **直接按坐标裁原书版面**，最忠实。
题2 跨页（p134 底 + p135 顶），裁两块上下拼。
"""
import os
import fitz

SRC = (r"D:\workplace\ai-bkb\测试数据\小学数学所有内容\新四上人教版数学同步典例考点讲义"
       r"\第一套\空白题目\26新版四上同步讲义汇总（原卷版）162页 人教版 .pdf")
OUT = r"D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第11课-平四梯形与统计图\figs"
os.makedirs(OUT, exist_ok=True)
DPI = 200
# 🔴 X0 必须留够左边距：62 会切掉「【」和纵轴刻度（实测），用 40
X0, X1 = 40, 552

# (输出名, [(页码1-based, y0, y1), ...])  多段=跨页拼接
CUTS = [
    ('u6_q1.png', [(133, 320, 690)]),                      # 典型例题·洛阳太原地铁客运量
    ('u6_q2.png', [(134, 68, 566)]),                       # 对应练习1·黄豆花生营养成分
    ('u6_q3.png', [(134, 630, 748), (135, 66, 296)]),      # 对应练习2·男女生喜欢的活动（跨页）
    ('u6_q4.png', [(135, 333, 748)]),                      # 对应练习3·体育达标（5 小问，最综合）
]


def crop(doc, page_no, y0, y1):
    pg = doc[page_no - 1]
    m = fitz.Matrix(DPI / 72, DPI / 72)
    return pg.get_pixmap(matrix=m, clip=fitz.Rect(X0, y0, X1, y1))


def to_img(pix):
    from PIL import Image
    return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)


def main():
    from PIL import Image
    doc = fitz.open(SRC)
    for name, segs in CUTS:
        imgs = [to_img(crop(doc, p, a, b)) for p, a, b in segs]
        if len(imgs) == 1:
            out = imgs[0]
        else:                                   # 跨页：等宽上下拼
            w = max(i.width for i in imgs)
            h = sum(i.height for i in imgs)
            out = Image.new('RGB', (w, h), 'white')
            y = 0
            for i in imgs:
                out.paste(i, (0, y))
                y += i.height
        out.save(os.path.join(OUT, name))
        print(f'{name}  {out.width}×{out.height}')
    doc.close()


if __name__ == '__main__':
    main()
