# -*- coding: utf-8 -*-
"""
骨架 `two_col_spread` —— 两列平摊开 · 一列一节 · 一天一页
=========================================================
首用 = 七上有理数与实数计算打卡（2026-08-10），页型照实体教辅拍照页复刻。

长相来源（用户给的教辅原页）：粗细双横线压在标题下 · 左右两列各排若干题 ·
题号加粗带点 · 每题下方等高大留白 · 题与题之间浅虚线分隔。

好用在哪：
  1. **一页塞得下 8 道过程题** —— 单列排 8 题每题只剩 28mm 写不开，两列一变 55mm，
     混合运算的四五行过程正好落得下。`flat_spread`（单列 5 题）与
     `dense_sections`（单列节末留白）都覆盖不到这个题量区间。
  2. **一列一节 = 两个专项天然对照** —— 左列「有理数混合运算」右列「实数计算」，
     不用横向节标题去切页面，视觉上就是两张并排的小卷。
  3. **题号列内自增** —— CSS counter 出题号，与答案卷 `_qn` 的节内圈码一一对上
     （连续编号 1..8 会与答案卷的 ①..④ 对不上，这是踩过的错位）。

🔴 **学科无关**：科学挂 `renderers.get('science')` 直接能用。

🔴 **带一道版面宽度闸**（`guard`）：MathJax 行内公式**不换行**，列宽只有 ~84mm，
   长算式会**横向溢出到列外**——而页数断言查不出来（页数照样对）。
   闸按字符估宽，超阈值即 FAIL，逼你在 days 里换个短点的参数。
"""
from .. import core

SPEC = {
    'key': 'two_col_spread',
    'name': '两列平摊开',
    '学科': '通用',
    '长相': '黑体大标题 + 「—— 第N天 ——」副标题 + **粗细双横线**；姓名/日期/用时信息栏；'
            '左右两列各一节（黑体节标题）；题号加粗带点；每题**等高大留白**；'
            '题间浅虚线分隔；右下角水印可拔插',
    '适合': '🔴 **一页 6~10 道过程题**的册子：混合运算、实数计算、化简求值这类'
            '「题面一行、过程四五行」的专项。题量卡在 flat_spread(5题) 与 '
            'dense_sections(单列节末留白) 中间的那一档',
    '每页': '1 天',
    '槽位': '由 ctx["sections"] 逐列指定（**一节 = 一列**），任意组合；'
            '推荐 expr（算式一行 + 答案卷挂分步链）',
    '旋钮': 'sections[].name=列标题｜sections[].ans_cols=答案卷该节压成几列｜'
            'title/subtitle｜show_info=信息栏｜watermark=None 可移除｜'
            'max_w=版面宽度闸阈值(缺省 46 全角字符)｜dash=题间虚线(缺省 True)',
    '数据形状': 'days = [day, ...]；day = [第1列items, 第2列items, ...]，'
                '与 ctx["sections"] 等长（**与 dense_sections / boxed_sections 同契约**）',
    '用过的册': '七上有理数与实数计算打卡（原生）',
}

CSS = """
  @page { size: A4; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.5; color: #000; }

  .card { width: 190mm; height: 272mm; margin: 0 auto; padding: 10mm 7mm 6mm;
          position: relative; display: flex; flex-direction: column;
          page-break-after: always; }
  .card:last-child { page-break-after: auto; }

  h1 { font-family: "SimHei", sans-serif; font-size: __H1__pt; text-align: center;
       letter-spacing: .06em; margin: 0; }
  .sub { text-align: center; font-family: "SimHei", sans-serif;
         font-size: __SUB__pt; letter-spacing: .35em; margin: 1.6mm 0 0; }
  /* 🔴 粗细双横线 —— 教辅原页的招牌，上粗下细，中间留 .8mm */
  .rule { border-top: .75mm solid #000; border-bottom: .22mm solid #000;
          height: 1.1mm; margin: 2.2mm 0 0; }

  .info { text-align: center; font-size: __INFO__pt; margin: 2.4mm 0 1mm; }
  .info span { display: inline-block; width: 24mm; border-bottom: .3mm solid #000;
               margin: 0 1mm; }

  /* ══ 两列主体：撑满剩余高度，列内每题等高 ══ */
  .cols { flex: 1; display: grid; grid-template-columns: repeat(__NC__, 1fr);
          column-gap: __GAP__mm; min-height: 0; }
  .col { display: flex; flex-direction: column; counter-reset: q; min-width: 0; }
  .sec { font-family: "SimHei", sans-serif; font-size: 1em;
         margin: 0 0 1.5mm; padding-bottom: 1mm; }

  /* 每题一格，flex:1 均分列内剩余空间 = 留白自动最大化 */
  .q { flex: 1; min-height: 0; padding-top: 1.2mm;
       border-bottom: .25mm dashed #b9b9b9; }
  .q:last-child { border-bottom: none; }
  .q.nodash { border-bottom: none; }
  /* 🔴 题号走 CSS counter：**列内自增**，与答案卷 `_qn` 的节内圈码对得上 */
  .q > div:first-child::before { counter-increment: q;
       content: counter(q) ". "; font-family: "SimHei", sans-serif; }

  .wm { position: absolute; right: 7mm; bottom: 4mm;
        font-family: "SimHei", sans-serif; font-size: 12pt; color: #6b6b6b; }
  .wm img { height: 14pt; vertical-align: -3pt; margin-right: 1mm; }

  /* ══ 答案卷：单列紧排、无留白、允许一天多页 ══ */
  body.asheet .card { height: auto; padding-bottom: 10mm; }
  body.asheet .cols { display: block; }
  body.asheet .col { display: block; margin-bottom: 3mm; }
  body.asheet .sec { margin: 3mm 0 1.5mm; }
  body.asheet .q { border-bottom: none; padding-top: 0; margin-bottom: 1.8mm; }
  /* 答案卷题号由渲染器的圈码出，关掉 counter 免得双重编号 */
  body.asheet .q > div:first-child::before { content: none; counter-increment: none; }
  .ac { display: grid; column-gap: 5mm; }
"""

