# -*- coding: utf-8 -*-
"""答案补齐批（PRD-008 段① 转正件）——缺答清单 → 分批解题物料 → 答案包 + 覆盖率对账。

来源：2026-08-20 窗G 浙教出卷战役 scratchpad「主线-dump174.py」+「主线-构建答案包.py」转正。
🔴 独立新文件：不 import 也不改 `ingest_flow.py`——回写那一段仍走 ingest_flow 的 patch-answer 闸，
   本工具只负责「出物料」与「收答案打包对账」，一行都不写库。

三段接力（中间那段是人/agent 的活，由 skill「出卷流水线」的双盲+裁判提示词承载）：
    ① dump  ：方案 JSON（或 --ids）的缺答题 → 分批物料 JSON（题面 blocks 原样）+ 批次表
    ②（解题）：解题员/核对员双盲互不通气 → 不一致或低置信送裁判员强制 python 实算 → 定案 JSON
    ③ pack  ：定案 JSON + 物料 → 答案包（patch-answer 契约）+ 覆盖率对账（缺一题都如实报）
    ④ check ：回写后复查覆盖率（读库看 answer_blocks_json 到位没）

用法（--db 缺省 = <v2根>/知识库/kb.db；沙盘测试传副本）：
  python 工具箱/回流/answer_batch.py dump --plan 试验场/xxx/方案.json --out-dir 试验场/xxx/解题物料 [--batches 8]
  python 工具箱/回流/answer_batch.py pack --result 定案.json --material 试验场/xxx/解题物料/批*.json --out 答案包.json
  python 工具箱/回流/answer_batch.py check --plan 试验场/xxx/方案.json [--db 副本.db]
  # 回写（本工具不做，照抄这行）：
  python 工具箱/回流/ingest_flow.py --db 知识库/kb.db patch-check 答案包.json   # 先干跑
  python 工具箱/回流/ingest_flow.py --db 知识库/kb.db patch-answer 答案包.json

定案 JSON 形（workflow/子 agent 汇总输出，两种壳都吃）：
  {"result": {"batches"|"vols": [{"confirmed": [item...], "refereed": [item...]}]}}
  或直接 {"batches": [...]} / {"items": [item...]}
  item = {"id":"q…", "final":"最终答案（md）", "steps":["解析行1","解析行2"],
          "confidence":95, "verified":true, "method":"sympy 实算", "note":"…"}
  🔴 verified 不为真的一律压进低置信档（<90）——没实算自证的答案不许冒充高置信。
"""
import argparse
import glob
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
PLAN_CONTRACT = 'paper-plan/v1'
MATERIAL_CONTRACT = 'answer-material/v1'
LOW_CONF = 90            # 与 ingest_flow.patch-answer 的低置信线同口径


def die(msg):
    sys.exit(f'🔴 {msg}')


def resolve(p):
    q = Path(p)
    return q if q.is_absolute() else (ROOT / q)


def db_ro(db):
    """🔴 只读连接，用完立刻关（SQLite 单写者，写窗口归主线）。"""
    return sqlite3.connect(f'file:{resolve(db).as_posix()}?mode=ro', uri=True)


def load_plan(fp):
    plan = json.loads(resolve(fp).read_text(encoding='utf-8'))
    if plan.get('contract') != PLAN_CONTRACT:
        die(f'方案契约 {plan.get("contract")!r} 不是 {PLAN_CONTRACT}——先用 draft_paper.py 出方案')
    return plan


def plan_index(plan):
    """qid → 落在哪几套的哪几题（物料带上，解题时能说清出处）。"""
    idx = {}
    for st in plan['sets']:
        n = 0
        for s in st['sections']:
            for d in s['detail']:
                n += 1
                idx.setdefault(d['qid'], []).append(f'{st["key"]}·{st["seq"]}#{n}')
    return idx


