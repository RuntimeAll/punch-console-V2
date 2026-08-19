# -*- coding: utf-8 -*-
"""自产题回流入库轻通路（PRD-002 交付件 #2）——生产线出题入 question 的唯一门。

飞轮铁律落点（PRD-002 §1）：
  ①出题必回流：blocks v2 + 血缘（mother_qid/variant_op/prov）+ 考点叶子 + source_kind；
  ②过三闸才算出完：块流校验器 + 执行阀五条 + 考点叶子闸（gates.py，违例拒收不静默）；
  ③出题前必查库：本通路兜底做相似前查（match_key 撞库→拒，除非 --allow-dup）；
  ④每次执行落 skill_log；
  ⑤**入库收尾自动补语意向量**（PRD-003 阶段4）：新题进库后立刻算 question_vec——
    常驻 serve(:4315) 在就走它（毫秒级），不在回落冷载 sidecar，venv/serve 都不在就
    **打印待补命令**。🔴 无论哪种失败都**不阻断入库**（题已过闸进库，向量只是③层检索加速）。
    不想算：--no-vec。

🔴 D-21 等级审矩阵（正本=认知/数据结构.md §2.7 / 业务流程.md §四）——本文件是它的实装点，逐题纯机械判定：

  复杂度（只看题面 blocks，不问 LLM、不看人脸色）           基准等级
    纯 text（0 图 0 表）                                    L0 直入
    恰 1 个 figure                                          L1 抽检
    ≥2 个 figure，或含 table                                L2 速审
    题面 text 总字数 > 600 且 figure ≥ 2                     L3 细审

  源（question.source_kind）
    manual / model / pipeline = 文字层基准，不加级
    🔴 scan（拍照/扫描）一律 +1 级——OCR 无守恒基准，天然多一分不确定；封顶 L3

  行为
    L0        直入草稿，不留待办
    L1        直入草稿，报告与 skill_log 标「L1·抽检」（抽检=人有空时抽着看，不拦上架）
    L2 / L3   题照样入草稿，但**自动开 review_ticket(kind='图审', ref=qid, status='待处理')**，
              note 写明等级与机械判定原因；「先审后上架」由 gates.assert_promotable（闸④）在
              promote 处兜底——工单没处理完，题就上不了架，不许静默跳。
    --skip-review   显式旗标 = 用户明说跳过审核（执行阀第④条的既有口径，同时喂给
                    execution_valve 的 review_skipped_by_user）：L2/L3 不开工单，
                    但报告里大字标明「这批没走等级审」，风险落在用户身上，不静默。

  🔴 裁量留痕：question 表没有 gates_json 列（那列在 ingest_item 上，本轻通路不开批次），
     所以逐题等级落在**报告 + skill_log.detail（等级分布）+ L2/L3 的工单 note**三处，
     不塞进 prov_json/anchor_json（那两处各有其义，混进去=字段一物两名，老区血案）。

用法：
  python ingest_flow.py ingest 题目包.json [--partial] [--allow-dup] [--skip-review] [--no-vec]
  python ingest_flow.py promote --ids q2026...,q2026...   # 草稿→上架（进入交付才可见，D-9；过闸④）
  python ingest_flow.py promote --match 前缀%             # 按 id LIKE 批量
  python ingest_flow.py check 题目包.json                  # 只过闸不入库（干跑，含等级预判）
  python ingest_flow.py tickets [--status 待处理|已处理|已驳回|全部]     # 列审核工单
  python ingest_flow.py ticket-done --id 7 [--note 结论] [--reject]     # 待处理→已处理/已驳回

题目包格式（一册/一批一文件）：
{
  "source_line": "每日打卡",
  "items": [{
    "blocks": {v:2,rows:[…]},            # 题面（必）
    "answer_blocks": {…}, "analysis_blocks": {…},
    "qtype": "计算题", "difficulty": "巩固",     # 中文标签，按 dict_item 翻译
    "source_kind": "model",                      # model/manual/pipeline/scan
    "source_raw": "自编·有理数混合运算 D1-3",
    "kp": ["有理数混合运算", "100001003003"],     # 名/别名/id 混填，全走 resolve+叶子闸
    "primary_kp": "有理数混合运算",               # 缺省=kp[0]
    "mother_qid": null, "variant_op": null,      # 血缘（举一反三必填）
    "prov": {"model_id": "EM-…", "params": {…}, "seed": 7},
    "confidence": 95,
    "tags": [{"domain": "方法", "name": "整体代入"}]
  }]
}
"""
import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import (execution_valve, assert_leaf_kp, assert_promotable,  # noqa: E402
                   LeafKpError, GateError, validate_blocks, SECOND_CARRIERS)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'


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
        ('回流入库', action, str(digest)[:200], result, str(detail)[:500],
         int((time.time() - t0) * 1000), now()))
    conn.commit()


