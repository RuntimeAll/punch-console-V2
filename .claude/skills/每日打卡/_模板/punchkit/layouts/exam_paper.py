# -*- coding: utf-8 -*-
"""
骨架 `exam_paper` —— A4 真实试卷版式（单元测试卷 / 期中期末卷 / 专项卷）
=====================================================================
对标件 = `测试数据/七上试卷/卷3/`（4 张拍照卷面，七年级数学上册单元测试卷·第1章有理数）。
逐条照着卷面长的，别自己改：

  1. **卷头三行**：居中大标题（22pt 黑体）→ 居中副标题「第1章 有理数」→
     居中副标行「（满分：120 分　考试时间：120 分钟）」。三行之后才是可选的
     姓名行 / 「题号—得分」评分表。
  2. **大题节标题带分值**：`一、选择题（每小题 3 分，共 33 分）` —— 黑体、左顶格、
     `page-break-after:avoid`（节标题绝不许落在页底当孤儿）。
  3. 🔴 **题号全卷连号**：卷 3 的题号是 1→24 一路排下去**跨节不重置**（选择 1~11、
     填空 12~15、解答 16~24）。渲染器只知道"节内第几题"，所以本骨架**自己打题号**：
     渲完再把 `<span class="qn">` 换成全卷连号；渲染器没打题号的槽位（expr/oral/fill
     的题目卷）则补一个进去 —— 试卷上**每道题都必须有号**。
     副作用（好的那种）：不再吃渲染器答案卷 `①~⑩` 圈码的 10 题上限。
  4. **解答题题号带分值**：`16.(6 分)` —— 卷面原样。由 `sections[i]['item_scores']` 驱动。
  5. **题距紧凑**：行高 1.85、题间 1.2mm，靠 `gap_each` 明码标价给作答留白，
     而不是把题排稀。选择题/填空题 `gap_each=0` 就是卷面那种一行接一行的密度。
  6. **一卷 = 一张卡，内容自然流到多页**：所以页边距走 `@page margin`（每页都有），
     不能像别的骨架那样用 `.card` 的上下 padding（那个只作用在首页与末页）。

🔴 **学科无关**：`ctx['renderer']` 挂谁都行；选择题槽沿用渲染器的 `tpl-choice-v1`
   列位口径（`<table>` 网格，跨行绝对对齐），本骨架**不重写选项排布**。

旋钮全在 `paper.layout`（render-pack 的 layout_json）与 `sections[i]` 里，见 SPEC['旋钮']。
"""
import re

from .. import core

SPEC = {
    'key': 'exam_paper',
    'name': 'A4 真卷·单元测试卷',
    '学科': '通用',
    '长相': '居中大标题 + 副标题 + 「（满分：N 分　考试时间：N 分钟）」副标行；'
            '可选姓名行 / 「题号—得分」评分表 / 左侧装订密封线；'
            '黑体大题节标题带分值「一、选择题（每小题 3 分，共 33 分）」；'
            '🔴 题号**全卷连号**、解答题题号带分值「16.(6 分)」；题距紧凑，一卷多页连排',
    '适合': '单元测试卷 / 期中期末卷 / 专项训练卷 —— 要的是"像一张真卷"，'
            '不是打卡册那种一天一页',
    '每页': '不定（一张卷 = 一张卡，内容自然流到多页；页边距走 @page 每页都在）',
    '槽位': '由 ctx["sections"] 逐节指定，任意组合；'
            'choice 沿用渲染器 tpl-choice-v1 的 table 网格列位口径',
    '数据形状': 'days = [卷, ...]；卷 = [第1节items, 第2节items, ...]，与 ctx["sections"] 等长'
                '（**与 dense_sections / boxed_sections 同契约 → 一行互换**）',
    '用过的册': '（2026-08-20 新建，对标 测试数据/七上试卷/卷3 拍照卷面）',
    '旋钮': 'paper.layout：subtitle 副标题｜full_score 满分｜duration_min 时长分钟｜'
            'name_row 姓名行(true/项名数组)｜score_table 评分表(true)｜seal_line 装订密封线(true)｜'
            'head_note 副标行后小字；'
            'sections[i]：score_note 节标题分值说明｜item_scores 逐题分值(数组或单数)｜'
            'show_item_score 题号后印不印分值(缺省 true)｜'
            'gap_each 每题后留白mm｜gap 节末留白mm｜cols 节内分栏数',
    '闸': '满分守恒闸（逐题分值合计 == 卷头满分）｜item_scores 数量闸｜题号连号闸（guard）',
}

