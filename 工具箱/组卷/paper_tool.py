# -*- coding: utf-8 -*-
"""组卷工具（PRD-002 交付件 #10b）——paper / paper_item 两表的唯一写入通路。

库中心产线的中段（认知/数据结构.md §2.6b、认知/业务流程.md §二/§三）：
    出题 → ingest_flow 入 question（草稿）→ **本工具组册（从库取题）** →
    render-pack 导出 → 工具箱/渲染/render_paper.py 从库渲件 → finalize 定稿+promote → 挂账。

🔴 落点纪律：
  · 题号=paper_item.ord、分值=paper_item.score（question 表根本没有 qno/score 两列）；
  · 渲染不落第二载荷：render-pack 只是 paper.layout_json + question.blocks_json 的搬运，
    题面改了重渲即得（两处漂移不可能发生）；
  · 组卷闸四条（违例拒收不静默）：question 存在且非退役、必挂叶子考点；
    同一 artifact 内一题不出现两次（跨 paper 也查）；take 取不足如实报差额并整体失败；
    paper_item.section 必须在 layout.sections 里找得到同名节；
  · 幂等：组卷是**编排动作**，同 artifact+ord 的 paper 重跑 = 先删该卷全部 items 再重建（重排），
    并把该卷退回「草稿」（改卷回草稿，DDL 原话）。

用法（--db 缺省 = 脚本位置自解析 <v2根>/知识库/kb.db；worktree 里跑 = 天然沙盘）：
  python paper_tool.py assemble --spec 组卷.json
  python paper_tool.py render-pack --artifact A2026… [--paper-ord 1] --out 产物/…/render-pack.json
  python paper_tool.py finalize --artifact A2026…
  python paper_tool.py list [--artifact A2026…]
  python paper_tool.py show --paper P2026…
每次执行落 skill_log（skill='组卷'）。

组卷 spec（一册一文件）：
{
  "artifact": {"id": "可省=新建", "name": "浙教七上有理数·5天打卡", "kind": "打卡册",
               "source_line": "每日打卡", "template": "可空（须已 template-add 登记）"},
  "papers": [{
    "kind": "打卡天", "title": "第一天·有理数的加减", "ord": 1,
    "layout": {"layout": "dense_sections", "body_pt": 12.5, "watermark": null,
               "sections": [{"name": "整数加减混合链", "slot": "expr", "grid": "block",
                             "gap": 0, "gap_each": 11, "ans_cols": 1}]},
    "sections": [{
      "name": "整数加减混合链",                    # 🔴 必须在 layout.sections 里有同名节
      "qids": ["q2026…"],                          # 取题路一：显式指定（非退役即可）
      "take": {"kp": "考点名/别名/id前缀", "difficulty": "巩固",
               "unused_only": true, "limit": 2},   # 取题路二：从库取（限 草稿/上架）
      # take 的条件走 工具箱/检索/query_core.py（与「找题」同一个查询核），可用维度：
      #   kp（名/别名→叶子；数字 id 前缀=整枝，如 100002 取整章）/ difficulty / qtype /
      #   tag（"域:名"，多个=AND）/ pattern / model（prov.model_id）/ source_kind /
      #   mother（取某题的变体）/ siblings（同母兄弟）/ text（题面子串）/ unused_only / limit
      "score": null                                # 可选，整节同分（打卡册留空）
    }]
  }]
}
"""
import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '检索'))
from gates import assert_mounted_kp, LeafKpError  # noqa: E402
# 🔴 take 的取题条件不在这里手写 SQL：与「找题」共用同一个查询核（D-20 ①②层），
#    两处各写一份 SQL = 组卷取到的题和页面/CLI 查到的题会悄悄不一致（口径漂移是查不出来的错）。
from query_core import find_ids, QueryError  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'

