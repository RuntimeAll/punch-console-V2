# -*- coding: utf-8 -*-
"""
punchkit.renderers.math —— 数学题型渲染器
=========================================
🔴 数学的硬约束：**MathJax 渲出的公式不吃外层 CSS 的 font-weight / color**（踩过两次），
   所以「这是答案」只能写进 LaTeX：`\\color{...}{...}` 或 `\\mathbf{...}`。
   科学若不走 MathJax 就没这个限制——这正是渲染器要分学科的原因之一。

槽位（骨架按名取用，骨架自己不认识这些名字的含义）：

| 槽位 | 长相 | 典型用法 |
|---|---|---|
| `oral`  | `算式 =` 一行，答案卷在等号后补着色答案 | 口算、竖式题面 |
| `expr`  | 纯算式一行，答案卷在下方挂分步链 | 脱式、简便运算 |
| `equation` | `左边 = 右边`，答案卷挂「解：x=…」逐行 | 解方程 |
| `word`  | 文字题面独占段落，答案卷挂算式行 + 答语 | 应用题 |
"""
import re

SUBJECT = '数学'
STATUS = '🟢 可用（五升六暑假每日一练 在用）'

ANSWER_COLOR = '#c0272d'

# 该学科额外需要的 CSS（骨架布局之外的追加，别覆盖骨架的 grid/flex）
CSS = """
  i { font-style: italic; font-family: "Times New Roman", serif; }
  mjx-container { margin: 0 !important; }
  .ln { padding-left: 2.2em; text-indent: -2.2em; margin-top: .6mm; }
  .ln.ind { padding-left: 3.6em; text-indent: 0; }
  .st { padding-left: 2.2em; }
  .nb { white-space: nowrap; }
"""

# 🔴 **公式后面的标点不许甩到行首**（2026-08-04 全册出到第 12 天时目检抓到）：
#    MathJax 渲出来的 `mjx-container` 是 inline-block，浏览器认为它后面可以断行，
#    于是「…看了全书的 \(5/12\)。还剩…」把句号顶到了下一行开头 —— 中文排版硬伤。
#    办法是把**公式 + 紧随其后的标点**裹进一个 nowrap，让它们只能一起走。
#    （只裹标点，不裹后面的汉字：裹多了长题面会整段推下去，留出一条大白缝。）
_GLUE = re.compile(r'(\\\(.+?\\\))([，。？！；：、）】》]+)')


def glue(text):
    return _GLUE.sub(r'<span class="nb">\1\2</span>', text)


def head(ctx=None):
    """数学要离线 MathJax。core.build_html 已统一注入，这里不重复。"""
    return ''


def answer_mark(tex):
    """🔴 着色必须进公式内部——外层 CSS 对 MathJax 无效"""
    return '\\color{%s}{%s}' % (ANSWER_COLOR, tex)


def bold(tex):
    return '\\mathbf{%s}' % tex


def M(tex):
    """行内公式"""
    return '\\(%s\\)' % tex


def _qn(i, ans, word=False, circ='①②③④⑤⑥⑦⑧⑨⑩'):
    """题号口径（2026-08-03 对照原图定，全线统一）：
       题目卷 —— 计算类**不编号**（原图裸题靠位置区分，加圈码视觉更碎）；
                 应用题保留 `1.` `2.`（原图应用题有编号）。
       答案卷 —— **全部圈码**，家长对答案要能数到第几题（按可用性来，与原图无关）。"""
    if ans:
        return '<span class="qn">%s</span>' % circ[i]
    return ('<span class="qn">%d.</span>' % (i + 1)) if word else ''


# ═══════════════ 槽位实现 ═══════════════
def oral(it, i, ans, ctx=None):
    """🔴 连接符可由题目自带的 `op` 覆盖（缺省 `=`）——「积/商的近似数」那类题
       题面必须落 `≈` 而不是 `=`（人教五上原题就这么印）。不认 op 的老册不受影响。"""
    s = '<div>%s%s' % (_qn(i, ans), M(it['stem'].h + it.get('op', '=')))
    if ans:
        s += M(answer_mark(it['lines'][-1]))
    return s + '</div>'


def _chain(first, lines):
    """原式＝…＝…：拆成多段行内公式，允许在「＝」处换行，防长链溢出页边"""
    parts = [M(first)]
    for j, ln in enumerate(lines):
        parts.append(M(answer_mark(ln)) if j == len(lines) - 1 else M(ln))
    return '＝'.join(parts)


