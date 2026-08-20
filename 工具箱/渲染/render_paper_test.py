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
import sqlite3
import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import render_paper as RP                                      # noqa: E402

HERE = Path(__file__).resolve().parent
SAMPLE = HERE / '_样例' / 'render-pack-最小样例.json'
PASS, FAIL = [], []

# ── 沙盘常量：图实体与库副本全落临时目录，🔴 一个字节都不写 知识库/ ──
FIG_HASH = 'a1b2c3d4e5f6a1b2'
FIG_REL = '知识库/资产/a1/a1b2c3d4e5f6a1b2.png'
GONE_HASH = 'deadbeefdeadbeef'        # 库里有行、盘上没文件
ABS_HASH = 'abs0abs0abs0abs0'         # rel_path 是绝对路径（老货架血案）
SB = {}                               # {'root':…, 'db':…}，make_sandbox 填


def ok(name, cond, why=''):
    (PASS if cond else FAIL).append(name)
    print('  %s %s%s' % ('🟢' if cond else '🔴', name, '' if cond else '  ← ' + why))


def raises(name, fn, kw=None):
    """反例（函数级）：必须抛 PackError，且报错里带 kw 关键词（拒得对不对，不只是拒了）。"""
    try:
        fn()
        ok('拒渲：' + name, False, '没抛错')
    except RP.PackError as e:
        ok('拒渲：' + name, (kw in str(e)) if kw else True, str(e)[:110])


def sb_args():
    """所有跑 RP.main 的用例都显式指到沙盘库/沙盘资产根 —— 绝不碰主位 知识库/。"""
    return ['--db', str(SB['db']), '--asset-root', str(SB['root'])]


def rejects(name, pack, tmp, extra=()):
    """反例：写成临时 pack 跑一遍，必须非零退出。"""
    p = Path(tmp) / (name + '.json')
    p.write_text(json.dumps(pack, ensure_ascii=False), encoding='utf-8')
    rc = RP.main([str(p), '--out-dir', str(Path(tmp) / 'out'), '--no-log']
                 + sb_args() + list(extra))
    ok('拒渲：' + name, rc == 1, '退出码 %d（本该 1）' % rc)


# ══════════════ 沙盘：1×1 PNG + asset 副本库 ══════════════
def png_1px():
    """最小合法 PNG（1×1 白点）—— 现造，不往仓里塞二进制。"""
    def chunk(tag, data):
        c = tag + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)        # 1×1 truecolor 8bit
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
            + chunk(b'IEND', b''))


def make_sandbox(tmp):
    root = Path(tmp) / 'render沙盘根'
    img = root / FIG_REL
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(png_1px())
    db = root / 'kb沙盘.db'
    conn = sqlite3.connect(str(db))
    conn.execute('CREATE TABLE asset (hash TEXT PRIMARY KEY, kind TEXT NOT NULL, '
                 'rel_path TEXT NOT NULL, meta_json TEXT, created_at TEXT)')
    conn.executemany('INSERT INTO asset(hash,kind,rel_path,created_at) VALUES (?,?,?,?)', [
        (FIG_HASH, 'figure', FIG_REL, '2026-08-20'),
        (GONE_HASH, 'figure', '知识库/资产/de/deadbeefdeadbeef.png', '2026-08-20'),
        (ABS_HASH, 'figure', 'D:/workplace/somewhere/x.png', '2026-08-20'),
    ])
    conn.commit()
    conn.close()
    SB['root'], SB['db'] = root, db
    return root, db


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
    raises('figure 块无 asset 解析器', lambda: RP.md_lines(fig, '题面'), '解析器')
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
    # ── 2026-08-20 答案卷三缺口回归 ──
    it_noans = {'question': {'blocks': B('$1-2=$（　）'), 'answer_blocks': None}}
    dn = RP.adapt_item(it_noans, 'fill', 'T')
    ok('🔴 fill 无答案态如实印「（待补答案）」不静默',
       dn['ans'] == '（待补答案）' and dn['_src'] == '无答案态', repr(dn))
    multi = {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': '答案', 'md': '$-3$'}]},
                              {'cells': [{'type': 'text', 'role': '答案', 'md': '$5$'}]}]}
    dm2 = RP.adapt_item({'question': {'blocks': B('两空：①（　）②（　）'),
                                      'answer_blocks': multi}}, 'fill', 'T')
    ok('🔴 fill 多行答案全印（此前静默丢第二行起）',
       dm2['ans'].count('\\color{') == 2 and '<br>' in dm2['ans']
       and dm2['_src'] == '答案2行', repr(dm2['ans']))
    it2 = {'question': {'blocks': B('$36\\div 4$'), 'answer_blocks': B('$9$')}}
    d2 = RP.adapt_item(it2, 'oral', 'T')
    ok('oral 槽位：stem + 末行答案', d2['stem'].h == '36\\div 4' and d2['lines'] == ['9'])
    # 🔴 槽位全集已补齐（equation/word_multi 2026-08-20 实装），这里拿一个**真不存在**的
    #    槽名钉「未实装必拒」，别再拿已实装的槽当反例（会拒得对、理由却是错的）。
    raises('未实装槽位（judge）', lambda: RP.adapt_item(it2, 'judge', 'T'), '本版未实装')


# ══════════════ 二、正例出件 ══════════════
def unit_choice():
    """option 块与 choice 槽（2026-08-20 补实装的「出」通路）——摘掉实装必红。"""
    print('\n── option/choice 单测 ──')
    opt = lambda lb, md: {'type': 'option', 'label': lb,
                          'blocks': [{'type': 'text', 'role': '题面', 'md': md}]}
    blocks = {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'role': '题面', 'md': '下列各数为负数的是（　）'}]},
        {'cells': [opt('A', '$-2$'), opt('B', '$0$'), opt('C', '$3$'), opt('D', '$5$')]}]}
    lines = RP.md_lines(blocks, 'T')
    ok('option 行拼成卷面样式一行', len(lines) == 2 and lines[1].startswith('A．')
       and 'D．' in lines[1], repr(lines))
    long_blocks = {'v': 2, 'rows': [{'cells': [
        opt('A', '零上' * 12), opt('B', '零下' * 12), opt('C', 'x' * 24), opt('D', 'y' * 24)]}]}
    ok('超长选项自动折行（两选项一行）', len(RP.md_lines(long_blocks, 'T')) == 2)
    mixed = RP.md_lines({'v': 2, 'rows': [{'cells': [
        {'type': 'text', 'role': '题面', 'md': '题干（　）'}, opt('A', 'x'), opt('B', 'y')]}]}, 'T')
    ok('题干与选项同 row 合法（text 归题干）', mixed[0] == '题干（　）' and mixed[1].startswith('A．'), repr(mixed))
    try:
        RP.md_lines({'v': 2, 'rows': [{'cells': [
            opt('A', 'x'), {'type': 'table', 'md': ''}]}]}, 'T')
        ok('option 行混入 table 拒渲', False, '没抛错')
    except RP.PackError:
        ok('option 行混入 table 拒渲', True)
    try:
        RP.md_lines({'v': 2, 'rows': [{'cells': [{'type': 'option', 'label': 'A',
            'blocks': [{'type': 'figure', 'ref': 'x'}]}]}]}, 'T')
        ok('option 内嵌坏 figure（缺 asset）拒渲', False, '没抛错')
    except RP.PackError:
        ok('option 内嵌坏 figure（缺 asset）拒渲', True)
    try:
        RP.md_lines({'v': 2, 'rows': [{'cells': [{'type': 'option', 'label': 'A',
            'blocks': [{'type': 'table', 'md': '|a|\n|-|\n|1|'}]}]}]}, 'T')
        ok('option 内嵌 table 拒渲', False, '没抛错')
    except RP.PackError:
        ok('option 内嵌 table 拒渲', True)
    it = {'question': {'blocks': blocks, 'answer_blocks': None, 'analysis_blocks': None}}
    d = RP.adapt_item(it, 'choice', 'T')
    ok('choice 槽·选项独立占位不进题干', d['ans'] == '' and d['_src'] == '无答案态'
       and 'A．' not in d['text'] and len(d['options']) == 4
       and d['options'][0]['label'] == 'A', repr(d))
    ok('choice 槽·短选项 4 列', d['opt_cols'] == 4, repr(d.get('opt_cols')))
    mid = {'v': 2, 'rows': [{'cells': [opt(l, '零上 $%d^\\circ C$ 左右幅度' % n)
                                       for l, n in (('A', 3), ('B', 5), ('C', 7), ('D', 9))]}]}
    dm = RP.adapt_item({'question': {'blocks': mid, 'answer_blocks': None,
                                     'analysis_blocks': None}}, 'choice', 'T')
    ok('choice 槽·中长选项 2 列', dm['opt_cols'] == 2, repr(dm.get('opt_cols')))
    lng = {'v': 2, 'rows': [{'cells': [opt(l, '这是一个非常长的文字选项内容用于测试单列排布行为' )
                                       for l in 'ABCD']}]}
    dl = RP.adapt_item({'question': {'blocks': lng, 'answer_blocks': None,
                                     'analysis_blocks': None}}, 'choice', 'T')
    ok('choice 槽·长选项 1 列', dl['opt_cols'] == 1, repr(dl.get('opt_cols')))
    it2 = {'question': {'blocks': blocks, 'analysis_blocks': None,
                        'answer_blocks': {'v': 2, 'rows': [{'cells': [
                            {'type': 'text', 'role': '答案', 'md': 'A'}]}]}}}
    d2 = RP.adapt_item(it2, 'choice', 'T')
    ok('choice 槽·有答案带答案', d2['ans'] == 'A' and d2['_src'] == '答案')