ARTIFACT_KINDS = ('打卡册', '专项卷', '举一反三', '讲义', '报告模版', '其他')
PAPER_KINDS = ('打卡天', '专项卷', '试卷', '其他')
STOCK_STATUS = ('草稿', '上架')          # 可取库存的题（草稿=同批新造待交付，上架=库存复用）
RENDER_PACK_CONTRACT = 'render-pack/v1'


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def open_db(path):
    import sqlite3
    p = Path(path)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}（先跑 工具箱/库/init_db.py）')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def log_skill(conn, action, digest, result, detail, t0):
    conn.execute(
        'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) VALUES (?,?,?,?,?,?,?)',
        ('组卷', action, str(digest)[:200], result, str(detail)[:500],
         int((time.time() - t0) * 1000), now()))
    conn.commit()


# ══════════════════════════════════════════════════════════════════════
# 公共原语
# ══════════════════════════════════════════════════════════════════════
def dict_label(conn, domain, code):
    """字典码→中文标签（render-pack 吐中文；翻不出原样回码，绝不静默丢）。"""
    if not code:
        return None
    row = conn.execute('SELECT label FROM dict_item WHERE domain=? AND code=?',
                       (domain, code)).fetchone()
    return row[0] if row else code


def first_line(blocks_json, width=36):
    """题面首行（供 list/show 视图截断展示）。"""
    try:
        doc = json.loads(blocks_json) if isinstance(blocks_json, str) else blocks_json
    except Exception:
        return '(块流解析失败)'
    for row in (doc or {}).get('rows') or []:
        for cell in (row or {}).get('cells') or []:
            if isinstance(cell, dict) and cell.get('type') == 'text':
                md = str(cell.get('md') or '').strip().replace('\n', ' ')
                if md:
                    return md if len(md) <= width else md[:width] + '…'
    return '(无正文块)'


def check_question(conn, qid, errs, tag):
    """组卷闸：question 存在、非退役、必挂叶子考点。返回 True/False。"""
    row = conn.execute('SELECT status FROM question WHERE id=?', (qid,)).fetchone()
    if not row:
        errs.append(f'{tag} question {qid!r} 库里不存在——组卷取的是真题，不是意向')
        return False
    if row[0] == '退役':
        errs.append(f'{tag} question {qid!r} 已退役——退役题不进新卷（软删就要真的删得掉）')
        return False
    kps = [r[0] for r in conn.execute('SELECT kp_id FROM question_kp WHERE question_id=?', (qid,))]
    if not kps:
        errs.append(f'{tag} question {qid!r} 没挂考点——裸题不进卷（学情分轨的分母就是考点集）')
        return False
    # 🔴 存量挂载走 assert_mounted_kp 不走新挂闸（2026-08-21 窗L）：考点细分出题型后，
    #    存量题留在考点层仍是合法账；拿「必须末端」筛存量=铺枝当天全库存量题被组卷判废。
    for kid in kps:
        try:
            assert_mounted_kp(conn, kid)
            return True
        except LeafKpError:
            continue
    errs.append(f'{tag} question {qid!r} 挂的考点 {kps} 没有一个是现行本体节点（考点/题型）——'
                f'挂章级/退役节点=坏账，先修挂载再组卷')
    return False


def used_in_artifact(conn, artifact_id, qid):
    return conn.execute(
        'SELECT p.id, p.ord, pi.ord FROM paper_item pi JOIN paper p ON p.id=pi.paper_id '
        'WHERE p.artifact_id=? AND pi.question_id=? LIMIT 1', (artifact_id, qid)).fetchone()


# take 支持的取题维度（键名 → query_core 过滤器键 + 差额报告里的中文说法）。
# 🔴 走查询核=「找题」有的维度组卷都能用：标签/pattern/模型/血缘/题面子串一并可取，
#    加维度只需在这张表加一行，SQL 一行都不用碰。
TAKE_DIMS = [
    ('kp', 'kp', '考点'),
    ('difficulty', 'difficulty', '难度'),
    ('qtype', 'qtype', '题型'),
    ('tag', 'tag', '标签'),
    ('pattern', 'pattern', '题型目录'),
    ('model', 'model', '考察模型'),
    ('source_kind', 'source_kind', '来源类'),
    ('mother', 'mother', '母题变体'),
    ('siblings', 'siblings', '同母兄弟'),
    ('text', 'text', '题面含'),
]
TAKE_KEYS = {k for k, _, _ in TAKE_DIMS} | {'unused_only', 'limit'}