CN = '一二三四五六七八九十'
DEFAULT_PT = 11.5
# 页边距（mm）：对着卷 3 拍照件量的 —— 卷面正文净宽约 186mm（页边 ~12mm），
# 比打卡册紧一圈；节标题那种长括号说明正好一行放得下，就是靠这个宽度。
MARGIN_TOP, MARGIN_X, MARGIN_BOTTOM = 13.0, 12.0, 12.0
SEAL_GUTTER_MM = 13.0            # 开装订线时 .card 额外让出的左侧走廊（卷 3 实测约 13mm）

CSS = """
  @page { size: A4; margin: __MT__mm __MX__mm __MB__mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.85; color: #000; }

  /* 一卷 = 一张卡；卡内容自然流到多页，卡与卡之间强制分页 */
  .card { page-break-after: always; }
  .card:last-child { page-break-after: auto; }

  /* ═══ 卷头 ═══ */
  h1 { font-family: "SimHei", sans-serif; font-size: __H1__pt; line-height: 1.28;
       text-align: center; letter-spacing: .04em; margin: 0 0 1.6mm; }
  .sub { font-family: "SimHei", sans-serif; font-size: __H2__pt; text-align: center;
         margin: 0 0 1.6mm; }
  .meta { text-align: center; margin: 0 0 2mm; }
  .hnote { text-align: center; font-size: .92em; margin: 0 0 2mm; }

  .names { margin: 0 0 2.6mm; }
  .names em { font-style: normal; margin-right: 8mm; }
  .names em:last-child { margin-right: 0; }
  .names i { display: inline-block; width: 26mm; border-bottom: .3mm solid #000;
             font-style: normal; }

  /* 「题号 / 一 / 二 / 三 / 总分」评分表 —— 卷 3 卷头原样 */
  .stab { width: 100%; border-collapse: collapse; table-layout: fixed;
          text-align: center; margin: 0 0 2.8mm; }
  .stab td { border: .3mm solid #000; height: 8.4mm; }
  .stab td.k { width: 20%; }

  /* ═══ 大题节标题 ═══ */
  .sec { font-family: "SimHei", sans-serif; margin: 3.2mm 0 1mm;
         page-break-after: avoid; break-after: avoid; }
  .card > .sec:first-of-type { margin-top: 1.2mm; }

  /* ═══ 题 ═══ */
  .q { margin: 0 0 1.2mm; break-inside: avoid; page-break-inside: avoid; }
  .q > div { padding-left: 1.7em; text-indent: -1.7em; }
  .qn { font-family: "SimHei", sans-serif; margin-right: .1em; }
  .sp { }
  .cols { display: grid; column-gap: 6mm; }

  /* ═══ 左侧装订密封线（可选）═══
     🔴 一卷多页 ⇒ 只能用 position:fixed（Chrome 打印时每页重绘一次）；
     absolute 只会印在第一页上。 */
  .card.sealed { padding-left: __SEAL__mm; }
  .sealbar { position: fixed; left: 0; top: 0; bottom: 0; width: __SEAL__mm; }
  .sealbar .dash { position: absolute; left: 9.5mm; top: 0; bottom: 0;
                   border-left: .3mm dashed #000; }
  .sealbar .txt { position: absolute; left: 0; top: 0; bottom: 0; width: 8mm;
                  writing-mode: vertical-rl; text-align: center;
                  letter-spacing: .55em; font-size: .95em;
                  display: flex; align-items: center; justify-content: center; }

  .wm { position: fixed; right: 0; bottom: 0;
        font-family: "SimHei", sans-serif; font-size: .9em; color: #666; }
  .wm img { height: 12pt; vertical-align: -2.5pt; margin-right: 1mm; }

  /* ═══ 答案卷：紧排、无留白、无卷头装饰 ═══ */
  body.asheet { line-height: 1.7; }
  body.asheet .sp { display: none !important; }
  body.asheet .q { margin-bottom: .6mm; }
  body.asheet .sec { margin: 2.4mm 0 .8mm; }
"""


# ══════════════════════════════════════════════════════════════════════
# 小工具
# ══════════════════════════════════════════════════════════════════════
def _f(d, *keys):
    """按序取第一个非 None 的键。英文键为准，中文键当别名（layout_json 两种写法都吃）。"""
    for k in keys:
        v = (d or {}).get(k)
        if v is not None:
            return v
    return None