# ══════════════════════════════════════════════════════════════════════
# ① dump —— 缺答题分批出物料
# ══════════════════════════════════════════════════════════════════════
def cmd_dump(args):
    ids, idx = [], {}
    if args.plan:
        plan = load_plan(args.plan)
        ids = list(plan['need_answers'])
        idx = plan_index(plan)
    if args.ids:
        ids += [x for x in args.ids.replace(',', ' ').split() if x]
    ids = sorted(dict.fromkeys(ids))              # 去重且稳定
    if not ids:
        print('缺答清单为空——方案里的题全有答案，本段跳过')
        return 0

    conn = db_ro(args.db)
    qt = dict(conn.execute("SELECT code,label FROM dict_item WHERE domain='qtype'"))
    df = dict(conn.execute("SELECT code,label FROM dict_item WHERE domain='difficulty'"))
    items, missing, has_ans, nfig = [], [], [], 0
    for qid in ids:
        r = conn.execute('SELECT source_raw, qtype_code, diff_code, blocks_json,'
                         ' answer_blocks_json IS NOT NULL FROM question WHERE id=?',
                         (qid,)).fetchone()
        if not r:
            missing.append(qid)
            continue
        if r[4]:
            has_ans.append(qid)
            continue
        b = json.loads(r[3])
        figs = [c for row in b.get('rows', []) for c in row.get('cells', [])
                if c.get('type') == 'figure']
        if figs:
            nfig += 1
        items.append({'id': qid, 'source_raw': r[0], 'qtype': qt.get(r[1], r[1]),
                      'difficulty': df.get(r[2], r[2]), 'has_figure': bool(figs),
                      'in_papers': idx.get(qid, []), 'blocks': b})
    conn.close()
    if missing:
        die(f'{len(missing)} 个 qid 库里不存在：{missing[:10]}——方案与库对不上，别蒙着解题')
    if has_ans:
        print(f'⚠ {len(has_ans)} 题库里已有答案，跳过不再出物料（方案是旧的就重跑 draft_paper）',
              file=sys.stderr)
    if not items:
        print('没有需要解的题（全部已有答案）')
        return 0

    out_dir = resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nb = args.batches or max(1, (len(items) + args.per - 1) // args.per)
    per = (len(items) + nb - 1) // nb
    batches = []
    for i in range(nb):
        chunk = items[i * per:(i + 1) * per]
        if not chunk:
            continue
        fp = out_dir / f'批{i + 1}.json'
        fp.write_text(json.dumps({'contract': MATERIAL_CONTRACT, 'batch': f'批{i + 1}',
                                  'n': len(chunk), 'items': chunk},
                                 ensure_ascii=False), encoding='utf-8')
        batches.append({'name': f'批{i + 1}', 'file': str(fp), 'n': len(chunk),
                        'ids': [c['id'] for c in chunk]})
    tp = out_dir / '_批次表.json'          # 🔴 下划线打头：不被 pack 的 批*.json 通配误吃
    tp.write_text(json.dumps(batches, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'缺答 {len(items)} 题 → {len(batches)} 批（每批 ≤{per}）｜含 figure 块 {nfig} 题'
          + ('（🔴 图题解题员看不见图，须走图题专线或人裁）' if nfig else '（无图题，可直接派解题）'))
    print('批次表 →', tp)
    return 0


# ══════════════════════════════════════════════════════════════════════
# ② pack —— 定案 → 答案包 + 覆盖率对账
# ══════════════════════════════════════════════════════════════════════
def collect(result):
    """吃三种壳：{'result':{'batches'|'vols':[{confirmed,refereed}]}} / {'batches':…} / {'items':…}"""
    if isinstance(result, dict) and 'result' in result:
        result = result['result']
    out, dup = {}, []
    if isinstance(result, dict) and result.get('items'):
        groups = [{'confirmed': result['items']}]
    else:
        groups = (result.get('batches') or result.get('vols') or []) if isinstance(result, dict) else result
    for g in groups:
        for a in (g.get('confirmed') or []) + (g.get('refereed') or []):
            if a['id'] in out:
                dup.append(a['id'])
            out[a['id']] = a
    return out, dup


def to_blocks(a):
    """final → answer_blocks；steps → analysis_blocks（块流 v2，role 块级）。"""
    final = str(a.get('final') or '').strip()
    if not final:
        return None, None
    ans = {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': '答案', 'md': final}]}]}
    steps = [str(s).strip() for s in (a.get('steps') or []) if str(s).strip()]
    ana = ({'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': '解析', 'md': s}]}
                             for s in steps]} if steps else None)
    return ans, ana


