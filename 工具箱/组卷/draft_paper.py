# -*- coding: utf-8 -*-
"""选题器（PRD-008 段① 转正件）——配方 JSON 驱动的五维取题，只读库、只出方案。

来源：2026-08-20 窗G 浙教出卷战役 scratchpad「主线-选题器v4.py」+「主线-浙教明细.py」，
逻辑一比一转正（选题次序完全复现 v4），把三处写死项参数化：配方（RECIPES/META）、库路径、产出路径。

在产线里的位置（认知/业务流程.md §三）：
    KG/录题 → question 入库 → **本工具选题出方案 JSON** → answer_batch 补缺答 →
    paper_run（assemble→render-pack→双 PDF→机器验页）→ 挂账。

🔴 纪律：
  · **只读库**（mode=ro URI），一行都不写——方案是文件，落库是 paper_run 的事；
  · **确定性**：池按 (使用级优先, qid) 全序排定，轮转起点由配方顺序决定，无随机数——
    同库同配方重跑必得同卷（战役 10 套即用本次序产出）；
  · **五维取题**：单元 × 题型槽 × 难度 × 考点(去重上限) × 版本使用级；
  · **三级使用级绝不取**（配方 pool.tier_exclude，池构建期就滤掉，出口再验一遍）；
  · **全局互不重题**：一个 used 集横跨所有套，某套中途干涸则整套回滚（占用不留残渣）；
  · **格干涸如实停产**：某格取不到就该配方停产并记「哪个槽×哪个难度干了」，绝不硬凑；
  · **降档替补留痕**：配方降档阶梯就近顶位，逐题写 want/got，逐套汇总替补清单进命题明细。

用法（--db 缺省 = <v2根>/知识库/kb.db；沙盘测试传副本库）：
  python 工具箱/组卷/draft_paper.py --recipe 工具箱/组卷/配方/浙教U1.json \
      --recipe 工具箱/组卷/配方/浙教U2.json --recipe 工具箱/组卷/配方/浙教MIX.json \
      --out-plan 试验场/xxx/方案.json --out-md 产物/验收/xxx/命题明细.md [--db 副本.db] [--max-sets N]

多配方 = 轮转出卷（U1→U2→MIX→U1…）直到全部停产；单配方 = 只出该类直到停产。
输出路径相对时按 **v2 根** 解析（老货架 717 行绝对路径全断的教训）。
"""
import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
PLAN_CONTRACT = 'paper-plan/v1'
RECIPE_CONTRACT = 'paper-recipe/v1'
CN = '一二三四五六七八九十'

# 题型（dict_item.qtype 标签）→ 配方里的题型槽。配方可用 qtype_slot 覆盖。
QTYPE_SLOT = {'选择题': '选择', '填空题': '填空', '解答题': '解答',
              '计算题': '解答', '应用题': '解答', '作图题': '解答'}


def die(msg):
    sys.exit(f'🔴 {msg}')


def resolve_out(p):
    """相对路径按 v2 根解析（绝对路径原样用，沙盘/临时目录才该给绝对）。"""
    q = Path(p)
    return q if q.is_absolute() else (ROOT / q)


# ══════════════════════════════════════════════════════════════════════
# 配方装载 + 配方闸
# ══════════════════════════════════════════════════════════════════════
def load_recipe(path):
    fp = resolve_out(path)
    if not fp.exists():
        die(f'配方不存在：{fp}')
    r = json.loads(fp.read_text(encoding='utf-8'))
    if r.get('_契约') != RECIPE_CONTRACT:
        die(f'{fp.name} 契约 {r.get("_契约")!r} 不是 {RECIPE_CONTRACT}——配方格式变了就该显式改契约号')
    errs = []
    for k in ('id', 'key', 'title', 'units', 'full_score', 'duration_min',
              'artifact', 'pool', 'kp_cap', '降档阶梯', 'layout', 'sections'):
        if k not in r:
            errs.append(f'缺键 {k}')
    if 'exclude_qids' in r and not isinstance(r['exclude_qids'], list):
        errs.append('exclude_qids 必须是 qid 数组（常驻排除清单，如泄答案闸拦下的题）')
    if errs:
        die(f'{fp.name} 配方闸拒收：' + '；'.join(errs))

    total = 0
    for i, s in enumerate(r['sections']):
        n = sum(c for _, c in s['mix'])
        sc = s['score']
        if isinstance(sc, list):
            if len(sc) != n:
                errs.append(f'sections[{i}] {s["name"]}：难度配比合计 {n} 题，'
                            f'但 score 数组 {len(sc)} 个分值——题数与分值必须一一对位')
            total += sum(sc)
        else:
            total += sc * n
    if total != r['full_score']:
        errs.append(f'满分守恒闸：逐题分合计 {total} ≠ full_score {r["full_score"]}'
                    f'——凡"拍平"必配守恒闸，对不上拒收')
    if errs:
        die(f'{fp.name} 配方闸拒收 {len(errs)} 条：\n' + '\n'.join('  ✗ ' + e for e in errs))
    r['_file'] = str(fp)
    return r


