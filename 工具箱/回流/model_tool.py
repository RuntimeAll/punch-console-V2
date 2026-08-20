# -*- coding: utf-8 -*-
"""模型留档工具（PRD-002 交付件 #2 配套）——solution_model / exam_model 的唯一写入通路。

飞轮铁律落点：
  ②模型必留档：母题定性→solution_model（触发→动作+tier/freq）；DSL 出题路径→exam_model
    （dsl_ref 指向 工具箱/dsl/ 或册 _源/ 的相对路径——每个考点都能持续再出题）；
  ③出题前必查库：coverage 一条命令对账（这个考点已有几题/几模型）。

用法：
  python model_tool.py solution-add --name 绝对值双开定号 --kp 绝对值的性质 --kp 与绝对值有关的计算 \
      --trigger "看到 |a|+|b| 且给出 a,b 符号" --action "按符号脱号→合并同类项" --tier 2 --freq 3
  python model_tool.py exam-add --name 有理数混合运算·三步带括号 --kp 有理数混合运算 \
      --dsl-ref 工具箱/dsl/有理数混合运算.py --params '{"steps":3,"paren":1,"tier":[1,3]}'
  python model_tool.py coverage --kp 有理数混合运算
  python model_tool.py list solution / list exam
"""
import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import assert_leaf_kp, LeafKpError  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def open_db(path):
    import sqlite3
    p = Path(path)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def log_skill(conn, action, digest, result, detail, t0):
    conn.execute(
        'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) VALUES (?,?,?,?,?,?,?)',
        ('模型留档', action, str(digest)[:200], result, str(detail)[:500],
         int((time.time() - t0) * 1000), now()))
    conn.commit()


def resolve_kp_words(conn, words, allow_node=False):
    """词表→kp id 表；任何一个 resolve 不出就整体失败（模型锚点不许猜）。
    allow_node=True（2026-08-21 用户令「模型挂靠不固定层级」）：模型可挂叶/节/章任意**存在的**节点
    ——叶子闸的本意是防题挂章级坏学情分母，模型不进学情分母；题挂载通路（ingest）不走本函数，闸不动。"""
    ids = []
    for w in words:
        w = str(w)
        if re.fullmatch(r'\d{6,15}', w):
            if allow_node:
                if not conn.execute('SELECT 1 FROM kp WHERE id=?', (w,)).fetchone():
                    sys.exit(f'🔴 挂靠节点 {w} 在 kp 表不存在——层级随意≠id 随意')
            else:
                assert_leaf_kp(conn, w)
            ids.append(w)
            continue
        hits = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name=?', (w,))]
        if not hits:
            hits = [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (w,))]
        if allow_node:
            ok = list(dict.fromkeys(h for h in hits
                                    if conn.execute('SELECT 1 FROM kp WHERE id=?', (h,)).fetchone()))
        else:
            ok = []
            for h in dict.fromkeys(hits):
                try:
                    assert_leaf_kp(conn, h)
                    ok.append(h)
                except LeafKpError:
                    pass
        if len(ok) != 1:
            sys.exit(f'🔴 考点 {w!r} resolve 命中 {len(ok)} 个（要恰一）：{ok}——写 id 消歧或先补 KG')
        ids.append(ok[0])
    return list(dict.fromkeys(ids))


def cmd_solution_add(conn, args):
    kp_ids = resolve_kp_words(conn, args.kp, allow_node=True)
    mid = args.id or 'SM' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
    dup = conn.execute('SELECT id FROM solution_model WHERE name=? AND status=?',
                       (args.name, '在用')).fetchone()
    if dup and not args.id:
        sys.exit(f'🔴 已有在用同名解题模型 {dup[0]}（{args.name}）——先查库再留档，别重复蒸馏')
    conn.execute(
        'INSERT INTO solution_model(id,name,kp_ids_json,trigger_feature,action_conclusion,tier,freq,status) '
        'VALUES (?,?,?,?,?,?,?,?)',
        (mid, args.name, json.dumps(kp_ids, ensure_ascii=False),
         args.trigger, args.action, args.tier, args.freq, '在用'))
    conn.commit()
    print(f'solution_model 留档：{mid} {args.name} → 考点 {kp_ids} tier={args.tier} freq={args.freq}')
    return mid, f'{args.name} kp={kp_ids}'


