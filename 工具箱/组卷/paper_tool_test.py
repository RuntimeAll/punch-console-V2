# -*- coding: utf-8 -*-
"""组卷端到端自证：沙盘库 + 正向全链 + 反向三例，跑完打印判绿表。

    python 工具箱\\组卷\\paper_tool_test.py

链路：临时沙盘库（照真 DDL 建）→ 铺首枝 → ingest 4 题（题面纯净、只放 $算式$）→
      assemble（一节走 qids 一节走 take）→ 幂等重跑 → render-pack + 契约逐字自检 →
      finalize 验状态 → 三个反向用例（取不足报差额 / 同册重复题 / 节名对不上 layout）。

判绿口径：**正向全过 + 反向全拒 + 反向一行不落库**（任一条不符即退出码 1）。
🔴 绝不碰主位两库：库建在系统临时目录，只有 render-pack 的落盘要在 v2 根下
   （工具强制相对路径），用 试验场/_组卷自测/ 当草稿纸，跑完删干净。
"""
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
SCRATCH_REL = '试验场/_组卷自测'
SCRATCH = ROOT / SCRATCH_REL
rows = []                      # (环节, 用例, 期望, 实际, 判)


def rec(stage, name, want, got, ok):
    rows.append((stage, name, want, str(got), bool(ok)))


def run(argv, expect, stage, name):
    p = subprocess.run([sys.executable] + argv, cwd=str(ROOT), capture_output=True)
    out = (p.stdout + p.stderr).decode('utf-8', 'replace').strip()
    rec(stage, name, '退出 %d' % expect, '退出 %d｜%s' % (p.returncode, out.replace('\n', ' ⏎ ')),
        p.returncode == expect)
    return out


