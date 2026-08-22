# -*- coding: utf-8 -*-
"""浙教七上 · 一元一次方程的解法 · DSL 题库（五考点 · 同源 token + 双路实算）
==============================================================================
2026-08-22 立。源料 = 测试数据/一元一次方程/（强化训练3 五张照片，26 题×2 小问），
**不照录原题**，按解法结构归成五个考点后参数化重造。

🔴 同源（消灭"题面写的和算的不是一回事"）：一道方程只有**一份 token 结构**，
   题面 LaTeX 与求值器都从它生成——不存在双录漂移，tex 里写错数字这种事在结构上不可能。

🔴 双路实算：
   路 A（构造路）= 先定根 x0，再反解出某个常数项，使方程恰好以 x0 为根；
   路 B（求解路）= 把两边当 x 的一次函数，在 x=0 与 x=1 各求一次值得到斜率与截距，
   解 kx+b=0 得根。两路不等 = verify 拒收。构造从不解方程、求解从不看构造，是两条真独立的路。

五考点（＝五个专项，与「线段专项」同结构）：
  ① 移项与合并   ② 去括号   ③ 去分母   ④ 分母含小数   ⑤ 综合·分数系数（难）
"""
import re
import sys
from fractions import Fraction as F
from math import gcd
from random import Random

sys.stdout.reconfigure(encoding='utf-8')

# ── KG 落点（现行叶子）────────────────────────────────────────────────
KP_YIXIANG = '100005002002'          # 移项解方程
KP_KUOHAO = '100005002003001'        # 去括号解一元一次方程
KP_FENMU = '100005002003003'         # 去分母解一元一次方程

TIPS = {
    1: '先把带 $x$ 的移到左边、数字移到右边——**移过去的项要变号**，再合并、最后两边同除以 $x$ 的系数。',
    2: '先去括号：括号前是「$-$」号，**里面每一项都要变号**；然后移项、合并、系数化 1。',
    3: '两边同乘各分母的最小公倍数去分母——**不含分母的项也要乘**，这是最常丢的一步。',
    4: '分母有小数先化整：分子分母同乘 10（或 100），变成整数分母再按去分母做。',
    5: '五步都用上：去分母 → 去括号 → 移项 → 合并 → 系数化 1；带分数先化成假分数。',
}
TYPE_NAME = {1: '移项与合并', 2: '去括号', 3: '去分母', 4: '分母含小数', 5: '综合·分数系数'}
KP_OF = {1: KP_YIXIANG, 2: KP_KUOHAO, 3: KP_FENMU, 4: KP_FENMU, 5: KP_FENMU}


# ══════════════════ 数与 LaTeX ══════════════════
def S(v):
    """Fraction → LaTeX（整数直出，分数走 \\frac，负号提到最前）。"""
    v = F(v)
    if v.denominator == 1:
        return str(v.numerator)
    return ('-' if v < 0 else '') + r'\frac{%d}{%d}' % (abs(v.numerator), v.denominator)


def coef_tex(a, var='x'):
    """系数×x 的写法：1x→x，-1x→-x，分数→\\frac{p}{q}x。"""
    a = F(a)
    if a == 1:
        return var
    if a == -1:
        return '-' + var
    return S(a) + var


def dec_tex(v):
    """分母的写法：整数直出；🔴 非整数分母印成**小数**（0.5／2.5／0.2）——
    考点④的题面就是要保留小数分母，化整是解析里的第一步，不能在题面就化掉。"""
    v = F(v)
    if v.denominator == 1:
        return str(v.numerator)
    f = float(v)
    s = ('%.4f' % f).rstrip('0').rstrip('.')
    return s if F(s) == v else S(v)


def lin_tex(a, b, var='x'):
    """一次式 ax+b 的裸写法（用于中间步骤）。"""
    if a == 0:
        return S(b)
    s = coef_tex(a, var)
    if b == 0:
        return s
    return s + ('+' if b > 0 else '-') + S(abs(b))


