# -*- coding: utf-8 -*-
"""一元一次方程解法 · 出卷驱动（与「线段专项」同结构：一考点一页 5 题 + 技巧卡）
==============================================================================
用法：
  python 方程_出卷.py --days 1 --check-only     # 干跑（不写库）
  python 方程_出卷.py --days 1 --apply          # 入库 + 出组卷 spec
  python 方程_出卷.py --days 1 --apply --assemble
--days N：出前 N 个考点（1..5），一考点一卷一页 5 题。
"""
import argparse
import json
import sys
from pathlib import Path
from random import Random

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / '试验场' / '2026-08-22-一元一次方程'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / '工具箱' / '回流'))
import 一元一次方程_qbank as qb                  # noqa: E402
import ingest_flow as ing                        # noqa: E402

SEED = 20260822
DSL_REF = '工具箱/dsl/一元一次方程_qbank.py'
SOURCE_RAW = '自编·浙教七上一元一次方程解法（源=强化训练3 题型结构，参数化重造）'
ARTIFACT = {'name': '浙教七上·一元一次方程的解法·分考点专项', 'kind': '专项卷',
            'subkind': '组卷册', 'source_line': '每日打卡'}
QTYPE, CONFIDENCE = '计算题', 98
CN = '一二三四五'


def build(days):
    papers, seen = [], set()
    for t in range(1, days + 1):
        rng = Random(SEED + t * 131)
        items = []
        for g in qb.TYPE_GENS[t]:
            for _ in range(200):
                it = g(rng)
                if it and it['q'] not in seen:
                    seen.add(it['q'])
                    items.append(it)
                    break
            else:
                sys.exit(f'🔴 {g.__name__} 出题耗尽')
        name = f'考点{CN[t - 1]} · {qb.TYPE_NAME[t]}'
        papers.append({'ord': t, 'kind': '专项卷',
                       'title': f'一元一次方程的解法·第 {t} 天　{qb.TYPE_NAME[t]}',
                       'sections': [{'name': name, 'tip': qb.TIPS[t], 'items': items}]})
    return papers


def B(md, role):
    return {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': role, 'md': md}]}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=1)
    ap.add_argument('--check-only', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--assemble', action='store_true')
    ap.add_argument('--db', default=str(ROOT / '知识库' / 'kb.db'))
    ap.add_argument('--model-id', default='EM-方程-待建')
    a = ap.parse_args()

    papers = build(a.days)
    allq = [it for p in papers for s in p['sections'] for it in s['items']]
    print(f'{len(papers)} 卷 / {len(allq)} 题')
    ok = True
    for p in papers:
        for s in p['sections']:
            if not qb.verify(s['items'], f"[{p['ord']}] {s['name']}"):
                ok = False
    if not ok:
        sys.exit('🔴 verify 未全绿')

    pack = []
    for p in papers:
        for s in p['sections']:
            for it in s['items']:
                pack.append({
                    'blocks': B(it['q'], '题面'),
                    'answer_blocks': B(it['ans'], '答案'),
                    'analysis_blocks': B(it['sol'], '解析'),
                    'qtype': QTYPE, 'difficulty': qb.DIFF_BY_LV[it['lv']],
                    'source_kind': 'model', 'source_raw': SOURCE_RAW,
                    'kp': [it['kp']],
                    'prov': {'model_id': a.model_id, 'dsl_ref': DSL_REF, 'gen': it['gen'],
                             'type': it['type'], 'lv': it['lv'], 'seed': SEED,
                             'paper_ord': p['ord']},
                    'confidence': CONFIDENCE,
                    'tags': [{'domain': '方法', 'name': f'解方程·{qb.TYPE_NAME[it["type"]]}'}],
                })
    (OUT / '题目包.json').write_text(
        json.dumps({'source_line': ARTIFACT['source_line'], 'items': pack},
                   ensure_ascii=False, indent=1), encoding='utf-8')
    if not (a.check_only or a.apply):
        return

    conn = ing.open_db(a.db)
    qids, errs, grades = [], [], {}
    conn.execute('BEGIN')
    for i, item in enumerate(pack):
        res = ing.ingest_one(conn, item, i, False)
        qid, e = res[0], res[1]
        g = res[2] if len(res) > 2 else None
        if g:
            grades[g['name']] = grades.get(g['name'], 0) + 1
        (errs.extend(e) if e else qids.append(qid))
    if a.check_only or errs:
        conn.rollback()
    else:
        conn.commit()
    print(f'入库：过闸 {len(qids)}/{len(pack)}　等级={grades}')
    if errs:
        for e in errs[:10]:
            print('  🔴', e)
        sys.exit(1)
    if a.check_only:
        print('🟢 干跑全绿（已回滚）')
        return

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
                               'layout': {'layout': '专项卷', 'body_pt': 12,
                                          'sections': lay},
                               'sections': secs})
    sp = OUT / '组卷spec.json'
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding='utf-8')
    print('组卷 spec →', sp)
    conn.close()
    if a.assemble:
        import subprocess
        r = subprocess.run([sys.executable, str(ROOT / '工具箱' / '组卷' / 'paper_tool.py'),
                            'assemble', '--spec', str(sp), '--db', a.db],
                           text=True, encoding='utf-8')
        sys.exit(r.returncode)


if __name__ == '__main__':
    main()
