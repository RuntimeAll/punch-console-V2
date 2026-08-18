# -*- coding: utf-8 -*-
"""
punchkit.renderers.preschool —— 学前 / 幼小衔接题型渲染器
==========================================================
🔴 **这一层与数学渲染器最大的不同：不走 MathJax，走「图形化空格」**。
   幼小衔接的题面本身就是图（分解树、看图列式、待填的圆圈方框），
   数字只是图里的一个格子。所以这里全部用 HTML/SVG 手绘，
   `answer_mark` 用普通 `<b class="ansv">` 即可（没有 MathJax 那条"外层 CSS 无效"的限制）。

🔴 **答案标记 = `class="ansv"`，已登记进 `core.ANSWER_ONLY_MARKS`**
   （题目卷一旦出现它，泄答案闸直接 assert 挂掉）。

槽位（骨架按名取用，骨架自己不认识这些名字的含义）：

| 槽位 | 长相 | 数据 |
|---|---|---|
| `decomp`  | 数字分解树：上一格、两条斜线、下两格，空格待填 | `{t,a,b,q}` q∈{t,a,b} 指哪一格空 |
| `piceq`   | 看图列式：两个图形框 + 大括号 + `□○□○□` 五格算式 | `{total,left,right,unknown,icon}` |
| `sign`    | 巧填符号：`9 ○ 1 ＝ 10`，圆圈里填 ＋ / － | `{a,op,b,r}` |
| `calc`    | 加减法：`2 ＋ 6 ＝ (　)`，括号里填得数 | `{a,op,b,r}` |
| `compare` | 比大小：`7 ○ 8`，圆圈里填 ＞ ＜ ＝ | `{a,b,r}` |

🔴 `<` `>` 一律写成实体（`&lt;` `&gt;`）——裸尖括号会被浏览器当标签吞掉（打卡线通用坑）。
"""

SUBJECT = '学前（幼小衔接）'
STATUS = '🟢 可用（幼小衔接数学综合练习 在用）'

ANSWER_COLOR = '#c0272d'

# ── 简笔图形库：描边风格（fill:none），黑白打印清晰，孩子还能自己涂色 ──────────
# viewBox 统一 0 0 40 40，由 CSS 的 .ic 控制显示尺寸。
_ICON_PATHS = {
    'apple':   '<path d="M20 14c-7 0-12 5-12 12 0 6 5 10 12 10s12-4 12-10c0-7-5-12-12-12z"/>'
               '<path d="M20 14V8"/><path d="M20 10c3-4 8-4 10-2-2 4-7 5-10 2z"/>',
    'fish':    '<path d="M6 20c5-7 13-9 20-6 4 2 6 4 8 6-2 2-4 4-8 6-7 3-15 1-20-6z"/>'
               '<path d="M34 20l5-5v10l-5-5z"/><circle cx="13" cy="18" r="1.6"/>',
    'star':    '<path d="M20 5l4.6 9.8 10.4 1.5-7.6 7.6 1.9 10.7L20 29.5 10.7 34.6l1.9-10.7'
               'L5 16.3l10.4-1.5L20 5z"/>',
    'heart':   '<path d="M20 34S6 25 6 16.5C6 11.8 9.8 8 14.5 8c2.6 0 4.6 1.2 5.5 2.8'
               'C20.9 9.2 22.9 8 25.5 8 30.2 8 34 11.8 34 16.5 34 25 20 34 20 34z"/>',
    'flower':  '<circle cx="20" cy="11" r="5.4"/><circle cx="20" cy="29" r="5.4"/>'
               '<circle cx="11" cy="20" r="5.4"/><circle cx="29" cy="20" r="5.4"/>'
               '<circle cx="20" cy="20" r="4"/>',
    'balloon': '<ellipse cx="20" cy="16" rx="10" ry="12"/><path d="M20 28v8"/>'
               '<path d="M17 36h6"/>',
    'leaf':    '<path d="M8 32C8 18 18 8 32 8c0 14-10 24-24 24z"/><path d="M32 8L14 26"/>',
    'cup':     '<path d="M10 12h20l-2.5 22h-15L10 12z"/><path d="M30 16h4a3 3 0 010 8h-4"/>',
}
ICON_KEYS = tuple(_ICON_PATHS)