def take_questions(conn, artifact_id, take, tag, errs):
    """从库取题（D-20 ①②层，条件构造全部委托 工具箱/检索/query_core.py）。

    维度：kp（名/别名→叶子，或数字 id 前缀=整枝）+ difficulty/qtype（中文标签）+ 标签/pattern/模型/血缘/
    题面子串 + unused_only（全库未进过任何卷）+ limit；取库存限 status ∈ ('草稿','上架')。

    🔴 取不足如实报差额并整体失败（绝不静默凑）；同 artifact 已用的题不进候选（重复由本条兜住）。
    """
    limit = take.get('limit')
    if not isinstance(limit, int) or limit <= 0:
        errs.append(f'{tag} take.limit={limit!r} 非法（要正整数）')
        return []
    unknown = sorted(set(take) - TAKE_KEYS)
    if unknown:
        errs.append(f'{tag} take 里有未知键 {unknown}——拼错的取题条件绝不静默忽略（那会静默多取题）。'
                    f'可用：{sorted(TAKE_KEYS)}')
        return []

    filters = {
        'status': list(STOCK_STATUS),
        # 同 artifact 内已用的题一律不进候选（组卷闸「一题不出现两次」的前置过滤）
        'not_in_artifact': artifact_id,
    }
    cond = []
    for key, fkey, cn in TAKE_DIMS:
        if take.get(key):
            filters[fkey] = take[key]
            cond.append(f'{cn}={take[key]}')
    if take.get('unused_only', True):
        filters['unused'] = True
        cond.append('仅未用过')

    try:
        hits = find_ids(conn, filters, order='created', limit=limit)
    except QueryError as e:
        errs.append(f'{tag} take 条件立不住：{e}')
        return []
    if len(hits) < limit:
        errs.append(
            f'{tag} take 取不足：要 {limit} 道（{"，".join(cond) or "无过滤"}，限 状态∈{STOCK_STATUS}），'
            f'库里只捞到 {len(hits)} 道，**差 {limit - len(hits)} 道**——'
            f'绝不静默凑：要么先 DSL 新造补库回流，要么改 spec 降量')
    return hits


