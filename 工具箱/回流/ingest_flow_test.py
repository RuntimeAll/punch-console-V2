# -*- coding: utf-8 -*-
"""D-21 等级审矩阵 + 工单原语 端到端自证（沙盘库，绝不碰主位两库）。

    python 工具箱\\回流\\ingest_flow_test.py [--verbose]

判绿口径照 gates_test：**合法全过 + 非法全拒**（任一条不符即退出码 1）。
覆盖：
  等级矩阵  纯文本/单图/两图/含表/超长多图 × 文字层源(manual) 与拍照源(scan，+1 级、封顶 L3)
  工单行为  L0/L1 不开工单；L2/L3 自动开图审工单；--skip-review 显式跳过则不开（报告大字标明）
  闸④串联  挂待处理工单 ⇒ promote 被拦；ticket-done 结掉工单 ⇒ promote 通过
  留痕纪律  已处理的工单不许再改（第二次 ticket-done 必须被拒）
"""
import argparse
import io
import json
import sqlite3
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
LIB = HERE.parent / '库'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LIB))

import ingest_flow as F                              # noqa: E402
from init_db import SEED                             # noqa: E402

SCHEMA = LIB / 'schema_kb.sql'
# 1×1 透明 PNG（沙盘资产实体：图指针闸要文件真在盘上）
PNG_1PX = bytes.fromhex(
    '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4'
    '890000000a49444154789c6360000002000100ffff03000006000557bfabd400'
    '00000049454e44ae426082')


# ── 沙盘库：真 DDL + 真 seed + 一小截首枝 ──────────────────────────────
def build_sandbox(tmpdir):
    db = Path(tmpdir) / 'kb_sandbox.db'
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA.read_text(encoding='utf-8'))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executemany(
        'INSERT INTO dict_item(domain,code,label,ord,status) VALUES (?,?,?,?,?)',
        [(d, c, lab, o, '在用') for d, rows in SEED.items() for c, lab, o in rows])
    conn.executemany(
        'INSERT INTO kp(id,name,parent_id,level,ord,status) VALUES (?,?,?,?,?,?)',
        [('001', '人教七上', None, '版本', 1, '现行'),
         ('001001', '有理数', '001', '单元', 1, '现行'),
         ('001001001', '有理数混合运算', '001001', '考点', 1, '现行')])
    # 🔴 2026-08-20 起 figure 悬空指针闸（X7）要求「asset 表有行 + 文件真在盘」：
    #    沙盘落真行 + 在 tmpdir 里落真 PNG 文件（root=tmpdir，绝不碰主位 知识库/资产/）。
    conn.executemany(
        'INSERT INTO asset(hash,kind,rel_path,meta_json,created_at) VALUES (?,?,?,?,?)',
        [(h, 'figure', f'知识库/资产/{h}.png', None, '2026-08-19')
         for h in ('fa01', 'fa02', 'fa03', 'fa04', 'fa05', 'fa06', 'fa07', 'fa08')])
    adir = Path(tmpdir) / '知识库' / '资产'
    adir.mkdir(parents=True, exist_ok=True)
    for h in ('fa01', 'fa02', 'fa03', 'fa04', 'fa05', 'fa06', 'fa07', 'fa08'):
        (adir / f'{h}.png').write_bytes(PNG_1PX)
    conn.commit()
    return conn


# ── 题面积木 ──────────────────────────────────────────────────────────
def txt(md):
    return {'type': 'text', 'role': '题面', 'md': md}


def fig(h, w='48%'):
    return {'type': 'figure', 'asset': h, 'width': w}


def blocks(*cells_rows):
    return {'v': 2, 'rows': [{'cells': list(c)} for c in cells_rows]}


LONG = ('某工厂三个车间在四个季度的产量与成本数据如下所述，甲车间每季度产量稳定增长，'
        '乙车间受设备检修影响第二季度产量下滑，丙车间在第四季度引入新生产线后产量翻番。') * 9  # >600 字

