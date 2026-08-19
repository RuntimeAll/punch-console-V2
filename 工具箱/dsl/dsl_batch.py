# -*- coding: utf-8 -*-
"""计算题 DSL 批处理入库（2026-08-19 立）——**一条命令：排班计划 → 题在库里 + 组卷 spec 就绪**。

用户口径（2026-08-19 拍板）：「计算题本身就是模型AI生成的，有对应的DSL，不应该直接生成，
应该批处理，和规律入库，不然损耗太大了」——计算题从生成到入库**全程零 LLM**：
打标规律全部来自 DSL 本体的 `GEN_META`/`DIFF_BY_LV` 与库里的 exam_model，
agent 不再为每册手写一份编排脚本（老做法：每册一个 gen_打卡.py，规律散在册子里、改一处别处不跟）。

用法（--db 缺省 = 脚本位置自解析 <v2根>/知识库/kb.db；worktree 里跑 = 天然沙盘）：
    python 工具箱/dsl/dsl_batch.py run 排班.json [--db …] [--check-only] [--assemble]
                                                [--no-vec] [--serve-port 4315]
      --check-only  只干跑（生成+verify+模型解析+过三闸），全程回滚、不写库不写 spec
      --assemble    入库后直接调 工具箱/组卷/paper_tool.py assemble 把册组出来
      --no-vec      入库后不补语意向量（缺省会补：serve 在走 serve、不在回落冷载、
                    两条都不通只打印待补命令——绝不静默、绝不阻断入库）
      --serve-port  常驻 embed serve 端口（缺省 4315／环境变量 EMBED_SERVE_PORT）
每次执行落 skill_log（skill='DSL批处理'）。

排班.json（🔴 数据不是代码——「每册手写 gen 脚本」到此为止）：
{
  "dsl": "有理数混合运算_qbank",          // 工具箱/dsl/ 下的模块名（必须带 GEN_META）
  "seed": 20260818,                       // 每卷实际种子 = seed + 卷序号×97（确定性可复算）
  "artifact": {"name": "…", "kind": "打卡册", "source_line": "每日打卡"},   // 直接喂给 paper_tool
  "layout_defaults": {"layout": "dense_sections", "body_pt": 12.5, "watermark": null,
                      "section": {"slot": "expr", "grid": "block",
                                  "gap": 0, "gap_each": 11, "ans_cols": 1}},
  "papers": [{"kind": "打卡天", "title": "第一天·有理数的加减", "ord": 1,
              "sections": [{"name": "整数加减混合链",
                            "gens": [["gen_addsub_chain", 4, 1]]}]}]   // [生成器, 题数, 难度档 lv]
}
可选覆盖：paper["layout"]（盖 layout_defaults 的卷级键）、section["layout"]（盖 layout_defaults.section）。

流程（全机械，无一处需要 LLM）：
  0. 预检：排班结构 + 生成器存在 + GEN_META 有 kp + DIFF_BY_LV 有 lv +
     **exam_model 从库里规律解析**（SELECT … WHERE status='在用' AND dsl_ref=? AND params_json LIKE '%<gen名>%'）；
     🔴 查不到 = 整体拒跑「模型必留档：先 model_tool exam-add」——飞轮铁律②的硬闸，
        不许静默降级为无模型入库；多命中报名单拒（不自动挑）。
  1. 出题：逐 paper/section/gen 调生成器；去重口径 = **题面全册精确去重 + 骨架限次逐级放宽
     (卷内,全册) = (2,5)→(4,8)→(6,14)**（骨架签名 = qb._skel，数字全归一成 N）。
  2. `qb.verify()` 全绿才继续（题面独立求值双路 + 逐行恒等 + 值域/步数）；不绿整体退出码 1。
  3. 打标：kp←GEN_META、难度←DIFF_BY_LV、qtype='计算题'、source_kind='model'、confidence=98、
     题面 md=`$裸tex$`（🔴 净题面无「计算：」类指令词——指令词是载体/渲染层的事）、
     答案=`$值$`、解析=「＝$步$」按行；prov 记 model_id/dsl_ref/gen/lv/seed（DSL 出题路径必留档）。
  4. 入库：走 ingest_flow.ingest_one 过三闸，全或无（一条拒收全批回滚），拿回 qids。
  5. 组卷 spec：qids 已回填、layout 由 layout_defaults + 节名合成 → 写 `<排班名>-组卷spec.json`；
     --assemble 时接着跑 paper_tool assemble。
  6. 收尾：增量语意向量（**与 ingest_flow 同一个 autovec，同款行为**）——D-20 第③层跟着入库走，
     不用人记着补。🔴 serve 在 → 批量走 serve（毫秒级）；serve 不在 → 回落冷载 sidecar；
     两条都不通 → **打印待补命令**（python 工具箱/检索/embed_tool.py build --db …）后照常返回。
     🔴 绝不静默（每条路都印一行）、🔴 绝不阻断入库（题已过闸进库了，向量算不动不影响退出码）。
"""
import argparse
import importlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from random import Random

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent                  # …/工具箱/dsl
ROOT = HERE.parents[1]                                  # …/ai-bkb-v2（或 worktree 根）
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
PAPER_TOOL = ROOT / '工具箱' / '组卷' / 'paper_tool.py'

