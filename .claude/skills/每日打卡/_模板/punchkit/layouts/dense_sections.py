# -*- coding: utf-8 -*-
"""
骨架 `dense_sections` —— 无框极简 · 大留白 · 一天一页
=====================================================
首用 = 三上混合运算每日特训（30 天 420 题），**用户点名"用得非常好用"，2026-08-03 提为通用模版**。

好用在哪（照抄这三条，别改）：
  1. **留白舍得给** —— 每节下方一整块**固定高度**留白（缺省 42mm），不是按剩余空间挤出来的。
     一天四节 = 四大块空白，孩子写得开；也因此这套天生适合「过程长」的题。
  2. **无边框、极简** —— 只有黑体节标题，没有框线没有底色，打印省墨、复印不糊。
  3. **信息栏带「用时」** —— 姓名 / 日期 / **用时** 三项。「用时」是打卡册的灵魂，
     其余册子的「班级/姓名/日期」是作业本口径，这套是**打卡**口径。

🔴 **学科无关**：科学要用直接挂 `renderers.get('science')`，不要为它再造骨架。
"""
from .. import core

SPEC = {
    'key': 'dense_sections',
    'name': '无框极简·大留白',
    '学科': '通用',
    '长相': '无边框；单行居中标题（第N天）；姓名/日期/**用时**信息栏；'
            '黑体节标题；每节 N 道一行排开 + **固定 42mm 大留白**；右下角绝对定位水印',
    '适合': '🔴 **最通用的一套**（用户点名好用）。过程长、要写步骤的册子首选；'
            '题多过程短的也扛得住（调小 gap 即可）',
    '每页': '1 天',
    '槽位': '由 ctx["sections"] 逐节指定，任意组合',
    '数据形状': 'days = [day, ...]；day = [第1节items, 第2节items, ...]，与 ctx["sections"] 等长'
                '（**与 boxed_sections 同契约 → 两者可一行互换**）',
    '用过的册': '三上混合运算每日特训（原生）· 五升六暑假每日一练 · 五上计算强化每日一练',
    '旋钮': 'gap=节末留白mm（缺省42）｜gap_each=block节每题后留白mm｜'
            'ans_cols=答案卷该节压成几列（分步最长的那节别降列）',
}

DEFAULT_GAP_MM = 42          # 每节下方留白，三上原版就是这个值

CSS = """
  @page { size: A4; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.5; color: #000; }

  .card { width: 186mm; height: 266mm; margin: 0 auto; padding: 8mm 6mm 6mm;
          position: relative; display: flex; flex-direction: column;
          page-break-after: always; }
  .card:last-child { page-break-after: auto; }

  h1 { font-family: "SimHei", sans-serif; font-size: __H1__pt; text-align: center;
       margin: 0 0 3mm; }
  /* 🔴 姓名/日期/**用时** —— 「用时」是打卡口径的灵魂，别换成「班级」 */
  .info { text-align: center; font-size: __INFO__pt; margin-bottom: 2mm; }
  .info span { display: inline-block; width: 26mm; border-bottom: .35mm solid #000;
               margin: 0 1mm; }

  .sec { font-family: "SimHei", sans-serif; font-size: 1em; margin: 2.5mm 0 1.5mm; }
  .qn { font-family: "SimHei", sans-serif; margin-right: .15em; }

  /* 一行 N 道均分 */
  .g5 { display: grid; grid-template-columns: repeat(5, 1fr); column-gap: 1.5mm;
        row-gap: 5.5mm; }
  .r4 { display: grid; grid-template-columns: repeat(4, 1fr); column-gap: 2mm; }
  .blk > div { margin-bottom: 1mm; }
  .app { padding-left: 1.35em; text-indent: -1.35em; }

  /* 🔴 固定高度留白 —— 这套的招牌。不是 flex 挤出来的，是明码标价给的 */
  .sp { }

  .wm { position: absolute; right: 6mm; bottom: 4mm;
        font-family: "SimHei", sans-serif; font-size: 13pt; color: #525252; }
  .wm img { height: 15pt; vertical-align: -3pt; margin-right: 1mm; }

  /* ══ 答案卷：紧排、无留白、允许一天多页 ══ */
  body.asheet .card { height: auto; }
  body.asheet .sp { display: none !important; }
  body.asheet .g5 { row-gap: 1.8mm; }
  body.asheet .r4 { display: block; }
  /* 答案卷多列（`ans_cols`）：分步短的节可以并成 2~3 列，把整册答案压回更少页。
     🔴 分步链最长的那节（如简便运算 `=10×4.5−0.1×4.5`）**别降列**，会撞隔壁。 */
  .ac { display: grid; column-gap: 5mm; }
"""

