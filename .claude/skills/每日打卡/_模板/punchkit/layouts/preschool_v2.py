# -*- coding: utf-8 -*-
"""
骨架 `preschool_v2` —— 通栏节头 · 无框斑马纹（学前页型的 **B 版**）
====================================================================
与 `preschool_v1` 是**一对刻意做成两个样子的骨架**，专供小红书 A/B 双号：
平台判重看的是**版面结构**（栏数、节头形式、留白分布、页眉页脚），
水印和 dpi 都改不动它 —— 所以两个号必须各走一套骨架。

| 维度 | `preschool_v1`（A） | `preschool_v2`（B，本骨架） |
|---|---|---|
| 版心 | 整页彩色粗边框 | **无框**，靠页眉细线与节头色带分区 |
| 标题 | 居中超大 + 中文天序 | **左对齐中号**，天序落右上角徽标 |
| 信息栏 | 居中下划线一行 | **右上角方框**（姓名/日期两格） |
| 节头 | 「一、名称」纯文字行 | **通栏浅底色带** + 左侧竖色条 + 数字徽标 |
| 分隔 | 无（靠留白） | **交替浅底斑马纹**（单双节底色不同） |
| 页脚 | 居中天序 + 署名 | 左书名 · 右「Day N / 总数」 |

🔴 **内容零差异**：两版读同一份 `days.py`，题、答案、顺序一个字不动。
   改内容做差异化 = 两个号的答案对不上，客户拿到两版会以为发错货。
"""
from .. import core
from .daily_v1 import cn

SPEC = {
    'key': 'preschool_v2',
    'name': '通栏节头·学前B版',
    '学科': '通用',
    '长相': '无外框 + 左对齐中号标题 + 右上角天序徽标与姓名方框 + 五个通栏色带节头 + '
            '单双节交替浅底 + 页脚左书名右 Day 数',
    '适合': '与 `preschool_v1` 配对做 A/B 双号；单用也可（更"教辅内页"味，不那么仪式感）',
    '每页': '1 天',
    '槽位': '与 preschool_v1 完全相同（ctx["sections"] 逐节指定，grid 可选 g2/g3/g4/g5）',
    '数据形状': '同 preschool_v1：days = [day, ...]；day = [第1节items, ...]',
    '用过的册': '幼小衔接数学综合练习（B 号）',
}

GRIDS = {'g2': 2, 'g3': 3, 'g4': 4, 'g5': 5}

CSS = """
  @page { size: A4; margin: 11mm 10mm; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: "SimSun", serif; font-size: __PT__pt; line-height: 1.4; color: #000; }

  .card  { height: 275mm; display: flex; flex-direction: column; page-break-after: always; }
  .card:last-child { page-break-after: auto; }
  .frame { flex: 1; display: flex; flex-direction: column; min-height: 0; }

  /* ── 页眉：左标题、右天序徽标 + 姓名方框（A 版是居中大标题 + 居中下划线栏）── */
  .top   { display: flex; align-items: flex-start; justify-content: space-between;
           border-bottom: .8mm solid __ACC__; padding-bottom: 2.2mm; }
  .tl    { display: flex; flex-direction: column; gap: 1.4mm; }
  .tl .t1{ font-family: "SimHei", sans-serif; font-size: __H1__pt; letter-spacing: 1px;
           line-height: 1.1; }
  .tl .t2{ font-family: "SimHei", sans-serif; font-size: __SUB__pt; color: #5a5a5a;
           letter-spacing: 3px; }
  .tr    { display: flex; align-items: stretch; gap: 2.4mm; }
  .day   { border: .7mm solid __ACC__; padding: 1mm 3.2mm; text-align: center;
           font-family: "SimHei", sans-serif; line-height: 1.15; }
  .day b { display: block; font-size: __DAYN__pt; font-weight: normal; }
  .day i { display: block; font-style: normal; font-size: __SUB__pt; color: #5a5a5a; }
  .name  { border: .35mm solid #000; display: flex; flex-direction: column;
           font-family: "SimHei", sans-serif; font-size: __INFO__pt; }
  .name span { padding: 1mm 2.6mm; min-width: 32mm; }
  .name span + span { border-top: .35mm solid #000; }

  /* ── 节：通栏色带节头 + 交替浅底（A 版是纯文字节标题、无底色）── */
  .box { display: flex; flex-direction: column; min-height: min-content; margin-top: 2mm; }
  .box:nth-child(even) > .gr { background: #f4f4f4; }
  .hd  { display: flex; align-items: center; gap: 2.2mm; background: __BAND__;
         border-left: 1.6mm solid __ACC__; padding: 1mm 2.4mm; }
  .hd .no { font-family: "SimHei", sans-serif; font-size: __HD__pt;
            background: __ACC__; color: #fff; padding: 0 1.8mm; }
  .hd .nm { font-family: "SimHei", sans-serif; font-size: __HD__pt; letter-spacing: .5px; }
  .hd .qt { margin-left: auto; font-family: "SimHei", sans-serif;
            font-size: __INFO__pt; color: #5a5a5a; }

  .gr  { display: grid; flex: 1; min-height: min-content; align-content: space-between;
         justify-items: center; row-gap: 2mm; column-gap: 3mm; padding: 2mm 1mm; }
  .it  { display: flex; justify-content: center; width: 100%; }

  .foot { display: flex; justify-content: space-between; align-items: baseline;
          border-top: .35mm solid #9a9a9a; margin-top: 1.6mm; padding-top: 1.2mm;
          font-family: "SimHei", sans-serif; font-size: 10.5pt; color: #6b6b6b;
          letter-spacing: 1px; }
  .foot img { height: 1.2em; vertical-align: -0.26em; margin-right: 4px; }

  /* ══ 答案卷 ══ */
  body.asheet .card  { height: auto; }
  body.asheet .frame { flex: none; }
  body.asheet .box   { flex: none !important; }
  body.asheet .gr    { flex: none; align-content: start; row-gap: 2.4mm; }
"""