CN = '一二三四五六七八九十'

# 版面宽度闸：列宽 ~84mm，12pt 下一个全角字符 ≈ 4.2mm ⇒ 约 20 全角。
# LaTeX 源码里 \frac{}{} 之类控制序列不占宽，故按「去掉控制序列后的可见字符数」估。
DEFAULT_MAX_W = 46


def css(pt=None):
    pt = float(pt or 12.0)
    k = pt / 12.0
    from ..renderers import math as _default
    return (CSS.replace('__H1__', '%.2f' % (19.0 * k))
               .replace('__SUB__', '%.2f' % (11.5 * k))
               .replace('__INFO__', '%.2f' % (10.5 * k))
               .replace('__PT__', '%.2f' % pt)
               .replace('__NC__', '%d' % css.ncols)
               .replace('__GAP__', '%g' % css.gap)) + _default.CSS


css.ncols = 2          # 由 render_card 首次调用时按 ctx 覆盖（见 configure）
css.gap = 7.0


def configure(ctx):
    """列数与列间距是 CSS 里的常量，出卷前按 ctx 定一次。"""
    css.ncols = len(ctx['sections'])
    css.gap = float(ctx.get('col_gap', 7.0))


def _wm(ctx):
    w = ctx.get('watermark')
    if not w:
        return ''
    text, img = (w.get('text', ''), w.get('img', True)) if isinstance(w, dict) else (w, True)
    return '<div class="wm">%s%s</div>' % (core.watermark_img() if img else '', text)


def render_card(idx, data, ans, ctx):
    """
    idx  第几天（0 起）
    data 该天数据 = [第1列items, 第2列items, ...]，与 ctx['sections'] 等长
    ctx  {'sections':[{'name','slot','ans_cols'}], 'title', 'subtitle', 'renderer', ...}
    """
    R = ctx['renderer']
    secs = ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 列，与 ctx["sections"] 的 %d 列不符' % (idx + 1, len(data), len(secs))

    day_cn = CN[idx] if idx < len(CN) else str(idx + 1)
    o = ['<div class="card">',
         '<h1>%s</h1>' % ctx.get('title', ''),
         '<div class="sub">—— 第 %s 天 %s——</div>'
         % (day_cn, '（答案） ' if ans else ''),
         '<div class="rule"></div>']
    if not ans and ctx.get('show_info', True):
        o.append('<div class="info">姓名：<span></span>　日期：<span></span>　'
                 '用时：<span></span></div>')

    o.append('<div class="cols">')
    for si, sec in enumerate(secs):
        grp = data[si]
        o.append('<div class="col">')
        o.append('<div class="sec">%s、%s</div>' % (CN[si], sec['name']))
        render = R.SLOTS[sec['slot']]
        parts = [render(it, i, ans, ctx) for i, it in enumerate(grp)]
        cols = sec.get('ans_cols', 1) if ans else 1
        if ans and cols > 1:
            # 🔴 每题裹一层：grid 按直接子元素分格，而一道题可能返回多个兄弟 div
            o.append('<div class="ac" style="grid-template-columns:repeat(%d,1fr)">'
                     '%s</div>' % (cols, ''.join('<div class="q">%s</div>' % p
                                                 for p in parts)))
        else:
            dash = ctx.get('dash', True)
            o.append(''.join('<div class="q%s">%s</div>'
                             % ('' if dash else ' nodash', p) for p in parts))
        o.append('</div>')
    o.append('</div>')

    o.append(_wm(ctx) + '</div>')
    return ''.join(o)


# ═══════════════ 骨架自己的闸：版面宽度 ═══════════════
import re as _re

_CTRL = _re.compile(r'\\[a-zA-Z]+\s*|[{}\\$]')


def _visual_width(tex):
    """去掉 LaTeX 控制序列后的可见字符数。分数按分子分母较长的一支折半计。"""
    # \frac{a}{b} 竖排只占较宽一支的宽度 → 粗略地把 \frac{..}{..} 折成较长一支
    def _fold(m):
        a, b = m.group(1), m.group(2)
        return a if len(a) >= len(b) else b
    t = _re.sub(r'\\d?frac\{([^{}]*)\}\{([^{}]*)\}', _fold, tex)
    t = _re.sub(r'\^\{?[^{}\s]{1,6}\}?', '^', t)      # 上标只占一点点
    return len(_CTRL.sub('', t))


def guard(html, days, ctx):
    """🔴 版面宽度闸：MathJax 行内公式不换行，超列宽会横向溢出（页数断言查不出）。"""
    lim = int(ctx.get('max_w', DEFAULT_MAX_W))
    bad = []
    for di, day in enumerate(days):
        for si, grp in enumerate(day):
            for qi, it in enumerate(grp):
                stem = it.get('stem')
                tex = getattr(stem, 'h', stem) if stem is not None else ''
                w = _visual_width(str(tex))
                if w > lim:
                    bad.append('第%d天 第%d列 第%d题 宽约%d（上限%d）：%s'
                               % (di + 1, si + 1, qi + 1, w, lim, tex))
    assert not bad, ('🔴 版面宽度闸 FAIL —— 下列题面会溢出列宽：\n  '
                     + '\n  '.join(bad))