sys.path.insert(0, str(HERE))                           # DSL 模块按模块名 import
sys.path.insert(0, str(ROOT / '工具箱' / '回流'))
import ingest_flow as ing                               # noqa: E402  入库通路（唯一门）

# 骨架限次逐级放宽：(卷内上限, 全册上限)。先按最严找，找不到才退让——
# 退让代价 = 同型多一道，比整册出不来轻得多（老区实锤：直接 raise 等于"配额敢要，出卷就崩"）。
SKEL_CAPS = ((2, 5), (4, 8), (6, 14))
TRY_PER_CAP = 400
QTYPE = '计算题'
CONFIDENCE = 98

RE_STEP = re.compile(r'^＝ \\\((.*)\\\)$')
RE_COLOR = re.compile(r'^\\color\{#c00\}\{(.*)\}$')


class BatchError(Exception):
    """批处理整体拒跑（带原话，绝不静默降级）。"""


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def open_db(path):
    import sqlite3
    p = Path(path)
    if not p.exists():
        raise BatchError(f'🔴 库不存在：{p}（先跑 工具箱/库/init_db.py）')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def log_skill(conn, action, digest, result, detail, t0):
    conn.execute(
        'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) '
        'VALUES (?,?,?,?,?,?,?)',
        ('DSL批处理', action, str(digest)[:200], result, str(detail)[:500],
         int((time.time() - t0) * 1000), now()))
    conn.commit()