TABLE_MD = '| 月份 | 产量 |\n|---|---|\n| 1 | 20 |\n| 2 | 35 |'


def item(qid, stem, src='manual', text_extra=''):
    return {
        'id': qid, 'blocks': stem, 'qtype': '计算题', 'difficulty': '巩固',
        'source_kind': src, 'source_raw': '沙盘用例' + text_extra,
        'kp': ['001001001'], 'primary_kp': '001001001', 'confidence': 95,
    }


# 用例表：(编号, 说明, qid, 题面, 源, --skip-review, 期望等级, 期望待处理工单数)
CASES = [
    ('L0', '纯文本·manual', 'qT_a', blocks([txt('计算 $(-2)^3+5\\times(-3)$ 的值。')]),
     'manual', False, 'L0·直入', 0),
    ('L1', '单图·manual', 'qT_b', blocks([txt('如图，梯形 ABCD 中求阴影面积。')], [fig('fa01')]),
     'manual', False, 'L1·抽检', 0),
    ('L2', '两图·manual', 'qT_c',
     blocks([txt('如图甲、图乙，比较两种拼法的周长。')], [fig('fa02'), fig('fa03')]),
     'manual', False, 'L2·速审', 1),
    ('L3', '含表格块·manual', 'qT_d',
     blocks([txt('根据下表回答本月产量问题。')], [{'type': 'table', 'md': TABLE_MD}]),
     'manual', False, 'L2·速审', 1),
    ('L4', '超长+两图·manual', 'qT_e',
     blocks([txt(LONG)], [fig('fa04'), fig('fa05')]), 'manual', False, 'L3·细审', 1),
    ('L5', '纯文本·scan(+1)', 'qT_f', blocks([txt('化简：$|{-}3|+|2-5|$，并说明依据。')]),
     'scan', False, 'L1·抽检', 0),
    ('L6', '单图·scan(+1)', 'qT_g', blocks([txt('观察下图折线的变化趋势并作答。')], [fig('fa06')]),
     'scan', False, 'L2·速审', 1),
    ('L7', '两图·scan(+1封顶)', 'qT_h',
     blocks([txt('下面两幅统计图来自同一次调查，回答问题。')], [fig('fa07'), fig('fa08')]),
     'scan', False, 'L3·细审', 1),
    ('L8', '两图·manual·--skip-review', 'qT_i',
     blocks([txt('如图 1 与图 2 所示，求两图形面积之差。')], [fig('fa02'), fig('fa03')]),
     'manual', True, 'L2·速审', 0),
]


def run_pack(conn, tmpdir, it, skip_review):
    pack = Path(tmpdir) / f'pack_{it["id"]}.json'
    pack.write_text(json.dumps({'source_line': '沙盘', 'items': [it]}, ensure_ascii=False),
                    encoding='utf-8')
    # no_vec=True：本套自证的是 D-21 等级审与工单，跟语意向量无关；开着的话每条用例都要
    # 冷载一次 bge（十几秒 × 十几条），把一套 1 秒的测试拖成几分钟。
    # 🔴 入库收尾增量向量的正主自证在 工具箱/检索/serve_test.py（走 serve / 冷载 / 都不在 三态全测）。
    args = argparse.Namespace(pack=str(pack), partial=False, allow_dup=False,
                              skip_review=skip_review, no_vec=True, serve_port=None,
                              root=str(tmpdir))    # 沙盘副本资产树（figure 悬空闸的解析根）
    buf = io.StringIO()
    with redirect_stdout(buf):
        _, _, code = F.cmd_ingest(conn, args, dry=False)
    return code, buf.getvalue()


def q_status(conn, qid):
    row = conn.execute('SELECT status FROM question WHERE id=?', (qid,)).fetchone()
    return row[0] if row else None


def n_open(conn, qid):
    return conn.execute(
        "SELECT COUNT(*) FROM review_ticket WHERE ref=? AND status='待处理'", (qid,)).fetchone()[0]


