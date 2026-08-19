# -*- coding: utf-8 -*-
"""
七上 有理数混合运算 · DSL 题库（订阅特训产线 · 工卡 0）
==========================================================
2026-08-05 立。老册（10天×20题）是无源手造的，本文件是**重建的 DSL 单一事实源**——
题面 LaTeX、答案、逐步过程链全部同源自一棵表达式树 + 模板自带的解法路径。

🔴 设计三铁律：
  1. **同源**：题面/过程/答案共用一份 Fraction 精确值，杜绝双录漂移；
  2. **过程链是模板的一部分**：每个生成器出 (LaTeX题面, 过程行[], 考点标签[])，
     过程按"老师板书"走（乘方绝对值括号先化 → 乘除 → 加减），不是通用归约器瞎拆；
  3. **每题挂考点标签**（订阅学情账本的锚）：七码词表的唯一正本 =
     `订阅特训/_产线/err_kp.json`，本文件的 KP / KP_CN 从那里读，不再自存一份

校准集 = 合刊 `books/yls_hunhe.json`（原册 200 题转录），难度分布对齐它（不复刻题目）。
verify()：逐行恒等（sympy 双路）+ 题面不撞 + 值域闸 + 步数闸 + 考点配额断言。
"""
import json as _json
import os as _os
import re as _re
import sys
from fractions import Fraction as F
from random import Random

import sympy as sp

# ── 错因考点七码词表：唯一正本 = 订阅特训/_产线/err_kp.json（2026-08-11 收敛） ──
# 此前本文件与 批改链.py / 审核台.py 各存一份硬拷贝，改一处别处不跟。
# 🔴 读不到正本直接抛错退出，绝不静默退化成空词表。
# v2 平移（2026-08-18）：词表正本随文件拷入本目录（工具箱/dsl/err_kp.json），
# 老区那份不再引用（独立生态零交互）。
_KP_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'err_kp.json')


def _load_kp(path=_KP_JSON):
    if not _os.path.exists(path):
        raise RuntimeError('🔴 错因考点词表正本缺失：%s —— 词表不许退化成空表' % path)
    with open(path, encoding='utf-8') as _fh:
        codes = _json.load(_fh).get('codes')
    if not isinstance(codes, list) or not codes:
        raise RuntimeError('🔴 词表正本 %s 里没有 codes 列表' % path)
    for c in codes:
        if not c.get('code') or not c.get('cn'):
            raise RuntimeError('🔴 词表正本 %s 有缺 code/cn 的条目：%r' % (path, c))
    return tuple(c['code'] for c in codes), {c['code']: c['cn'] for c in codes}


KP, KP_CN = _load_kp()

# ────────────────────────── 数的 LaTeX 渲染 ──────────────────────────


def fx(v, dec=False):
    """Fraction → LaTeX。dec=True 且能整表示时印小数形。"""
    v = F(v)
    if v.denominator == 1:
        return str(v.numerator)
    if dec:
        f = float(v)
        s = ('%f' % f).rstrip('0').rstrip('.')
        if F(s) == v:
            return s
    sign = '-' if v < 0 else ''
    return sign + r'\frac{%d}{%d}' % (abs(v.numerator), v.denominator)


def par_if_neg(v, dec=False):
    """链中第二+项 / 乘除操作数：负数或分数带 \\left(..\\right)"""
    h = fx(v, dec)
    if v < 0:
        return r'\left(%s\right)' % h
    return h


def chain_tex(terms, dec=False):
    """[(v, op)] op∈'+-' 首项 op 忽略 → '12+(-17)-(-3)' 风格（保留括号形，去括号是学生的事）"""
    out = fx(terms[0][0], dec) if terms[0][0] >= 0 else fx(terms[0][0], dec)
    for v, op in terms[1:]:
        out += op + par_if_neg(v, dec)
    return out


def plain_chain_tex(vals, dec=False):
    """去括号后的化简链：值序列 → '12-17+3'（负值直接用减号呈现）"""
    out = fx(vals[0], dec)
    for v in vals[1:]:
        out += ('+' + fx(v, dec)) if v >= 0 else fx(v, dec)
    return out


def ln(tex):
    return r'＝ \(%s\)' % tex


def fin(v, dec=False):
    return r'＝ \(\color{#c00}{%s}\)' % fx(v, dec)


# ────────────────────────── 题目容器 ──────────────────────────


