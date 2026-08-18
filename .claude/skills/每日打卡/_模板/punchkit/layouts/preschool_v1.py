# -*- coding: utf-8 -*-
"""
骨架 `preschool_v1` —— 彩边大字 · 一天一页（幼小衔接页型）
==========================================================
照实体《幼小衔接 数学综合练习》页型：
**整页彩色粗边框** + 大号居中标题（带天序）+ 姓名/班级/日期下划线栏 +
五个黑体小节（无框）+ 页脚天序。
首用 = 幼小衔接数学综合练习（2026-08-13）。

🔴 **学科无关**（`学科='通用'`）：彩边框、五节无框、大字号，与教什么科目没关系。
   默认挂学前渲染器（`renderers.get('preschool')`），换别的渲染器一样能用。

🔴 **本骨架的留白哲学与计算册相反**：学前题目**自带作答位**（分解树的空格、
   算式的括号与圆圈），不需要额外的空白行；要撑满一页靠的是**把行距拉开**
   （`align-content:space-between`），而不是在节末塞 `.blank`。
   —— 对幼儿来说，字大、格子大、行间松，比留一片空白重要得多。
"""
from .. import core
from .daily_v1 import cn          # 🔴 中文数字必须用它：CN[i] 到第 11 天会 IndexError

SPEC = {
    'key': 'preschool_v1',
    'name': '彩边大字·学前',
    '学科': '通用',
    '长相': '整页彩色粗边框 + 大号居中标题（带中文天序）+ 姓名/班级/日期下划线栏 + '
            '五个黑体无框小节 + 页脚天序署名',
    '适合': '幼小衔接 / 一年级上：题目自带作答格（分解树、圆圈、括号），字大行松、一天一页',
    '每页': '1 天',
    '槽位': '由 ctx["sections"] 逐节指定；grid 可选 g2/g3/g4/g5（列数）',
    '数据形状': 'days = [day, ...]；day = [第1节items, 第2节items, ...]，与 ctx["sections"] 等长',
    '用过的册': '幼小衔接数学综合练习',
}

GRIDS = {'g2': 2, 'g3': 3, 'g4': 4, 'g5': 5}

CSS = """
  @page { size: A4; margin: 6mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.4; color: #000; }

  .card  { height: 285mm; display: flex; flex-direction: column; page-break-after: always; }
  .card:last-child { page-break-after: auto; }
  /* 整页彩色粗边框 —— 幼儿册的标志性外观，也是打印裁切的参照 */
  .frame { flex: 1; border: 2.2mm solid __ACC__; border-radius: 2mm;
           padding: 4mm 5mm 3mm; display: flex; flex-direction: column; min-height: 0; }

  .banner { font-family: "SimHei", sans-serif; font-size: __H1__pt; text-align: center;
            letter-spacing: 2px; line-height: 1.2; }
  .info   { text-align: center; font-size: __INFO__pt; letter-spacing: 1px;
            margin: 2.4mm 0 1.2mm; font-family: "SimHei", sans-serif; }
  .info .fill { border-bottom: .3mm solid #000; display: inline-block; min-width: 24mm; }
  .info .sp   { display: inline-block; width: 6mm; }

  /* 🔴 `min-height: min-content` 而不是 0 —— flex 只许分配**剩余**空间，绝不许把节压到
     小于内容高。写 0 时 flex 权重配小了会让下一节的标题直接压在上一节的题上（实伤过），
     而这种重叠**页数断言抓不到**（还是 1 页）。改成 min-content 后，权重配错只会撑成
     2 页 → 页数断言当场报错，静默事故变成响亮报错。 */
  .box { display: flex; flex-direction: column; min-height: min-content; margin-top: 1.4mm; }
  .hd  { font-family: "SimHei", sans-serif; font-size: __HD__pt; letter-spacing: .5px;
         margin-bottom: 1mm; }

  /* 🔴 行距拉开靠 space-between，不靠塞空白行（见模块 docstring） */
  .gr  { display: grid; flex: 1; min-height: min-content; align-content: space-between;
         justify-items: center; row-gap: 2mm; column-gap: 3.5mm; }
  .it  { display: flex; justify-content: center; width: 100%; }

  .foot { display: flex; justify-content: space-between; align-items: baseline;
          padding: 1.4mm 1.5mm 0; font-family: "SimHei", sans-serif;
          font-size: 11pt; color: #6b6b6b; letter-spacing: 2px; }
  .foot .dm { font-size: .9em; }
  .foot img { height: 1.2em; vertical-align: -0.26em; margin-right: 4px; }

  /* ══ 答案卷：紧排、不撑页 ══ */
  body.asheet .card  { height: auto; }
  body.asheet .frame { flex: none; }
  body.asheet .box   { flex: none !important; }
  body.asheet .gr    { flex: none; align-content: start; row-gap: 2.4mm; }
"""


def css(pt=None):
    pt = float(pt or 12.0)
    k = pt / 12.0
    from ..renderers import preschool as _default   # 骨架自带的默认追加 CSS（学前）
    return (CSS.replace('__H1__', '%.2f' % (23.0 * k))
               .replace('__INFO__', '%.2f' % (11.5 * k))
               .replace('__HD__', '%.2f' % (12.5 * k))
               .replace('__ACC__', '#93c83e')
               .replace('__PT__', '%.2f' % pt)) + _default.css()


def render_card(idx, data, ans, ctx):
    """
    idx  第几天（0 起）
    data 该天数据 = [第1节items, 第2节items, ...]，与 ctx['sections'] 等长
    ctx  {'sections':[{'name','slot','grid','flex'}], 'title', 'total_days',
          'renderer', 'watermark'(bool，缺省 True)}
    """
    R = ctx['renderer']
    secs = ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 节，与 ctx["sections"] 的 %d 节不符' % (idx + 1, len(data), len(secs))

    title = '%s（%s）' % (ctx.get('title', ''), cn(idx + 1))
    o = ['<div class="card"><div class="frame">',
         '<div class="banner">%s</div>' % title]

    if ans:
        o.append('<div class="info">参　考　答　案<span class="sp"></span>'
                 '第%s天<span class="sp"></span>共 %d 题</div>'
                 % (cn(idx + 1), sum(len(g) for g in data)))
    else:
        o.append('<div class="info">姓名：<span class="fill"></span><span class="sp"></span>'
                 '班级：<span class="fill"></span><span class="sp"></span>'
                 '日期：<span class="fill"></span></div>')

    for si, sec in enumerate(secs):
        grp = data[si]
        flex = ' style="flex:%d"' % sec['flex'] if sec.get('flex') else ''
        cols = GRIDS.get(sec.get('grid', 'g5'), 5)
        render = R.SLOTS[sec['slot']]
        o.append('<div class="box"%s>' % flex)
        o.append('<div class="hd">%s、%s</div>' % (cn(si + 1), sec['name']))
        # 🔴 每题裹 wrapper —— grid 按直接子元素分格，一道题若返回多个兄弟 div 会被拆散
        o.append('<div class="gr" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
                 % (cols, ''.join('<div class="it">%s</div>' % render(it, i, ans, ctx)
                                  for i, it in enumerate(grp))))
        o.append('</div>')

    wm = ('<span class="wm">%s玉米训练营</span>' % core.watermark_img()
          if ctx.get('watermark', True) else '<span></span>')
    o.append('</div><div class="foot"><span class="dm">第%s天　·　共 %d 天</span>%s</div></div>'
             % (cn(idx + 1), ctx.get('total_days', 1), wm))
    return ''.join(o)
