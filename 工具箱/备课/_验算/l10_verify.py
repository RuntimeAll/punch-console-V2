# -*- coding: utf-8 -*-
"""第10课·同步奥数（平行四边形为核心）10 题逐题实算。"""
import itertools
from math import comb

OK = []


def chk(tag, got, want):
    ok = got == want
    OK.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {tag}: got={got} want={want}")


# 1. 4×4 钉板横平竖直长方形
def axis_rects(n):
    return comb(n, 2) ** 2


chk("Q1 4×4轴正长方形", axis_rects(4), 36)

# 2. 4×4 钉板正方形（含斜）
def squares(n):
    P = [(x, y) for x in range(n) for y in range(n)]
    out = set()
    for a, b, c, d in itertools.combinations(P, 4):
        for p, q, r in itertools.permutations([b, c, d]):
            v = (p[0] - a[0], p[1] - a[1]); w = (r[0] - a[0], r[1] - a[1])
            if (a[0] + q[0], a[1] + q[1]) != (p[0] + r[0], p[1] + r[1]):
                continue
            if v[0] * w[0] + v[1] * w[1] == 0 and v[0] ** 2 + v[1] ** 2 == w[0] ** 2 + w[1] ** 2 and (v[0] or v[1]):
                out.add(tuple(sorted([a, p, q, r]))); break
    return len(out)


chk("Q2 4×4正方形(含斜)", squares(4), 20)
chk("Q2 轴正部分 3²+2²+1²", 3 ** 2 + 2 ** 2 + 1 ** 2, 14)

# 3. 规律：n×n 轴正长方形 = [n(n-1)/2]²
chk("Q3 5×5轴正长方形", axis_rects(5), 100)
chk("Q3 公式核对 3/4/5", [axis_rects(k) for k in (3, 4, 5)], [9, 36, 100])

# 4. 对角线互相平分：对角线 12 → 交点到顶点 6
chk("Q4 半对角线", 12 // 2, 6)

# 5. 长方形 8×5 拉成平四：周长不变
chk("Q5 拉伸周长", (8 + 5) * 2, 26)

# 6. 周长 40，AB 比 BC 长 4（和差）
s, d = 40 // 2, 4
ab, bc = (s + d) // 2, (s - d) // 2
chk("Q6 和差 AB/BC", (ab, bc), (12, 8))
chk("Q6 回验周长", (ab + bc) * 2, 40)
chk("Q6 回验差", ab - bc, 4)

# 7. 铁丝 48，一边是邻边 2 倍（和倍）
s7 = 48 // 2
short = s7 // 3
chk("Q7 短边/长边", (short, short * 2), (8, 16))
chk("Q7 回验周长", (short + short * 2) * 2, 48)

# 8. 两个完全一样的平四沿一条长边贴合拼成大平四
per, long_side = 30, 10
short_side = per // 2 - long_side
chk("Q8 小平四短边", short_side, 5)
big = per * 2 - long_side * 2          # 拼合处两条长边消失
chk("Q8 大平四周长", big, 40)
chk("Q8 直接算 (10+5+5)×2", (long_side + short_side * 2) * 2, 40)

# 9. 靠墙围平四：一条长边靠墙，篱笆 46，长边 18
fence, L = 46, 18
W = (fence - L) // 2
chk("Q9 短边", W, 14)
chk("Q9 回验", L + W * 2, 46)
chk("Q9 短边<长边", W < L, True)

# 10. 平四与等腰梯形周长相等
p10 = (12 + 9) * 2
up, down = 8, 8 + 6
leg = (p10 - up - down) // 2
chk("Q10 平四周长", p10, 42)
chk("Q10 梯形腰", leg, 10)
chk("Q10 回验梯形周长", up + down + leg * 2, 42)

print("\n汇总:", "ALL PASS" if all(OK) else f"有 {OK.count(False)} 处 FAIL")
