# -*- coding: utf-8 -*-
"""KG 建树工具（PRD-002 交付件 #1）——kp/kp_alias 的唯一写入通路。

契约（认知/数据结构.md §2.2 KG 口径定稿 2026-08-18）：
  · id 体系沿用老区：数字 id 每 3 位一层；老区册根(3位)落「年级学期」层，
    往下 单元(6位)/小节(9位)/考点(12位或15位叶)，存量硬编码 id 原值保留；
  · 「版本」层是 v2 新加的顶层分组（如 浙教版数学），id 用非 3 倍长度的可读串
    （如 zjsx2024），一眼区分于数字契约、绝不与老区 id 相撞；
  · 名字不沿用老区：干净名（编号进 ord 不进名字；叶子=名词短语≥3字；教辅栏目不占 KG 位）；
  · 别名表=翻译层：老区名/细分点名/产线词都挂 kp_alias，alias_kind 记词源；
  · UNIQUE(parent_id,name) 由 DDL 保证；叶子闸由 gates.assert_leaf_kp 保证；
  · 🔴 按需铺枝：用到哪个专项铺哪枝，没铺的单元立「未铺」占位不造空树。

用法（--db 缺省=脚本位置自解析 <v2根>/知识库/kb.db；worktree 里跑=天然沙盘）：
  python kg_tool.py build-branch 首枝-浙教七上.json     # 幂等铺枝（spec 见样例）
  python kg_tool.py add-leaf --parent 100001002 --name 数轴上的动点问题
  python kg_tool.py alias --kp 100002003003 --alias 倒数 --kind 老区名
  python kg_tool.py resolve 倒数                        # 名/别名→叶子（全路径）
  python kg_tool.py merge --from 100001003001 --into 100001003002
  python kg_tool.py show [100001]                       # 树打印
每次执行落 skill_log（skill='KG维护'）。
"""
import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import assert_leaf_kp, LeafKpError  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
LEVELS = ('版本', '年级学期', '单元', '小节', '考点')

# kp_ids_json 引用巡查清单（merge 时要迁的 JSON 数组列）
KP_JSON_COLS = [
    ('question_pattern', 'kp_ids_json'),
    ('solution_model', 'kp_ids_json'),
    ('exam_model', 'kp_ids_json'),
    ('error_cause', 'kp_ids_json'),
    ('artifact', 'kp_ids_json'),
]


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def open_db(path):
    p = Path(path)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}（先跑 工具箱/库/init_db.py）')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def log_skill(conn, action, args_digest, result, detail, t0):
    conn.execute(
        'INSERT INTO skill_log(skill, action, args_digest, result, detail, duration_ms, created_at) '
        'VALUES (?,?,?,?,?,?,?)',
        ('KG维护', action, args_digest[:200], result, detail[:500],
         int((time.time() - t0) * 1000), now()))
    conn.commit()


def digit_level(kp_id):
    """数字 id 按每 3 位推层：3位=年级学期 6位=单元 9位=小节 12/15位=考点。非数字=版本层。"""
    if not kp_id.isdigit():
        return '版本'
    return {3: '年级学期', 6: '单元', 9: '小节', 12: '考点', 15: '考点'}.get(len(kp_id))


def upsert_node(conn, nid, name, parent_id, level, ord_, status, note):
    """幂等插入：已存在且同名同父 → 跳过；已存在但不同 → 🔴 如实报错不静默改写。"""
    row = conn.execute('SELECT name, parent_id, level, status FROM kp WHERE id=?', (nid,)).fetchone()
    if row:
        if row[0] != name or (row[1] or '') != (parent_id or ''):
            raise SystemExit(
                f'🔴 id 冲突：kp {nid} 库内=({row[0]!r}, parent={row[1]!r}) '
                f'≠ spec=({name!r}, parent={parent_id!r})——同 id 两义绝不静默覆盖，人工裁决')
        if row[3] != status:
            conn.execute('UPDATE kp SET status=? WHERE id=?', (status, nid))
            return 'status'
        return 'skip'
    if level not in LEVELS:
        raise SystemExit(f'🔴 level={level!r} 不在 {LEVELS}')
    conn.execute('INSERT INTO kp(id,name,parent_id,level,ord,status,note) VALUES (?,?,?,?,?,?,?)',
                 (nid, name, parent_id, level, ord_, status, note))
    return 'new'


