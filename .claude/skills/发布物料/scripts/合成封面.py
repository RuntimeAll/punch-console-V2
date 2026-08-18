# -*- coding: utf-8 -*-
r"""合成封面（小红书首图）：册子里取三页裁成纸卡斜叠 ＋ 大标题 ＋ 红斜标签 ＋ 板块清单。

    python .claude\skills\发布物料\scripts\合成封面.py <册目录|册名>          # A/B 两号都出
    python .claude\skills\发布物料\scripts\合成封面.py <册目录|册名> A        # 只出 A 号
    python .claude\skills\发布物料\scripts\合成封面.py <册目录> --配置 x.json

## 🔴 v2 平移标注（2026-08-18）
老区「小红书笔记」skill 里**合成封面没有通用件**，只有按线各存一份的 `出封面.py`
（SKILL.md §4 点名两个正本 + 一句预警："第三条线再复制时如果发现改法又和前两次一样，
那就该抽通用件了"）。三份实物：

    订阅特训\_产线\出封面.py                                   连发型（第 N 天）
    举一反三产物\打卡\幼小衔接数学综合练习\_源\出封面.py         一册型 · A/B 双号  ← 本件底稿
    举一反三产物\打卡\六上分数乘除法打卡\_源\出封面.py           一册型 · 第三份复制

平移时**兑现那个预警**：以「一册型 A/B 双号」那份为底稿，绘制逻辑（五件套构图、
字体分段画、斜标签自适应缩档、纸卡裁切、几何闸）**一字未改**，只把三份之间实际发生过
变化的那几样（书名/板块/题量/取页/裁切带/内容块高度/大标题数字）抽成配置。改动清单：

| # | 老区 | v2 |
|---|---|---|
| ① | 常量写死在脚本里（LINES/PLAN/STEM/BLOCK_TOP/裁切 0.38↔0.42），一册一份 | 全进 `封面配置.json`，脚本一份（模板见 `_模板\封面配置.example.json`） |
| ② | `_BOOK = 脚本上一层`（脚本必须躺在册子里） | 册目录走命令行；册名可简写，默认在 `D:\workplace\ai-bkb-v2\产物\打卡\` 下找 |
| ③ | 底稿 PDF 取 `_交付\<号>版\`（**把号当版用了**） | 🔴 按 `号用版` 交叉表取：A 号→B 版骨架、B 号→A 版骨架（与 `发布包.py` 同一张表） |
| ④ | 出到 `_交付\发布包-<号>\封面-<号>.png` | 出到 `_交付\小红书图·<书名>\<号>\0_封面.png`——🔴 老位置会被 `发布包.py` 的 rmtree 清掉 |
| ⑤ | 取页零重叠靠人记（`_物料闸.py` 事后查） | 载配置时当场 assert：A/B 取页有交集直接拒跑 |
| ⑥ | `import fitz` | 先试 `pymupdf`（新名，与 `AB隔离闸.py` 一致），回退 `fitz` |

🔴 本脚本只读册目录里的 PDF、只写 `_交付\小红书图·<书名>\`，**不碰 kb.db / grading.db**，
   不调任何服务。字体读 `C:\Windows\Fonts`（本机资源，非老区）。

## 🔴 三条口径（老区血案，照抄别复验）
1. **不拿卷子第 1 页当封面**：A4 卷面留白极大，当封面信息量太低——划到只看见一张白纸，
   看不出练什么、多少题、凭什么点进来；十册十张同版面，平台看图也判重。
2. **数字用 Times、汉字用雅黑，分段画**：汉字塞进 Times 渲成豆腐块。
3. **全图唯一的红**只给红斜标签，给了两处就没重点；玉米黄只给品牌方点。

## 🔴 A/B 隔离（七维清单见 SKILL §2，封面这一层要错开四样）
拼图版式（A=fan / B=hero＋整叠镜像）、**取页零重叠**、标签词层（A 吃知识点词 / B 吃场景词）、
底稿 PDF 各取各版。⚠️ 只换版式不换取页 = 白换（页上的题一模一样）。
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

V2主位 = r'D:\workplace\ai-bkb-v2'
册区 = os.path.join(V2主位, '产物', '打卡')

W, H = 1200, 1600                     # 小红书竖版 3:4（feed 里不被裁）
INK = (30, 47, 66)                    # 学术深蓝墨（品牌 --ink）
MUTE = (125, 136, 148)
HAIR = (217, 223, 230)
GRID = (238, 242, 247)                # 坐标纸底纹
CORN = (240, 180, 0)                  # 玉米黄：全图只出现在品牌方点
RED = (198, 32, 38)                   # 🔴 全图唯一的红：给了两处就没重点
RED_D = (146, 16, 22)

# 号 → 用哪一版的骨架（🔴 交叉，与 发布包.py 是同一张表，改一处必须两处一起改）
号用版 = {'A': 'B版', 'B': 'A版'}
图前缀 = '小红书图·'


def 认册目录(arg):
    """认路径，也认光一个册名（补 `产物\\打卡\\` 前缀）。"""
    if os.path.isdir(arg):
        return os.path.abspath(arg)
    cand = os.path.join(册区, arg)
    if os.path.isdir(cand):
        return cand
    sys.exit('🔴 找不到册目录：%s\n   也不在册区 %s 下' % (arg, 册区))


def 读配置(book, path=None):
    """默认找 `<册>\\_源\\封面配置.json`，再找 `<册>\\封面配置.json`。"""
    cands = [path] if path else [os.path.join(book, '_源', '封面配置.json'),
                                 os.path.join(book, '封面配置.json')]
    for c in cands:
        if c and os.path.exists(c):
            with open(c, encoding='utf-8') as fh:
                cfg = json.load(fh)
            cfg['_path'] = c
            查配置(cfg)
            return cfg
    sys.exit('🔴 没有封面配置：%s\n   照 `.claude\\skills\\发布物料\\_模板\\封面配置.example.json` 抄一份'
             % '、'.join(x for x in cands if x))


def 查配置(cfg):
    """载入即闸：缺字段、取页重叠当场拒跑（别等出完图再靠目检）。"""
    for k in ('书名', 'PDF名', '大数字', '板块', '号'):
        if not cfg.get(k):
            sys.exit('🔴 封面配置缺字段 `%s`' % k)
    号表 = cfg['号']
    for 号, p in 号表.items():
        for k in ('tag', 'pages', 'layout', 'head', 'foot'):
            if k not in p:
                sys.exit('🔴 封面配置 号.%s 缺字段 `%s`' % (号, k))
        if len(p['pages']) != 3:
            sys.exit('🔴 封面配置 号.%s 的 pages 必须正好三页（拼图是三张纸卡）' % 号)
    # 🔴 A/B 取页零重叠：版式两套但页上的题一样 = 等于白换（skill §2 第三维）
    if 'A' in 号表 and 'B' in 号表:
        重 = set(号表['A']['pages']) & set(号表['B']['pages'])
        if 重:
            sys.exit('🔴 A/B 取页重叠：%s —— 两号必须零重叠，换页再跑'
                     % '、'.join('第%d页' % (i + 1) for i in sorted(重)))


def _font(px, bold=True, serif=False):
    from PIL import ImageFont
    cands = ([r'C:\Windows\Fonts\timesbd.ttf', r'C:\Windows\Fonts\times.ttf'] if serif
             else ([r'C:\Windows\Fonts\msyhbd.ttc'] if bold else [])
             + [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf'])
    for p in cands:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, px)
            except Exception:
                pass
    return ImageFont.load_default()


def _tw(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0], b[3] - b[1]


def _bg():
    """白底 + 5mm 极浅坐标纸网格（品牌 v4 封面同款底纹）"""
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 30):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 30):
        d.line([(0, y), (W, y)], fill=GRID, width=1)
    return im


def _card(page_img, width, tilt, 裁切带):
    """一页卷面 → 一张「纸卡」：裁有内容的那一条 ＋ 白边 ＋ 淡投影 ＋ 微倾斜。

    🔴 裁切带按册调（配置项 `裁切带`）：卷面下半多是留白算式行，裁浅了只露标题；
       页首若是「今日必读」这类差异点，裁到 0.38 会把它切一半，得放到 0.42。
    """
    from PIL import Image, ImageDraw, ImageFilter
    w0, h0 = page_img.size
    上, 下 = 裁切带
    crop = page_img.crop((0, int(h0 * 上), w0, int(h0 * 下)))
    k = width / crop.width
    crop = crop.resize((width, int(crop.height * k)), Image.LANCZOS)
    b = max(6, width // 60)
    card = Image.new('RGB', (width + b * 2, crop.height + b * 2), (255, 255, 255))
    card.paste(crop, (b, b))
    ImageDraw.Draw(card).rectangle([0, 0, card.width - 1, card.height - 1],
                                   outline=HAIR, width=1)
    pad = 26
    lay = Image.new('RGBA', (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([pad + 5, pad + 8, pad + card.width + 5,
                                 pad + card.height + 8], fill=(30, 47, 66, 62))
    lay = Image.alpha_composite(lay, sh.filter(ImageFilter.GaussianBlur(9)))
    lay.paste(card, (pad, pad))
    return lay.rotate(tilt, expand=True, resample=Image.BICUBIC)


def _label(text, angle, maxw, 头词='这本练'):
    """红色斜标签。字号自适应，放不下就缩一档。"""
    import math
    from PIL import Image, ImageDraw
    fs = 74
    while True:
        f1, f2 = _font(int(fs * 0.60)), _font(fs)
        tmp = ImageDraw.Draw(Image.new('RGB', (10, 10)))
        w1, h1 = _tw(tmp, 头词, f1)
        w2, h2 = _tw(tmp, text, f2)
        px1, px2, py = int(fs * 0.40), int(fs * 0.46), int(fs * 0.34)
        w = px1 * 2 + w1 + px2 * 2 + w2
        h = max(h1, h2) + py * 2 + int(fs * 0.34)
        if (w * math.cos(math.radians(abs(angle)))
                + h * math.sin(math.radians(abs(angle))) <= maxw or fs <= 40):
            break
        fs -= 4
    lay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    head = px1 * 2 + w1
    d.rectangle([0, 0, w, h], fill=RED + (245,))
    d.rectangle([0, 0, head, h], fill=RED_D + (250,))
    d.text((px1, (h - h1) // 2 - int(fs * 0.10)), 头词, font=f1, fill=(255,) * 3 + (255,))
    d.text((head + px2, (h - h2) // 2 - int(fs * 0.13)), text, font=f2,
           fill=(255,) * 3 + (255,))
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0))
    sh.paste((30, 47, 66, 70), (0, 0), lay.split()[3])
    return (lay.rotate(angle, expand=True, resample=Image.BICUBIC),
            sh.rotate(angle, expand=True, resample=Image.BICUBIC))


def _pages(pdf, idxs, dpi=112):
    try:
        import pymupdf                       # 新名，与 AB隔离闸.py 一致
    except ImportError:                      # noqa: BLE001
        try:
            import fitz as pymupdf           # 老名回退
        except ImportError:
            sys.exit('🔴 需要 pymupdf：pip install pymupdf')
    from PIL import Image
    doc = pymupdf.open(pdf)
    out = []
    for i in idxs:
        if i >= doc.page_count:
            doc.close()
            sys.exit('🔴 取页越界：要第 %d 页，但 %s 只有 %d 页'
                     % (i + 1, os.path.basename(pdf), doc.page_count))
        pm = doc[i].get_pixmap(dpi=dpi)
        out.append(Image.frombytes('RGB', (pm.width, pm.height), pm.samples))
    doc.close()
    return out


def build(cfg, 号, pdf, out_path):
    from PIL import Image, ImageDraw
    p = cfg['号'][号]
    裁切带 = cfg.get('裁切带', [0.02, 0.40])
    BLOCK_TOP = H - cfg.get('内容块顶偏移', 482)   # 🔴 绘制与纸卡闸共用这一个数
    行距 = cfg.get('行距', 56)
    im = _bg()
    d = ImageDraw.Draw(im)
    M = 76

    # ── ① 眉行：品牌一处小字（黄方点＋名），右侧学段 ──────────────────────
    d.rectangle([M, 74, M + 15, 89], fill=CORN)
    d.text((M + 26, 68), cfg.get('品牌', '玉米训练营'), font=_font(27), fill=INK)
    t = cfg.get('眉行右', '')
    f_eb = _font(27, bold=False)
    w, _ = _tw(d, t, f_eb)
    d.text((W - M - w, 70), t, font=f_eb, fill=MUTE)
    d.line([(M, 116), (W - M, 116)], fill=INK, width=2)

    # ── ② 大标题：N 天（Times 数字）＋ 节奏；右侧规格 ───────────────────────
    # 🔴 数字用 Times、汉字用雅黑，**分段画** —— 汉字塞进 Times 会渲成豆腐块
    f_num, f_cn = _font(150, serif=True), _font(62)
    大数字 = str(cfg['大数字'])
    d.text((M - 4, 128), 大数字, font=f_num, fill=INK)
    nw, _ = _tw(d, 大数字, f_num)
    d.text((M + nw + 16, 152), cfg.get('大数字后', '天'), font=f_cn, fill=INK)
    d.text((M + nw + 92, 168), cfg.get('节奏', ''), font=_font(48), fill=INK)
    f_n, f_u = _font(46, serif=True), _font(34)
    seg = [(s, f_n if kind == 'n' else f_u) for s, kind in cfg.get('规格', [])]
    ws = [_tw(d, s, f)[0] for s, f in seg]
    x = W - M - sum(ws)
    for (s, f), sw in zip(seg, ws):
        d.text((x, 246 + (0 if f is f_n else 8)), s, font=f, fill=INK)
        x += sw
    d.text((M, 268), cfg.get('学段行', ''), font=_font(32), fill=INK)

    # ── ③ 红斜标签（全图唯一的红）────────────────────────────────────────
    lab, lsh = _label(p['tag'], p.get('angle', -6.5), W - M * 2 + 40,
                      cfg.get('标签头词', '这本练'))
    lx, ly = M - 24, 340
    im.paste(Image.alpha_composite(
        Image.new('RGBA', lsh.size, (255, 255, 255, 0)), lsh), (lx + 7, ly + 9), lsh)
    im.paste(lab, (lx, ly), lab)

    # ── ④ 拼图：三页斜叠 ────────────────────────────────────────────────
    pgs = _pages(pdf, p['pages'])
    top = ly + lab.size[1] + 26
    if p['layout'] == 'fan':                    # 扇形：中间在前，两侧外张
        cw = cfg.get('扇形卡宽', 556)
        cs = [_card(pgs[0], cw, 5.4, 裁切带), _card(pgs[2], cw, -4.6, 裁切带),
              _card(pgs[1], cw, 0.8, 裁切带)]
        pos = [(M - 40, top + 34), (W - M - cw + 22, top + 58), ((W - cw) // 2, top)]
    else:                                       # hero：一大两小
        cs = [_card(pgs[0], 576, -2.2, 裁切带), _card(pgs[1], 352, 4.6, 裁切带),
              _card(pgs[2], 352, -5.2, 裁切带)]
        pos = [(M - 48, top + 30), (W - M - 352, top - 10), (W - M - 330, top + 150)]
    if p.get('flip'):                           # 只把落点左右对调，卡片内容不翻（字得能读）
        pos = [(W - x - c.size[0], y) for (x, y), c in zip(pos, cs)]
    # 🔴 闸：纸卡不许伸进下方内容块。图压字是**静默事故** —— 图照样存盘、尺寸也正常，
    #    只有渲出来看才发现底下那行被卡片盖掉半行（老区幼小衔接 B 版实伤）。
    #    这里算一次几何，超了当场 assert，别指望目检每次都逮到。
    bottom = max(y + c.size[1] for c, (_, y) in zip(cs, pos))
    if bottom > BLOCK_TOP - 8:
        sys.exit('🔴 %s 号纸卡底 %d 已侵入内容块（顶 %d）：把卡片改窄、'
                 '或把配置里的 内容块顶偏移 调小' % (号, bottom, BLOCK_TOP))
    for c, q in zip(cs, pos):
        im.paste(c, q, c)

    # ── ⑤ 内容块：各板块 ＋ 题量 ＋ 一句 ──────────────────────────────────
    y = BLOCK_TOP + 30
    d.line([(M, BLOCK_TOP), (W - M, BLOCK_TOP)], fill=HAIR, width=2)
    d.text((M, y - 16), p['head'], font=_font(38), fill=INK)
    y += 44
    f_ln, f_nq, f_u2, f_bl = (_font(34), _font(32, serif=True), _font(25),
                              _font(28, bold=False))
    for name, nq, blurb in cfg['板块']:
        d.rectangle([M + 2, y + 12, M + 10, y + 30], fill=RED)
        d.text((M + 26, y), name, font=f_ln, fill=INK)
        w, _ = _tw(d, name, f_ln)
        d.text((M + 40 + w, y + 4), str(nq), font=f_nq, fill=MUTE)
        nw2, _ = _tw(d, str(nq), f_nq)
        d.text((M + 47 + w + nw2, y + 10), '题', font=f_u2, fill=MUTE)
        bw, _ = _tw(d, blurb, f_bl)
        d.text((W - M - bw, y + 6), blurb, font=f_bl, fill=MUTE)
        y += 行距

    # ── 底行 ────────────────────────────────────────────────────────────
    d.line([(M, H - 126), (W - M, H - 126)], fill=INK, width=2)
    d.rectangle([M + 2, H - 94, M + 10, H - 70], fill=CORN)
    d.text((M + 26, H - 100), p['foot'], font=_font(30), fill=INK)
    im.save(out_path, 'PNG', optimize=True)
    return out_path


def 找底稿(book, cfg, 号):
    """🔴 按 号用版 交叉表取骨架：A 号发的是 B 版，B 号发的是 A 版（见 发布包.py 文件头）。

    配置里可用 `稿版` 显式覆盖；两处都取不到时，退回册根同名 PDF（单版册子）。
    """
    p = cfg['号'][号]
    版 = p.get('稿版') or 号用版.get(号)
    tried = []
    if 版:
        c = os.path.join(book, '_交付', 版, cfg['PDF名'])
        tried.append(c)
        if os.path.exists(c):
            return c, 版
    for c in (os.path.join(book, cfg['PDF名']),
              os.path.join(book, '_源', cfg['PDF名'])):
        tried.append(c)
        if os.path.exists(c):
            return c, '（单版）'
    sys.exit('🔴 %s 号找不到底稿 PDF，试过：\n   %s' % (号, '\n   '.join(tried)))


def main():
    ap = argparse.ArgumentParser(description='合成封面（小红书首图，一册型 A/B 双号）')
    ap.add_argument('book', help=r'册目录（含 _交付/），或光一个册名（默认在 产物\打卡\ 下找）')
    ap.add_argument('号', nargs='?', default=None, help='只出某一号（A / B）；不给则全出')
    ap.add_argument('--配置', dest='cfg', default=None, help='封面配置 json 路径')
    a = ap.parse_args()

    book = 认册目录(a.book)
    cfg = 读配置(book, a.cfg)
    书名 = cfg['书名']
    号表 = list(cfg['号'])
    if a.号:
        t = a.号.upper()
        if t not in 号表:
            sys.exit('🔴 配置里没有 %s 号（有：%s）' % (t, '、'.join(号表)))
        号表 = [t]

    print('合成封面　%s　《%s》　配置=%s' % (book, 书名, cfg['_path']))
    for 号 in 号表:
        pdf, 版 = 找底稿(book, cfg, 号)
        out_dir = os.path.join(book, '_交付', 图前缀 + 书名, 号)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, '0_封面.png')
        build(cfg, 号, pdf, out)
        # 🔴 把「号↔版」印出来：这条交叉是最容易拿错文件的地方
        print('  🟢 %s 号封面（骨架=%s，取页 %s）→ %s'
              % (号, 版, '、'.join('第%d页' % (i + 1) for i in cfg['号'][号]['pages']), out))
    print('\n  下一步：出正文配图 → python .claude\\skills\\发布物料\\scripts\\AB隔离闸.py "%s"'
          % book)
    print('        → python .claude\\skills\\发布物料\\scripts\\发布包.py "%s"' % book)


if __name__ == '__main__':
    main()