# ── match_key：排重键（v2 口径，确定性可复算）──────────────────────────
# 题面全部 text.md 拼接 → NFKC 归一 → 去全部空白 → 前 40 字 + sha1 前 8 位。
def match_key_of(blocks):
    parts = []

    def walk(cells):
        for c in cells:
            if not isinstance(c, dict):
                continue
            if c.get('type') == 'text':
                parts.append(str(c.get('md') or ''))
            elif c.get('type') == 'option':
                walk(c.get('blocks') or [])
            elif c.get('type') == 'table' and c.get('md'):
                parts.append(str(c['md']))

    for row in blocks.get('rows') or []:
        walk((row or {}).get('cells') or [])
    canon = unicodedata.normalize('NFKC', ''.join(parts))
    canon = re.sub(r'\s+', '', canon)
    if not canon:
        return None
    return canon[:40] + '#' + hashlib.sha1(canon.encode('utf-8')).hexdigest()[:8]


# ══════════════════════════════════════════════════════════════════════
# D-21 等级审矩阵（复杂度 × 源）——纯机械判定，逐题
# ══════════════════════════════════════════════════════════════════════
LEVEL_NAME = {0: 'L0·直入', 1: 'L1·抽检', 2: 'L2·速审', 3: 'L3·细审'}
LONG_TEXT = 600          # 「超长题」阈值（题面 text 去空白后的字数）
TICKET_FROM = 2          # ≥ 该等级自动开 review_ticket（L2/L3 = 速审/细审）
SCAN_BUMP_KINDS = ('scan',)   # 🔴 拍照/扫描源整体 +1 级（OCR 无守恒基准）


def _scan_stem(blocks):
    """机械扫题面：返回 (figure 数, 是否含表, text 净字数)。option/table 内的块一并计。"""
    n_fig = 0
    has_table = False
    texts = []

    def walk(cells):
        nonlocal n_fig, has_table
        for c in cells:
            if not isinstance(c, dict):
                continue
            t = c.get('type')
            if t == 'text':
                texts.append(str(c.get('md') or ''))
            elif t == 'figure':
                n_fig += 1
            elif t == 'option':
                walk(c.get('blocks') or [])
            elif t == 'table':
                has_table = True
                # 表体不计入「正文字数」（表属结构不属题干正文），但表格内的图要数
                for trow in c.get('rows') or []:
                    if isinstance(trow, list):
                        for tcell in trow:
                            if isinstance(tcell, list):
                                walk(tcell)

    rows = blocks.get('rows') if isinstance(blocks, dict) else None
    for row in rows or []:
        walk((row or {}).get('cells') or [])
    canon = re.sub(r'\s+', '', unicodedata.normalize('NFKC', ''.join(texts)))
    return n_fig, has_table, len(canon)


def grade_item(blocks, source_kind):
    """D-21 等级审：复杂度×源 → 等级。返回 dict（level/base/reason/…），不抛异常。

    复杂度：纯 text→L0；恰 1 图→L1；≥2 图 或 含表→L2；正文>600 字 且 ≥2 图→L3。
    源：scan +1 级（封顶 L3）；manual/model/pipeline = 文字层基准。
    """
    n_fig, has_table, n_chars = _scan_stem(blocks)
    if n_fig >= 2 and n_chars > LONG_TEXT:
        base, why = 3, f'超长题（正文 {n_chars} 字 > {LONG_TEXT}）+ {n_fig} 图'
    elif n_fig >= 2:
        base, why = 2, f'{n_fig} 图（正文 {n_chars} 字）'
    elif has_table:
        base, why = 2, f'含表格（{n_fig} 图，正文 {n_chars} 字）'
    elif n_fig == 1:
        base, why = 1, f'恰 1 图（正文 {n_chars} 字）'
    else:
        base, why = 0, f'纯文本（正文 {n_chars} 字）'

    bumped = source_kind in SCAN_BUMP_KINDS
    level = min(3, base + 1) if bumped else base
    src_why = (f'源={source_kind}（拍照/扫描 +1 级' + ('，已封顶 L3' if base + 1 > 3 else '') + '）'
               if bumped else f'源={source_kind or "?"}（文字层基准）')
    return {
        'level': level, 'base': base, 'bumped': bumped,
        'n_fig': n_fig, 'has_table': has_table, 'n_chars': n_chars,
        'name': LEVEL_NAME[level],
        'reason': f'{why}｜{src_why}',
        'need_ticket': level >= TICKET_FROM,
    }