# ══════════════ 一·五、equation / word_multi 两槽（2026-08-20 补齐最后两个） ══════════════
# 🔴 库口径取样（试验场/2026-08-20-收尾战役/kb-快照.db 只读副本，一个字节没写主位）：
#    · qtype 域九档 q1..q9；实存 q7 计算 384 / q1 选择 270 / q5 解答 173 /
#      q4 填空 162 / q3 应用 56 / q6 作图 2；
#    · 解方程类题面 = **一条纯方程**（`$\frac{x-m}{2} = \frac{x-n}{3}$`），
#      解析是**逐条方程**（`3(x+1)=2(x+2)` → `3x+3=2x+4` → `x=1`）—— 一个等号都不能切；
#    · q3/q5 多小问题解析 = **逐行步骤**（一 cell 一行），答案是一整行「(1)…；(2)…；(3)…」。
def unit_equation_wordmulti(root, db):
    print('\n── equation / word_multi 两槽单测（形状取自 kb 快照） ──')
    A = RP.AssetResolver(db=db, root=root)
    M = RP.renderers.get('math')
    B = lambda md: {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': md}]}]}       # noqa: E731
    ROWS = lambda *ms: {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': m}]}      # noqa: E731
                                         for m in ms]}

    # ── equation 正例 ──
    it = {'question': {'blocks': B('$2x+1=5$'),
                       'analysis_blocks': ROWS('$2x=5-1$', '$2x=4$', '$x=2$'),
                       'answer_blocks': B('$x=2$')}}
    d = RP.adapt_item(it, 'equation', 'T')
    ok('equation 正例：题面按顶层「=」劈成左右两边',
       d['lhs'].h == '2x+1' and d['rhs'].h == '5', repr(d)[:120])
    ok('🔴 equation 正例：解题步骤整行取，等号一个不切',
       d['lines'] == ['2x=5-1', '2x=4', 'x=2'] and d['_src'].startswith('解析逐步行'),
       repr(d['lines']))
    ok('对照：同一步进 ＝链会被切成两段（所以解方程必须另走 solve_lines）',
       RP.split_eq_chain('2x=4') == ['2x', '4'])
    df = RP.adapt_item({'question': {'blocks': B('$x^{2}=9$'),
                                     'analysis_blocks': ROWS('由平方根定义得 $x=\\pm 3$'),
                                     'answer_blocks': B('$x_{1}=3$')}}, 'equation', 'T')
    ok('equation：解析全是混排说明行 → 退到答案首式（答案卷不会空）',
       df['lines'] == ['x_{1}=3'] and df['_src'].startswith('答案首式'), repr(df))
    d2 = RP.adapt_item({'question': {'blocks': B('$\\frac{x-1}{2}=\\frac{x+2}{3}$'),
                                     'analysis_blocks': ROWS('＝$3(x-1)=2(x+2)$', '$x=7$')},
                        }, 'equation', 'T')
    ok('equation：行首写「＝」的解析行剥掉行首等号后整行取',
       d2['lines'] == ['3(x-1)=2(x+2)', 'x=7'], repr(d2['lines']))

    # ── equation 反例 ──
    raises('equation 题面带指令词不是纯方程',
           lambda: RP.adapt_item({'question': {'blocks': B('解方程：$2x+1=5$'),
                                               'answer_blocks': B('$x=2$')}}, 'equation', 'T'),
           '纯方程')
    raises('equation 题面顶层「=」段数不是 2（多段链）',
           lambda: RP.adapt_item({'question': {'blocks': B('$2x+1=5=6$'),
                                               'answer_blocks': B('$x=2$')}}, 'equation', 'T'),
           '正好 2')
    raises('equation 题面根本没有等号',
           lambda: RP.adapt_item({'question': {'blocks': B('$36\\div 4$'),
                                               'answer_blocks': B('$9$')}}, 'equation', 'T'),
           '正好 2')
    raises('equation 题面里有图（该槽只渲一条方程）',
           lambda: RP.adapt_item({'question': {'blocks': {'v': 2, 'rows': [
               {'cells': [{'type': 'text', 'md': '$2x+1=5$'}]},
               {'cells': [{'type': 'figure', 'asset': FIG_HASH, 'width': '40%'}]}]},
               'answer_blocks': B('$x=2$')}}, 'equation', 'T', A), 'word_multi')
    raises('equation 既无解析算式行也无答案公式',
           lambda: RP.adapt_item({'question': {'blocks': B('$2x+1=5$'),
                                               'analysis_blocks': ROWS('先移项再合并')}},
                                 'equation', 'T'), '没有答案')

    # ── equation 接得上渲染器 ──
    ha = M.equation(d, 0, True, None)
    ok('equation 接得上渲染器：答案卷首行「解：」+ 逐步 + 末步着色',
       'class="ln ind">解：' in ha and ha.count('class="ln ind"') == 3
       and '\\color{' in ha, ha[:120])
    hq = M.equation(d, 0, False, None)
    ok('equation 题目卷只印方程一行，零答案容器类零着色',
       '\\(2x+1=5\\)' in hq and not RP.core.answer_class_hits(hq)
       and '\\color{' not in hq and '解：' not in hq, hq[:120])

    # ── word_multi 正例 ──
    itw = {'question': {
        'blocks': ROWS('王先生乘电梯，上下楼层依次记作 $+6$，$-3$，$+10$．',
                       '（1）最后是否回到出发点？\n（2）电梯共运行多少层？'),
        'analysis_blocks': ROWS('（1）$(+6)+(-3)+(+10)=13$，净上升 $13$ 层，没回到出发点',
                                '（2）取各记录绝对值之和 $6+3+10=19$（层）',
                                '核验：净位移 $13$ 与总层数 $19$ 不同，符合往返'),
        'answer_blocks': B('（1）没有回到出发点；（2）$19$ 层')}}
    dw = RP.adapt_item(itw, 'word_multi', 'T')
    ok('word_multi 正例：解析逐行各自成行（不压成一条＝链）',
       len(dw['lines']) == 3 and dw['_src'] == '解析3行', repr(dw['lines'])[:160])
    ok('🔴 word_multi 正例：首行挂「解：」+ 全行已渲成定界串（渲染器不再解析一遍）',
       dw['lines'][0].startswith('解：') and '\\(' in dw['lines'][0]
       and '$' not in ''.join(dw['lines']), repr(dw['lines'][0])[:120])
    ok('word_multi 正例：答语行取答案块', '19' in dw['ansline'] and '\\(' in dw['ansline'])
    dw2 = RP.adapt_item({'question': {'blocks': B('求 $x$．'),
                                      'analysis_blocks': ROWS('解：设 $x$ 为所求', '$x=3$'),
                                      'answer_blocks': B('$x=3$')}}, 'word_multi', 'T')
    ok('word_multi：库里自带「解：」不重复挂（存取同构）',
       dw2['lines'][0].startswith('解：设') and '解：解：' not in dw2['lines'][0],
       repr(dw2['lines'][0]))
    ok('word_multi：末行是纯公式 → 着色（与 expr/word 同口径）',
       dw2['lines'][-1] == '\\(\\color{%s}{x=3}\\)' % M.ANSWER_COLOR, repr(dw2['lines'][-1]))
    ok('🔴 word_multi：末行是中文混排句 → 不着色（整句染红不是卷面惯例）',
       '\\color{' not in ''.join(dw['lines']), repr(dw['lines'][-1])[:80])
    ok('word_multi：末行着色不盖掉「解：」前缀（单行解答的边界）',
       RP.adapt_item({'question': {'blocks': B('求 $x$．'),
                                   'analysis_blocks': B('$x=3$')}},
                     'word_multi', 'T')['lines'][0]
       == '解：\\(\\color{%s}{x=3}\\)' % M.ANSWER_COLOR)
    dw3 = RP.adapt_item({'question': {'blocks': B('求 $7$ 名学生的平均体重．'),
                                      'analysis_blocks': None,
                                      'answer_blocks': ROWS('（1）学生 $4$', '（2）$11$ 千克')}},
                        'word_multi', 'T')
    ok('🔴 word_multi 无解析态：答案行当解答过程，答语行留空不把同段再印一遍',
       len(dw3['lines']) == 2 and dw3['lines'][0].startswith('解：')
       and dw3['ansline'] == '' and dw3['_src'] == '答案2行（解析缺失）', repr(dw3))
    gfm = {'type': 'table', 'md': '| 学生 | 差 |\n| --- | --- |\n| $1$ | $-5$ |'}
    dwt = RP.adapt_item({'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '看表求平均体重：'}]}, {'cells': [gfm]}]},
        'analysis_blocks': ROWS('平均差 $=-5$，平均体重 $=45-5=40$'),
        'answer_blocks': B('$40$ 千克')}}, 'word_multi', 'T', A)
    ok('word_multi：题面带表照收（该槽答案卷本就不重印题面，不触省纸口径）',
       '<table class="tbl">' in dwt['text'] and len(dwt['lines']) == 1)
    dwf = RP.adapt_item({'question': {'blocks': B('在数轴上表示 $A$、$B$．'),
        'analysis_blocks': {'v': 2, 'rows': [
            {'cells': [{'type': 'text', 'md': '如图所示：'}]},
            {'cells': [{'type': 'figure', 'asset': FIG_HASH, 'width': '40%'}]}]},
        'answer_blocks': B('见图')}}, 'word_multi', 'T', A)
    ok('word_multi：解析里的图原样进解答行（＝链会把它整块丢掉）',
       any('<img class="fig"' in x for x in dwf['lines']), repr(dwf['lines'])[:140])
    raises('word_multi 既无解析行也无答案行',
           lambda: RP.adapt_item({'question': {'blocks': B('求 $x$．')}}, 'word_multi', 'T'),
           '整题空白')

    # ── word_multi 接得上渲染器 ──
    hwa = M.word_multi(dw, 0, True, None)
    ok('word_multi 接得上渲染器：首行 .ln + 其余逐行 .ln ind + 答语行',
       hwa.count('class="ln ind"') == 3 and 'class="ln"' in hwa and '解：' in hwa, hwa[:0])
    hwq = M.word_multi(dw, 0, False, None)
    ok('word_multi 题目卷=题面段落，零答案容器类且不泄解答',
       'class="app"' in hwq and not RP.core.answer_class_hits(hwq)
       and '解：' not in hwq and '\\color{' not in hwq, hwq[:0])


