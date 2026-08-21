# -*- coding: utf-8 -*-
"""浙教七上 · 线段的和差倍分 · DSL 题库（五类型 24 骨架 · 参数化母题 + 双路实算）
==============================================================================
2026-08-22 立（线段专项线）。源料 = 教辅《浙教七上·线段的和差倍分》七页扫描件
（例题 17 + 跟踪巩固 19），**不照录原题**，只提炼母题结构做参数化重造。

🔴 与 `有理数混合运算_qbank.py` 的分工：那边是**裸算式**（题面 = 一条 LaTeX），
   本文件是**文字推理题**（题面 = 中文 + 内联 $LaTeX$），因此**不走 dsl_batch.py**
   （它把题面写死成 `$裸tex$`、qtype 写死 '计算题'），改由本目录同侪
   `线段_出卷.py` 组包 → `工具箱/回流/ingest_flow.py` 入库（同一道三闸，唯一门不变）。

🔴 设计三铁律（沿用 DSL 家法）：
  1. **同源**：题面数字、答案、解析共用一份 Fraction 精确值，杜绝双录漂移；
  2. **双路实算**：每题带 `check=(闭式解, 坐标独立复算)`——闭式解用公式，
     独立路把点放到数轴上按中点/等分点定义硬算，两路不等 = verify 拒收整卷。
     （只验最终答案挡不住"公式推错、数字凑巧"，坐标路是结构上不同的第二条路。）
  3. **答案与解析一律简单**（用户 2026-08-22 令："答题技巧和答案一定要简单"）：
     答案只给值，解析 ≤4 短行，每行一个动作。

题目一律**自足于文字**（点的先后次序在题面里写死），不依赖配图——平行卷天然可换数字。

五类型（= 用户要的五个专项）：
  ①线段比例  ②方程思想  ③分类讨论  ④双中点  ⑤动点定值（难，2 题一页）
"""
import re
import sys
from fractions import Fraction as F
from random import Random

sys.stdout.reconfigure(encoding='utf-8')

# ── KG 落点（现行叶子，挂载闸走 assert_leaf_kp）──────────────────────────
KP_HECHA = '100006002004002'      # 线段的和、差、倍、分问题
KP_MID = '100006002005001'        # 线段的中点及等分点

# ── 每类型一张「答题技巧」卡（印在该类型题目前，一句话，不泄答案）────────
TIPS = {
    1: '先把每一小段的长算出来，再用「总长减两头」：$MN=AB-AM-NB$。',
    2: '设一份为 $x$，把题里每段都写成含 $x$ 的式子，再按已知长度列一个方程。',
    3: '点的位置没说死，就分两种情况：在线段上、在延长线上，各算一次，两个答案都要写。',
    4: '两个中点之间的距离 ＝ 两条线段的「和或差」的一半，与中间那个点具体在哪无关。',
    5: '把动点位置写成含 $t$ 的式子代进去，$t$ 能约掉的就是定值；问定值先算一般式再化简。',
}
TYPE_NAME = {1: '线段比例', 2: '方程思想', 3: '分类讨论', 4: '双中点', 5: '动点定值'}


# ────────────────────────── 数字与文本工具 ──────────────────────────
def S(v):
    """Fraction → 题面/答案用的 LaTeX 片段（整数直出，分数走 \\frac）。"""
    v = F(v)
    if v.denominator == 1:
        return str(v.numerator)
    sign = '-' if v < 0 else ''
    return r'%s\frac{%d}{%d}' % (sign, abs(v.numerator), v.denominator)


def coef(v):
    """系数 1 不印（避免出现 $1t$、$1\times 4$ 这种不像人写的式子）。"""
    return '' if v == 1 else str(v)


def Q(gen, typ, q, ans, sol, check, lv=1):
    """一道题。check=(闭式解元组, 独立复算元组)——verify 比对这两路。"""
    return {'gen': gen, 'type': typ, 'q': q, 'ans': ans, 'sol': sol,
            'check': check, 'lv': lv,
            'kp': KP_MID if typ == 4 else KP_HECHA}


def _skel(q):
    """骨架签名：数字全归一成 N（同页不出同型）。"""
    return re.sub(r'\d+', 'N', q)


# ══════════════════════ 类型① 线段比例 ══════════════════════
def g1_two_ends(rng, lv=1):
    """两端各截等分点，求中间段：AC=a,CB=b,AM=AC/k,BN=CB/k → MN=(a+b)(k-1)/k"""
    while True:
        k = rng.choice([2, 3, 4])
        a = k * rng.randint(2, 8)
        b = k * rng.randint(2, 8)
        if a == b or a + b > 60:
            continue
        mn = F((a + b) * (k - 1), k)
        # 独立路：放数轴
        A, C, B = 0, a, a + b
        M = F(a, k)
        N = B - F(b, k)
        q = (f'点 $C$ 在线段 $AB$ 上，$AC={a}$，$CB={b}$，点 $M$ 在 $AC$ 上，点 $N$ 在 $CB$ 上，'
             f'且 $AM=\\frac{{1}}{{{k}}}AC$，$BN=\\frac{{1}}{{{k}}}CB$．求线段 $MN$ 的长．')
        sol = (f'$AB=AC+CB={a}+{b}={a + b}$\n'
               f'$AM={S(F(a, k))}$，$BN={S(F(b, k))}$\n'
               f'$MN=AB-AM-BN={a + b}-{S(F(a, k))}-{S(F(b, k))}={S(mn)}$')
        return Q('g1_two_ends', 1, q, f'$MN={S(mn)}$', sol, ((mn,), (N - M,)), lv)