def css(pt=None):
    pt = float(pt or 12.0)
    k = pt / 12.0
    from ..renderers import preschool as _default
    return (CSS.replace('__H1__', '%.2f' % (19.0 * k))
               .replace('__SUB__', '%.2f' % (9.5 * k))
               .replace('__DAYN__', '%.2f' % (20.0 * k))
               .replace('__INFO__', '%.2f' % (10.0 * k))
               .replace('__HD__', '%.2f' % (12.0 * k))
               .replace('__ACC__', '#2f7d5c')          # B 版走墨绿，与 A 版草绿分开
               .replace('__BAND__', '#e7f0ea')
               .replace('__PT__', '%.2f' % pt)) + _default.css()


def render_card(idx, data, ans, ctx):
    R = ctx['renderer']
    secs = ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 节，与 ctx["sections"] 的 %d 节不符' % (idx + 1, len(data), len(secs))

    total = sum(len(g) for g in data)
    o = ['<div class="card"><div class="frame">', '<div class="top">',
         '<div class="tl"><div class="t1">%s</div><div class="t2">%s</div></div>'
         % (ctx.get('title', ''),
            ('参考答案' if ans else ctx.get('subtitle', '')))]
    o.append('<div class="tr"><div class="day"><b>%d</b><i>DAY</i></div>' % (idx + 1))
    if ans:
        o.append('<div class="name"><span>第 %s 天</span><span>共 %d 题</span></div>'
                 % (cn(idx + 1), total))
    else:
        o.append('<div class="name"><span>姓名</span><span>日期</span></div>')
    o.append('</div></div>')

    for si, sec in enumerate(secs):
        grp = data[si]
        flex = ' style="flex:%d"' % sec['flex'] if sec.get('flex') else ''
        cols = GRIDS.get(sec.get('grid', 'g5'), 5)
        render = R.SLOTS[sec['slot']]
        o.append('<div class="box"%s>' % flex)
        o.append('<div class="hd"><span class="no">%d</span><span class="nm">%s</span>'
                 '<span class="qt">%d 题</span></div>' % (si + 1, sec['name'], len(grp)))
        o.append('<div class="gr" style="grid-template-columns:repeat(%d,1fr)">%s</div>'
                 % (cols, ''.join('<div class="it">%s</div>' % render(it, i, ans, ctx)
                                  for i, it in enumerate(grp))))
        o.append('</div>')

    wm = ('%s玉米训练营' % core.watermark_img()) if ctx.get('watermark', True) else ''
    o.append('</div><div class="foot"><span>%s</span><span>Day %d / %d　%s</span></div></div>'
             % (ctx.get('title', ''), idx + 1, ctx.get('total_days', 1), wm))
    return ''.join(o)