# ══════════════════════════════════════════════════════════════════════
# 排班计划：读 + 结构预检（错一次报全，不逐条来回）
# ══════════════════════════════════════════════════════════════════════
def load_plan(path):
    p = Path(path)
    if not p.exists():
        raise BatchError(f'🔴 排班计划不存在：{path}')
    try:
        plan = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        raise BatchError(f'🔴 排班计划不是合法 JSON：{e}')
    errs = []
    if not isinstance(plan.get('dsl'), str) or not plan['dsl']:
        errs.append('dsl 缺失（工具箱/dsl 下的模块名，如 "有理数混合运算_qbank"）')
    if not isinstance(plan.get('seed'), int):
        errs.append(f'seed={plan.get("seed")!r} 非法（要整数——种子不确定=题不可复算）')
    if not isinstance(plan.get('artifact'), dict):
        errs.append('artifact 缺失（直接喂 paper_tool：name/kind/source_line 或 id）')
    ld = plan.get('layout_defaults')
    if not isinstance(ld, dict):
        errs.append('layout_defaults 缺失（版式默认值，合成到每卷 layout）')
    elif not isinstance(ld.get('section'), dict):
        errs.append('layout_defaults.section 缺失（每个节的版式模板：slot/grid/gap/…）')
    papers = plan.get('papers')
    if not isinstance(papers, list) or not papers:
        errs.append('papers 为空——排班没卷可排')
        raise BatchError(_lines('🔴 排班计划不合格', errs))
    ords = []
    for pi, p_ in enumerate(papers):
        tag = f'papers[{pi}]'
        if not isinstance(p_, dict):
            errs.append(f'{tag} 必须是对象')
            continue
        if not isinstance(p_.get('ord'), int):
            errs.append(f'{tag}.ord={p_.get("ord")!r} 非法（要整数，打卡=天号）')
        else:
            ords.append(p_['ord'])
        if not p_.get('title'):
            errs.append(f'{tag}.title 缺失——卷面标题必填')
        if not p_.get('kind'):
            errs.append(f'{tag}.kind 缺失（打卡天/专项卷/试卷/其他）')
        secs = p_.get('sections')
        if not isinstance(secs, list) or not secs:
            errs.append(f'{tag}.sections 为空——一张卷至少一节')
            continue
        for si, sec in enumerate(secs):
            stag = f'{tag}.sections[{si}]'
            if not isinstance(sec, dict) or not sec.get('name'):
                errs.append(f'{stag}.name 缺失——节名是 paper_item 与 layout 的对位键')
                continue
            gens = sec.get('gens')
            if not isinstance(gens, list) or not gens:
                errs.append(f'{stag}.gens 为空——一节至少一条 [生成器, 题数, 难度档]')
                continue
            for gi, g in enumerate(gens):
                if (not isinstance(g, (list, tuple)) or len(g) != 3
                        or not isinstance(g[0], str)
                        or not isinstance(g[1], int) or g[1] <= 0
                        or not isinstance(g[2], int)):
                    errs.append(f'{stag}.gens[{gi}]={g!r} 非法——要 ["gen_名", 正整数题数, 难度档lv]')
    if len(set(ords)) != len(ords):
        errs.append(f'papers.ord 重复：{ords}——册内序是唯一坐标')
    if errs:
        raise BatchError(_lines('🔴 排班计划不合格', errs))
    return plan


def _lines(head, errs):
    return head + f'（{len(errs)} 条，整体拒跑）：\n' + '\n'.join('  ✗ ' + e for e in errs)


def gen_specs(plan):
    """摊平排班里所有 (gen名, 题数, lv)，按出现顺序。"""
    out = []
    for pi, p in enumerate(plan['papers']):
        for si, sec in enumerate(p['sections']):
            for g in sec['gens']:
                out.append((pi, si, g[0], g[1], g[2]))
    return out


