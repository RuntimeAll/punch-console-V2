# -*- coding: utf-8 -*-
"""三闸拒错自证：临时库 + 合法/非法用例各若干，跑完打印通过表。

    python 工具箱\\库\\gates_test.py

判绿口径：**合法全过 + 非法全拒**（任一条不符即退出码 1）。
闸只有能拒错才算闸——常绿闸=没闸。
"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gates import validate_blocks, assert_leaf_kp, execution_valve, LeafKpError  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent


# ── 临时库（照真 DDL 建，不另写简化版）────────────────────────────────
def build_tmp_kb(tmpdir):
    db = Path(tmpdir) / 'kb_test.db'
    conn = sqlite3.connect(str(db))
    conn.executescript((SQL_DIR / 'schema_kb.sql').read_text(encoding='utf-8'))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executemany(
        'INSERT INTO kp(id,name,parent_id,level,ord,status) VALUES (?,?,?,?,?,?)',
        [('001', '人教七上', None, '版本', 1, '现行'),
         ('001001', '有理数', '001', '单元', 1, '现行'),          # 有子 → 章级
         ('001001001', '有理数混合运算', '001001', '考点', 1, '现行'),   # 叶子
         ('001001002', '绝对值化简', '001001', '考点', 2, '现行'),      # 叶子
         ('001001003', '旧考点已并叶', '001001', '考点', 3, '退役'),    # 退役叶（无子）→ 状态闸拒
         ('001002', '实数', '001', '单元', 2, '未铺')])                # 未铺占位（无子）→ 层级闸拒
    conn.commit()
    return conn


# ── 块流用例 ──────────────────────────────────────────────────────────
def B(rows):
    return json.dumps({'v': 2, 'rows': rows}, ensure_ascii=False)


T_OK = B([{'cells': [{'type': 'text', 'role': '题面', 'md': '计算 $1+2\\times3$ 的值。'}]}])
T_FIG = B([{'cells': [{'type': 'text', 'md': '把两个直角梯形拼成一个长方形（如图）。'}]},
           {'cells': [{'type': 'figure', 'asset': 'cceea0b6', 'width': '48%'}]}])
T_OPT = B([{'cells': [{'type': 'text', 'md': '下列图形中是轴对称图形的是（　）'}]},
           {'cells': [{'type': 'option', 'label': L,
                       'blocks': [{'type': 'figure', 'asset': f'f0{i}', 'width': '22%'}]}
                      for i, L in enumerate('ABCD', 1)]}])
T_TABLE_MD = B([{'cells': [{'type': 'text', 'md': '根据下表回答：\n\n| 月份 | 产量 |\n|---|---|\n| 1 | 20 |\n\n哪个月最多？'}]}])
T_TABLE_BLK = B([{'cells': [{'type': 'table', 'rows': [
    [[{'type': 'text', 'md': '甲'}], [{'type': 'figure', 'asset': 'g1', 'width': '30%'}]],
    [[{'type': 'text', 'md': '乙'}], [{'type': 'text', 'md': '3'}]]]}]}])
T_ANS = B([{'cells': [{'type': 'text', 'role': '答案', 'md': '1、$x=3$'}]}])          # 答案流不跑前缀闸
T_DECIMAL = B([{'cells': [{'type': 'text', 'md': '1.5 米的绳子剪去一半后还剩多少？'}]}])  # (?!\d) 不该误判
T_ABSW = B([{'cells': [{'type': 'figure', 'asset': 'a1', 'width': '60mm'}]},
            {'cells': [{'type': 'text', 'md': '量一量上图线段长度。'}]}])

BAD_V1 = json.dumps({'v': 1, 'rows': [{'cells': [{'type': 'text', 'md': 'x'}]}]}, ensure_ascii=False)
BAD_NOROWS = json.dumps({'v': 2}, ensure_ascii=False)
BAD_EMPTYCELLS = B([{'cells': []}])
BAD_TYPE = B([{'cells': [{'type': 'video', 'src': 'x.mp4'}]}])
BAD_ROLE = B([{'cells': [{'type': 'text', 'role': '题号', 'md': '求值。'}]}])
BAD_OPTSKIP = B([{'cells': [{'type': 'text', 'md': '选一个（　）'}]},
                 {'cells': [{'type': 'option', 'label': L, 'blocks': [{'type': 'text', 'md': L}]}
                            for L in 'ABD']}])
BAD_OPT2FIG = B([{'cells': [{'type': 'text', 'md': '选一个（　）'}]},
                 {'cells': [{'type': 'option', 'label': 'A', 'blocks': [
                     {'type': 'figure', 'asset': 'f1', 'width': '20%'},
                     {'type': 'figure', 'asset': 'f2', 'width': '20%'}]}]}])
BAD_NOASSET = B([{'cells': [{'type': 'text', 'md': '如图。'}]},
                 {'cells': [{'type': 'figure', 'width': '40%'}]}])
BAD_WIDTH = B([{'cells': [{'type': 'text', 'md': '如图。'}]},
               {'cells': [{'type': 'figure', 'asset': 'f9', 'width': '48'}]}])
BAD_EMPTYTEXT = B([{'cells': [{'type': 'text', 'md': '   '}]}])
BAD_TABLE_NOBLANK = B([{'cells': [{'type': 'text', 'md': '根据下表回答：\n| 月份 | 产量 |\n|---|---|\n| 1 | 20 |\n哪个月最多？'}]}])
BAD_QNO = B([{'cells': [{'type': 'text', 'md': '1、计算：$(-2)^3+5$'}]}])
BAD_SCORE = B([{'cells': [{'type': 'text', 'md': '（3分）如图，求阴影面积。'}]}])
BAD_OPT_EMPTY = B([{'cells': [{'type': 'option', 'label': 'A', 'blocks': []}]}])
BAD_TABLE_NOSEP = B([{'cells': [{'type': 'table', 'md': '| 月份 | 产量 |\n| 1 | 20 |'}]}])
BAD_JSON = '{"v":2,"rows":['

BLOCK_LEGAL = [('L1 纯文本题面', T_OK, True), ('L2 文+图(48%)', T_FIG, True),
               ('L3 四选项各1图', T_OPT, True), ('L4 GFM表前后空行', T_TABLE_MD, True),
               ('L5 table块装块列表', T_TABLE_BLK, True), ('L6 答案流带"1、"(非题面)', T_ANS, False),
               ('L7 首块"1.5米"不误判', T_DECIMAL, True), ('L8 图宽绝对值 60mm', T_ABSW, True)]

BLOCK_ILLEGAL = [('X01 v=1', BAD_V1, True), ('X02 缺 rows', BAD_NOROWS, True),
                 ('X03 cells 空', BAD_EMPTYCELLS, True), ('X04 块型 video', BAD_TYPE, True),
                 ('X05 role 非枚举', BAD_ROLE, True), ('X06 选项跳号 ABD', BAD_OPTSKIP, True),
                 ('X07 单选项 2 图', BAD_OPT2FIG, True), ('X08 figure 无 asset', BAD_NOASSET, True),
                 ('X09 width 无单位', BAD_WIDTH, True), ('X10 text.md 空', BAD_EMPTYTEXT, True),
                 ('X11 GFM 表前无空行', BAD_TABLE_NOBLANK, True), ('X12 题号前缀', BAD_QNO, True),
                 ('X13 分值前缀', BAD_SCORE, True), ('X14 option.blocks 空', BAD_OPT_EMPTY, True),
                 ('X15 表块无分隔行', BAD_TABLE_NOSEP, True), ('X16 非法 JSON', BAD_JSON, True)]


def run_blocks(rows_out):
    ok_all = True
    for name, payload, is_stem in BLOCK_LEGAL:
        ok, errs = validate_blocks(payload, is_stem=is_stem)
        ok_all &= ok
        rows_out.append(('闸①块流', name, '过', '过' if ok else '拒:' + '；'.join(errs)[:70], ok))
    for name, payload, is_stem in BLOCK_ILLEGAL:
        ok, errs = validate_blocks(payload, is_stem=is_stem)
        ok_all &= (not ok)
        rows_out.append(('闸①块流', name, '拒', ('拒:' + errs[0][:66]) if not ok else '❌过了', not ok))
    return ok_all


def run_leaf(conn, rows_out):
    ok_all = True
    for name, kid in [('L1 叶子 001001001', '001001001'), ('L2 叶子 001001002', '001001002')]:
        try:
            assert_leaf_kp(conn, kid)
            ok, detail = True, '过'
        except LeafKpError as e:
            ok, detail = False, '❌拒:' + str(e)[:60]
        ok_all &= ok
        rows_out.append(('闸②叶子', name, '过', detail, ok))
    for name, kid in [('X1 章级 001001', '001001'), ('X2 版本级 001', '001'),
                      ('X3 不存在 999', '999'), ('X4 空 id', ''),
                      ('X5 退役叶 001001003', '001001003'), ('X6 未铺单元 001002', '001002')]:
        try:
            assert_leaf_kp(conn, kid)
            ok, detail = False, '❌过了'
        except LeafKpError as e:
            ok, detail = True, '拒:' + str(e)[:66]
        ok_all &= ok
        rows_out.append(('闸②叶子', name, '拒', detail, ok))
    return ok_all


def run_valve(conn, rows_out):
    base = {'blocks_json': T_FIG, 'confidence': 92, 'kp_ids': ['001001001']}
    pure = B([{'cells': [{'type': 'figure', 'asset': 'p1', 'width': '80%'}]}])
    legal = [
        ('L1 常规题 conf=92', dict(base)),
        ('L2 纯图题已过审 conf=0.9', {'blocks_json': pure, 'confidence': 0.9,
                                      'kp_ids': ['001001002'], 'reviewed': True}),
    ]
    illegal = [
        ('X1 置信度 80', dict(base, confidence=80)),
        ('X2 块流非法(v=1)', dict(base, blocks_json=BAD_V1)),
        ('X3 带第二载体 stem_text', dict(base, stem_text='计算 1+2×3')),
        ('X4 纯图题未过审', {'blocks_json': pure, 'confidence': 95, 'kp_ids': ['001001001']}),
        ('X5 未挂考点', {'blocks_json': T_FIG, 'confidence': 95}),
        ('X6 考点挂章级', dict(base, kp_ids=['001001'])),
        ('X7 缺置信度', {'blocks_json': T_FIG, 'kp_ids': ['001001001']}),
    ]
    ok_all = True
    for name, item in legal:
        ok, res = execution_valve(item, conn)
        ok_all &= ok
        bad = [r['name'] for r in res if not r['ok']]
        rows_out.append(('闸③执行阀', name, '过', '五条全过' if ok else '❌拒于:' + ','.join(bad), ok))
    for name, item in illegal:
        ok, res = execution_valve(item, conn)
        ok_all &= (not ok)
        bad = [f"{r['no']}{r['name']}" for r in res if not r['ok']]
        rows_out.append(('闸③执行阀', name, '拒', ('拒于:' + ','.join(bad)) if not ok else '❌过了', not ok))
    return ok_all


def main():
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        conn = build_tmp_kb(tmp)
        try:
            ok1 = run_blocks(rows)
            ok2 = run_leaf(conn, rows)
            ok3 = run_valve(conn, rows)
        finally:
            conn.close()

    print('=' * 108)
    print(f'{"闸":<10}{"用例":<26}{"期望":<6}{"实际":<58}{"判"}')
    print('-' * 108)
    for gate, name, want, got, ok in rows:
        print(f'{gate:<10}{name:<26}{want:<6}{got[:56]:<58}{"√" if ok else "×"}')
    print('-' * 108)
    n_legal = sum(1 for r in rows if r[2] == '过')
    n_illegal = sum(1 for r in rows if r[2] == '拒')
    passed_legal = sum(1 for r in rows if r[2] == '过' and r[4])
    passed_illegal = sum(1 for r in rows if r[2] == '拒' and r[4])
    print(f'合法用例 {passed_legal}/{n_legal} 通过　|　非法用例 {passed_illegal}/{n_illegal} 被拒')
    green = ok1 and ok2 and ok3 and passed_legal == n_legal and passed_illegal == n_illegal
    print('结论：' + ('🟢 全绿（合法全过、非法全拒）' if green else '🔴 有用例不符，闸不成立'))
    print('=' * 108)
    return 0 if green else 1


if __name__ == '__main__':
    raise SystemExit(main())
