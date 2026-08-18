# -*- coding: utf-8 -*-
"""
⑤ 验收：导出还原逐题比对 + 人工抽查底稿。
   比对三方：原件 docx 段落流（事实源） ↔ 切出的题卡 ↔ 导出 PDF 的文字层/图对象。
   🔴 只报事实，不修饰。
"""
import sys, os, re, json, unicodedata
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')
import fitz

ROOT = J.ROOT
OUT = os.path.join(ROOT, '产物')
SRC = os.path.join(ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
SRC_PDF = os.path.join(ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.pdf')
EXP_PDF = os.path.join(OUT, '导出-题目卷.pdf')

R = json.load(open(os.path.join(OUT, '切割结果.json'), encoding='utf-8'))
cards, tree, stats = R['题卡'], R['归属树'], R['统计']

WS = set(' \t\r\n　\xa0​   ')
def vis(s):
    return Counter(c for c in (s or '') if c not in WS)
def flat(s):
    return ''.join(c for c in (s or '') if c not in WS)

# ---------- 原件事实源：docx 单元段落流 ----------
stream, _ = J.build_stream(SRC, os.path.join(ROOT, '_tmp_img_book3'))
a, b = stats['段区间']
src_nodes = stream[a:b]
src_text = '\n'.join(J.stream_text(nd) for nd in src_nodes)
src_fig = sum(J.count_figs(nd) for nd in src_nodes)

# ---------- 导出件 ----------
ed = fitz.open(EXP_PDF)
exp_text = '\n'.join(ed[i].get_text() for i in range(ed.page_count))
exp_fig = sum(len(ed[i].get_images(full=True)) for i in range(ed.page_count))

# 🔴 期望式（逐项列明，不含糊）：
#    导出件字符 == 原件单元字符 － 声明丢弃的单元内考点小目录 ＋ 我方版面装饰
# ① 声明丢弃：单元正文开头重复一遍的「考点小目录」（与其后正文的考点头逐字重复）
DROP_TOC = Counter()
for t in stats['剪掉的考点小目录行']:
    DROP_TOC += vis(t)
# ② 我方装饰：副标题行 + 页脚行（h1 单元名原件本来就有，不算装饰）
ADDED = Counter()
for s in ['%s ｜ 题目卷（不含答案）｜ 由块流渲染还原' % tree['书'],
          '导出还原件 · PRD-001 · 源：%s（段 %d-%d）· 题 %d 道 · 图 %d 张'
          % (stats['原件'], a, b, len(cards), sum(c['图数'] for c in cards))]:
    ADDED += vis(s)

src_c = vis(src_text)
exp_c = vis(exp_text)
expect_c = src_c - DROP_TOC + ADDED
lost = expect_c - exp_c
extra = exp_c - expect_c

print('== ④ 导出保真（字符层）==')
print('  原件单元 %d 个可见字符；声明丢弃(单元内考点小目录) %d；我方版面装饰 %d'
      % (sum(src_c.values()), sum(DROP_TOC.values()), sum(ADDED.values())))
print('  期望导出 %d 个 / 实测导出 %d 个' % (sum(expect_c.values()), sum(exp_c.values())))
print('  丢字 %d 个：%s' % (sum(lost.values()), dict(list(lost.items())[:15])))
print('  多字 %d 个：%s' % (sum(extra.values()), dict(list(extra.items())[:15])))
fidelity = 1 - (sum(lost.values()) + sum(extra.values())) / max(1, sum(expect_c.values()))
print('  字符保真率 = %.4f' % fidelity)
print('== ④ 导出保真（图层）==')
print('  原件 %d 图槽 / 导出 PDF %d 个图对象  %s' % (src_fig, exp_fig, 'OK' if src_fig == exp_fig else 'MISMATCH'))

# ---------- 逐题：题面是否在导出件中原样可寻 ----------
exp_flat = flat(exp_text)
per_q = []
for c in cards:
    body = '\n'.join(b.get('text', '') for b in c['块流'] if b['type'] == 'text')
    # 导出件里题面会带回栏目前缀/标题/小问号，故只查题面主体的连续片段
    frags = [f for f in (flat(x) for x in body.split('\n')) if len(f) >= 6]
    miss = [f for f in frags if f not in exp_flat]
    per_q.append({'qid': c['qid'], '片段数': len(frags), '未命中': miss})
q_ok = [x for x in per_q if not x['未命中']]
print('== ④ 导出保真（逐题）==')
print('  题面片段全部原样出现在导出件：%d/%d 题' % (len(q_ok), len(cards)))
for x in per_q:
    if x['未命中']:
        print('   ✗ %s 未命中 %d 片段：%s' % (x['qid'], len(x['未命中']), x['未命中'][:2]))

# ---------- 人工抽查底稿：逐题三方对照 ----------
lines = []
lines.append('# 人工抽查底稿 · 第五单元 三角形·特性篇（全 39 题逐题核对）\n')
lines.append('> PRD-001 步骤⑤ 产物 ｜ 2026-08-18 ｜ 生成脚本 `脚本/6_比对与抽查.py`')
lines.append('> 三方对照：**原件**（docx 段落流原文，事实源） / **切出**（题卡块流 + 元信息） / **导出**（题目卷 PDF 文字层是否原样命中）')
lines.append('> 🔴 "原件"列是机器从 docx 直读的原字，未经任何人工誊抄。\n')
lines.append('| # | qid | 归属（机器预挂） | 栏目/配对 | 原件段 | 判定 |')
lines.append('|---|---|---|---|---|---|')

def clip(s, n=140):
    s = (s or '').replace('\n', ' ⏎ ').replace('|', '｜')
    return s[:n] + ('…' if len(s) > n else '')

detail = []
for i, c in enumerate(cards, 1):
    s0, s1 = c['para区间']
    raw = '\n'.join(J.stream_text(nd) for nd in stream[s0:s1])
    rawfig = sum(J.count_figs(nd) for nd in stream[s0:s1])
    pq = next(x for x in per_q if x['qid'] == c['qid'])
    ok = (not pq['未命中'])
    verdict = '✅' if ok and not c['低置信'] else ('⚠️低置信' if ok else '❌导出缺片段')
    lines.append('| %d | %s | 【考点%s】%s | %s%s%s | %s | %s |'
                 % (i, c['qid'], c['归属']['考点序'], c['归属']['考点名'],
                    c['栏目'], c['栏目序号'] or '',
                    ('→' + c['配对典例']) if c['配对典例'] else '',
                    clip(raw, 90), verdict))
    body = '\n'.join(b.get('text', '') for b in c['块流'] if b['type'] == 'text')
    detail.append(
        '### %d. %s ｜ 【考点%s】%s ｜ %s%s%s\n\n'
        '- **原件原文**（docx 段 %d-%d，图 %d 张）：\n\n```\n%s\n```\n'
        '- **切出题面**（元信息已剥离，图 %d 张）：\n\n```\n%s\n```\n'
        '- **抽离账**：%s\n'
        '- **题型判定**：%s ｜ **归属**：%s → 【考点%s】%s ｜ **配对**：%s\n'
        '- **导出比对**：%s\n'
        % (i, c['qid'], c['归属']['考点序'], c['归属']['考点名'],
           c['栏目'], c['栏目序号'] or '',
           ('（配 %s）' % c['配对典例']) if c['配对典例'] else '',
           s0, s1, rawfig, raw.strip() or '（本段无文字，纯图）',
           c['图数'], body.strip() or '（无文字）',
           '；'.join('%s=`%s`' % (l['类'], l['原文']) for l in c['剥离账']) or '无',
           c['题型'], c['归属']['单元'], c['归属']['考点序'], c['归属']['考点名'],
           c['配对典例'] or '（本身是典例）',
           '题面 %d 个片段全部原样命中导出 PDF' % pq['片段数'] if ok
           else '❌ 未命中片段：%s' % pq['未命中'])
        + ('- **低置信**：%s\n' % '；'.join('%s=%s(%s)' % (x['项'], x['值'], x['置信'])
                                            for x in c['低置信']) if c['低置信'] else ''))

lines.append('\n---\n\n## 逐题详录（原件 / 切出 / 抽离账 三方对照）\n')
lines.extend(detail)
open(os.path.join(OUT, '人工抽查底稿.md'), 'w', encoding='utf-8').write('\n'.join(lines))
print('\n人工抽查底稿.md 写好（%d 题逐题）' % len(cards))

# ---------- 汇总 JSON ----------
summary = {
    '导出保真': {'原件字符': sum(src_c.values()), '声明丢弃(单元内小目录)': sum(DROP_TOC.values()),
                 '我方版面装饰': sum(ADDED.values()),
                 '期望导出字符': sum(expect_c.values()), '实测导出字符': sum(exp_c.values()),
                 '字符保真率': round(fidelity, 6),
                 '丢字': dict(lost), '多字': dict(extra),
                 '原件图槽': src_fig, '导出图对象': exp_fig,
                 '逐题片段全命中': '%d/%d' % (len(q_ok), len(cards)),
                 '导出页数': ed.page_count},
    '逐题': per_q,
}
json.dump(summary, open(os.path.join(OUT, '_比对结果.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
