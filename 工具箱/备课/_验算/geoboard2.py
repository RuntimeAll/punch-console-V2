# -*- coding: utf-8 -*-
"""钉板计数细目：3×3 按「对角线交点」分类的完整账；4×4 长方形/正方形明细。"""
import itertools
from collections import defaultdict
from math import comb


def pts(n):
    return [(x, y) for x in range(n) for y in range(n)]


def by_center(n):
    P = set(pts(n))
    mids = defaultdict(list)
    for a, b in itertools.combinations(sorted(P), 2):
        mids[(a[0] + b[0], a[1] + b[1])].append((a, b))
    rows = []
    total = 0
    for mid in sorted(mids):
        pairs = mids[mid]
        good = 0
        for (a, b), (c, d) in itertools.combinations(pairs, 2):
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) != 0:
                good += 1
        if good:
            rows.append((f"({mid[0]/2:g},{mid[1]/2:g})", len(pairs), comb(len(pairs), 2), good))
            total += good
    return rows, total


rows, total = by_center(3)
print("══ 3×3 钉板：按「两条对角线的交点」分类 ══")
print(" 交点位置        过它的点对数 k   C(k,2)   去掉四点共线后")
for c, k, ck, g in rows:
    print(f"  {c:<12} {k:^12} {ck:^8} {g:^10}")
print(f"  合计 = {total} 个平行四边形")

# 分组归纳（对称性）
grp = defaultdict(list)
for c, k, ck, g in rows:
    grp[(k, g)].append(c)
print("\n 归纳（同类交点合并）：")
for (k, g), cs in sorted(grp.items(), reverse=True):
    print(f"  过它的点对 {k} 对 → 贡献 {g} 个 ｜ 共 {len(cs)} 个位置：{', '.join(cs)}")
    print(f"     小计 {g} × {len(cs)} = {g * len(cs)}")

print("\n══ 3×3 正方形明细 ══")
P = pts(3)
sqs = []
for a, b, c, d in itertools.combinations(P, 4):
    for perm in itertools.permutations([b, c, d]):
        p, q, r = perm
        v = (p[0] - a[0], p[1] - a[1])
        w = (r[0] - a[0], r[1] - a[1])
        if (a[0] + q[0], a[1] + q[1]) != (p[0] + r[0], p[1] + r[1]):
            continue
        if v[0] * w[0] + v[1] * w[1] == 0 and v[0] ** 2 + v[1] ** 2 == w[0] ** 2 + w[1] ** 2 \
                and (v[0] or v[1]):
            sqs.append((tuple(sorted([a, p, q, r])), v, w))
            break
seen = set()
for q, v, w in sqs:
    if q in seen:
        continue
    seen.add(q)
    tilt = "斜" if (v[0] and v[1]) else "轴正"
    print(f"  {q}  边向量{v}/{w}  [{tilt}]")
print(f"  共 {len(seen)} 个")

print("\n══ 4×4 钉板 ══")
print("  横平竖直长方形 C(4,2)^2 =", comb(4, 2) ** 2)
P4 = pts(4)
cnt_sq, tilt_sq = 0, []
for a, b, c, d in itertools.combinations(P4, 4):
    done = False
    for perm in itertools.permutations([b, c, d]):
        p, q, r = perm
        v = (p[0] - a[0], p[1] - a[1])
        w = (r[0] - a[0], r[1] - a[1])
        if (a[0] + q[0], a[1] + q[1]) != (p[0] + r[0], p[1] + r[1]):
            continue
        if v[0] * w[0] + v[1] * w[1] == 0 and v[0] ** 2 + v[1] ** 2 == w[0] ** 2 + w[1] ** 2 \
                and (v[0] or v[1]):
            cnt_sq += 1
            if v[0] and v[1]:
                tilt_sq.append((tuple(sorted([a, p, q, r])), v))
            done = True
            break
    if done:
        continue
print("  正方形总数 =", cnt_sq, "｜其中斜的", len(tilt_sq), "个")
for q, v in tilt_sq:
    print("    斜正方形", q, "边向量", v)