def run_matrix(conn, tmpdir, out, log):
    ok_all = True
    for no, desc, qid, stem, src, skip, want_lv, want_tk in CASES:
        it = item(qid, stem, src)
        code, text = run_pack(conn, tmpdir, it, skip)
        log.append(f'--- {no} {desc} ---\n{text}')
        got_lv = next((lv for lv in F.LEVEL_NAME.values()
                       if any(qid in ln and lv in ln for ln in text.splitlines())), '（未打印）')
        got_tk = n_open(conn, qid)
        got_st = q_status(conn, qid)
        ok = (code == 0 and got_lv == want_lv and got_tk == want_tk and got_st == '草稿')
        ok_all &= ok
        out.append(('等级审', f'{no} {desc}', f'{want_lv}/工单{want_tk}',
                    f'{got_lv}/工单{got_tk}/状态{got_st}', ok))
    # 反证：--skip-review 那题（L8）与不跳过的同型题（L2）等级相同、工单一有一无
    ok = (n_open(conn, 'qT_c') == 1 and n_open(conn, 'qT_i') == 0)
    ok_all &= ok
    out.append(('等级审', 'L9 跳过审核只免工单不改等级', 'L2 有单 / L8 无单',
                f'qT_c={n_open(conn, "qT_c")} qT_i={n_open(conn, "qT_i")}', ok))
    return ok_all


