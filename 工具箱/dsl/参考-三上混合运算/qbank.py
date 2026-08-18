# -*- coding: utf-8 -*-
"""三上混合运算特训 · 题库层（DSL 单一事实源，SOP v1）· 30 天全册

🔴🔴 v2 平移标注（2026-08-18）：本文件是**只读参考件**（结构型题表达式树 DSL 的样板——
    树状图/二合一综合算式怎么参数化）。其中「出题器 API」段（BASE=:9190 /teacher/oralcalc）
    调的是老区备课帮 dev 服务，**v2 禁用**（独立生态零交互）——要复用请把对应生成段
    改成纯本地生成，绝不接通老区端口。

每题一棵表达式树 tree = int | (op, left, right)，op ∈ '+-×÷'。
题面 HTML 与验算值同源自这棵树，杜绝双录漂移。
四个小节（每天 14 题）：
  s1 脱式·无括号 ×4（出题器 muladd 乘加乘减 ×2 + 本地 除加除减 ×2）
  s2 脱式·含括号 ×4（出题器 paren ×2 + 本地 乘括号 ×2）
  s3 二合一：两个算式合并成综合算式 ×4（本地）
  s4 树状图：先填空再列综合算式 ×2（本地）
出题器 = A 位 BE :9190 /teacher/oralcalc/generate（seed 复现；PRD-013 未上 prod 前走本地 dev）。
三上口径：表内乘除（因数 2-9）、加减 100 以内、除法必整除、中间量与结果非负。
"""
import json
import random
import urllib.request

BASE = 'http://localhost:9190'
CID = 'e5cd7e4891bf95d1d19206ce24a7b32e'
DAYS = 30

# ───────────────────────── 表达式树 ─────────────────────────

PREC = {'+': 1, '-': 1, '×': 2, '÷': 2}


def ev(t):
    if isinstance(t, int):
        return t
    op, l, r = t
    a, b = ev(l), ev(r)
    if op == '+':
        return a + b
    if op == '-':
        assert a >= b, f'负数越界: {a}-{b}'
        return a - b
    if op == '×':
        return a * b
    if op == '÷':
        assert b != 0 and a % b == 0, f'除不尽: {a}÷{b}'
        return a // b


def render(t, parent_op=None, side='l'):
    """树 → 题面文本（按优先级自动补必要括号；同级右侧遇 - ÷ 也补）"""
    if isinstance(t, int):
        return str(t)
    op, l, r = t
    s = f'{render(l, op, "l")}{op}{render(r, op, "r")}'
    if parent_op is None:
        return s
    need = PREC[op] < PREC[parent_op] or (
        PREC[op] == PREC[parent_op] and side == 'r' and parent_op in '-÷')
    return f'({s})' if need else s


def steps(t):
    """脱式步骤链：每次归约最深可算的一个子式 → ['81-45','36']"""
    out, cur = [], t
    while not isinstance(cur, int):
        cur = _reduce_once(cur)
        out.append(render(cur))
    return out


def leaves(t):
    return [t] if isinstance(t, int) else leaves(t[1]) + leaves(t[2])


def too_easy(t):
    """过易闸：三上特训不收「结果 <10」或「全是小数字」的口算级题
    （出题器 muladd 是二下类型，会产 3×2−5=1 这种，混进三上册里显敷衍）"""
    return ev(t) < 10 or max(leaves(t)) < 6


def _reduce_once(t):
    op, l, r = t
    if isinstance(l, tuple):
        return (op, _reduce_once(l), r)
    if isinstance(r, tuple):
        return (op, l, _reduce_once(r))
    return ev(t)


def tree_of_s4(spec):
    """s4 spec=(顶层树, 中层op, 另一操作数, 顶结果在中层的哪侧) → 完整树"""
    top, op, other, side = spec
    return (op, top, other) if side == 'l' else (op, other, top)


# ───────────────────────── 出题器对接 ─────────────────────────

def _post(path, body, token=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('clientid', CID)
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())


def fetch_engine(groups, seed):
    r = _post('/auth/login', {'clientId': CID, 'grantType': 'password',
                              'tenantId': '000000', 'username': 'admin', 'password': 'admin123'})
    assert r.get('code') == 200, f'登录失败: {r}'
    g = _post('/teacher/oralcalc/generate',
              {'groups': groups, 'seed': seed, 'fill_rows': False}, r['data']['access_token'])
    assert g.get('code') == 1, f'出题器失败: {g}'
    return g['response']['groups']


def parse_q(q):
    """出题器题面 '81－(24＋21)＝' → 表达式树（全角→半角，纳入本地闸重算）"""
    s = (q.replace('＋', '+').replace('－', '-').replace('＝', '')
          .replace('（', '(').replace('）', ')').strip())
    return _parse_expr(s)