def Q(q_tex, steps, ans, kps, feat=()):
    """一道题：题面 LaTeX（不含 \\(\\)）、过程行（含＝、含定界）、答案 Fraction、考点、特征"""
    assert kps and all(k in KP for k in kps), kps
    return {'q': r'\(%s\)' % q_tex, 'steps': steps, 'ans': F(ans),
            'kp': tuple(kps), 'feat': tuple(feat)}


# ────────────────────────── 生成器模板族 ──────────────────────────
# 每个 gen_*(rng, lv) → Q。lv ∈ 1..3 难度（项数/数域/指数上探）。


def _nz(rng, lo, hi):
    v = 0
    while v == 0:
        v = rng.randint(lo, hi)
    return v


def gen_addsub_chain(rng, lv):
    """纯加减链（含负括号项）：12+(-17)-(-3)　[sign]"""
    k = 3 + (lv >= 2) + (lv >= 3)
    while True:
        terms = [(F(_nz(rng, -20, 20)), '+')]
        for _ in range(k - 1):
            terms.append((F(_nz(rng, -20, 20)), rng.choice('+-')))
        if not any(v < 0 for v, _ in terms):        # 至少一个负数才有"符号"可练
            continue
        vals = [terms[0][0]] + [(v if op == '+' else -v) for v, op in terms[1:]]
        if abs(sum(vals)) > 60:
            continue
        return Q(chain_tex(terms),
                 [ln(plain_chain_tex(vals)), fin(sum(vals))],
                 sum(vals), ['sign'])


def gen_dec_chain(rng, lv):
    """小数加减·凑整简算：7.4-8.2+6.6-10.8　[sign, fracdec, dist]"""
    while True:
        x = rng.randint(1, 9)
        a = F(rng.randint(3, 12)) + F(x, 10)
        c = F(rng.randint(3, 12)) + F(10 - x, 10)
        y = rng.randint(1, 9)
        b = F(rng.randint(3, 12)) + F(y, 10)
        d = F(rng.randint(3, 12)) + F(10 - y, 10)
        if len({a, b, c, d}) < 4:
            continue
        v = a - b + c - d
        gh = r'\left(%s+%s\right)-\left(%s+%s\right)' % (
            fx(a, 1), fx(c, 1), fx(b, 1), fx(d, 1))
        return Q('%s-%s+%s-%s' % (fx(a, 1), fx(b, 1), fx(c, 1), fx(d, 1)),
                 [ln(gh), ln('%s-%s' % (fx(a + c, 1), fx(b + d, 1))), fin(v, 1)],
                 v, ['sign', 'fracdec', 'dist'])


def gen_abs_chain(rng, lv):
    """加减链带绝对值：12+|-7|+18-15　[abs, sign]"""
    while True:
        k = 3 + (lv >= 2)
        vals, texs = [], []
        n_abs = 1 + (lv >= 3)
        pos_abs = rng.sample(range(k), n_abs)
        for i in range(k):
            v = F(_nz(rng, -19, 19))
            op = '+' if i == 0 else rng.choice('+-')
            if i in pos_abs:
                inner = -abs(v)                     # 绝对值里放负数才有"脱号"
                t = r'\left|%s\right|' % fx(inner)
                real = abs(inner)
            else:
                t, real = par_if_neg(v), v
            if i == 0:
                texs.append(t if i in pos_abs or v >= 0 else fx(v))
                vals.append(real if op == '+' else -real)
            else:
                texs.append(op + t)
                vals.append(real if op == '+' else -real)
        v = sum(vals)
        if abs(v) > 60:
            continue
        return Q(''.join(texs),
                 [ln(plain_chain_tex(vals)), fin(v)],
                 v, ['abs', 'sign'])


def gen_pow_mixed(rng, lv):
    """乘方+乘除混合：(-1)^{2022}×2+(-2)^{3}÷4　[pow, order, sign]"""
    big = rng.choice([2021, 2022, 2023, 2024, 2025]) + (0 if rng.random() < .7 else rng.randint(-3, 3))
    sgn1 = 1 if big % 2 == 0 else -1
    a = _nz(rng, 2, 9)
    b = rng.choice([2, 3, 4, 5])
    e = rng.choice([2, 3]) if lv < 3 else rng.choice([2, 3, 4])
    pb = F(-b) ** e
    divisors = [d for d in (2, 3, 4, 5, 6, 8) if pb % d == 0]
    c = rng.choice(divisors) if divisors else 1
    v1 = F(sgn1) * a
    v2 = pb / c
    v = v1 + v2
    q_tex = r'(-1)^{%d}\times%d+(-%d)^{%d}\div%d' % (big, a, b, e, c)
    s1 = r'%s\times%d+%s\div%d' % (par_if_neg(F(sgn1)), a, par_if_neg(pb), c)
    return Q(q_tex,
             [ln(s1), ln(plain_chain_tex([v1, v2])), fin(v)],
             v, ['pow', 'order', 'sign'])