# ══════════════════════════════════════════════════════════════════════
# assemble —— 吃 spec 建 artifact 壳 + papers + paper_items
# ══════════════════════════════════════════════════════════════════════
def cmd_assemble(conn, args):
    spec = json.loads(Path(args.spec).read_text(encoding='utf-8'))
    a = spec.get('artifact') or {}
    papers = spec.get('papers') or []
    if not papers:
        sys.exit('🔴 spec.papers 为空——组卷是编排动作，没卷可编')

    # ── artifact 壳：给了 id 就引用已存在的，没给就新建 ──
    aid = a.get('id')
    if aid:
        row = conn.execute('SELECT id,name,kind FROM artifact WHERE id=?', (aid,)).fetchone()
        if not row:
            sys.exit(f'🔴 artifact {aid} 不存在——引用已存在的册要给真 id，新建请省掉 artifact.id')
        print(f'artifact 引用：{aid} {row[1]}（{row[2]}）')
    else:
        kind = a.get('kind')
        if kind not in ARTIFACT_KINDS:
            sys.exit(f'🔴 artifact.kind={kind!r} 非法（{ARTIFACT_KINDS}）')
        if not a.get('name'):
            sys.exit('🔴 新建 artifact 必须给 name')
        if a.get('template'):
            if not conn.execute('SELECT 1 FROM template WHERE id=?', (a['template'],)).fetchone():
                sys.exit(f'🔴 template {a["template"]} 未登记（先 artifact_tool.py template-add）')
        aid = 'A' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
        conn.execute(
            'INSERT INTO artifact(id,name,kind,status,source_line,template_id,created_at) '
            'VALUES (?,?,?,?,?,?,?)',
            (aid, a['name'], kind, '在产', a.get('source_line'), a.get('template'), now()))
        print(f'artifact 新建：{aid} {a["name"]}（{kind}，在产）')

    # ── 第一遍：结构校验 + 幂等清场（删掉要重排的卷的旧 items）──
    errs = []
    ords = [p.get('ord') for p in papers]
    if len(set(ords)) != len(ords):
        sys.exit(f'🔴 spec 内 paper.ord 重复：{ords}——册内序是唯一坐标')
    plan = []
    for pi, p in enumerate(papers):
        tag = f'papers[{pi}]'
        pord = p.get('ord')
        if not isinstance(pord, int):
            errs.append(f'{tag}.ord={pord!r} 非法（要整数，打卡=天号）')
            continue
        if p.get('kind') not in PAPER_KINDS:
            errs.append(f'{tag}.kind={p.get("kind")!r} 非法（{PAPER_KINDS}）')
        if not p.get('title'):
            errs.append(f'{tag}.title 缺失——卷面标题必填')
        layout = p.get('layout')
        if layout is not None and not isinstance(layout, dict):
            errs.append(f'{tag}.layout 必须是对象（版式参数，渲染从库读的依据）')
            layout = None
        lay_sections = []
        for s in (layout or {}).get('sections') or []:
            if isinstance(s, dict) and s.get('name'):
                lay_sections.append(s['name'])
        old = conn.execute('SELECT id,status FROM paper WHERE artifact_id=? AND ord=?',
                           (aid, pord)).fetchone()
        plan.append({'tag': tag, 'spec': p, 'ord': pord, 'layout': layout,
                     'lay_sections': lay_sections, 'old': old})
    if errs:
        _fail(errs)

    for it in plan:
        if it['old']:
            n = conn.execute('SELECT COUNT(*) FROM paper_item WHERE paper_id=?',
                             (it['old'][0],)).fetchone()[0]
            conn.execute('DELETE FROM paper_item WHERE paper_id=?', (it['old'][0],))
            print(f'  幂等重排：{it["tag"]} ord={it["ord"]} 命中已存在卷 {it["old"][0]}，'
                  f'清掉旧 {n} 道题重建（卷退回草稿）')

    # ── 第二遍：建卷 + 逐节取题 + 组卷闸 ──
    made = []
    for it in plan:
        p, pord, tag = it['spec'], it['ord'], it['tag']
        layout_json = json.dumps(it['layout'], ensure_ascii=False) if it['layout'] is not None else None
        if it['old']:
            pid = it['old'][0]
            conn.execute('UPDATE paper SET kind=?,title=?,layout_json=?,status=? WHERE id=?',
                         (p['kind'], p['title'], layout_json, '草稿', pid))
        else:
            pid = 'P' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
            conn.execute(
                'INSERT INTO paper(id,artifact_id,kind,title,ord,layout_json,status,created_at) '
                'VALUES (?,?,?,?,?,?,?,?)',
                (pid, aid, p['kind'], p['title'], pord, layout_json, '草稿', now()))

        ord_no = 0
        detail = []
        for si, sec in enumerate(p.get('sections') or []):
            stag = f'{tag}.sections[{si}]'
            sname = sec.get('name')
            if not sname:
                errs.append(f'{stag}.name 缺失——节名是 paper_item 与 layout 的对位键')
                continue
            # 🔴 节名闸：paper_item.section 必须能在 layout.sections 里找到同名节
            if sname not in it['lay_sections']:
                errs.append(
                    f'{stag} 节名 {sname!r} 在 layout.sections 里找不到同名节'
                    f'（layout 有：{it["lay_sections"] or "无"}）——'
                    f'对不上的节渲染时无处安放，拒收不静默')
                continue
            qids = list(sec.get('qids') or [])
            for q in qids:
                if not isinstance(q, str):
                    errs.append(f'{stag}.qids 含非字符串 {q!r}——🔴 id 全链路字符串')
            n_err = len(errs)
            if sec.get('take'):
                qids += take_questions(conn, aid, sec['take'], stag, errs)
            if not qids and len(errs) == n_err:      # take 已报差额就不再刷屏重复一条
                errs.append(f'{stag} 一道题都没取到（qids 与 take 都空）')
            score = sec.get('score')
            for q in qids:
                if not isinstance(q, str) or not check_question(conn, q, errs, stag):
                    continue
                dup = used_in_artifact(conn, aid, q)
                if dup:
                    errs.append(
                        f'{stag} 题 {q} 在本册已出现过（卷 {dup[0]} 第 {dup[1]} 卷第 {dup[2]} 题）'
                        f'——同一 artifact 内一题不出现两次')
                    continue
                ord_no += 1
                conn.execute(
                    'INSERT INTO paper_item(paper_id,ord,question_id,section,score,note) '
                    'VALUES (?,?,?,?,?,?)', (pid, ord_no, q, sname, score, sec.get('note')))
            detail.append(f'{sname}×{len([q for q in qids if isinstance(q, str)])}')
        if ord_no == 0 and not errs:
            errs.append(f'{tag} 这张卷一道题都没有——空卷不建（要占位先在 spec 里删掉它）')
        made.append((pid, pord, p.get('title'), ord_no, detail))

    if errs:
        _fail(errs)

    conn.commit()
    for pid, pord, title, n, detail in made:
        print(f'  卷 {pid} ord={pord} 《{title}》 {n} 题 [{" / ".join(detail)}]')
    print(f'组卷完成：artifact {aid}，{len(made)} 卷 / {sum(m[3] for m in made)} 题（全草稿，finalize 才定稿）')
    return f'spec={args.spec} artifact={aid}', f'papers={len(made)} items={sum(m[3] for m in made)}'