# ══════════════════ token：一道方程只有这一份结构 ══════════════════
# 每项 = dict，kind ∈ {'x','c','par','frac','fracpar'}；sign 在 coef/常数里自带。
#   x        : {'k':'x','a':F}                      → a·x
#   c        : {'k':'c','b':F}                      → b
#   par      : {'k':'par','m':F,'a':F,'b':F}        → m(a x + b)
#   frac     : {'k':'frac','a':F,'b':F,'d':F}       → (a x + b)/d
#   fracpar  : {'k':'fracpar','m':F,'a':F,'b':F,'d':F} → m(a x + b)/d
def T_x(a):
    return {'k': 'x', 'a': F(a)}


def T_c(b):
    return {'k': 'c', 'b': F(b)}


def T_par(m, a, b):
    return {'k': 'par', 'm': F(m), 'a': F(a), 'b': F(b)}


def T_frac(a, b, d):
    return {'k': 'frac', 'a': F(a), 'b': F(b), 'd': F(d)}


def T_fracpar(m, a, b, d):
    return {'k': 'fracpar', 'm': F(m), 'a': F(a), 'b': F(b), 'd': F(d)}


def t_val(t, x):
    """项在 x 处的值。"""
    if t['k'] == 'x':
        return t['a'] * x
    if t['k'] == 'c':
        return t['b']
    if t['k'] == 'par':
        return t['m'] * (t['a'] * x + t['b'])
    if t['k'] == 'frac':
        return (t['a'] * x + t['b']) / t['d']
    return t['m'] * (t['a'] * x + t['b']) / t['d']


def t_lin(t):
    """项展开成 (A, B) 表示 A·x + B。"""
    if t['k'] == 'x':
        return t['a'], F(0)
    if t['k'] == 'c':
        return F(0), t['b']
    if t['k'] == 'par':
        return t['m'] * t['a'], t['m'] * t['b']
    if t['k'] == 'frac':
        return t['a'] / t['d'], t['b'] / t['d']
    return t['m'] * t['a'] / t['d'], t['m'] * t['b'] / t['d']


def t_tex(t, lead):
    """项的 LaTeX；lead=True 表示它是该侧第一项（不带前导 +）。"""
    def wrap(body, neg):
        if neg:
            return '-' + body
        return body if lead else '+' + body

    if t['k'] == 'x':
        a = t['a']
        return wrap(coef_tex(abs(a)), a < 0)
    if t['k'] == 'c':
        b = t['b']
        return wrap(S(abs(b)), b < 0)
    if t['k'] == 'par':
        m, inner = t['m'], lin_tex(t['a'], t['b'])
        head = '' if abs(m) == 1 else S(abs(m))
        return wrap(head + r'\left(%s\right)' % inner, m < 0)
    if t['k'] == 'frac':
        a, b, d = t['a'], t['b'], t['d']
        neg = d < 0
        # 负号提到分式前（教辅写法）：\frac{-5x-9}{4} 印成 -\frac{5x+9}{4}
        if (a < 0 and b <= 0) or (a == 0 and b < 0):
            a, b, neg = -a, -b, not neg
        return wrap(r'\frac{%s}{%s}' % (lin_tex(a, b), dec_tex(abs(d))), neg)
    m = t['m']
    head = '' if abs(m) == 1 else S(abs(m))
    num = head + r'\left(%s\right)' % lin_tex(t['a'], t['b'])
    return wrap(r'\frac{%s}{%s}' % (num, dec_tex(t['d'])), m < 0)


def norm_side(side):
    """侧内整理（题面与步骤都用它）：
       ①小数分母化整（分子分母同乘，(ax+b)/0.5 → (2ax+2b)/1）
       ②分母为 1 的分式摊平成 x 项+常数
       ③同侧常数合并成一项（避免出现「=3+…+2」这种没合并的丑写法）。"""
    out, const = [], F(0)
    for t in side:
        t = dict(t)
        if t['k'] in ('frac', 'fracpar') and t['d'].denominator != 1:
            q = t['d'].denominator
            t['a'] *= q
            t['b'] *= q
            t['d'] = F(t['d'].numerator)
        if t['k'] == 'frac' and t['d'] == 1:
            if t['a']:
                out.append(T_x(t['a']))
            const += t['b']
            continue
        if t['k'] == 'fracpar' and t['d'] == 1:
            t = T_par(t['m'], t['a'], t['b'])
        if t['k'] == 'c':
            const += t['b']
            continue
        out.append(t)
    if const or not out:
        out.append(T_c(const))
    return out