CN = '一二三四五六七八九十'


def css(pt=None):
    pt = float(pt or 12.0)
    k = pt / 12.0
    from ..renderers import math as _default
    return (CSS.replace('__H1__', '%.2f' % (17.0 * k))
               .replace('__INFO__', '%.2f' % (10.5 * k))
               .replace('__PT__', '%.2f' % pt)) + _default.CSS


def _watermark(ctx):
    """水印拔插：None=彻底移除 / str=换文字 / dict={'text','img'}。

    🔴 2026-08-17 补：本骨架原来把「玉米训练营」写死在 render_card 里，
    `watermark=None` 对它无效 —— 而**网盘交付版必须无水印**（付费客户下载打印，
    卷面带广告是减损体验）。缺省仍是「玉米训练营」，老册行为不变。
    """
    wm = ctx.get('watermark', '玉米训练营')
    if not wm:
        return ''
    if isinstance(wm, str):
        wm = {'text': wm, 'img': True}
    img = core.watermark_img() if wm.get('img', True) else ''
    style = (' style="color:%s"' % wm['color']) if wm.get('color') else ''
    return '<div class="wm"%s>%s%s</div>' % (style, img, wm.get('text', ''))


def render_card(idx, data, ans, ctx):
    """
    idx  第几天（0 起）
    data 该天数据 = [第1节items, ...]，与 ctx['sections'] 等长
    ctx  {'sections':[{'name','slot','grid','gap'}], 'book_title', 'renderer', ...}
         sections[i]['gap'] = 该节留白 mm（缺省 DEFAULT_GAP_MM，给 0 表示不留）
    """
    R = ctx['renderer']
    secs = ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 节，与 ctx["sections"] 的 %d 节不符' % (idx + 1, len(data), len(secs))

    title = ctx.get('book_title', '')
    o = ['<div class="card">',
         '<h1>%s（第%s天）%s</h1>' % (title, CN[idx], '　参考答案' if ans else '')]
    if not ans:
        o.append('<div class="info">姓名：<span></span>　日期：<span></span>　'
                 '用时：<span></span></div>')

    for si, sec in enumerate(secs):
        grp = data[si]
        o.append('<div class="sec">%s、%s</div>' % (CN[si], sec['name']))
        render = R.SLOTS[sec['slot']]
        g = sec.get('grid', 'block')
        # 🔴 block 节可以「每题后各留一块」（gap_each），而不是只在节末留一次。
        #    三上原版第三/四节题目自带作答位（综合算式横线、树状图）所以不需要；
        #    但应用题这类**题面各占几行、要各自留白**的，节末留一次会把题挤成一坨。
        each = 0 if ans else sec.get('gap_each', 0)
        parts = [render(it, i, ans, ctx) for i, it in enumerate(grp)]
        cols = sec.get('ans_cols', 1) if ans else 1
        if ans and cols > 1:
            # 🔴 **每题必须裹一个 wrapper**（2026-08-03 实证的坑）：grid 按**直接子元素**分格，
            #    而「解方程/应用题」这类槽位一道题返回的是**多个兄弟 div**（题头 + 各解答行）。
            #    不裹就会把一道题拆散到两列去——解方程节实测出现过「①的题头在左列、
            #    它的解答行却排到右列」。裹了以后一格 = 一道题。
            o.append('<div class="ac" style="grid-template-columns:repeat(%d,1fr)">'
                     '%s</div>' % (cols, ''.join('<div>%s</div>' % p for p in parts)))
        elif g == 'block' and each:
            o.append('<div class="blk">%s</div>'
                     % ''.join(p + '<div class="sp" style="height:%gmm"></div>' % each
                               for p in parts))
        else:
            o.append('<div class="%s">%s</div>'
                     % ({'grid5': 'g5', 'row4': 'r4'}.get(g, 'blk'), ''.join(parts)))
        if not ans:
            gap = sec.get('gap', DEFAULT_GAP_MM)
            if gap:
                o.append('<div class="sp" style="height:%gmm"></div>' % gap)

    o.append('%s</div>' % _watermark(ctx))
    return ''.join(o)