def _fail(errs):
    lines = '\n'.join('  ✗ ' + e for e in errs)
    sys.exit(f'🔴 组卷闸拒收 {len(errs)} 条（整体失败、一条不入）：\n{lines}')


# ══════════════════════════════════════════════════════════════════════
# render-pack —— 从库导出渲染包（契约 render-pack/v1）
# ══════════════════════════════════════════════════════════════════════
def cmd_render_pack(conn, args):
    row = conn.execute('SELECT id,name,kind FROM artifact WHERE id=?', (args.artifact,)).fetchone()
    if not row:
        sys.exit(f'🔴 artifact {args.artifact} 不存在')
    sql = 'SELECT id,kind,title,ord,layout_json,status FROM paper WHERE artifact_id=?'
    params = [args.artifact]
    if args.paper_ord is not None:
        sql += ' AND ord=?'
        params.append(args.paper_ord)
    prows = conn.execute(sql + ' ORDER BY ord', params).fetchall()
    if not prows:
        sys.exit(f'🔴 artifact {args.artifact} 下没有卷'
                 + (f'（ord={args.paper_ord}）' if args.paper_ord is not None else '')
                 + '——先 assemble')

    papers = []
    for pid, pkind, ptitle, pord, layout_json, pstatus in prows:
        items = []
        for iord, qid, section, score in conn.execute(
                'SELECT ord,question_id,section,score FROM paper_item WHERE paper_id=? ORDER BY ord',
                (pid,)):
            q = conn.execute(
                'SELECT blocks_json,answer_blocks_json,analysis_blocks_json,qtype_code,diff_code,status '
                'FROM question WHERE id=?', (qid,)).fetchone()
            if not q:
                sys.exit(f'🔴 卷 {pid} 第 {iord} 题指向的 question {qid} 不存在——库坏了，别渲')
            if q[5] == '退役':
                print(f'⚠️ 卷 {pid} 第 {iord} 题 {qid} 已退役却还在卷里——重跑 assemble 换题', file=sys.stderr)
            items.append({
                'ord': iord,
                'section': section,
                'score': score,
                'question': {
                    'id': qid,
                    'blocks': json.loads(q[0]),
                    'answer_blocks': json.loads(q[1]) if q[1] else None,
                    'analysis_blocks': json.loads(q[2]) if q[2] else None,
                    'qtype': dict_label(conn, 'qtype', q[3]),
                    'difficulty': dict_label(conn, 'difficulty', q[4]),
                },
            })
        papers.append({
            'id': pid, 'kind': pkind, 'title': ptitle, 'ord': pord,
            'layout': json.loads(layout_json) if layout_json else None,
            'items': items,
        })

    pack = {
        'contract': RENDER_PACK_CONTRACT,
        'artifact': {'id': row[0], 'name': row[1], 'kind': row[2]},
        'papers': papers,
    }
    out = Path(args.out)
    if out.is_absolute():
        sys.exit(f'🔴 --out 必须相对 v2 根（老货架 717 行绝对路径全断的教训）：{args.out}')
    dst = ROOT / out
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding='utf-8')
    n = sum(len(p['items']) for p in papers)
    print(f'render-pack/v1 导出：{out}（{len(papers)} 卷 / {n} 题，{dst.stat().st_size} 字节）')
    return f'artifact={args.artifact} out={out}', f'papers={len(papers)} items={n}'