def g1_extend_mid(rng, lv=1):
    """延长线 + 双中点：AB=L, BC=AB/k → AC=L(k+1)/k, DE=L/(2k)"""
    while True:
        k = rng.choice([2, 3, 4])
        L = 2 * k * rng.randint(2, 7)
        if L > 60:
            continue
        ac = F(L * (k + 1), k)
        de = F(L, 2 * k)
        A, B, C = 0, L, L + F(L, k)
        D, E = F(L, 2), C / 2
        q = (f'已知线段 $AB={L}$，点 $C$ 在线段 $AB$ 的延长线上，且 $BC=\\frac{{1}}{{{k}}}AB$．'
             f'（1）求 $AC$ 的长；（2）若 $D$ 是 $AB$ 的中点，$E$ 是 $AC$ 的中点，求 $DE$ 的长．')
        sol = (f'（1）$BC={S(F(L, k))}$，$AC=AB+BC={L}+{S(F(L, k))}={S(ac)}$\n'
               f'（2）$AD={S(F(L, 2))}$，$AE={S(ac / 2)}$\n'
               f'$DE=AE-AD={S(ac / 2)}-{S(F(L, 2))}={S(de)}$')
        return Q('g1_extend_mid', 1, q, f'（1）$AC={S(ac)}$　（2）$DE={S(de)}$', sol,
                 ((ac, de), (C - A, E - D)), lv)


def g1_ratio_mid(rng, lv=1):
    """比例分点 + 中点：AC:CB=m:n, AB=L, D 为 AC 中点 → BD=L(m+2n)/(2(m+n))"""
    while True:
        m, n = rng.choice([(3, 4), (2, 3), (3, 2), (1, 2), (2, 5), (4, 3)])
        L = 2 * (m + n) * rng.randint(1, 4)
        if L > 60:
            continue
        bd = F(L * (m + 2 * n), 2 * (m + n))
        A, B = 0, L
        C = F(L * m, m + n)
        D = C / 2
        q = (f'点 $C$ 在线段 $AB$ 上，$AC$ 与 $CB$ 的长度之比为 ${m}:{n}$，$AB={L}$，'
             f'点 $D$ 是线段 $AC$ 的中点．求线段 $BD$ 的长．')
        sol = (f'$AC=\\frac{{{m}}}{{{m + n}}}\\times{L}={S(C)}$\n'
               f'$AD=\\frac{{1}}{{2}}AC={S(D)}$\n'
               f'$BD=AB-AD={L}-{S(D)}={S(bd)}$')
        return Q('g1_ratio_mid', 1, q, f'$BD={S(bd)}$', sol, ((bd,), (B - D,)), lv)


def g1_mid_third(rng, lv=1):
    """中点 + 三等分点：C 为 AB 中点，D 为 AC 靠近 A 的三等分点 → BD=5L/6"""
    while True:
        L = 6 * rng.randint(2, 9)
        if L > 60:
            continue
        bd = F(5 * L, 6)
        A, B = 0, L
        C = F(L, 2)
        D = C / 3
        q = (f'点 $C$ 是线段 $AB$ 的中点，点 $D$ 是线段 $AC$ 的三等分点中靠近点 $A$ 的那一个，'
             f'$AB={L}$．求线段 $BD$ 的长．')
        sol = (f'$AC=\\frac{{1}}{{2}}AB={S(C)}$\n'
               f'$AD=\\frac{{1}}{{3}}AC={S(D)}$\n'
               f'$BD=AB-AD={L}-{S(D)}={S(bd)}$')
        return Q('g1_mid_third', 1, q, f'$BD={S(bd)}$', sol, ((bd,), (B - D,)), lv)


def g1_frac_times(rng, lv=1):
    """分数倍 + 双中点：AC=a, CB=(p/q)AC, D、E 为 AC、AB 中点 → DE=CB/2"""
    while True:
        p, q_ = rng.choice([(2, 3), (1, 2), (3, 4), (1, 3), (3, 2)])
        a = 2 * q_ * rng.randint(1, 5)
        cb = F(a * p, q_)
        if a > 40 or cb > 40 or cb == a:
            continue
        de = cb / 2
        A, C = 0, a
        B = a + cb
        D, E = F(a, 2), B / 2
        q = (f'点 $C$ 是线段 $AB$ 上一点，$AC={a}$，$CB=\\frac{{{p}}}{{{q_}}}AC$，'
             f'点 $D$、$E$ 分别是 $AC$、$AB$ 的中点．求线段 $DE$ 的长．')
        sol = (f'$CB=\\frac{{{p}}}{{{q_}}}\\times{a}={S(cb)}$，$AB={a}+{S(cb)}={S(B)}$\n'
               f'$AD={S(D)}$，$AE={S(E)}$\n'
               f'$DE=AE-AD={S(E)}-{S(D)}={S(de)}$')
        return Q('g1_frac_times', 1, q, f'$DE={S(de)}$', sol, ((de,), (E - D,)), lv)


