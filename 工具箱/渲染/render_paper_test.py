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
    it2 = {'question': {'blocks': B('$36\\div 4$'), 'answer_blocks': B('$9$')}}
    d2 = RP.adapt_item(it2, 'oral', 'T')
    ok('oral 槽位：stem + 末行答案', d2['stem'].h == '36\\div 4' and d2['lines'] == ['9'])
    try:
        RP.adapt_item(it2, 'equation', 'T')
        ok('未实装槽位拒渲', False, '没抛错')
    except RP.PackError:
        ok('未实装槽位拒渲', True)


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
        ok('option 内嵌 figure 拒渲', False, '没抛错')
    except RP.PackError:
        ok('option 内嵌 figure 拒渲', True)
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


def main():
    if not SAMPLE.exists():
        sys.exit('🔴 样例不存在：%s' % SAMPLE)
    tmp = tempfile.mkdtemp(prefix='render_paper_test_')
    try:
        root, db = make_sandbox(tmp)
        unit()
        unit_choice()
        unit_figure(root, db)
        unit_table(root, db)
        negative(tmp)
        negative_figtable(tmp)
        positive(tmp)
        positive_figtable(tmp, root, db)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('\n═══ 结论：通过 %d 条，失败 %d 条 ═══' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  🔴 %s' % f)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