def unify_pool_cfg(recipes):
    """多配方共用一个池：pool 配置必须一致（不一致=两套口径，静默取不同的题）。"""
    base = recipes[0]['pool']
    for r in recipes[1:]:
        if r['pool'] != base:
            die(f'配方 {r["id"]} 的 pool 配置与 {recipes[0]["id"]} 不一致——'
                f'同一轮出卷共用一个题池，两套口径必然静默取到不同的题')
    return base


# ══════════════════════════════════════════════════════════════════════
# 建池（五维中的 单元/槽/难度 做键，使用级做序，考点做上限）
# ══════════════════════════════════════════════════════════════════════
def build_pool(conn, cfg, qtype_slot, exclude_qids=()):
    qt = dict(conn.execute("SELECT code,label FROM dict_item WHERE domain='qtype'"))
    df = dict(conn.execute("SELECT code,label FROM dict_item WHERE domain='difficulty'"))
    kpname = dict(conn.execute('SELECT id,name FROM kp'))
    prefixes = cfg['unit_kp_prefix']            # 单元 → kp_id 前缀
    status = list(cfg['status'])
    order = list(cfg['tier_order'])
    exclude = list(cfg['tier_exclude'])

    like = ' OR '.join('qk.kp_id LIKE ?' for _ in prefixes)
    sql = (
        "SELECT q.id, qk.kp_id, q.qtype_code, q.diff_code,"
        " json_extract(q.prov_json,'$.版本使用级'), q.answer_blocks_json IS NOT NULL, q.source_raw"
        " FROM question q JOIN question_kp qk ON qk.question_id=q.id AND qk.is_primary=1"
        f" WHERE q.status IN ({','.join('?' * len(status))}) AND q.diff_code IS NOT NULL"
        f" AND ({like})"
        " AND json_extract(q.prov_json,'$.版本使用级') IS NOT NULL")
    params = status + [p + '%' for p in prefixes.values()]

    pool = defaultdict(list)
    stat = {'扫描': 0, '排除三级': 0, '题型无对应槽': 0, '点名排除': 0, '入池': 0}
    unknown_tier, noslot = set(), defaultdict(int)
    exclude_qids = set(exclude_qids)
    for qid, kp, qc, dc, tier, has_ans, sr in conn.execute(sql, params):
        stat['扫描'] += 1
        if qid in exclude_qids:
            stat['点名排除'] += 1
            continue
        tier = str(tier)
        if any(tier.startswith(x) for x in exclude):
            stat['排除三级'] += 1
            continue
        pri = next((i for i, t in enumerate(order) if tier.startswith(t)), None)
        if pri is None:
            unknown_tier.add(tier)
            continue
        slot = qtype_slot.get(qt.get(qc))
        if not slot:
            stat['题型无对应槽'] += 1
            noslot[qt.get(qc, qc)] += 1
            continue
        unit = next((u for u, p in prefixes.items() if kp.startswith(p)), None)
        if unit is None:
            die(f'题 {qid} 的考点 {kp} 不属于任何配方单元——SQL 与 unit_kp_prefix 走岔了')
        src = sr.split('·')[1] if '·' in sr else (sr or '')[:8]
        pool[(unit, slot, df.get(dc))].append(
            {'qid': qid, 'kp': kp, 'kpn': kpname.get(kp, kp), 'pri': pri, 'tier': tier,
             'ans': bool(has_ans), 'src': src, 'diff': df.get(dc), 'slot': slot, 'unit': unit})
        stat['入池'] += 1
    if unknown_tier:
        die(f'池里有未知版本使用级 {sorted(unknown_tier)}（配方 tier_order={order}／'
            f'tier_exclude={exclude} 都没覆盖）——不认识的级别绝不静默放行')
    # 🔴 确定性：使用级优先（一级在前），同级按 qid 字典序——全序，无并列
    for k in pool:
        pool[k].sort(key=lambda r: (r['pri'], r['qid']))
    return pool, stat, dict(noslot)


