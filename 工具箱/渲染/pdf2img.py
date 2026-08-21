# -*- coding: utf-8 -*-
r"""PDF → 图片 通用件（发布物料/目检/配图 共用一把）

    python 工具箱\渲染\pdf2img.py <输入...> --out <目录> [选项]

输入可以混着给：PDF 文件、目录（自动找里面的 *.pdf）、通配符。
按给的先后顺序处理，序号命名时的编号顺序就是这个顺序。

常用三条：

    # ① 全页出图目检（不要水印）
    python 工具箱\渲染\pdf2img.py 产物\某卷.pdf --out 目检 --无水印

    # ② 发布配图：每份卷只取第 1 页，带水印，顺序编号 01.png 02.png…
    python 工具箱\渲染\pdf2img.py "产物\某册\*.pdf" --out 图 --pages first --命名 序号

    # ③ 一份卷全页 ＋ 另几份各首页，拼成一组配图（输入顺序即编号顺序）
    python 工具箱\渲染\pdf2img.py 卷一.pdf --out 图 --命名 序号 --清空
    python 工具箱\渲染\pdf2img.py 卷二.pdf 卷三.pdf --out 图 --pages first --命名 序号 --起号 5

🔴 三条口径（都做成闸，不靠注释）：
  1. **越界不静默**：`--pages 1-4` 撞上只有 3 页的卷，越界页逐条打警告并**退出码 2**，
     除非显式 `--允许越界`——少出一张图这种事，事后目检最容易漏。
  2. **序号模式不覆盖旧图**：输出目录里已有 png 一律拒跑，要么 `--清空` 要么换目录
     （两批图混一个目录 = 发出去顺序全乱）。
  3. **水印默认开**：出去见人的图带水印是常态，要干净件显式 `--无水印`
     （付费客户拿到的 PDF 才是干净的，图片物料不是）。

只读 PDF、只写 `--out` 目录；不碰两库、不调任何服务。字体读 C:\Windows\Fonts（本机资源）。
"""
import argparse
import glob as _glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

品牌 = '玉米训练营'
默认水印色 = '7a7a7a'          # A 号浅水印（发布物料 SKILL §1）


# ────────────────────────────────────────────────────────────── 输入与取页
def 收输入(args):
    """PDF 文件 / 目录 / 通配符 → 有序 PDF 路径表（去重保序）。"""
    out = []
    for a in args:
        if os.path.isdir(a):
            hit = sorted(_glob.glob(os.path.join(a, '*.pdf')))
        elif any(c in a for c in '*?['):
            hit = sorted(_glob.glob(a))
        else:
            hit = [a]
        if not hit:
            sys.exit('🔴 没匹配到任何 PDF：%s' % a)
        for p in hit:
            if not p.lower().endswith('.pdf'):
                continue
            if not os.path.exists(p):
                sys.exit('🔴 文件不存在：%s' % p)
            if p not in out:
                out.append(p)
    if not out:
        sys.exit('🔴 输入里一个 PDF 都没有')
    return out