CSS = """
  /* ══════ 通用格子 ══════ */
  .pc { display:inline-flex; align-items:center; justify-content:center;
        border:.9pt solid #000; width:__CW__mm; height:__CH__mm;
        font-family:"SimHei",sans-serif; font-size:1.32em; line-height:1;
        vertical-align:middle; }
  .ansv { color:__RED__; font-family:"SimHei",sans-serif; font-weight:normal; }

  /* ══════ 一、数字分解树 ══════ */
  .dq  { display:flex; flex-direction:column; align-items:center; }
  .dfk { width:__DW__mm; height:5.6mm; display:block; }
  .dfk line { stroke:#000; stroke-width:1.4; vector-effect:non-scaling-stroke; }
  .dbt { display:flex; gap:__DG__mm; }

  /* ══════ 二、看图列式 ══════ */
  .pq   { display:flex; flex-direction:column; align-items:center; width:100%; }
  .prow { display:flex; gap:2.2mm; width:100%; justify-content:center; }
  .pbx  { border:.9pt solid #000; border-radius:2.4mm; flex:1; min-height:__PH__mm;
          display:flex; flex-wrap:nowrap; align-items:center; justify-content:center;
          gap:.6mm; padding:.8mm; }
  .pbx.qm { font-family:"SimHei",sans-serif; font-size:1.6em; }
  .ic   { width:__IW__mm; height:__IW__mm; display:block; flex:none; }
  /* 🔴 描边偏粗（2.6）——幼儿册的图要在 A4 上一眼看清，细线打印出来发虚 */
  .ic path, .ic circle, .ic ellipse { fill:none; stroke:#000; stroke-width:2.6;
          stroke-linejoin:round; stroke-linecap:round; }
  /* 大括号：两端上翘、中间下垂并收出一个尖角指向总数 —— 光一条扁弧会被误读成框的下边线 */
  .pbr  { width:100%; height:5.2mm; display:block; margin-top:.5mm; }
  .pbr path { fill:none; stroke:#000; stroke-width:1.5; vector-effect:non-scaling-stroke; }
  .ptt  { font-family:"SimHei",sans-serif; font-size:1.3em; line-height:1;
          margin:.2mm 0 .4mm; }
  .peq  { display:flex; align-items:center; gap:1.6mm; }

  /* ══════ 三/五、圆圈；四、括号 ══════ */
  .lq  { font-family:"SimHei",sans-serif; font-size:1.24em; line-height:1;
         display:flex; align-items:center; justify-content:center; gap:1.5mm;
         white-space:nowrap; }
  .cir { display:inline-flex; align-items:center; justify-content:center;
         border:.9pt solid #000; border-radius:50%;
         width:__RW__mm; height:__RW__mm; font-size:.92em; }
  .brk { white-space:nowrap; }
  .par { display:inline-block; min-width:__PW__mm; text-align:center; }
"""


def css(vars_=None):
    """骨架调它拿本学科 CSS。vars_ 可覆盖尺寸旋钮（单位 mm）。"""
    v = dict(CW=9.2, CH=7.0, DW=26.0, DG=6.0, PH=13.5, IW=9.0, RW=7.0, PW=8.5)
    v.update(vars_ or {})
    out = CSS.replace('__RED__', ANSWER_COLOR)
    for k, val in v.items():
        out = out.replace('__%s__' % k, '%g' % val)
    return out


def head(ctx=None):
    """学前不用 MathJax（core 仍会注入，无害）。"""
    return ''


def answer_mark(html):
    """🔴 这个标记进了 core.ANSWER_ONLY_MARKS —— 题目卷出现它即判泄答案"""
    return '<b class="ansv">%s</b>' % html


def bold(html):
    return '<b>%s</b>' % html


def icon(key, n):
    """n 个同款简笔图形"""
    p = _ICON_PATHS.get(key) or _ICON_PATHS['apple']
    one = '<svg class="ic" viewBox="0 0 40 40">%s</svg>' % p
    return one * n