def cmd_pack(args):
    expect = {}
    files = []
    for pat in args.material:
        hit = sorted(glob.glob(str(resolve(pat))))
        if not hit:
            die(f'物料没匹配到文件：{pat}')
        files += hit
    used_files = []
    for mf in files:
        d = json.loads(Path(mf).read_text(encoding='utf-8'))
        if not isinstance(d, dict) or d.get('contract') != MATERIAL_CONTRACT:
            print(f'  跳过非物料件（契约不是 {MATERIAL_CONTRACT}）：{Path(mf).name}', file=sys.stderr)
            continue
        used_files.append(Path(mf).name)
        for it in d['items']:
            expect[it['id']] = it.get('source_raw', '')
    if not expect:
        die(f'没吃到任何物料件（契约须为 {MATERIAL_CONTRACT}）：{[Path(f).name for f in files]}')
    print(f'物料 {len(used_files)} 件 / 应交 {len(expect)} 题')

    got, dup = collect(json.loads(resolve(args.result).read_text(encoding='utf-8')))
    missing = [i for i in expect if i not in got]
    extra = [i for i in got if i not in expect]
    items, low, empty = [], [], []
    for qid in expect:                              # 🔴 按物料次序出包，稳定可比对
        a = got.get(qid)
        if not a:
            continue
        ans, ana = to_blocks(a)
        if ans is None:
            empty.append(qid)
            continue
        conf = int(a.get('confidence') or 0)
        if not a.get('verified'):
            conf = min(conf, LOW_CONF - 5)          # 没实算自证的一律压进低置信档
        it = {'id': qid, 'answer_blocks': ans, 'confidence': conf,
              'note': (a.get('method') or '') + ('；' + a['note'] if a.get('note') else '')}
        if ana:
            it['analysis_blocks'] = ana
        if conf < LOW_CONF:
            low.append(qid)
        items.append(it)

    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'说明': '答案补齐批（双盲+裁判定案）', 'items': items},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'定案 {len(items)}/{len(expect)}｜缺 {len(missing)}｜多余 {len(extra)}'
          f'｜重复 {len(dup)}｜空答案 {len(empty)}｜低置信(<{LOW_CONF}) {len(low)}')
    if missing:
        print('🔴 没交答案的题：', ' '.join(f'{i}({expect[i]})' for i in missing[:20]))
    if extra:
        print('⚠ 物料之外的多余定案（不入包）：', ' '.join(extra[:20]), file=sys.stderr)
    if empty:
        print('🔴 final 为空的定案：', ' '.join(empty[:20]))
    if low:
        print(f'⚠ 低置信待人审：', ' '.join(low[:20]))
    print('包 →', out)
    print(f'回写：python 工具箱/回流/ingest_flow.py --db 知识库/kb.db patch-check {out.name} → 干跑绿了再 patch-answer')
    return 0 if not (missing or empty) else 1


# ══════════════════════════════════════════════════════════════════════
# ③ check —— 回写后覆盖率复查（读库）
# ══════════════════════════════════════════════════════════════════════
def cmd_check(args):
    ids = []
    if args.plan:
        plan = load_plan(args.plan)
        ids = [d['qid'] for st in plan['sets'] for s in st['sections'] for d in s['detail']]
    if args.ids:
        ids += [x for x in args.ids.replace(',', ' ').split() if x]
    ids = sorted(dict.fromkeys(ids))
    if not ids:
        die('没给要查的题（--plan 或 --ids）')
    conn = db_ro(args.db)
    rows = {r[0]: r[1] for r in conn.execute(
        'SELECT id, answer_blocks_json IS NOT NULL FROM question WHERE id IN (%s)'
        % ','.join('?' * len(ids)), ids)}
    conn.close()
    absent = [i for i in ids if i not in rows]
    noans = [i for i in ids if rows.get(i) == 0]
    print(f'方案用题 {len(ids)}｜有答案 {len(ids) - len(noans) - len(absent)}'
          f'｜缺答案 {len(noans)}｜库里没有 {len(absent)}')
    if noans:
        print('缺答案：', ' '.join(noans[:40]) + (' …' if len(noans) > 40 else ''))
    if absent:
        print('🔴 库里不存在：', ' '.join(absent[:20]))
    return 0 if not (noans or absent) else 1


def main():
    ap = argparse.ArgumentParser(description='答案补齐批：缺答清单→物料→答案包→对账（不写库）')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('dump', help='缺答题分批出解题物料')
    s.add_argument('--plan'); s.add_argument('--ids')
    s.add_argument('--out-dir', required=True)
    s.add_argument('--batches', type=int, help='分几批（与 --per 二选一）')
    s.add_argument('--per', type=int, default=25, help='每批题数上限（缺省 25）')
    s = sub.add_parser('pack', help='定案 JSON + 物料 → 答案包 + 覆盖率对账')
    s.add_argument('--result', required=True)
    s.add_argument('--material', action='append', required=True, help='物料文件（可 glob，可多次）')
    s.add_argument('--out', required=True)
    s = sub.add_parser('check', help='读库复查覆盖率')
    s.add_argument('--plan'); s.add_argument('--ids')
    args = ap.parse_args()
    sys.exit({'dump': cmd_dump, 'pack': cmd_pack, 'check': cmd_check}[args.cmd](args))


if __name__ == '__main__':
    main()