def add_alias(conn, kp_id, alias, kind):
    """别名幂等挂靠；alias 与目标现名相同则跳过（不造自指别名）。"""
    name = conn.execute('SELECT name FROM kp WHERE id=?', (kp_id,)).fetchone()
    if not name:
        raise SystemExit(f'🔴 加别名失败：kp {kp_id} 不存在')
    if alias == name[0]:
        return 'skip'
    cur = conn.execute('INSERT OR IGNORE INTO kp_alias(kp_id, alias, alias_kind) VALUES (?,?,?)',
                       (kp_id, alias, kind))
    return 'new' if cur.rowcount else 'skip'


# ══════════════════════════════════════════════════════════════════════
def cmd_build_branch(conn, args):
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
    stats = {'new': 0, 'skip': 0, 'status': 0, 'alias': 0}

    def bump(r):
        stats[r] = stats.get(r, 0) + 1

    ver = spec['version']
    bump(upsert_node(conn, ver['id'], ver['name'], None, '版本', ver.get('ord'),
                     ver.get('status', '现行'), json.dumps(ver.get('note'), ensure_ascii=False) if ver.get('note') else None))
    book = spec['book']
    bump(upsert_node(conn, book['id'], book['name'], ver['id'], '年级学期', book.get('ord'),
                     book.get('status', '现行'), json.dumps(book.get('note'), ensure_ascii=False) if book.get('note') else None))

    def walk(nodes, parent_id, level_idx):
        for nd in nodes:
            lv = LEVELS[level_idx]
            bump(upsert_node(conn, nd['id'], nd['name'], parent_id, lv, nd.get('ord'),
                             nd.get('status', '现行'),
                             json.dumps(nd.get('note'), ensure_ascii=False) if nd.get('note') else None))
            for al in nd.get('aliases', []):
                r = add_alias(conn, nd['id'], al['alias'], al.get('kind', '老区名'))
                if r == 'new':
                    stats['alias'] += 1
            children = nd.get('units') or nd.get('sections') or nd.get('leaves') or []
            if children:
                walk(children, nd['id'], level_idx + 1)

    walk(spec.get('units', []), book['id'], 2)
    conn.commit()
    print(f"铺枝完成：新建 {stats['new']} / 已在跳过 {stats['skip']} / 状态更新 {stats['status']} / 别名 {stats['alias']}")
    return f"spec={args.spec}", f"new={stats['new']} skip={stats['skip']} alias={stats['alias']}"


def cmd_add_leaf(conn, args):
    parent = conn.execute('SELECT id, level FROM kp WHERE id=?', (args.parent,)).fetchone()
    if not parent:
        raise SystemExit(f'🔴 父节点 {args.parent} 不存在')
    if parent[1] not in ('小节', '考点'):
        raise SystemExit(f'🔴 挂叶只挂在小节层下（父 {args.parent} level={parent[1]}）')
    if len(args.name) < 3:
        raise SystemExit(f'🔴 叶子名 {args.name!r} <3 字（短名是 resolve 毒药：老区「比」命中 87 个叶子）')
    nid = args.id
    if not nid:
        sibs = [r[0] for r in conn.execute(
            "SELECT id FROM kp WHERE parent_id=? AND length(id)=length(?)+3", (args.parent, args.parent))]
        seq = max([int(s[-3:]) for s in sibs], default=0) + 1
        nid = f'{args.parent}{seq:03d}'
    ord_ = args.ord if args.ord is not None else int(nid[-3:])
    r = upsert_node(conn, nid, args.name, args.parent, '考点', ord_, '现行', args.note)
    conn.commit()
    print(f'挂叶 {r}: {nid} {args.name}')
    return f'{nid} {args.name}', r


def cmd_alias(conn, args):
    assert_leaf_kp(conn, args.kp)          # 别名只挂叶子（产线词翻译层的落点）
    r = add_alias(conn, args.kp, args.alias, args.kind)
    conn.commit()
    print(f'别名 {r}: {args.alias} → {args.kp}')
    return f'{args.alias}->{args.kp}', r


def full_path(conn, kp_id):
    parts, cur = [], kp_id
    while cur:
        row = conn.execute('SELECT name, parent_id FROM kp WHERE id=?', (cur,)).fetchone()
        if not row:
            break
        parts.append(row[0])
        cur = row[1]
    return ' / '.join(reversed(parts))


def leaves_only(conn, ids):
    return [i for i in ids if conn.execute(
        'SELECT 1 FROM kp k WHERE k.id=? AND k.status!=? AND NOT EXISTS'
        '(SELECT 1 FROM kp c WHERE c.parent_id=k.id)', (i, '退役')).fetchone()]


