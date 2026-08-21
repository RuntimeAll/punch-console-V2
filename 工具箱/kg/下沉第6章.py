# -*- coding: utf-8 -*-
"""第6章「图形的初步知识」题目下沉题型层（窗L · 2026-08-21 · 只此一章的试刀）。

干什么：把挂在 100006% 考点叶上的题，按 question.prov_json 的「讲+题型」→ 题型锚定映射件 →
题型名 → 该名的题型节点，把 question_kp.kp_id 从考点叶改挂到题型节点。
is_primary / anchor_json 保留，anchor_json 里追加 {"下沉":"窗L","from":"<旧考点id>"}。

🔴 范围死锁定：只动 kp_id LIKE '100006%' 的挂载行（脚本内断言），其余章一行不许碰——
   靠「非 100006 行整体哈希前后一致」自证，不靠注释。
🔴 沉不动的一律留在考点层不动并逐题写明原因（就近可挂保证旧挂载永远合法，留着不算错）：
   无题型标注 / 映射件无此键 / 题型未锚定 / 题型名与父叶同名（冗余没建节点）/ 跨叶（默认不动）。
🔴 跨叶：题现挂 A 叶、但该题型节点建在 B 叶下（如 讲20题型8「线段、射线条数的规律探究」
   题在「线段的基本性质」、节点按调度中心裁定落在「射线的概念」下）——这不是下沉是改属，
   默认 **不动**、如实计数；确认要改属再加 --allow-cross-leaf。

用法（🔴 必须显式点名库）：
    python 工具箱\\kg\\下沉第6章.py --db 试验场\\2026-08-21-七上发布闭环\\窗L沙盘.db --dry-run
    python 工具箱\\kg\\下沉第6章.py --db 试验场\\2026-08-21-七上发布闭环\\窗L沙盘.db
前置：先跑 apply_ddl_窗L题型层.py 和 铺题型枝.py。
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import assert_leaf_kp, LeafKpError  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_MAP = HERE / '题型锚定映射.json'
SCOPE = '100006%'          # 第6章 图形的初步知识


def qkp_hash(conn, where, params=()):
    h = hashlib.sha256()
    for r in conn.execute(
            'SELECT question_id, kp_id, is_primary, IFNULL(anchor_json, "␀") FROM question_kp '
            f'WHERE {where} ORDER BY question_id, kp_id', params):
        h.update(('␟'.join(map(str, r)) + '\n').encode('utf-8'))
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='第6章题目下沉题型层')
    ap.add_argument('--db', required=True)
    ap.add_argument('--map', default=str(DEFAULT_MAP))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-cross-leaf', action='store_true',
                    help='允许跨叶改属（默认不动，只计数）')
    args = ap.parse_args()
    if not os.path.exists(args.db):
        sys.exit(f'🔴 库不存在：{args.db}')
    raw = json.loads(Path(args.map).read_text(encoding='utf-8'))

    conn = sqlite3.connect(args.db)
    conn.execute('PRAGMA foreign_keys=ON')
    t0 = time.time()
    fails = []

    def chk(name, got, want):
        ok = got == want
        print(f'[{"PASS" if ok else "FAIL"}] {name}: 实际={got} 期望={want}')
        if not ok:
            fails.append(name)

    try:
        # ── 基线 ──────────────────────────────────────────────────────
        n_all0 = conn.execute('SELECT COUNT(*) FROM question_kp').fetchone()[0]
        h_out0 = qkp_hash(conn, "kp_id NOT LIKE ?", (SCOPE,))
        n_out0 = conn.execute('SELECT COUNT(*) FROM question_kp WHERE kp_id NOT LIKE ?', (SCOPE,)).fetchone()[0]
        cnt0 = {r[0]: r[1] for r in conn.execute(
            'SELECT question_id, COUNT(*) FROM question_kp GROUP BY question_id')}
        rows = conn.execute(
            'SELECT k.question_id, k.kp_id, k.is_primary, k.anchor_json, q.prov_json '
            'FROM question_kp k JOIN question q ON q.id = k.question_id '
            'WHERE k.kp_id LIKE ? ORDER BY k.kp_id, k.question_id', (SCOPE,)).fetchall()
        print(f'库：{args.db}{"（DRY-RUN 未写）" if args.dry_run else ""}')
        print(f'基线：question_kp 全库 {n_all0} 行；第6章（{SCOPE}）{len(rows)} 行；'
              f'其余章 {n_out0} 行 哈希={h_out0[:16]}…')
        if not rows:
            sys.exit('🔴 第6章零行——库不对，红停')

        # 题型节点索引：name → [(id, parent_id)]
        by_name = {}
        for nid, nm, pid in conn.execute(
                "SELECT id, name, parent_id FROM kp WHERE level='题型' AND status='现行'"):
            by_name.setdefault(nm, []).append((nid, pid))
        kpname = {r[0]: r[1] for r in conn.execute('SELECT id, name FROM kp')}
        kplevel = {r[0]: r[1] for r in conn.execute('SELECT id, level FROM kp')}
        n_on_pat0 = conn.execute(
            "SELECT COUNT(*) FROM question_kp k JOIN kp ON kp.id=k.kp_id WHERE kp.level='题型'").fetchone()[0]
        if not by_name:
            sys.exit('🔴 库里一个题型节点都没有——先跑 铺题型枝.py')

        # ── 逐题判定 ──────────────────────────────────────────────────
        moves, holds = [], []
        for qid, kid, isp, anchor, prov in rows:
            if not kid.startswith('100006'):                 # 范围断言（双保险）
                sys.exit(f'🔴 越界：{qid} 挂在 {kid}，不在第6章——红停')
            if kplevel.get(kid) == '题型':                   # 幂等：重跑不再动已下沉的行
                holds.append((qid, kid, '已在题型层（幂等跳过）', kpname.get(kid, '')))
                continue
            p = json.loads(prov) if prov else {}
            jiang, tx = p.get('讲'), p.get('题型')
            if not jiang or not tx:
                holds.append((qid, kid, '无题型标注（prov 缺 讲/题型）', f'讲={jiang} 题型={tx}'))
                continue
            key = f'讲{jiang}题型{tx}'
            hit = raw.get(key)
            if hit is None:
                holds.append((qid, kid, '映射件无此键', key))
                continue
            name = hit['题型名']
            if name == kpname.get(kid):
                holds.append((qid, kid, '题型名与父叶同名（冗余未建节点）', f'{key}→{name}'))
                continue
            cands = by_name.get(name, [])
            if not cands:
                holds.append((qid, kid, '题型未锚定/无对应节点', f'{key}→{name}'))
                continue
            if len(cands) > 1:
                holds.append((qid, kid, '题型名多处命中（不自动挑）', f'{key}→{name}:{cands}'))
                continue
            tid, tparent = cands[0]
            if tparent != kid:
                if not args.allow_cross_leaf:
                    holds.append((qid, kid, '跨叶改属（默认不动，需 --allow-cross-leaf）',
                                  f'{key}→{name} 节点 {tid} 在 {tparent}（{kpname.get(tparent)}）下'))
                    continue
            if conn.execute('SELECT 1 FROM question_kp WHERE question_id=? AND kp_id=?',
                            (qid, tid)).fetchone():
                holds.append((qid, kid, '该题已挂目标题型（避免撞主键）', f'{key}→{tid}'))
                continue
            try:
                assert_leaf_kp(conn, tid)                    # 目标必须过就近可挂闸
            except LeafKpError as e:
                holds.append((qid, kid, '目标节点过不了叶子闸', str(e)[:80]))
                continue
            moves.append((qid, kid, tid, name, key, isp, anchor, tparent != kid))

        # ── 落库 ──────────────────────────────────────────────────────
        for qid, kid, tid, name, key, isp, anchor, cross in moves:
            try:
                a = json.loads(anchor) if anchor else {}
                if not isinstance(a, dict):
                    a = {'原值': a}
            except (ValueError, TypeError):
                a = {'原值': anchor}
            a['下沉'] = '窗L'
            a['from'] = kid
            if cross:
                a['跨叶改属'] = f'{kid}→{tid}（低置信·人审）'
            if not args.dry_run:
                conn.execute('UPDATE question_kp SET kp_id=?, anchor_json=? '
                             'WHERE question_id=? AND kp_id=?',
                             (tid, json.dumps(a, ensure_ascii=False), qid, kid))
        if not args.dry_run and moves:
            try:
                conn.execute(
                    'INSERT INTO skill_log(skill, action, args_digest, result, detail, duration_ms, created_at) '
                    'VALUES (?,?,?,?,?,?,?)',
                    ('KG维护', '下沉第6章', f'db={os.path.basename(args.db)}', '成功',
                     f'下沉 {len(moves)} 题 / 留考点层 {len(holds)} 题',
                     int((time.time() - t0) * 1000), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            except sqlite3.Error as e:
                print(f'⚠️ skill_log 落账失败（不挡主流程）：{e}')
            conn.commit()

        # ── 清单 ──────────────────────────────────────────────────────
        print(f'\n—— 下沉 {len(moves)} 题 ——')
        for qid, kid, tid, name, key, _isp, _a, cross in moves:
            print(f'{qid}  {kid}（{kpname[kid]}） → {tid}（{name}）  [{key}]' + ('  ⚠️跨叶' if cross else ''))
        print(f'\n—— 留考点层 {len(holds)} 题（逐题原因）——')
        for qid, kid, why, det in holds:
            print(f'{qid}  {kid}（{kpname[kid]}）  {why}：{det}')
        print('\n留层原因汇总：', dict(Counter(w for _q, _k, w, _d in holds)))

        # ── 守恒 ──────────────────────────────────────────────────────
        print('\n—— 守恒对账 ——')
        chk('第6章题数守恒（下沉+留层=基线）', len(moves) + len(holds), len(rows))
        chk('question_kp 总行数不变', conn.execute('SELECT COUNT(*) FROM question_kp').fetchone()[0], n_all0)
        chk('非第6章行数不变', conn.execute(
            'SELECT COUNT(*) FROM question_kp WHERE kp_id NOT LIKE ?', (SCOPE,)).fetchone()[0], n_out0)
        chk('非第6章逐行哈希不变', qkp_hash(conn, "kp_id NOT LIKE ?", (SCOPE,)), h_out0)
        cnt1 = {r[0]: r[1] for r in conn.execute(
            'SELECT question_id, COUNT(*) FROM question_kp GROUP BY question_id')}
        diff = [(q, cnt0.get(q), cnt1.get(q)) for q in set(cnt0) | set(cnt1) if cnt0.get(q) != cnt1.get(q)]
        chk(f'每题挂载数逐题不变（{len(cnt1)} 题，列差异）', diff, [])
        chk('第6章行数不变（题型 id 仍在 100006 前缀内）', conn.execute(
            'SELECT COUNT(*) FROM question_kp WHERE kp_id LIKE ?', (SCOPE,)).fetchone()[0], len(rows))
        n_on_pat = conn.execute(
            "SELECT COUNT(*) FROM question_kp k JOIN kp ON kp.id=k.kp_id WHERE kp.level='题型'").fetchone()[0]
        chk('挂在题型层的行数', n_on_pat, n_on_pat0 + (0 if args.dry_run else len(moves)))
        fk = conn.execute('PRAGMA foreign_key_check').fetchall()
        chk('外键零违例', fk, [])
        print('\n=== ' + ('全绿' if not fails else f'🔴 {len(fails)} 条 FAIL：{fails}') + ' ===')
        sys.exit(1 if fails else 0)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