# ══════════════════════════════════════════════════════════════════════
# 用例数据（🔴 题面 md 只放算式本体，不带「计算：」类指令词）
# ══════════════════════════════════════════════════════════════════════
def blocks(md, role):
    return {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': role, 'md': md}]}]}


def q(stem, ans, ana, diff, kp, seed):
    return {'blocks': blocks(stem, '题面'), 'answer_blocks': blocks(ans, '答案'),
            'analysis_blocks': blocks(ana, '解析'),
            'qtype': '计算题', 'difficulty': diff, 'source_kind': 'model',
            'source_raw': '自编·组卷自测 %d' % seed, 'kp': [kp],
            'prov': {'model_id': 'EM-自测', 'params': {'seed': seed}, 'seed': seed},
            'confidence': 95}


PACK = {'source_line': '每日打卡', 'items': [
    q('$(-3)+(-5)-(-2)$', '$-6$', '$(-3)+(-5)-(-2)=-3-5+2=-6$', '巩固', '有理数的加减混合运算', 1),
    q('$12-(-7)+(-9)$', '$10$', '$12-(-7)+(-9)=12+7-9=10$', '巩固', '有理数的加减混合运算', 2),
    q('$-2^{2}\\times 3+(-4)\\div 2$', '$-14$',
      '$-2^{2}\\times 3+(-4)\\div 2=-4\\times 3+(-2)=-12-2=-14$', '中档', '有理数混合运算的运算顺序', 3),
    q('$(-1)^{3}\\times(-6)+(-3)^{2}$', '$15$',
      '$(-1)^{3}\\times(-6)+(-3)^{2}=(-1)\\times(-6)+9=6+9=15$', '中档', '有理数混合运算的运算顺序', 4),
]}

LAYOUT = {'layout': 'dense_sections', 'body_pt': 12.5, 'watermark': None, 'sections': [
    {'name': '整数加减混合链', 'slot': 'expr', 'grid': 'block', 'gap': 0, 'gap_each': 11, 'ans_cols': 1},
    {'name': '混合运算三步', 'slot': 'expr', 'grid': 'block', 'gap': 0, 'gap_each': 13, 'ans_cols': 1},
]}


def spec_main(qids, artifact_id=None):
    art = {'id': artifact_id} if artifact_id else {
        'name': '自测·有理数一天打卡', 'kind': '打卡册', 'source_line': '每日打卡'}
    return {'artifact': art, 'papers': [{
        'kind': '打卡天', 'title': '第一天·有理数的加减与混合', 'ord': 1, 'layout': LAYOUT,
        'sections': [
            {'name': '整数加减混合链', 'qids': qids[:2]},
            {'name': '混合运算三步',
             'take': {'kp': '有理数混合运算的运算顺序', 'difficulty': '中档',
                      'unused_only': True, 'limit': 2}},
        ]}]}


def write(name, obj):
    p = SCRATCH / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    return f'{SCRATCH_REL}/{name}'


# ══════════════════════════════════════════════════════════════════════
# render-pack/v1 契约自检（逐字对契约 + 与库对账，专挡"悄悄多一层转换"）
# ══════════════════════════════════════════════════════════════════════
def check_contract(pack_path, db):
    pack = json.loads((ROOT / pack_path).read_text(encoding='utf-8'))
    conn = sqlite3.connect(db)
    errs = []

    def need(cond, msg):
        if not cond:
            errs.append(msg)

    need(pack.get('contract') == 'render-pack/v1', f'contract={pack.get("contract")!r}')
    for k in ('id', 'name', 'kind'):
        need(k in (pack.get('artifact') or {}), f'artifact 缺 {k}')
    need(isinstance(pack.get('papers'), list) and pack['papers'], 'papers 必须非空数组')
    for pi, p in enumerate(pack.get('papers') or []):
        for k in ('id', 'kind', 'title', 'ord', 'layout', 'items'):
            need(k in p, f'papers[{pi}] 缺 {k}')
        lay_names = [s.get('name') for s in (p.get('layout') or {}).get('sections') or []]
        ords = [it.get('ord') for it in p.get('items') or []]
        need(ords == list(range(1, len(ords) + 1)), f'papers[{pi}] 题序不连续 {ords}')
        for ii, it in enumerate(p.get('items') or []):
            tag = f'papers[{pi}].items[{ii}]'
            for k in ('ord', 'section', 'score', 'question'):
                need(k in it, f'{tag} 缺 {k}')
            need(it.get('section') in lay_names, f'{tag}.section 不在 layout.sections')
            qq = it.get('question') or {}
            for k in ('id', 'blocks', 'answer_blocks', 'analysis_blocks', 'qtype', 'difficulty'):
                need(k in qq, f'{tag}.question 缺 {k}')
            need(isinstance(qq.get('blocks'), dict) and qq['blocks'].get('v') == 2,
                 f'{tag}.blocks 不是块流 v2')
            row = conn.execute(
                'SELECT blocks_json,qtype_code,diff_code FROM question WHERE id=?',
                (qq.get('id'),)).fetchone()
            need(row is not None, f'{tag}.question.id 库里没有')
            if row:
                # 🔴 存取同构：吐出去的 blocks 必须与库里 blocks_json 逐字一致（有转换层就在这被抓）
                need(json.loads(row[0]) == qq.get('blocks'), f'{tag} blocks 与库不一致（出现转换层）')
                for dom, key in (('qtype', 'qtype'), ('difficulty', 'difficulty')):
                    lab = conn.execute('SELECT label FROM dict_item WHERE domain=? AND code=?',
                                       (dom, row[1] if dom == 'qtype' else row[2])).fetchone()
                    need(lab and lab[0] == qq.get(key), f'{tag}.{key} 不是中文标签（{qq.get(key)!r}）')
            for r in (qq.get('blocks') or {}).get('rows') or []:
                for c in (r or {}).get('cells') or []:
                    md = str((c or {}).get('md') or '')
                    for w in ('计算：', '计算:', '求解：', '化简：', '解方程：', '解方程:'):
                        need(w not in md, f'{tag} 题面带指令词 {w!r}')
    conn.close()
    return errs


# ══════════════════════════════════════════════════════════════════════
def main():
    sys.path.insert(0, str(ROOT / '工具箱' / '库'))
    import init_db

    tmpdir = Path(tempfile.mkdtemp(prefix='paper_tool_test_'))
    db = str(tmpdir / 'kb_test.db')
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    D = ['--db', db]
    try:
        init_db.apply_schema(Path(db), ROOT / '工具箱' / '库' / 'schema_kb.sql')
        init_db.seed_dict(Path(db))
        run(['工具箱/kg/kg_tool.py', *D, 'build-branch', '工具箱/kg/首枝-浙教七上.json'],
            0, '备料', '铺首枝（48 节点）')
        out = run(['工具箱/回流/ingest_flow.py', *D, 'ingest', write('题目包.json', PACK)],
                  0, '备料', 'ingest 4 题过三闸入草稿')
        # 🔴 按入库回吐序取 qid：同一秒入库 created_at 相同，再按 created_at 排就退化成按 id 排
        qids = out.split('入库（草稿）：')[1].split('\n')[0].split()
        rec('备料', '4 道题入库', '4 个 qid', qids, len(qids) == 4)

        conn = sqlite3.connect(db)

        # ── 正向 ①assemble ──
        out = run(['工具箱/组卷/paper_tool.py', *D, 'assemble',
                   '--spec', write('组卷.json', spec_main(qids))], 0, '正向', 'assemble 组册')
        m = re.search(r'A\d{8}[0-9a-f]{6}', out)          # 🔴 别按空白切：中文逗号不带空格会粘住 id
        rec('正向', '回吐 artifact id', '有', m.group(0) if m else '无', bool(m))
        if not m:
            return report()
        aid = m.group(0)
        pid = conn.execute('SELECT id FROM paper').fetchone()[0]
        items = conn.execute(
            'SELECT ord,question_id,section FROM paper_item WHERE paper_id=? ORDER BY ord',
            (pid,)).fetchall()
        rec('正向', '题序 1..N 连续', '[1,2,3,4]', [i[0] for i in items],
            [i[0] for i in items] == [1, 2, 3, 4])
        rec('正向', 'qids 路按 spec 顺序落位', qids[:2], [i[1] for i in items[:2]],
            [i[1] for i in items[:2]] == qids[:2])
        rec('正向', 'take 路归到第二节', '混合运算三步×2', [i[2] for i in items[2:]],
            all(i[2] == '混合运算三步' for i in items[2:]) and len(items) == 4)

        # ── 正向 ②幂等重排 ──
        run(['工具箱/组卷/paper_tool.py', *D, 'assemble',
             '--spec', write('组卷.json', spec_main(qids, aid))], 0, '正向', 'assemble 重跑（幂等）')
        np_ = conn.execute('SELECT COUNT(*) FROM paper').fetchone()[0]
        ni = conn.execute('SELECT COUNT(*) FROM paper_item').fetchone()[0]
        rec('正向', '重跑不长新卷/不翻倍', '1 卷 4 题', f'{np_} 卷 {ni} 题', (np_, ni) == (1, 4))

        # ── 正向 ③render-pack + 契约 ──
        packrel = f'{SCRATCH_REL}/render-pack.json'
        run(['工具箱/组卷/paper_tool.py', *D, 'render-pack', '--artifact', aid, '--out', packrel],
            0, '正向', 'render-pack 导出')
        errs = check_contract(packrel, db)
        rec('正向', 'render-pack/v1 契约逐字自检', '0 条不合格', f'{len(errs)} 条：{errs[:2]}', not errs)

        # ── 正向 ④finalize ──
        run(['工具箱/组卷/paper_tool.py', *D, 'finalize', '--artifact', aid],
            0, '正向', 'finalize 定稿+promote')
        qs = dict(conn.execute('SELECT status,COUNT(*) FROM question GROUP BY status').fetchall())
        ps = dict(conn.execute('SELECT status,COUNT(*) FROM paper GROUP BY status').fetchall())
        kp = json.loads(conn.execute('SELECT kp_ids_json FROM artifact WHERE id=?',
                                     (aid,)).fetchone()[0] or '[]')
        rec('正向', 'finalize 后题全上架', "{'上架': 4}", qs, qs == {'上架': 4})
        rec('正向', 'finalize 后卷全定稿', "{'定稿': 1}", ps, ps == {'定稿': 1})
        rec('正向', '覆盖考点回填叶子', '2 个', f'{len(kp)} 个 {kp}', len(kp) == 2)

        # ── 反向三例：整体失败（退出 1）且一行不落库 ──
        before = tuple(conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                       for t in ('artifact', 'paper', 'paper_item'))
        bad1 = {'artifact': {'name': '反例①', 'kind': '打卡册'},
                'papers': [{'kind': '打卡天', 'title': '反例一', 'ord': 1, 'layout': LAYOUT,
                            'sections': [{'name': '整数加减混合链',
                                          'take': {'kp': '有理数的加减混合运算',
                                                   'unused_only': True, 'limit': 2}}]}]}
        bad2 = {'artifact': {'id': aid},
                'papers': [{'kind': '打卡天', 'title': '反例二', 'ord': 2, 'layout': LAYOUT,
                            'sections': [{'name': '整数加减混合链', 'qids': qids[:2]}]}]}
        bad3 = {'artifact': {'name': '反例③', 'kind': '打卡册'},
                'papers': [{'kind': '打卡天', 'title': '反例三', 'ord': 1, 'layout': LAYOUT,
                            'sections': [{'name': '根本没有的节', 'qids': qids[:1]}]}]}
        for i, (obj, name) in enumerate(((bad1, 'take 取不足→报差额整体失败'),
                                         (bad2, '同 artifact 重复题→拒'),
                                         (bad3, 'section 名不在 layout→拒')), 1):
            run(['工具箱/组卷/paper_tool.py', *D, 'assemble',
                 '--spec', write(f'反例{i}.json', obj)], 1, '反向', name)
        after = tuple(conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                      for t in ('artifact', 'paper', 'paper_item'))
        rec('反向', '三例全量回滚（库计数不变）', before, after, before == after)

        lg = dict(conn.execute(
            "SELECT result,COUNT(*) FROM skill_log WHERE skill='组卷' GROUP BY result").fetchall())
        rec('账单', 'skill_log 成功/失败都留账', "{'成功':4,'失败':3}", lg,
            lg == {'成功': 4, '失败': 3})
        conn.close()
        return report()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(SCRATCH, ignore_errors=True)


def report():
    print('=' * 116)
    print(f'{"环节":<6}{"用例":<30}{"期望":<18}{"实际":<56}{"判"}')
    print('-' * 116)
    for stage, name, want, got, ok in rows:
        print(f'{stage:<6}{name:<30}{str(want)[:16]:<18}{got[:54]:<56}{"√" if ok else "×"}')
    print('-' * 116)
    n_ok = sum(1 for r in rows if r[4])
    green = n_ok == len(rows)
    print(f'{n_ok}/{len(rows)} 条通过')
    print('结论：' + ('🟢 全绿（正向全过、反向全拒且不落库）' if green else '🔴 有用例不符，组卷闸不成立'))
    print('=' * 116)
    return 0 if green else 1


if __name__ == '__main__':
    raise SystemExit(main())
