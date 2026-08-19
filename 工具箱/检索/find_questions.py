# -*- coding: utf-8 -*-
"""找题 CLI（D-20 三层的人机入口）——库里有什么、能不能拿来用，一条命令说清。

三层（正本=认知/数据结构.md §三c）：
  ①精确过滤（难度/题型/状态/来源类）+ ②倒排（考点/标签/模型/pattern/血缘/使用足迹）= query_core 纯 SQL；
  ③语意层 `--like "自然语言描述"` = embed_tool（本地 bge sidecar），
    🔴 **先 SQL 过滤再向量排序**——语意层只负责排序，不负责放宽条件。

用法（--db 缺省=脚本位置自解析 <v2根>/知识库/kb.db；worktree 里跑=天然沙盘）：
  python 工具箱/检索/find_questions.py --kp 相反数 --difficulty 巩固 --unused
  python 工具箱/检索/find_questions.py --kp 100002 --qtype 应用题 --tag 场景:行程 --limit 20
  python 工具箱/检索/find_questions.py --siblings q2026… --include-self
  python 工具箱/检索/find_questions.py --in-artifact A2026… --count
  python 工具箱/检索/find_questions.py --kp 100002 --like "路程速度时间的应用题" --topk 5
  python 工具箱/检索/find_questions.py --model EM-mix --ids-only     # 喂给别的脚本
组合条件**一律 AND**（同一维度内多值：考点/题型/难度/状态/来源/pattern 是 OR，标签是 AND）。
输出行：id / 难度 / 状态 / 进过几卷 / 考点名 / 题面首块（截 60）。
每次执行落 skill_log（skill='找题'）。
"""
import argparse
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import embed_tool  # noqa: E402
from query_core import QueryError, count, explain, fetch_rows, find_ids, rows_by_ids  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def build_filters(a):
    """命令行 → query_core 过滤器字典（只放用户真给了的键；没给的键**不进字典**）。"""
    f = {}
    for key, val in (('kp', a.kp), ('qtype', a.qtype), ('difficulty', a.difficulty),
                     ('status', a.status), ('source_kind', a.source_kind), ('tag', a.tag),
                     ('pattern', a.pattern)):
        if val:
            f[key] = val
    for key, val in (('model', a.model), ('mother', a.mother), ('siblings', a.siblings),
                     ('in_artifact', a.in_artifact), ('not_in_artifact', a.not_in_artifact),
                     ('text', a.text)):
        if val:
            f[key] = val
    if a.include_self:
        f['siblings_include_self'] = True
    if a.unused:
        f['unused'] = True
    elif a.used:
        f['unused'] = False
    return f


def fmt_row(r, score=None):
    kps = '/'.join(k['name'] for k in r['kps']) or '🔴 没挂考点'
    head = f'{r["id"]}\t{r["difficulty"] or "—"}\t{r["status"]}\t{r["paper_count"]}卷\t{kps}\t{r["stem"]}'
    return (f'{score:.4f}  ' if score is not None else '') + head


