# -*- coding: utf-8 -*-
"""卷面考频分析 —— 任意已组卷的册 → 考点考频报告 + 考卷结构模型（可复用沉淀）
==============================================================================
定位（2026-08-22 窗S 首立，用户令「考点考频分析+试卷总结，存起来后面直接拿来用」）：
分析不是聊天里说一遍就散的东西——本工具把一份卷的结构画像**机器算**出来，落两个地方：
  ① 报告 markdown（教研可读：单元权重/考点考频/难度分布/大题结构）→ 出件目录，
     挂 artifact.files 成为册的一部分；
  ② exam_model 一行（机器可用：params_json 装全量结构化数据）→ 后续出同型卷/配比
     参照/备课重点排序直接查库拿。

考频口径（🔴 单卷口径，如实标注）：
  考点权重 = Σ(主挂载题分值) + 0.5 × Σ(次挂载题分值)；单元权重 = Σ(该单元下考点权重)。
  分级：权重≥10=核心｜5~9.5=重点｜<5=覆盖。这是**这一份卷**的考频画像；
  kp.freq（全局考频）要跨卷积累后另行回填，单卷不冒充全局（n=1 不定调）。

用法：
  python 工具箱/组卷/卷面考频分析.py --artifact A2026… [--paper-ord 1]
         [--out-dir 产物/…]           # 缺省=册 files 第一件所在目录
         [--save-model]               # 落/更新 exam_model（幂等 by name）
         [--db 知识库/kb.db]
🔴 --save-model 写库（exam_model + skill_log），动主位库前先排写窗口；不带它=纯只读。
"""
import argparse
import json
import sqlite3
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]


def kp_path(conn, kid):
    """考点 id → (单元名, 小节名或None, 考点名)。"""
    names, cur = [], kid
    while cur:
        r = conn.execute('SELECT name, level, parent_id FROM kp WHERE id=?', (cur,)).fetchone()
        if r is None:
            return ('（幽灵节点）', None, kid)
        names.append((r[1], r[0]))
        cur = r[2]
    d = dict(names)
    return (d.get('单元', '？'), d.get('小节'), d.get('考点', kid))