# ══════════════════════════════════════════════════════════════════════
# 预检：生成器 / 打标规律 / exam_model（🔴 模型必留档硬闸）
# ══════════════════════════════════════════════════════════════════════
def preflight(conn, qb, plan, dsl_ref):
    errs = []
    meta = getattr(qb, 'GEN_META', None)
    diff_map = getattr(qb, 'DIFF_BY_LV', None)
    if not isinstance(meta, dict) or not meta:
        raise BatchError(
            f'🔴 DSL 模块 {plan["dsl"]} 没有 GEN_META——打标规律的唯一事实源在 DSL 本体里，'
            f'先在该文件文末补 GEN_META（生成器→{{"kp": 叶子id}}）与 DIFF_BY_LV')
    if not isinstance(diff_map, dict) or not diff_map:
        raise BatchError(f'🔴 DSL 模块 {plan["dsl"]} 没有 DIFF_BY_LV（难度档 lv→中文标签）')

    used = {}
    for pi, si, gname, k, lv in gen_specs(plan):
        tag = f'papers[{pi}].sections[{si}]'
        if not callable(getattr(qb, gname, None)):
            errs.append(f'{tag} 生成器 {gname!r} 在 {plan["dsl"]} 里不存在')
            continue
        if gname not in meta or not meta[gname].get('kp'):
            errs.append(f'{tag} 生成器 {gname!r} 在 GEN_META 里没有 kp——'
                        f'打标规律缺失就不许出题（裸题入库=学情分母失真）')
        if lv not in diff_map:
            errs.append(f'{tag} 难度档 lv={lv} 不在 DIFF_BY_LV {sorted(diff_map)} 里')
        used[gname] = used.get(gname, 0) + k
    if errs:
        raise BatchError(_lines('🔴 排班预检不过', errs))

    # 考点叶子闸（先查一遍，别等入库才报）
    for gname in sorted(used):
        kp = meta[gname]['kp']
        row = conn.execute('SELECT name,level,status FROM kp WHERE id=?', (kp,)).fetchone()
        if not row:
            errs.append(f'{gname} 的 GEN_META.kp={kp} 在 kp 表里不存在——先铺枝/改 GEN_META')
        elif row[1] != '考点' or row[2] != '现行':
            errs.append(f'{gname} 的 GEN_META.kp={kp}（{row[0]}）level={row[1]} status={row[2]}'
                        f'——只挂现行叶子')
    if errs:
        raise BatchError(_lines('🔴 打标规律的考点不合格', errs))

    # 🔴 模型必留档：exam_model 从库里规律解析（dsl_ref + params 含 gen 名）
    model_of, missing, multi = {}, [], []
    for gname in sorted(used):
        hits = [r[0] for r in conn.execute(
            "SELECT id FROM exam_model WHERE status='在用' AND dsl_ref=? AND params_json LIKE ?",
            (dsl_ref, f'%{gname}%'))]
        if not hits:
            missing.append(gname)
        elif len(hits) > 1:
            multi.append(f'{gname} → {hits}')
        else:
            model_of[gname] = hits[0]
    if missing:
        raise BatchError(
            '🔴 模型必留档：以下生成器在库里没有在用 exam_model（'
            f'dsl_ref={dsl_ref}，params_json 需含 gen 名）：\n'
            + '\n'.join(f'  ✗ {g}（考点 {meta[g]["kp"]}）' for g in missing)
            + '\n  先跑：python 工具箱/回流/model_tool.py exam-add --name <模型名> --kp <考点> \\\n'
              f'        --dsl-ref {dsl_ref} --params \'{{"gens": ["{missing[0]}"], "lv": [1,3]}}\'\n'
              '  （飞轮铁律②：DSL 出题路径必留档，每个考点后续都能持续再出题；'
              '不许静默降级为无模型入库）')
    if multi:
        raise BatchError(
            '🔴 exam_model 多命中（要恰一，不自动挑）：\n'
            + '\n'.join('  ✗ ' + m for m in multi)
            + '\n  改 params_json 让 gen 名只落在一个模型里，或停用多余模型')

    # 非阻断提醒：模型挂的考点与 GEN_META 的 kp 不一致（低置信点，人来判）
    for gname, mid in model_of.items():
        row = conn.execute('SELECT kp_ids_json,name FROM exam_model WHERE id=?', (mid,)).fetchone()
        try:
            kps = json.loads(row[0] or '[]')
        except Exception:
            kps = []
        if meta[gname]['kp'] not in kps:
            print(f'⚠️ {gname}：GEN_META.kp={meta[gname]["kp"]} 不在模型 {mid}《{row[1]}》'
                  f'的 kp_ids {kps} 里——题按 GEN_META 打标，模型口径请人工对一眼', file=sys.stderr)
    return meta, diff_map, model_of