# ══════════════════════════════════════════════════════════════════════
# 取题：单元轮转 → 考点上限 → 降档阶梯
# ══════════════════════════════════════════════════════════════════════
def take(pool, used, units, slot, diff, kp_cnt, turn, ladder, kp_cap):
    """取一题，返回 (rec, 实际难度)；取不到返回 (None, None)。最多试 3 档（原档+两级）。"""
    d = diff
    for _ in range(3):
        for i in range(len(units)):
            u = units[(turn + i) % len(units)]
            for cap in kp_cap:
                for r in pool[(u, slot, d)]:
                    if r['qid'] in used or kp_cnt[r['kp']] >= cap:
                        continue
                    used.add(r['qid'])
                    kp_cnt[r['kp']] += 1
                    return r, d
        d = ladder.get(d)
        if d is None or d == diff:
            break
    return None, None


def build_set(recipe, pool, used, turn0):
    """按配方出一套；某格干涸返回 (None, '槽×难度 干涸')。"""
    kp_cnt = defaultdict(int)
    ladder, kp_cap = recipe['降档阶梯'], list(recipe['kp_cap'])
    secs_out, subs, picked = [], [], []
    turn = turn0
    for sec in recipe['sections']:
        rows = []
        for diff, n in sec['mix']:
            for _ in range(n):
                r, got = take(pool, used, recipe['units'], sec['slot'], diff,
                              kp_cnt, turn, ladder, kp_cap)
                turn += 1
                if r is None:
                    return None, f'{sec["slot"]}×{diff} 干涸'
                if got != diff:
                    subs.append(f'{sec["slot"]}{diff}位以{got}替补')
                rec = dict(r)
                rec['want'] = diff
                rec['got'] = got
                rows.append(rec)
                picked.append(rec)
        secs_out.append({'sec': sec, 'rows': rows})
    return {'secs': secs_out, 'subs': subs, 'picked': picked}, None


# ══════════════════════════════════════════════════════════════════════
# 出方案（含渲染 layout：paper_run 直接吃，不再第二处配版式）
# ══════════════════════════════════════════════════════════════════════
def make_set_json(recipe, no, built):
    title = f"{recipe['title']}（{CN[no - 1]}）" if no <= len(CN) else f"{recipe['title']}（{no}）"
    lay_secs, sections = [], []
    for so in built['secs']:
        sec, rows = so['sec'], so['rows']
        score = sec['score']
        item_scores = list(score) if isinstance(score, list) else [score] * len(rows)
        lay_secs.append({
            'name': sec['name'], 'score_note': sec.get('score_note'),
            'slot': sec['render_slot'], 'grid': sec.get('grid', 'block'),
            'gap': sec.get('gap', 0), 'gap_each': sec.get('gap_each', 0),
            'ans_cols': sec.get('ans_cols', 1), 'item_scores': item_scores,
            'show_item_score': bool(sec.get('show_item_score'))})
        sections.append({
            'name': sec['name'], 'slot': sec['slot'], 'score': score,
            'qids': [r['qid'] for r in rows],
            'detail': [{'qid': r['qid'], 'kp': r['kpn'], 'kp_id': r['kp'], 'diff': r['diff'],
                        'unit': r['unit'], 'src': r['src'],
                        'tier': recipe['pool']['tier_order'][r['pri']],
                        'tier_raw': r['tier'], 'has_answer': r['ans'],
                        'want': r['want'], 'sub': r['want'] != r['got']}
                       for r in rows]})
    layout = dict(recipe['layout'])
    layout['full_score'] = recipe['full_score']
    layout['duration_min'] = recipe['duration_min']
    layout['sections'] = lay_secs
    return {
        'recipe': recipe['id'], 'key': recipe['key'], 'seq': no, 'title': title,
        'artifact_name': f"{recipe['artifact']['name_prefix']}·{no}",
        'artifact_kind': recipe['artifact'].get('kind', '专项卷'),
        'source_line': recipe['artifact'].get('source_line'),
        'paper_kind': recipe['artifact'].get('paper_kind', '专项卷'),
        'full': recipe['full_score'], 'dur': recipe['duration_min'],
        'subs': built['subs'], 'layout': layout, 'sections': sections}