def _cell(val, blank, ans):
    """一个方格：blank=True 表示这格要学生填（题目卷留空，答案卷出红字）"""
    if not blank:
        return '<span class="pc">%s</span>' % val
    return '<span class="pc">%s</span>' % (answer_mark(val) if ans else '')


def _circ(val, ans):
    """一个待填圆圈"""
    return '<span class="cir">%s</span>' % (answer_mark(val) if ans else '')


# 🔴 裸尖括号会被浏览器当标签吞掉 —— 比大小的 < > 一律走实体
_ENT = {'<': '&lt;', '>': '&gt;', '=': '＝'}


def esc(sym):
    return _ENT.get(sym, sym)


# ═══════════════ 槽位实现 ═══════════════
def decomp(it, i, ans, ctx=None):
    """一、数字分解：上一格 + 两条斜线 + 下两格，q 指的那一格空着"""
    q = it['q']
    return ('<div class="dq">'
            '<div>%s</div>'
            '<svg class="dfk" viewBox="0 0 100 22" preserveAspectRatio="none">'
            '<line x1="50" y1="1" x2="15" y2="21"/><line x1="50" y1="1" x2="85" y2="21"/>'
            '</svg>'
            '<div class="dbt">%s%s</div></div>'
            % (_cell(it['t'], q == 't', ans),
               _cell(it['a'], q == 'a', ans),
               _cell(it['b'], q == 'b', ans)))


def piceq(it, i, ans, ctx=None):
    """二、看图列式：两个图形框 + 大括号 + 总数 + `□○□○□` 五格算式

    unknown='total' → 右框画图、总数是 ?，列加法 left＋right＝total
    unknown='right' → 右框是 ?、总数已知，列减法 total－left＝right
    """
    unk_total = it['unknown'] == 'total'
    ic = it['icon']
    right_box = ('<div class="pbx qm">？</div>' if not unk_total
                 else '<div class="pbx">%s</div>' % icon(ic, it['right']))
    total_txt = ('？' if unk_total else str(it['total']))

    if unk_total:
        cells = [it['left'], '＋', it['right'], '＝', it['total']]
    else:
        cells = [it['total'], '－', it['left'], '＝', it['right']]

    eq = ''.join(
        (_circ(esc(v), ans) if j in (1, 3) else _cell(v, True, ans))
        for j, v in enumerate(cells))

    return ('<div class="pq">'
            '<div class="prow"><div class="pbx">%s</div>%s</div>'
            '<svg class="pbr" viewBox="0 0 200 20" preserveAspectRatio="none">'
            '<path d="M3 1 Q3 11 95 11 L100 19 L105 11 Q197 11 197 1"/></svg>'
            '<div class="ptt">%s</div>'
            '<div class="peq">%s</div></div>'
            % (icon(ic, it['left']), right_box, total_txt, eq))


def sign(it, i, ans, ctx=None):
    """三、巧填符号：`9 ○ 1 ＝ 10`

    🔴 每个元素独立成 span、**不夹 `&nbsp;`** —— `.lq` 是 flex，间距一律交给 `gap`。
       混用（既有 nbsp 又有 gap）会让同一行出现两种宽度的缝，四列排版直接顶破版心。
    """
    return ('<div class="lq"><span>%d</span>%s<span>%d</span>'
            '<span>＝</span><span>%d</span></div>'
            % (it['a'], _circ('＋' if it['op'] == '+' else '－', ans), it['b'], it['r']))


def calc(it, i, ans, ctx=None):
    """四、加减法：`2 ＋ 6 ＝ (　)`"""
    return ('<div class="lq"><span>%d</span><span>%s</span><span>%d</span>'
            '<span>＝</span><span class="brk">(<span class="par">%s</span>)</span></div>'
            % (it['a'], '＋' if it['op'] == '+' else '－', it['b'],
               answer_mark(it['r']) if ans else ''))


def compare(it, i, ans, ctx=None):
    """五、比大小：`7 ○ 8`"""
    return ('<div class="lq"><span>%d</span>%s<span>%d</span></div>'
            % (it['a'], _circ(esc(it['r']), ans), it['b']))


SLOTS = {'decomp': decomp, 'piceq': piceq, 'sign': sign,
         'calc': calc, 'compare': compare}