def _parse_expr(s):
    depth, split_at = 0, None
    for lvl in (1, 2):                      # 先切低优先级；右往左保左结合
        for i in range(len(s) - 1, -1, -1):
            c = s[i]
            if c == ')':
                depth += 1
            elif c == '(':
                depth -= 1
            elif depth == 0 and c in PREC and PREC[c] == lvl and i > 0:
                split_at = (i, c)
                break
        if split_at:
            break
    if not split_at:
        s = s.strip()
        return _parse_expr(s[1:-1]) if s.startswith('(') else int(s)
    i, op = split_at
    return (op, _parse_expr(s[:i]), _parse_expr(s[i + 1:]))


# ───────────────────────── 本地题型生成器 ─────────────────────────

def _take(rng, seen, maker, day_chains=None, tries=400):
    """反复摇直到出一道合法、全册题面未出现、且当天脱式步骤链不重复的题。
    🔴 步骤链查重：(28-8)×4 与 (13+7)×4 题面不同但都归约成 20×4→80，
    等于同一道题换壳，同页出现是凑数不是训练。"""
    for _ in range(tries):
        t = maker(rng)
        if t is None:
            continue
        try:
            v = ev(t)
        except AssertionError:
            continue
        if not (0 <= v <= 200) or too_easy(t):
            continue
        key = render(t)
        if key in seen:
            continue
        chain = '|'.join(steps(t))
        if day_chains is not None and chain in day_chains:
            continue
        seen.add(key)
        if day_chains is not None:
            day_chains.add(chain)
        return t
    raise SystemExit(f'生成器摇不出新题（{tries} 次）——放宽参数域')


def _mk_s1_local(rng):
    """除加除减：a÷b+c / c+a÷b / c-a÷b（除法整除，表内除法）"""
    b, q = rng.randint(2, 9), rng.randint(2, 9)
    a, c = b * q, rng.randint(11, 89)
    form = rng.choice(['add_l', 'add_r', 'sub_r'])
    if form == 'add_l':
        return ('+', ('÷', a, b), c)
    if form == 'add_r':
        return ('+', c, ('÷', a, b))
    return ('-', c, ('÷', a, b)) if c > q else None


def _mk_s2_local(rng):
    """乘括号：k×(a+b) / (a-b)×k / k×(a-b) / (a+b)×k（积 ≤ 200）"""
    k = rng.randint(2, 9)
    form = rng.choice(['mul_add', 'sub_mul', 'mul_sub', 'add_mul'])
    if form in ('mul_add', 'add_mul'):
        a, b = rng.randint(2, 15), rng.randint(2, 15)
        if (a + b) * k > 200:
            return None
        inner = ('+', a, b)
    else:
        a, b = rng.randint(12, 60), rng.randint(3, 11)
        if a <= b or (a - b) * k > 200:
            return None
        inner = ('-', a, b)
    return ('×', k, inner) if form.startswith('mul') else ('×', inner, k)


S3_FORMS = ('sub_div', 'mul_add', 'div_mul', 'sub_mul', 'add_div', 'mul_sub', 'sub_mul_r')


def _mk_s3(rng, form):
    """二合一：返回 (式1树, 式2树, 综合树)；式1 的结果必被式2 引用"""
    if form == 'sub_div':                          # (a-b)÷c
        c, q = rng.randint(2, 9), rng.randint(2, 9)
        v1 = c * q
        b = rng.randint(11, 60)
        a = v1 + b
        if a > 99:
            return None
        t1 = ('-', a, b)
        return t1, ('÷', v1, c), ('÷', t1, c)
    if form == 'mul_add':                          # a×b+c
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        v1, c = a * b, rng.randint(11, 89)
        if c == v1:                                # 🔴 另一操作数=式1结果 → 学生分不清哪个是代入值
            return None
        t1 = ('×', a, b)
        return t1, ('+', v1, c), ('+', t1, c)
    if form == 'div_mul':                          # a÷b×c
        b, q, c = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 9)
        a, v1 = b * q, q
        if v1 * c > 200 or c == v1:
            return None
        t1 = ('÷', a, b)
        return t1, ('×', v1, c), ('×', t1, c)
    if form == 'sub_mul':                          # c-a×b
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        v1 = a * b
        c = rng.randint(v1 + 1, 99)
        t1 = ('×', a, b)
        return t1, ('-', c, v1), ('-', c, t1)
    if form == 'add_div':                          # (a+b)÷c
        c, q = rng.randint(2, 9), rng.randint(2, 9)
        v1 = c * q
        a = rng.randint(2, v1 - 2) if v1 > 3 else None
        if a is None:
            return None
        t1 = ('+', a, v1 - a)
        return t1, ('÷', v1, c), ('÷', t1, c)
    if form == 'mul_sub':                          # a×b-c
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        v1 = a * b
        c = rng.randint(2, v1 - 1) if v1 > 2 else None
        if c is None:
            return None
        t1 = ('×', a, b)
        return t1, ('-', v1, c), ('-', t1, c)
    # sub_mul_r：(a-b)×c
    c, a = rng.randint(2, 9), rng.randint(20, 90)
    b = rng.randint(11, a - 2)
    v1 = a - b
    if v1 * c > 200 or c == v1:
        return None
    t1 = ('-', a, b)
    return t1, ('×', v1, c), ('×', t1, c)


