# -*- coding: utf-8 -*-
r"""AB 隔离闸：**内容必须同源，版面必须不同**。

    python AB隔离闸.py <册目录>
    python AB隔离闸.py <册目录> --图 "小红书图·有理数运算一本通"

## 🔴 这道闸在管什么
双号发布靠**换版面骨架**防平台判重（不是换水印，水印和 dpi 都改不动结构）。
但"两版要不一样"是句口号 —— 靠人记就一定会漏。真实漏法（2026-08-10 全踩过）：

1. **正文分了骨架，封面/目录忘了分** —— 出书脚本对两版共用一份前页 CSS，
   只换输出文件名。于是 A 号发的第 1 张和 B 号发的第 1 张是同一张脸，
   **漏在最显眼的位置**。
2. **两号配图取了同一条线的同一页** —— 版面是两套没错，但内容一样，
   平台看图仍然像同一篇。
3. **为了差异化把内容也改了** —— 这是反向事故：两个号的题/答案对不上，
   客户买了两版会以为发错货。

## 🔴 判据只有一条（硬）：**同一页的几何指纹必须不同**
几何指纹 = 该页所有 span 的 `(x, y, 字号)` 排序后取 hash，**不含文字**。
它刻画的正是平台判重看的那层东西：栏数、题号位置、留白分布、节头形式。
两版同一页指纹相同 = 版面压根没差异化（多半只换了水印或 dpi）。

## ⚠️ 「内容同源」**不由本闸判错，只做提示**
第一版把「两版纯文本必须逐字相同」也写成硬判据，**当场全线误报** ——
七上第二单元打卡册的 A 版是把题意并进题面的（`-7 的相反数是 ___`），
B 版走独立题组行（`1. 求下列各数的相反数` + `(1) -7`），
**文本本来就不同，那是设计**；题号形态（通栏连号 ‖ 分组编号）也必然不同。

内容同源真正的保证在**产线结构**：两版出卷器读的是同一份 `days.py`／`qbank.py`，
根本没有第二份数据。拿 PDF 文本反推同源性，只会把正常设计判成事故。
所以这里只打印**文本相似度**供人扫一眼：太低（<40%）时提醒确认有没有误改内容。

## 用法前提
册目录下的成品按版分目录：`_交付/A版/*.pdf` 与 `_交付/B版/*.pdf`，两边**同名**。
配图（可选）：`_交付/<图目录名>/A/*.png` 与 `/B/*.png`。
"""
import argparse
import difflib
import hashlib
import os
import re
import sys

# 🔴 stdout 和 stderr **都要转** —— 失败信息走 `sys.exit(msg)` 即 stderr，
#    只转 stdout 的话，GBK 控制台上最关键的那句报错是一堆乱码（实测踩过）。
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

try:
    import pymupdf
except ImportError:                              # noqa: BLE001
    sys.exit('🔴 需要 pymupdf：pip install pymupdf')


def 几何指纹(page):
    """只取几何、丢掉文字 —— 这才是平台判重看的那层。"""
    items = sorted(
        (round(sp['bbox'][0], 1), round(sp['bbox'][1], 1), round(sp['size'], 1))
        for b in page.get_text('dict')['blocks']
        for ln in b.get('lines', [])
        for sp in ln['spans'])
    return hashlib.md5(str(items).encode()).hexdigest()[:12]


def 纯文本(page):
    """去掉所有空白后的文字。**只用来算相似度做提示**，不作判据（见文件头）。"""
    return re.sub(r'\s+', '', page.get_text())


def 查PDF(book):
    """→ (坏的份数, 查过没)。**查过没**很关键：见 main 里"别把跳过当全绿"。"""
    deliv = os.path.join(book, '_交付')
    da, db = os.path.join(deliv, 'A版'), os.path.join(deliv, 'B版')
    if not (os.path.isdir(da) and os.path.isdir(db)):
        print('  跳过 PDF：没有 _交付/A版 与 _交付/B版 两个目录')
        return 0, False
    共有 = sorted(set(os.listdir(da)) & set(os.listdir(db)))
    共有 = [f for f in 共有 if f.lower().endswith('.pdf')]
    if not 共有:
        print('  跳过 PDF：两版没有同名文件')
        return 0, False

    坏 = 0
    for name in 共有:
        a = pymupdf.open(os.path.join(da, name))
        b = pymupdf.open(os.path.join(db, name))
        n = min(a.page_count, b.page_count)
        撞版, 比值 = [], []
        for i in range(n):
            if 几何指纹(a[i]) == 几何指纹(b[i]):
                撞版.append(i + 1)
            比值.append(difflib.SequenceMatcher(None, 纯文本(a[i]), 纯文本(b[i])).quick_ratio())
        note = ''
        if a.page_count != b.page_count:
            # 版面变了分页跟着变是正常的，只提示不判错
            note = '（页数 %d/%d 不同，按短的比）' % (a.page_count, b.page_count)
        a.close(); b.close()
        平均 = sum(比值) / len(比值) if 比值 else 1.0

        if 撞版:
            坏 += 1
            print('  🔴 %s%s' % (name, note))
            print('     **版面没隔离**的页：%s' % _缩(撞版))
            print('     两版这些页的 (x,y,字号) 完全一致 —— 换的不是骨架，可能只换了水印/dpi。')
            if 1 in 撞版 or 2 in 撞版:
                print('     ⚠️ 第 1/2 页是封面与目录：**双号发出去的头两张图就是同一张脸**，'
                      '最该隔离的位置。出书脚本的前页多半两版共用了同一份 CSS。')
        else:
            print('  🟢 %s%s　%d 页版面逐页不同（文本相似度 %.0f%%）' % (name, note, n, 平均 * 100))
        # 相似度只是提示：太低时**人去确认**是不是误改了内容，闸不判错（理由见文件头）
        if 平均 < 0.40:
            print('     ⚠️ 文本相似度偏低 —— 确认一下两版是不是不小心用了不同的题源'
                  '（题意措辞/题号形态不同是正常的，题和答案不该不同）。')
    return 坏, True


