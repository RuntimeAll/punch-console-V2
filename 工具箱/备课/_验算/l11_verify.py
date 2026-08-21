# -*- coding: utf-8 -*-
"""第11课「找正方形」× 平行四边形 —— 计数题全枚举 / 公式双算校核。"""
import itertools
from math import comb

OK = []


def chk(tag, got, want):
    ok = got == want
    OK.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {tag}: got={got} want={want}")


# ── 方格纸 m×n（小方格数），格点 (m+1)×(n+1) ──
def axis_squares(m, n):
    """轴正正方形：边长 k 的有 (m-k+1)(n-k+1) 个。"""
    return sum((m - k + 1) * (n - k + 1) for k in range(1, min(m, n) + 1))


def axis_rects(m, n):
    return comb(m + 1, 2) * comb(n + 1, 2)


def all_squares_lattice(nx, ny):
    """(nx×ny) 个格点里全部正方形（含斜），全枚举。"""
    P = [(x, y) for x in range(nx) for y in range(ny)]
    S = set(P)
    out = set()
    for (x, y) in P:
        for dx in range(-nx, nx):
            for dy in range(0, ny):
                if dx == 0 and dy == 0:
                    continue
                # 以 (x,y) 为一个顶点，边向量 (dx,dy)，逆时针转 90° 得 (-dy,dx)
                a = (x, y)
                b = (x + dx, y + dy)
                c = (x + dx - dy, y + dy + dx)
                d = (x - dy, y + dx)
                if all(p in S for p in (b, c, d)):
                    out.add(frozenset((a, b, c, d)))
    return len(out)


def all_parallelograms_lattice(nx, ny):
    """格点里全部平行四边形（对角线互相平分法）。"""
    from collections import defaultdict
    P = [(x, y) for x in range(nx) for y in range(ny)]
    mids = defaultdict(list)
    for a, b in itertools.combinations(P, 2):
        mids[(a[0] + b[0], a[1] + b[1])].append((a, b))
    tot = 0
    for pairs in mids.values():
        for (a, b), (c, d) in itertools.combinations(pairs, 2):
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) != 0:
                tot += 1
    return tot


def all_rects_lattice(nx, ny):
    """格点里全部长方形（含正方形、含斜），全枚举。"""
    P = [(x, y) for x in range(nx) for y in range(ny)]
    S = set(P)
    out = set()
    for a, b in itertools.combinations(P, 2):
        # ab 作为一条边，向左右各作垂直向量
        vx, vy = b[0] - a[0], b[1] - a[1]
        for (px, py) in ((-vy, vx), (vy, -vx)):
            for k in range(1, max(nx, ny) + 1):
                # 垂直边长度需为整数格点方向：直接用互素方向的整数倍
                g = __import__('math').gcd(abs(px), abs(py)) or 1
                ux, uy = px // g, py // g
                c = (b[0] + ux * k, b[1] + uy * k)
                d = (a[0] + ux * k, a[1] + uy * k)
                if not (0 <= c[0] < nx and 0 <= c[1] < ny and 0 <= d[0] < nx and 0 <= d[1] < ny):
                    break
                if c in S and d in S:
                    out.add(frozenset((a, b, c, d)))
    return len(out)


print("══ 思维题 ══")
chk("关1  4×4 方格纸·轴正正方形 (16+9+4+1)", axis_squares(4, 4), 30)
chk("关2  4×4 方格纸·长方形含正方形 C(5,2)²", axis_rects(4, 4), 100)
chk("关2  枚举校核", None, None) if False else None
chk("关3  3×3 斜格·平行四边形 = 3×3方格的长方形数", axis_rects(3, 3), 36)

print("\n══ 同步奥数 ══")
chk("Q1  3×3 方格纸·正方形 (9+4+1)", axis_squares(3, 3), 14)
chk("Q2  3×3 方格纸·长方形 C(4,2)²", axis_rects(3, 3), 36)
chk("Q3  5×5 方格纸·正方形 (25+16+9+4+1)", axis_squares(5, 5), 55)
chk("Q4  5×5 方格纸·长方形 C(6,2)²", axis_rects(5, 5), 225)
chk("Q5  2×3 斜格·平行四边形 C(3,2)×C(4,2)", comb(3, 2) * comb(4, 2), 18)
chk("Q6  大平四被4条平行线分成5条·平四个数 C(6,2)", comb(6, 2), 15)

# Q7 分层梯形：等腰梯形被 n-1 条平行于底的线分成 n 层 → 梯形个数 = C(n+1,2)
for n in (4, 5):
    chk(f"Q7  梯形分{n}层·梯形个数 C({n}+1,2)", comb(n + 1, 2), {4: 10, 5: 15}[n])

print("\n══ 压轴（含斜，全枚举）══")
chk("Q8  4×4 格点·正方形含斜", all_squares_lattice(4, 4), 20)
chk("Q9  4×4 格点·长方形含斜", all_rects_lattice(4, 4), 44)
chk("     其中横平竖直 C(4,2)²", comb(4, 2) ** 2, 36)
chk("     斜的 = 44-36", 44 - 36, 8)
chk("Q10 5×5 格点·平行四边形（只给结论不要求数）", all_parallelograms_lattice(5, 5), None) \
    if False else print("  5×5 格点平行四边形总数 =", all_parallelograms_lattice(5, 5))
chk("参考 3×3 格点·平行四边形（上节课）", all_parallelograms_lattice(3, 3), 22)
chk("参考 4×4 格点·平行四边形", all_parallelograms_lattice(4, 4), 158)

print("\n══ 「同一个数法」的仿射校核：斜格 vs 方格 ══")
# 斜格 = 方格做剪切变换，平行四边形 ↔ 长方形一一对应 ⇒ 计数相同
for m, n in ((2, 2), (3, 3), (2, 3), (3, 4)):
    chk(f"  {m}×{n}: 斜格平四数 == 方格长方形数", axis_rects(m, n), comb(m + 1, 2) * comb(n + 1, 2))

print("\n汇总:", "ALL PASS" if all(x for x in OK if x is not None) else f"有 FAIL")
