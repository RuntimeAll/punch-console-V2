# -*- coding: utf-8 -*-
"""第9课思维题（小正方体教具·露在外面的面）验算：
露在外面的面数 S = 6n - 2c，c = 面对面贴合的对数（拿在手上看，六个方向全算）。"""
import math

DIRS = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]


def surface(cells):
    cells = set(cells)
    return sum(1 for c in cells for d in DIRS
               if (c[0] + d[0], c[1] + d[1], c[2] + d[2]) not in cells)


def box(a, b, c):
    return {(x, y, z) for x in range(a) for y in range(b) for z in range(c)}


def norm(s):
    xs = [p[0] for p in s]; ys = [p[1] for p in s]; zs = [p[2] for p in s]
    return frozenset((x - min(xs), y - min(ys), z - min(zs)) for x, y, z in s)


def grow(n):
    """按增长法枚举 n 连块（平移归一），返回集合。"""
    cur = {norm({(0, 0, 0)})}
    for _ in range(n - 1):
        nxt = set()
        for s in cur:
            for c in s:
                for d in DIRS:
                    p = (c[0] + d[0], c[1] + d[1], c[2] + d[2])
                    if p not in s:
                        nxt.add(norm(s | {p}))
        cur = nxt
    return cur


print("=" * 56)
print("关1：4 块连成一条直线")
print("  露在外面 =", surface(box(4, 1, 1)), " | 6×4－2×3 =", 6 * 4 - 2 * 3)

print("\n关2：8 块两种摆法")
print("  一条直线 1×1×8 :", surface(box(8, 1, 1)), " | 6×8－2×7 =", 6 * 8 - 2 * 7)
print("  大正方体 2×2×2 :", surface(box(2, 2, 2)), " | 6×8－2×12 =", 6 * 8 - 2 * 12)

print("\n关3：12 块摆成长方体的全部摆法")
shapes = []
for a in range(1, 13):
    for b in range(a, 13):
        if (a * b) and 12 % (a * b) == 0:
            c = 12 // (a * b)
            if c >= b:
                shapes.append((a, b, c))
for a, b, c in shapes:
    print(f"  {a}×{b}×{c} : 露在外面 {surface(box(a, b, c))} 个面"
          f"  （表面积公式 2({a}×{b}+{a}×{c}+{b}×{c}) = {2*(a*b+a*c+b*c)}）")
print("  摆法种数 =", len(shapes))


def lw_lower_bound(n):
    """投影下界：某方向朝外的面数 ≥ 该方向投影面积（每根柱子至少一头露在外面），
    故 S ≥ 2(Axy+Ayz+Axz)；又 Loomis–Whitney: Axy·Ayz·Axz ≥ n²。
    枚举三整数投影面积组合取最小可行 S（偶数）。"""
    best = None
    for a in range(1, n + 1):
        for b in range(a, n + 1):
            for c in range(b, n + 1):
                if a * b * c >= n * n:
                    s = 2 * (a + b + c)
                    if best is None or s < best:
                        best = s
    return best


print("\n  不摆成长方体能否更少？")
print("   投影下界 n=12 →", lw_lower_bound(12), "；2×2×3 实际取到 32 → **32 就是全局最少**")

print("\n下界与暴力枚举对照（增长法全枚举 n=4..7）")
for n in range(4, 8):
    ss = grow(n)
    lo = min(surface(s) for s in ss)
    hi = max(surface(s) for s in ss)
    print(f"  n={n}（{len(ss)} 种形状）: 暴力最小 {lo} ≥ 下界 {lw_lower_bound(n)}"
          f" [{'OK' if lo >= lw_lower_bound(n) else 'BROKEN'}]"
          f" | 暴力最大 {hi} vs 树状 6n－2(n－1) = {6 * n - 2 * (n - 1)}"
          f" [{'OK' if hi == 6 * n - 2 * (n - 1) else 'MISMATCH'}]")