def open_review_ticket(conn, qid, grade):
    """L2/L3 自动开图审工单（先审后上架的入口；出口=gates.assert_promotable）。"""
    note = f'{grade["name"]}｜机械判定：{grade["reason"]}｜等级审矩阵 D-21，先审后上架'
    cur = conn.execute(
        'INSERT INTO review_ticket(kind,ref,status,note,created_at) VALUES (?,?,?,?,?)',
        ('图审', qid, '待处理', note, now()))
    return cur.lastrowid


# ══════════════════════════════════════════════════════════════════════
# 入库收尾：增量向量（D-20 第③层跟着入库走，不用人记着补）
# ══════════════════════════════════════════════════════════════════════
VEC_HINT = ('  补：python 工具箱\\检索\\embed_tool.py build --db <本次的库>'
            '（只补缺的）\n  想快先起常驻 serve：python 工具箱\\启动台.py')


def autovec(conn, qids, serve_port=None):
    """给刚入库的这批题补语意向量（增量）→ (算了几题, 一句说明)。

    🔴 三条：
      · **绝不阻断入库**：题已经过闸进库了，向量只是③层的检索加速。算不动就**打印待补命令**、
        照常返回，退出码不受影响（收尾步骤把主事务拖下水是老区最典型的坏账来源）；
      · 常驻 serve（:4315）在 → 走 serve，毫秒级；不在 → 回落冷载 sidecar；
        **venv 与 serve 都不在 → 只打印待补命令**，一行报警说清楚，不静默；
      · 纯图题（题面无 text 块）如实列出跳过，绝不塞空向量充数。
    """
    if not qids:
        return 0, '无新题'
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '检索'))
        import embed_tool                                  # noqa: PLC0415 —— 故意懒加载
    except Exception as e:                                 # noqa: BLE001
        print(f'⚠️ 增量向量跳过（检索模块加载失败：{type(e).__name__}: {e}）——题已入库，不受影响\n'
              + VEC_HINT)
        return 0, 'skip:import'
    rows = conn.execute(
        'SELECT id, blocks_json FROM question WHERE id IN (%s)' % ','.join('?' * len(qids)),
        list(qids)).fetchall()
    keys, texts, empty = [], [], []
    for qid, bj in rows:
        t = embed_tool.plain_text(bj)
        if not t:
            empty.append(qid)
            continue
        keys.append(qid)
        texts.append(t)
    if empty:
        print(f'⚠️ 增量向量：{len(empty)} 题无正文块（纯图题？）如实跳过，不塞空向量：{empty[:5]}')
    if not keys:
        return 0, 'skip:no-text'

    h = embed_tool.serve_health(serve_port)
    if h:
        via = f'常驻 serve :{embed_tool.serve_port_of(serve_port)}（pid={h.get("pid")}，毫秒级）'
    else:
        try:
            embed_tool.resolve_venv(None)
            via = '冷载 sidecar（serve 没起，每批多花 5~6s；起：python 工具箱\\启动台.py）'
        except embed_tool.EmbedError as e:
            print(f'⚠️ 增量向量跳过：常驻 serve 不在、venv 也不可用——{str(e).splitlines()[0]}\n'
                  f'  🔴 题已入库不受影响，只是③语意层暂时搜不到这 {len(keys)} 题。\n' + VEC_HINT)
            return 0, 'skip:no-venv'
    print(f'增量向量：{len(keys)} 题 走{via}')
    done = 0
    try:
        for i in range(0, len(keys), embed_tool.CHUNK):
            chunk = keys[i:i + embed_tool.CHUNK]
            vecs, dim, model = embed_tool.embed_texts(texts[i:i + embed_tool.CHUNK],
                                                      quiet=True, serve_port=serve_port)
            done += embed_tool.save_vecs(conn, list(zip(chunk, vecs)), model, dim)
    except Exception as e:                                 # noqa: BLE001
        print(f'⚠️ 增量向量没算完（{type(e).__name__}: {e}）——已算 {done}/{len(keys)} 题，'
              f'🔴 题已入库不受影响。\n' + VEC_HINT)
        return done, f'partial:{done}/{len(keys)}'
    print(f'  ✓ 向量入库 {done}/{len(keys)} 题（模型 {model} dim={dim}）')
    return done, f'{done}/{len(keys)}'