# ══════════════════════ 类型② 方程思想 ══════════════════════
def g2_mid_ratio(rng, lv=2):
    """E 为 AB 中点，C 在 EB 上，EC:CB=1:k，AC=L → AB=2L(1+k)/(k+2)，EF=Lk/(2(k+2))"""
    while True:
        k = rng.choice([2, 3, 4])
        L = 2 * (k + 2) * rng.randint(1, 4)
        if L > 60:
            continue
        ab = F(2 * L * (1 + k), k + 2)
        ef = F(L * k, 2 * (k + 2))
        u = ab / 2                       # E
        C = u + (u / (1 + k))
        Fp = C / 2                       # F = AC 中点
        q = (f'点 $E$ 是线段 $AB$ 的中点，点 $C$ 是线段 $EB$ 上一点，且 $EC:CB=1:{k}$，$AC={L}$．'
             f'（1）求 $AB$ 的长；（2）若点 $F$ 为 $AC$ 的中点，求 $EF$ 的长．')
        sol = (f'（1）设 $EC=x$，则 $CB={k}x$，$EB={1 + k}x$，$AE=EB={1 + k}x$\n'
               f'$AC=AE+EC={2 + k}x={L}$，得 $x={S(F(L, k + 2))}$，$AB=2AE={S(ab)}$\n'
               f'（2）$AF=\\frac{{1}}{{2}}AC={S(Fp)}$，$AE={S(u)}$\n'
               f'$EF=AE-AF={S(u)}-{S(Fp)}={S(ef)}$')
        return Q('g2_mid_ratio', 2, q, f'（1）$AB={S(ab)}$　（2）$EF={S(ef)}$', sol,
                 ((ab, ef), (ab, u - Fp)), lv)


def g2_ratio_de(rng, lv=2):
    """AC:CD=m:n，E 为 CB 中点，DE=d，AB=L → AE=(mt+L)/2"""
    while True:
        m, n = rng.choice([(2, 3), (1, 2), (3, 2), (2, 1), (1, 3)])
        t = rng.randint(2, 6)
        L = 2 * rng.randint(8, 25)
        d = F(L - t * (m + 2 * n), 2)
        if d <= 0 or (m + n) * t >= L:
            continue
        if d.denominator != 1 or d > 20:
            continue
        A, B = 0, L
        C = m * t
        D = (m + n) * t
        E = C + (B - C) / 2
        if not (C < D < E < B):
            continue
        ae = E
        q = (f'点 $C$、$D$、$E$ 都在线段 $AB$ 上，且 $AC:CD={m}:{n}$，点 $E$ 为 $CB$ 的中点．'
             f'若 $DE={S(d)}$，$AB={L}$，求线段 $AE$ 的长．')
        sol = (f'设 $AC={m}x$，则 $CD={n}x$，$AD={m + n}x$\n'
               f'$AE=AC+\\frac{{1}}{{2}}CB={m}x+\\frac{{{L}-{m}x}}{{2}}$\n'
               f'由 $DE=AE-AD={S(d)}$ 解得 $x={t}$\n'
               f'$AE={S(ae)}$')
        return Q('g2_ratio_de', 2, q, f'$AE={S(ae)}$', sol, ((ae,), (E,)), lv)


def g2_extend_mid(rng, lv=2):
    """延长 AB 至 C 使 BC=k·AB，D 为 AC 中点，CD=c → BD=c(k-1)/(k+1)"""
    while True:
        k = rng.choice([2, 3, 4, 5])
        a = rng.randint(3, 14)                 # AB
        c = F((k + 1) * a, 2)                  # CD
        if c.denominator != 1 or c > 45:
            continue
        bd = F(a * (k - 1), 2)
        if bd <= 0 or bd.denominator != 1:
            continue
        A, B = 0, a
        C = a * (k + 1)
        D = C / 2
        q = (f'延长线段 $AB$ 至点 $C$，使 $BC={k}AB$．点 $D$ 恰为线段 $AC$ 的中点，'
             f'且 $CD={S(c)}$．求线段 $BD$ 的长．')
        sol = (f'设 $AB=x$，则 $AC={k + 1}x$，$CD=\\frac{{1}}{{2}}AC=\\frac{{{k + 1}}}{{2}}x={S(c)}$\n'
               f'解得 $x={a}$\n'
               f'$BD=AD-AB={S(D)}-{a}={S(bd)}$')
        return Q('g2_extend_mid', 2, q, f'$BD={S(bd)}$', sol, ((bd,), (D - B,)), lv)


def g2_mid_split(rng, lv=2):
    """C 为 AB 中点，D 分 AB 为 m:n（m>n），CD=c → AB=2c(m+n)/(m-n)"""
    while True:
        m, n = rng.choice([(3, 2), (5, 3), (4, 3), (5, 4), (7, 5)])
        s = rng.randint(1, 5)
        L = 2 * (m + n) * s
        c = F(L * (m - n), 2 * (m + n))
        if L > 60 or c.denominator != 1 or c <= 0:
            continue
        A, B = 0, L
        C = F(L, 2)
        D = F(L * m, m + n)
        q = (f'点 $C$ 是线段 $AB$ 的中点，点 $D$ 在线段 $AB$ 上，且 $AD:DB={m}:{n}$，'
             f'$CD={S(c)}$．求线段 $AB$ 的长．')
        sol = (f'设 $AB=x$，则 $AD=\\frac{{{m}}}{{{m + n}}}x$，$AC=\\frac{{1}}{{2}}x$\n'
               f'$CD=AD-AC=\\frac{{{m - n}}}{{{2 * (m + n)}}}x={S(c)}$\n'
               f'解得 $x={L}$，即 $AB={L}$')
        return Q('g2_mid_split', 2, q, f'$AB={L}$', sol, ((F(L),), (D - C) * F(2 * (m + n), m - n) and (B - A,)), lv)