def cmd_resolve(conn, args):
    q = args.word
    # ① 名字精确 → ② 别名精确 → ③ LIKE 兜底（只返回叶子，带全路径）
    hits = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name=?', (q,))]
    via = '名字精确'
    if not leaves_only(conn, hits):
        hits = [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (q,))]
        via = '别名精确'
    hits = leaves_only(conn, hits)
    if not hits:
        like = [r[0] for r in conn.execute(
            'SELECT id FROM kp WHERE name LIKE ? ORDER BY id', (f'%{q}%',))]
        like += [r[0] for r in conn.execute(
            'SELECT kp_id FROM kp_alias WHERE alias LIKE ?', (f'%{q}%',))]
        hits = leaves_only(conn, list(dict.fromkeys(like)))
        via = 'LIKE兜底'
    if not hits:
        print(f'MISS: {q!r} 零命中——挂不上就别硬挂（可 add-leaf 建叶或 alias 补翻译）')
        return q, 'MISS', 2
    for h in hits:
        print(f'{h}\t{full_path(conn, h)}\t[{via}]')
    if len(hits) > 1:
        print(f'⚠️ 多命中 {len(hits)} 个：不自动挑，人工/调用方选（exit 3）')
        return q, f'多命中x{len(hits)}', 3
    return q, f'命中 {hits[0]}', 0


def cmd_merge(conn, args):
    src, dst = args.src, args.dst
    if src == dst:
        raise SystemExit('🔴 from=into')
    assert_leaf_kp(conn, dst)
    srow = conn.execute('SELECT name, status FROM kp WHERE id=?', (src,)).fetchone()
    if not srow:
        raise SystemExit(f'🔴 merge：源 {src} 不存在')
    nkids = conn.execute('SELECT COUNT(*) FROM kp WHERE parent_id=?', (src,)).fetchone()[0]
    if nkids:
        raise SystemExit(f'🔴 merge：源 {src} 有 {nkids} 个子节点——只并叶子，整枝重组先人工拆')
    moved = {'question_kp': 0, 'alias': 0, 'json': 0, 'err_code_map': 0, 'cause_deposit': 0}

    # question_kp：搬行；两边都挂了同一题 → 删源行（不重复）；is_primary 冲突交 UNIQUE 索引兜
    for qid, is_p, anchor in conn.execute(
            'SELECT question_id, is_primary, anchor_json FROM question_kp WHERE kp_id=?', (src,)).fetchall():
        dup = conn.execute('SELECT 1 FROM question_kp WHERE question_id=? AND kp_id=?', (qid, dst)).fetchone()
        if dup:
            conn.execute('DELETE FROM question_kp WHERE question_id=? AND kp_id=?', (qid, src))
        else:
            has_primary = conn.execute(
                'SELECT 1 FROM question_kp WHERE question_id=? AND is_primary=1 AND kp_id!=?',
                (qid, src)).fetchone()
            conn.execute('UPDATE question_kp SET kp_id=?, is_primary=? WHERE question_id=? AND kp_id=?',
                         (dst, 0 if (is_p and has_primary) else is_p, qid, src))
        moved['question_kp'] += 1

    # 别名整体搬家 + 源名字转为目标的别名
    for al, kind in conn.execute('SELECT alias, alias_kind FROM kp_alias WHERE kp_id=?', (src,)).fetchall():
        conn.execute('DELETE FROM kp_alias WHERE kp_id=? AND alias=?', (src, al))
        if add_alias(conn, dst, al, kind) == 'new':
            moved['alias'] += 1
    if add_alias(conn, dst, srow[0], '并叶前源名') == 'new':
        moved['alias'] += 1

    # kp_ids_json 引用迁移
    for tab, col in KP_JSON_COLS:
        for rid, raw in conn.execute(f'SELECT id, {col} FROM {tab} WHERE {col} LIKE ?', (f'%{src}%',)).fetchall():
            ids = json.loads(raw)
            if src in ids:
                ids = [dst if i == src else i for i in ids]
                ids = list(dict.fromkeys(ids))
                conn.execute(f'UPDATE {tab} SET {col}=? WHERE id=?', (json.dumps(ids, ensure_ascii=False), rid))
                moved['json'] += 1

    # err_code_map：作用域搬家；目标已有同码不同义 → 🔴 拒绝（同键不静默覆盖）
    for code, cause in conn.execute('SELECT code, cause_id FROM err_code_map WHERE kp_id=?', (src,)).fetchall():
        clash = conn.execute('SELECT cause_id FROM err_code_map WHERE kp_id=? AND code=?', (dst, code)).fetchone()
        if clash and clash[0] != cause:
            raise SystemExit(f'🔴 merge 中止：错因码 {code!r} 在 {dst} 已映射 {clash[0]}≠{cause}（同码两义，人工裁决）')
        conn.execute('DELETE FROM err_code_map WHERE kp_id=? AND code=?', (src, code))
        if not clash:
            conn.execute('INSERT INTO err_code_map(kp_id, code, cause_id) VALUES (?,?,?)', (dst, code, cause))
        moved['err_code_map'] += 1

    n = conn.execute('UPDATE cause_deposit SET kp_id=? WHERE kp_id=?', (dst, src)).rowcount
    moved['cause_deposit'] = n

    conn.execute('UPDATE kp SET status=?, note=? WHERE id=?',
                 ('退役', f'并入 {dst}（{now()}）', src))
    conn.commit()
    print(f'并叶完成 {src} → {dst}：{moved}')
    return f'{src}->{dst}', json.dumps(moved, ensure_ascii=False)