def side_tex(side):
    return ''.join(t_tex(t, i == 0) for i, t in enumerate(side))


def side_val(side, x):
    return sum((t_val(t, x) for t in side), F(0))


def side_lin(side):
    A = sum((t_lin(t)[0] for t in side), F(0))
    B = sum((t_lin(t)[1] for t in side), F(0))
    return A, B


def tidy_side(side):
    """题面用的轻整理：**只合并同侧常数**，小数分母原样保留（那是考点④的题眼）。"""
    out, const = [], F(0)
    for t in side:
        if t['k'] == 'c':
            const += t['b']
        else:
            out.append(t)
    if const or not out:
        out.append(T_c(const))
    return out


def eq_tex(L, R):
    return side_tex(tidy_side(L)) + '=' + side_tex(tidy_side(R))


def solve_indep(L, R):
    """🔴 路 B（独立求解）：两边当一次函数，取 x=0/1 两点定斜率截距再解根。
    完全不看构造过程——构造错了这里就对不上。"""
    d0 = side_val(L, F(0)) - side_val(R, F(0))
    d1 = side_val(L, F(1)) - side_val(R, F(1))
    k = d1 - d0
    if k == 0:
        return None
    return -d0 / k


def lcm_of(ds):
    out = 1
    for d in ds:
        d = int(d)
        out = out * d // gcd(out, d)
    return out


# ══════════════════ 解析：五步法（数字全部实算，不手写） ══════════════════
def steps_md(L, R):
    lines = []
    raw_dec = any(t['d'].denominator != 1 for t in L + R if t['k'] in ('frac', 'fracpar'))
    L, R = norm_side(L), norm_side(R)
    if raw_dec:
        lines.append(f'分母化整：分子分母同乘　$\Rightarrow$　${side_tex(L)}={side_tex(R)}$')
    dens = [int(t['d']) for t in L + R if t['k'] in ('frac', 'fracpar')]
    cur_L, cur_R = L, R
    if dens:
        m = lcm_of(dens)
        def mul(side):
            out = []
            for t in side:
                if t['k'] == 'frac':
                    f = F(m) / t['d']
                    out.append(T_par(f, t['a'], t['b']) if f != 1 else T_par(1, t['a'], t['b']))
                elif t['k'] == 'fracpar':
                    out.append(T_par(t['m'] * F(m) / t['d'], t['a'], t['b']))
                elif t['k'] == 'x':
                    out.append(T_x(t['a'] * m))
                elif t['k'] == 'c':
                    out.append(T_c(t['b'] * m))
                else:
                    out.append(T_par(t['m'] * m, t['a'], t['b']))
            return out
        cur_L, cur_R = mul(L), mul(R)
        lines.append(f'去分母：两边乘 ${m}$　$\\Rightarrow$　${eq_tex(cur_L, cur_R)}$')
    if any(t['k'] in ('par', 'fracpar') for t in cur_L + cur_R):
        a1, b1 = side_lin(cur_L)
        a2, b2 = side_lin(cur_R)
        lines.append(f'去括号：${lin_tex(a1, b1)}={lin_tex(a2, b2)}$')
    A1, B1 = side_lin(cur_L)
    A2, B2 = side_lin(cur_R)
    A, B = A1 - A2, B2 - B1
    # 🔴 移项单独成一步：这是最容易错的一步（变号），合并掉就没得教了
    if A2 != 0 or B1 != 0:
        # 🔴 系数/常数为 0 的一侧不印（否则会出现 "0x-7x=…" 这种不像人写的式子）
        lhs = coef_tex(A1) if A1 else ''
        if A2 > 0:
            lhs += ('-' + coef_tex(A2)) if lhs else coef_tex(-A2)
        elif A2 < 0:
            lhs += ('+' if lhs else '') + coef_tex(-A2)
        rhs = S(B2) if B2 else ''
        if B1 > 0:
            rhs += ('-' + S(B1)) if rhs else S(-B1)
        elif B1 < 0:
            rhs += ('+' if rhs else '') + S(-B1)
        rhs = rhs or '0'
        lines.append(f'移项（**移过去的项变号**）：${lhs}={rhs}$')
    lines.append(f'合并：${coef_tex(A)}={S(B)}$')
    if A != 1:
        lines.append(f'系数化 1：两边同除以 ${S(A)}$　$\\Rightarrow$　$x={S(B / A)}$')
    return '\n'.join(lines)


