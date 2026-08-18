# -*- coding: utf-8 -*-
"""render_paper.py 自证：正例出件 + 反例全拒 + 适配规则单测。

    python 工具箱\\渲染\\render_paper_test.py

判绿口径（照 工具箱/库/gates_test.py）：**正例全过 + 反例全拒**，任一条不符退出码 1。
闸只有能拒错才算闸 —— 常绿闸=没闸。
🔴 本测试只写临时目录、只用 --no-log，不碰任何库、不写 产物/。
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_paper as RP                                      # noqa: E402

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / '_样例' / 'render-pack-最小样例.json'
PASS, FAIL = [], []


def ok(name, cond, why=''):
    (PASS if cond else FAIL).append(name)
    print('  %s %s%s' % ('🟢' if cond else '🔴', name, '' if cond else '  ← ' + why))


def rejects(name, pack, tmp, extra=()):
    """反例：写成临时 pack 跑一遍，必须非零退出。"""
    p = Path(tmp) / (name + '.json')
    p.write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
    rc = RP.main([str(p), '--out-dir', str(Path(tmp) / 'out'), '--no-log'] + list(extra))
    ok('拒渲：' + name, rc == 1, '退出码 %d（本该 1）' % rc)


# ══════════════ 一、适配规则单测（不出 PDF，秒级） ══════════════
def unit():
    print('\n── 适配规则单测 ──')
    ok('md→定界：$…$ 换 \\(…\\)',
       RP.md_to_delim('计算：$3+5$') == '计算：\\(3+5\\)')
    ok('md→定界：\\$ 转义不当定界', RP.md_to_delim('单价 \\$5') == '单价 $5')
    ok('公式段 < > 转 \\lt \\gt', RP.md_to_delim('$a<b$') == '\\(a\\lt b\\)')
    ok('文字段 HTML 转义', RP.md_to_delim('a<b') == 'a&lt;b')
    try:
        RP.md_to_delim('$3+5')
        ok('奇数 $ 拒渲', False, '没抛错')
    except RP.PackError:
        ok('奇数 $ 拒渲', True)
    try:
        RP.md_to_delim('$$x$$')
        ok('$$ 显示公式拒渲', False, '没抛错')
    except RP.PackError:
        ok('$$ 显示公式拒渲', True)

    ok('纯公式取裸串', RP.pure_formula('$\\frac{1}{2}$') == '\\frac{1}{2}')
    ok('混排不算纯公式', RP.pure_formula('计算：$3+5$') is None)
    ok('expr 纯公式 stem=裸 tex', RP.stem_tex('$3+5$') == '3+5')
    # 混排 stem：外层 M() 会再包一对定界 → 首尾"先关后开"，退化成两个空公式
    ok('expr 混排 stem 不嵌套定界',
       RP.stem_tex('计算：$3+5$') == '\\)计算：\\(3+5\\)\\(')

    B = lambda md: {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': md}]}]}   # noqa: E731
    lead, lines, src = RP.chain_lines(B('＝$5-(-5)$\n＝$10$'), B('$10$'))
    ok('＝链按序剥等号与定界', lines == ['5-(-5)', '10'] and src == '解析＝链')
    lead, lines, src = RP.chain_lines(B('$12-12\\times\\frac{1}{3}$\n＝$8$'), None)
    ok('非等号首行记作 lead（word 原式）', lead == '12-12\\times\\frac{1}{3}' and lines == ['8'])
    lead, lines, src = RP.chain_lines(None, B('$10$'))
    ok('解析缺失退到答案首式', lines == ['10'] and src.startswith('答案首式'))
    # 组卷侧实测写法：整条解析存成一个公式，等号在公式内部
    lead, lines, src = RP.chain_lines(B('$(-3)+(-5)-(-2)=-3-5+2=-6$'), B('$-6$'))
    ok('行内等号链按顶层 = 切开',
       lead == '(-3)+(-5)-(-2)' and lines == ['-3-5+2', '-6'] and src == '解析行内等号链')
    ok('花括号内的等号不切', RP.split_eq_chain('\\frac{a=b}{c}=d') == ['\\frac{a=b}{c}', 'd'])
    it3 = {'question': {'blocks': B('$(-3)+(-5)-(-2)$'),
                        'analysis_blocks': B('$(-3)+(-5)-(-2)=-3-5+2=-6$')}}
    ok('expr：lead 与题面同 → 不重复打头',
       RP.adapt_item(it3, 'expr', 'T')['lines'] == ['-3-5+2', '-6'])
    it4 = {'question': {'blocks': B('$36\\div 4+2$'),
                        'analysis_blocks': B('$9+2=11$')}}
    ok('expr：lead 与题面不同 → 补进链首不丢步',
       RP.adapt_item(it4, 'expr', 'T')['lines'] == ['9+2', '11'])
    try:
        RP.chain_lines(B('＝$4$元'), None)
        ok('＝行混中文拒渲', False, '没抛错')
    except RP.PackError:
        ok('＝行混中文拒渲', True)

    fig = {'v': 2, 'rows': [{'cells': [{'type': 'figure', 'asset': 'f01', 'width': '48%'}]}]}
    try:
        RP.md_lines(fig, '题面')
        ok('figure 块拒渲', False, '没抛错')
    except RP.PackError as e:
        ok('figure 块拒渲', '批次⑥' in str(e), str(e))
    try:
        RP.md_lines({'v': 1, 'rows': []}, '题面')
        ok('blocks 非 v2 拒渲', False, '没抛错')
    except RP.PackError:
        ok('blocks 非 v2 拒渲', True)

    it = {'question': {'blocks': B('括号里填几：$3+\\square=8$'),
                       'answer_blocks': B('$5$')}}
    d = RP.adapt_item(it, 'fill', 'T')
    ok('fill 槽位：题面转定界 + 答案着色',
       d['text'] == '括号里填几：\\(3+\\square=8\\)' and '\\color{' in d['ans'])
    it2 = {'question': {'blocks': B('$36\\div 4$'), 'answer_blocks': B('$9$')}}
    d2 = RP.adapt_item(it2, 'oral', 'T')
    ok('oral 槽位：stem + 末行答案', d2['stem'].h == '36\\div 4' and d2['lines'] == ['9'])
    try:
        RP.adapt_item(it2, 'equation', 'T')
        ok('未实装槽位拒渲', False, '没抛错')
    except RP.PackError:
        ok('未实装槽位拒渲', True)


# ══════════════ 二、正例出件 ══════════════
def positive(tmp):
    print('\n── 正例：样例 pack 出双 PDF ──')
    out = Path(tmp) / '全册'
    rc = RP.main([str(SAMPLE), '--out-dir', str(out), '--png', '--no-log'])
    ok('两卷全册出件成功', rc == 0, '退出码 %d' % rc)
    q = out / '有理数计算·两天打卡样例.pdf'
    a = out / '有理数计算·两天打卡样例（答案）.pdf'
    ok('题目卷落盘', q.exists() and q.stat().st_size > 10000)
    ok('答案卷落盘', a.exists() and a.stat().st_size > 10000)
    ok('题目卷 2 页（一天一页）', q.exists() and RP.core.page_count(str(q)) == 2)
    ok('目检 PNG 已出', len(list((out / '_源').glob('_chk_*.png'))) >= 2)

    print('\n── 正例：--sample-ord 只渲第 2 天 ──')
    out2 = Path(tmp) / '单天'
    rc = RP.main([str(SAMPLE), '--out-dir', str(out2), '--stem', 'D2样张', '--no-log',
                  '--sample-ord', '2'])
    ok('单卷样张出件成功', rc == 0, '退出码 %d' % rc)
    ok('单卷题目卷 1 页',
       (out2 / 'D2样张.pdf').exists() and RP.core.page_count(str(out2 / 'D2样张.pdf')) == 1)


# ══════════════ 三、反例：四条必拒 ══════════════
def negative(tmp):
    print('\n── 反例（四条必拒） ──')
    base = json.loads(SAMPLE.read_text(encoding='utf-8'))

    p = copy.deepcopy(base)
    p['contract'] = 'render-pack/v2'
    rejects('contract 版本不对', p, tmp)

    p = copy.deepcopy(base)
    p['papers'][0]['items'][0]['question']['blocks']['rows'][0]['cells'][0]['md'] = '$(-8)+13'
    rejects('奇数个 $', p, tmp)

    p = copy.deepcopy(base)
    p['papers'][0]['items'][0]['question']['blocks']['rows'].append(
        {'cells': [{'type': 'figure', 'asset': 'cceea0b6', 'width': '48%'}]})
    rejects('题面带 figure 块', p, tmp)

    p = copy.deepcopy(base)
    p['papers'][0]['items'][1]['section'] = '不存在的节'
    rejects('section 不在 layout.sections 里', p, tmp)


def main():
    if not SAMPLE.exists():
        sys.exit('🔴 样例不存在：%s' % SAMPLE)
    tmp = tempfile.mkdtemp(prefix='render_paper_test_')
    try:
        unit()
        negative(tmp)
        positive(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('\n═══ 结论：通过 %d 条，失败 %d 条 ═══' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  🔴 %s' % f)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