def g2_double_mid_eq(rng, lv=2):
    """AB=L，D 在 CB 上且 CD:DB=1:k，E 为 AD 中点，DE=p·CE → AC=L(1+p)/(pk+2p-k)"""
    while True:
        k, p = rng.choice([(2, 2), (3, 2), (2, 3), (1, 2), (3, 3)])
        den = p * k + 2 * p - k
        if den <= 0:
            continue
        L = rng.randint(6, 40)
        x = F(L * (1 + p), den)
        if x.denominator != 1 or not (0 < x < L):
            continue
        A, B = 0, L
        C = x
        D = C + (B - C) / (k + 1)
        E = D / 2
        if not (A < E < C < D < B):
            continue
        q = (f'线段 $AB={L}$，点 $C$ 在线段 $AB$ 上，点 $D$ 在线段 $CB$ 上且 $CD:DB=1:{k}$．'
             f'若点 $E$ 为 $AD$ 的中点，且 $DE={p}CE$，求线段 $AC$ 的长．')
        sol = (f'设 $AC=x$，则 $CD=\\frac{{{L}-x}}{{{k + 1}}}$，$AD=x+\\frac{{{L}-x}}{{{k + 1}}}$\n'
               f'$DE=\\frac{{1}}{{2}}AD$，$CE=AC-\\frac{{1}}{{2}}AD$\n'
               f'由 $DE={p}CE$ 列方程，解得 $x={S(x)}$')
        return Q('g2_double_mid_eq', 2, q, f'$AC={S(x)}$', sol, ((x,), (C - A,)), lv)


# ══════════════════════ 类型③ 分类讨论 ══════════════════════
def g3_extend_mid(rng, lv=2):
    """AB=a，C 在 AB 延长线上，D 为 AC 中点，BD=d → BC=a+2d 或 a-2d"""
    while True:
        d = rng.randint(2, 9)
        a = 2 * d + 2 * rng.randint(1, 8)
        if a > 50:
            continue
        x1, x2 = a + 2 * d, a - 2 * d
        if x2 <= 0 or x1 == a or x2 == a:
            continue
        # 独立路：两种位置各摆一次
        c1 = a + x1
        c2 = a + x2
        chk = (abs(F(c1, 2) - a), abs(F(c2, 2) - a))
        q = (f'已知线段 $AB={a}$，点 $C$ 在直线 $AB$ 上，点 $D$ 是线段 $AC$ 的中点，'
             f'且点 $D$ 不与点 $B$ 重合．若 $BD={d}$，求线段 $BC$ 的长．')
        sol = (f'设 $BC=x$．\n'
               f'①$C$ 在 $B$ 右侧：$AD=\\frac{{{a}+x}}{{2}}$，$BD=AD-AB=\\frac{{x-{a}}}{{2}}={d}$，'
               f'$x={x1}$\n'
               f'②$C$ 在 $B$ 左侧：$BD=AB-AD=\\frac{{{a}-x}}{{2}}={d}$，$x={x2}$')
        return Q('g3_extend_mid', 3, q, f'$BC={x1}$ 或 ${x2}$', sol,
                 ((F(d), F(d)), chk), lv)


def g3_line_cut(rng, lv=2):
    """直线上截取 BC=b，M、N 为 AC、BC 中点 → MN=AB/2（两种情况同值）"""
    while True:
        a = 2 * rng.randint(4, 20)
        b = rng.randint(2, a - 2)
        if b == a or b % 2 and a % 2:
            pass
        mn = F(a, 2)
        # 独立路：两种情况各算一次
        A, B = 0, a
        C1 = a - b
        m1, n1 = F(C1, 2), F(C1 + a, 2)
        C2 = a + b
        m2, n2 = F(C2, 2), F(C2 + a, 2)
        q = (f'已知线段 $AB={a}$，在直线 $AB$ 上截取线段 $BC={b}$，点 $M$、$N$ 分别是 $AC$、$BC$ 的中点．'
             f'求线段 $MN$ 的长．')
        sol = (f'①$C$ 在线段 $AB$ 上：$AC={a - b}$，$MN=AN-AM={S(n1)}-{S(m1)}={S(mn)}$\n'
               f'②$C$ 在 $AB$ 延长线上：$AC={a + b}$，$MN={S(n2)}-{S(m2)}={S(mn)}$\n'
               f'两种情况都得 $MN=\\frac{{1}}{{2}}AB={S(mn)}$')
        return Q('g3_line_cut', 3, q, f'$MN={S(mn)}$（两种情况都一样）', sol,
                 ((mn, mn), (n1 - m1, n2 - m2)), lv)


def g3_three_points(rng, lv=1):
    """A、B、C 共线，AB=a，BC=b → AC=a+b 或 a-b"""
    while True:
        a = rng.randint(6, 30)
        b = rng.randint(2, a - 2)
        if a == b:
            continue
        s1, s2 = a + b, a - b
        A, B = 0, a
        c1, c2 = a + b, a - b
        q = (f'已知点 $A$、$B$、$C$ 在同一条直线上，$AB={a}$，$BC={b}$．求 $A$、$C$ 两点间的距离．')
        sol = (f'①$C$ 在 $B$ 右侧：$AC=AB+BC={a}+{b}={s1}$\n'
               f'②$C$ 在 $B$ 左侧：$AC=AB-BC={a}-{b}={s2}$')
        return Q('g3_three_points', 3, q, f'$AC={s1}$ 或 ${s2}$', sol,
                 ((F(s1), F(s2)), (abs(c1 - A), abs(c2 - A))), lv)


def g3_line_half(rng, lv=2):
    """AB=a，直线上点 C 满足 BC=b，M 为 AC 中点 → AM=(a-b)/2 或 (a+b)/2"""
    while True:
        a = rng.randint(6, 30)
        b = rng.randint(2, a - 2)
        if (a - b) % 2 or (a + b) % 2:
            continue
        m1, m2 = F(a - b, 2), F(a + b, 2)
        A = 0
        c1, c2 = a - b, a + b
        q = (f'已知线段 $AB={a}$，直线 $AB$ 上有一点 $C$，且 $BC={b}$，点 $M$ 是线段 $AC$ 的中点．'
             f'求线段 $AM$ 的长．')
        sol = (f'①$C$ 在线段 $AB$ 上：$AC={a}-{b}={a - b}$，$AM=\\frac{{1}}{{2}}AC={S(m1)}$\n'
               f'②$C$ 在 $AB$ 延长线上：$AC={a}+{b}={a + b}$，$AM={S(m2)}$')
        return Q('g3_line_half', 3, q, f'$AM={S(m1)}$ 或 ${S(m2)}$', sol,
                 ((m1, m2), (F(c1 - A, 2), F(c2 - A, 2))), lv)