def dict_code(conn, domain, label):
    """中文标签→字典码；翻不出→如实报 None（调用侧决定拒）。已是码值则原样回。"""
    if not label:
        return None, None
    row = conn.execute('SELECT code FROM dict_item WHERE domain=? AND label=? AND status=?',
                       (domain, label, '在用')).fetchone()
    if row:
        return row[0], None
    row = conn.execute('SELECT code FROM dict_item WHERE domain=? AND code=? AND status=?',
                       (domain, label, '在用')).fetchone()
    if row:
        return row[0], None
    return None, f'{domain} 标签 {label!r} 字典翻不出（dict_item 无此条）——翻不出的进隔离不猜'


def resolve_kp(conn, word):
    """名/别名/id → 现行叶子 id。恰一命中才算成；0/多命中都如实报错。"""
    if re.fullmatch(r'\d{6,15}', word):
        try:
            assert_leaf_kp(conn, word)
            return word, None
        except LeafKpError as e:
            return None, str(e)
    hits = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name=?', (word,))]
    if not hits:
        hits = [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (word,))]
    leaf = []
    for h in dict.fromkeys(hits):
        try:
            assert_leaf_kp(conn, h)
            leaf.append(h)
        except LeafKpError:
            pass
    if not leaf:
        return None, f'考点 {word!r} resolve 零命中（KG 工具 add-leaf/alias 先补），绝不裸题入库'
    if len(leaf) > 1:
        return None, f'考点 {word!r} 多命中 {leaf}——不自动挑，题目包里写 id 消歧'
    return leaf[0], None


def ensure_tag(conn, domain, name):
    row = conn.execute('SELECT id FROM tag WHERE domain=? AND name=?', (domain, name)).fetchone()
    if row:
        return row[0]
    tid = 't' + uuid.uuid4().hex[:10]
    conn.execute('INSERT INTO tag(id,domain,name,status) VALUES (?,?,?,?)', (tid, domain, name, '在用'))
    return tid


