# -*- coding: utf-8 -*-
"""
骨架 `boxed_sections` —— 边框分节 · 一天一页
============================================
照实体教辅《暑假作业·每日一练》页型：
整页大边框 + **每节独立边框** + 顶部特大粗黑横幅 + 班级/姓名/日期栏。
首用 = 五升六暑假每日一练（2026-08-03）。

🔴 **学科无关**：分几节、有没有边框、留白怎么分，与教什么科目没关系。
   科学要用直接挂 `renderers.get('science')`，不要为它再造一个骨架。
"""
from .. import core

SPEC = {
    'key': 'boxed_sections',
    'name': '边框分节',
    '学科': '通用',
    '长相': '整页大边框 + 每节独立边框 + 特大粗黑横幅标题 + 班级/姓名/日期栏 + 页脚天序',
    '适合': '「暑假作业」型：节多（3~5 节）、每节题量差异大、要有仪式感的册子',
    '每页': '1 天',
    '槽位': '由 ctx["sections"] 逐节指定，任意组合（本骨架不限定题型）',
    '数据形状': 'days = [day, ...]；day = [第1节items, 第2节items, ...]，与 ctx["sections"] 等长',
    '用过的册': '五升六暑假每日一练',
}

# 节的排布方式：grid5=5列×N行 / row4=4道一行 / block=每题独占段落
GRIDS = {'grid5': 'g5', 'row4': 'r4', 'block': 'blk'}

CSS = """
  @page { size: A4; margin: 10mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.5; color: #000; }

  /* 一页 = 大边框 + 框外页脚（页脚不压学生作答区） */
  .card { height: 277mm; display: flex; flex-direction: column; page-break-after: always; }
  .card:last-child { page-break-after: auto; }
  .frame { flex: 1; border: 1.5pt solid #000; padding: 2.6mm 3mm 3mm;
           display: flex; flex-direction: column; min-height: 0; }

  /* 顶部横幅。🔴 27pt：原图是特大粗黑横幅占页顶显眼一块，21pt 那版偏小偏细 */
  .banner { font-family: "SimHei", sans-serif; font-size: __H1__pt; text-align: center;
            letter-spacing: 3px; line-height: 1.25; }
  .banner .r { color: __RED__; }
  /* 🔴 原图标题下**直接**是信息栏，没有副标题行——天序落页脚，且天的主题名是
     内部编排语言（「同分母加减」这类），按纪律不上学生卷面 */

  .info { border: 1pt solid #000; text-align: center; padding: 1.3mm 0;
          font-size: __INFO__pt; letter-spacing: 1px; }
  .info .fill { border-bottom: .35mm solid #000; display: inline-block; min-width: 26mm; }

  /* 每节独立边框 */
  .box { border: 1pt solid #000; margin-top: 1.8mm; padding: 1.2mm 2.2mm 1.8mm;
         display: flex; flex-direction: column; }
  .hd { font-family: "SimHei", sans-serif; font-size: 1.03em; letter-spacing: .5px;
        border-bottom: .5pt dashed #808080; padding-bottom: .8mm; margin-bottom: 1.2mm; }
  /* 🔴 节标题后不挂提示语：原图没有，且「最后两题先约分再算」这类等于把设计意图
     告诉学生——本该他自己看出来，点破这题就废了一半。提示语只留在册子的大纲里。 */
  .qn { font-family: "SimHei", sans-serif; margin-right: .15em; }

  /* 🔴 公式 1.12em：原图分数明显大于正文，小学生卷面分数印小了不好读 */
  .g5 { display: grid; grid-template-columns: repeat(5, 1fr);
        row-gap: 6.5mm; column-gap: 1.5mm; font-size: 1.12em; }
  .r4 { display: grid; grid-template-columns: repeat(4, 1fr); column-gap: 3mm;
        font-size: 1.12em; }
  .blank { flex: 1; min-height: 6mm; }
  .app { padding-left: 1.35em; text-indent: -1.35em; }

  .foot { display: flex; justify-content: space-between; align-items: baseline;
          padding: 1.1mm 1mm 0 1mm; font-family: "SimHei", sans-serif;
          font-size: 12pt; color: #525252; letter-spacing: 2px; }
  .foot .dm { font-size: .85em; letter-spacing: 1px; }
  .foot img { height: 1.25em; vertical-align: -0.28em; margin-right: 4px; }

  /* ══ 答案卷：不留白、紧排，一天不必占满整页 ══ */
  body.asheet .card { height: auto; }
  body.asheet .frame { flex: none; }
  body.asheet .box { flex: none !important; }
  body.asheet .blank { display: none; }
  body.asheet .g5 { row-gap: 1.8mm; }
  body.asheet .r4 { display: block; }
"""

CN = '一二三四五六七八九十'


def css(pt=None):
    pt = float(pt or 10.5)
    k = pt / 10.5
    from ..renderers import math as _default  # 骨架自带的默认追加 CSS（数学）
    return (CSS.replace('__H1__', '%.2f' % (27.0 * k))
               .replace('__INFO__', '%.2f' % (11.0 * k))
               .replace('__RED__', '#c0272d')
               .replace('__PT__', '%.2f' % pt)) + _default.CSS


def render_card(idx, data, ans, ctx):
    """
    idx  第几天（0 起）
    data 该天数据 = [第1节items, 第2节items, ...]，与 ctx['sections'] 等长
    ctx  {'sections':[{'name','slot','grid','flex'}], 'title_a','title_b',
          'total_days', 'renderer'}
    """
    R = ctx['renderer']
    secs = ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 节，与 ctx["sections"] 的 %d 节不符' % (idx + 1, len(data), len(secs))

    o = ['<div class="card"><div class="frame">',
         '<div class="banner">%s<span class="r">%s</span></div>'
         % (ctx.get('title_a', ''), ctx.get('title_b', ''))]

    if ans:
        o.append('<div class="info">参考答案　第%s天　共 %d 题</div>'
                 % (CN[idx], sum(len(g) for g in data)))
    else:
        o.append('<div class="info">班级：<span class="fill"></span>　'
                 '姓名：<span class="fill"></span>　'
                 '日期：<span class="fill"></span></div>')

    for si, sec in enumerate(secs):
        grp = data[si]
        flex = ' style="flex:%d"' % sec['flex'] if sec.get('flex') else ''
        o.append('<div class="box"%s>' % flex)
        # 🔴 「共N道」= 实际题量，与内容强绑定（原图写"共20道"却只有10道，我们按实际）
        o.append('<div class="hd">%s、%s（共%d道）</div>' % (CN[si], sec['name'], len(grp)))
        render = R.SLOTS[sec['slot']]
        g = sec.get('grid', 'block')
        if g == 'grid5':
            o.append('<div class="g5">%s</div>'
                     % ''.join(render(it, i, ans, ctx) for i, it in enumerate(grp)))
        elif g == 'row4':
            if ans:
                o.append(''.join(render(it, i, ans, ctx) for i, it in enumerate(grp)))
            else:
                o.append('<div class="r4">%s</div>'
                         % ''.join(render(it, i, ans, ctx) for i, it in enumerate(grp)))
                o.append('<div class="blank"></div>')
        else:                                   # block：每题独占段落 + 各自留白
            for i, it in enumerate(grp):
                o.append(render(it, i, ans, ctx))
                if not ans:
                    o.append('<div class="blank"></div>')
        o.append('</div>')

    o.append('</div><div class="foot"><span class="dm">第%s天　·　共 %d 天</span>'
             '<span class="wm">%s玉米训练营</span></div></div>'
             % (CN[idx], ctx.get('total_days', 1), core.watermark_img()))
    return ''.join(o)