def 解析取页(spec, n):
    """取页规格 → 0 基页号表 ＋ 越界清单（1 基，用于报警）。

    支持：all / first / last / 3 / 1-3 / 1,3,5-7 / -1（倒数第一页）
    """
    s = (spec or 'all').strip().lower()
    if s == 'all':
        return list(range(n)), []
    if s == 'first':
        return ([0], []) if n else ([], [1])
    if s == 'last':
        return ([n - 1], []) if n else ([], [1])
    want, bad = [], []
    for part in s.replace('，', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part[1:]:                       # 首字符的 - 是负号，不是区间
            a, b = part.split('-', 1)
            try:
                a, b = int(a), int(b)
            except ValueError:
                sys.exit('🔴 取页规格看不懂：%r' % part)
            rng = range(a, b + 1) if a <= b else range(a, b - 1, -1)
        else:
            try:
                rng = [int(part)]
            except ValueError:
                sys.exit('🔴 取页规格看不懂：%r' % part)
        for one in rng:
            if one == 0:
                sys.exit('🔴 页号从 1 开始，没有第 0 页')
            i = one - 1 if one > 0 else n + one   # -1 = 最后一页
            if 0 <= i < n:
                if i not in want:
                    want.append(i)
            else:
                bad.append(one)
    return want, bad


# ────────────────────────────────────────────────────────────── 水印
def _字体(px):
    from PIL import ImageFont
    for p in (r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc',
              r'C:\Windows\Fonts\simhei.ttf'):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                pass
    return ImageFont.load_default()


def 造水印瓦(文本, 色hex, 透明, 角度, 字号, 疏密):
    from PIL import Image, ImageDraw
    h = 色hex.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    f = _字体(字号)
    b = ImageDraw.Draw(Image.new('RGB', (10, 10))).textbbox((0, 0), 文本, font=f)
    tw, th = b[2] - b[0], b[3] - b[1]
    间x, 间y = int(300 * 疏密), int(260 * 疏密)
    lay = Image.new('RGBA', (tw + 间x, th + 间y), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((0, 0), 文本, font=f, fill=rgb + (透明,))
    return lay.rotate(角度, expand=True, resample=Image.BICUBIC)


def 打水印(im, 瓦):
    from PIL import Image
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    tw, th = 瓦.size
    for y in range(-th, im.size[1] + th, th):
        for x in range(-tw, im.size[0] + tw, tw):
            lay.alpha_composite(瓦, (x, y))
    return Image.alpha_composite(im.convert('RGBA'), lay).convert('RGB')


# ────────────────────────────────────────────────────────────── 主流程
def 出名(模板, 卷, 页, 序, 前缀):
    if 模板 == '序号':
        名 = '%02d' % 序
    elif 模板 == '原名':
        名 = '%s-p%d' % (卷, 页)
    else:
        名 = 模板.format(卷=卷, 页=页, 序=序, 序2='%02d' % 序)
    return (前缀 or '') + 名 + '.png'


def main():
    ap = argparse.ArgumentParser(
        description='PDF → 图片 通用件（发布配图 / 目检 / 物料）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='取页规格：all | first | last | 3 | 1-3 | 1,3,5-7 | -1（倒数第一页）')
    ap.add_argument('输入', nargs='+', help='PDF 文件 / 目录 / 通配符（按给定顺序处理）')
    ap.add_argument('--out', required=True, help='输出目录（不存在自动建）')
    ap.add_argument('--pages', default='all', help='取页规格，默认 all')
    ap.add_argument('--dpi', type=int, default=150, help='渲染 dpi，默认 150（A4≈1240×1754）')
    ap.add_argument('--宽', type=int, default=0, dest='宽', help='最大宽度像素，等比缩；0=不缩')
    ap.add_argument('--命名', default='原名',
                    help='原名（默认，<卷名>-p<页>）| 序号（01.png…）| 模板串，可用 {卷}{页}{序}{序2}')
    ap.add_argument('--前缀', default='', help='文件名前缀')
    ap.add_argument('--起号', type=int, default=1, help='序号模式起始号，默认 1')
    ap.add_argument('--清空', action='store_true', help='先删掉输出目录里已有的 *.png')
    ap.add_argument('--清单', action='store_true', help='额外写 清单.md（哪张图来自哪个 PDF 第几页）')
    ap.add_argument('--水印', default=品牌, help='水印文字，默认 ' + 品牌)
    ap.add_argument('--无水印', action='store_true', dest='无水印', help='关水印（目检/干净件用）')
    ap.add_argument('--水印色', default=默认水印色, dest='水印色', help='十六进制，默认 ' + 默认水印色)
    ap.add_argument('--水印透明', type=int, default=24, dest='水印透明', help='0~255，默认 24')
    ap.add_argument('--水印角度', type=int, default=30, dest='水印角度', help='默认 30')
    ap.add_argument('--水印字号', type=int, default=46, dest='水印字号', help='默认 46')
    ap.add_argument('--水印疏密', type=float, default=1.0, dest='水印疏密', help='>1 更稀疏，默认 1.0')
    ap.add_argument('--允许越界', action='store_true', dest='允许越界', help='越界页只警告不改退出码')
    a = ap.parse_args()

    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf
        except ImportError:
            sys.exit('🔴 需要 pymupdf：pip install pymupdf')
    from PIL import Image

    pdfs = 收输入(a.输入)
    os.makedirs(a.out, exist_ok=True)
    已有 = sorted(_glob.glob(os.path.join(a.out, '*.png')))
    if a.清空:
        for p in 已有:
            os.remove(p)
        已有 = []
    # 🔴 闸②：序号模式撞上旧图 = 两批混一起顺序必乱，当场拒跑
    if 已有 and a.命名 == '序号' and a.起号 <= len(已有):
        sys.exit('🔴 %s 里已有 %d 张 png，起号 %d 会和旧图混序'
                 '——加 --清空、换目录，或把 --起号 提到 %d'
                 % (a.out, len(已有), a.起号, len(已有) + 1))

    瓦 = None if a.无水印 else 造水印瓦(a.水印, a.水印色, a.水印透明,
                                        a.水印角度, a.水印字号, a.水印疏密)
    序 = a.起号
    出件, 越界 = [], []
    for pdf in pdfs:
        卷 = os.path.splitext(os.path.basename(pdf))[0]
        doc = pymupdf.open(pdf)
        idxs, bad = 解析取页(a.pages, doc.page_count)
        for one in bad:
            越界.append((卷, one, doc.page_count))
            print('  ⚠️ %s 只有 %d 页，第 %d 页取不到' % (卷, doc.page_count, one))
        for i in idxs:
            pm = doc[i].get_pixmap(dpi=a.dpi)
            im = Image.frombytes('RGB', (pm.width, pm.height), pm.samples)
            if a.宽 and im.width > a.宽:
                im = im.resize((a.宽, round(im.height * a.宽 / im.width)), Image.LANCZOS)
            if 瓦 is not None:
                im = 打水印(im, 瓦)
            fn = 出名(a.命名, 卷, i + 1, 序, a.前缀)
            im.save(os.path.join(a.out, fn), 'PNG', optimize=True)
            出件.append((fn, 卷, i + 1))
            序 += 1
        doc.close()
        print('  🟢 %-46s 取 %d 页' % (卷, len(idxs)))

    if a.清单:
        p = os.path.join(a.out, '清单.md')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('# 图片清单（%d 张，dpi=%d，水印=%s）\n\n' %
                    (len(出件), a.dpi, '无' if a.无水印 else a.水印))
            f.write('| 图 | 来自 | 页 |\n|---|---|---|\n')
            for fn, 卷, pg in 出件:
                f.write('| %s | %s | p%d |\n' % (fn, 卷, pg))
        print('  📄 清单 →', p)

    print('\n%d 份 PDF → %d 张图　%s' % (len(pdfs), len(出件), os.path.abspath(a.out)))
    if 越界:
        print('🔴 %d 页越界被跳过（少出的图最容易漏，别当没发生）' % len(越界))
        if not a.允许越界:
            return 2
    print('PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