def analyze(conn, artifact_id, paper_ord):
    art = conn.execute('SELECT id, name FROM artifact WHERE id=?', (artifact_id,)).fetchone()
    assert art, f'🔴 artifact {artifact_id} 不存在'
    paper = conn.execute('SELECT id, title, layout_json FROM paper WHERE artifact_id=? AND ord=?',
                         (artifact_id, paper_ord)).fetchone()
    assert paper, f'🔴 册 {artifact_id} 没有 ord={paper_ord} 的卷'
    layout = json.loads(paper[2] or '{}')

    items = conn.execute(
        'SELECT pi.ord, pi.section, pi.score, pi.question_id, q.diff_code '
        'FROM paper_item pi JOIN question q ON q.id=pi.question_id '
        'WHERE pi.paper_id=? ORDER BY pi.ord', (paper[0],)).fetchall()
    assert items, '🔴 卷里没有题'

    diff_label = {r[0]: r[1] for r in conn.execute(
        "SELECT code, label FROM dict_item WHERE domain='difficulty'")}

    # 分值兜底：paper_item.score 为空时按 layout.sections[].item_scores 位置取
    # （复刻类 spec 分值常只写在版式层——两处都没有才是真 0 分，如实记 0 并打警）
    sec_scores_cfg = {s['name']: s.get('item_scores') or []
                      for s in layout.get('sections', [])}
    sec_seen = defaultdict(int)
    fixed = []
    for ordn, section, score, qid, diff in items:
        idx = sec_seen[section]
        sec_seen[section] += 1
        if score is None:
            cfg = sec_scores_cfg.get(section, [])
            score = cfg[idx] if idx < len(cfg) else 0
            if score == 0:
                print(f'⚠️ 题 ord={ordn}（{section}）两处都无分值，按 0 计')
        fixed.append((ordn, section, score, qid, diff))
    items = fixed

    kp_w = defaultdict(lambda: {'主': 0.0, '次': 0.0, '主题号': [], '次题号': []})
    sec_score = defaultdict(float)
    diff_score = defaultdict(float)
    for ordn, section, score, qid, diff in items:
        sec_score[section] += score
        diff_score[diff_label.get(diff, diff or '未标')] += score
        for kid, is_p in conn.execute(
                'SELECT kp_id, is_primary FROM question_kp WHERE question_id=?', (qid,)):
            slot = '主' if is_p else '次'
            kp_w[kid][slot] += score
            kp_w[kid][slot + '题号'].append(ordn)

    rows = []
    for kid, w in kp_w.items():
        unit, sec, kp = kp_path(conn, kid)
        weight = w['主'] + 0.5 * w['次']
        grade = '核心' if weight >= 10 else ('重点' if weight >= 5 else '覆盖')
        rows.append({'kp_id': kid, '单元': unit, '小节': sec, '考点': kp,
                     '主分值': w['主'], '次分值': w['次'], '权重': round(weight, 1),
                     '级': grade, '主题号': sorted(w['主题号']), '次题号': sorted(w['次题号'])})
    rows.sort(key=lambda r: -r['权重'])

    unit_w = defaultdict(float)
    for r in rows:
        unit_w[r['单元']] += r['权重']
    total_w = sum(unit_w.values()) or 1

    return {
        'artifact': {'id': art[0], 'name': art[1]},
        'paper': {'id': paper[0], 'title': paper[1],
                  'full_score': layout.get('full_score'),
                  'duration_min': layout.get('duration_min')},
        'sections': [{'name': s['name'], 'slot': s.get('slot'),
                      'score': sec_score.get(s['name'], 0),
                      'score_note': s.get('score_note')}
                     for s in layout.get('sections', [])],
        'units': sorted(([u, round(w, 1), round(100 * w / total_w)]
                         for u, w in unit_w.items()), key=lambda x: -x[1]),
        'kp_rows': rows,
        'diff': dict(diff_score),
        'n_items': len(items),
        'analyzed_at': datetime.now().strftime('%Y-%m-%d'),
    }


def render_md(a):
    L = []
    p = a['paper']
    L.append(f"# {p['title']} · 考点考频分析")
    L.append('')
    L.append(f"> 册 {a['artifact']['id']}《{a['artifact']['name']}》卷 {p['id']}｜"
             f"满分 {p['full_score']}｜{p['duration_min']} 分钟｜{a['n_items']} 题｜"
             f"机器算自 kb.db（paper_item×question_kp），{a['analyzed_at']}。")
    L.append('> 🔴 考频口径＝**本卷单卷画像**（主挂载分值+0.5×次挂载分值）；'
             '全局考频待跨卷积累回填 kp.freq，单卷不冒充全局。')
    L.append('')
    L.append('## 一、单元权重（备课重点排序）')
    L.append('')
    L.append('| 单元 | 权重 | 占比 |')
    L.append('|---|---:|---:|')
    for u, w, pct in a['units']:
        L.append(f'| {u} | {w} | {pct}% |')
    L.append('')
    L.append('## 二、考点 × 考频明细')
    L.append('')
    L.append('| 级 | 考点 | 单元/小节 | 权重 | 主挂(题号) | 次挂(题号) | kp_id |')
    L.append('|---|---|---|---:|---|---|---|')
    for r in a['kp_rows']:
        loc = r['单元'] + ('／' + r['小节'] if r['小节'] else '')
        zhu = f"{r['主分值']:g}分{r['主题号']}" if r['主题号'] else '—'
        ci = f"{r['次分值']:g}分{r['次题号']}" if r['次题号'] else '—'
        L.append(f"| {r['级']} | {r['考点']} | {loc} | {r['权重']:g} | {zhu} | {ci} | {r['kp_id']} |")
    L.append('')
    L.append('## 三、大题结构与难度')
    L.append('')
    L.append('| 大题 | 槽位 | 分值 | 说明 |')
    L.append('|---|---|---:|---|')
    for s in a['sections']:
        L.append(f"| {s['name']} | {s['slot']} | {s['score']:g} | {s.get('score_note') or ''} |")
    L.append('')
    diffs = '｜'.join(f'{k} {v:g}分' for k, v in
                      sorted(a['diff'].items(), key=lambda x: -x[1]))
    L.append(f'难度分值分布：{diffs}。')
    L.append('')
    L.append('## 四、命题特征观察（人工判读）')
    L.append('')
    L.append('（待补：本节由人写——机器只算数，不装懂命题人。）')
    L.append('')
    return '\n'.join(L)