def Q(gen, typ, L, R, x0, lv):
    return {'gen': gen, 'type': typ, 'kp': KP_OF[typ], 'lv': lv,
            'q': f'解方程：${eq_tex(L, R)}$',
            'ans': f'$x={S(x0)}$',
            'sol': steps_md(L, R),
            'check': ((x0,), (solve_indep(L, R),))}


def _nz(rng, lo, hi):
    v = 0
    while v == 0:
        v = rng.randint(lo, hi)
    return v


def _root(rng):
    """根优先取整数，偶尔取半整数（初一口味）。"""
    return F(_nz(rng, -12, 12)) if rng.random() < 0.82 else F(_nz(rng, -9, 9), 2)


# ══════════════════ 考点① 移项与合并 ══════════════════
def g1_both_sides(rng, lv=1):
    """ax+b=cx+d"""
    while True:
        x0 = _root(rng)
        a, c = _nz(rng, -9, 9), _nz(rng, -9, 9)
        if a == c:
            continue
        b = _nz(rng, -20, 20)
        d = (a - c) * x0 + b
        if d.denominator != 1 or abs(d) > 60:
            continue
        return Q('g1_both_sides', 1, [T_x(a), T_c(b)], [T_x(c), T_c(d)], x0, lv)


def g1_three_terms(rng, lv=1):
    """ax+b-cx=d（同侧先合并）"""
    while True:
        x0 = _root(rng)
        a, c = _nz(rng, 2, 9), _nz(rng, 2, 9)
        if a == c:
            continue
        b = _nz(rng, -18, 18)
        d = (a - c) * x0 + b
        if d.denominator != 1 or abs(d) > 60:
            continue
        return Q('g1_three_terms', 1, [T_x(a), T_c(b), T_x(-c)], [T_c(d)], x0, lv)


def g1_const_left(rng, lv=1):
    """b-ax=cx+d（常数在前）"""
    while True:
        x0 = _root(rng)
        a, c = _nz(rng, 1, 8), _nz(rng, -8, 8)
        if -a == c:
            continue
        b = _nz(rng, -15, 25)
        d = (-a - c) * x0 + b
        if d.denominator != 1 or abs(d) > 60:
            continue
        return Q('g1_const_left', 1, [T_c(b), T_x(-a)], [T_x(c), T_c(d)], x0, lv)


def g1_x_right(rng, lv=1):
    """b=cx+d 型（未知数只在右边，练移项方向）"""
    while True:
        x0 = _root(rng)
        c = _nz(rng, -9, 9)
        d = _nz(rng, -20, 20)
        b = c * x0 + d
        if b.denominator != 1 or abs(b) > 60:
            continue
        return Q('g1_x_right', 1, [T_c(b)], [T_x(c), T_c(d)], x0, lv)


def g1_four_terms(rng, lv=2):
    """ax+b=cx+d 且两侧都要合并"""
    while True:
        x0 = _root(rng)
        a1, a2 = _nz(rng, -7, 7), _nz(rng, -7, 7)
        c1, c2 = _nz(rng, -7, 7), _nz(rng, -7, 7)
        if (a1 + a2) == (c1 + c2):
            continue
        b = _nz(rng, -15, 15)
        d = (a1 + a2 - c1 - c2) * x0 + b
        if d.denominator != 1 or abs(d) > 60:
            continue
        return Q('g1_four_terms', 1, [T_x(a1), T_c(b), T_x(a2)], [T_x(c1), T_x(c2), T_c(d)], x0, lv)


