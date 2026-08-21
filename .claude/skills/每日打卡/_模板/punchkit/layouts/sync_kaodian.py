# -*- coding: utf-8 -*-
"""
骨架 `sync_kaodian` —— 同步考点型 · 一天一页 · 考点小标题随天变
==============================================================
首用 = 七上第二单元打卡册（人教版）。**规格来自 2026-08-08 用户白板**：

    每个打卡（= 一天）= 4 个考点 × 3 个例题（2 易 1 中）= 12 题
    考点顺序按课节内容「由浅入深」；3 天一组用同一套考点**平行出卷**

## 🔴 与其余骨架的根本差异：考点名**随天变**

`dense_sections` / `boxed_sections` / `daily_v1` 的节名写在 `ctx['sections']` 里，
**全册固定**（第一节永远叫「口算」）。同步册不是这样——它跟着课本节次走，
第 1 天练「有理数的加法法则」、第 4 天练「乘法运算律」，**节名是内容的一部分**。

所以本骨架的数据形状把节名下放到天里：

    days = [day, ...]
    day  = [{'name': '有理数的加法法则', 'items': [...]}, ...]   # 缺省 4 组

`ctx['sections']` 在本骨架里**不用**（给了也忽略），别照 dense_sections 的样子配。

## 难度标记

每道题可带 `lv`（`'易'`/`'中'`/`'难'`），渲成题号前的小灰字。
不带 `lv` 的题不显示标记——老册和别的骨架混用时不会炸。

## 留白

四个考点块**均分整页剩余空间**（`flex:1`），所以：
  - 题多的天留白小、题少的天留白大，但**页数恒等于天数**；
  - 想给某个考点更多写字空间，在该组上写 `'weight': 2`。
"""
from .. import core

SPEC = {
    'key': 'sync_kaodian',
    'name': '同步考点型',
    '学科': '通用',
    '长相': '页眉册名小字 + 单元名大标题（第N天）；学生/用时/**建议时长**三项信息栏；'
            '每个考点一个块（黑体「考点一：知识点名」+ 左侧竖条）；'
            '题号前可带 易/中 难度小字；四块均分剩余空间作答；页脚天序 + 出卷人',
    '适合': '🔴 **跟课本单元/课节走的同步打卡册**：一天覆盖若干考点、每考点若干例题、'
            '由浅入深。考点名随天变是它与其余骨架的分水岭',
    '每页': '1 天',
    '槽位': '每个考点组自带 slot（缺省 ctx["slot"]，再缺省 "expr"），渲染器按槽位出题',
    '数据形状': 'days = [day, ...]；day = [{"name": 考点名, "items": [...], '
                '"slot"?: 槽位, "weight"?: 留白权重}, ...]　🔴 **节名在天里，不在 ctx**',
    '用过的册': '（暂无）',
    '状态': '🟠 在库·**未启用** —— 同一份 2026-08-08 白板规格，实际落地走的是 '
            '`textbook_spread` 的**范式 B（考点分组）**（红标题 + 口诀 + 全大题），'
            '首用 = 七上第二单元打卡册（人教版）。本骨架是另一种长相（页眉册名小字 + '
            '竖条考点块 + 易/中标记），要「考点型」先去看那边，别在这里重开一套',
    '旋钮': 'book_title=册名(页眉小字)｜unit_title=单元名(大标题)｜suggest_min=建议时长(分钟)｜'
            'author=出卷人(页脚)｜show_lv=是否显示易/中标记(缺省True)｜slot=全册缺省槽位｜'
            'watermark=None 可移除',
}

CSS = """
  @page { size: A4; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.5; color: #000; }

  .card { width: 186mm; height: 266mm; margin: 0 auto; padding: 9mm 7mm 7mm;
          position: relative; display: flex; flex-direction: column;
          page-break-after: always; }
  .card:last-child { page-break-after: auto; }

  /* ── 页眉：册名小字 + 单元名大标题 ── */
  .bk { font-family: "SimHei", sans-serif; font-size: __BK__pt; color: #666;
        text-align: center; letter-spacing: .06em; margin-bottom: 1mm; }
  h1 { font-family: "SimHei", sans-serif; font-size: __H1__pt; text-align: center;
       margin: 0 0 2.5mm; }
  h1 .day { font-size: .72em; font-weight: normal; color: #444; margin-left: .4em; }

  /* ── 信息栏：学生 / 用时 / 建议时长（建议时长是印死的值，不是填空） ── */
  .info { text-align: center; font-size: __INFO__pt; margin-bottom: 3mm;
          padding-bottom: 2mm; border-bottom: .35mm solid #000; }
  .info span { display: inline-block; width: 24mm; border-bottom: .3mm solid #000;
               margin: 0 1mm; }
  .info .fix { white-space: nowrap; }
  .info .fix { color: #444; }

  /* ── 考点块：左侧竖条 + 黑体标题；四块均分剩余空间 ── */
  .kp { display: flex; flex-direction: column; margin-bottom: 2mm; }
  .kp-h { font-family: "SimHei", sans-serif; font-size: 1.02em;
          border-left: 1.1mm solid #000; padding-left: 2mm; margin-bottom: 2mm; }
  .kp-h .kpn { margin-right: .3em; }
  .qs > div { margin-bottom: 1.2mm; }
  .qs .app { padding-left: 1.35em; text-indent: -1.35em; }
  /* 难度小字：不抢题面的视觉，灰、小、贴在题号前 */
  .lv { font-family: "SimHei", sans-serif; font-size: .72em; color: #777;
        margin-right: .35em; }
  /* 作答留白：吃掉剩余空间，页数恒等于天数 */
  .sp { flex: 1; min-height: 6mm; }

  .ft { position: absolute; left: 7mm; right: 7mm; bottom: 4.5mm;
        font-size: __FT__pt; color: #555; display: flex; }
  .ft .r { margin-left: auto; }
  .wm { font-family: "SimHei", sans-serif; color: #525252; }
  .wm img { height: 11pt; vertical-align: -2pt; margin-right: 1mm; }

  /* ══ 答案卷：紧排、无留白、允许一天多页 ══ */
  body.asheet .card { height: auto; }
  body.asheet .sp { display: none !important; }
  body.asheet .kp { margin-bottom: 3mm; }
  body.asheet .info { display: none; }
  .ac { display: grid; column-gap: 5mm; }
"""