def gate_plan(plan, cfg):
    """出口三闸：三级零混入 / 全局互不重题 / 逐套题数与分值对位。"""
    errs = []
    seen = {}
    for st in plan['sets']:
        n = 0
        for s in st['sections']:
            n += len(s['qids'])
            for d in s['detail']:
                if any(str(d['tier_raw']).startswith(x) for x in cfg['tier_exclude']):
                    errs.append(f'{st["title"]} 混入排除级题 {d["qid"]}（{d["tier_raw"]}）')
                if d['qid'] in seen:
                    errs.append(f'题 {d["qid"]} 重复出现：{seen[d["qid"]]} 与 {st["title"]}')
                seen[d['qid']] = st['title']
        scores = [x for s in st['layout']['sections'] for x in s['item_scores']]
        if len(scores) != n:
            errs.append(f'{st["title"]} 题数 {n} ≠ 分值项 {len(scores)}')
        if sum(scores) != st['full']:
            errs.append(f'{st["title"]} 满分守恒破：逐题分 {sum(scores)} ≠ {st["full"]}')
    if errs:
        die(f'方案出口闸拒收 {len(errs)} 条：\n' + '\n'.join('  ✗ ' + e for e in errs))


# ══════════════════════════════════════════════════════════════════════
# 命题明细 md
# ══════════════════════════════════════════════════════════════════════
def make_detail_md(plan, recipes):
    cfg = recipes[0]['pool']
    rlist = '；'.join('%s=%s' % (r['id'], r['title']) for r in recipes)
    L = [f'# 命题明细（{plan["generated_at"][:10]}）', '',
         f'> 配方：{rlist}；',
         f'> 题源=库内混编（{cfg["tier_order"][0]} 优先，'
         f'{"／".join(cfg["tier_order"][1:]) or "无"} 补充；{"／".join(cfg["tier_exclude"])} 已剔除）；'
         f'各套互不重题；',
         '> 压轴/中档池干涸的格就近降档替补，逐处如实标注。答案卷随题目卷同出。', '']
    for st in plan['sets']:
        subs = (f'｜替补 {len(st["subs"])} 处：{"；".join(st["subs"])}' if st['subs'] else '｜零替补')
        L.append(f'## {st["title"]}（满分 {st["full"]}·{st["dur"]} 分钟{subs}）')
        L.append('')
        L.append('| 题位 | 单元 | 考点 | 难度 | 使用级 | 来源 |')
        L.append('|---|---|---|---|---|---|')
        n = 0
        marks = []
        for s in st['sections']:
            for d in s['detail']:
                n += 1
                L.append(f'| {n} | 第{d["unit"]}单元 | {d["kp"]} | {d["diff"]} | {d["tier"]} | {d["src"]} |')
                if d['sub']:
                    marks.append(f'第{n}题（{s["slot"]}·{d["want"]}位→{d["diff"]}）')
        L.append('')
        if marks:
            L.append(f'> 替补落位：{"；".join(marks)}')
            L.append('')
    L.append(f'> 缺答案待解 {len(plan["need_answers"])} 题；'
             f'停产原因：{"；".join(f"{k}={v}" for k, v in plan["stop_reasons"].items())}')
    L.append('')
    return '\n'.join(L)