# ══════════════════ 考点② 去括号 ══════════════════
def g2_minus_par(rng, lv=2):
    """x-k(x+m)=n（负号在括号前，最常错）"""
    while True:
        x0 = _root(rng)
        k, m = _nz(rng, 2, 6), _nz(rng, -8, 8)
        L = [T_x(1), T_par(-k, 1, m)]
        n = side_val(L, x0)
        if n.denominator != 1 or abs(n) > 60 or (1 - k) == 0:
            continue
        return Q('g2_minus_par', 2, L, [T_c(n)], x0, lv)


def g2_par_both(rng, lv=2):
    """p(x+q)=r-s(x+t)"""
    while True:
        x0 = _root(rng)
        p, q_, s, t = _nz(rng, 2, 6), _nz(rng, -6, 6), _nz(rng, 2, 6), _nz(rng, -6, 6)
        if p + s == 0:
            continue
        L = [T_par(p, 1, q_)]
        r = side_val(L, x0) + s * (x0 + t)
        if r.denominator != 1 or abs(r) > 60:
            continue
        return Q('g2_par_both', 2, L, [T_c(r), T_par(-s, 1, t)], x0, lv)


def g2_coef_par(rng, lv=2):
    """ax+b(cx+d)=e"""
    while True:
        x0 = _root(rng)
        a, b, c, d = _nz(rng, 2, 8), _nz(rng, 2, 5), _nz(rng, 2, 5), _nz(rng, -6, 6)
        L = [T_x(a), T_par(b, c, d)]
        e = side_val(L, x0)
        if e.denominator != 1 or abs(e) > 80:
            continue
        return Q('g2_coef_par', 2, L, [T_c(e)], x0, lv)


def g2_same_par(rng, lv=2):
    """p(x-m)=n-s(x-m)（同一个括号出现两次）"""
    while True:
        x0 = _root(rng)
        p, s, m = _nz(rng, 2, 6), _nz(rng, 2, 6), _nz(rng, -6, 6)
        if p + s == 0:
            continue
        L = [T_par(p, 1, -m)]
        n = side_val(L, x0) + s * (x0 - m)
        if n.denominator != 1 or abs(n) > 60:
            continue
        return Q('g2_same_par', 2, L, [T_c(n), T_par(-s, 1, -m)], x0, lv)


def g2_merge_par(rng, lv=2):
    """ax-bx+c=d(x-e)（左边先合并再看右边括号）"""
    while True:
        x0 = _root(rng)
        a, b, c, d, e = (_nz(rng, 2, 8), _nz(rng, 2, 8), _nz(rng, -10, 10),
                         _nz(rng, 2, 5), _nz(rng, -5, 5))
        if (a - b) == d:
            continue
        L = [T_x(a), T_x(-b), T_c(c)]
        rhs = T_par(d, 1, -e)
        # 右边补一个常数使 x0 成根
        extra = side_val(L, x0) - t_val(rhs, x0)
        if extra.denominator != 1 or abs(extra) > 60:
            continue
        R = [rhs] + ([T_c(extra)] if extra != 0 else [])
        return Q('g2_merge_par', 2, L, R, x0, lv)


# ══════════════════ 考点③ 去分母 ══════════════════
def _ugly(side):
    """版面洁癖闸：分式可约（(3x+6)/3）、m 与分母相消（2(...)/2）都不像人出的题。"""
    from math import gcd as _g
    for t in side:
        if t['k'] == 'frac' and t['d'].denominator == 1:
            g = _g(_g(abs(int(t['a'])), abs(int(t['b']))), abs(int(t['d'])))
            if g > 1:
                return True
        if t['k'] == 'fracpar' and t['m'] == t['d']:
            return True
    return False


def _mk_frac_eq(rng, gen, typ, build, lv, cap=80):
    """通吃壳：build(rng,x0) → (L,R_head)；补常数使 x0 成根。"""
    for _ in range(400):
        x0 = _root(rng)
        L, Rh = build(rng, x0)
        if L is None:
            continue
        extra = side_val(L, x0) - side_val(Rh, x0)
        # 🔴 补出来的常数必须是整数：否则题面会冒出 rac{69}{2} 这种不像题的常数
        if extra.denominator != 1 or abs(extra) > cap:
            continue
        if _ugly(L) or _ugly(Rh):
            continue
        A1, B1 = side_lin(L)
        A2, B2 = side_lin(Rh + [T_c(extra)])
        if A1 - A2 == 0:
            continue
        R = Rh + ([T_c(extra)] if extra != 0 else [])
        if not R:
            continue
        return Q(gen, typ, L, R, x0, lv)
    return None