def save_model(conn, a):
    name = f"{a['paper']['title']}·结构与考频模型"
    kp_ids = [r['kp_id'] for r in a['kp_rows']]
    params = {'型': '卷结构', '满分': a['paper']['full_score'],
              '时长': a['paper']['duration_min'], '大题': a['sections'],
              '单元权重': a['units'],
              '考点考频': [{k: r[k] for k in ('kp_id', '考点', '权重', '级')}
                           for r in a['kp_rows']],
              '难度分值': a['diff'], '源卷': a['paper']['id'],
              '口径': '单卷画像：主挂分值+0.5×次挂分值；跨卷积累前不回填 kp.freq'}
    row = conn.execute('SELECT id FROM exam_model WHERE name=?', (name,)).fetchone()
    if row:
        mid = row[0]
        conn.execute('UPDATE exam_model SET kp_ids_json=?, params_json=?, note=? WHERE id=?',
                     (json.dumps(kp_ids), json.dumps(params, ensure_ascii=False),
                      f"卷面考频分析自动沉淀（{a['analyzed_at']} 重算）", mid))
    else:
        mid = 'EM' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
        conn.execute('INSERT INTO exam_model(id,name,kp_ids_json,dsl_ref,params_json,note,status) '
                     "VALUES(?,?,?,?,?,?,'在用')",
                     (mid, name, json.dumps(kp_ids),
                      f"工具箱/组卷/卷面考频分析.py --artifact {a['artifact']['id']}",
                      json.dumps(params, ensure_ascii=False),
                      f"卷面考频分析自动沉淀（{a['analyzed_at']}）——首个「怎么造卷」型考察模型"))
    conn.execute('INSERT INTO skill_log(skill,action,result,detail,created_at) '
                 'VALUES(?,?,?,?,?)',
                 ('组卷', '考频分析沉淀', '成功',
                  f'{mid} ← {a["artifact"]["id"]}（考点{len(kp_ids)}）',
                  time.strftime('%Y-%m-%d %H:%M:%S')))
    return mid


def main():
    ap = argparse.ArgumentParser(description='卷面考频分析（报告+考卷结构模型）')
    ap.add_argument('--artifact', required=True)
    ap.add_argument('--paper-ord', type=int, default=1)
    ap.add_argument('--out-dir')
    ap.add_argument('--save-model', action='store_true')
    ap.add_argument('--db', default=str(ROOT / '知识库' / 'kb.db'))
    a = ap.parse_args()

    if a.save_model:
        conn = sqlite3.connect(a.db)
    else:
        conn = sqlite3.connect('file:%s?mode=ro' % Path(a.db).as_posix(), uri=True)
    try:
        res = analyze(conn, a.artifact, a.paper_ord)
        if a.out_dir:
            out_dir = ROOT / a.out_dir
        else:
            f = conn.execute('SELECT files_json FROM artifact WHERE id=?',
                             (a.artifact,)).fetchone()[0]
            files = json.loads(f or '[]')
            assert files, '🔴 册无 files 也没给 --out-dir，报告不知道落哪'
            out_dir = (ROOT / files[0]).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        md_path = out_dir / f"{res['paper']['title']}·考点考频分析.md"
        md_path.write_text(render_md(res), encoding='utf-8')
        print(f'📊 报告 → {md_path.relative_to(ROOT)}')
        for u, w, pct in res['units'][:5]:
            print(f'   {u}: 权重{w}（{pct}%）')
        if a.save_model:
            with conn:
                mid = save_model(conn, res)
            print(f'💾 exam_model → {mid}（幂等 by name）')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
