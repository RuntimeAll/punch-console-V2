# -*- coding: utf-8 -*-
"""确定性查询核（D-20 找题检索 ①精确过滤 + ②倒排 两层）——纯 SQL 构造，零 LLM。

正本＝认知/数据结构.md §三c「D-20 找题检索模型」：
    ①精确过滤（难度/状态/来源类是**准确查询**，🔴 不进向量）
    ②倒排索引（考点/模型/标签/血缘/使用足迹，全走关联表现算，不建计数列）
    ③语意向量（工具箱/检索/embed_tool.py，本文件不碰）

本文件是**库**不是命令：入 过滤器字典 → 出 (sql, params)。三个使用方共用同一口径：
    · 工具箱/检索/find_questions.py   —— 找题 CLI（①②③ 全层）
    · 工具箱/组卷/paper_tool.py       —— 组卷 take 取题（①② 子集）
    · console/server/kb-read-api.mjs  —— 展示台读 API（js 侧手写等价 SQL，口径照本文件）

🔴 三条纪律（违一条这个核就废了）：
  · **全参数化**：一切外部输入进 SQL 走 ? 占位，无字符串拼接（唯一拼接是占位符个数）；
  · **翻不出就报错，绝不静默当「不过滤」**：考点 resolve 不中 / 标签库里没有 / 字典翻不出，
    一律抛 QueryError（老区「查不到就返回全库」是查询侧最阴的静默降级）；
  · **未知过滤器键=拒收**：拼错 `dificulty` 不许当没写（那等于悄悄放宽条件）。

过滤器全表（组合一律 AND；维度内多值的合并方式见各条）：
| 键                    | 值                      | 语义                                              |
|-----------------------|-------------------------|---------------------------------------------------|
| kp                    | 词 / 词表               | 名/别名→现行叶子（恰一）；🔴 纯数字=id **前缀取整枝**（100002=整章）。多值 OR |
| qtype                 | 中文标签/码 / 表        | question.qtype_code，多值 OR                      |
| difficulty            | 中文标签/码 / 表        | question.diff_code，多值 OR（🔴 难度是精确过滤不进向量）|
| status                | 草稿/已审/上架/退役 / 表| question.status，多值 OR                          |
| source_kind           | scan/manual/model/pipeline| question.source_kind，多值 OR                   |
| tag                   | `域:名` 或 `名` / 表    | question_tag 倒排；🔴 多值 **AND**（标签是收窄用的）|
| pattern               | pattern_id / 表         | question.pattern_id，多值 OR                      |
| model                 | model_id                | prov_json.model_id 精确（json_extract，无 json1 则 LIKE 兜底）|
| mother                | qid                     | 取该题的**变体**（question.mother_qid = qid）     |
| siblings              | qid                     | 取该题的**同母兄弟**（母=qid.mother_qid；qid 无母则以 qid 自身为母=取它的变体）|
| siblings_include_self | bool（缺省 False）      | 兄弟集是否含 qid 自身                             |
| unused                | bool                    | True=没进过任何卷；False=至少进过一卷             |
| in_artifact           | artifact_id             | 进过该册                                          |
| not_in_artifact       | artifact_id             | 没进过该册（组卷「同册一题不出现两次」的前置过滤）|
| text                  | 子串                    | 题面块流 JSON 原文 LIKE（跨块的短语匹配不到，如实说）|

用法（库）：
    from query_core import build_query, find_ids, fetch_rows, count, QueryError
    sql, params = build_query(conn, {'kp': '相反数', 'difficulty': '巩固', 'unused': True}, limit=5)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import assert_leaf_kp, LeafKpError  # noqa: E402

# ── 值域（与 认知/数据结构.md 一致，改这里=改契约）──────────────────────
Q_STATUS = ('草稿', '已审', '上架', '退役')
SOURCE_KINDS = ('scan', 'manual', 'model', 'pipeline')
ORDERS = {
    'created': 'q.created_at, q.id',          # 缺省：入库序（组卷 take 依赖它的确定性）
    'created_desc': 'q.created_at DESC, q.id',
    'id': 'q.id',
}
FILTER_KEYS = frozenset((
    'kp', 'qtype', 'difficulty', 'status', 'source_kind', 'tag', 'pattern', 'model',
    'mother', 'siblings', 'siblings_include_self', 'unused', 'in_artifact', 'not_in_artifact',
    'text',
))
RE_KP_ID = re.compile(r'^\d{3,15}$')


class QueryError(Exception):
    """查询条件立不住（resolve 不中/字典翻不出/键拼错）——拒查不静默放宽。"""


# ══════════════════════════════════════════════════════════════════════
# 小原语
# ══════════════════════════════════════════════════════════════════════
def _marks(n):
    return ','.join(['?'] * n)


def _like(s):
    """LIKE 实参转义（% _ \\ 三个元字符）——配 ESCAPE '\\' 用。"""
    return str(s).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _listify(v, key):
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        out = [str(x) for x in v if str(x).strip()]
    elif isinstance(v, str):
        out = [v] if v.strip() else []
    else:
        raise QueryError(f'过滤器 {key}={v!r} 类型非法（要字符串或字符串数组）')
    return out


def _has_json1(conn):
    """本机 sqlite 有没有 json1 扩展（每次现探：sqlite3.Connection 挂不住自定义属性，
    而这条探针本身是微秒级的——宁可多探一次，也不缓存到全局字典里养 id 复用的坑）。"""
    try:
        conn.execute("""SELECT json_extract('{"a":1}','$.a')""").fetchone()
        return True
    except Exception:
        return False


def dict_codes(conn, domain, labels):
    """中文标签/码 → 字典码表；翻不出如实报错不猜（老区四套题型编码的教训）。"""
    codes = []
    for lab in labels:
        row = conn.execute('SELECT code FROM dict_item WHERE domain=? AND label=? AND status=?',
                           (domain, lab, '在用')).fetchone()
        if not row:
            row = conn.execute('SELECT code FROM dict_item WHERE domain=? AND code=? AND status=?',
                               (domain, lab, '在用')).fetchone()
        if not row:
            have = [r[0] for r in conn.execute(
                'SELECT label FROM dict_item WHERE domain=? AND status=? ORDER BY ord',
                (domain, '在用'))]
            raise QueryError(f'{domain} 标签 {lab!r} 字典翻不出（dict_item 无此条）——'
                             f'在用的是 {have}；翻不出的不猜')
        codes.append(row[0])
    return list(dict.fromkeys(codes))


def resolve_kp_words(conn, words):
    """考点词表 → kp id 集合（供 question_kp 倒排 IN），并回报每个词怎么命中的。

    🔴 两条路，写法自解释：
      · 纯数字（3~15 位）= **id 前缀取整枝**：该 id 自身 + 全部后代（KG 每 3 位一层的 id 契约），
        `100002` 就是整章、`100002003` 就是整节、12 位就是那一片叶；前缀零命中=报错不静默；
      · 非数字 = 名/别名 → **现行叶子恰一命中**（照 paper_tool 原有口径），
        0 命中或多命中都拒查（取题锚点不许猜）。
    返回 (ids, notes)：ids 去重保序；notes 为 [(词, 说明)] 供调用方如实打印。
    """
    ids, notes = [], []
    for w in words:
        w = str(w).strip()
        if not w:
            continue
        if RE_KP_ID.match(w):
            hit = [r[0] for r in conn.execute(
                "SELECT id FROM kp WHERE id LIKE ? ESCAPE '\\' ORDER BY id", (_like(w) + '%',))]
            if not hit:
                raise QueryError(f'考点 id 前缀 {w!r} 在 kp 表零命中——先铺枝（工具箱/kg/kg_tool.py），别空查')
            leaves = [r[0] for r in conn.execute(
                f"SELECT id FROM kp WHERE id IN ({_marks(len(hit))}) AND level='考点'", hit)]
            ids += hit
            notes.append((w, f'id 前缀取整枝：kp 节点 {len(hit)} 个（叶子 {len(leaves)} 个）'))
            continue
        hits = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name=?', (w,))]
        via = '考点名'
        if not hits:
            hits = [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (w,))]
            via = '别名'
        leaf = []
        for h in dict.fromkeys(hits):
            try:
                assert_leaf_kp(conn, h)
                leaf.append(h)
            except LeafKpError:
                pass
        if len(leaf) != 1:
            raise QueryError(
                f'考点 {w!r} resolve 命中现行叶子 {len(leaf)} 个（要恰一）：{leaf}——'
                f'名/别名只认叶子；要整枝请写数字 id 前缀（如 100002=整章），'
                f'要消歧请写 12 位叶 id，缺词先补 KG 别名')
        ids.append(leaf[0])
        notes.append((w, f'{via}→叶子 {leaf[0]}'))
    return list(dict.fromkeys(ids)), notes


def resolve_tag_spec(conn, spec):
    """`域:名` 或 `名` → tag id 表（跨域同名=该条件内 OR）。库里没有=拒查不静默返空。"""
    dom, name = None, str(spec)
    for sep in (':', '：'):                       # 🔴 全角冒号也认（中文输入常态）
        if sep in name:
            dom, name = name.split(sep, 1)
            break
    dom = dom.strip() if dom else None
    name = name.strip()
    if not name:
        raise QueryError(f'标签 {spec!r} 非法（要 `域:名` 或 `名`）')
    if dom:
        rows = conn.execute('SELECT id,domain,name,status FROM tag WHERE domain=? AND name=?',
                            (dom, name)).fetchall()
    else:
        rows = conn.execute('SELECT id,domain,name,status FROM tag WHERE name=?', (name,)).fetchall()
    if not rows:
        have = [f'{r[0]}:{r[1]}' for r in conn.execute(
            'SELECT domain,name FROM tag ORDER BY domain,name LIMIT 12')]
        raise QueryError(f'标签 {spec!r} 在 tag 表零命中——库里有的（前 12）：{have or "（一个都没有）"}；'
                         f'标签不猜，要么改词要么先打标')
    return rows


# ══════════════════════════════════════════════════════════════════════
# where 构造
# ══════════════════════════════════════════════════════════════════════
def build_where(conn, filters):
    """过滤器字典 → (where 子句串, params, meta)。where 串不带 'WHERE'；空条件返回 ''。

    meta = {'kp': [...], 'tag': [...], 'note': [...]}——resolve 结果如实回给调用方打印。
    """
    filters = dict(filters or {})
    bad = sorted(set(filters) - FILTER_KEYS)
    if bad:
        raise QueryError(f'未知过滤器键 {bad}——拼错的键绝不静默忽略（那等于悄悄放宽条件）。'
                         f'合法键：{sorted(FILTER_KEYS)}')
    where, params, meta = [], [], {'note': []}

    # ── ② 倒排：考点（名/别名→叶子；数字 id 前缀→整枝）──────────────────
    kp_words = _listify(filters.get('kp'), 'kp')
    if kp_words:
        kp_ids, notes = resolve_kp_words(conn, kp_words)
        meta['kp'] = kp_ids
        meta['note'] += [f'考点 {w}：{d}' for w, d in notes]
        where.append(f'EXISTS (SELECT 1 FROM question_kp qk WHERE qk.question_id=q.id '
                     f'AND qk.kp_id IN ({_marks(len(kp_ids))}))')
        params += kp_ids

    # ── ① 精确过滤：题型 / 难度（🔴 难度不进向量）/ 状态 / 来源类 ────────
    for key, col, domain in (('qtype', 'q.qtype_code', 'qtype'),
                             ('difficulty', 'q.diff_code', 'difficulty')):
        vals = _listify(filters.get(key), key)
        if vals:
            codes = dict_codes(conn, domain, vals)
            where.append(f'{col} IN ({_marks(len(codes))})')
            params += codes
            meta['note'].append(f'{key} {vals}→码 {codes}')
    for key, col, allowed in (('status', 'q.status', Q_STATUS),
                              ('source_kind', 'q.source_kind', SOURCE_KINDS)):
        vals = _listify(filters.get(key), key)
        if vals:
            illegal = [v for v in vals if v not in allowed]
            if illegal:
                raise QueryError(f'{key}={illegal} 非法（值域 {allowed}）')
            where.append(f'{col} IN ({_marks(len(vals))})')
            params += vals

    # ── ② 倒排：标签（多值 AND，一个标签一条 EXISTS）───────────────────
    tag_specs = _listify(filters.get('tag'), 'tag')
    if tag_specs:
        meta['tag'] = []
        for spec in tag_specs:
            rows = resolve_tag_spec(conn, spec)
            tids = [r[0] for r in rows]
            meta['tag'] += [f'{r[1]}:{r[2]}' + ('' if r[3] == '在用' else f'（{r[3]}）') for r in rows]
            where.append(f'EXISTS (SELECT 1 FROM question_tag qt WHERE qt.question_id=q.id '
                         f'AND qt.tag_id IN ({_marks(len(tids))}))')
            params += tids

    # ── ② 倒排：题型目录 pattern / 考察模型 model（血缘里的 model_id）──
    pats = _listify(filters.get('pattern'), 'pattern')
    if pats:
        where.append(f'q.pattern_id IN ({_marks(len(pats))})')
        params += pats
    model = filters.get('model')
    if model:
        model = str(model)
        if _has_json1(conn):
            where.append("json_valid(q.prov_json) AND json_extract(q.prov_json,'$.model_id')=?")
            params.append(model)
            meta['note'].append(f'model={model}（json_extract 精确匹配）')
        else:
            # 兜底：本机 sqlite 无 json1 时退 LIKE（两种 JSON 间距写法都试），如实标注是兜底
            where.append("(q.prov_json LIKE ? ESCAPE '\\' OR q.prov_json LIKE ? ESCAPE '\\')")
            params += [f'%"model_id": "{_like(model)}"%', f'%"model_id":"{_like(model)}"%']
            meta['note'].append(f'⚠️ 本机 sqlite 无 json1，model={model} 走 LIKE 兜底（可能宽）')

    # ── +6 血缘：母题的变体 / 同母兄弟 ────────────────────────────────
    mother = filters.get('mother')
    if mother:
        mother = str(mother)
        if not conn.execute('SELECT 1 FROM question WHERE id=?', (mother,)).fetchone():
            raise QueryError(f'mother={mother!r} 在库里不存在——血缘锚点不许指空')
        where.append('q.mother_qid=?')
        params.append(mother)
    sib = filters.get('siblings')
    if sib:
        sib = str(sib)
        row = conn.execute('SELECT mother_qid FROM question WHERE id=?', (sib,)).fetchone()
        if not row:
            raise QueryError(f'siblings={sib!r} 在库里不存在——血缘锚点不许指空')
        root = row[0] or sib               # 自己没母题=它就是母题，取它的变体
        where.append('q.mother_qid=?')
        params.append(root)
        if not filters.get('siblings_include_self'):
            where.append('q.id<>?')
            params.append(sib)
        meta['note'].append(f'同母兄弟：母={root}' + ('（含自身）' if filters.get('siblings_include_self')
                                                     else '（不含自身，加 siblings_include_self 才含）'))
    elif filters.get('siblings_include_self'):
        raise QueryError('siblings_include_self 只在给了 siblings 时有意义——单给它=条件没落地，拒查')

    # ── +7 使用足迹：join paper_item 现算，不建计数列 ──────────────────
    unused = filters.get('unused')
    if unused is not None:
        if not isinstance(unused, bool):
            raise QueryError(f'unused={unused!r} 非法（要 True/False）')
        where.append(('NOT EXISTS' if unused else 'EXISTS') +
                     ' (SELECT 1 FROM paper_item pi WHERE pi.question_id=q.id)')
    for key, neg in (('in_artifact', False), ('not_in_artifact', True)):
        aid = filters.get(key)
        if not aid:
            continue
        aid = str(aid)
        if not conn.execute('SELECT 1 FROM artifact WHERE id=?', (aid,)).fetchone():
            raise QueryError(f'{key}={aid!r} 在 artifact 表不存在——册锚点不许指空')
        where.append(('NOT EXISTS' if neg else 'EXISTS') +
                     ' (SELECT 1 FROM paper_item pi JOIN paper p ON p.id=pi.paper_id '
                     'WHERE pi.question_id=q.id AND p.artifact_id=?)')
        params.append(aid)

    # ── 题面子串（🔴 匹配的是块流 JSON 原文，跨块短语匹配不到，如实说）──
    text = filters.get('text')
    if text:
        where.append("q.blocks_json LIKE ? ESCAPE '\\'")
        params.append(f'%{_like(text)}%')

    return ' AND '.join(where), params, meta


def build_query(conn, filters, select='q.id', order='created', limit=None, offset=None):
    """过滤器字典 → (sql, params)。这是本文件对外的正主。"""
    if order is not None and order not in ORDERS:
        raise QueryError(f'order={order!r} 非法（{sorted(ORDERS)}）')
    w, params, _meta = build_where(conn, filters)
    sql = f'SELECT {select} FROM question q'
    if w:
        sql += ' WHERE ' + w
    if order:
        sql += ' ORDER BY ' + ORDERS[order]
    if limit is not None:
        if not isinstance(limit, int) or limit <= 0:
            raise QueryError(f'limit={limit!r} 非法（要正整数）')
        sql += ' LIMIT ?'
        params = params + [limit]
        if offset:
            sql += ' OFFSET ?'
            params = params + [int(offset)]
    return sql, params


# ══════════════════════════════════════════════════════════════════════
# 执行侧便捷（三个使用方都走这几个，口径才不会漂）
# ══════════════════════════════════════════════════════════════════════
def find_ids(conn, filters, order='created', limit=None, offset=None):
    sql, params = build_query(conn, filters, 'q.id', order, limit, offset)
    return [r[0] for r in conn.execute(sql, params)]


def count(conn, filters):
    sql, params = build_query(conn, filters, 'COUNT(*)', order=None)
    return conn.execute(sql, params).fetchone()[0]


def explain(conn, filters, order='created', limit=None):
    """给 CLI 打印用：SQL 原文 + 参数 + resolve 说明（查询透明，不做黑箱）。"""
    _w, _p, meta = build_where(conn, filters)
    sql, params = build_query(conn, filters, 'q.id', order, limit)
    return sql, params, meta


def first_text(blocks_json, width=60):
    """题面首个 text 块（列表行展示用）；块流坏了如实说，不静默变空。"""
    try:
        doc = json.loads(blocks_json) if isinstance(blocks_json, str) else blocks_json
    except Exception as e:
        return f'🔴 块流损坏：{e}'
    for row in (doc or {}).get('rows') or []:
        for cell in (row or {}).get('cells') or []:
            if isinstance(cell, dict) and cell.get('type') == 'text':
                md = str(cell.get('md') or '').strip().replace('\n', ' ')
                if md:
                    return md if len(md) <= width else md[:width] + '…'
    return '(无正文块)'


def plain_text(blocks_json):
    """题面全部 text 块 md 拼接（③语意层算向量的文本口径，与 match_key 同源思路）。"""
    parts = []

    def walk(cells):
        for c in cells or []:
            if not isinstance(c, dict):
                continue
            if c.get('type') == 'text':
                parts.append(str(c.get('md') or ''))
            elif c.get('type') == 'option':
                parts.append(f'{c.get("label")}.')
                walk(c.get('blocks') or [])
            elif c.get('type') == 'table':
                if isinstance(c.get('md'), str):
                    parts.append(c['md'])
                for trow in c.get('rows') or []:
                    for tcell in trow or []:
                        walk(tcell if isinstance(tcell, list) else [tcell])

    try:
        doc = json.loads(blocks_json) if isinstance(blocks_json, str) else blocks_json
    except Exception:
        return ''
    for row in (doc or {}).get('rows') or []:
        walk((row or {}).get('cells') or [])
    return re.sub(r'\s+', ' ', ' '.join(parts)).strip()


ROW_COLS = ('q.id, q.blocks_json, q.qtype_code, q.diff_code, q.status, q.source_kind, '
            'q.mother_qid, q.pattern_id, q.created_at, '
            '(SELECT COUNT(DISTINCT pi.paper_id) FROM paper_item pi WHERE pi.question_id=q.id)')


def _row_dicts(conn, raws, stem_width):
    ids = [r[0] for r in raws]
    kp_by_q, dict_map = {}, {}
    for r in conn.execute('SELECT code,label FROM dict_item'):
        dict_map[r[0]] = r[1]
    if ids:
        for qid, kid, prim, name in conn.execute(
                f'SELECT qk.question_id, qk.kp_id, qk.is_primary, kp.name FROM question_kp qk '
                f'JOIN kp ON kp.id=qk.kp_id WHERE qk.question_id IN ({_marks(len(ids))}) '
                f'ORDER BY qk.is_primary DESC, kp.id', ids):
            kp_by_q.setdefault(qid, []).append({'id': kid, 'name': name, 'is_primary': bool(prim)})
    out = []
    for r in raws:
        out.append({
            'id': r[0],
            'stem': first_text(r[1], stem_width),
            'qtype': dict_map.get(r[2], r[2]),
            'difficulty': dict_map.get(r[3], r[3]),
            'status': r[4],
            'source_kind': r[5],
            'mother_qid': r[6],
            'pattern_id': r[7],
            'created_at': r[8],
            'paper_count': r[9],
            'kps': kp_by_q.get(r[0], []),
        })
    return out


def fetch_rows(conn, filters, order='created', limit=None, offset=None, stem_width=60):
    """过滤器 → 展示行（id/题面首块/考点/难度/状态/进过几卷）。CLI 与页面同一口径。"""
    sql, params = build_query(conn, filters, ROW_COLS, order, limit, offset)
    return _row_dicts(conn, conn.execute(sql, params).fetchall(), stem_width)


def rows_by_ids(conn, ids, stem_width=60):
    """按给定 id 顺序取展示行（③语意层排序后回填用；库里没有的 id 如实丢并可对账）。"""
    ids = list(ids)
    if not ids:
        return []
    raws = conn.execute(
        f'SELECT {ROW_COLS} FROM question q WHERE q.id IN ({_marks(len(ids))})', ids).fetchall()
    by_id = {r[0]: r for r in raws}
    return _row_dicts(conn, [by_id[i] for i in ids if i in by_id], stem_width)