# ══════════════ 一·六、泄答案闸白名单口径（PRD-008 §一②-3 第一件） ══════════════
# 🔴 新口径 = **只拦渲染器注入的答案元素**（着色/加粗宏 + 答案容器类），
#    **不拦题面 md 原文里固有的「解：」「答：」**。
# 正例素材 = 2026-08-20 窗G 实拦的那两道讲义阅读理解题（原文节选自 kb 快照）：
#    · U1·2 型（q20260820419dcf11）：「…他采用了如下的"整体代换"的方法：\n解：根据题意…」
#    · MIX·3 型（q20260820a438cb8a）：「…这种做法正确吗？答：______．」
STEM_JIE = ('小明在做作业时遇到这样一道题：若 $x^{2}-x-4=5$，求 $2x^{2}-2x+3$ 的值，'
            '他采用了如下的“整体代换”的方法：\n'
            '解：根据题意，得 $x^{2}-x-4=5$，则有 $x^{2}-x=9$．\n'
            '则 $2x^{2}-2x+3=2(x^{2}-x)+3=21$．')
STEM_DA = ('阅读下列材料，计算 $50 \\div \\left(\\frac{1}{3}-\\frac{1}{4}\\right)$．\n'
           '(1) 解法 1 思路：原式 $=50 \\div \\frac{1}{3}-50 \\div \\frac{1}{4}$；'
           '这种做法正确吗？答：______．\n'
           '(2) 计算：$\\frac{7}{8} \\div \\frac{1}{4}=$ ______．')


def leak_ok(name, html, extra=()):
    """正例：题目卷这段 HTML **必须放行**（误拦=出不了卷）。"""
    try:
        RP.core.leak_guard(html, extra)
        ok('放行：' + name, True)
    except AssertionError as e:
        ok('放行：' + name, False, str(e)[:110])


def leak_bad(name, html, kw=None, extra=()):
    """反例：真泄漏**必须仍被拦**，且拦的理由对得上。"""
    try:
        RP.core.leak_guard(html, extra)
        ok('拦下：' + name, False, '没抛错（放宽了真泄漏面）')
    except AssertionError as e:
        ok('拦下：' + name, (kw in str(e)) if kw else True, str(e)[:110])


