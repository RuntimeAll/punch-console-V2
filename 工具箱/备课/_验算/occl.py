# -*- coding: utf-8 -*-
"""等距图遮挡自检：(x,y,z) 与 (x+1,y+1,z+1) 在等距投影下完全重合，
后者会把前者整块盖住。若某一摞的【顶部方块】被盖住，学生就数不出这一摞 → 图不可用。"""
import sys
sys.path.insert(0, r"D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\_卷面生成工具")
import cube3d as c3


def fully_hidden(cells):
    cells = set(cells)
    return {c for c in cells if (c[0] + 1, c[1] + 1, c[2] + 1) in cells}


def hidden_tops(cells):
    """被完全盖住的「摞顶」——这是硬伤。"""
    cells = set(cells)
    tops = {}
    for (x, y, z) in cells:
        if (x, y) not in tops or z > tops[(x, y)]:
            tops[(x, y)] = z
    return {(x, y, z) for (x, y), z in tops.items() if (x + 1, y + 1, z + 1) in cells}


def check(name, cells):
    fh, ht = fully_hidden(cells), hidden_tops(cells)
    print(f"{name}: 共{len(cells)}块 | 被完全遮挡 {len(fh)} | 🔴摞顶被遮挡 {sorted(ht)}"
          f" {'← 图不可用' if ht else '← OK'}")


print("── 现有图自检 ──")
check("题1 Q1", {(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 0, 1), (1, 1, 0)})
for i, s in enumerate([
    {(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1)},
    {(0, 0, 0), (0, 0, 1), (0, 1, 0), (1, 0, 0)},
    {(0, 1, 0), (0, 1, 1), (1, 0, 0), (1, 1, 0)},
    {(0, 1, 0), (1, 0, 0), (1, 0, 1), (1, 1, 0)}], 1):
    check(f"题2 物体{i}", s)
check("题3 Q3", {(0, 0, 0), (1, 0, 0), (2, 0, 0), (1, 0, 1)})
H10 = {(x, y): (3 if x == 0 else 2 if x == 1 else 1) for x in range(3) for y in range(3)}
S10 = {(x, y, z) for (x, y), h in H10.items() for z in range(h)}
check("题10 墙角堆（旧）", S10)
T11 = {(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (1, 1, 1), (2, 1, 0)}
check("题11 目标（旧）", T11)

print("\n── 新方案自检 ──")
H10n = {(x, y): 4 - y for x in range(3) for y in range(3)}
S10n = {(x, y, z) for (x, y), h in H10n.items() for z in range(h)}
check("题10 墙角堆（新 后4中3前2）", S10n)
A = {(0, 0, 0), (1, 0, 0), (0, 1, 0)}
B = {(0, 0, 0), (1, 0, 0), (0, 0, 1)}
C = {(0, 0, 0), (1, 0, 0), (2, 0, 0)}
Bs = {(x + 2, y, z) for x, y, z in B}
T11n = A | Bs
check("题11 目标（新）", T11n)
for k, v in (("A", A), ("B", B), ("C", C)):
    check(f"题11 件{k}", v)

print("\n── 题10 新数据答案 ──")
V = c3.views_of
import itertools
v = V(S10n)
keys = sorted(H10n)
best = None
for hs in itertools.product(*[range(1, H10n[k] + 1) for k in keys]):
    s = {(k[0], k[1], z) for k, h in zip(keys, hs) for z in range(h)}
    vv = V(s)
    if frozenset(vv["top"]) == frozenset(v["top"]) and frozenset(vv["front"]) == frozenset(v["front"]):
        if best is None or len(s) < best:
            best = len(s)
print(f"原有 {len(S10n)}，最少保留 {best}，最多搬走 {len(S10n) - best}")

print("\n── 题11 新数据唯一性 ──")
def can_tile(p1, p2, target):
    rng = range(-4, 5)
    for a in itertools.product(rng, rng, rng):
        A_ = {(x + a[0], y + a[1], z + a[2]) for x, y, z in p1}
        if not A_ <= target:
            continue
        rest = target - A_
        for b in itertools.product(rng, rng, rng):
            if {(x + b[0], y + b[1], z + b[2]) for x, y, z in p2} == rest:
                return True
    return False
P = {"A": A, "B": B, "C": C}
for k1, k2 in itertools.combinations(P, 2):
    print(f"  {k1}+{k2}:", can_tile(P[k1], P[k2], T11n))