def ingest_one(conn, item, idx, allow_dup, skip_review=False):
    """单题回流。返回 (qid, 错误清单|None, 等级 dict|None)。

    等级审在闸前先算（拒收的题也报等级，便于人看这批到底难在哪），
    工单只在真入库之后开（不给不存在的 qid 挂工单）。
    """
    errs = []
    blocks = item.get('blocks')
    if not isinstance(blocks, dict):
        return None, [f'items[{idx}] 缺 blocks（题面块流 v2）'], None
    grade = grade_item(blocks, item.get('source_kind'))

    # 考点 resolve（先做：执行阀要吃叶子 id）
    kp_words = item.get('kp') or []
    if isinstance(kp_words, str):
        kp_words = [kp_words]
    kp_ids, kp_map = [], {}
    for w in kp_words:
        kid, e = resolve_kp(conn, str(w))
        if e:
            errs.append(f'items[{idx}] {e}')
        else:
            kp_ids.append(kid)
            kp_map[str(w)] = kid
    kp_ids = list(dict.fromkeys(kp_ids))
    primary_word = item.get('primary_kp') or (kp_words[0] if kp_words else None)
    primary_id = kp_map.get(str(primary_word)) if primary_word is not None else None
    if primary_word is not None and primary_id is None and not errs:
        errs.append(f'items[{idx}] primary_kp={primary_word!r} 不在 kp 清单内')

    # 字典翻译
    qtype_code, e1 = dict_code(conn, 'qtype', item.get('qtype'))
    diff_code, e2 = dict_code(conn, 'difficulty', item.get('difficulty'))
    for e in (e1, e2):
        if e:
            errs.append(f'items[{idx}] {e}')

    # 血缘：mother_qid 必须真实存在
    mother = item.get('mother_qid')
    if mother:
        if not conn.execute('SELECT 1 FROM question WHERE id=?', (mother,)).fetchone():
            errs.append(f'items[{idx}] mother_qid={mother!r} 在库里不存在——血缘不许指空')
    src_kind = item.get('source_kind')
    if src_kind not in ('scan', 'manual', 'model', 'pipeline'):
        errs.append(f'items[{idx}] source_kind={src_kind!r} 非法（scan/manual/model/pipeline）')
    if src_kind in ('model', 'pipeline') and not (item.get('prov') or mother):
        errs.append(f'items[{idx}] 生成类必须带 prov（model_id/params/seed）或 mother_qid——DSL 出题路径必留档')

    # 执行阀五条（含块流校验+叶子闸复核）
    valve_item = {
        'blocks_json': blocks,
        'answer_blocks_json': item.get('answer_blocks'),
        'analysis_blocks_json': item.get('analysis_blocks'),
        'confidence': item.get('confidence'),
        'kp_ids': kp_ids,
        'primary_kp': primary_id,
        'reviewed': item.get('reviewed'),
        # --skip-review = 用户明说跳过审核，正是执行阀④「或用户明确说跳过审核才免」的口径
        'review_skipped_by_user': item.get('review_skipped_by_user') or skip_review,
    }
    ok, results = execution_valve(valve_item, conn)
    if not ok:
        errs += [f"items[{idx}] 执行阀{r['no']}·{r['name']}: {r['detail']}" for r in results if not r['ok']]

    # 相似前查（match_key 撞库）
    mk = item.get('match_key') or match_key_of(blocks)
    if mk:
        dup = conn.execute(
            'SELECT id FROM question WHERE match_key=? AND status!=?', (mk, '退役')).fetchone()
        if dup and not allow_dup:
            errs.append(f'items[{idx}] 相似前查撞库：match_key 与 {dup[0]} 相同——重复出题（--allow-dup 才放行）')

    if errs:
        return None, errs, grade

    qid = item.get('id') or f'q{datetime.now().strftime("%Y%m%d")}{uuid.uuid4().hex[:8]}'
    if conn.execute('SELECT 1 FROM question WHERE id=?', (qid,)).fetchone():
        return None, [f'items[{idx}] id={qid} 已存在——不静默覆盖'], grade

    conn.execute(
        'INSERT INTO question(id,blocks_json,answer_blocks_json,analysis_blocks_json,'
        'qtype_code,diff_code,pattern_id,source_kind,source_raw,prov_json,mother_qid,variant_op,'
        'match_key,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (qid,
         json.dumps(blocks, ensure_ascii=False),
         json.dumps(item['answer_blocks'], ensure_ascii=False) if item.get('answer_blocks') else None,
         json.dumps(item['analysis_blocks'], ensure_ascii=False) if item.get('analysis_blocks') else None,
         qtype_code, diff_code, item.get('pattern_id'),
         src_kind, item.get('source_raw'),
         json.dumps(item.get('prov'), ensure_ascii=False) if item.get('prov') else None,
         mother, item.get('variant_op'), mk, '草稿', now(), now()))
    for kid in kp_ids:
        conn.execute(
            'INSERT INTO question_kp(question_id,kp_id,is_primary,anchor_json) VALUES (?,?,?,?)',
            (qid, kid, 1 if kid == primary_id else 0,
             json.dumps({'stage': '回流', 'confidence': item.get('confidence')}, ensure_ascii=False)))
    for tg in item.get('tags') or []:
        tid = ensure_tag(conn, tg['domain'], tg['name'])
        conn.execute('INSERT OR IGNORE INTO question_tag(question_id,tag_id) VALUES (?,?)', (qid, tid))

    # 🔴 D-21：L2/L3 题照样进草稿，但挂一张待处理图审工单——上架由闸④卡住
    if grade['need_ticket'] and not skip_review:
        grade['ticket_id'] = open_review_ticket(conn, qid, grade)
    return qid, None, grade


