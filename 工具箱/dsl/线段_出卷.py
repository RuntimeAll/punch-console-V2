# -*- coding: utf-8 -*-
"""线段专项训练包 · 整册出卷驱动（26 卷 / 138 题）
==============================================================================
用户令（2026-08-22）：浙教七上线段，五个类型，每类型 5 题一页，第五类型难、2 题一页；
**每个专项要 5 份平行卷**；最后一份综合八页含五个类型；每类型前印一张简单的答题技巧；
答案与技巧一律简单。源料 = 教辅《浙教七上·线段的和差倍分》（只提炼母题结构，不照录原题）。

册结构（26 卷）：
  专项①~④  各 5 份 × 1 页 × 5 题 = 100 题     （同份第 i 题恒为同一骨架、不同数字 ⇒ 平行）
  专项⑤     5 份 × 1 页 × 2 题 = 10 题
  综合卷    1 份 × 8 页（①~④ 各 1 页 5 题 + ⑤ 4 页各 2 题）= 28 题

🔴 库中心：本驱动只负责「出题 + 打标 + 过闸入库 + 出组卷 spec」，
   题进 kb.question 走 工具箱/回流/ingest_flow.py（唯一门），卷进 paper 走 paper_tool（唯一门）。

用法：
  python 出卷.py --check-only            # 干跑：生成+双路实算+过三闸，全程回滚不写库
  python 出卷.py --apply                 # 真入库（草稿）+ 写组卷 spec
  python 出卷.py --apply --assemble      # 再接着组卷
"""
import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                       # …/ai-bkb-v2（worktree 里 = 沙盘根）
# 🔴 产出（题目包/组卷 spec）落战役目录，不落代码目录——代码空间只放代码
OUT = ROOT / '试验场' / '2026-08-22-线段专项'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / '工具箱' / 'dsl'))
sys.path.insert(0, str(ROOT / '工具箱' / '回流'))
import 线段_qbank as qb                       # noqa: E402
import ingest_flow as ing                     # noqa: E402

SEED = 20260822
DSL_REF = '工具箱/dsl/线段_qbank.py'
SOURCE_RAW = '自编·浙教七上线段专项（源=教辅《线段的和差倍分》母题结构，参数化重造）'
# kind/subkind 取 paper_tool 的合法值域（专项卷 / 组卷册）
ARTIFACT = {'name': '浙教七上·线段的和差倍分·专项训练包', 'kind': '专项卷',
            'subkind': '组卷册', 'source_line': '举一反三'}
QTYPE = '解答题'
CONFIDENCE = 98

# 类型⑤ 每份取哪两个骨架（4 骨架轮转，保证 5 份之间也铺得开）
V5_PICK = {1: (0, 1), 2: (2, 3), 3: (1, 2), 4: (3, 0), 5: (0, 2)}
V5_ZONGHE = [(0, 1), (2, 3), (1, 3), (0, 2)]


def sec_name(typ, idx=None):
    cn = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五'}[typ]
    base = f'类型{cn} · {qb.TYPE_NAME[typ]}'
    return base if idx is None else f'{base}（{"一二三四"[idx]}）'


def gen_unique(gen, rng, seen):
    """出一道且题面全册不撞（match_key 闸在库里也会拦，这里先拦住省得整批回滚）。"""
    for _ in range(600):
        it = gen(rng)
        if it['q'] not in seen:
            seen.add(it['q'])
            return it
    raise SystemExit(f'🔴 {gen.__name__} 出题耗尽：题面撞尽')


def build_book():
    """→ (papers, all_items)；papers = [{title, ord, sections:[{name, tip, items:[题]}]}]"""
    from random import Random
    seen = set()
    papers = []
    ordn = 0

    # ── 专项①~⑤ 各 5 份 ─────────────────────────────────────
    for typ in (1, 2, 3, 4, 5):
        for v in range(1, 6):
            ordn += 1
            rng = Random(SEED + typ * 1000 + v * 97)
            if typ == 5:
                gens = [qb.TYPE_GENS[5][i] for i in V5_PICK[v]]
            else:
                gens = qb.TYPE_GENS[typ]
            items = [gen_unique(g, rng, seen) for g in gens]
            papers.append({
                'title': f'线段专项{"①②③④⑤"[typ - 1]}·{qb.TYPE_NAME[typ]}（第 {v} 份）',
                'ord': ordn, 'kind': '专项卷',
                'sections': [{'name': sec_name(typ), 'tip': qb.TIPS[typ], 'items': items}],
            })

    # ── 综合卷（八页）──────────────────────────────────────
    ordn += 1
    secs = []
    for typ in (1, 2, 3, 4):
        rng = Random(SEED + 90000 + typ)
        secs.append({'name': sec_name(typ), 'tip': qb.TIPS[typ],
                     'items': [gen_unique(g, rng, seen) for g in qb.TYPE_GENS[typ]]})
    for pi, pick in enumerate(V5_ZONGHE):
        rng = Random(SEED + 95000 + pi)
        secs.append({'name': sec_name(5, pi), 'tip': qb.TIPS[5],
                     'items': [gen_unique(qb.TYPE_GENS[5][i], rng, seen) for i in pick]})
    papers.append({'title': '线段综合卷（八页·含五个类型）', 'ord': ordn,
                   'kind': '试卷', 'sections': secs})

    all_items = [it for p in papers for s in p['sections'] for it in s['items']]
    return papers, all_items