def unit_leak_guard():
    print('\n── 泄答案闸·白名单口径单测（PRD-008 §一②-3） ──')
    C, M = RP.core, RP.renderers.get('math')
    B = lambda md: {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': md}]}]}       # noqa: E731

    ok('口径①：判定两表里不再有裸词「解：」「答：」',
       C.STEM_LEGIT_WORDS == ('解：', '答：')
       and not [w for w in C.STEM_LEGIT_WORDS
                if w in C.ANSWER_ONLY_TEX or w in C.ANSWER_ONLY_CLASSES],
       repr(C.ANSWER_ONLY_TEX + C.ANSWER_ONLY_CLASSES))
    ok('口径②：判定表全是渲染层注入物（宏 2 条 + 容器类 5 条）',
       C.ANSWER_ONLY_TEX == ('\\color{', '\\mathbf{')
       and set(C.ANSWER_ONLY_CLASSES) == {'ln', 'st', 'app-sol', 'ansv', 'a'},
       repr(C.ANSWER_ONLY_CLASSES))

    # ── 正例：窗G 两道被误拦的题型，题面固有「解：/答：」一律放行 ──
    qj = M.fill(RP.adapt_item({'question': {'blocks': B(STEM_JIE),
                                            'answer_blocks': B('$21$')}}, 'fill', 'T'),
                0, False, None)
    qd = M.fill(RP.adapt_item({'question': {'blocks': B(STEM_DA),
                                            'answer_blocks': B('$-3$')}}, 'fill', 'T'),
                1, False, None)
    ok('正例素材真的带着那两个词（否则放行是假绿）',
       '解：根据题意' in qj and '答：______' in qd, repr(qj)[:80])
    leak_ok('🔴 正例① 窗G U1·2 型：题面固有「解：」的阅读理解讲义题', qj)
    leak_ok('🔴 正例② 窗G MIX·3 型：题面固有「答：___」作答提示位', qd)
    leak_ok('正例③：两道题同在一张题目卷（整卷级放行）',
            '<body class="qsheet">%s%s</body>' % (qj, qd))
    leak_ok('正例④：题面写「答：见解析」这类字样也放行（题面原文即正当内容）',
            '<div class="app">下列解法对吗？答：见解析。</div>')

    # ── 反例：渲染层注入物一条都不许放过 ──
    RED = M.ANSWER_COLOR
    leak_bad('答案着色宏 \\color{ 进题目卷',
             '<div>\\(3+5=\\color{%s}{8}\\)</div>' % RED, '\\color{')
    leak_bad('答案加粗宏 \\mathbf{ 进题目卷', '<div>\\(\\mathbf{8}\\)</div>', '\\mathbf{')
    leak_bad('填空答案 ansv 进题目卷',
             '<div>括号里填几　<span class="ansv" style="color:%s">\\(5\\)</span></div>' % RED,
             'ansv')
    leak_bad('答案卷过程行容器 .ln 进题目卷', '<div class="ln">\\(2x=4\\)</div>', 'ln')
    leak_bad('🔴 答案卷答语行 .ln ind 进题目卷（多类写法，旧闸整串比对抓不住）',
             '<div class="ln ind">答：共 \\(5\\) 元．</div>', 'ln')
    leak_bad('🔴 渲染器注入的「解：」行 .ln ind 进题目卷（放行裸词≠放行这一行）',
             '<div class="ln ind">解：\\(x=2\\)</div>', 'ln')
    leak_bad('.st 过程行进题目卷', '<div class="st">\\(=8\\)</div>', 'st')
    leak_bad('.app-sol 应用题解答进题目卷', '<div class="app-sol">列式 \\(3\\times 5\\)</div>',
             'app-sol')
    leak_bad('🔴 科学 <b class="a"> 答案标记（此前只在注释里说登记了、实际没登记）',
             '<p>气体是<b class="a">氧气</b></p>', 'class="a"')
    leak_bad('骨架私有标记 EXTRA_LEAK_MARKS 照旧生效',
             '<div>ANS-ONLY-MARK</div>', 'ANS-ONLY-MARK', extra=('ANS-ONLY-MARK',))

    # ── 结构依据：每个槽的**答案卷**输出都必须带答案卷专有标记 ──
    # 🔴 这一组不绿，白名单口径就不成立：渲染器注入的「解：/答：」会没有容器兜着，
    #    摘掉裸词就真成了放宽。新增槽位漏挂标记在这里当场变红。
    ROWS = lambda *ms: {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': m}]}      # noqa: E731
                                         for m in ms]}
    opt = lambda lb, md: {'type': 'option', 'label': lb,                             # noqa: E731
                          'blocks': [{'type': 'text', 'md': md}]}
    Q = lambda **kw: {'question': kw}                                                # noqa: E731
    fixtures = [
        ('oral', Q(blocks=B('$36\\div 4$'), answer_blocks=B('$9$'))),
        ('expr', Q(blocks=B('$36\\div 4+2$'), analysis_blocks=B('$9+2=11$'))),
        ('equation', Q(blocks=B('$2x+1=5$'), analysis_blocks=ROWS('$2x=4$', '$x=2$'))),
        ('word', Q(blocks=B('共几元？'), analysis_blocks=B('＝$3\\times 5$\n＝$15$'),
                   answer_blocks=B('共 $15$ 元'))),
        ('word_multi', Q(blocks=B('共几层？'), analysis_blocks=ROWS('$6+3=9$', '共 $9$ 层'),
                         answer_blocks=B('共 $9$ 层'))),
        ('fill', Q(blocks=B('$3+\\square=8$'), answer_blocks=B('$5$'))),
        ('choice', Q(blocks={'v': 2, 'rows': [{'cells': [
            {'type': 'text', 'md': '负数是（　）'}, opt('A', '$-2$'), opt('B', '$3$')]}]},
            answer_blocks=B('A'))),
    ]
    for slot, it in fixtures:
        data = RP.adapt_item(it, slot, 'T')
        ha = M.SLOTS[slot](data, 0, True, None)
        marks = C.answer_marks_in(ha)
        ok('闸覆盖·%s 槽答案卷输出带专有标记 %s' % (slot, marks), bool(marks), ha[:100])
        leak_bad('闸覆盖·%s 槽的答案卷输出整段进题目卷' % slot, ha)
        leak_ok('闸覆盖·%s 槽的题目卷输出本身放行' % slot, M.SLOTS[slot](data, 0, False, None))
    dn = RP.adapt_item({'question': {'blocks': B('$1-2=$（　）'), 'answer_blocks': None}},
                       'fill', 'T')
    ok('闸覆盖·唯一无标记的形态=fill 无答案态「（待补答案）」（没有答案可泄，本就不需要标记）',
       dn['ans'] == '（待补答案）'
       and not C.answer_marks_in(M.fill(dn, 0, True, None)), repr(dn['ans']))


