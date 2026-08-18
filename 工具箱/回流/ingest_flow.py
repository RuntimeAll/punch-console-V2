# -*- coding: utf-8 -*-
"""自产题回流入库轻通路（PRD-002 交付件 #2）——生产线出题入 question 的唯一门。

飞轮铁律落点（PRD-002 §1）：
  ①出题必回流：blocks v2 + 血缘（mother_qid/variant_op/prov）+ 考点叶子 + source_kind；
  ②过三闸才算出完：块流校验器 + 执行阀五条 + 考点叶子闸（gates.py，违例拒收不静默）；
  ③出题前必查库：本通路兜底做相似前查（match_key 撞库→拒，除非 --allow-dup）；
  ④每次执行落 skill_log。

用法：
  python ingest_flow.py ingest 题目包.json [--partial] [--allow-dup]
  python ingest_flow.py promote --ids q2026...,q2026...   # 草稿→上架（进入交付才可见，D-9）
  python ingest_flow.py promote --match 前缀%             # 按 id LIKE 批量
  python ingest_flow.py check 题目包.json                  # 只过闸不入库（干跑）

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
from gates import execution_valve, assert_leaf_kp, LeafKpError  # noqa: E402

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


def ingest_one(conn, item, idx, allow_dup):
    """单题回流。返回 (qid, None) 或 (None, 错误清单)。"""
    errs = []
    blocks = item.get('blocks')
    if not isinstance(blocks, dict):
        return None, [f'items[{idx}] 缺 blocks（题面块流 v2）']

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
        'review_skipped_by_user': item.get('review_skipped_by_user'),
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
        return None, errs

    qid = item.get('id') or f'q{datetime.now().strftime("%Y%m%d")}{uuid.uuid4().hex[:8]}'
    if conn.execute('SELECT 1 FROM question WHERE id=?', (qid,)).fetchone():
        return None, [f'items[{idx}] id={qid} 已存在——不静默覆盖']

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
    return qid, None


def cmd_ingest(conn, args, dry=False):
    pack = json.loads(Path(args.pack).read_text(encoding='utf-8'))
    items = pack.get('items') or []
    if not items:
        sys.exit('🔴 题目包 items 为空')
    ok_ids, all_errs = [], []
    conn.execute('BEGIN')
    for i, item in enumerate(items):
        qid, errs = ingest_one(conn, item, i, args.allow_dup)
        if errs:
            all_errs += errs
        else:
            ok_ids.append(qid)
    if dry or (all_errs and not args.partial):
        conn.rollback()
    else:
        conn.commit()

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
    return (f'pack={args.pack}', f'ok={len(ok_ids)}/{len(items)} rej={len(all_errs)}',
            0 if not all_errs else 1)


def cmd_promote(conn, args):
    ids = []
    if args.ids:
        ids = [x.strip() for x in args.ids.split(',') if x.strip()]
    elif args.match:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM question WHERE id LIKE ? AND status='草稿'", (args.match,))]
    if not ids:
        sys.exit('🔴 promote：没有目标（--ids 或 --match）')
    n = 0
    for qid in ids:
        row = conn.execute('SELECT status FROM question WHERE id=?', (qid,)).fetchone()
        if not row:
            print(f'  ✗ {qid} 不存在')
            continue
        if row[0] != '草稿':
            print(f'  · {qid} 状态={row[0]}，跳过')
            continue
        conn.execute("UPDATE question SET status='上架', updated_at=? WHERE id=?", (now(), qid))
        n += 1
    conn.commit()
    print(f'promote：{n}/{len(ids)} 草稿→上架')
    return f'{len(ids)}个', f'promoted={n}', 0


def main():
    ap = argparse.ArgumentParser(description='自产题回流入库轻通路（过三闸才算出完）')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('ingest', 'check'):
        s = sub.add_parser(name)
        s.add_argument('pack')
        s.add_argument('--partial', action='store_true', help='过闸的入、拒收的列清单（默认全或无）')
        s.add_argument('--allow-dup', action='store_true', help='match_key 撞库仍放行（变式同题面时显式用）')
    s = sub.add_parser('promote')
    s.add_argument('--ids'); s.add_argument('--match')
    args = ap.parse_args()

    t0 = time.time()
    conn = open_db(args.db)
    try:
        if args.cmd == 'ingest':
            digest, detail, code = cmd_ingest(conn, args, dry=False)
        elif args.cmd == 'check':
            digest, detail, code = cmd_ingest(conn, args, dry=True)
        else:
            digest, detail, code = cmd_promote(conn, args)
        log_skill(conn, args.cmd, digest, '成功' if code == 0 else '失败', detail, t0)
    finally:
        conn.close()
    sys.exit(code)


if __name__ == '__main__':
    main()