CN = '一二三四五六七八九十'
_CN_DAY = '一二三四五六七八九十'


def css(pt=None):
    pt = float(pt or 12.0)
    k = pt / 12.0
    from ..renderers import math as _default
    return (CSS.replace('__BK__', '%.2f' % (10.0 * k))
               .replace('__H1__', '%.2f' % (18.0 * k))
               .replace('__INFO__', '%.2f' % (10.5 * k))
               .replace('__FT__', '%.2f' % (9.0 * k))
               .replace('__PT__', '%.2f' % pt)) + _default.CSS


def _day_word(idx):
    """第 N 天：十以内用中文，超过十用数字（十一天以上的册不至于崩）"""
    return _CN_DAY[idx] if idx < len(_CN_DAY) else str(idx + 1)


def render_card(idx, data, ans, ctx):
    """
    idx  第几天（0 起）
    data 该天数据 = [{'name','items','slot'?,'weight'?}, ...]
    ctx  book_title / unit_title / suggest_min / author / show_lv / slot / renderer
    """
    R = ctx['renderer']
    assert isinstance(data, (list, tuple)) and data and isinstance(data[0], dict), \
        ('🔴 第%d天的数据形状不对。sync_kaodian 要的是 '
         '[{"name":考点名,"items":[...]}, ...]，不是 dense_sections 那种纯 items 列表' % (idx + 1))

    o = ['<div class="card">']
    if ctx.get('book_title'):
        o.append('<div class="bk">%s</div>' % ctx['book_title'])
    o.append('<h1>%s<span class="day">第%s天%s</span></h1>'
             % (ctx.get('unit_title', ''), _day_word(idx), '·参考答案' if ans else ''))

    if not ans:
        suggest = ctx.get('suggest_min')
        o.append('<div class="info">学生：<span></span>　用时：<span></span>'
                 + ('　<span class="fix">建议时长：%s分钟</span>' % suggest if suggest else '')
                 + '</div>')

    show_lv = ctx.get('show_lv', True)
    default_slot = ctx.get('slot', 'expr')

    for gi, grp in enumerate(data):
        items = grp.get('items', [])
        render = R.SLOTS[grp.get('slot', default_slot)]
        o.append('<div class="kp" style="flex:%g">' % (grp.get('weight', 1) if not ans else 0))
        o.append('<div class="kp-h"><span class="kpn">考点%s：</span>%s</div>'
                 % (CN[gi] if gi < len(CN) else str(gi + 1), grp['name']))

        parts = []
        for i, it in enumerate(items):
            html = render(it, i, ans, ctx)
            # 难度小字插在题号前：题号由渲染器吐在 <div> 开头，这里挤进去
            lv = it.get('lv') if isinstance(it, dict) else None
            if show_lv and lv and not ans:
                html = html.replace('>', '><span class="lv">[%s]</span>' % lv, 1)
            parts.append(html)

        cols = grp.get('ans_cols', 1) if ans else 1
        if ans and cols > 1:
            # 一格 = 一道题（一道题可能吐多个兄弟 div，不裹会被 grid 拆散）
            o.append('<div class="ac" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
                     % (cols, ''.join('<div>%s</div>' % p for p in parts)))
        else:
            o.append('<div class="qs">%s</div>' % ''.join(parts))

        if not ans:
            o.append('<div class="sp"></div>')
        o.append('</div>')

    # 页脚：左=天序，右=出卷人/水印
    right = []
    if ctx.get('author'):
        right.append(ctx['author'])
    wm = ctx.get('watermark', '玉米训练营')
    if wm:
        right.append('<span class="wm">%s%s</span>' % (core.watermark_img(), wm))
    o.append('<div class="ft"><span>%s</span><span class="r">%s</span></div>'
             % ('第 %d 天' % (idx + 1), '　'.join(right)))
    o.append('</div>')
    return ''.join(o)


def guard(html, days, ctx):
    """骨架自己的闸：每天的考点组数与每组题数要齐整（白板规格 = 4 考点 × 3 题）。
    只提醒不拦路 —— 打样阶段常故意先摆一天。"""
    want_g = ctx.get('expect_groups')
    want_q = ctx.get('expect_per_group')
    bad = []
    for i, d in enumerate(days):
        if want_g and len(d) != want_g:
            bad.append('第%d天 %d 个考点（期望 %d）' % (i + 1, len(d), want_g))
        if want_q:
            for g in d:
                if len(g.get('items', [])) != want_q:
                    bad.append('第%d天「%s」%d 题（期望 %d）'
                               % (i + 1, g['name'], len(g.get('items', [])), want_q))
    if bad:
        print('  ⚠️ 结构提醒：' + '；'.join(bad[:6]) + ('…' if len(bad) > 6 else ''))