def run_promote_chain(conn, out, log):
    ok_all = True

    def promote(qid):
        buf = io.StringIO()
        with redirect_stdout(buf):
            _, _, code = F.cmd_promote(conn, argparse.Namespace(ids=qid, match=None))
        log.append(f'--- promote {qid} ---\n{buf.getvalue()}')
        return code, buf.getvalue()

    def ticket_done(tid, note=None, reject=False):
        buf = io.StringIO()
        with redirect_stdout(buf):
            _, _, code = F.cmd_ticket_done(
                conn, argparse.Namespace(id=tid, note=note, reject=reject))
        log.append(f'--- ticket-done #{tid} ---\n{buf.getvalue()}')
        return code, buf.getvalue()

    # P1 L0 题无工单 → 直接可上架
    code, _ = promote('qT_a')
    ok = (code == 0 and q_status(conn, 'qT_a') == '上架')
    ok_all &= ok
    out.append(('闸④串联', 'P1 L0 无工单 promote', '过·上架',
                f'code={code}/状态{q_status(conn, "qT_a")}', ok))

    # P2 L2 题挂待处理工单 → promote 必须被拦，状态原地不动
    code, _ = promote('qT_c')
    ok = (code == 1 and q_status(conn, 'qT_c') == '草稿')
    ok_all &= ok
    out.append(('闸④串联', 'P2 挂待处理工单 promote', '拒·仍草稿',
                f'code={code}/状态{q_status(conn, "qT_c")}', ok))

    # P3 tickets 列得出这张单
    buf = io.StringIO()
    with redirect_stdout(buf):
        _, _, code = F.cmd_tickets(conn, argparse.Namespace(status='待处理'))
    log.append('--- tickets --status 待处理 ---\n' + buf.getvalue())
    tid = conn.execute(
        "SELECT id FROM review_ticket WHERE ref='qT_c' AND status='待处理'").fetchone()[0]
    ok = (code == 0 and 'qT_c' in buf.getvalue() and 'L2·速审' in buf.getvalue())
    ok_all &= ok
    out.append(('工单原语', 'P3 tickets 列待处理', '含 qT_c 与等级原因',
                ('列到 #%d 且带等级原因' % tid) if ok else '❌没列全', ok))

    # P4 ticket-done 结掉 → 待处理→已处理，done_at 落时间
    code, _ = ticket_done(tid, note='图已核对，两图完整')
    row = conn.execute('SELECT status,done_at,note FROM review_ticket WHERE id=?', (tid,)).fetchone()
    ok = (code == 0 and row[0] == '已处理' and row[1] and '图已核对' in row[2] and 'L2·速审' in row[2])
    ok_all &= ok
    out.append(('工单原语', 'P4 ticket-done 处理', '已处理·有 done_at·结论追加',
                f'{row[0]}/done_at={"有" if row[1] else "无"}/note保留机械判定', ok))

    # P5 工单结掉后 promote 通过
    code, _ = promote('qT_c')
    ok = (code == 0 and q_status(conn, 'qT_c') == '上架')
    ok_all &= ok
    out.append(('闸④串联', 'P5 结单后 promote', '过·上架',
                f'code={code}/状态{q_status(conn, "qT_c")}', ok))

    # P6 🔴 已处理的工单不许再改
    code, text = ticket_done(tid, note='想反悔')
    row2 = conn.execute('SELECT status,note FROM review_ticket WHERE id=?', (tid,)).fetchone()
    ok = (code == 1 and row2[0] == '已处理' and '想反悔' not in (row2[1] or ''))
    ok_all &= ok
    out.append(('工单原语', 'P6 已处理工单再改', '拒·库里一字不动',
                f'code={code}/status={row2[0]}/note未被改={"是" if ok else "否"}', ok))

    # P7 驳回路径：L3 题的工单驳回后同样放行上架（驳回=已结，不是待处理）
    tid3 = conn.execute(
        "SELECT id FROM review_ticket WHERE ref='qT_e' AND status='待处理'").fetchone()[0]
    code, _ = ticket_done(tid3, note='图缺失，打回重录', reject=True)
    st = conn.execute('SELECT status FROM review_ticket WHERE id=?', (tid3,)).fetchone()[0]
    ok = (code == 0 and st == '已驳回')
    ok_all &= ok
    out.append(('工单原语', 'P7 ticket-done --reject', '已驳回', f'code={code}/{st}', ok))

    # P8 不存在的工单
    code, _ = ticket_done(999999)
    ok = (code == 1)
    ok_all &= ok
    out.append(('工单原语', 'P8 ticket-done 不存在的 id', '拒', f'code={code}', ok))

    # P9 --skip-review 那题没工单 ⇒ 闸④不拦（跳过的代价如实体现，不假装拦住）
    code, _ = promote('qT_i')
    ok = (code == 0 and q_status(conn, 'qT_i') == '上架')
    ok_all &= ok
    out.append(('闸④串联', 'P9 跳过审核的 L2 直接上架', '过（代价如实）',
                f'code={code}/状态{q_status(conn, "qT_i")}', ok))
    return ok_all


def main():
    ap = argparse.ArgumentParser(description='D-21 等级审 + 工单原语 端到端自证')
    ap.add_argument('--verbose', action='store_true', help='附打各步原始输出全文')
    a = ap.parse_args()

    out, log = [], []
    with tempfile.TemporaryDirectory() as tmp:
        conn = build_sandbox(tmp)
        try:
            ok1 = run_matrix(conn, tmp, out, log)
            ok2 = run_promote_chain(conn, out, log)
        finally:
            conn.close()

    if a.verbose:
        print('\n'.join(log))
    print('=' * 112)
    print(f'{"环节":<10}{"用例":<32}{"期望":<24}{"实际":<40}{"判"}')
    print('-' * 112)
    for seg, name, want, got, ok in out:
        print(f'{seg:<10}{name:<32}{want:<24}{got[:38]:<40}{"√" if ok else "×"}')
    print('-' * 112)
    n_ok = sum(1 for r in out if r[4])
    print(f'用例 {n_ok}/{len(out)} 符合预期')
    green = ok1 and ok2 and n_ok == len(out)
    print('结论：' + ('🟢 全绿（等级判定逐题对表、工单该开的开该拦的拦）'
                     if green else '🔴 有用例不符，等级审不成立'))
    print('=' * 112)
    return 0 if green else 1


if __name__ == '__main__':
    raise SystemExit(main())