def g3_two_frac(rng, lv=2):
    """(ax+b)/p - (cx+d)/q = e"""
    def build(rng, x0):
        p, q_ = rng.choice([(3, 6), (2, 4), (3, 4), (4, 12), (2, 6)])
        a, b = _nz(rng, 1, 5), _nz(rng, -9, 9)
        c, d = _nz(rng, 1, 5), _nz(rng, -9, 9)
        return [T_frac(a, b, p), T_frac(-c, -d, q_)], []
    return _mk_frac_eq(rng, 'g3_two_frac', 3, build, lv)


def g3_frac_int(rng, lv=2):
    """(ax+b)/p - 1 = c + (dx+e)/q （不含分母的项也要乘）"""
    def build(rng, x0):
        p, q_ = rng.choice([(2, 4), (3, 6), (2, 6), (3, 4)])
        a, b = _nz(rng, 1, 4), _nz(rng, -8, 8)
        d, e = _nz(rng, 1, 4), _nz(rng, -8, 8)
        c = _nz(rng, -6, 6)
        return [T_frac(a, b, p), T_c(-1)], [T_c(c), T_frac(d, e, q_)]
    return _mk_frac_eq(rng, 'g3_frac_int', 3, build, lv)


def g3_x_plus_frac(rng, lv=2):
    """ax + (bx+c)/p = d - (ex+f)/q"""
    def build(rng, x0):
        p, q_ = rng.choice([(2, 3), (3, 6), (2, 4), (4, 3)])
        a = _nz(rng, 1, 4)
        b, c = _nz(rng, 1, 4), _nz(rng, -8, 8)
        e, f = _nz(rng, 1, 4), _nz(rng, -8, 8)
        return [T_x(a), T_frac(b, c, p)], [T_frac(-e, -f, q_)]
    return _mk_frac_eq(rng, 'g3_x_plus_frac', 3, build, lv)


def g3_eq_frac(rng, lv=2):
    """(ax+b)/p = (cx+d)/q - 1"""
    def build(rng, x0):
        p, q_ = rng.choice([(3, 2), (3, 6), (4, 12), (2, 3)])
        a, b = _nz(rng, 1, 5), _nz(rng, -9, 9)
        c, d = _nz(rng, 1, 5), _nz(rng, -9, 9)
        return [T_frac(a, b, p)], [T_frac(c, d, q_), T_c(-1)]
    return _mk_frac_eq(rng, 'g3_eq_frac', 3, build, lv)


def g3_three_frac(rng, lv=3):
    """(ax+b)/p - (cx)/q = 1 - (dx+e)/r"""
    def build(rng, x0):
        p, q_, r = rng.choice([(3, 2, 4), (2, 3, 6), (3, 4, 6), (4, 2, 3)])
        a, b = _nz(rng, 1, 4), _nz(rng, -6, 6)
        c = _nz(rng, 1, 4)
        d, e = _nz(rng, 1, 4), _nz(rng, -6, 6)
        return [T_frac(a, b, p), T_frac(-c, 0, q_)], [T_c(1), T_frac(-d, -e, r)]
    return _mk_frac_eq(rng, 'g3_three_frac', 3, build, lv)


# ══════════════════ 考点④ 分母含小数 ══════════════════
def g4_dec_den(rng, lv=3):
    """(x+a)/0.5 - (bx+c)/2.5 = dx"""
    def build(rng, x0):
        a = _nz(rng, -8, 8)
        b, c = _nz(rng, 1, 6), _nz(rng, -8, 8)
        d = _nz(rng, -3, 3)
        return ([T_frac(1, a, F(1, 2)), T_frac(-b, -c, F(5, 2))],
                [T_x(d)])
    return _mk_frac_eq(rng, 'g4_dec_den', 4, build, lv)


