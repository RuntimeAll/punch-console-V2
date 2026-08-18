# -*- coding: utf-8 -*-
"""
附加探测（为②模板规则服务）：答案版 ↔ 原卷版 是否结构同构，答案能否确定性归到题。
🔴 只探测不入库；结论写进 模板规则.md / 切割报告.md。
"""
import sys, os, re, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')

ROOT = J.ROOT
OUT = os.path.join(ROOT, '产物')
SRC = os.path.join(ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
ANS = os.path.join(ROOT, '原料', '答案', '第五单元三角形·特性篇【八大考点】（答案版）人教版.docx')
R = json.load(open(os.path.join(OUT, '切割结果.json'), encoding='utf-8'))
stats = R['统计']
# 🔴 本系列答案标记**两态**（2026-08-18 实测）：带括号的【答案】31 处 + 裸「解析：」8 处
RE_ANS = re.compile(r'^[\s　]*(?:【(?:答案|解析|详解|分析|点评)】|(?:答案|解析|详解|分析)[：:])')

def mark_seq(stream, lo=0, hi=None):
    hi = hi if hi is not None else len(stream)
    out = []
    for nd in stream[lo:hi]:
        k, meta = J.classify(nd['head'])
        if k in ('kp', 'explain', 'example', 'practice'):
            out.append((k, meta.get('no') or '', (meta.get('title') or '').rstrip('。．')))
    return out

s_book, _ = J.build_stream(SRC, os.path.join(ROOT, '_tmp_img_book4'))
s_ans, ansbase = J.build_stream(ANS, os.path.join(ROOT, '_tmp_img_ans'))
a, b = stats['段区间']
seq_q = mark_seq(s_book, a, b)
seq_a = mark_seq(s_ans)

print('原卷版标记序列 %d 条 / 答案版 %d 条' % (len(seq_q), len(seq_a)))
# 剪掉原卷版单元内考点小目录（连续的 kp 且后面没有 explain/题）
def prune_toc(seq):
    out = []
    for i, it in enumerate(seq):
        if it[0] == 'kp':
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            if nxt and nxt[0] == 'kp':
                continue
        out.append(it)
    return out
seq_q2 = prune_toc(seq_q)
print('剪掉小目录后：原卷 %d 条' % len(seq_q2))

same = seq_q2 == seq_a
kn_q = [(k, n) for k, n, t in seq_q2]
kn_a = [(k, n) for k, n, t in seq_a]
same_kn = kn_q == kn_a
print('序列完全一致（含标题）：', same)
print('序列一致（只看 类型+编号，配对实际用这个键）：', same_kn,
      ' %d/%d' % (sum(1 for x, y in zip(kn_q, kn_a) if x == y), len(kn_q)))
if not same:
    n = min(len(seq_q2), len(seq_a))
    diff = [(i, seq_q2[i], seq_a[i]) for i in range(n) if seq_q2[i] != seq_a[i]]
    print('首 8 处不一致：')
    for d in diff[:8]:
        print('  #%d 原卷=%s ｜ 答案=%s' % d)
    print('不一致条数 %d / %d' % (len(diff), n))
    if len(seq_q2) != len(seq_a):
        print('长度不同：原卷 %d vs 答案 %d' % (len(seq_q2), len(seq_a)))

# 答案版：每个题段里有几个【答案】块
segs, cur = [], None
for nd in s_ans:
    k, meta = J.classify(nd['head'])
    if k in ('kp', 'explain', 'example', 'practice', 'unit'):
        cur = {'kind': k, 'meta': meta, 'ans': 0, 'nodes': 0, 'fig': 0, 'i': nd['i']}
        segs.append(cur)
    if cur is not None:
        cur['nodes'] += 1
        cur['fig'] += J.count_figs(nd)
        if RE_ANS.match(J.stream_text(nd)):
            cur['ans'] += 1
qsegs = [s for s in segs if s['kind'] in ('example', 'practice')]
have = [s for s in qsegs if s['ans'] >= 1]
multi = [s for s in qsegs if s['ans'] > 1]
print('答案版题段 %d 个；带【答案】块 %d 个（%.1f%%）；多于 1 个答案块 %d 个'
      % (len(qsegs), len(have), 100.0 * len(have) / max(1, len(qsegs)), len(multi)))
missing = [(s['i'], s['meta'].get('label'), s['meta'].get('no')) for s in qsegs if s['ans'] == 0]
print('无【答案】块的题段：', missing)
print('答案版图槽 %d（原卷同单元 %d）' % (ansbase['fig'], stats['基准']['图槽']))

json.dump({'原卷标记序列条数': len(seq_q2), '答案标记序列条数': len(seq_a),
           '序列完全一致(含标题)': same, '序列一致(类型+编号)': same_kn,
           '答案版题段': len(qsegs), '带答案块': len(have), '多答案块': len(multi),
           '无答案块': missing, '答案版图槽': ansbase['fig']},
          open(os.path.join(OUT, '_答案版同构.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