def unit_figure(root, db):
    """figure 块（2026-08-20 实装）：asset 指针 → 真文件 → <img> 按块 width 限宽。"""
    print('\n── figure 单测 ──')
    A = RP.AssetResolver(db=db, root=root)
    cell = lambda h=FIG_HASH, w='48%': {'type': 'figure', 'asset': h, 'width': w}   # noqa: E731
    B = lambda c: {'v': 2, 'rows': [{'cells': [c]}]}                                # noqa: E731

    ls = RP.md_lines(B(cell()), 'T', A)
    h = ls[0] if ls else ''
    ok('figure 正例：asset→file:/// 的 <img>',
       len(ls) == 1 and isinstance(h, RP.Html) and h.kind == 'figure'
       and h.startswith('<img class="fig" src="file:///')
       and 'a1b2c3d4e5f6a1b2.png' in h, repr(ls)[:160])
    ok('figure 正例：按块 width 百分比限宽 + max-width 兜底',
       'style="width:48%;max-width:100%"' in h, repr(h)[:160])
    ok('figure 正例：绝对 URL 指向沙盘真文件（不是 rel_path 原样)',
       str(root).replace('\\', '/') in h, repr(h)[:160])
    ok('figure 正例：绝对单位 width 原样落',
       'style="width:60mm;max-width:100%"' in RP.md_lines(B(cell(w='60mm')), 'T', A)[0])
    ok('figure 正例：解析结果带缓存（同 hash 只查一次）',
       A.url(FIG_HASH, 'T') == h.split('src="')[1].split('"')[0])

    A2 = RP.AssetResolver({'assets': {FIG_HASH: FIG_REL}}, db=None, root=root)
    ok('figure 正例：pack 自带 assets 时一次库都不查',
       A2.url(FIG_HASH, 'T').startswith('file:///') and A2._conn is None)
    A3 = RP.AssetResolver({'assets': {FIG_HASH: {'rel_path': FIG_REL}}}, db=None, root=root)
    ok('figure 正例：pack.assets 的 dict 形态也认', A3.url(FIG_HASH, 'T').startswith('file:///'))

    # ── 反例：一条都不许静默 ──
    raises('asset 库里查不到', lambda: RP.md_lines(B(cell(h='没这个hash')), 'T', A), '查不到')
    raises('asset 有行但文件不在盘上', lambda: RP.md_lines(B(cell(h=GONE_HASH)), 'T', A), '不在盘上')
    raises('rel_path 是绝对路径', lambda: RP.md_lines(B(cell(h=ABS_HASH)), 'T', A), '相对 v2 根')
    raises('figure 缺 asset',
           lambda: RP.md_lines(B({'type': 'figure', 'width': '48%'}), 'T', A), '缺 asset')
    raises('figure 缺 width',
           lambda: RP.md_lines(B({'type': 'figure', 'asset': FIG_HASH}), 'T', A), '缺 width')
    raises('figure width 无单位', lambda: RP.md_lines(B(cell(w=48)), 'T', A), '无单位')
    raises('figure width 百分比越界', lambda: RP.md_lines(B(cell(w='120%')), 'T', A), '越界')
    raises('无 --db 又无 pack.assets',
           lambda: RP.md_lines(B(cell()), 'T', RP.AssetResolver(root=root)), '没给 --db')
    raises('库文件不存在',
           lambda: RP.md_lines(B(cell()), 'T',
                               RP.AssetResolver(db=root / '没这个库.db', root=root)), '库不存在')

    # ── 槽位：expr/oral 不吃图；fill 答案卷不重复题面图（省纸口径） ──
    it = {'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '$1+1$'}]}, {'cells': [cell()]}]},
        'answer_blocks': {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': '$2$'}]}]}}}
    raises('expr 槽的题面里有图', lambda: RP.adapt_item(it, 'expr', 'T', A), 'fill / word / choice')
    d = RP.adapt_item(it, 'fill', 'T', A)
    ok('fill 槽·题目卷题面带图', '<img class="fig"' in d['text'])
    ok('fill 槽·答案卷题面剥图换占位（省纸口径不破）',
       '<img' not in d['text_ans'] and RP.FIG_IN_Q in d['text_ans'], repr(d['text_ans'])[:120])
    opt = lambda lb, md: {'type': 'option', 'label': lb,                            # noqa: E731
                          'blocks': [{'type': 'text', 'role': '题面', 'md': md}]}
    ch = {'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '看图选（　）'}]},
        {'cells': [cell(w='30%')]},
        {'cells': [opt('A', 'x'), opt('B', 'y')]}]}, 'answer_blocks': None,
        'analysis_blocks': None}}
    dc = RP.adapt_item(ch, 'choice', 'T', A)
    ok('choice 槽·配图题干渲进题面（此前被静默丢）',
       '<img class="fig"' in dc['text'] and len(dc['options']) == 2, repr(dc['text'])[:120])
    ch2 = {'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '选（　）'}]},
        {'cells': [opt('A', 'x'), opt('B', 'y')]}]},
        'answer_blocks': {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': 'B'}]},
                                           {'cells': [cell(w='30%')]}]},
        'analysis_blocks': None}}
    dc2 = RP.adapt_item(ch2, 'choice', 'T', A)
    ok('🔴 choice 槽·答案带图不误拒（2026-08-20 修：答案漏传 assets）',
       'B' in dc2['ans'] and '<img class="fig"' in dc2['ans'], repr(dc2['ans'])[:120])
    fopt = lambda lb: {'type': 'option', 'label': lb, 'blocks': [cell(w='46%')]}      # noqa: E731
    ch3 = {'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '数轴表示正确的是（　）'}]},
        {'cells': [fopt('A'), fopt('B'), fopt('C'), fopt('D')]}]},
        'answer_blocks': None, 'analysis_blocks': None}}
    dc3 = RP.adapt_item(ch3, 'choice', 'T', A)
    ok('🔴 choice 槽·图选项实装（两列+图宽按列数折算 46%→92%）',
       dc3['opt_cols'] == 2 and all('<img class="fig"' in o['html'] for o in dc3['options'])
       and 'width:92%' in dc3['options'][0]['html'], repr(dc3['options'][0])[:160])
    raises('option 嵌 table 仍拒渲',
           lambda: RP.adapt_item({'question': {'blocks': {'v': 2, 'rows': [
               {'cells': [{'type': 'option', 'label': 'A',
                           'blocks': [{'type': 'table', 'md': 'x'}]}]}]},
               'answer_blocks': None}}, 'choice', 'T', A), '只认 text/figure')