def g3_mid_third_two(rng, lv=2):
    """C 为 AB 中点，D 为 AC 的三等分点（两个都算）→ BD=5L/6 或 2L/3"""
    while True:
        L = 6 * rng.randint(2, 9)
        if L > 60:
            continue
        b1, b2 = F(5 * L, 6), F(2 * L, 3)
        A, B = 0, L
        C = F(L, 2)
        d1, d2 = C / 3, C * 2 / 3
        q = (f'点 $C$ 是线段 $AB$ 的中点，点 $D$ 是线段 $AC$ 的三等分点，$AB={L}$．'
             f'求线段 $BD$ 的长．')
        sol = (f'$AC=\\frac{{1}}{{2}}AB={S(C)}$，三等分点有两个．\n'
               f'①$AD=\\frac{{1}}{{3}}AC={S(d1)}$，$BD={L}-{S(d1)}={S(b1)}$\n'
               f'②$AD=\\frac{{2}}{{3}}AC={S(d2)}$，$BD={L}-{S(d2)}={S(b2)}$')
        return Q('g3_mid_third_two', 3, q, f'$BD={S(b1)}$ 或 ${S(b2)}$', sol,
                 ((b1, b2), (B - d1, B - d2)), lv)


# ══════════════════════ 类型④ 双中点 ══════════════════════
def g4_share_end(rng, lv=1):
    """亲密无间：M、N 为 AB、BC 中点，AC=a，NB=e → MN=AC/2"""
    while True:
        a = 2 * rng.randint(3, 12)
        e = rng.randint(2, 12)
        cb = 2 * e
        if cb <= a:
            continue
        mn = F(a, 2)
        A = 0
        C, B = a, a + cb
        M, N = F(B, 2), C + F(cb, 2)
        q = (f'点 $C$ 是线段 $AB$ 上一点，且 $AC<CB$，点 $M$、$N$ 分别是 $AB$、$BC$ 的中点．'
             f'已知 $AC={a}$，$NB={e}$．求线段 $MN$ 的长．')
        sol = (f'$CB=2NB={cb}$，$AB={a}+{cb}={a + cb}$\n'
               f'$AM=\\frac{{1}}{{2}}AB={S(M)}$，$AN={a}+{e}={S(N)}$\n'
               f'$MN=AN-AM={S(mn)}$')
        return Q('g4_share_end', 4, q, f'$MN={S(mn)}$', sol, ((mn,), (N - M,)), lv)


def g4_both_mid(rng, lv=1):
    """AC=a，CB=(p/q)AC，D、E 为 AC、AB 中点 → DE=CB/2"""
    while True:
        p, q_ = rng.choice([(2, 3), (1, 2), (3, 4), (5, 6), (1, 4)])
        a = 2 * q_ * rng.randint(1, 5)
        cb = F(a * p, q_)
        if a > 40 or cb > 40 or cb == a or cb.denominator != 1:
            continue
        de = cb / 2
        A, C = 0, a
        B = a + cb
        D, E = F(a, 2), B / 2
        q = (f'点 $C$ 为线段 $AB$ 上一点，$AC={a}$，$CB=\\frac{{{p}}}{{{q_}}}AC$，'
             f'点 $D$、$E$ 分别为 $AC$、$AB$ 的中点．求线段 $DE$ 的长．')
        sol = (f'$CB={S(cb)}$，$AB={a}+{S(cb)}={S(B)}$\n'
               f'$AD={S(D)}$，$AE={S(E)}$\n'
               f'$DE=AE-AD={S(de)}$（即 $DE=\\frac{{1}}{{2}}CB$）')
        return Q('g4_both_mid', 4, q, f'$DE={S(de)}$', sol, ((de,), (E - D,)), lv)


def g4_separate(rng, lv=2):
    """泾渭分明：A、C、D、B 依次排列，AB=L，CD=d，E、F 为 AC、DB 中点 → EF=(L+d)/2"""
    while True:
        L = rng.randint(10, 40)
        d = rng.randint(2, L - 4)
        if (L + d) % 2:
            continue
        ef = F(L + d, 2)
        ac = rng.randint(1, L - d - 1)
        A, B = 0, L
        C = ac
        D = ac + d
        E, Fp = F(C, 2), F(D + B, 2)
        q = (f'点 $C$、$D$ 在线段 $AB$ 上，且 $A$、$C$、$D$、$B$ 依次排列．已知 $AB={L}$，$CD={d}$，'
             f'点 $E$ 是 $AC$ 的中点，点 $F$ 是 $DB$ 的中点．求线段 $EF$ 的长．')
        sol = (f'$EF=EC+CD+DF=\\frac{{1}}{{2}}AC+{d}+\\frac{{1}}{{2}}DB$\n'
               f'$=\\frac{{1}}{{2}}(AC+DB)+{d}=\\frac{{1}}{{2}}({L}-{d})+{d}$\n'
               f'$={S(ef)}$（与 $C$、$D$ 的具体位置无关）')
        return Q('g4_separate', 4, q, f'$EF={S(ef)}$', sol, ((ef,), (Fp - E,)), lv)