def g4_dec_two(rng, lv=3):
    """(x-a)/0.2 = (x+b)/0.5"""
    def build(rng, x0):
        a, b = _nz(rng, -9, 9), _nz(rng, -9, 9)
        return [T_frac(1, -a, F(1, 5))], [T_frac(1, b, F(1, 2))]
    return _mk_frac_eq(rng, 'g4_dec_two', 4, build, lv)


def g4_dec_mix(rng, lv=3):
    """(ax+b)/0.3 - c = (dx+e)/0.6"""
    def build(rng, x0):
        a, b = _nz(rng, 1, 4), _nz(rng, -6, 6)
        d, e = _nz(rng, 1, 4), _nz(rng, -6, 6)
        c = _nz(rng, -5, 5)
        return [T_frac(a, b, F(3, 10)), T_c(-c)], [T_frac(d, e, F(3, 5))]
    return _mk_frac_eq(rng, 'g4_dec_mix', 4, build, lv)


def g4_dec_int(rng, lv=3):
    """(ax+b)/0.4 + c = dx"""
    def build(rng, x0):
        a, b = _nz(rng, 1, 4), _nz(rng, -8, 8)
        c = _nz(rng, -8, 8)
        d = _nz(rng, -4, 4)
        return [T_frac(a, b, F(2, 5)), T_c(c)], [T_x(d)]
    return _mk_frac_eq(rng, 'g4_dec_int', 4, build, lv)


def g4_dec_par(rng, lv=3):
    """m(ax+b)/0.5 = c - dx"""
    def build(rng, x0):
        m = rng.choice([2, 3])
        a, b = _nz(rng, 1, 3), _nz(rng, -5, 5)
        d = _nz(rng, 1, 5)
        return [T_fracpar(m, a, b, F(1, 2))], [T_x(-d)]
    return _mk_frac_eq(rng, 'g4_dec_par', 4, build, lv)


# ══════════════════ 考点⑤ 综合·分数系数（难）══════════════════
def g5_frac_coef(rng, lv=3):
    """(m/n)x + (x+a)/p = q(x+b)/r - (s/t)x"""
    def build(rng, x0):
        m, n = _nz(rng, 1, 4), rng.choice([2, 3, 5])
        s, t = _nz(rng, 1, 4), rng.choice([2, 3, 5])
        p, r = rng.choice([(2, 2), (2, 3), (3, 2), (4, 2)])
        a, b = _nz(rng, -6, 6), _nz(rng, -6, 6)
        q_ = rng.choice([2, 3])
        return ([T_x(F(m, n)), T_frac(1, a, p)],
                [T_fracpar(q_, 1, b, r), T_x(-F(s, t))])
    return _mk_frac_eq(rng, 'g5_frac_coef', 5, build, lv)


def g5_mixed_num(rng, lv=3):
    """ax + p/q = bx + 带分数（带分数先化假分数）"""
    def build(rng, x0):
        a, b = _nz(rng, 2, 6), _nz(rng, 1, 5)
        if a == b:
            return None, None
        p, q_ = _nz(rng, 1, 3), rng.choice([2, 4])
        whole = _nz(rng, 1, 6)
        return [T_x(a), T_c(F(p, q_))], [T_x(b), T_c(whole + F(p, q_))]
    return _mk_frac_eq(rng, 'g5_mixed_num', 5, build, lv)


def g5_par_frac(rng, lv=3):
    """x - m(ax+b)/p = c - (dx+e)/q"""
    def build(rng, x0):
        p, q_ = rng.choice([(2, 3), (3, 2), (2, 4), (3, 6)])
        m = rng.choice([1, 2])
        a, b = _nz(rng, 1, 4), _nz(rng, -6, 6)
        d, e = _nz(rng, 1, 4), _nz(rng, -6, 6)
        return [T_x(1), T_fracpar(-m, a, b, p)], [T_frac(-d, -e, q_)]
    return _mk_frac_eq(rng, 'g5_par_frac', 5, build, lv)


