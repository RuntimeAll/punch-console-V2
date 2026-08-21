# -*- coding: utf-8 -*-
"""把 3×3 钉板整体「推斜」成平行四边形阵后：平行四边形个数是否仍为 22？正方形还剩几个？"""
import itertools
from collections import defaultdict
from fractions import Fraction as F

SKEW = F(45, 100)          # 与卷面图一致的推斜量 x' = x + 0.45y


def pts_skew(n, s):
    return [(F(x) + s * y, F(y)) for x in range(n) for y in range(n)]


def count_par(P):
    mids = defaultdict(list)
    for a, b in itertools.combinations(P, 2):
        mids[(a[0] + b[0], a[1] + b[1])].append((a, b))
    tot = 0
    for pairs in mids.values():
        for (a, b), (c, d) in itertools.combinations(pairs, 2):
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) != 0:
                tot += 1
    return tot


def count_sq(P):
    """四点成正方形：邻边垂直且等长（精确有理数运算，无浮点误差）。"""
    S = set(P)
    out = set()
    for a, b in itertools.combinations(P, 2):
        vx, vy = b[0] - a[0], b[1] - a[1]
        for (px, py) in ((-vy, vx), (vy, -vx)):
            c, d = (b[0] + px, b[1] + py), (a[0] + px, a[1] + py)
            if c in S and d in S:
                out.add(frozenset((a, b, c, d)))
    return len(out)


P0 = pts_skew(3, F(0))
P1 = pts_skew(3, SKEW)
print("正阵 3×3 ：平行四边形", count_par(P0), "｜正方形", count_sq(P0))
print("斜阵 3×3 ：平行四边形", count_par(P1), "｜正方形", count_sq(P1), f"(skew={float(SKEW)})")

print("\n换几个推斜量看正方形是否都为 0：")
for s in (F(1, 4), F(1, 3), F(45, 100), F(1, 2), F(3, 5), F(7, 10), F(1, 1)):
    Pk = pts_skew(3, s)
    print(f"  skew={float(s):<5} 平四 {count_par(Pk):<3} 正方形 {count_sq(Pk)}")