def unit_table(root, db):
    """table 块（2026-08-20 实装）：GFM 与 rows 两形态都渲成规矩 HTML 表。"""
    print('\n── table 单测 ──')
    A = RP.AssetResolver(db=db, root=root)
    B = lambda c: {'v': 2, 'rows': [{'cells': [c]}]}                                # noqa: E731

    gfm = {'type': 'table', 'md': '| 甲 | 乙 |\n| --- | --- |\n| $1$ | 二 |\n| 三 | 四 |'}
    h = RP.md_lines(B(gfm), 'T')[0]
    ok('table·GFM 正例：出 thead/tbody 规矩表',
       isinstance(h, RP.Html) and h.kind == 'table'
       and h.startswith('<table class="tbl"><thead>')
       and h.count('<tr>') == 3 and h.count('<td>') == 4, repr(h)[:200])
    ok('table·GFM 正例：表头进 <th>，格内公式转定界串',
       '<th>甲</th><th>乙</th>' in h and '<td>\\(1\\)</td>' in h, repr(h)[:200])
    h2 = RP.md_lines(B({'type': 'table', 'md': '| a\\|b | c |\n|---|---|\n| 1 | 2 |'}), 'T')[0]
    ok('table·GFM 正例：格内 \\| 不劈格', '<th>a|b</th><th>c</th>' in h2, repr(h2)[:200])

    rows = {'type': 'table', 'rows': [
        [[{'type': 'text', 'md': '甲'}], [{'type': 'text', 'md': '$1$'}]],
        [[{'type': 'text', 'md': '乙'}], [{'type': 'figure', 'asset': FIG_HASH, 'width': '20%'}]]]}
    h3 = RP.md_lines(B(rows), 'T', A)[0]
    ok('table·rows 正例：全 <td> 不猜表头 + 格内图渲进单元格',
       h3.kind == 'table' and '<thead>' not in h3 and h3.count('<tr>') == 2
       and h3.count('<td>') == 4 and '<td><img class="fig"' in h3
       and '<td>\\(1\\)</td>' in h3, repr(h3)[:240])

    # ── 坏表反例 ──
    raises('GFM 无 |---| 分隔行',
           lambda: RP.md_lines(B({'type': 'table', 'md': '| 甲 | 乙 |\n| 1 | 2 |'}), 'T'), '分隔行')
    raises('GFM 分隔行不在第 2 行',
           lambda: RP.md_lines(B({'type': 'table',
                                  'md': '| 甲 |\n| 乙 |\n|---|'}), 'T'), '第 2 行')
    raises('GFM 正文行列数与表头对不上',
           lambda: RP.md_lines(B({'type': 'table',
                                  'md': '| 甲 | 乙 |\n|---|---|\n| 1 | 2 | 3 |'}), 'T'), '列数对不上')
    raises('GFM 只有一行',
           lambda: RP.md_lines(B({'type': 'table', 'md': '| 甲 | 乙 |'}), 'T'), '不足两行')
    raises('table 既无 md 也无 rows',
           lambda: RP.md_lines(B({'type': 'table'}), 'T'), '两形态')
    raises('rows 的 cell 被拍平成字符串',
           lambda: RP.md_lines(B({'type': 'table', 'rows': [['甲', '乙']]}), 'T'), '禁拍平')
    raises('rows 各行列数不齐',
           lambda: RP.md_lines(B({'type': 'table', 'rows': [
               [[{'type': 'text', 'md': '甲'}], [{'type': 'text', 'md': '乙'}]],
               [[{'type': 'text', 'md': '丙'}]]]}), 'T'), '列数对不上')
    raises('rows 格内嵌 option（表中选项）',
           lambda: RP.md_lines(B({'type': 'table', 'rows': [
               [[{'type': 'option', 'label': 'A', 'blocks': []}]]]}), 'T'), '格内只认')
    raises('text 块的 md 里夹 GFM 表',
           lambda: RP.md_lines({'v': 2, 'rows': [{'cells': [
               {'type': 'text', 'md': '看表：\n| 甲 | 乙 |\n|---|---|\n| 1 | 2 |'}]}]}, 'T'),
           'table 块')

    # 表进 fill 的题面流：答案卷保留表（表是题面数据，剥了答案看不懂）
    it = {'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '看表填空：'}]}, {'cells': [gfm]}]},
        'answer_blocks': {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': '$5$'}]}]}}}
    d = RP.adapt_item(it, 'fill', 'T', A)
    ok('table 进 fill 题面流（答案卷保留表）',
       '<table class="tbl">' in d['text'] and '<table class="tbl">' in d['text_ans'])
    itw = {'question': {'blocks': {'v': 2, 'rows': [
        {'cells': [{'type': 'text', 'md': '看表答题。'}]}, {'cells': [gfm]}]},
        'analysis_blocks': {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': '＝$1+2$\n＝$3$'}]}]},
        'answer_blocks': {'v': 2, 'rows': [{'cells': [{'type': 'text', 'md': '答：$3$。'}]}]}}}
    dw = RP.adapt_item(itw, 'word', 'T', A)
    ok('table 进 word 题面流', '<table class="tbl">' in dw['text'] and dw['lines'] == ['1+2', '3'])


# ══════════════ 二·五、图表 pack 端到端出件 ══════════════
def _fig_table_pack():
    """一卷 × 两节：fill 节带题面图、word 节带题面表。kind 非「打卡天」⇒ 不断言页数。"""
    T = lambda md: {'type': 'text', 'role': '题面', 'md': md}                        # noqa: E731
    blk = lambda cells: {'v': 2, 'rows': [{'cells': [c]} for c in cells]}            # noqa: E731
    return {
        'contract': 'render-pack/v1',
        'artifact': {'id': 'A-FIGTBL-001', 'name': '图表样张', 'kind': '样张'},
        'papers': [{
            'id': 'p-fig', 'kind': '样张', 'title': '图表实装样张', 'ord': 1,
            'layout': {'layout': 'dense_sections', 'body_pt': 12.5, 'watermark': None,
                       'sections': [
                           {'name': '看图填空', 'slot': 'fill', 'grid': 'g5', 'gap': 0},
                           {'name': '看表解答', 'slot': 'word', 'grid': 'block',
                            'gap': 0, 'gap_each': 10}]},
            'items': [
                {'ord': 1, 'section': '看图填空', 'score': None, 'question': {
                    'id': 'qf1',
                    'blocks': blk([T('看图填空：$3+\\square=8$'),
                                   {'type': 'figure', 'asset': FIG_HASH, 'width': '40%'}]),
                    'answer_blocks': blk([{'type': 'text', 'role': '答案', 'md': '$5$'}])}},
                {'ord': 2, 'section': '看图填空', 'score': None, 'question': {
                    'id': 'qf2',
                    'blocks': blk([T('再填一个：$9-\\square=4$')]),
                    'answer_blocks': blk([{'type': 'text', 'role': '答案', 'md': '$5$'}])}},
                {'ord': 3, 'section': '看表解答', 'score': None, 'question': {
                    'id': 'qt1',
                    'blocks': blk([T('下表是甲乙两地的气温，求温差。'),
                                   {'type': 'table',
                                    'md': '| 地点 | 气温 |\n| --- | --- |\n| 甲 | $-3$ |'
                                          '\n| 乙 | $5$ |'}]),
                    'analysis_blocks': blk([{'type': 'text', 'role': '解析',
                                             'md': '＝$5-(-3)$\n＝$8$'}]),
                    'answer_blocks': blk([{'type': 'text', 'role': '答案', 'md': '答：温差 $8$ ℃。'}])}},
            ]}]}


def positive_figtable(tmp, root, db):
    print('\n── 正例：图 + 表 端到端出双 PDF ──')
    p = Path(tmp) / 'figtbl.json'
    p.write_text(json.dumps(_fig_table_pack(), ensure_ascii=False), encoding='utf-8')
    out = Path(tmp) / '图表卷'
    rc = RP.main([str(p), '--out-dir', str(out), '--stem', '图表样张', '--no-log'] + sb_args())
    ok('图表卷出件成功', rc == 0, '退出码 %d' % rc)
    q_pdf = out / '图表样张.pdf'
    a_pdf = out / '图表样张（答案）.pdf'
    ok('图表卷双 PDF 落盘',
       q_pdf.exists() and q_pdf.stat().st_size > 5000 and a_pdf.exists())
    qh = (out / '_源' / '_图表样张.html').read_text(encoding='utf-8')
    ah = (out / '_源' / '_图表样张（答案）.html').read_text(encoding='utf-8')
    ok('题目卷 HTML 有 <img class="fig"> 且指向沙盘真文件',
       '<img class="fig"' in qh and 'a1b2c3d4e5f6a1b2.png' in qh)
    ok('题目卷 HTML 有 <table class="tbl"> 规矩表',
       '<table class="tbl">' in qh and '<th>地点</th>' in qh)
    ok('🔴 答案卷不重复题面图（省纸口径不破）',
       '<img class="fig"' not in ah and RP.FIG_IN_Q in ah)


def negative_figtable(tmp):
    print('\n── 反例：图/表坏件必拒（端到端） ──')
    p = _fig_table_pack()
    p['papers'][0]['items'][0]['question']['blocks']['rows'][1]['cells'][0]['asset'] = '不存在的hash'
    rejects('端到端·asset 查不到', p, tmp)

    p = _fig_table_pack()
    p['papers'][0]['items'][0]['question']['blocks']['rows'][1]['cells'][0]['asset'] = GONE_HASH
    rejects('端到端·asset 文件不在盘上', p, tmp)

    p = _fig_table_pack()
    p['papers'][0]['items'][0]['question']['blocks']['rows'][1]['cells'][0].pop('width')
    rejects('端到端·figure 缺 width', p, tmp)

    p = _fig_table_pack()
    p['papers'][0]['items'][2]['question']['blocks']['rows'][1]['cells'][0]['md'] = \
        '| 地点 | 气温 |\n| 甲 | $-3$ |'
    rejects('端到端·GFM 表无分隔行', p, tmp)

    p = _fig_table_pack()
    p['papers'][0]['items'][2]['question']['blocks']['rows'][1]['cells'][0] = \
        {'type': 'table', 'rows': [['甲', '乙']]}
    rejects('端到端·表格 cell 被拍平成字符串', p, tmp)


# ══════════════ 二·六、白名单口径 + 两槽 端到端出件 ══════════════
def _leak_pack():
    """一卷三节：阅读理解（题面固有 解：/答：，fill）+ 解方程（equation）+ 多行解答（word_multi）。
    kind 非「打卡天」⇒ 不断言页数。"""
    blk = lambda *ms: {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': '题面',   # noqa: E731
                                                    'md': m}]} for m in ms]}
    return {
        'contract': 'render-pack/v1',
        'artifact': {'id': 'A-LEAK-001', 'name': '白名单口径样张', 'kind': '样张'},
        'papers': [{
            'id': 'p-leak', 'kind': '样张', 'title': '泄答案闸白名单·两槽样张', 'ord': 1,
            'layout': {'layout': 'dense_sections', 'body_pt': 12.5, 'watermark': None,
                       'sections': [
                           {'name': '阅读理解', 'slot': 'fill', 'grid': 'block', 'gap': 0},
                           {'name': '解方程', 'slot': 'equation', 'grid': 'block', 'gap': 0},
                           {'name': '多行解答', 'slot': 'word_multi', 'grid': 'block',
                            'gap': 0, 'gap_each': 8}]},
            'items': [
                {'ord': 1, 'section': '阅读理解', 'score': None, 'question': {
                    'id': 'qr1',
                    'blocks': blk(STEM_JIE, '（1）若 $x^{2}+x+2=5$，求 $3x^{2}+3x+4$ 的值．'),
                    'answer_blocks': blk('$13$')}},
                {'ord': 2, 'section': '阅读理解', 'score': None, 'question': {
                    'id': 'qr2', 'blocks': blk(STEM_DA), 'answer_blocks': blk('$\\frac{7}{2}$')}},
                {'ord': 3, 'section': '解方程', 'score': None, 'question': {
                    'id': 'qe1', 'blocks': blk('$2x+1=5$'),
                    'analysis_blocks': blk('$2x=5-1$', '$2x=4$', '$x=2$'),
                    'answer_blocks': blk('$x=2$')}},
                {'ord': 4, 'section': '多行解答', 'score': None, 'question': {
                    'id': 'qw1',
                    'blocks': blk('小明骑车从家出发，先向东 $1km$ 到 $A$ 村，再向东 $4km$ 到 $B$ 村．',
                                  '（1）以家为原点、向东为正，$A$、$B$ 各表示什么数？\n'
                                  '（2）$B$ 村离家多远？'),
                    'analysis_blocks': blk('（1）$A=0+1=+1$，$B=1+4=+5$',
                                           '（2）$|5-0|=5$（$km$）'),
                    'answer_blocks': blk('（1）$A=+1$，$B=+5$；（2）$5$ 千米')}},
            ]}]}