def B(md, role):
    return {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': role, 'md': md}]}]}


def to_pack(papers, model_id):
    """题 → ingest_flow 题目包 item（顺序 = 全册题序，入库后按序回填 qid）。"""
    out = []
    for p in papers:
        for s in p['sections']:
            for it in s['items']:
                out.append({
                    'blocks': B(it['q'], '题面'),
                    'answer_blocks': B(it['ans'], '答案'),
                    'analysis_blocks': B(it['sol'], '解析'),
                    'qtype': QTYPE,
                    'difficulty': qb.DIFF_BY_LV[it['lv']],
                    'source_kind': 'model',
                    'source_raw': SOURCE_RAW,
                    'kp': [it['kp']],
                    'prov': {'model_id': model_id, 'dsl_ref': DSL_REF, 'gen': it['gen'],
                             'type': it['type'], 'lv': it['lv'], 'seed': SEED,
                             'paper_ord': p['ord']},
                    'confidence': CONFIDENCE,
                    'tags': [{'domain': '方法', 'name': f'线段·{qb.TYPE_NAME[it["type"]]}'}],
                })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--assemble', action='store_true')
    ap.add_argument('--db', default=str(ROOT / '知识库' / 'kb.db'))
    ap.add_argument('--model-id', default='EM-线段-待建')
    a = ap.parse_args()

    papers, all_items = build_book()
    print(f'册结构：{len(papers)} 卷 / {len(all_items)} 题')
    for p in papers[:3] + papers[-1:]:
        n = sum(len(s['items']) for s in p['sections'])
        print(f"  [{p['ord']:>2}] {p['title']}　{len(p['sections'])} 节 {n} 题")
    print('  …')

    # ── 闸①：逐页双路实算 + 页内不撞 ────────────────────────
    allok = True
    for p in papers:
        for s in p['sections']:
            if not qb.verify(s['items'], f"[{p['ord']}] {s['name']}"):
                allok = False
    if not allok:
        sys.exit('🔴 verify 未全绿，整册拒出')
    # 闸②：全册题面互异
    stems = [it['q'] for it in all_items]
    if len(set(stems)) != len(stems):
        sys.exit('🔴 全册题面有重复')
    print(f'🟢 全册闸过：{len(stems)} 题题面互异，双路实算逐页全绿')

    pack = to_pack(papers, a.model_id)
    (OUT / '题目包.json').write_text(
        json.dumps({'source_line': ARTIFACT['source_line'], 'items': pack},
                   ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'题目包 → {OUT / "题目包.json"}（{len(pack)} 题）')

    if not (a.check_only or a.apply):
        return

    # ── 入库（全或无）────────────────────────────────────────
    conn = ing.open_db(a.db)
    qids, errs, grades = [], [], {}
    conn.execute('BEGIN')
    for i, item in enumerate(pack):
        res = ing.ingest_one(conn, item, i, False)
        qid, e = res[0], res[1]
        g = res[2] if len(res) > 2 else None
        if g:
            grades[g['name']] = grades.get(g['name'], 0) + 1
        if e:
            errs += e
        else:
            qids.append(qid)
    if a.check_only or errs:
        conn.rollback()
    else:
        conn.commit()
    print(f'入库：过闸 {len(qids)}/{len(pack)}　等级分布={grades}')
    if errs:
        print('🔴 拒收（全批回滚）：')
        for e in errs[:12]:
            print('   ', e)
        sys.exit(1)
    if a.check_only:
        print('🟢 干跑全绿（已回滚，未写库）')
        conn.close()
        return

    # ── 组卷 spec（qid 按题序回填）──────────────────────────
    spec = {'artifact': ARTIFACT, 'papers': []}
    k = 0
    for p in papers:
        secs, lay = [], []
        for s in p['sections']:
            n = len(s['items'])
            secs.append({'name': s['name'], 'qids': qids[k:k + n]})
            lay.append({'name': s['name'], 'tip': s['tip'], 'slot': 'word_multi'})
            k += n
        spec['papers'].append({'kind': p['kind'], 'title': p['title'], 'ord': p['ord'],
                               'layout': {'layout': '专项卷', 'body_pt': 11.5,
                                          'sections': lay},
                               'sections': secs})
    sp = OUT / '组卷spec.json'
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'组卷 spec → {sp}')
    conn.close()

    if a.assemble:
        import subprocess
        r = subprocess.run([sys.executable, str(ROOT / '工具箱' / '组卷' / 'paper_tool.py'),
                            'assemble', '--spec', str(sp), '--db', a.db],
                           text=True, encoding='utf-8')
        sys.exit(r.returncode)


if __name__ == '__main__':
    main()