def cmd_ingest(conn, args, dry=False):
    pack = json.loads(Path(args.pack).read_text(encoding='utf-8'))
    items = pack.get('items') or []
    if not items:
        sys.exit('🔴 题目包 items 为空')
    skip_review = bool(getattr(args, 'skip_review', False))
    ok_ids, all_errs, graded = [], [], []
    conn.execute('BEGIN')
    for i, item in enumerate(items):
        qid, errs, grade = ingest_one(conn, item, i, args.allow_dup, skip_review)
        graded.append((i, qid, grade, bool(errs)))
        if errs:
            all_errs += errs
        else:
            ok_ids.append(qid)
    rolled_back = dry or (all_errs and not args.partial)
    if rolled_back:
        conn.rollback()
    else:
        conn.commit()

    # ── D-21 等级审：逐题一行 ────────────────────────────────────────
    print('等级审（D-21 复杂度×源，纯机械判定）：')
    dist, n_ticket, skipped = {}, 0, []
    for i, qid, grade, rejected in graded:
        if grade is None:
            print(f'  · items[{i}] —          （无 blocks，判不了等级）')
            continue
        dist[grade['level']] = dist.get(grade['level'], 0) + 1
        mark = ''
        if grade['need_ticket']:
            if skip_review:
                skipped.append(qid or f'items[{i}]')
                mark = ' → 🔴 --skip-review：未开工单'
            elif rejected:
                mark = ' → 该题被闸拒收，未开工单'
            elif rolled_back:
                mark = ' → 全批回滚，工单同批撤销'
            elif grade.get('ticket_id'):
                mark = f' → 已开工单 #{grade["ticket_id"]}（图审·待处理）'
                n_ticket += 1
        elif grade['level'] == 1:
            mark = ' → 抽检（不拦上架）'
        print(f'  · items[{i}] {qid or "—":<18} {grade["name"]:<8}{grade["reason"]}{mark}')
    dist_txt = ' '.join(f'{LEVEL_NAME[lv]}×{dist[lv]}' for lv in sorted(dist))
    print(f'  等级分布：{dist_txt or "（无）"}｜自动开图审工单 {n_ticket} 张')
    if skipped:
        print('🔴🔴 --skip-review：用户明说跳过审核，以下 L2/L3 题**未开工单、未走等级审**，'
              '上架不再被闸④拦，风险由用户承担：' + ' '.join(skipped))

    print(f'{"干跑" if dry else "回流"}：{len(ok_ids)}/{len(items)} 过闸' +
          ('' if not all_errs else f'，{len(all_errs)} 条拒收：'))
    for e in all_errs:
        print('  ✗ ' + e)
    if ok_ids and not dry and (not all_errs or args.partial):
        print('入库（草稿）：' + ' '.join(ok_ids))
        if all_errs:
            print('⚠️ --partial：过闸的已入，拒收的如上——别当没看见')
    elif all_errs and not args.partial and not dry:
        print('🔴 全批回滚（默认全或无；要部分入加 --partial）')

    # ── 收尾：增量向量（③语意层跟着入库走）🔴 算不动只打印待补命令，绝不阻断入库 ──
    vec_note = 'off'
    if ok_ids and not dry and not rolled_back:
        if getattr(args, 'no_vec', False):
            print('· --no-vec：不算增量向量（③语意层搜不到这批，直到你手动 build）')
            vec_note = 'skip:--no-vec'
        else:
            _n, vec_note = autovec(conn, ok_ids, getattr(args, 'serve_port', None))

    detail = (f'ok={len(ok_ids)}/{len(items)} rej={len(all_errs)} '
              f'等级[{dist_txt}] 工单={n_ticket} 向量[{vec_note}]'
              + ('（--skip-review 跳过审核）' if skip_review else ''))
    return f'pack={args.pack}', detail, 0 if not all_errs else 1


def cmd_promote(conn, args):
    ids = []
    if args.ids:
        ids = [x.strip() for x in args.ids.split(',') if x.strip()]
    elif args.match:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM question WHERE id LIKE ? AND status='草稿'", (args.match,))]
    if not ids:
        sys.exit('🔴 promote：没有目标（--ids 或 --match）')
    n, blocked, skipped = 0, [], 0
    for qid in ids:
        row = conn.execute('SELECT status FROM question WHERE id=?', (qid,)).fetchone()
        if not row:
            print(f'  ✗ {qid} 不存在')
            skipped += 1
            continue
        if row[0] != '草稿':
            print(f'  · {qid} 状态={row[0]}，跳过')
            skipped += 1
            continue
        # 🔴 闸④（gates.assert_promotable）：还挂待处理审核工单的题不许上架——先审后上
        try:
            assert_promotable(conn, qid)
        except GateError as e:
            print(f'  ✗ {qid} 被闸④拦下：{e}')
            blocked.append(qid)
            continue
        conn.execute("UPDATE question SET status='上架', updated_at=? WHERE id=?", (now(), qid))
        n += 1
        print(f'  √ {qid} 草稿→上架')
    conn.commit()
    print(f'promote：{n}/{len(ids)} 草稿→上架'
          f'｜闸④拦下 {len(blocked)}｜非草稿或不存在 {skipped}')
    if blocked:
        print('🔴 被拦的题工单没处理完（tickets 看清单，ticket-done 处理后再 promote）：' + ' '.join(blocked))
    return (f'{len(ids)}个', f'promoted={n} blocked={len(blocked)} skipped={skipped}',
            0 if not blocked else 1)


# ── 审核工单原语（写动作归工具，页面只读 —— 与 D-14 待办同口径）────────
def cmd_tickets(conn, args):
    st = getattr(args, 'status', None) or '待处理'
    if st == '全部':
        rows = conn.execute(
            'SELECT id,kind,ref,status,note,created_at,done_at FROM review_ticket ORDER BY id').fetchall()
    else:
        rows = conn.execute(
            'SELECT id,kind,ref,status,note,created_at,done_at FROM review_ticket '
            'WHERE status=? ORDER BY id', (st,)).fetchall()
    print(f'审核工单（status={st}）：{len(rows)} 张')
    if rows:
        print(f'{"id":<6}{"kind":<8}{"status":<8}{"ref":<20}{"created_at":<21}note')
        for tid, kind, ref, status, note, created, done in rows:
            tail = str(note or '').replace('\n', '　｜　') + (f'（done_at={done}）' if done else '')
            print(f'{tid:<6}{kind:<8}{status:<8}{str(ref or "-"):<20}{str(created or "-"):<21}{tail}')
    return f'status={st}', f'rows={len(rows)}', 0