# ══════════════════════════════════════════════════════════════════════
# finalize —— 全册定稿 + 涉及草稿题 promote 上架（一个事务）
# ══════════════════════════════════════════════════════════════════════
def cmd_finalize(conn, args):
    if not conn.execute('SELECT 1 FROM artifact WHERE id=?', (args.artifact,)).fetchone():
        sys.exit(f'🔴 artifact {args.artifact} 不存在')
    pids = [r[0] for r in conn.execute('SELECT id FROM paper WHERE artifact_id=?', (args.artifact,))]
    if not pids:
        sys.exit(f'🔴 artifact {args.artifact} 下没有卷——没东西可定稿')
    qids = [r[0] for r in conn.execute(
        'SELECT DISTINCT pi.question_id FROM paper_item pi JOIN paper p ON p.id=pi.paper_id '
        'WHERE p.artifact_id=?', (args.artifact,))]
    dead = [r[0] for r in conn.execute(
        'SELECT DISTINCT pi.question_id FROM paper_item pi JOIN paper p ON p.id=pi.paper_id '
        "JOIN question q ON q.id=pi.question_id WHERE p.artifact_id=? AND q.status='退役'",
        (args.artifact,))]
    if dead:
        sys.exit(f'🔴 册内含已退役题 {dead}——定稿前先重排（assemble 重跑换题）')

    # 🔴 闸④（先审后上架）：finalize 也是 promote 通路，挂审核工单的题一样拦——不许留后门
    from gates import GateError, assert_promotable
    blocked = []
    for qid in qids:
        try:
            assert_promotable(conn, qid)
        except GateError as e:
            blocked.append(str(e))
    if blocked:
        for b in blocked:
            print('  ✗ ' + b)
        sys.exit(f'🔴 finalize 中止：{len(blocked)} 道题被闸④拦下（先审后上架），先清工单再定稿')

    conn.execute('BEGIN')
    conn.execute("UPDATE paper SET status='定稿' WHERE artifact_id=?", (args.artifact,))
    n = conn.execute(
        "UPDATE question SET status='上架', updated_at=? WHERE status='草稿' AND id IN "
        '(SELECT pi.question_id FROM paper_item pi JOIN paper p ON p.id=pi.paper_id '
        'WHERE p.artifact_id=?)', (now(), args.artifact)).rowcount
    # 覆盖考点回填（开轨 kp_scope 从这取）：只在空时填，绝不覆盖人工圈定的范围
    cur = conn.execute('SELECT kp_ids_json FROM artifact WHERE id=?', (args.artifact,)).fetchone()[0]
    kp_ids = [r[0] for r in conn.execute(
        'SELECT DISTINCT qk.kp_id FROM paper_item pi JOIN paper p ON p.id=pi.paper_id '
        'JOIN question_kp qk ON qk.question_id=pi.question_id WHERE p.artifact_id=? ORDER BY qk.kp_id',
        (args.artifact,))]
    if cur in (None, '', '[]'):
        conn.execute('UPDATE artifact SET kp_ids_json=? WHERE id=?',
                     (json.dumps(kp_ids, ensure_ascii=False), args.artifact))
        print(f'  覆盖考点回填：{len(kp_ids)} 个叶子 {kp_ids}')
    else:
        print(f'  覆盖考点已有值（{cur}），不覆盖——册内实际用到 {len(kp_ids)} 个叶子')
    conn.commit()
    print(f'finalize：{len(pids)} 卷 → 定稿；{n}/{len(qids)} 题 草稿→上架（其余本已上架/已审）')
    return args.artifact, f'papers={len(pids)} promoted={n}/{len(qids)} kp={len(kp_ids)}'


