# -*- coding: utf-8 -*-
"""扫全书边界形态：为②模板规则提供实证（不切题，只统计）。"""
import sys, os, re, json
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')

SRC = os.path.join(J.ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
stream, base = J.build_stream(SRC, os.path.join(J.ROOT, '_tmp_img_book'))

marks = []
for nd in stream:
    k, meta = J.classify(nd['head'])
    marks.append((nd['i'], k, meta))

# 只看正文（跳过目录：目录 = 空标记连片，正文从第一个 explain 之前的 unit 起）
first_explain = next(i for i, (p, k, m) in enumerate(marks) if k == 'explain')
# 正文起点 = first_explain 之前最近的 unit
body_start = max(i for i, (p, k, m) in enumerate(marks[:first_explain]) if k == 'unit')

stat = Counter()
issues = defaultdict(list)
cur_kp = None
kp_seq = []          # 当前考点内的标记序列
kp_meta = None

def flush_kp():
    global kp_seq, kp_meta
    if kp_meta is None:
        return
    kinds = [k for _, k, _ in kp_seq]
    if not kinds:            # 目录里的空考点行，剪掉不统计
        kp_seq = []
        return
    stat['考点节(非空)'] += 1
    if kinds.count('explain') != 1:
        issues['方法点拨数≠1'].append((kp_meta, kinds.count('explain')))
    # 第一个题标记之前是否有方法点拨
    if 'example' in kinds and 'practice' in kinds:
        if kinds.index('practice') < kinds.index('example'):
            issues['练习出现在首个典例之前'].append(kp_meta)
    if 'example' not in kinds:
        issues['考点无典例'].append(kp_meta)
    if 'practice' not in kinds:
        issues['考点无练习'].append(kp_meta)
    # 典例/练习编号形态
    ex_nos = [m.get('no') for _, k, m in kp_seq if k == 'example']
    pr_nos = [m.get('no') for _, k, m in kp_seq if k == 'practice']
    stat['典例编号形态:' + ('全空' if all(n == '' for n in ex_nos) else
                          ('全有号' if all(n for n in ex_nos) else '混合'))] += 1
    stat['练习编号形态:' + ('全空' if all(n == '' for n in pr_nos) else
                          ('全有号' if all(n for n in pr_nos) else '混合'))] += 1
    kp_seq = []

for idx in range(body_start, len(marks)):
    p, k, m = marks[idx]
    if k in ('unit', 'kp'):
        flush_kp()
        if k == 'kp':
            kp_meta = (p, m.get('title'))
        else:
            kp_meta = None
    elif k in ('explain', 'example', 'practice') and kp_meta is not None:
        kp_seq.append((p, k, m))
flush_kp()

# 题标记段后的续行形态：题面是否在标记同段（inline）还是下一段
inline_head = tail_head = 0
head_only = 0
for i, (p, k, m) in enumerate(marks):
    if k not in ('example', 'practice'):
        continue
    title = (m.get('title') or '').strip()
    if title:
        inline_head += 1
    else:
        head_only += 1
# 方法点拨里是否有图（老区 §9 遗留项：explain 图不落库）
explain_fig = 0
for i, (p, k, m) in enumerate(marks):
    if k != 'explain':
        continue
    nxt = marks[i + 1][0] if i + 1 < len(marks) else len(stream)
    f = sum(J.count_figs(stream[j]) for j in range(p, nxt))
    if f:
        explain_fig += f

print('== 考点节形态 ==')
for k, v in sorted(stat.items()):
    print(' ', k, v)
print('== 异常 ==')
for k, v in issues.items():
    print(' ', k, len(v), v[:5])
print('== 题标记 ==')
print('  标记同段即带题面(inline):', inline_head, ' 标记独占段(题面在下一段):', head_only)
print('  方法点拨区内图数(老区遗留项:explain图不落库):', explain_fig)