# ══════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description='配方驱动的五维选题器（只读库，出方案 JSON + 命题明细 md）')
    ap.add_argument('--recipe', action='append', required=True, help='配方 JSON（可多次=轮转出卷）')
    ap.add_argument('--db', default=str(DEFAULT_DB), help='缺省 <v2根>/知识库/kb.db；沙盘传副本')
    ap.add_argument('--out-plan', required=True, help='方案 JSON 出路（相对=按 v2 根解析）')
    ap.add_argument('--out-md', help='命题明细 md 出路（不给=不出 md）')
    ap.add_argument('--max-sets', type=int, help='最多出几套（不给=出到全部配方停产）')
    ap.add_argument('--exclude', action='append', default=[],
                    help='点名排除的 qid（可多次）。用途：泄答案闸拦下的题整题出池后重跑，'
                         '取代手改库换题——🔴 排除会连锁改变其后所有槽的取题，方案整体重出')
    ap.add_argument('--exclude-file', help='排除清单 JSON（qid 数组，或 {"exclude":[...]}）')
    args = ap.parse_args()

    recipes = [load_recipe(p) for p in args.recipe]
    exclude = list(args.exclude)
    if args.exclude_file:
        ef = json.loads(resolve_out(args.exclude_file).read_text(encoding='utf-8'))
        exclude += ef if isinstance(ef, list) else list(ef.get('exclude') or [])
    for r in recipes:                       # 配方自带的常驻排除（如泄答案闸拦下的题）
        exclude += list(r.get('exclude_qids') or [])
    keys = [r['key'] for r in recipes]
    if len(set(keys)) != len(keys):
        die(f'配方 key 重复 {keys}——key 是套号命名与幂等的坐标')
    cfg = unify_pool_cfg(recipes)
    qtype_slot = dict(QTYPE_SLOT)
    qtype_slot.update(recipes[0].get('qtype_slot') or {})

    dbp = Path(args.db)
    if not dbp.is_absolute():
        dbp = ROOT / dbp
    if not dbp.exists():
        die(f'库不存在：{dbp}')
    conn = sqlite3.connect(f'file:{dbp.as_posix()}?mode=ro', uri=True)   # 🔴 只读，一行都不写
    pool, stat, noslot = build_pool(conn, cfg, qtype_slot, exclude)
    conn.close()

    print(f'池：扫描 {stat["扫描"]} → 入池 {stat["入池"]}'
          f'（排除{"／".join(cfg["tier_exclude"])} {stat["排除三级"]}；'
          f'题型无对应槽 {stat["题型无对应槽"]}{"：" + str(noslot) if noslot else ""}'
          + (f'；点名排除 {stat["点名排除"]}/{len(set(exclude))}' if exclude else '') + '）')
    if exclude and stat['点名排除'] < len(set(exclude)):
        print(f'⚠ 点名排除清单里有 {len(set(exclude)) - stat["点名排除"]} 个 qid 本就不在池内'
              f'（已停用/三级/题型无槽），不影响出卷', file=sys.stderr)

    used, sets, dead, stop = set(), [], set(), {}
    seq = defaultdict(int)
    i = 0
    while len(dead) < len(recipes):
        rc = recipes[i % len(recipes)]
        i += 1                                   # 🔴 轮转起点=递增计数（v4 原次序，别动）
        if rc['key'] in dead:
            continue
        snap = set(used)
        built, why = build_set(rc, pool, used, i)
        if built is None:
            used.clear()
            used.update(snap)                    # 整套回滚：干涸的套一题都不占
            dead.add(rc['key'])
            stop[rc['id']] = why
            print(f'{rc["id"]} 停产（{why}）')
            continue
        seq[rc['key']] += 1
        st = make_set_json(rc, seq[rc['key']], built)
        sets.append(st)
        print(f'√ {rc["id"]} 第{seq[rc["key"]]}套 {len(built["picked"])} 题'
              + (f'｜替补:{";".join(built["subs"])}' if built['subs'] else ''))
        if args.max_sets and len(sets) >= args.max_sets:
            stop['(全部)'] = f'达到 --max-sets {args.max_sets}'
            break
    for rc in recipes:
        stop.setdefault(rc['id'], '未停产（被 --max-sets 截断）' if args.max_sets else '未停产')

    need = sorted({d['qid'] for st in sets for s in st['sections']
                   for d in s['detail'] if not d['has_answer']})
    plan = {'contract': PLAN_CONTRACT,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'db': str(dbp), 'recipes': [{'id': r['id'], 'key': r['key'], 'file': r['_file']}
                                        for r in recipes],
            'excluded': sorted(set(exclude)),
            'pool_stat': stat, 'sets': sets, 'need_answers': need, 'stop_reasons': stop}
    gate_plan(plan, cfg)

    fp = resolve_out(args.out_plan)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n=== 共 {len(sets)} 套（' + '／'.join(f'{k}:{seq[k]}' for k in keys)
          + f'）｜用题 {len(used)}｜无答案待解 {len(need)} ===')
    print('方案 →', fp)
    if args.out_md:
        mp = resolve_out(args.out_md)
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(make_detail_md(plan, recipes), encoding='utf-8')
        print('明细 →', mp)


if __name__ == '__main__':
    main()