def main():
    ap = argparse.ArgumentParser(
        description='找题（D-20 三层：①精确过滤 + ②倒排 + ③语意 --like）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='组合条件全 AND；同维度多值：考点/题型/难度/状态/来源/pattern=OR，标签=AND。')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    g = ap.add_argument_group('② 倒排')
    g.add_argument('--kp', action='append', help='考点名/别名（→现行叶子恰一）或数字 id 前缀（=整枝，如 100002 取整章）；可多次')
    g.add_argument('--tag', action='append', help='标签 `域:名` 或 `名`；可多次（多个=AND 收窄）')
    g.add_argument('--pattern', action='append', help='题型目录 pattern_id；可多次')
    g.add_argument('--model', help='考察模型 model_id（prov_json.model_id 精确匹配）')
    g.add_argument('--mother', metavar='QID', help='取该题的变体')
    g.add_argument('--siblings', metavar='QID', help='取该题的同母兄弟')
    g.add_argument('--include-self', dest='include_self', action='store_true',
                   help='配 --siblings：结果含该题自身（缺省不含）')
    g = ap.add_argument_group('① 精确过滤')
    g.add_argument('--qtype', action='append', help='题型中文标签（选择题/计算题/应用题…）；可多次')
    g.add_argument('--difficulty', action='append', help='难度中文标签（送分/巩固/中档/压轴）；可多次')
    g.add_argument('--status', action='append', help='草稿/已审/上架/退役；可多次（缺省=不筛，退役题也会出现）')
    g.add_argument('--source-kind', dest='source_kind', action='append',
                   help='scan/manual/model/pipeline；可多次')
    g.add_argument('--text', help='题面子串（🔴 匹配块流 JSON 原文，跨块短语匹配不到）')
    g = ap.add_argument_group('+7 使用足迹')
    m = g.add_mutually_exclusive_group()
    m.add_argument('--unused', action='store_true', help='没进过任何卷')
    m.add_argument('--used', action='store_true', help='至少进过一卷')
    g.add_argument('--in-artifact', dest='in_artifact', metavar='AID', help='进过该册')
    g.add_argument('--not-in-artifact', dest='not_in_artifact', metavar='AID', help='没进过该册')
    g = ap.add_argument_group('③ 语意层（本地 bge sidecar）')
    g.add_argument('--like', metavar='描述', help='自然语言描述；🔴 先按上面的过滤器过 SQL，再在候选里按语意排序')
    g.add_argument('--topk', type=int, default=8, help='语意层返回条数（缺省 8）')
    g.add_argument('--venv', help=f'sidecar venv 里的 python（缺省 {embed_tool.DEFAULT_VENV}）')
    g.add_argument('--model-dir', dest='model_dir', help=f'模型权重根（缺省 {embed_tool.DEFAULT_MODEL_DIR}）')
    g = ap.add_argument_group('输出')
    g.add_argument('--limit', type=int, help='最多列几条（缺省 20；--like 时由 --topk 管）')
    g.add_argument('--count', action='store_true', help='只报命中条数')
    g.add_argument('--ids-only', dest='ids_only', action='store_true', help='只吐 id（一行一个，给别的脚本吃）')
    g.add_argument('--order', default='created', choices=('created', 'created_desc', 'id'))
    g.add_argument('--sql', action='store_true', help='把生成的 SQL 与参数打出来（查询透明）')
    a = ap.parse_args()

    p = Path(a.db)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}（先跑 工具箱/库/init_db.py --only kb）')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    t0 = time.time()
    filters = build_filters(a)
    action = 'find-like' if a.like else 'find'
    digest = str(filters)[:180] + (f' like={a.like[:40]}' if a.like else '')

    try:
        if a.sql:
            sql, params, meta = explain(conn, filters, a.order, a.limit)
            print(f'SQL   : {sql}\n参数  : {params}')
            for n in meta.get('note') or []:
                print(f'resolve: {n}')

        n = count(conn, filters)
        if a.count:
            print(n)
            _log(conn, action, digest, '成功', f'count={n}', t0)
            return 0
        if not a.ids_only:
            _sql, _p, meta = explain(conn, filters, a.order, a.limit)
            for note in meta.get('note') or []:
                print(f'· {note}')

        if a.like:
            cand = find_ids(conn, filters, a.order)          # ①② 先过滤（不限量），③ 只在候选里排
            if a.limit:
                print(f'⚠️ --like 时 --limit 不生效（条数由 --topk={a.topk} 管）', file=sys.stderr)
            if not cand:
                print(f'命中 0 条（①②层就空了，语意层没得排）')
                _log(conn, action, digest, '成功', 'hits=0', t0)
                return 0
            hits, info = embed_tool.rank(conn, a.like, cand, a.topk, a.venv, a.model_dir)
            rows = rows_by_ids(conn, [q for q, _ in hits])
            score = dict(hits)
            if a.ids_only:
                for r in rows:
                    print(r['id'])
            else:
                print(f'①②层命中 {n} 条 → ③语意「{a.like}」排序取前 {len(rows)} '
                      f'（模型 {info["model"]}，候选里 {info["vectored"]} 题有向量）')
                if info['missing']:
                    print(f'⚠️ 候选里有 {info["missing"]} 题还没算向量，排不进来——'
                          f'补：python 工具箱/检索/embed_tool.py build')
                for r in rows:
                    print(fmt_row(r, score[r['id']]))
            _log(conn, action, digest, '成功', f'cand={n} hits={len(rows)}', t0)
            return 0

        limit = a.limit or 20
        rows = fetch_rows(conn, filters, a.order, limit)
        if a.ids_only:
            for r in rows:
                print(r['id'])
        else:
            print(f'命中 {n} 条' + (f'，列前 {len(rows)}（--limit 调）' if n > len(rows) else ''))
            for r in rows:
                print(fmt_row(r))
        _log(conn, action, digest, '成功', f'hits={n} shown={len(rows)}', t0)
        return 0
    except (QueryError, embed_tool.EmbedError) as e:
        print(f'🔴 {e}', file=sys.stderr)
        _log(conn, action, digest, '失败', str(e), t0)
        return 1
    finally:
        conn.close()


def _log(conn, action, digest, result, detail, t0):
    try:
        conn.execute(
            'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) '
            'VALUES (?,?,?,?,?,?,?)',
            ('找题', action, str(digest)[:200], result, str(detail)[:500],
             int((time.time() - t0) * 1000), now()))
        conn.commit()
    except Exception:
        pass


if __name__ == '__main__':
    raise SystemExit(main())