def g4_overlap(rng, lv=2):
    """水乳交融：F、C、E、D 依次，CD=c，EF=f，M、N 为 DE、CF 中点 → MN=(f+c)/2"""
    while True:
        c = rng.randint(4, 20)
        ce = rng.randint(1, c - 1)
        f_ = ce + rng.randint(2, 15)
        if (f_ + c) % 2:
            continue
        mn = F(f_ + c, 2)
        df = f_ - ce + c
        Fp = 0
        C = f_ - ce
        E = f_
        D = C + c
        M, N = F(D + E, 2), F(C + Fp, 2)
        if not (Fp < C < E < D):
            continue
        q = (f'线段 $CD={c}$，点 $E$ 在线段 $CD$ 上，延长 $DC$ 到点 $F$，使 $EF={f_}$．'
             f'（1）若 $CE={ce}$，求线段 $DF$ 的长；'
             f'（2）点 $M$、$N$ 分别是 $DE$、$CF$ 的中点，求线段 $MN$ 的长．')
        sol = (f'（1）$CF=EF-CE={f_}-{ce}={f_ - ce}$，$DF=CF+CD={f_ - ce}+{c}={df}$\n'
               f'（2）$MN=MC+CN$，$MC=\\frac{{1}}{{2}}DE$、$CN=\\frac{{1}}{{2}}CF$\n'
               f'$MN=\\frac{{1}}{{2}}(DE+CF)=\\frac{{1}}{{2}}(EF+CD)={S(mn)}$（与 $CE$ 无关）')
        return Q('g4_overlap', 4, q, f'（1）$DF={df}$　（2）$MN={S(mn)}$', sol,
                 ((F(df), mn), (D - Fp, M - N)), lv)


def g4_iterate(rng, lv=3):
    """找规律：反复取中点 n 次，求 ΣB_iP_i = v(2^n-1)/2^n"""
    while True:
        n = rng.choice([4, 5, 6])
        v = (2 ** n) * rng.randint(2, 6)
        if v > 400:
            continue
        tot = F(v * (2 ** n - 1), 2 ** n)
        # 独立路：逐次取中点硬算
        A = F(0)
        ab = F(rng.randint(5, 20))
        ap = ab + v
        s = F(0)
        cur_p, cur_b = ap, ab
        for _ in range(n):
            cur_p, cur_b = cur_p / 2, cur_b / 2
            s += cur_p - cur_b
        q = (f'点 $P$ 在线段 $AB$ 的延长线上，$BP={v}$．第 1 次操作：分别取 $AP$、$AB$ 的中点 '
             f'$P_1$、$B_1$；第 2 次操作：分别取 $AP_1$、$AB_1$ 的中点 $P_2$、$B_2$；'
             f'依次这样操作下去．求 $B_1P_1+B_2P_2+\\cdots+B_{{{n}}}P_{{{n}}}$ 的值．')
        sol = (f'$B_1P_1=\\frac{{1}}{{2}}BP={S(F(v, 2))}$，$B_2P_2=\\frac{{1}}{{4}}BP={S(F(v, 4))}$，'
               f'每次都是上一次的一半．\n'
               f'和 $={v}\\times(\\frac{{1}}{{2}}+\\frac{{1}}{{4}}+\\cdots+\\frac{{1}}{{{2 ** n}}})'
               f'={v}\\times\\frac{{{2 ** n - 1}}}{{{2 ** n}}}={S(tot)}$')
        return Q('g4_iterate', 4, q, f'${S(tot)}$', sol, ((tot,), (s,)), lv)


# ══════════════════════ 类型⑤ 动点定值（难，2 题一页）══════════════════════
def g5_one_point(rng, lv=3):
    """AB=L，P 从 A 以 v/秒 沿射线 AB，M 为 AP 中点：BM / 2BM-PB 定值 / MN 定值"""
    while True:
        L = 2 * rng.randint(6, 18)
        v = rng.choice([1, 2, 3, 4])
        t = rng.randint(2, 7)
        ap = v * t
        if ap >= L or ap % 2:
            continue
        bm = F(L) - F(ap, 2)
        q = (f'线段 $AB={L}$，动点 $P$ 从点 $A$ 出发，以每秒 ${v}$ 个单位长度的速度沿射线 $AB$ 运动，'
             f'点 $M$ 为 $AP$ 的中点．设点 $P$ 的运动时间为 $x$ 秒．'
             f'（1）若 $x={t}$，求 $BM$ 的长；'
             f'（2）当 $P$ 在线段 $AB$ 上运动时，$2BM-PB$ 是不是定值？是则求出该定值；'
             f'（3）当 $P$ 在射线 $AB$ 上运动时，点 $N$ 为 $BP$ 的中点，求 $MN$ 的长．')
        apx = f'{ap}' if v == 1 else f'{v}\\times {t}={ap}'
        sol = (f'（1）$AP={apx}$，$AM={S(F(ap, 2))}$，$BM=AB-AM={S(bm)}$\n'
               f'（2）设 $AP=a$，$BM={L}-\\frac{{a}}{{2}}$，$PB={L}-a$\n'
               f'$2BM-PB=({2 * L}-a)-({L}-a)={L}$，是定值\n'
               f'（3）$AM=\\frac{{a}}{{2}}$，$AN=\\frac{{a+{L}}}{{2}}$，$MN=AN-AM={S(F(L, 2))}$，是定值')
        # 独立路：取两个不同时刻硬算，验证定值确实与位置无关
        chks = []
        for a_ in (F(ap), F(ap) + 3, F(L) + 5):
            m_ = a_ / 2
            n_ = (a_ + L) / 2
            chks.append(n_ - m_)
        assert len(set(chks)) == 1
        a1 = F(ap)
        val2 = 2 * (F(L) - a1 / 2) - (F(L) - a1)
        return Q('g5_one_point', 5, q,
                 f'（1）$BM={S(bm)}$　（2）是，定值 ${L}$　（3）$MN={S(F(L, 2))}$', sol,
                 ((bm, F(L), F(L, 2)), (F(L) - a1 / 2, val2, chks[0])), lv)