def g5_four_frac(rng, lv=3):
    """(ax+b)/p - (cx)/q = 1 - (dx+e)/r - (fx)/s"""
    def build(rng, x0):
        p, q_, r, s = rng.choice([(3, 2, 4, 6), (2, 3, 6, 4), (4, 3, 2, 6)])
        a, b = _nz(rng, 1, 3), _nz(rng, -5, 5)
        c = _nz(rng, 1, 3)
        d, e = _nz(rng, 1, 3), _nz(rng, -5, 5)
        f = _nz(rng, 1, 3)
        return ([T_frac(a, b, p), T_frac(-c, 0, q_)],
                [T_c(1), T_frac(-d, -e, r), T_frac(-f, 0, s)])
    return _mk_frac_eq(rng, 'g5_four_frac', 5, build, lv)


def g5_par_in_frac(rng, lv=3):
    """m(x+a)/p + (bx+c)/q = d - x"""
    def build(rng, x0):
        p, q_ = rng.choice([(2, 3), (3, 4), (2, 6), (4, 3)])
        m = rng.choice([2, 3, 4])
        a = _nz(rng, -6, 6)
        b, c = _nz(rng, 1, 4), _nz(rng, -6, 6)
        return [T_fracpar(m, 1, a, p), T_frac(b, c, q_)], [T_x(-1)]
    return _mk_frac_eq(rng, 'g5_par_in_frac', 5, build, lv)


TYPE_GENS = {
    1: [g1_both_sides, g1_three_terms, g1_const_left, g1_x_right, g1_four_terms],
    2: [g2_minus_par, g2_par_both, g2_coef_par, g2_same_par, g2_merge_par],
    3: [g3_two_frac, g3_frac_int, g3_x_plus_frac, g3_eq_frac, g3_three_frac],
    4: [g4_dec_den, g4_dec_two, g4_dec_mix, g4_dec_int, g4_dec_par],
    5: [g5_frac_coef, g5_mixed_num, g5_par_frac, g5_four_frac, g5_par_in_frac],
}
GEN_META = {g.__name__: {'kp': KP_OF[t]} for t, gs in TYPE_GENS.items() for g in gs}
DIFF_BY_LV = {1: '巩固', 2: '中档', 3: '压轴'}


def _skel(q):
    return re.sub(r'\d+', 'N', q)


def verify(items, label='卷'):
    """四闸：①双路一致（构造根 vs 系数反解根）②题面不撞 ③骨架不撞 ④根适合初一。"""
    bad = []
    seen_q, seen_sk = {}, {}
    for i, it in enumerate(items, 1):
        (x0,), (xb,) = it['check']
        if xb is None:
            bad.append(f'#{i} {it["gen"]}：x 的系数为 0，不是一元一次方程')
        elif F(x0) != F(xb):
            bad.append(f'#{i} {it["gen"]}：双路不一致 构造根={x0} 反解根={xb}')
        if F(x0).denominator > 4:
            bad.append(f'#{i} {it["gen"]}：根 {x0} 分母过大，不适合初一')
        if it['q'] in seen_q:
            bad.append(f'#{i} {it["gen"]}：题面与 #{seen_q[it["q"]]} 相同')
        seen_q.setdefault(it['q'], i)
        seen_sk.setdefault(_skel(it['q']), []).append(i)
    for sk, idxs in seen_sk.items():
        if len(idxs) > 1:
            bad.append(f'骨架重复：题 {idxs} 同型')
    if bad:
        print(f'🔴 {label} verify 不过（{len(bad)} 条）：')
        for b in bad:
            print('   ', b)
        return False
    print(f'🟢 {label} verify 全绿：{len(items)} 题（双路一致/题面骨架不撞/根合口味）')
    return True


def build_page(typ, seed, n=None):
    gens = TYPE_GENS[typ]
    n = n or len(gens)
    rng = Random(seed)
    out = []
    for j in range(n):
        it = gens[j % len(gens)](rng)
        if it is None:
            raise SystemExit(f'🔴 {gens[j % len(gens)].__name__} 出题耗尽')
        out.append(it)
    return out


if __name__ == '__main__':
    allq = []
    for t in (1, 2, 3, 4, 5):
        page = build_page(t, seed=20260822 + t * 131)
        print(f'--- 考点{t} {TYPE_NAME[t]} ---')
        for q in page:
            print('  ', q['gen'], '|', q['q'][:58], '→', q['ans'])
        allq += page
    sys.exit(0 if verify(allq, '自检全考点') else 1)