# ══════════════════════════════════════════════════════════════════════
# 出题：题面全册精确去重 + 骨架限次逐级放宽
# ══════════════════════════════════════════════════════════════════════
def build_book(qb, plan):
    seed = plan['seed']
    seen, book_skel = set(), {}
    book = []                                    # [[section_items, …], …] 与 papers 同序
    for pi, p in enumerate(plan['papers']):
        rng = Random(seed + pi * 97)
        paper_skel = {}
        paper_items = []
        for si, sec in enumerate(p['sections']):
            items = []
            for gname, k, lv in [(g[0], g[1], g[2]) for g in sec['gens']]:
                gen = getattr(qb, gname)
                for n in range(k):
                    placed = False
                    for pcap, bcap in SKEL_CAPS:
                        for _try in range(TRY_PER_CAP):
                            it = gen(rng, lv)
                            sig = qb._skel(it['q'])
                            if (it['q'] in seen
                                    or paper_skel.get(sig, 0) >= pcap
                                    or book_skel.get(sig, 0) >= bcap):
                                continue
                            seen.add(it['q'])
                            paper_skel[sig] = paper_skel.get(sig, 0) + 1
                            book_skel[sig] = book_skel.get(sig, 0) + 1
                            it['gen'], it['lv'] = gname, lv
                            it['paper_ord'], it['paper_seed'] = p['ord'], seed + pi * 97
                            items.append(it)
                            placed = True
                            break
                        if placed:
                            break
                    if not placed:
                        raise BatchError(
                            f'🔴 papers[{pi}]（ord={p["ord"]}）.sections[{si}]《{sec["name"]}》'
                            f'第 {n + 1} 道 {gname} 出题耗尽：题面/骨架撞尽（上限已放宽到 {SKEL_CAPS[-1]}）'
                            f'——给该生成器加变体，或降本节题量')
            paper_items.append(items)
        book.append(paper_items)
    return book


# ══════════════════════════════════════════════════════════════════════
# 打标 → 题目包 items（ingest_flow 契约）
# ══════════════════════════════════════════════════════════════════════
def strip_q(q):
    if not (q.startswith('\\(') and q.endswith('\\)')):
        raise BatchError(f'🔴 题面 LaTeX 定界异常（要 \\(…\\)）：{q[:60]}')
    return q[2:-2]


def strip_steps(steps):
    out = []
    for s in steps:
        m = RE_STEP.match(s)
        if not m:
            raise BatchError(f'🔴 过程行不是「＝ \\(…\\)」形：{s[:60]}')
        inner = m.group(1)
        mc = RE_COLOR.match(inner)
        out.append(mc.group(1) if mc else inner)
    return out