def cmd_ticket_done(conn, args):
    row = conn.execute(
        'SELECT id,kind,ref,status,note FROM review_ticket WHERE id=?', (args.id,)).fetchone()
    if not row:
        print(f'🔴 工单 #{args.id} 不存在')
        return f'id={args.id}', 'not_found', 1
    tid, kind, ref, status, note = row
    # 🔴 已处理/已驳回的工单不许再改（审核结论是留痕，不是草稿；要翻案另开工单）
    if status != '待处理':
        print(f'🔴 工单 #{tid} 当前 status={status}，不是「待处理」——已结的工单不许再改'
              f'（审核结论是留痕；要翻案请另开工单）。')
        return f'id={tid}', f'refused status={status}', 1
    new_status = '已驳回' if getattr(args, 'reject', False) else '已处理'
    new_note = note or ''
    if getattr(args, 'note', None):
        new_note = (new_note + '\n' if new_note else '') + f'[{new_status}] {args.note}'
    conn.execute('UPDATE review_ticket SET status=?, note=?, done_at=? WHERE id=?',
                 (new_status, new_note, now(), tid))
    conn.commit()
    print(f'工单 #{tid}（{kind}·ref={ref}）待处理 → {new_status}，done_at={now()}')
    left = conn.execute(
        "SELECT COUNT(*) FROM review_ticket WHERE ref=? AND status='待处理'", (ref,)).fetchone()[0]
    print(f'  该 ref 剩余待处理工单：{left} 张' + ('（可 promote 了）' if left == 0 else '（还上不了架）'))
    if new_status == '已驳回' and left == 0:
        # 🔴 闸④只认「待处理」：驳回=已结，它就不拦了。驳回的题必须显式处置，别让它顺着 promote 溜上架。
        print(f'  🔴 注意：闸④只拦「待处理」工单，{ref} 现在没有待处理单了 ⇒ promote 不会再被拦。'
              f'驳回意味着这题要重录/退役，请显式处置（改 status 或重开工单），别让它溜上架。')
    return f'id={tid}', f'{new_status} ref={ref} left={left}', 0


# ── patch-answer：答案补齐回写（2026-08-20 五步战役令窗B建）───────────────
def cmd_patch_answer(conn, args, dry=False):
    """给已入库题回写 answer_blocks（可带 analysis_blocks）。此前 answer_blocks 只有
    INSERT 通路没有回写通路——答案补齐批（先无答案态入库、事后集中解题）需要这条。

    口径：🔴 只补空不覆盖——已有答案的题必须 --force 显式放行（同 ingest 对已存在 id 的口径）；
    闸=validate_blocks(is_stem=False)+第二载体拒收（与执行阀闸③同一份 SECOND_CARRIERS）；
    缺省全或无，--partial 放行过闸子集；confidence<90 的题如实列出待人审，绝不静默。

    答案包格式：{"items":[{"id":"q…","answer_blocks":{v2块流},"analysis_blocks":{可选},
                  "confidence":95,"note":"实算闸=sympy恒等"}]}
    """
    pack = json.loads(Path(args.pack).read_text(encoding='utf-8'))
    items = pack.get('items') or []
    if not items:
        sys.exit('🔴 答案包 items 为空')
    ok_n, errs, low_conf = 0, [], []
    conn.execute('BEGIN')
    for i, item in enumerate(items):
        qid = item.get('id')
        where = f'items[{i}] id={qid}'
        if not qid:
            errs.append(f'items[{i}] 缺 id')
            continue
        dirty = [k for k in SECOND_CARRIERS if item.get(k) not in (None, '', [], {})]
        if dirty:
            errs.append(f'{where} 检出第二载体字段 {dirty}——答案只有 answer_blocks 一份')
            continue
        row = conn.execute('SELECT answer_blocks_json FROM question WHERE id=?', (qid,)).fetchone()
        if not row:
            errs.append(f'{where} 不存在')
            continue
        if row[0] and not getattr(args, 'force', False):
            errs.append(f'{where} 已有答案——不静默覆盖（--force 显式放行）')
            continue
        ans = item.get('answer_blocks')
        if not ans:
            errs.append(f'{where} 缺 answer_blocks')
            continue
        ok_b, es = validate_blocks(ans, is_stem=False)
        if not ok_b:
            errs.append(f'{where} 答案闸拒收：' + '；'.join(es))
            continue
        ana = item.get('analysis_blocks')
        if ana:
            ok_a, es_a = validate_blocks(ana, is_stem=False)
            if not ok_a:
                errs.append(f'{where} 解析闸拒收：' + '；'.join(es_a))
                continue
        conn.execute(
            'UPDATE question SET answer_blocks_json=?, '
            'analysis_blocks_json=COALESCE(?, analysis_blocks_json), updated_at=? WHERE id=?',
            (json.dumps(ans, ensure_ascii=False),
             json.dumps(ana, ensure_ascii=False) if ana else None, now(), qid))
        if (item.get('confidence') or 100) < 90:
            low_conf.append(qid)
        ok_n += 1
    rolled = dry or bool(errs and not args.partial)
    if rolled:
        conn.rollback()
    else:
        conn.commit()
    tag = '干跑' if dry else ('部分入' if errs and args.partial else '全入')
    print(f'patch-answer[{tag}]：{ok_n}/{len(items)} 过闸回写' + ('（已回滚未写库）' if rolled else ''))
    if low_conf:
        print(f'⚠ 低置信（<90）待人审 {len(low_conf)} 题：' + ' '.join(low_conf))
    for e in errs:
        print('  ✗', e)
    return (f'{len(items)}题', f'ok={ok_n} err={len(errs)} low={len(low_conf)} rolled={int(rolled)}',
            0 if not errs else 1)


