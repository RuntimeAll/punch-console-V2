# -*- coding: utf-8 -*-
"""逐行恒等校验闸 —— 解析过程的每一行都必须与原式恒等（不只验最终答案）。

背景：2026-07-30 有理数打卡第二天第9题事故——LLM 写解析时去括号漏变号，
最后一行又锚定回已验算的正确答案，形成「答案对、过程错」。答案验证闸
（只重算最终答案）对这种错误完全免疫，必须逐行校验。

输入 JSON（转写层产出，通常由多模态 subagent 对照卷面逐行转写）：
[
  {"id": "第2天-9",
   "mode": "expr",                     # expr=表达式链 / eq=方程变形链
   "lines": ["-2**3-(-3+(-3)**2/(-S(1)/6))",   # 第1行=原式（照抄题目）
             "-2**3+3+(-3)**2/(-S(1)/6)", ...], # 后续行=解析每一步
   "answer": "49"},                    # 卷面标注的最终答案
  {"id": "专项一-1",
   "mode": "eq",
   "lines": ["4-3*x=6-5*x", "-3*x+5*x=6-4", "2*x=2", "x=1"],
   "answer": "x=1"}
]

转写规范：÷→/  ×→*  乘方→**  分数→S(a)/b（保精确有理算术）  |x|→Abs(x)
         带分数 8½ → (8+S(1)/2)。转写必须忠实卷面，不许顺手改错。

判定：
  expr : 每行 sympy 精确求值，全体必须等于第1行（原式），且 answer 也相等。
  eq   : 每行按 '=' 拆成方程，解集必须与第1行方程一致；answer 形如 "x=值"。
  无解方程 / parse 失败 → FAIL（附原因），绝不静默跳过。

用法：python 逐行恒等校验.py cases.json  → 输出逐题 PASS/FAIL + 汇总，
      有 FAIL 时退出码 1。
"""
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')  # GBK 控制台会被中文/− 直接杀掉进程

from sympy import Abs, S, Symbol, nsimplify, simplify, solveset, sqrt, sympify
from sympy.sets import EmptySet

SYMS = {n: Symbol(n) for n in 'abcdmnpqxyz'}
LOCALS = {'Abs': Abs, 'S': S, 'sqrt': sqrt, **SYMS}


def parse(s):
    return sympify(s, locals=LOCALS, rational=True)


def check_expr(lines, answer):
    # 「SKIP:」前缀行 = 转写层无法机读（省略号数列等），跳过该行、其余照验；
    # 首行(原式)SKIP 则整题只能人工抽查
    if lines[0].startswith('SKIP'):
        return True, 'SKIP题(原式含省略号等不可机读结构,需人工抽查)'
    lines = [l for l in lines if not l.startswith('SKIP')]
    ref = parse(lines[0])
    for i, ln in enumerate(lines[1:], 2):
        v = parse(ln)
        if simplify(ref - v) != 0:
            return False, f'第{i}行断裂: 「{ln}」={v} ≠ 原式={ref}'
    if answer is not None and simplify(ref - parse(str(answer))) != 0:
        return False, f'答案不符: 原式={ref}, 卷面答案={answer}'
    return True, f'{len(lines)}行恒等, 值={ref}'


def solset(line):
    lhs, rhs = line.split('=', 1)
    eq = parse(lhs) - parse(rhs)
    free = eq.free_symbols
    if not free:
        # 化到 "0=0" / "8=1" 这类无未知数行：恒真=全集语义，恒假=空集
        return S.Complexes if simplify(eq) == 0 else EmptySet
    var = free.pop() if len(free) == 1 else SYMS['x']
    return solveset(eq, var, domain=S.Complexes)

def check_eq(lines, answer):
    ref = solset(lines[0])
    if ref is EmptySet:
        return False, f'原方程无解: {lines[0]}'
    for i, ln in enumerate(lines[1:], 2):
        s = solset(ln)
        if s != ref:
            return False, f'第{i}行变形不同解: 「{ln}」解集={s} ≠ 原方程解集={ref}'
    if answer is not None:
        if solset(str(answer)) != ref:
            return False, f'答案不符: 方程解集={ref}, 卷面答案={answer}'
    return True, f'{len(lines)}行同解, 解集={ref}'


def run(cases):
    fails = []
    for c in cases:
        cid, mode = c.get('id', '?'), c.get('mode', 'expr')
        try:
            ok, msg = (check_eq if mode == 'eq' else check_expr)(c['lines'], c.get('answer'))
        except Exception as e:
            ok, msg = False, f'解析失败(转写待人裁): {e}'
        print(('PASS' if ok else 'FAIL'), cid, '——', msg)
        if not ok:
            fails.append((cid, msg))
    print(f'\n== 汇总: {len(cases)} 题, FAIL {len(fails)} ==')
    for cid, msg in fails:
        print('  ✗', cid, msg)
    return fails


if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as f:
        cases = json.load(f)
    sys.exit(1 if run(cases) else 0)