def expr(it, i, ans, ctx=None):
    if not ans:
        return '<div>%s%s</div>' % (_qn(i, ans), M(it['stem'].h))
    return '<div class="ln">%s%s</div>' % (_qn(i, ans),
                                           _chain(it['stem'].h, it['lines']))


def equation(it, i, ans, ctx=None):
    head_ = M(it['lhs'].h + '=' + it['rhs'].h)
    if not ans:
        return '<div>%s%s</div>' % (_qn(i, ans), head_)
    out = ['<div class="ln">%s%s</div>' % (_qn(i, ans), head_)]
    for j, ln in enumerate(it['lines']):
        last = j == len(it['lines']) - 1
        out.append('<div class="ln ind">%s%s</div>'
                   % ('解：' if j == 0 else '',
                      M(answer_mark(ln)) if last else M(ln)))
    return ''.join(out)


def word(it, i, ans, ctx=None):
    """应用题。
    🔴 **答案卷不重复题面**（2026-08-03 迁库时实测）：题面动辄两三行，
       两道应用题的题面就能把答案卷从 1 页顶成 2 页；而家长手里本来就有题目卷，
       对答案只需要「第几题 → 算式 → 答语」。重复题面 = 白白多一页纸。"""
    if not ans:
        return '<div class="app">%s%s</div>' % (_qn(i, ans, word=True), glue(it['text']))
    return ('<div class="ln">%s%s</div><div class="ln ind">%s</div>'
            % (_qn(i, ans), _chain(it['lines'][0], it['lines'][1:]),
               glue(it['ansline'])))


def word_multi(it, i, ans, ctx=None):
    """应用题·**多行解答**（「解：设经过 x 小时…」→ 列方程 → 解 → 答）。

    与 `word` 的区别：`word` 是「一条 ＝ 链 + 答语」（小学低年级算术题），
    本槽位是「逐行各自成行」（含设未知数/列方程的题）。

    契约：`it['lines']` 里每个元素都是**已经渲好的最终字符串**（可含 `\\(...\\)`），
    渲染器只负责一行一个 div —— 树怎么变字符串、答案怎么着色，由册子的适配层决定。
    这样渲染器不必认识任何一本册的题库内部结构。
    """
    if not ans:
        return '<div class="app">%s%s</div>' % (_qn(i, ans, word=True), glue(it['text']))
    out = ['<div class="ln">%s%s</div>' % (_qn(i, ans), it['lines'][0])]
    out += ['<div class="ln ind">%s</div>' % ln for ln in it['lines'][1:]]
    out.append('<div class="ln ind">%s</div>' % glue(it['ansline']))
    return ''.join(out)


def fill(it, i, ans, ctx=None):
    """填空题 —— **一个空 = 一道题**，可中文与公式混排，进网格横向排布。

    🔴 与 `word_multi` 的分工（2026-08-17 加，起因：填空题挤成一大段）：
       `word_multi` 是「一道题里含若干小问」的**段落**，小问只能靠 <br> 竖着排，
       排出来又长又空；填空题真正要的是**像口算那样一格一道、横着铺、排满自动换行**。
       所以本槽位只渲一格：题面（自带括号/○ 作答位）+ 答案卷在末尾补着色答案。

    契约：`it['text']` = 已渲好的题面 HTML（可含 \\(...\\)）；
          `it['ans']`  = 已渲好的答案 HTML（答案卷用；着色由册子自己决定）。
    """
    body = glue(it['text'])
    if ans and it.get('ans'):
        body += '　' + it['ans']
    return '<div>%s%s</div>' % (_qn(i, ans), body)


def choice(it, i, ans, ctx=None):
    """选择题（2026-08-20 补实装——讲义快录后打通「出」通路）。
    契约：it['text'] = 渲好的题面 HTML（题干+选项行，可含 \\(...\\)）；
          it['ans']  = 渲好的答案 HTML，**可空**（无答案态出练习卷合法）。
    题目卷=题干+选项行；答案卷=题号+答案（不重复题面，省纸口径同 word）；
    无答案时答案卷如实印「（待补答案）」——绝不静默漏题号。"""
    if not ans:
        return '<div class="app">%s%s</div>' % (_qn(i, ans, word=True), glue(it['text']))
    return '<div class="ln">%s%s</div>' % (_qn(i, ans),
                                           glue(it.get('ans') or '（待补答案）'))


SLOTS = {'oral': oral, 'expr': expr, 'equation': equation, 'choice': choice,
         'word': word, 'word_multi': word_multi, 'fill': fill}