def main():
    ap = argparse.ArgumentParser(description='自产题回流入库轻通路（过三闸才算出完）')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('ingest', 'check'):
        s = sub.add_parser(name)
        s.add_argument('pack')
        s.add_argument('--partial', action='store_true', help='过闸的入、拒收的列清单（默认全或无）')
        s.add_argument('--allow-dup', action='store_true', help='match_key 撞库仍放行（变式同题面时显式用）')
        s.add_argument('--skip-review', action='store_true',
                       help='🔴 用户明说跳过审核：L2/L3 不开工单（执行阀④口径），报告里大字标明')
        s.add_argument('--no-vec', dest='no_vec', action='store_true',
                       help='入库后不算增量向量（缺省会算：serve 在走 serve，不在回落冷载；'
                            '算不动只打印待补命令，不阻断入库）')
        s.add_argument('--serve-port', dest='serve_port', type=int,
                       help='常驻 embed serve 端口（缺省 4315／环境变量 EMBED_SERVE_PORT）')
    for name in ('patch-answer', 'patch-check'):
        s = sub.add_parser(name, help='答案补齐回写（patch-check=干跑不写库）')
        s.add_argument('pack')
        s.add_argument('--partial', action='store_true', help='过闸的写、拒收的列清单（默认全或无）')
        s.add_argument('--force', action='store_true', help='已有答案也覆盖（缺省不静默覆盖）')
    s = sub.add_parser('promote')
    s.add_argument('--ids'); s.add_argument('--match')
    s = sub.add_parser('tickets')
    s.add_argument('--status', default='待处理', choices=['待处理', '已处理', '已驳回', '全部'])
    s = sub.add_parser('ticket-done')
    s.add_argument('--id', type=int, required=True)
    s.add_argument('--note', help='审核结论（追加进 note，不覆盖机械判定原文）')
    s.add_argument('--reject', action='store_true', help='驳回（→已驳回）而非通过（→已处理）')
    args = ap.parse_args()

    t0 = time.time()
    conn = open_db(args.db)
    try:
        if args.cmd == 'ingest':
            digest, detail, code = cmd_ingest(conn, args, dry=False)
        elif args.cmd == 'check':
            digest, detail, code = cmd_ingest(conn, args, dry=True)
        elif args.cmd == 'patch-answer':
            digest, detail, code = cmd_patch_answer(conn, args, dry=False)
        elif args.cmd == 'patch-check':
            digest, detail, code = cmd_patch_answer(conn, args, dry=True)
        elif args.cmd == 'tickets':
            digest, detail, code = cmd_tickets(conn, args)
        elif args.cmd == 'ticket-done':
            digest, detail, code = cmd_ticket_done(conn, args)
        else:
            digest, detail, code = cmd_promote(conn, args)
        log_skill(conn, args.cmd, digest, '成功' if code == 0 else '失败', detail, t0)
    finally:
        conn.close()
    sys.exit(code)


if __name__ == '__main__':
    main()