def _num(x):
    """`120` / `'120'` / `'120 分'` → 120.0；取不出数就返回 None（不静默当 0）。"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    m = re.search(r'-?\d+(?:\.\d+)?', str(x))
    return float(m.group()) if m else None


def _g(x):
    """分值好看写法：6.0 → 6，6.5 → 6.5"""
    f = _num(x)
    if f is None:
        return str(x)
    return ('%g' % f)


def _item_scores(sec, n, si):
    """该节逐题分值 → [分, ...]；没给返回 None。数量对不上直接拒（静默错号=坏卷）。"""
    v = _f(sec, 'item_scores', '题分')
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return [v] * n
    v = list(v)
    assert len(v) == n, ('🔴 第%s大题 item_scores 给了 %d 个，本节实有 %d 题 —— '
                         '题号会挂错分值，拒渲' % (CN[si], len(v), n))
    return v


_QN_RE = re.compile(r'<span class="qn">.*?</span>', re.S)


def _renumber(html, label):
    """🔴 把渲染器打的节内题号换成**全卷连号**；渲染器没打号的槽位就补一个进去。

    渲染器只认得"本节第 i 题"（`math._qn` 题目卷给 `1.`、答案卷给圈码 `①`），
    而真卷的题号跨节连续。所以题号这件事由骨架收口：渲完替换，只换第一个。
    """
    tag = '<span class="qn">%s</span>' % label
    out, n = _QN_RE.subn(lambda m: tag, html, count=1)
    if n:
        return out
    i = html.find('>')                       # 塞进第一个块级元素的开标签之后
    return (html[:i + 1] + tag + html[i + 1:]) if i >= 0 else tag + html


# ══════════════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════════════
def css(pt=None, body_pt=None):
    pt = float(body_pt or pt or DEFAULT_PT)
    k = pt / DEFAULT_PT
    from ..renderers import math as _default
    return (CSS.replace('__H1__', '%.2f' % (22.0 * k))
               .replace('__H2__', '%.2f' % (15.5 * k))
               .replace('__PT__', '%.2f' % pt)
               .replace('__MT__', '%g' % MARGIN_TOP)
               .replace('__MX__', '%g' % MARGIN_X)
               .replace('__MB__', '%g' % MARGIN_BOTTOM)
               .replace('__SEAL__', '%g' % SEAL_GUTTER_MM)) + _default.CSS


# ══════════════════════════════════════════════════════════════════════
# 卷头
# ══════════════════════════════════════════════════════════════════════
_DEFAULT_NAMES = ('姓名', '班级', '学号')


def _head(lay, secs, ctx):
    """副标题 + 副标行 + 小字 + 姓名行 + 评分表（题目卷才出；答案卷只留 h1）。"""
    o = []
    sub = _f(lay, 'subtitle', '副标题')
    if sub:
        o.append('<div class="sub">%s</div>' % sub)

    full, dur = _num(_f(lay, 'full_score', '满分')), _num(_f(lay, 'duration_min', '时长'))
    bits = []
    if full is not None:
        bits.append('满分：%s 分' % _g(full))
    if dur is not None:
        bits.append('考试时间：%s 分钟' % _g(dur))
    if bits:
        o.append('<div class="meta">（%s）</div>' % '　'.join(bits))

    note = _f(lay, 'head_note', '卷头小字')
    if note:
        o.append('<div class="hnote">%s</div>' % note)

    nr = _f(lay, 'name_row', '姓名行')
    if nr:
        fields = _DEFAULT_NAMES if nr is True else tuple(nr)
        o.append('<div class="names">%s</div>'
                 % ''.join('<em>%s：<i></i></em>' % f for f in fields))

    if _f(lay, 'score_table', '评分表'):
        head = ''.join('<td>%s</td>' % CN[i] for i in range(len(secs)))
        blank = '<td></td>' * (len(secs) + 1)
        o.append('<table class="stab">'
                 '<tr><td class="k">题号</td>%s<td>总分</td></tr>'
                 '<tr><td class="k">得分</td>%s</tr></table>' % (head, blank))
    return ''.join(o)


def _seal(lay):
    if not _f(lay, 'seal_line', '密封线'):
        return '', ''
    txt = _f(lay, 'seal_text', '密封线文字') or '学校　　　班级　　　姓名　　　学号'
    return (' sealed',
            '<div class="sealbar"><div class="txt">%s</div><div class="dash"></div></div>' % txt)


def _watermark(ctx):
    """试卷默认**无水印**（真卷不带广告）。要就 ctx['watermark'] 显式给。"""
    wm = ctx.get('watermark')
    if not wm:
        return ''
    if isinstance(wm, str):
        wm = {'text': wm, 'img': True}
    img = core.watermark_img() if wm.get('img', True) else ''
    style = (' style="color:%s"' % wm['color']) if wm.get('color') else ''
    return '<div class="wm"%s>%s%s</div>' % (style, img, wm.get('text', ''))


# ══════════════════════════════════════════════════════════════════════
# 主体
# ══════════════════════════════════════════════════════════════════════
def render_card(idx, data, ans, ctx):
    """
    idx  第几张卷（0 起）
    data 该卷数据 = [第1节items, ...]，与 ctx['sections'] 等长
    ctx  {'renderer', 'sections', 'book_title', 'paper_layout'(本骨架的旋钮包), ...}
    """
    R = ctx['renderer']
    secs = ctx['sections']
    lay = ctx.get('paper_layout') or {}
    assert len(data) == len(secs), \
        '🔴 第%d卷有 %d 节，与 ctx["sections"] 的 %d 节不符' % (idx + 1, len(data), len(secs))
    assert len(secs) <= len(CN), \
        '🔴 本骨架中文大题序号只到「%s」，本卷 %d 节' % (CN[-1], len(secs))

    # ── 🔴 满分守恒闸：凡"拍平"必配守恒闸；分值这类数字最容易一处改漏 ──
    scores = [_item_scores(sec, len(data[si]), si) for si, sec in enumerate(secs)]
    full = _num(_f(lay, 'full_score', '满分'))
    if full is not None and all(s is not None for s in scores):
        tot = sum(_num(x) or 0 for s in scores for x in s)
        assert abs(tot - full) < 1e-6, \
            ('🔴 满分守恒闸不过：逐题分值合计 %s 分 ≠ 卷头满分 %s 分（按节 %s）'
             % (_g(tot), _g(full),
                '+'.join(_g(sum(_num(x) or 0 for x in s)) for s in scores)))

    cls, seal = _seal(lay) if not ans else ('', '')
    o = ['<div class="card%s">' % cls, seal,
         '<h1>%s</h1>' % (ctx.get('book_title') or '试卷')]
    if not ans:
        o.append(_head(lay, secs, ctx))

    n = 0                                     # 🔴 全卷连号计数器（跨节不重置）
    for si, sec in enumerate(secs):
        grp = data[si]
        note = _f(sec, 'score_note', '分值说明')
        o.append('<div class="sec">%s、%s%s</div>'
                 % (CN[si], sec['name'], '（%s）' % note if note else ''))

        render = R.SLOTS[sec['slot']]
        each = 0 if ans else (_f(sec, 'gap_each', '每题留白') or 0)
        # 🔴 分值印不印与守恒闸算不算是两件事：卷 3 的选择/填空只在节标题写「每小题 3 分」，
        #    逐题分值不上卷面；但 item_scores 照给，闸照算。缺省印（解答题口径）。
        show = _f(sec, 'show_item_score', '印分值')
        show = True if show is None else bool(show)
        sc = scores[si]
        parts = []
        for i, it in enumerate(grp):
            n += 1
            # 🔴 传给渲染器的是**节内**下标（答案卷圈码表只有 ①~⑩），题号随后整个换掉
            html = render(it, i % 10, ans, ctx)
            label = '%d.' % n
            if sc and show and not ans:
                label += '(%s 分)' % _g(sc[i])
            parts.append('<div class="q">%s</div>' % _renumber(html, label))

        cols = int(_f(sec, 'cols', '分栏') or 1)
        if cols > 1 and not each:
            # 🔴 一题裹一个 .q wrapper 才敢进 grid：多 div 的槽位（解方程/应用题）
            #    不裹会被拆散到两列去（dense_sections 实证过的坑）
            o.append('<div class="cols" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
                     % (cols, ''.join(parts)))
        elif each:
            o.append(''.join(p + '<div class="sp" style="height:%gmm"></div>' % each
                             for p in parts))
        else:
            o.append(''.join(parts))

        gap = 0 if ans else (_f(sec, 'gap', '节末留白') or 0)
        if gap:
            o.append('<div class="sp" style="height:%gmm"></div>' % gap)

    o.append('%s</div>' % (_watermark(ctx) if not ans else ''))
    return ''.join(o)


# ══════════════════════════════════════════════════════════════════════
# 闸
# ══════════════════════════════════════════════════════════════════════
_CARD_RE = re.compile(r'<div class="card[^"]*">(.*?)(?=<div class="card|</body>)', re.S)
_QN_TXT = re.compile(r'<span class="qn">\s*(\d+)\s*[.．]')


def guard(html, days, ctx):
    """🔴 **题号连号闸**（只在题目卷跑）。

    真卷的题号是全卷 1..N 一路排下去的，学生对答案、老师登分都按这个号走；
    题号错位是那种"印出来才发现、印了几百份"的事故。所以出件前按渲出来的 HTML
    实数一遍：每张卷的题号必须恰好是 1,2,…,N，N = 该卷各节题数之和。
    （能拒错才算闸——把 `_renumber` 摘掉、或把节内下标漏传，这条立刻红。）
    """
    cards = _CARD_RE.findall(html)
    assert len(cards) == len(days), \
        '🔴 题号连号闸：HTML 里 %d 张卷，数据里 %d 张' % (len(cards), len(days))
    for ci, seg in enumerate(cards):
        want = sum(len(g) for g in days[ci])
        got = [int(x) for x in _QN_TXT.findall(seg)]
        assert got == list(range(1, want + 1)), \
            ('🔴 第%d卷题号不连续：实得 %s…（共 %d 个），应为 1..%d'
             % (ci + 1, got[:12], len(got), want))
