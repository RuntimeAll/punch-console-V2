# -*- coding: utf-8 -*-
"""考点打卡出件器（punchkit `sync_kaodian` 骨架首启 · 库中心取题）
==============================================================================
定位：打卡册形态的出件通路——与 render_paper.py（试卷形态）平行，同吃 kb.db 的
blocks_json，走 punchkit 骨架×渲染器两层制。🔴 本工具**只读**连库（mode=ro），
不写任何表；出的是纸，不是账（挂账走 artifact_tool，模版登记走 template-add）。

用法：
    python 工具箱/渲染/render_punch.py <spec.json> [--db kb.db] [--out-dir 产物/...]
           [--pt 11.5] [--png]

spec.json 契约（punch-spec/v1）：
    {
      "contract": "punch-spec/v1",
      "stem": "图形的初步知识·考点打卡·样稿",
      "ctx":  { "book_title": "...", "unit_title": "...", "suggest_min": 25,
                "author": "...", "body_pt": 11.5 },        # 透传 sync_kaodian 旋钮
      "days": [                                            # 一天一页
        [ { "name": "角的概念", "slot": "choice",           # 一考点组=同一槽位
            "items": [ {"qid": "q2026...", "lv": "中"}, ... ] }, ... ]
      ]
    }

槽位适配（blocks_json 规范 v2 → punchkit renderers.math 契约）：
    choice     → text=题面 + options[{label,html}]（option cells）+ opt_cols 按最长选项定
    fill       → text=题面；答案卷补 answer_blocks 首格（没有就如实印待补）
    word_multi → text=题面；答案卷 lines=answer_blocks 各行（没有就「（待补答案）」）
🔴 缺答案不拒渲（打卡样稿/练习卷合法态），但答案卷必须如实印「（待补答案）」，绝不静默漏题。
"""
import argparse
import html as _html
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.claude' / 'skills' / '每日打卡' / '_模板'))
from punchkit import core, layouts, renderers          # noqa: E402

CONTRACT = 'punch-spec/v1'


def md2html(md):
    """md（内联 $LaTeX$）→ 渲染层 HTML：转义 → $…$→\\(…\\) → 换行→<br>。
    与 render_paper.py 的 md_to_delim 同向（唯一形态转换点原则）；$$ 一律拒。"""
    if '$$' in md:
        sys.exit('🔴 出现 $$ 显示公式，本版只吃内联 $…$：%s' % md[:60])
    out, pos, opened = [], 0, False
    for m in re.finditer(r'(?<!\\)\$', md):
        seg = md[pos:m.start()]
        out.append(seg if opened else _html.escape(seg, quote=False))
        out.append('\\)' if opened else '\\(')
        opened = not opened
        pos = m.end()
    if opened:
        sys.exit('🔴 $ 定界不成对：%s' % md[:60])
    out.append(_html.escape(md[pos:], quote=False))
    s = ''.join(out)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)      # md 加粗（解析里常用 **(1)**）
    return s.replace('\n', '<br>')


def first_text_md(blocks):
    for row in blocks.get('rows', []):
        for cell in row.get('cells', []):
            if cell.get('type') == 'text':
                return cell.get('md', '')
    return ''


def answer_html(q, field='answer_blocks_json'):
    raw = q.get(field)
    if not raw or len(raw) <= 20:
        return None
    md = first_text_md(json.loads(raw))
    return md2html(md) if md else None


def adapt(q, slot):
    """一道库题 → 该槽位的渲染器 item。"""
    blocks = json.loads(q['blocks_json'])
    text = md2html(first_text_md(blocks))
    ans = answer_html(q)
    if slot == 'choice':
        opts, longest = [], 0
        for row in blocks.get('rows', []):
            for cell in row.get('cells', []):
                if cell.get('type') == 'option':
                    md = first_text_md({'rows': [{'cells': cell.get('blocks', [])}]})
                    longest = max(longest, len(md))
                    opts.append({'label': cell.get('label', '?'), 'html': md2html(md)})
        if not opts:
            sys.exit('🔴 %s 走 choice 槽位但 blocks 里没有 option 格' % q['id'])
        cols = 4 if longest <= 8 else (2 if longest <= 22 else 1)
        return {'text': text, 'options': opts, 'opt_cols': cols,
                'ans': ans or '（待补答案）'}
    if slot == 'fill':
        return {'text': text, 'ans': ans or '（待补答案）'}
    if slot == 'word_multi':
        # 答案卷口径：解答题印**完整过程**（analysis），没有解析才退回只印结论——
        # 老区打卡线的定版（"答案卷给完整计算过程不只是得数，孩子能自己定位错在第几步"）
        deep = answer_html(q, 'analysis_blocks_json')
        return {'text': text,
                'lines': [deep or ans or '（待补答案）'], 'ansline': ''}
    sys.exit('🔴 本出件器暂只适配 choice/fill/word_multi 三个槽位，来的是 %r' % slot)


def main():
    ap = argparse.ArgumentParser(description='考点打卡出件器（sync_kaodian）')
    ap.add_argument('spec')
    ap.add_argument('--db', default=str(ROOT / '知识库' / 'kb.db'))
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--pt', type=float, default=None)
    ap.add_argument('--png', action='store_true')
    a = ap.parse_args()

    spec = json.load(open(a.spec, encoding='utf-8'))
    if spec.get('contract') != CONTRACT:
        sys.exit('🔴 spec 契约不是 %s：%r' % (CONTRACT, spec.get('contract')))

    import sqlite3
    conn = sqlite3.connect('file:%s?mode=ro' % Path(a.db).as_posix(), uri=True)
    conn.row_factory = sqlite3.Row

    days = []
    for day in spec['days']:
        groups = []
        for grp in day:
            slot = grp.get('slot', 'word_multi')
            items = []
            for ref in grp['items']:
                q = conn.execute('SELECT id, blocks_json, answer_blocks_json, analysis_blocks_json '
                                 'FROM question WHERE id=?', (ref['qid'],)).fetchone()
                if q is None:
                    sys.exit('🔴 题 %s 库里不存在' % ref['qid'])
                it = adapt(dict(q), slot)
                if ref.get('lv'):
                    it['lv'] = ref['lv']
                items.append(it)
            groups.append({'name': grp['name'], 'slot': slot, 'items': items,
                           **({'weight': grp['weight']} if grp.get('weight') else {})})
        days.append(groups)
    conn.close()

    ctx = dict(spec.get('ctx') or {})
    ctx['renderer'] = renderers.get('math')
    out_dir = a.out_dir or str(ROOT / '产物' / '打卡' / spec['stem'])
    L = layouts.get('sync_kaodian')
    report = core.render_book(out_dir=out_dir, stem=spec['stem'],
                              title=spec['stem'], layout=L, days=days, ctx=ctx,
                              expect_pages=len(days), png=a.png, pt=a.pt)
    print('🟢 出件完成 →', out_dir)
    return report


if __name__ == '__main__':
    main()