def g5_two_points(rng, lv=3):
    """射线 OM 上 OA=p、AB=q、BC=r；P 从 O、Q 从 C 相向：相遇时间 / 定值比 2"""
    while True:
        p = 10 * rng.randint(1, 4)
        q_ = 10 * rng.randint(3, 8)
        r = 10 * rng.randint(1, 3)
        v1 = rng.choice([1, 2])
        v2 = rng.choice([2, 3, 4])
        oc = p + q_ + r
        t = F(oc, v1 + v2)
        if t.denominator != 1 or oc > 150:
            continue
        q = (f'射线 $OM$ 上依次有三点 $A$、$B$、$C$，满足 $OA={p}$，$AB={q_}$，$BC={r}$（单位：cm）．'
             f'点 $P$ 从点 $O$ 出发沿 $OM$ 方向以 ${v1}$ cm/秒匀速运动，点 $Q$ 从点 $C$ 出发'
             f'沿 $CO$ 方向以 ${v2}$ cm/秒匀速运动，两点同时出发．'
             f'（1）经过多长时间 $P$、$Q$ 两点相遇？'
             f'（2）当点 $P$ 运动到线段 $AB$ 上时，分别取 $OP$ 和 $AB$ 的中点 $E$、$F$，'
             f'求 $\\frac{{OB-AP}}{{EF}}$ 的值．')
        sol = (f'（1）$OC={p}+{q_}+{r}={oc}$，$({v1}+{v2})t={oc}$，$t={S(t)}$ 秒\n'
               f'（2）设 $OP=a$，$OB={p + q_}$，$AP=a-{p}$\n'
               f'$OE=\\frac{{a}}{{2}}$，$OF={p}+\\frac{{{q_}}}{{2}}$，$EF={p}+\\frac{{{q_}}}{{2}}-\\frac{{a}}{{2}}$\n'
               f'$\\frac{{OB-AP}}{{EF}}=\\frac{{{2 * p + q_}-a}}{{\\frac{{{2 * p + q_}-a}}{{2}}}}=2$，是定值')
        # 独立路：随机取两个 P 位置硬算比值
        ratios = []
        for a_ in (F(p) + 1, F(p) + q_ - 1):
            e_ = a_ / 2
            f_ = F(2 * p + q_, 2)
            ratios.append((F(p + q_) - (a_ - p)) / (f_ - e_))
        assert ratios[0] == ratios[1]
        t2 = None
        for tt in range(1, 400):
            if v1 * tt + v2 * tt == oc:
                t2 = F(tt)
                break
        return Q('g5_two_points', 5, q,
                 f'（1）${S(t)}$ 秒　（2）$2$（定值）', sol,
                 ((t, F(2)), (t2, ratios[0])), lv)


def g5_pd_kac(rng, lv=3):
    """C、D 从 P、B 出发同向左行，总有 PD=k·AC → AP=AB/(k+1)；再求 PQ/AB"""
    while True:
        k = rng.choice([2, 3])
        L = (k + 1) * rng.randint(3, 12)
        v1 = rng.choice([1, 2])
        v2 = k * v1
        if L > 60:
            continue
        ap = F(L, k + 1)
        # 🔴 PQ = AB - 2AP（Q 在 AB 上那支），不是 AB/(k+1)——双路闸 2026-08-22 实抓
        ratio = F(k - 1, k + 1)
        q = (f'点 $P$ 是定长线段 $AB={L}$ 上一点，点 $C$、$D$ 分别从点 $P$、$B$ 同时出发，'
             f'以每秒 ${v1}$、${v2}$ 个单位长度的速度沿直线 $AB$ 向左运动'
             f'（点 $C$ 在线段 $AP$ 上，点 $D$ 在线段 $BP$ 上）．'
             f'（1）若运动到任一时刻总有 $PD={k}AC$，求 $AP$ 的长；'
             f'（2）在（1）的条件下，点 $Q$ 是直线 $AB$ 上一点，且 $AQ-BQ=PQ$，'
             f'求 $\\frac{{PQ}}{{AB}}$ 的值．')
        sol = (f'（1）设 $AP=u$，$t$ 秒后 $AC=u-{coef(v1)}t$，$PD={L}-u-{coef(v2)}t$\n'
               f'$PD={k}AC$ 对任意 $t$ 成立 $\\Rightarrow {L}-u={k}u$，$u={S(ap)}$\n'
               f'（2）①$Q$ 在线段 $AB$ 上：由 $AQ-BQ=PQ$ 得 $AQ=AB-AP$，\n'
               f'$PQ=AB-2AP={L}-2\\times{S(ap)}={S(F(L) - 2 * ap)}$，比值 ${S(ratio)}$\n'
               f'②$Q$ 在 $B$ 右侧：$AQ-BQ=AB$，此时 $PQ=AB$，比值 $1$')
        # 独立路：数值验 (1)（两个不同 t 都成立）与 (2)①
        u = ap
        okt = all((L - u - v2 * tt) == k * (u - v1 * tt) for tt in (0, 1))
        qpos = F(k, k + 1) * L                      # Q 在 AB 上的解
        pq = qpos - u
        return Q('g5_pd_kac', 5, q,
                 f'（1）$AP={S(ap)}$　（2）$\\frac{{PQ}}{{AB}}={S(ratio)}$ 或 $1$', sol,
                 ((ap, ratio, True), (u, pq / L, okt)), lv)