S4_FORMS = ('div_add', 'sub_div', 'mul_sub', 'add_div', 'div_sub', 'mul_add')


def _mk_s4(rng, form):
    """树状图 spec=(顶层树, 中层op, 另一操作数, 顶结果在中层哪侧)"""
    if form == 'div_add':                          # a÷b=v → v+c
        b, q = rng.randint(2, 9), rng.randint(2, 9)
        return (('÷', b * q, b), '+', rng.randint(21, 89), 'l')
    if form == 'sub_div':                          # a-b=v → c÷v
        v, q = rng.randint(2, 9), rng.randint(2, 9)
        b = rng.randint(11, 60)
        a = v + b
        return (('-', a, b), '÷', v * q, 'r') if a <= 99 else None
    if form == 'mul_sub':                          # a×b=v → c-v
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        v = a * b
        return (('×', a, b), '-', rng.randint(v + 1, 99), 'r')
    if form == 'add_div':                          # a+b=v → v÷c
        c, q = rng.randint(2, 9), rng.randint(2, 9)
        v = c * q
        if v <= 3:
            return None
        a = rng.randint(2, v - 2)
        return (('+', a, v - a), '÷', c, 'l')
    if form == 'div_sub':                          # a÷b=v → c-v
        b, q = rng.randint(2, 9), rng.randint(2, 9)
        return (('÷', b * q, b), '-', rng.randint(q + 1, 99), 'r')
    # mul_add：a×b=v → v+c
    a, b = rng.randint(2, 9), rng.randint(2, 9)
    if a * b > 81:
        return None
    return (('×', a, b), '+', rng.randint(11, 89), 'l')


# ───────────────────────── 组册 ─────────────────────────

def build_all(days=DAYS):
    """产 30 天题库；出题器一次取够再按天分发，本地题全册跨天查重。"""
    # 🔴 多取 2.5 倍：过易闸会筛掉一批（muladd 是二下类型，口算级题不进三上册）
    # 🔴 出题器单卷总题数上限 200（两组合计）；过易闸筛掉一批（paren 通过率仅 ~50%），
    # 故分批次换 seed 累积取，边取边按题面去重，直到两池都够 days*2。
    need = days * 2
    pool_s1, pool_s2, got = [], [], set()
    for rd in range(1, 7):
        eng = fetch_engine([{'type': 'muladd', 'count': 95, 'label': 's1'},
                            {'type': 'paren', 'count': 95, 'label': 's2'}],
                           f'sanshang-tx-30d-r{rd}')
        for grp, pool in ((eng[0], pool_s1), (eng[1], pool_s2)):
            for it in grp['items']:
                t = parse_q(it['q'])
                k = render(t)
                if k in got or too_easy(t):
                    continue
                got.add(k)
                pool.append(t)
        print(f'  第{rd}批后：muladd 池 {len(pool_s1)} / paren 池 {len(pool_s2)}（需 {need}）')
        if len(pool_s1) >= need and len(pool_s2) >= need:
            break
    assert len(pool_s1) >= need and len(pool_s2) >= need, \
        f'过易闸后供题仍不足（muladd {len(pool_s1)} / paren {len(pool_s2)}，需 {need}）'

    seen = set(got)                                # 全册跨天查重（题面串）

    book = []
    for n in range(1, days + 1):
        rng = random.Random(f'sanshang-day-{n}')   # 按天定种，可复现
        s3_forms = rng.sample(S3_FORMS, 4)
        s4_forms = rng.sample(S4_FORMS, 2)
        e1 = pool_s1[(n - 1) * 2:(n - 1) * 2 + 2]
        e2 = pool_s2[(n - 1) * 2:(n - 1) * 2 + 2]
        chains = {'|'.join(steps(t)) for t in e1 + e2}   # 出题器题的链先入册
        d = {
            's1': e1 + [_take(rng, seen, _mk_s1_local, chains) for _ in range(2)],
            's2': e2 + [_take(rng, seen, _mk_s2_local, chains) for _ in range(2)],
            's3': [], 's4': [],
        }
        for f in s3_forms:
            for _ in range(400):
                r = _mk_s3(rng, f)
                if not r:
                    continue
                t1, t2, tc = r
                try:
                    ev(tc)
                except AssertionError:
                    continue
                key = render(tc)
                if key in seen or not (0 <= ev(tc) <= 200):
                    continue
                seen.add(key)
                d['s3'].append(r)
                break
            else:
                raise SystemExit(f'day{n} s3 {f} 摇不出新题')
        for f in s4_forms:
            for _ in range(400):
                spec = _mk_s4(rng, f)
                if not spec:
                    continue
                try:
                    v = ev(tree_of_s4(spec))
                except AssertionError:
                    continue
                key = render(tree_of_s4(spec))
                if key in seen or not (0 <= v <= 200):
                    continue
                seen.add(key)
                d['s4'].append(spec)
                break
            else:
                raise SystemExit(f'day{n} s4 {f} 摇不出新题')
        book.append(d)
    return book