# ══════════════════════════════════════════════════════════════════════
# list / show —— 一本账 / 单卷视图
# ══════════════════════════════════════════════════════════════════════
def cmd_list(conn, args):
    if args.artifact:
        row = conn.execute('SELECT id,name,kind,status FROM artifact WHERE id=?',
                           (args.artifact,)).fetchone()
        if not row:
            sys.exit(f'🔴 artifact {args.artifact} 不存在')
        print(f'{row[0]}\t{row[2]}\t{row[3]}\t{row[1]}')
        rows = conn.execute(
            'SELECT p.id,p.ord,p.kind,p.title,p.status,'
            '(SELECT COUNT(*) FROM paper_item pi WHERE pi.paper_id=p.id) '
            'FROM paper p WHERE p.artifact_id=? ORDER BY p.ord', (args.artifact,)).fetchall()
        for r in rows:
            print(f'  #{r[1]}\t{r[0]}\t{r[2]}\t{r[4]}\t{r[5]} 题\t{r[3]}')
        print(f'—— {len(rows)} 卷 / {sum(r[5] for r in rows)} 题')
        return args.artifact, f'papers={len(rows)}'
    rows = conn.execute(
        'SELECT a.id,a.name,a.kind,a.status,'
        '(SELECT COUNT(*) FROM paper p WHERE p.artifact_id=a.id),'
        '(SELECT COUNT(*) FROM paper_item pi JOIN paper p ON p.id=pi.paper_id WHERE p.artifact_id=a.id) '
        'FROM artifact a ORDER BY a.created_at').fetchall()
    for r in rows:
        print(f'{r[0]}\t{r[2]}\t{r[3]}\t{r[4]} 卷\t{r[5]} 题\t{r[1]}')
    print(f'—— artifact 共 {len(rows)} 条')
    return 'list', f'{len(rows)}条'


def cmd_show(conn, args):
    row = conn.execute(
        'SELECT p.id,p.artifact_id,p.kind,p.title,p.ord,p.status,p.layout_json,a.name '
        'FROM paper p LEFT JOIN artifact a ON a.id=p.artifact_id WHERE p.id=?',
        (args.paper,)).fetchone()
    if not row:
        sys.exit(f'🔴 paper {args.paper} 不存在')
    lay = json.loads(row[6]) if row[6] else None
    print(f'{row[0]}  #{row[4]} 《{row[3]}》 {row[2]} {row[5]}  ← {row[1]} {row[7] or ""}')
    print(f'layout: {lay.get("layout") if lay else "(空)"}'
          f'  节：{[s.get("name") for s in (lay or {}).get("sections") or []]}')
    rows = conn.execute(
        'SELECT pi.ord,pi.section,pi.score,q.id,q.status,q.blocks_json '
        'FROM paper_item pi JOIN question q ON q.id=pi.question_id '
        'WHERE pi.paper_id=? ORDER BY pi.ord', (args.paper,)).fetchall()
    for r in rows:
        sc = f'{r[2]:g}分' if r[2] is not None else '—'
        print(f'  {r[0]:>2}. [{r[1]}] {sc}\t{r[3]} {r[4]}\t{first_line(r[5])}')
    print(f'—— {len(rows)} 题')
    return args.paper, f'items={len(rows)}'


def main():
    ap = argparse.ArgumentParser(description='paper/paper_item 组卷原语（库中心产线中段）')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('assemble'); s.add_argument('--spec', required=True)
    s = sub.add_parser('render-pack')
    s.add_argument('--artifact', required=True)
    s.add_argument('--paper-ord', dest='paper_ord', type=int)
    s.add_argument('--out', required=True, help='相对 v2 根的输出路径')
    s = sub.add_parser('finalize'); s.add_argument('--artifact', required=True)
    s = sub.add_parser('list'); s.add_argument('--artifact')
    s = sub.add_parser('show'); s.add_argument('--paper', required=True)
    args = ap.parse_args()

    t0 = time.time()
    conn = open_db(args.db)
    try:
        fn = {'assemble': cmd_assemble, 'render-pack': cmd_render_pack,
              'finalize': cmd_finalize, 'list': cmd_list, 'show': cmd_show}[args.cmd]
        digest, detail = fn(conn, args)
        log_skill(conn, args.cmd, digest, '成功', detail, t0)
    except (SystemExit, LeafKpError) as e:
        conn.rollback()
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