def positive_leak(tmp):
    print('\n── 正例：白名单口径 + equation/word_multi 端到端出双 PDF ──')
    p = Path(tmp) / 'leak.json'
    p.write_text(json.dumps(_leak_pack(), ensure_ascii=False), encoding='utf-8')
    out = Path(tmp) / '白名单卷'
    rc = RP.main([str(p), '--out-dir', str(out), '--stem', '白名单样张', '--no-log'] + sb_args())
    ok('🔴 白名单卷出件成功（题面固有 解：/答： 不再被误拦）', rc == 0, '退出码 %d' % rc)
    qh = (out / '_源' / '_白名单样张.html').read_text(encoding='utf-8')
    ah = (out / '_源' / '_白名单样张（答案）.html').read_text(encoding='utf-8')
    ok('🔴 题目卷原样保留题面里的「解：」「答：」（放行不是靠删字）',
       '解：根据题意' in qh and '答：______' in qh)
    ok('题目卷零答案容器类零着色宏（闸真跑过且真绿）',
       not RP.core.answer_class_hits(qh) and '\\color{' not in qh
       and '\\mathbf{' not in qh)
    ok('equation 槽出件：答案卷「解：」逐步 + 末步着色',
       'class="ln ind">解：' in ah and '\\color{' in ah)
    ok('word_multi 槽出件：答案卷逐行 .ln ind（不压成一条＝链）',
       ah.count('class="ln ind"') >= 5, str(ah.count('class="ln ind"')))
    q_pdf, a_pdf = out / '白名单样张.pdf', out / '白名单样张（答案）.pdf'
    ok('白名单卷双 PDF 落盘',
       q_pdf.exists() and q_pdf.stat().st_size > 5000 and a_pdf.exists())


def negative_leak(tmp):
    print('\n── 反例：真泄漏必拦（端到端） ──')
    p = _leak_pack()
    p['papers'][0]['items'][0]['question']['blocks']['rows'][1]['cells'][0]['md'] = \
        '（1）答案是 $\\color{#c0272d}{13}$．'
    rejects('端到端·答案着色宏混进题面（渲染层注入物）', p, tmp)

    p = _leak_pack()
    p['papers'][0]['items'][1]['question']['blocks']['rows'][0]['cells'][0]['md'] = \
        '本题答案 <span class="ansv">$\\frac{7}{2}$</span>'
    rejects('端到端·答案元素串 class=ansv 混进题面', p, tmp)   # 🔴 名字里别带引号：会当文件名用

    p = _leak_pack()
    p['papers'][0]['items'][2]['question']['blocks']['rows'][0]['cells'][0]['md'] = \
        '解方程：$2x+1=5$'
    rejects('端到端·equation 槽题面带指令词（劈不出左右两边）', p, tmp)

    p = _leak_pack()
    p['papers'][0]['items'][3]['question'].pop('analysis_blocks')
    p['papers'][0]['items'][3]['question'].pop('answer_blocks')
    rejects('端到端·word_multi 无解析无答案（答案卷整题空白）', p, tmp)


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
    print('\n── 反例（契约/公式/图指针/归位 四条必拒） ──')
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
    # figure 已实装（2026-08-20），此处拒的是**悬空的图指针**：库里查无此 asset
    rejects('figure 的 asset 库里查不到', p, tmp)

    p = copy.deepcopy(base)
    p['papers'][0]['items'][1]['section'] = '不存在的节'
    rejects('section 不在 layout.sections 里', p, tmp)


# ══════════════ 四、exam_paper 骨架：四条闸 + 卷面口径 ══════════════
# 🔴 对标件 = 测试数据/七上试卷/卷3（4 张拍照卷面）。2026-08-20 全量 24 题渲染实测校准：
#    页1 正文左 25.2mm / 页2~4 左 10.2mm（密封线与走廊只吃第 1 页）、行距 8.29mm、
#    题号全卷 1..24 连号、解答题题号带分值、表铺 88% 版心。
def _ep_ctx(secs, lay):
    return {'renderer': RP.renderers.get('math'), 'sections': secs,
            'book_title': '七年级数学上册单元测试卷', 'paper_layout': lay}


def _ep_fill(t):
    return {'text': t, 'text_ans': t, 'ans': '（待补答案）'}


def _ep_case(full=20, scores0=(3, 3), seal=True):
    """两节四题的最小真卷：选择 3+3 分（不印逐题分值）＋解答 6+8 分（印）。"""
    secs = [{'name': '一、选择题', 'slot': 'fill', 'score_note': '每小题 3 分，共 6 分',
             'item_scores': list(scores0), 'show_item_score': False},
            {'name': '二、解答题', 'slot': 'fill', 'score_note': '共 14 分',
             'item_scores': [6, 8]}]
    lay = {'full_score': full, 'duration_min': 120, 'subtitle': '第1章 有理数',
           'score_table': True, 'seal_line': seal}
    day = [[_ep_fill('题一'), _ep_fill('题二')], [_ep_fill('题三'), _ep_fill('题四')]]
    return secs, lay, day


def araises(name, fn, kw=None):
    """反例（骨架闸走 assert）：必须抛 AssertionError，且报错带 kw。"""
    try:
        fn()
        ok('拒渲：' + name, False, '没抛错')
    except AssertionError as e:
        ok('拒渲：' + name, (kw in str(e)) if kw else True, str(e)[:110])


