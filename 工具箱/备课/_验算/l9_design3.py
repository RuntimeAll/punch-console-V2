# -*- coding: utf-8 -*-
"""第9课·观察物体 —— 10 题数据定稿 v2 + 全量枚举验算。"""
import sys, itertools
from collections import deque
sys.path.insert(0, r"D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\_卷面生成工具")
import cube3d as c3
V = c3.views_of


def build(hmap):
    """h[(x,y)] → 实心块集合。"""
    return {(x, y, z) for (x, y), h in hmap.items() for z in range(h)}


def solve(top_cells, front=None, left=None, maxh=4):
    cols = max(c for c, r in top_cells) + 1
    order = sorted(top_cells)
    sols = []
    for hs in itertools.product(range(1, maxh + 1), repeat=len(order)):
        s = set()
        for (c, r), h in zip(order, hs):
            for z in range(h):
                s.add((c, r, z))
        v = V(s)
        if front is not None and frozenset(v["front"]) != frozenset(front):
            continue
        if left is not None and frozenset(v["left"]) != frozenset(left):
            continue
        if frozenset(v["top"]) != frozenset(top_cells):
            continue
        sols.append(s)
    ns = [len(s) for s in sols]
    return (min(ns), max(ns), len(sols)) if sols else (None, None, 0)


print("═══ 题3：添 1 块保持「从前面看」不变 ═══")
Q3 = {(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 0, 1)}


def add_positions(cells, keep="front"):
    cells = set(cells)
    base = frozenset(V(cells)[keep])
    cand = set()
    for (x, y, z) in cells:
        for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            p = (x + d[0], y + d[1], z + d[2])
            if p in cells or p[2] < 0:
                continue
            if p[2] > 0 and (p[0], p[1], p[2] - 1) not in cells:
                continue
            cand.add(p)
    good = [p for p in sorted(cand) if frozenset(V(cells | {p})[keep]) == base]
    return good, sorted(cand)


g3, all3 = add_positions(Q3)
print("候选位", len(all3), "→ 合法", len(g3), g3)

print("\n═══ 题5：俯视图 + 主视图 → 最少/最多 ═══")
H5 = {(0, 0): 3, (1, 0): 2, (2, 0): 1, (0, 1): 3, (1, 1): 2, (2, 1): 1}
S5 = build(H5); v5 = V(S5)
print("俯视", sorted(v5["top"]), "主视", sorted(v5["front"]))
print("最少/最多/解数:", solve(v5["top"], front=v5["front"]))

print("\n═══ 题6：三视图全给 → 最多/最少 ═══")
H6 = {(0, 0): 3, (1, 0): 2, (2, 0): 2,
      (0, 1): 2, (1, 1): 2, (2, 1): 1,
      (0, 2): 1, (1, 2): 1, (2, 2): 1}
S6 = build(H6); v6 = V(S6)
print("俯视", sorted(v6["top"]), "\n主视", sorted(v6["front"]), "\n左视", sorted(v6["left"]))
print("最少/最多/解数:", solve(v6["top"], front=v6["front"], left=v6["left"]))

print("\n═══ 题10：墙角堆最多搬走 ═══")
H10 = {(x, y): (3 if x == 0 else 2 if x == 1 else 1) for x in range(3) for y in range(3)}
S10 = build(H10); v10 = V(S10)
keys = sorted(H10)
best = None
for hs in itertools.product(*[range(1, H10[k] + 1) for k in keys]):
    s = build(dict(zip(keys, hs)))
    vv = V(s)
    if frozenset(vv["top"]) == frozenset(v10["top"]) and frozenset(vv["front"]) == frozenset(v10["front"]):
        best = len(s) if best is None else min(best, len(s))
print("原有", len(S10), "最少保留", best, "最多搬走", len(S10) - best)

print("\n═══ 题11：拼接识别 ═══")
P = {"A": {(0, 0, 0), (1, 0, 0), (0, 1, 0)},
     "B": {(0, 0, 0), (0, 0, 1), (1, 0, 0)},
     "C": {(0, 0, 0), (1, 0, 0), (2, 0, 0)}}
T = P["A"] | {(1, 1, 0), (1, 1, 1), (2, 1, 0)}
print("目标", sorted(T), "块数", len(T))


def can_tile(p1, p2, target):
    rng = range(-3, 4)
    for a in itertools.product(rng, rng, rng):
        A = {(x + a[0], y + a[1], z + a[2]) for x, y, z in p1}
        if not A <= target:
            continue
        rest = target - A
        for b in itertools.product(rng, rng, rng):
            if {(x + b[0], y + b[1], z + b[2]) for x, y, z in p2} == rest:
                return True
    return False


for k1, k2 in itertools.combinations(P, 2):
    print(f"  {k1}+{k2}:", can_tile(P[k1], P[k2], T))