def cmd_show(conn, args):
    root_filter = args.id
    rows = conn.execute('SELECT id, name, parent_id, level, ord, status FROM kp ORDER BY id').fetchall()
    kids = {}
    for r in rows:
        kids.setdefault(r[2], []).append(r)
    by_id = {r[0]: r for r in rows}

    def rec(node, depth):
        mark = {'现行': '', '未铺': ' ⬜未铺', '退役': ' ✖退役'}[node[5]]
        nal = conn.execute('SELECT COUNT(*) FROM kp_alias WHERE kp_id=?', (node[0],)).fetchone()[0]
        al = f' (别名{nal})' if nal else ''
        print('  ' * depth + f'{node[0]} {node[1]}{mark}{al}')
        for c in sorted(kids.get(node[0], []), key=lambda x: (x[4] or 0, x[0])):
            rec(c, depth + 1)

    starts = [by_id[root_filter]] if root_filter and root_filter in by_id else \
        sorted(kids.get(None, []), key=lambda x: (x[4] or 0, x[0]))
    for s in starts:
        rec(s, 0)
    total = len(rows)
    leaves = sum(1 for r in rows if r[0] not in kids and r[5] != '退役')
    print(f'—— 共 {total} 节点 / {leaves} 现行叶子')
    return root_filter or 'all', f'{total}节点/{leaves}叶'


def main():
    ap = argparse.ArgumentParser(description='KG 建树工具（kp/kp_alias 唯一写入通路）')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('build-branch'); s.add_argument('spec')
    s = sub.add_parser('add-leaf')
    s.add_argument('--parent', required=True); s.add_argument('--name', required=True)
    s.add_argument('--id'); s.add_argument('--ord', type=int); s.add_argument('--note')
    s = sub.add_parser('alias')
    s.add_argument('--kp', required=True); s.add_argument('--alias', required=True)
    s.add_argument('--kind', default='产线词')
    s = sub.add_parser('resolve'); s.add_argument('word'); s.add_argument('--all', action='store_true')
    s = sub.add_parser('merge')
    s.add_argument('--from', dest='src', required=True); s.add_argument('--into', dest='dst', required=True)
    s = sub.add_parser('show'); s.add_argument('id', nargs='?')
    args = ap.parse_args()

    t0 = time.time()
    conn = open_db(args.db)
    code = 0
    try:
        fn = {'build-branch': cmd_build_branch, 'add-leaf': cmd_add_leaf, 'alias': cmd_alias,
              'resolve': cmd_resolve, 'merge': cmd_merge, 'show': cmd_show}[args.cmd]
        out = fn(conn, args)
        digest, detail = out[0], out[1]
        code = out[2] if len(out) > 2 else 0
        log_skill(conn, args.cmd, digest, '成功' if code == 0 else '失败', detail, t0)
    except (SystemExit, LeafKpError) as e:
        msg = str(e)
        if msg and msg not in ('0', ''):
            print(msg if isinstance(e, LeafKpError) else msg, file=sys.stderr)
            try:
                log_skill(conn, args.cmd, str(vars(args))[:200], '失败', msg, t0)
            except Exception:
                pass
            code = 1
    finally:
        conn.close()
    sys.exit(code)


if __name__ == '__main__':
    main()