def unit_exam_paper():
    print('\n── exam_paper 骨架单测（卷 3 复刻口径） ──')
    EP = RP.layouts.get('exam_paper')
    secs, lay, day = _ep_case()
    card = EP.render_card(0, day, False, _ep_ctx(secs, lay))
    body = '<body>' + card + '</body>'

    qn = [m for m in RP.re.findall(r'<span class="qn">([^<]*)</span>', card)]
    ok('题号全卷连号（跨节不重置）', [q[:2] for q in qn] == ['1.', '2.', '3.', '4.'], repr(qn))
    ok('解答题题号带分值「3.(6 分)」', qn[2] == '3.(6 分)' and qn[3] == '4.(8 分)', repr(qn))
    ok('选择题 show_item_score=False 时题号不带分值',
       qn[0] == '1.' and qn[1] == '2.', repr(qn))
    ok('大题节标题=半角括号带分值',
       '<div class="sec">一、选择题(每小题 3 分，共 6 分)</div>' in card
       and '<div class="sec">二、解答题(共 14 分)</div>' in card, card[:0])
    ok('组卷侧节名自带「一、」不重复印',
       '一、一、' not in card and '二、二、' not in card)
    ok('密封线：字段列 + 「密封线」列 + 虚线 + 首页走廊占位',
       'class="sealgap"' in card and 'class="sealbar"' in card
       and '<div class="col f"><span>学校<i></i>班级' in card and 'class="dash"' in card)
    ok('答案卷不带卷头/密封线（省纸口径）',
       'sealbar' not in EP.render_card(0, day, True, _ep_ctx(secs, lay))
       and 'stab' not in EP.render_card(0, day, True, _ep_ctx(secs, lay)))
    EP.guard(body, [day], _ep_ctx(secs, lay))
    ok('guard 正例：题号连号 + 无超长 nowrap + 走廊占位齐', True)

    # ── 反例①满分守恒闸（凡"拍平"必配守恒闸）──
    s2, l2, d2 = _ep_case(full=99)
    araises('满分守恒闸：逐题合计 20 ≠ 卷头 99',
            lambda: EP.render_card(0, d2, False, _ep_ctx(s2, l2)), '满分守恒闸')
    # ── 反例② item_scores 数量闸 ──
    s3, l3, d3 = _ep_case(scores0=(3,))
    araises('item_scores 给 1 个而本节 2 题',
            lambda: EP.render_card(0, d3, False, _ep_ctx(s3, l3)), 'item_scores')
    # ── 反例③题号连号闸 ──
    araises('题号连号闸：第 3 题被改成 9',
            lambda: EP.guard(body.replace('<span class="qn">3.', '<span class="qn">9.'),
                             [day], _ep_ctx(secs, lay)), '题号不连续')
    # ── 反例④防缩页闸（Chrome 只会静默缩印，出件前拒得掉才便宜）──
    long_nb = '<span class="nb">%s</span>' % ('长' * 30)
    araises('防缩页闸：整句被裹进 nowrap',
            lambda: EP.guard(body.replace('题一', '题一' + long_nb),
                             [day], _ep_ctx(secs, lay)), '防缩页闸')
    # ── 反例⑤首页走廊闸 ──
    araises('首页走廊闸：密封线在、走廊占位没了',
            lambda: EP.guard(body.replace('<div class="sealgap"></div>', ''),
                             [day], _ep_ctx(secs, lay)), '首页走廊闸')

    # ── _unnb 正例：裹错的超长 nowrap 在渲染时就被拆掉，闸才可能是常绿的 ──
    day_nb = [[_ep_fill('题一' + long_nb), _ep_fill('题二')],
              [_ep_fill('题三'), _ep_fill('题四')]]
    card_nb = EP.render_card(0, day_nb, False, _ep_ctx(secs, lay))
    ok('🔴 _unnb 拆包：超长 nowrap 渲完一个不剩（内容一字不动）',
       not EP._long_nb(card_nb) and '长' * 30 in card_nb)

    # ── gap_each 留白=margin 不=垫片（2026-08-20 用户打回：跨页垫片把下一题从页顶推下）──
    s4, l4, d4 = _ep_case()
    s4[0]['gap_each'] = 5
    s4[1]['gap_each'] = 40
    card_g = EP.render_card(0, d4, False, _ep_ctx(s4, l4))
    ok('🔴 gap_each 走 margin-bottom（跨页自动截断，下一题顶格）',
       card_g.count('class="q" style="margin-bottom:5mm"') == 2
       and card_g.count('class="q" style="margin-bottom:40mm"') == 1
       and '<div class="sp"' not in card_g, card_g[:0])
    ok('🔴 末节末题 margin 置零（强制分页不截断 margin，会顶出空白页）',
       card_g.count('margin-bottom:40mm') == 1, card_g[:0])
    ans_g = EP.render_card(0, d4, True, _ep_ctx(s4, l4))
    ok('答案卷无作答留白 margin', 'margin-bottom:5mm' not in ans_g
       and 'margin-bottom:40mm' not in ans_g)

    # ── CSS 口径（卷 3 像素实测反推，改一个数就该有人看见）──
    css = EP.css()
    ok('缺省正文 11.2pt / 行距 2.08 / 悬挂缩进 1em',
       'font-size: 11.20pt' in css and 'line-height: 2.08' in css
       and '.q > div { padding-left: 1em; text-indent: -1em; }' in css)
    ok('末尾作答留白不顶出空页', '.card > .sp:last-child { display: none; }' in css)
    ok('🔴 密封线只吃第 1 页：absolute + 固定 272mm 高（不是 fixed）',
       '.sealbar { position: absolute; left: 0; top: 0; height: 272mm;' in css
       and 'position: fixed' not in css.split('.wm {')[0])
    ok('首页走廊：float 占位 15.2mm + 卡内块自成 BFC + 评分表明码减走廊',
       '.sealgap { float: left; width: 15.2mm; height: 272mm; }' in css
       and 'display: flow-root' in css
       and '.card.sealed > .stab { width: calc(100% - 15.2mm); }' in css)
    ok('题面表铺 88% 版心 + 表头白底常规字重（真卷长相）',
       '.q table.tbl { width: 88%; }' in css
       and '.q table.tbl th { background: none; font-weight: normal; }' in css)
    ok('选项表边距归零（防横向溢出 ⇒ 防整卷缩印）',
       '.q table:not(.tbl) { margin: 0 !important; text-indent: 0; }' in css)

    # ── 选项列数门槛（卷 3 第 10 题实测校准）──
    opt = lambda l, t: {'type': 'option', 'label': l,                       # noqa: E731
                        'blocks': [{'type': 'text', 'role': '题面', 'md': t}]}
    j3q10 = {'v': 2, 'rows': [{'cells': [
        {'type': 'text', 'role': '题面', 'md': '下列语句错误的是(　　).'},
        opt('A', '相反数是它本身的数是 $0$'), opt('B', '负数的绝对值是正数'),
        opt('C', '$0$ 是最小的有理数'), opt('D', '绝对值等于它本身的数是非负数')]}]}
    d10 = RP.adapt_item({'question': {'blocks': j3q10, 'answer_blocks': None,
                                      'analysis_blocks': None}}, 'choice', 'T')
    ok('choice 门槛校准：卷 3 第 10 题（最长 28）排两列，同原卷',
       RP._plain_len('绝对值等于它本身的数是非负数') == 28 and d10['opt_cols'] == 2,
       repr(d10.get('opt_cols')))


def main():
    if not SAMPLE.exists():
        sys.exit('🔴 样例不存在：%s' % SAMPLE)
    tmp = tempfile.mkdtemp(prefix='render_paper_test_')
    try:
        root, db = make_sandbox(tmp)
        unit()
        unit_choice()
        unit_equation_wordmulti(root, db)
        unit_leak_guard()
        unit_figure(root, db)
        unit_table(root, db)
        unit_exam_paper()
        negative(tmp)
        negative_figtable(tmp)
        negative_leak(tmp)
        positive(tmp)
        positive_figtable(tmp, root, db)
        positive_leak(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('\n═══ 结论：通过 %d 条，失败 %d 条 ═══' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  🔴 %s' % f)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
