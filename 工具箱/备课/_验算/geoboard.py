# -*- coding: utf-8 -*-
"""钉板（geoboard）平行四边形计数 —— 思维题三关全枚举验算。
口径：顶点必须落在钉子上；位置不同即算不同；四点不共线（非退化）。"""
import itertools
from collections import defaultdict


def pts(n):
    return [(x, y) for x in range(n) for y in range(n)]


def count_parallelograms(n):
    """对角线互相平分法：同一中点的两条「对角线」两两配对，剔除四点共线。"""
    P = pts(n)
    by_mid = defaultdict(list)
    for a, b in itertools.combinations(P, 2):
        by_mid[(a[0] + b[0], a[1] + b[1])].append((a, b))
    out = []
    for mid, pairs in by_mid.items():
        for (a, b), (c, d) in itertools.combinations(pairs, 2):
            # 四点共线则退化
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0:
                continue
            out.append(frozenset([a, b, c, d]))
    assert len(out) == len(set(out))
    return out


def side_vectors(quad):
    """把 4 点还原成平行四边形的两条邻边向量（用于分类）。"""
    q = sorted(quad)
    a = q[0]
    rest = q[1:]
    for i in range(3):
        b, c = rest[i], rest[(i + 1) % 3]
        d = rest[(i + 2) % 3]
        if (b[0] + c[0], b[1] + c[1]) == (a[0] + d[0], a[1] + d[1]):
            return (b[0] - a[0], b[1] - a[1]), (c[0] - a[0], c[1] - a[1])
    return None


def classify(quad):
    v, w = side_vectors(quad)
    dot = v[0] * w[0] + v[1] * w[1]
    l1 = v[0] ** 2 + v[1] ** 2
    l2 = w[0] ** 2 + w[1] ** 2
    axis = (v[0] == 0 or v[1] == 0) and (w[0] == 0 or w[1] == 0)
    if dot == 0 and l1 == l2:
        return "正方形" + ("(轴正)" if axis else "(斜)")
    if dot == 0:
        return "长方形" + ("(轴正)" if axis else "(斜)")
    return "一般平四" + ("" if not axis else "(轴正?)")


for n in (3, 4):
    quads = count_parallelograms(n)
    kinds = defaultdict(int)
    for q in quads:
        kinds[classify(q)] += 1
    print(f"══ {n}×{n} 钉板（{n*n} 个钉子）══")
    print(f"  平行四边形总数（含长方形正方形）= {len(quads)}")
    for k in sorted(kinds):
        print(f"    {k}: {kinds[k]}")
    rect = sum(v for k, v in kinds.items() if "长方形" in k or "正方形" in k)
    rect_axis = sum(v for k, v in kinds.items() if ("长方形(轴正)" in k or "正方形(轴正)" in k))
    sq = sum(v for k, v in kinds.items() if "正方形" in k)
    print(f"  → 长方形(含正方形) 共 {rect}，其中横平竖直 {rect_axis}")
    print(f"  → 正方形 共 {sq}")
    print()

# 关1 校核：轴正长方形 = C(n,2)^2
from math import comb
for n in (3, 4):
    print(f"{n}×{n} 轴正长方形理论值 C({n},2)^2 =", comb(n, 2) ** 2)