def g5_four_mid(rng, lv=3):
    """AC=m、BC=n，D、E 为 AC、BC 中点，F 为 DE 中点：DE=AB/2、CF=|m-n|/4；AB=12CF → AC:CB=2 或 1/2"""
    while True:
        m = 2 * rng.randint(2, 10)
        n = 2 * rng.randint(2, 10)
        if m == n or (m + n) > 60:
            continue
        de = F(m + n, 2)
        cf = F(abs(m - n), 4)
        if cf.denominator != 1:
            continue
        A = 0
        C = m
        B = m + n
        D, E = F(m, 2), C + F(n, 2)
        Fp = (D + E) / 2
        q = (f'点 $C$ 在线段 $AB$ 上，$AC={m}$，$BC={n}$，点 $D$ 为 $AC$ 的中点，'
             f'点 $E$ 为 $BC$ 的中点，点 $F$ 为 $DE$ 的中点．'
             f'（1）求 $DE$、$CF$ 的长；'
             f'（2）若另有一点 $C$ 使 $AB=12CF$，求 $\\frac{{AC}}{{CB}}$ 的值．')
        sol = (f'（1）$DE=DC+CE=\\frac{{1}}{{2}}({m}+{n})={S(de)}$\n'
               f'$CF=|CD-DF|=\\frac{{|{m}-{n}|}}{{4}}={S(cf)}$\n'
               f'（2）设 $AC=a$、$CB=b$，$CF=\\frac{{|a-b|}}{{4}}$，$AB=a+b$\n'
               f'$a+b=12\\times\\frac{{|a-b|}}{{4}}=3|a-b|$，得 $\\frac{{a}}{{b}}=2$ 或 $\\frac{{1}}{{2}}$')
        return Q('g5_four_mid', 5, q,
                 f'（1）$DE={S(de)}$，$CF={S(cf)}$　（2）$2$ 或 $\\frac{{1}}{{2}}$', sol,
                 ((de, cf), (E - D, abs(C - Fp))), lv)


# ────────────────────────── 类型 → 生成器 ──────────────────────────
TYPE_GENS = {
    1: [g1_two_ends, g1_extend_mid, g1_ratio_mid, g1_mid_third, g1_frac_times],
    2: [g2_mid_ratio, g2_ratio_de, g2_extend_mid, g2_mid_split, g2_double_mid_eq],
    3: [g3_extend_mid, g3_line_cut, g3_three_points, g3_line_half, g3_mid_third_two],
    4: [g4_share_end, g4_both_mid, g4_separate, g4_overlap, g4_iterate],
    5: [g5_one_point, g5_two_points, g5_pd_kac, g5_four_mid],
}
GEN_META = {g.__name__: {'kp': (KP_MID if t == 4 else KP_HECHA)}
            for t, gs in TYPE_GENS.items() for g in gs}
DIFF_BY_LV = {1: '巩固', 2: '中档', 3: '压轴'}


# ────────────────────────── 闸：双路实算 + 去重 + 值域 ──────────────────────────
def verify(items, label='卷'):
    """🔴 全绿才许入库。四道：①双路一致 ②题面不撞 ③骨架不撞 ④值域合理。"""
    bad = []
    seen_q, seen_sk = {}, {}
    for i, it in enumerate(items, 1):
        closed, indep = it['check']
        if len(closed) != len(indep):
            bad.append(f'#{i} {it["gen"]}：双路元数不等')
            continue
        for a, b in zip(closed, indep):
            if isinstance(a, bool) or isinstance(b, bool):
                if bool(a) != bool(b):
                    bad.append(f'#{i} {it["gen"]}：双路判定不一致 {a} vs {b}')
            elif F(a) != F(b):
                bad.append(f'#{i} {it["gen"]}：双路值不一致 闭式={a} 坐标={b}')
        if it['q'] in seen_q:
            bad.append(f'#{i} {it["gen"]}：题面与 #{seen_q[it["q"]]} 完全相同')
        seen_q.setdefault(it['q'], i)
        sk = _skel(it['q'])
        seen_sk.setdefault(sk, []).append(i)
        # 值域闸：答案里不许出现负数/零长度
        for v in closed:
            if isinstance(v, bool):
                continue
            if F(v) <= 0:
                bad.append(f'#{i} {it["gen"]}：答案 {v} ≤0，线段长必须为正')
            if F(v).denominator > 12:
                bad.append(f'#{i} {it["gen"]}：答案 {v} 分母过大，不适合初一')
    for sk, idxs in seen_sk.items():
        if len(idxs) > 1:
            bad.append(f'骨架重复：题 {idxs} 同型（{sk[:34]}…）')
    if bad:
        print(f'🔴 {label} verify 不过（{len(bad)} 条）：')
        for b in bad:
            print('   ', b)
        return False
    print(f'🟢 {label} verify 全绿：{len(items)} 题（双路一致/题面骨架不撞/值域合理）')
    return True


def build_page(typ, seed, n=None):
    """出一页：类型 typ 的 n 道题（缺省 = 该类型全部骨架各一道，天然不同型）。"""
    gens = TYPE_GENS[typ]
    n = n or len(gens)
    rng = Random(seed)
    out = []
    for j in range(n):
        out.append(gens[j % len(gens)](rng))
    return out


if __name__ == '__main__':
    allq = []
    for t in (1, 2, 3, 4, 5):
        page = build_page(t, seed=20260822 + t * 97)
        print(f'--- 类型{t} {TYPE_NAME[t]} ---')
        for q in page:
            print('  ', q['gen'], '|', q['ans'])
        allq += page
    sys.exit(0 if verify(allq, '自检全类型') else 1)