def gen_bare_pow_chain(rng, lv):
    """裸乘方链：-1^{2022}-(-6)+2-3×(-1/3)　[pow, sign, fracdec]"""
    big = rng.choice([2022, 2023, 2024, 2025])
    a, b = _nz(rng, 2, 9), _nz(rng, 2, 9)
    m = rng.randint(2, 9)
    v_pow = F(-1)                                   # -1^n = -(1^n) 恒 -1
    v_mul = F(m) * F(-1, m)                          # m×(-1/m) = -1
    vals = [v_pow, F(a), F(b), -v_mul]
    v = v_pow + a + b - v_mul
    q_tex = r'-1^{%d}-(-%d)+%d-%d\times\left(-\frac{1}{%d}\right)' % (big, a, b, m, m)
    return Q(q_tex,
             [ln(plain_chain_tex(vals)), fin(v)],
             v, ['pow', 'sign', 'fracdec'])


def gen_dist_forward(rng, lv):
    """分配律正用：(1/9+1/6-1/4)×(-36)　[dist, fracdec, paren]"""
    while True:
        k = 2 + (lv >= 2)
        dens = rng.sample([2, 3, 4, 6, 9, 12, 18], k)
        N = 36 if all(36 % d == 0 for d in dens) else None
        if N is None:
            from math import lcm
            N = lcm(*dens)
            if N > 72:
                continue
        N_s = N * rng.choice([1, -1])
        fr, ops = [], []
        for i, d in enumerate(dens):
            nu = rng.choice([1, 1, rng.randint(1, d - 1) or 1])
            f = F(nu, d)
            if f.denominator == 1:
                continue
            fr.append(f)
            ops.append('+' if i == 0 else rng.choice('+-'))
        if len(fr) != k:
            continue
        inner = fr[0]
        inner_tex = fx(fr[0])
        parts = [fr[0] * N_s]
        for f, op in zip(fr[1:], ops[1:]):
            inner = inner + f if op == '+' else inner - f
            inner_tex += op + fx(f)
            parts.append(f * N_s if op == '+' else -f * N_s)
        v = inner * N_s
        if abs(v) > 100 or v.denominator > 1:
            continue
        q_tex = r'\left(%s\right)\times%s' % (inner_tex, par_if_neg(F(N_s)))
        Nt = par_if_neg(F(N_s))
        s0 = fx(fr[0]) + r'\times%s' % Nt            # 展开式行（板书第一步）
        for f, op in zip(fr[1:], ops[1:]):
            s0 += op + fx(f) + r'\times%s' % Nt
        s1 = plain_chain_tex(parts)                  # 分配展开后的整数链
        return Q(q_tex, [ln(s0), ln(s1), fin(v)], v,
                 ['dist', 'fracdec', 'paren'])


def gen_dist_reverse(rng, lv):
    """提公因数：13×(-7)+13×(-3)-13×(-10)　[dist]"""
    while True:
        c = rng.choice([13, 17, 19, 23, 25, 37, F(1, 2), F(3, 4)])
        a, b = _nz(rng, -12, 12), _nz(rng, -12, 12)
        d = a + b + rng.choice([-1, 1]) * rng.randint(1, 5)
        s = a + b - d
        if s == 0 or abs(F(c) * s) > 150 or (F(c) * s).denominator > 1:
            continue
        ct = par_if_neg(F(c))
        q_tex = r'%s\times%s+%s\times%s-%s\times%s' % (
            ct, par_if_neg(F(a)), ct, par_if_neg(F(b)), ct, par_if_neg(F(d)))
        s1 = r'%s\times\left[%s%s-%s\right]' % (
            ct, fx(F(a)), ('+' + par_if_neg(F(b))) if b >= 0 else par_if_neg(F(b)),
            par_if_neg(F(d)).replace(r'\left(', '').replace(r'\right)', '') if d >= 0 else par_if_neg(F(d)))
        # 中括号里保持可读：a+(b)-(d) 简写成去括号前形态
        s1 = r'%s\times\left[%s\right]' % (ct, plain_chain_tex([F(a), F(b), -F(d)]))
        v = F(c) * s
        return Q(q_tex, [s1 and ln(s1), ln(r'%s\times%s' % (ct, par_if_neg(F(s)))), fin(v)],
                 v, ['dist'])