def B(md, role):
    return {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': role, 'md': md}]}]}


def make_items(qb, plan, book, meta, diff_map, model_of, dsl_ref, book_name):
    """逐题打标成 ingest_flow 题目包 item；返回 (items, 每节题数在 items 里的切片索引)。"""
    items, slices = [], []
    for p, paper_items in zip(plan['papers'], book):
        for sec, sec_items in zip(p['sections'], paper_items):
            lo = len(items)
            for it in sec_items:
                kp = meta[it['gen']]['kp']
                steps = strip_steps(it['steps'])
                items.append({
                    'blocks': B('$%s$' % strip_q(it['q']), '题面'),      # 🔴 净题面，无指令词
                    'answer_blocks': B('$%s$' % qb.fx(it['ans']), '答案'),
                    'analysis_blocks': B('\n'.join('＝$%s$' % s for s in steps), '解析'),
                    'qtype': QTYPE,
                    'difficulty': diff_map[it['lv']],
                    'source_kind': 'model',
                    'source_raw': f'自编·{book_name} D{it["paper_ord"]}',
                    'kp': [kp],
                    'prov': {'model_id': model_of[it['gen']], 'dsl_ref': dsl_ref,
                             'gen': it['gen'], 'lv': it['lv'],
                             'seed': plan['seed'], 'paper_seed': it['paper_seed'],
                             'paper_ord': it['paper_ord']},
                    'confidence': CONFIDENCE,
                })
            slices.append((lo, len(items)))
    return items, slices


# ══════════════════════════════════════════════════════════════════════
# 入库（走 ingest_flow 的三闸；全或无）
# ══════════════════════════════════════════════════════════════════════
def ingest(conn, items, dry):
    """全批过三闸入草稿。返回 (qids, D-21 等级分布)。一条拒收 = 全批回滚。"""
    qids, errs, grades = [], [], {}
    conn.execute('BEGIN')
    for i, item in enumerate(items):
        # 🔴 容错解包：ingest_flow.ingest_one 2026-08-19 从 (qid,errs) 扩成 (qid,errs,等级)
        #    （D-21 等级审实装）——这里按位取，别被上游再扩一位就整条产线断。
        res = ing.ingest_one(conn, item, i, False)
        qid, e = res[0], res[1]
        g = res[2] if len(res) > 2 else None
        if g:
            grades[g['name']] = grades.get(g['name'], 0) + 1
        if e:
            errs += e
        else:
            qids.append(qid)
    if dry or errs:
        conn.rollback()
    else:
        conn.commit()
    if errs:
        raise BatchError(
            f'🔴 入库三闸拒收 {len(errs)} 条（全批回滚、一条不入）：\n'
            + '\n'.join('  ✗ ' + e for e in errs[:20])
            + ('\n  …（还有 %d 条）' % (len(errs) - 20) if len(errs) > 20 else ''))
    return qids, grades


# ══════════════════════════════════════════════════════════════════════
# 组卷 spec（qids 已回填 + layout 合成）
# ══════════════════════════════════════════════════════════════════════
def make_spec(plan, slices, qids, plan_path):
    ld = plan['layout_defaults']
    base = {k: v for k, v in ld.items() if k != 'section'}
    sec_tpl = ld.get('section') or {}
    papers, k = [], 0
    for p in plan['papers']:
        lay = dict(base)
        lay.update({x: y for x, y in (p.get('layout') or {}).items() if x != 'sections'})
        lay_secs, spec_secs = [], []
        for sec in p['sections']:
            lo, hi = slices[k]
            k += 1
            s = {'name': sec['name']}
            s.update(sec_tpl)
            s.update(sec.get('layout') or {})
            s['name'] = sec['name']
            lay_secs.append(s)
            item = {'name': sec['name'], 'qids': qids[lo:hi]}
            if sec.get('score') is not None:
                item['score'] = sec['score']
            spec_secs.append(item)
        lay['sections'] = lay_secs
        papers.append({'kind': p['kind'], 'title': p['title'], 'ord': p['ord'],
                       'layout': lay, 'sections': spec_secs})
    spec = {'artifact': plan['artifact'], 'papers': papers}
    out = Path(plan_path).resolve().with_name(Path(plan_path).stem + '-组卷spec.json')
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
    return out


# ══════════════════════════════════════════════════════════════════════
# 入库收尾：增量语意向量（🔴 ingest_flow.autovec 同款，一处口径两处用）
# ══════════════════════════════════════════════════════════════════════
def do_autovec(conn, args, qids):
    """给这批刚入库的题补语意向量 → 说明串（写进汇总与 skill_log）。

    🔴 本函数存在的理由（2026-08-19 审查实锤）：dsl_batch 直调 ingest_one，绕过了
       ingest_flow 的 cmd_ingest 收尾，于是「打卡册 16 题入库、③语意层一条向量都没有、
       且屏幕上一个字都不提」——静默缺口比算不出来更坏。

    三条与 ingest_flow 一字不差：
      · serve（缺省 :4315）在 → 批量走 serve；不在 → 回落冷载 sidecar；两条都不通 → 打印待补命令；
      · **绝不静默**：走哪条路、跳过什么原因，都印出来；
      · **绝不阻断入库**：题已过闸进库并 commit 了，向量是③层加速；这里任何异常都只报不抛。
    """
    if not qids:
        return '无新题'
    if getattr(args, 'no_vec', False):
        print('· --no-vec：不补语意向量（③语意层搜不到这批，直到你手动 build）\n'
              f'  待补：python 工具箱\\检索\\embed_tool.py build --db {args.db}')
        return 'skip:--no-vec'
    try:
        _n, note = ing.autovec(conn, qids, getattr(args, 'serve_port', None))
    except Exception as e:                                  # noqa: BLE001
        # 🔴 收尾步骤绝不把主事务拖下水：题已入库并 commit，这里只报不抛（老区最典型的坏账来源）
        print(f'⚠️ 增量向量收尾异常（{type(e).__name__}: {e}）——🔴 题已入库不受影响。\n'
              f'  待补：python 工具箱\\检索\\embed_tool.py build --db {args.db}', file=sys.stderr)
        return f'error:{type(e).__name__}'
    if note.startswith('skip:') or note.startswith('partial:'):
        # autovec 内部已印过原因与 build 提示，这里再把本次的库路径补全（它只印通用命令）
        print(f'  待补（本次的库）：python 工具箱\\检索\\embed_tool.py build --db {args.db}')
    return note


# ══════════════════════════════════════════════════════════════════════
# run
# ══════════════════════════════════════════════════════════════════════
def cmd_run(conn, args):
    plan = load_plan(args.plan)
    dsl_ref = f'工具箱/dsl/{plan["dsl"]}.py'
    if not (ROOT / dsl_ref).exists():
        raise BatchError(f'🔴 DSL 文件不存在：{dsl_ref}（dsl 写模块名，不带 .py）')
    try:
        qb = importlib.import_module(plan['dsl'])
    except Exception as e:
        raise BatchError(f'🔴 import DSL 模块 {plan["dsl"]} 失败：{e}')

    a = plan['artifact']
    book_name = a.get('name') or a.get('id') or Path(args.plan).stem
    meta, diff_map, model_of = preflight(conn, qb, plan, dsl_ref)
    print(f'预检通过：DSL={dsl_ref} 生成器 {len(model_of)} 个，exam_model 全部命中'
          f'（{" ".join(f"{g}→{m}" for g, m in sorted(model_of.items()))}）')

    book = build_book(qb, plan)
    flat = [it for paper in book for sec in paper for it in sec]
    print(f'出题：{len(plan["papers"])} 卷 / {len(flat)} 题（seed={plan["seed"]}，'
          f'去重=题面全册精确 + 骨架限次{SKEL_CAPS}）')

    if not qb.verify(flat, book_name):
        raise BatchError('🔴 verify 未全绿——拒绝入库（答案对≠过程对，逐行恒等这关不许绕）')

    items, slices = make_items(qb, plan, book, meta, diff_map, model_of, dsl_ref, book_name)
    qids, grades = ingest(conn, items, dry=args.check_only)

    spec_path = None
    vec_note = 'off'
    if args.check_only:
        would = Path(args.plan).resolve().with_name(Path(args.plan).stem + '-组卷spec.json')
        print(f'干跑：{len(qids)}/{len(items)} 过三闸，全部回滚（真跑去掉 --check-only）；'
              f'组卷 spec 将写到 {would}')
        vec_note = 'skip:--check-only'
    else:
        spec_path = make_spec(plan, slices, qids, args.plan)
        print(f'入库（草稿）：{len(qids)} 题；组卷 spec → {spec_path}')
        # ── 收尾：增量语意向量（🔴 与 ingest_flow 同一个 autovec，一处口径两处用）──
        #    绝不静默：serve/冷载/待补命令三条路各印一行；绝不阻断：算不动不影响入库与退出码。
        vec_note = do_autovec(conn, args, qids)

    # ── 汇总 ──
    cov, lvs = {}, {}
    for it in flat:
        kp = meta[it['gen']]['kp']
        cov[kp] = cov.get(kp, 0) + 1
        d = diff_map[it['lv']]
        lvs[d] = lvs.get(d, 0) + 1
    per_paper = ' '.join('#%s×%d' % (p['ord'], sum(len(s) for s in bk))
                         for p, bk in zip(plan['papers'], book))
    print('—— 批处理汇总 ——')
    print(f'  题数：{len(flat)}（{len(plan["papers"])} 卷：{per_paper}）')
    for kp, n in sorted(cov.items()):
        row = conn.execute('SELECT name FROM kp WHERE id=?', (kp,)).fetchone()
        print(f'  考点 {kp} {row[0] if row else "?"}：{n} 题')
    print('  难度分布：' + ' '.join(f'{k}×{v}' for k, v in sorted(lvs.items())))
    print('  审级分布（D-21，ingest_flow 判）：'
          + (' '.join(f'{k}×{v}' for k, v in sorted(grades.items())) or '（无）'))
    print(f'  语意向量（D-20 第③层）：{vec_note}')
    if qids:
        head = ' '.join(qids[:2])
        tail = ' '.join(qids[-2:])
        print(f'  qids：{head} … {tail}（共 {len(qids)}）')
    print(f'  组卷 spec：{spec_path if spec_path else "(干跑未写)"}')
    return (f'plan={args.plan} dsl={plan["dsl"]}',
            f'papers={len(plan["papers"])} items={len(flat)} qids={len(qids)} '
            f'check_only={bool(args.check_only)} 向量[{vec_note}]', spec_path)


def run_assemble(spec_path, db):
    print(f'—— 调 paper_tool assemble（{spec_path}）——')
    r = subprocess.run([sys.executable, str(PAPER_TOOL), '--db', str(db),
                        'assemble', '--spec', str(spec_path)],
                       capture_output=True, text=True, encoding='utf-8')
    if r.stdout:
        print(r.stdout.rstrip())
    if r.stderr:
        print(r.stderr.rstrip(), file=sys.stderr)
    if r.returncode != 0:
        raise BatchError(f'🔴 组卷失败（paper_tool 退出码 {r.returncode}）——'
                         f'题已入库（草稿），修 spec 后重跑 paper_tool assemble 即可（幂等重排）')


def main(argv=None):
    ap = argparse.ArgumentParser(description='计算题 DSL 批处理入库（排班计划 → 题在库里 + 组卷 spec）')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('run')
    s.add_argument('plan', help='排班.json')
    s.add_argument('--check-only', dest='check_only', action='store_true',
                   help='只干跑：生成+verify+模型解析+过三闸，全程回滚不写库不写 spec')
    s.add_argument('--assemble', action='store_true', help='入库后直接调 paper_tool assemble')
    s.add_argument('--no-vec', dest='no_vec', action='store_true',
                   help='入库后不补语意向量（缺省会补：serve 在走 serve，不在回落冷载；'
                        '两条都不通只打印待补命令，不阻断入库）')
    s.add_argument('--serve-port', dest='serve_port', type=int,
                   help='常驻 embed serve 端口（缺省 4315／环境变量 EMBED_SERVE_PORT）')
    args = ap.parse_args(argv)

    t0 = time.time()
    action = 'check' if getattr(args, 'check_only', False) else 'run'
    try:
        conn = open_db(args.db)
    except BatchError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    spec_path = digest = detail = None
    try:
        digest, detail, spec_path = cmd_run(conn, args)
    except BatchError as e:
        conn.rollback()
        print(str(e), file=sys.stderr)
        try:
            log_skill(conn, action, f'plan={args.plan}', '失败', str(e)[:500], t0)
        except Exception:
            pass
        conn.close()
        sys.exit(1)
    conn.close()

    if args.assemble and not args.check_only:
        try:
            run_assemble(spec_path, args.db)
            detail += ' assembled=1'
        except BatchError as e:
            print(str(e), file=sys.stderr)
            conn = open_db(args.db)
            log_skill(conn, action, digest, '失败', str(e)[:500], t0)
            conn.close()
            sys.exit(1)
    elif args.assemble and args.check_only:
        print('⚠️ --check-only 与 --assemble 同给：干跑不写库也不组卷（组卷段跳过）', file=sys.stderr)

    conn = open_db(args.db)
    log_skill(conn, action, digest, '成功', detail, t0)
    conn.close()
    sys.exit(0)


if __name__ == '__main__':
    main()