# ───────────────────────── 验算闸 ─────────────────────────

def verify(book, label='全册'):
    fails, seen = [], {}

    def chk(tag, cond, msg=''):
        if not cond:
            fails.append(f'{tag} {msg}')

    total = 0
    for n, d in enumerate(book, 1):
        chk(f'day{n}', len(d['s1']) == 4 and len(d['s2']) == 4
            and len(d['s3']) == 4 and len(d['s4']) == 2, '题量配比不对')
        day_keys, day_chains = set(), set()
        for key, items in (('s1', d['s1']), ('s2', d['s2'])):
            for i, t in enumerate(items, 1):
                total += 1
                tag = f'day{n}-{key}-{i}'
                try:
                    v = ev(t)                                  # 整除/非负由 ev 断言
                except AssertionError as e:
                    fails.append(f'{tag} {e}')
                    continue
                chk(tag, 0 <= v <= 200, f'结果越界 {v}')
                chk(tag, len(steps(t)) >= 2, '非两步式')
                chk(tag, not too_easy(t), f'过易（口算级）: {render(t)}={v}')
                k = render(t)
                chk(tag, k not in day_keys, '同页撞题')
                chk(tag, k not in seen, f'跨天撞 day{seen.get(k)}')
                ch = '|'.join(steps(t))
                chk(tag, ch not in day_chains, f'同页脱式链重复（换壳同题）: {ch}')
                day_chains.add(ch)
                day_keys.add(k)
                seen[k] = n
        for i, (t1, t2, tc) in enumerate(d['s3'], 1):
            total += 1
            tag = f'day{n}-s3-{i}'
            v1 = ev(t1)
            chk(tag, v1 in (t2[1], t2[2]), f'式1结果 {v1} 未被式2引用')
            chk(tag, not (t2[1] == v1 and t2[2] == v1),
                f'式2两个操作数都等于式1结果 {v1}（代入位歧义）')
            chk(tag, ev(tc) == ev(t2), '综合算式结果≠式2结果')
            sub = ((t2[0], t1, t2[2]) if t2[1] == v1      # 只替换一处（左优先）
                   else (t2[0], t2[1], t1))
            chk(tag, render(sub) == render(tc), f'综合树不同构 {render(sub)} vs {render(tc)}')
            k = render(tc)
            chk(tag, k not in day_keys, '同页撞题')
            chk(tag, k not in seen, f'跨天撞 day{seen.get(k)}')
            day_keys.add(k)
            seen[k] = n
        for i, spec in enumerate(d['s4'], 1):
            total += 1
            tag = f'day{n}-s4-{i}'
            t = tree_of_s4(spec)
            try:
                v = ev(t)
            except AssertionError as e:
                fails.append(f'{tag} {e}')
                continue
            chk(tag, 0 <= v <= 200, f'结果越界 {v}')
            chk(tag, isinstance(spec[0], tuple), '顶层非算式')
            k = render(t)
            chk(tag, k not in day_keys, '同页撞题')
            chk(tag, k not in seen, f'跨天撞 day{seen.get(k)}')
            day_keys.add(k)
            seen[k] = n
    if fails:
        raise SystemExit(f'[{label}] verify FAIL {len(fails)} 条:\n  ' + '\n  '.join(fails[:40]))
    print(f'[{label}] verify 全绿：{len(book)} 天 × 14 题 = {total} 题，'
          f'全册题面互异 {len(seen)} 条')


if __name__ == '__main__':
    book = build_all()
    verify(book)
    d = book[0]
    print('\n--- 第1天抽样 ---')
    for k in ('s1', 's2'):
        for t in d[k]:
            print(f'  {k} {render(t)} = {ev(t)}  脱式: ' + ' → '.join(steps(t)))
    for t1, t2, tc in d['s3']:
        print(f'  s3 {render(t1)}={ev(t1)} ; {render(t2)}={ev(t2)} → {render(tc)}')
    for spec in d['s4']:
        print(f'  s4 {render(spec[0])}={ev(spec[0])} → {render(tree_of_s4(spec))}={ev(tree_of_s4(spec))}')
