# -*- coding: utf-8 -*-
"""列出 4×4 格点里所有「斜的」长方形（含斜正方形），供答案卷出图。"""
import itertools, math

N = 4
P = [(x, y) for x in range(N) for y in range(N)]
S = set(P)
out = {}
for a, b in itertools.combinations(P, 2):
    vx, vy = b[0] - a[0], b[1] - a[1]
    for (px, py) in ((-vy, vx), (vy, -vx)):
        g = math.gcd(abs(px), abs(py)) or 1
        ux, uy = px // g, py // g
        for k in range(1, N + 1):
            c = (b[0] + ux * k, b[1] + uy * k)
            d = (a[0] + ux * k, a[1] + uy * k)
            if not all(0 <= p[0] < N and 0 <= p[1] < N for p in (c, d)):
                break
            if c in S and d in S:
                quad = (a, b, c, d)
                key = frozenset(quad)
                if key not in out:
                    out[key] = quad
tilt = []
for key, quad in out.items():
    xs = {p[0] for p in quad}
    ys = {p[1] for p in quad}
    axis = len(xs) == 2 and len(ys) == 2
    if not axis:
        tilt.append(quad)
print("长方形总数(含正方形,含斜) =", len(out))
print("斜的 =", len(tilt))
for q in sorted(tilt):
    v = (q[1][0] - q[0][0], q[1][1] - q[0][1])
    w = (q[3][0] - q[0][0], q[3][1] - q[0][1])
    kind = "正方形" if v[0]**2+v[1]**2 == w[0]**2+w[1]**2 else "长方形"
    print(f"  {q}  边{v}/{w}  {kind}")