def gen_frac_div(rng, lv):
    """乘与绝对值除分数：4×(-3)+|-2|÷(2/7)　[order, abs, fracdec]
    🔴 绝对值里**必须放负数**——|9| 这种脱号形同虚设，考点没练到（样张目检抓的）"""
    while True:
        a, b = _nz(rng, 2, 9), _nz(rng, -9, -2)
        c = _nz(rng, -9, -2)
        p = rng.randint(2, 9)
        qd = rng.randint(2, 9)
        from math import gcd
        if gcd(p, qd) != 1:                          # 🔴 卷面不许出非最简分数（3/9、6/8）
            continue
        f = F(p, qd)
        if f.denominator == 1:
            continue
        v1 = F(a) * b
        v2 = abs(F(c)) / f                           # |c| ÷ p/q = |c|×q/p
        if v2.denominator > 1 and lv < 2:
            continue
        v = v1 + v2
        if abs(v) > 120 or v.denominator > 12:
            continue
        q_tex = r'%d\times%s+\left|%s\right|\div\frac{%d}{%d}' % (
            a, par_if_neg(F(b)), fx(F(c)), p, qd)
        s1 = r'%s+%d\times\frac{%d}{%d}' % (par_if_neg(v1), abs(c), qd, p)
        return Q(q_tex, [ln(s1), ln(plain_chain_tex([v1, v2])), fin(v)],
                 v, ['order', 'abs', 'fracdec'])


def gen_div_by_unit_frac(rng, lv):
    """括号链除以单位分数（本质分配）：(-1/4-2/5+1/10)÷(-1/20)　[dist, fracdec, paren, sign]"""
    while True:
        from math import lcm
        dens = rng.sample([2, 4, 5, 8, 10, 20], 3 if lv >= 2 else 2)
        N = lcm(*dens)
        if N > 40:
            continue
        fr = [F(rng.choice([1, 1, 3]), d) * rng.choice([1, -1]) for d in dens]
        if any(f.denominator == 1 for f in fr):
            continue
        inner = sum(fr)
        v = inner * (-N)                             # ÷(-1/N) = ×(-N)
        if abs(v) > 60 or v.denominator > 1:
            continue
        inner_tex = fx(fr[0]) + ''.join(
            ('+' + fx(f)) if f >= 0 else fx(f) for f in fr[1:])
        q_tex = r'\left(%s\right)\div\left(-\frac{1}{%d}\right)' % (inner_tex, N)
        s1 = r'\left(%s\right)\times\left(-%d\right)' % (inner_tex, N)
        parts = [f * (-N) for f in fr]
        return Q(q_tex, [ln(s1), ln(plain_chain_tex(parts)), fin(v)],
                 v, ['dist', 'fracdec', 'paren', 'sign'])


def gen_mixed_long(rng, lv):
    """乘方×括号×小数长链：2^{3}×(1-1/4)×0.5　[pow, fracdec, order, paren]"""
    while True:
        e = rng.choice([2, 3])
        base = rng.choice([2, 3]) if e == 3 else rng.choice([2, 3, 4, 5])
        pv = F(base) ** e
        d = rng.choice([2, 3, 4, 5, 8])
        f = 1 - F(1, d)
        dc = rng.choice([F(1, 2), F(1, 4), F(3, 4), F(1, 5)])
        v = pv * f * dc
        if v.denominator > 8 or abs(v) > 60:
            continue
        q_tex = r'%d^{%d}\times\left(1-\frac{1}{%d}\right)\times%s' % (
            base, e, d, fx(dc, 1))
        s1 = r'%s\times%s\times%s' % (fx(pv), fx(f), fx(dc, 1))
        return Q(q_tex, [ln(s1), fin(v, dec=(v.denominator in (1, 2, 4, 5, 8)))],
                 v, ['pow', 'fracdec', 'order', 'paren'])


