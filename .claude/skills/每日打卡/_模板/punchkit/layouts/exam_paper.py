# -*- coding: utf-8 -*-
"""
骨架 `exam_paper` —— A4 真实试卷版式（单元测试卷 / 期中期末卷 / 专项卷）
=====================================================================
对标件 = `测试数据/七上试卷/卷3/`（4 张拍照卷面，七年级数学上册单元测试卷·第1章有理数）。
逐条照着卷面长的，别自己改：

  1. **卷头三行**：居中大标题（26pt 黑体）→ 居中副标题「第1章 有理数」→
     居中副标行「（满分：120 分　考试时间：120 分钟）」。三行之后才是可选的
     姓名行 / 「题号—得分」评分表。
  2. **大题节标题带分值**：`一、选择题(每小题 3 分，共 33 分)` —— 黑体、左顶格、
     **半角括号**（卷面原样）、与正文同一行距无额外留白、
     `page-break-after:avoid`（节标题绝不许落在页底当孤儿）。
  3. 🔴 **题号全卷连号**：卷 3 的题号是 1→24 一路排下去**跨节不重置**（选择 1~11、
     填空 12~15、解答 16~24）。渲染器只知道"节内第几题"，所以本骨架**自己打题号**：
     渲完再把 `<span class="qn">` 换成全卷连号；渲染器没打题号的槽位（expr/oral/fill
     的题目卷）则补一个进去 —— 试卷上**每道题都必须有号**。
     副作用（好的那种）：不再吃渲染器答案卷 `①~⑩` 圈码的 10 题上限。
  4. **解答题题号带分值**：`16.(6 分)` —— 卷面原样。由 `sections[i]['item_scores']` 驱动。
  5. 🔴 **一卷一个行距**：卷 3 拍照件实测 —— 正文 em ≈ 3.95mm（11.2pt）、行距 ≈ 8.27mm，
     **行距/em = 2.08，且题内行、题间行、选项行、节标题行全是这一个值**（题间没有额外
     margin，作答留白一律靠 `gap_each` 明码标价）。所以 `.q` 不带 margin、选项表不带
     cell padding —— 排稀排紧都由 `gap_each` 一个旋钮说了算。
  6. **缩进只有一级 = 1em**（实测：题号左顶格，续行/选项行/小问行一律缩进恰好 1 个字，
     跟题号宽度无关）。所以 `.q > div` 是 `padding-left:1em; text-indent:-1em`，
     并把渲染器选项表自带的 `margin-left:1.2em` 归零（否则缩成 2.2em，且撑破版心）。
  7. 🔴 **防缩页闸**（2026-08-20 卷 3 复刻实伤）：Chrome 打印一旦发现横向溢出，会把
     **整卷等比缩印**——实测缩到 79%：11.5pt 印成 9pt、页边距全失真，而退出码还是 0。
     两条溢出源在本骨架收口：① 选项表 `width:100%` + `margin-left:1.2em` 必溢出 1.2em；
     ② 渲染器 `glue()` 的回溯 bug 会把整句话裹进 `.nb`(nowrap)，一裹就是半页宽。
     见 `_unnb()` 与 CSS 的「防缩页」段；`guard()` 里有对应的闸，摘掉立刻红。
  8. **一卷 = 一张卡，内容自然流到多页**：所以页边距走 `@page margin`（每页都有），
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
            '可选姓名行 / 「题号—得分」评分表 / 左侧装订密封线（字段列带填写横线 + '
            '「密封线」竖列 + 竖虚线，一律竖排自下而上读，同真卷）；'
            '黑体大题节标题带分值「一、选择题(每小题 3 分，共 33 分)」；'
            '🔴 题号**全卷连号**、解答题题号带分值「16.(6 分)」；'
            '全卷一个行距 2.08em、缩进只有 1em 一级，一卷多页连排',
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
            'seal_fields 密封线字段(缺省 学校/班级/姓名/学号)｜seal_text 密封线三字(缺省「密封线」)｜'
            'head_note 副标行后小字；'
            'sections[i]：score_note 节标题分值说明｜item_scores 逐题分值(数组或单数)｜'
            'show_item_score 题号后印不印分值(缺省 true)｜'
            'gap_each 每题后留白mm｜gap 节末留白mm｜cols 节内分栏数；'
            '🔴 一比一复刻卷 3 的推荐值：body_pt 11.2',
    '闸': '满分守恒闸（逐题分值合计 == 卷头满分）｜item_scores 数量闸｜'
          '题号连号闸（guard）｜防缩页闸（guard：超长 nowrap 片段一个不许留）',
}

CN = '一二三四五六七八九十'
# 🔴 下面四个数是**量出来的不是拍的**（2026-08-20 卷 3 四张拍照件像素反推，量法：
#    黑体节标题「三、解答题(共 75 分)」= 10 em 宽 239px ⇒ em = 24.0px；页宽 1280px = 210mm
#    ⇒ 6.095 px/mm ⇒ em = 3.95mm = 11.2pt；正文左 63px / 右 1218px ⇒ 左右页边各 10.2mm）。
DEFAULT_PT = 11.2
LINE_H = 2.08                    # 行距/em，实测行距 50.4px = 8.27mm ÷ 3.95mm
HANG_EM = 1.0                    # 悬挂缩进：实测续行/选项行一律缩进 26px ≈ 1 em
MARGIN_TOP, MARGIN_BOTTOM = 13.0, 12.0
BODY_X_MM = 10.0                 # 正文左右页边（卷 3 实测 10.2mm）
# 🔴 密封线要探到距页左 4.5mm —— 比正文页边还靠外。Chrome 打印会把 position:fixed
#    **裁在 @page 版心边上**（实测：left:-5.5mm 那一段直接不印），所以只能反过来：
#    @page 边距先退到 4.5mm 给密封线腾地方，正文再用 .card 的左右 padding 补回 5.5mm
#    （🔴 横向 padding 每页都算数，只有纵向 padding 才是"只作用在首末页"的那个坑）。
MARGIN_X = 4.5                   # @page 左右边距 = 密封线最外一列的落点
CARD_PAD_MM = BODY_X_MM - MARGIN_X          # 5.5mm，.card 左右各补这么多
SEAL_GUTTER_MM = 10.5            # 开装订线时正文额外让出的左侧走廊（卷 3 实测 10.3mm）
SEAL_PAD_MM = CARD_PAD_MM + SEAL_GUTTER_MM  # 16mm = 密封线页 .card 的 padding-left

CSS = """
  @page { size: A4; margin: __MT__mm __MX__mm __MB__mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: __LH__; color: #000; }

  /* 一卷 = 一张卡；卡内容自然流到多页，卡与卡之间强制分页。
     左右 padding 把 @page 让给密封线的那 5.5mm 补回来（横向 padding 每页都在）。 */
  .card { page-break-after: always; padding: 0 __CPAD__mm; }
  .card:last-child { page-break-after: auto; }
  /* 末尾那块作答留白别自己顶出一张空白页（卷 3 复刻实伤：题目卷白白多印一页） */
  .card > .sp:last-child { display: none; }

  /* ═══ 卷头 ═══
     行间距实测（拍照件 ink-to-ink）：大标题↔副标题 42px、副标题↔满分行 31px、
     满分行↔评分表 14px、评分表↔节标题 14px —— 后三段全等于纯行距，
     也就是说卷头除大标题外**不带任何额外 margin**。 */
  h1 { font-family: "SimHei", sans-serif; font-size: __H1__pt; line-height: 1.28;
       text-align: center; letter-spacing: .04em; margin: 0 0 2.4mm; }
  .sub { font-family: "SimHei", sans-serif; font-size: __H2__pt; text-align: center;
         margin: 0; }
  .meta { text-align: center; margin: 0; }
  .hnote { text-align: center; font-size: .92em; margin: 0; }

  .names { margin: 0 0 2.6mm; }
  .names em { font-style: normal; margin-right: 8mm; }
  .names em:last-child { margin-right: 0; }
  .names i { display: inline-block; width: 26mm; border-bottom: .3mm solid #000;
             font-style: normal; }

  /* 「题号 / 一 / 二 / 三 / 总分」评分表 —— 卷 3 卷头原样（实测行高 8.4mm、五列等分） */
  .stab { width: 100%; border-collapse: collapse; table-layout: fixed;
          text-align: center; margin: 0; }
  .stab td { border: .3mm solid #000; height: 8.4mm; }
  .stab td.k { width: 20%; }

  /* ═══ 大题节标题 ═══ 与正文同一行距、无额外上下留白（实测：节标题前后都恰好一行） */
  .sec { font-family: "SimHei", sans-serif; margin: 0;
         page-break-after: avoid; break-after: avoid; }

  /* ═══ 题 ═══ 题间不留 margin：留白一律走 gap_each，排稀排紧只有一个旋钮 */
  .q { margin: 0; break-inside: avoid; page-break-inside: avoid; }
  .q > div { padding-left: __HANG__em; text-indent: -__HANG__em; }
  .qn { font-family: "SimHei", sans-serif; margin-right: .1em; }
  .sp { }
  .cols { display: grid; column-gap: 6mm; }

  /* ═══ 🔴 防缩页 + 选项块归位 ═══
     渲染器选项网格 = `<table style="width:100%;…;margin:2pt 0 0 1.2em">`（无 class，
     数据表是 `table.tbl`，两者用 :not(.tbl) 分开）。`width:100%` 已经占满题面净宽，
     再叠 1.2em 左边距必然向右溢出 1.2em ⇒ Chrome 打印整卷等比缩印。
     这里把边距归零：既堵死溢出，又让选项行正好落在 1em 缩进上（= 卷面实测位）。
     cell 的 1pt 上下 padding 同理归零 —— 卷面上选项行与题面行是同一个行距。 */
  .q table:not(.tbl) { margin: 0 !important; text-indent: 0; }
  .q table:not(.tbl) td { padding-top: 0 !important; padding-bottom: 0 !important; }

  /* ═══ 左侧装订密封线（可选）═══
     🔴 一卷多页 ⇒ 只能用 position:fixed（Chrome 打印时每页重绘一次）；
     absolute 只会印在第一页上。position:fixed 的 left:0 = **版心左边**
     （@page margin 之内），所以走廊宽度就等于 .card 让出的那一条。
     竖排一律「自下而上读」（原卷：从下往上是 学校__班级__姓名__学号__ / 密封线），
     用 rotate(-90deg) 而不是 writing-mode —— writing-mode 只能自上而下读，反了。 */
  .card.sealed { padding-left: __SEALPAD__mm; }
  .sealbar { position: fixed; left: 0; top: 0; bottom: 0; width: __SEAL__mm; }
  .sealbar .col { position: absolute; top: 0; bottom: 0;
                  display: flex; align-items: center; justify-content: center; }
  .sealbar .col > span { white-space: nowrap; transform: rotate(-90deg);
                         font-size: .95em; }
  .sealbar .f { left: 0; width: 4.5mm; }
  .sealbar .m { left: 8.9mm; width: 5mm; }
  /* 「密」「封」「线」三字要撒满整页高：实测字心间距 44mm（≈10.4em）。
     letter-spacing 会在末字后面也留一格 ⇒ 补等量 padding-left 才居得正。 */
  .sealbar .m > span { letter-spacing: 10.4em; padding-left: 10.4em; }
  /* 填写横线实测 30~36mm，字心间距 52mm */
  .sealbar .f i { display: inline-block; width: 36mm; border-bottom: .3mm solid #000;
                  font-style: normal; margin: 0 3mm; }
  /* 「密封线」三个字**骑在虚线上**（原卷原样），所以虚线落在 .m 列中线 */
  .sealbar .dash { position: absolute; left: 11.4mm; top: 0; bottom: 0;
                   border-left: .3mm dashed #000; }

  .wm { position: fixed; right: __CPAD__mm; bottom: 0;
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


# ── 🔴 防缩页闸：超长 nowrap 片段 ────────────────────────────────────────
# 渲染器 `glue()` 的本意是「公式 + 紧跟的标点」不许拆行，正则是
#   (\\\(.+?\\\))([，。？！；：、）】》]+)
# `.+?` 惰性没错，但**正则会回溯**：第一个 `\)` 后面不是标点它就继续往后找，
# 一直找到「某个 `\)` 恰好后面跟标点」为止 —— 于是从句首第一个公式一路裹到句中，
# 整句话被塞进一个 nowrap。卷 3 第 19 题实测裹了 217px（版心 40%），
# Chrome 打印判定横向溢出 ⇒ **整卷缩到 79%**：11.5pt 印成 9pt，退出码还是 0。
# 根治在渲染器（把 `.+?` 换成不跨 `\)` 的字符类），本骨架先在版式层拆包自保。
# 🔴 别拿 `[^<]*?` 图省事：裹错的那一段里就有 `<br>`（小问换行），一个字符类全漏。
#    这里按 `<span>/</span>` 计数配平，嵌套也认得准。
_NB_OPEN = '<span class="nb">'
NB_LIMIT_EM = 20.0                       # 一个不许拆行的整体，宽过 20 个字必是裹错了
_TEX = re.compile(r'\\[a-zA-Z]+\s?|[\\{}$^_]')
_TAG = re.compile(r'<[^>]*>')


def _vis_em(s):
    """估算一段 HTML 渲出来多宽（em）：去标签、去 LaTeX 控制序列，CJK 记 1，其余记 0.5。"""
    t = _TEX.sub('', _TAG.sub('', s))
    return sum(1.0 if (u'\u2e80' <= c <= u'\u9fff' or u'\uff00' <= c <= u'\uffef')
               else 0.5 for c in t)


def _iter_nb(html):
    """产出 (开始, 结束, 内文)：`<span class="nb">…</span>` 的配平切片。"""
    i = 0
    while True:
        s = html.find(_NB_OPEN, i)
        if s < 0:
            return
        j, depth = s + len(_NB_OPEN), 1
        while depth:
            a, b = html.find('<span', j), html.find('</span>', j)
            if b < 0:                        # HTML 不配平就别猜，原样交出去
                return
            if 0 <= a < b:
                depth, j = depth + 1, a + 5
            else:
                depth, j = depth - 1, b + 7
        yield s, j, html[s + len(_NB_OPEN):j - 7]
        i = j


def _long_nb(html):
    """返回所有「宽过 NB_LIMIT_EM」的 nb 片段（闸与拆包共用同一把尺）。"""
    return [t for _, _, t in _iter_nb(html) if _vis_em(t) > NB_LIMIT_EM]


def _unnb(html):
    """拆掉裹错的超长 nowrap 外壳，内容一个字不动。"""
    out, at = [], 0
    for s, e, t in _iter_nb(html):
        if _vis_em(t) > NB_LIMIT_EM:
            out.append(html[at:s]); out.append(t); at = e
    out.append(html[at:])
    return ''.join(out)


# ── 大题名去重号 ────────────────────────────────────────────────────────
# 本骨架自己打「一、」，组卷侧给的 name 有时已经带了（`一、选择题`），
# 直接拼会印成「一、一、选择题」（2026-08-20 _fkpack_卷3 实拍）。这里剥掉再拼。
_SEC_ORD = re.compile(r'^\s*[一二三四五六七八九十]+\s*[、．.]\s*')


def _sec_name(name):
    return _SEC_ORD.sub('', name or '')


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
    # 大标题 26pt：实测「七年级数学上册单元测试卷」12 字 ink 宽 670px ⇒ em 56.3px
    # = 9.24mm = 26.2pt（副标题同法 ≈ 15pt，取 15.5 与正文 11.2 成比例）。
    return (CSS.replace('__H1__', '%.2f' % (26.0 * k))
               .replace('__H2__', '%.2f' % (15.5 * k))
               .replace('__PT__', '%.2f' % pt)
               .replace('__LH__', '%g' % LINE_H)
               .replace('__HANG__', '%g' % HANG_EM)
               .replace('__MT__', '%g' % MARGIN_TOP)
               .replace('__MX__', '%g' % MARGIN_X)
               .replace('__MB__', '%g' % MARGIN_BOTTOM)
               .replace('__CPAD__', '%g' % CARD_PAD_MM)
               .replace('__SEALPAD__', '%g' % SEAL_PAD_MM)
               .replace('__SEAL__', '%g' % (SEAL_GUTTER_MM + CARD_PAD_MM))) + _default.CSS


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


_SEAL_FIELDS = ('学校', '班级', '姓名', '学号')


def _seal(lay):
    """左侧装订密封线 = 字段列（每项后带填写横线）+「密封线」竖列 + 竖虚线。

    卷 3 实测（距页左，mm）：字段列 4.9~9.8｜「密封线」列 13.1~15.5｜虚线 15.7｜
    正文起 20.5 —— 三样东西全在 10.3mm 宽的走廊里，自下而上读。
    """
    if not _f(lay, 'seal_line', '密封线'):
        return '', ''
    fields = _f(lay, 'seal_fields', '密封线字段') or _SEAL_FIELDS
    txt = _f(lay, 'seal_text', '密封线文字') or '密封线'
    return (' sealed',
            '<div class="sealbar">'
            '<div class="col f"><span>%s</span></div>'
            '<div class="col m"><span>%s</span></div>'
            '<div class="dash"></div></div>'
            % (''.join('%s<i></i>' % f for f in fields), txt))


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
        # 🔴 括号用**半角**：卷面原样是「一、选择题(每小题 3 分，共 33 分)」，
        #    与解答题题号的「16.(6 分)」同一副括号，全角会宽出两个字位。
        o.append('<div class="sec">%s、%s%s</div>'
                 % (CN[si], _sec_name(sec['name']), '(%s)' % note if note else ''))

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
            html = _unnb(render(it, i % 10, ans, ctx))   # 🔴 防缩页闸：先拆超长 nowrap
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
    """🔴 **题号连号闸 + 防缩页闸**（只在题目卷跑）。

    真卷的题号是全卷 1..N 一路排下去的，学生对答案、老师登分都按这个号走；
    题号错位是那种"印出来才发现、印了几百份"的事故。所以出件前按渲出来的 HTML
    实数一遍：每张卷的题号必须恰好是 1,2,…,N，N = 该卷各节题数之和。
    （能拒错才算闸——把 `_renumber` 摘掉、或把节内下标漏传，这条立刻红。）

    防缩页闸：整份 HTML 里不许剩下宽过 NB_LIMIT_EM 的 nowrap 片段。这类片段会把
    版心撑破，Chrome 打印**不报错、只把整卷等比缩印**（卷 3 实测 79%：11.5pt 印成 9pt）——
    出件前拒得掉，比印出来才发现便宜。（把 `_unnb` 摘掉，这条立刻红。）
    """
    bad = _long_nb(html)
    assert not bad, \
        ('🔴 防缩页闸不过：还剩 %d 段超长 nowrap（宽过 %g 字），Chrome 会把整卷缩印。'
         '首段：%s…' % (len(bad), NB_LIMIT_EM, bad[0][:60]))
    cards = _CARD_RE.findall(html)
    assert len(cards) == len(days), \
        '🔴 题号连号闸：HTML 里 %d 张卷，数据里 %d 张' % (len(cards), len(days))
    for ci, seg in enumerate(cards):
        want = sum(len(g) for g in days[ci])
        got = [int(x) for x in _QN_TXT.findall(seg)]
        assert got == list(range(1, want + 1)), \
            ('🔴 第%d卷题号不连续：实得 %s…（共 %d 个），应为 1..%d'
             % (ci + 1, got[:12], len(got), want))