def cmd_exam_add(conn, args):
    kp_ids = resolve_kp_words(conn, args.kp, allow_node=True)
    if args.dsl_ref:
        if Path(args.dsl_ref).is_absolute():
            sys.exit(f'🔴 dsl_ref 必须相对 v2 根（老货架 717 行绝对路径全断的教训）：{args.dsl_ref}')
        if not (ROOT / args.dsl_ref).exists():
            sys.exit(f'🔴 dsl_ref 指向的文件不存在：{args.dsl_ref}——DSL 必留档，留档=文件真在')
    params = None
    if args.params:
        params = json.dumps(json.loads(args.params), ensure_ascii=False)   # 验 JSON 再存
    mid = args.id or 'EM' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
    dup = conn.execute('SELECT id FROM exam_model WHERE name=? AND status=?',
                       (args.name, '在用')).fetchone()
    if dup and not args.id:
        sys.exit(f'🔴 已有在用同名考察模型 {dup[0]}（{args.name}）——出题前必查库')
    conn.execute(
        'INSERT INTO exam_model(id,name,kp_ids_json,dsl_ref,params_json,note,status) VALUES (?,?,?,?,?,?,?)',
        (mid, args.name, json.dumps(kp_ids, ensure_ascii=False), args.dsl_ref, params, args.note, '在用'))
    conn.commit()
    print(f'exam_model 留档：{mid} {args.name} → 考点 {kp_ids} dsl={args.dsl_ref}')
    return mid, f'{args.name} kp={kp_ids} dsl={args.dsl_ref}'


def cmd_coverage(conn, args):
    kp_ids = resolve_kp_words(conn, [args.kp])
    kid = kp_ids[0]
    name, = conn.execute('SELECT name FROM kp WHERE id=?', (kid,)).fetchone()
    qn = dict(conn.execute(
        'SELECT q.status, COUNT(*) FROM question_kp qk JOIN question q ON q.id=qk.question_id '
        'WHERE qk.kp_id=? GROUP BY q.status', (kid,)).fetchall())
    sm = [r for r in conn.execute(
        "SELECT id,name,tier,freq FROM solution_model WHERE status='在用' AND kp_ids_json LIKE ?",
        (f'%{kid}%',))]
    em = [r for r in conn.execute(
        "SELECT id,name,dsl_ref FROM exam_model WHERE status='在用' AND kp_ids_json LIKE ?",
        (f'%{kid}%',))]
    print(f'考点覆盖对账 · {kid} {name}')
    print(f'  题：{sum(qn.values())} 道（' + (' '.join(f'{k}{v}' for k, v in qn.items()) or '空') + '）')
    print(f'  解题模型：{len(sm)} 条')
    for r in sm:
        print(f'    {r[0]} {r[1]} (tier={r[2]} freq={r[3]})')
    print(f'  考察模型(DSL)：{len(em)} 条')
    for r in em:
        print(f'    {r[0]} {r[1]} dsl={r[2]}')
    return kid, f'{name} q={sum(qn.values())} sm={len(sm)} em={len(em)}'


def cmd_list(conn, args):
    tab = {'solution': 'solution_model', 'exam': 'exam_model'}[args.which]
    rows = conn.execute(f'SELECT id,name,kp_ids_json,status FROM {tab} ORDER BY id').fetchall()
    for r in rows:
        print('\t'.join(str(x) for x in r))
    print(f'—— {tab} 共 {len(rows)} 条')
    return tab, f'{len(rows)}条'


def main():
    ap = argparse.ArgumentParser(description='solution_model / exam_model 留档与考点覆盖对账')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('solution-add')
    s.add_argument('--name', required=True); s.add_argument('--kp', action='append', required=True)
    s.add_argument('--trigger', required=True); s.add_argument('--action', required=True)
    s.add_argument('--tier', type=int); s.add_argument('--freq', type=int); s.add_argument('--id')
    s = sub.add_parser('exam-add')
    s.add_argument('--name', required=True); s.add_argument('--kp', action='append', required=True)
    s.add_argument('--dsl-ref', dest='dsl_ref'); s.add_argument('--params'); s.add_argument('--note')
    s.add_argument('--id')
    s = sub.add_parser('coverage'); s.add_argument('--kp', required=True)
    s = sub.add_parser('list'); s.add_argument('which', choices=['solution', 'exam'])
    args = ap.parse_args()

    t0 = time.time()
    conn = open_db(args.db)
    try:
        fn = {'solution-add': cmd_solution_add, 'exam-add': cmd_exam_add,
              'coverage': cmd_coverage, 'list': cmd_list}[args.cmd]
        digest, detail = fn(conn, args)
        log_skill(conn, args.cmd, digest, '成功', detail, t0)
    except (SystemExit, LeafKpError) as e:
        msg = str(e)
        if msg and msg not in ('0',):
            print(msg, file=sys.stderr)
            try:
                log_skill(conn, args.cmd, str(vars(args))[:200], '失败', msg, t0)
            except Exception:
                pass
        conn.close()
        sys.exit(1)
    conn.close()


if __name__ == '__main__':
    main()