def gen_nested_paren(rng, lv):
    """中括号嵌套：18-[12-(7-4)]×2　[paren, order, sign]"""
    while True:
        c1, c2 = rng.randint(2, 15), rng.randint(2, 9)
        inner = c1 - c2                              # (c1-c2)
        b1 = rng.randint(max(inner + 1, 2), 20)
        mid = b1 - inner
        m = rng.choice([2, 3, 4])
        a1 = rng.randint(-20, 30)
        v = F(a1) - F(mid) * m
        if abs(v) > 80 or inner <= 0 or mid <= 0:
            continue
        q_tex = r'%s-\left[%d-\left(%d-%d\right)\right]\times%d' % (
            fx(F(a1)), b1, c1, c2, m)
        return Q(q_tex,
                 [ln(r'%s-\left[%d-%d\right]\times%d' % (fx(F(a1)), b1, inner, m)),
                  ln(r'%s-%d\times%d' % (fx(F(a1)), mid, m)),
                  ln(plain_chain_tex([F(a1), -F(mid) * m])), fin(v)],
                 v, ['paren', 'order', 'sign'])


# 模板注册表：考点 → 主生成器（一题多标签，主锚用于配额）
def gen_frac_addsub(rng, lv):
    """分数加减·通分：-1/3+5/6-1/2　[fracdec, sign]
    🔴 2026-08-06 补变体（同型闸落地后 fracdec 骨架撑不起 6 题配额）——
    直练「先通分再合并」，正是小李摸底第 18 题（1/3-1/9 分母直减）的错点技能"""
    from math import gcd, lcm
    while True:
        ds = rng.sample([2, 3, 4, 5, 6, 8, 9, 10, 12], 3)
        L = lcm(*ds)
        if L > 36:
            continue
        fs = []
        for d in ds:
            p = rng.randint(1, d - 1)
            if gcd(p, d) != 1:
                fs = None
                break
            fs.append(F(p, d))
        if not fs or len(set(fs)) < 3:
            continue
        sg = [rng.choice([1, -1]) for _ in range(3)]
        if sg == [1, 1, 1]:                        # 全正练不到符号
            continue
        a, b, c = (s * f for s, f in zip(sg, fs))
        v = a + b + c
        if v == 0 or v.denominator > 12 or abs(v) > 3:
            continue

        def term(x, first=False):
            t = r'\frac{%d}{%d}' % (abs(x.numerator), x.denominator)
            return (('-' if x < 0 else '') if first else
                    ('-' if x < 0 else '+')) + t
        q_tex = term(a, True) + term(b) + term(c)
        nums = [x.numerator * (L // x.denominator) for x in (a, b, c)]

        def lterm(n, first=False):
            t = r'\frac{%d}{%d}' % (abs(n), L)
            return (('-' if n < 0 else '') if first else
                    ('-' if n < 0 else '+')) + t
        s1 = lterm(nums[0], True) + lterm(nums[1]) + lterm(nums[2])
        s_num = sum(nums)
        steps = [ln(s1)]
        if F(s_num, L) != v or ('-' if s_num < 0 else '') + \
                r'\frac{%d}{%d}' % (abs(s_num), L) != fx(v):
            steps.append(ln(('-' if s_num < 0 else '') +
                            r'\frac{%d}{%d}' % (abs(s_num), L)))
        steps.append(fin(v))
        return Q(q_tex, steps, v, ['fracdec', 'sign'])


def gen_dec_frac_mix(rng, lv):
    """分数小数互化：(3/5-1.4)×(-5)　[fracdec, order, paren]（2026-08-06 补变体）"""
    while True:
        f = rng.choice([F(1, 2), F(1, 5), F(2, 5), F(3, 5), F(4, 5),
                        F(3, 10), F(7, 10), F(9, 10)])
        dec = F(rng.randint(2, 19), 10)
        if dec == f or dec.denominator == 1:       # 排整数、排相消为 0 的假算
            continue
        e = rng.choice([-9, -8, -7, -6, -5, -4, -3, -2, 3, 4, 6, 7])
        inner = f - dec
        v = inner * e
        if inner == 0 or abs(v) > 60:
            continue
        fd, dd = '%.1f' % float(f), '%.1f' % float(dec)
        idd = '%.1f' % float(inner)                # f 分母整除 10 → 全程一位小数精确
        q_tex = r'\left(\frac{%d}{%d}-%s\right)\times%s' % (
            f.numerator, f.denominator, dd, par_if_neg(F(e)))
        s2 = (r'\left(%s\right)' % idd if inner < 0 else idd) + \
            r'\times%s' % par_if_neg(F(e))
        return Q(q_tex,
                 [ln(r'\left(%s-%s\right)\times%s' % (fd, dd, par_if_neg(F(e)))),
                  ln(s2), fin(v, True)],
                 v, ['fracdec', 'order', 'paren'])


GENS = {
    'sign': (gen_addsub_chain,),
    'abs': (gen_abs_chain,),
    'pow': (gen_pow_mixed, gen_bare_pow_chain),
    'dist': (gen_dist_forward, gen_dist_reverse, gen_div_by_unit_frac),
    'fracdec': (gen_dec_chain, gen_frac_div, gen_frac_addsub, gen_dec_frac_mix),
    'order': (gen_frac_div, gen_mixed_long),      # 别放 pow_mixed：pow 配额已出它，一卷同型 3 次太密
    'paren': (gen_nested_paren, gen_mixed_long),
}
ALL_GENS = (gen_addsub_chain, gen_dec_chain, gen_abs_chain, gen_pow_mixed,
            gen_bare_pow_chain, gen_dist_forward, gen_dist_reverse,
            gen_frac_div, gen_div_by_unit_frac, gen_mixed_long, gen_nested_paren)


# ────────────────────────── 出卷 API（订阅产线入口） ──────────────────────────


def _skel(q):
    """题面骨架签名：数字全归一成 N——用于卷内同型限次"""
    return _re.sub(r'\d+', 'N', q)


def build_paper(seed, quota, lv=1, history=()):
    """按考点配额出一卷。
    quota: {'sign':3,'pow':3,...} 主锚配额（和=题量）；lv: 全卷难度档；
    history: 历史题面集合（跨天不撞——订阅 21 天题面全程互异）。
    每题带 anchor=主锚考点（题单审计配比用）。
    🔴 卷内同骨架 ≤2（2026-08-06 小李 D2 实抓：一卷 4 道 a×(-b)+|-c|÷分数 同型，
    其中两道系数都撞 ÷3/7——verify 只闸题面字符串不闸结构，这里补上）。
    → [Q, ...]（乱序后返回）"""
    rng = Random(seed)
    seen = set(history)
    skel_n = {}
    out = []
    for kp, k in quota.items():
        gens = GENS[kp]
        for i in range(k):
            # 🔴 骨架上限逐级放宽（2026-08-10 加）：先按 ≤2 找，找不到才退让。
            #    根因是**生成器容量有硬顶**——`order`/`pow` 各只有 2 个生成器 = 2 种骨架，
            #    在 ≤2 下整卷最多只出得了 4 题；配额一旦要 5（弱项 +2）或 8（攻坚）就断供。
            #    原来这里直接 raise，等于「配额敢要，出卷就崩」。
            #    退让代价 = 同型多一道，比整卷出不来轻得多。
            #    🔴 纯追加：cap=2 能成时行为与旧版逐字一致。
            placed = False
            for cap in (2, 3, 4, 6):
                for _try in range(300):
                    item = gens[(i + _try) % len(gens)](rng, lv)
                    sig = _skel(item['q'])
                    if item['q'] in seen or skel_n.get(sig, 0) >= cap:
                        continue
                    seen.add(item['q'])
                    skel_n[sig] = skel_n.get(sig, 0) + 1
                    item['anchor'] = kp
                    out.append(item)
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                raise RuntimeError('考点 %s 出题耗尽（题面/骨架撞尽——给该考点生成器加变体）' % kp)
    rng.shuffle(out)
    return out


MODI_QUOTA = {'sign': 3, 'abs': 3, 'pow': 3, 'dist': 3, 'fracdec': 3,
              'order': 2, 'paren': 3}               # 摸底卷：7 考点全覆盖 = 20 题


# ────────────────────────── verify：全量闸 ──────────────────────────

_TEX2SP = [(r'\left(', '('), (r'\right)', ')'), (r'\left[', '('), (r'\right]', ')'),
           (r'\left|', 'Abs('), (r'\right|', ')'), (r'\times', '*'), (r'\div', '/'),
           ('＝', ''), (r'\color{#c00}{', '('), ('}', ')'), ('{', '('), ('\\(', ''),
           ('\\)', ''), (r'\frac', 'FRAC'), ('^', '**')]


def _tex_val(tex):
    """LaTeX → sympy 精确值（独立第二条路，不走树）"""
    s = tex
    import re
    s = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'((\1)/(\2))', s)
    for a, b in _TEX2SP:
        if a == r'\frac':
            continue
        s = s.replace(a, b)
    s = re.sub(r'(\d)\s*\(', r'\1*(', s)             # 隐乘
    s = re.sub(r'\)\s*\(', r')*(', s)
    s = re.sub(r'\*\*\((\d+)\)', r'**\1', s)
    # rational=True：小数字面量按十进制精确转 Rational（浮点残差会把 6.8-11.8+12.2-7.2 算出 1e-27）
    return sp.nsimplify(sp.sympify(s, evaluate=True, rational=True))


def verify(items, label='卷'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    bad, stems = 0, set()
    for i, it in enumerate(items, 1):
        errs = []
        # ① 题面独立求值 = 声称答案（双路闸）
        try:
            got = _tex_val(it['q'])
            if sp.simplify(got - sp.Rational(it['ans'])) != 0:
                errs.append('题面算得 %s ≠ 声称 %s' % (got, it['ans']))
        except Exception as e:
            errs.append('题面解析失败: %s' % e)
        # ② 过程链逐行恒等（每行都等于答案——混合运算每行是全式化简）
        for j, st in enumerate(it['steps'], 1):
            try:
                sv = _tex_val(st)
                if sp.simplify(sv - sp.Rational(it['ans'])) != 0:
                    errs.append('第%d行 %s ≠ 答案' % (j, sv))
            except Exception as e:
                errs.append('第%d行解析失败: %s' % (j, e))
        # ③ 题面不撞
        if it['q'] in stems:
            errs.append('题面重复')
        stems.add(it['q'])
        # ④ 值域 + 步数
        if abs(it['ans']) > 200:
            errs.append('答案越界 %s' % it['ans'])
        if it['ans'].denominator > 36:
            errs.append('答案分母过大')
        if len(it['steps']) < 2:
            errs.append('过程行数 <2（太易）')
        if errs:
            bad += 1
            print('🔴 %s-%02d %s' % (label, i, it['q'][:60]))
            for e in errs:
                print('     ' + e)
    n = len(items)
    print('%s：%s %d 题，%d FAIL' % ('🟢 ALL PASS' if bad == 0 else '🔴', label, n, bad))
    return bad == 0


def kp_report(items):
    cnt = {k: 0 for k in KP}
    for it in items:
        for k in it['kp']:
            cnt[k] += 1
    return {KP_CN[k]: v for k, v in cnt.items()}


# ────────────────────────── 批处理打标规律（2026-08-19 下沉） ──────────────────────────
# 生成器 → 打标规律（批处理入库的唯一事实源；kp=KG 现行叶子 id，diff 按 lv 查表）
# 🔴 规律在 DSL 本体里，不在每册的手写脚本里——册脚本一散，同一个生成器就会被标成两种考点。
#    批处理入口 = 工具箱/dsl/dsl_batch.py（读本表打标，exam_model 从库里按 dsl_ref+gen 名解析）。
GEN_META = {
    'gen_addsub_chain':    {'kp': '100002002002'},
    'gen_frac_addsub':     {'kp': '100002002002'},
    'gen_abs_chain':       {'kp': '100001003003'},
    'gen_pow_mixed':       {'kp': '100002005001'},
    'gen_bare_pow_chain':  {'kp': '100002005001'},
    'gen_dist_forward':    {'kp': '100002003002'},
    'gen_dist_reverse':    {'kp': '100002003002'},
    'gen_div_by_unit_frac': {'kp': '100002003002'},
    'gen_dec_chain':       {'kp': '100002001002'},
    'gen_frac_div':        {'kp': '100002004002'},
    'gen_dec_frac_mix':    {'kp': '100002006001'},
    'gen_mixed_long':      {'kp': '100002006001'},
    'gen_nested_paren':    {'kp': '100002006001'},
}
DIFF_BY_LV = {1: '巩固', 2: '中档', 3: '压轴'}


if __name__ == '__main__':
    paper = build_paper(seed=20260805, quota=MODI_QUOTA, lv=1)
    ok = verify(paper, '摸底卷')
    print('考点覆盖:', kp_report(paper))
    sys.exit(0 if ok else 1)