def 查图(book, 图目录):
    """→ (坏的项数, 查过没)。

    认两套目录约定：
      现行  `_交付/小红书图·<名>/A/` 与 `/B/`
      老册  `_交付/小红书图-A浅水印/` 与 `_交付/小红书图-B深水印/`（平级两个目录）
    老约定是"靠水印区分双号"那个年代留下的（口径早已作废），但老册续造时还会遇到。
    """
    deliv = os.path.join(book, '_交付')
    if not os.path.isdir(deliv):
        print('  跳过配图：没有 _交付/')
        return 0, False

    da = db = None
    if 图目录:
        root = os.path.join(deliv, 图目录)
        da, db = os.path.join(root, 'A'), os.path.join(root, 'B')
    else:
        新式 = [d for d in os.listdir(deliv)
                if d.startswith('小红书图') and os.path.isdir(os.path.join(deliv, d))
                and os.path.isdir(os.path.join(deliv, d, 'A'))]
        if len(新式) == 1:
            root = os.path.join(deliv, 新式[0])
            da, db = os.path.join(root, 'A'), os.path.join(root, 'B')
        elif len(新式) > 1:
            print('  跳过配图：找到 %d 个图目录，用 --图 指定一个' % len(新式))
            return 0, False
        else:
            老A = [d for d in os.listdir(deliv) if re.match(r'^小红书图-A', d)]
            老B = [d for d in os.listdir(deliv) if re.match(r'^小红书图-B', d)]
            if len(老A) == 1 and len(老B) == 1:
                da, db = os.path.join(deliv, 老A[0]), os.path.join(deliv, 老B[0])
                print('  （老式图目录：%s ‖ %s）' % (老A[0], 老B[0]))

    if not (da and db and os.path.isdir(da) and os.path.isdir(db)):
        print('  跳过配图：没找到 A/B 两个图目录')
        return 0, False

    def 扫(d):
        out = {}
        for f in sorted(os.listdir(d)):
            if f.lower().endswith('.png'):
                with open(os.path.join(d, f), 'rb') as fh:
                    out[f] = hashlib.md5(fh.read()).hexdigest()
        return out

    A, Bm = 扫(da), 扫(db)
    坏 = 0
    撞 = [(x, y) for x, ha in A.items() for y, hb in Bm.items() if ha == hb]
    if 撞:
        坏 += 1
        print('  🔴 配图字节相同（两号发出去必判重）：')
        for x, y in 撞:
            print('     A/%s  ==  B/%s' % (x, y))
    # 文件名里的「正文·<管线名>」两号不该撞：版面两套但取同一条线的同一页，内容仍然一样
    def 线(names):
        s = set()
        for f in names:
            m = re.search(r'正文[·・](.+?)\.png$', f)
            if m:
                s.add(m.group(1))
        return s
    重线 = 线(A) & 线(Bm)
    if 重线:
        坏 += 1
        print('  🔴 两号取了**同一条线**的正文页：%s' % '、'.join(sorted(重线)))
        print('     版面是两套，但页上的题一模一样 —— 换一条线取图。')
    if not 撞 and not 重线:
        print('  🟢 配图 A %d 张 / B %d 张：字节两两不同、取的线不重叠' % (len(A), len(Bm)))
    return 坏, True


def _缩(nums):
    return '、'.join(str(n) for n in nums[:12]) + ('…共 %d 页' % len(nums) if len(nums) > 12 else '')


def main():
    ap = argparse.ArgumentParser(description='AB 隔离闸：内容同源 + 版面不同')
    ap.add_argument('book', help='册目录（含 _交付/）')
    ap.add_argument('--图', dest='imgdir', default=None, help='配图目录名，如「小红书图·xxx」')
    a = ap.parse_args()
    book = os.path.abspath(a.book)
    print('AB 隔离闸　%s' % book)
    坏1, 查过1 = 查PDF(book)
    坏2, 查过2 = 查图(book, a.imgdir)
    坏 = 坏1 + 坏2
    print()
    if 坏:
        sys.exit('🔴 %d 处没隔离 —— 双号发出去会被判重，先修再发。' % 坏)
    # 🔴 **别把"跳过"当"全绿"**：目录不符约定时两项都跳，若还打全绿，
    #    等于给一本根本没查过的册子发通行证 —— 闸装死比闸不存在更危险。
    if not (查过1 or 查过2):
        sys.exit('🔴 什么都没查到 —— 这册的目录不符合约定，闸等于没跑。\n'
                 '   期望：`_交付/A版/` 与 `_交付/B版/` 放同名 PDF；'
                 '配图放 `_交付/小红书图·<名>/A|B/`。\n'
                 '   **不要把这条当通过。**')
    if not 查过1:
        print('⚠️ 只查了配图，PDF 没查（缺 _交付/A版 与 _交付/B版）。')
    if not 查过2:
        print('⚠️ 只查了 PDF，配图没查（没找到 A/B 两个图目录）。')
    print('🟢 通过：查到的部分版面均已隔离。')


if __name__ == '__main__':
    main()
