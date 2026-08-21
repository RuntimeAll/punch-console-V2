# -*- coding: utf-8 -*-
"""
组件 `page_footer` —— 页脚（左=页码/天序，右=署名+水印）
=============================================================================
2026-08-21 用户令立：「页码还有水印，都要设置为页脚」「这个作为全局的组件来」。

## 🔴 为什么会出现「页脚浮在页中间」（本组件要解决的病）

页脚是 `position:absolute; bottom:…`，它贴的是**最近的定位祖先**（那张 `.card`），
不是纸。所以只要卡片比纸矮，页脚就跟着卡片矮的那条边走：

    A4 纸 297mm ─ 卡片 266mm ＝ 页脚离纸底永远差 31mm（sync_kaodian / dense_sections 老账）

**用本组件的前提**：宿主卡片必须占满整页（`height: 297mm` + `box-sizing:border-box`，
照 daily_v1 的 `.sheet` —— 那是实战出过册的尺寸），页脚才真的落在纸底。
卡片矮一截却引本组件 = 病还在，`assert_full_page_card()` 就是拦这个的。

答案卷那类「内容短、卡片 height:auto」的，宿主要给 `min-height: 297mm`，
否则卡片缩到内容那么高，页脚又浮回内容末尾。

## 契约

    css(inset_x='19mm', bottom='8mm', pt=9.0, color='#555') -> str
    html(left='', right='', watermark='玉米训练营')          -> str
"""
from .. import core

SPEC = {
    'key': 'page_footer',
    'name': '页脚·页码与水印',
    '用途': '每页底部一行：左＝页码/天序，右＝署名与玉米水印。跨版式通用，改一处全体受益',
    '适用': '打卡册/专项卷/试卷 —— 任何「一卡一页」的版式',
    '结构': 'position:absolute 贴宿主卡片底边；🔴 宿主卡片必须满页（297mm）否则页脚浮在页中间',
    '旋钮': 'inset_x=左右内缩(跟随宿主 padding)｜bottom=距纸底(缺省8mm)｜pt=字号｜'
            'color=颜色｜watermark=水印文字(None 可拔掉)',
    '用过的版式': 'sync_kaodian（首用 2026-08-21）',
}

CSS = """
  /* ── 组件 page_footer：页脚一行（左页码 / 右署名水印）────────────────
     🔴 贴的是宿主 .card 的底边——宿主必须满页，否则页脚跟着矮卡片浮在页中间 */
  .pgft { position: absolute; left: __IX__; right: __IX__; bottom: __BT__;
          font-size: __FT__pt; color: __CL__; display: flex; align-items: baseline; }
  .pgft .r { margin-left: auto; }
  .pgft .wm { font-family: "SimHei", sans-serif; color: #525252; }
  .pgft .wm img { height: 11pt; vertical-align: -2pt; margin-right: 1mm; }
"""


def css(inset_x='19mm', bottom='8mm', pt=9.0, color='#555'):
    return (CSS.replace('__IX__', str(inset_x))
               .replace('__BT__', str(bottom))
               .replace('__FT__', '%.2f' % float(pt))
               .replace('__CL__', color))


def html(left='', right='', watermark='玉米训练营'):
    """left=页码/天序；right=署名（可空）；watermark=水印文字（None 拔掉）。"""
    rs = []
    if right:
        rs.append(str(right))
    if watermark:
        rs.append('<span class="wm">%s%s</span>' % (core.watermark_img(), watermark))
    return ('<div class="pgft"><span>%s</span><span class="r">%s</span></div>'
            % (left or '', '　'.join(rs)))


def assert_full_page_card(card_css, page_mm=297.0):
    """闸：宿主卡片必须满页，否则页脚必然浮在页中间（本组件的头号误用）。

    card_css = 宿主 .card 那条规则的字符串（含 height: …mm）。
    只在版式的 guard 里调，拿不准就别调——它只认 `height: <数字>mm` 这一种写法。
    """
    import re
    m = re.search(r'height\s*:\s*([\d.]+)\s*mm', card_css)
    if not m:
        return True                      # 没写死高度（如 exam_paper 走 @page margin）不管
    h = float(m.group(1))
    if h < page_mm - 0.5:
        raise AssertionError(
            '🔴 page_footer 误用：宿主卡片只有 %gmm，纸是 %gmm——页脚会浮在离纸底 %gmm 的地方'
            '（这正是本组件要治的病）。把卡片改成满页 %gmm（box-sizing:border-box，'
            '照 daily_v1 的 .sheet），用 padding 控内容边距。' % (h, page_mm, page_mm - h, page_mm))
    return True
