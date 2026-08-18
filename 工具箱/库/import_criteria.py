# -*- coding: utf-8 -*-
"""判据首批导入：三个来源 → kb.db 的 criterion（D-13 判据沉淀）。

    python 工具箱\\库\\import_criteria.py            # 导入（幂等，重跑不翻倍）
    python 工具箱\\库\\import_criteria.py --dry-run  # 只算不写

三个来源：
  ① 认知\\考古\\备课帮坑清单.md §6 —— 75 条（line='录入'，照文档标注 status='现行'）
  ② prd\\PRD-001-教辅整书切割测试\\产物\\模板规则.json —— 52 条机读判据
     （同时把「系列通用」的模板信息写一条 ingest_template：方言A-2026 同步典例考点讲义系列）
  ③ 手写补录 —— 切割试验三大坑 + 两条**废止示范**（superseded_by 挂替代条）

幂等口径：按 (line, scene, rule) 判重（kb 里有 ux_criterion_lsr 唯一索引兜底）；
命中即比对 why/source_ref/status/superseded_by，有变才更新，不翻倍不静默覆盖。
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / '知识库' / 'kb.db'
SRC_KENG = ROOT / '认知' / '考古' / '备课帮坑清单.md'
SRC_TPL = ROOT / 'prd' / 'PRD-001-教辅整书切割测试' / '产物' / '模板规则.json'
CUT_REPORT = r'试验场\切割测试-20260817\切割报告.md'

SPLIT_PIPE = re.compile(r'(?<!\\)\|')


# ══════════════════════════════════════════════════════════════════════
# 来源① 备课帮坑清单 §6（75 条）
# ══════════════════════════════════════════════════════════════════════
def load_keng():
    text = SRC_KENG.read_text(encoding='utf-8').splitlines()
    start = next(i for i, l in enumerate(text) if l.startswith('## §6'))
    end = next((i for i in range(start + 1, len(text)) if text[i].startswith('## ')), len(text))
    recs = []
    for line in text[start:end]:
        if not re.match(r'^\|\s*R\d+\s*\|', line):
            continue
        # 🔴 只切「未转义」的竖线（R05 的 rule 里写着 \|---\| ），并且只削首尾空列——
        #    中间空列若被顺手丢掉会整行错位（列错位是静默坏账）。
        cells = [c.replace('\\|', '|').strip() for c in SPLIT_PIPE.split(line)]
        if cells and cells[0] == '':
            cells = cells[1:]
        if cells and cells[-1] == '':
            cells = cells[:-1]
        if len(cells) != 5:
            print(f'⚠️ 跳过异常行（列数 {len(cells)}≠5）：{line[:60]}')
            continue
        rid, scene, rule = cells[0], cells[1], cells[2]
        why = cells[3] if len(cells) > 3 else ''
        old_ref = cells[4] if len(cells) > 4 else ''
        recs.append({
            'id': f'BKB-{rid}',
            'line': '录入',                       # 文档头明写 line='录入'、status='现行'
            'scene': scene, 'rule': rule, 'why': why,
            'source_ref': f'认知\\考古\\备课帮坑清单.md §6 {rid}' + (f'；老区正本：{old_ref}' if old_ref else ''),
            'status': '现行', 'superseded_by': None,
        })
    return recs


# ══════════════════════════════════════════════════════════════════════
# 来源② PRD-001 模板规则.json（52 条 + 1 条 ingest_template）
# ══════════════════════════════════════════════════════════════════════
def load_tpl():
    d = json.loads(SRC_TPL.read_text(encoding='utf-8'))
    recs = []
    for x in d['判据']:
        # 🔴 裁量：criterion 表没有「档/置信/来源」列，不自造字段——原样并进 source_ref 保住可回查。
        ref = (f'prd\\PRD-001-教辅整书切割测试\\产物\\模板规则.json {x["id"]}'
               f'（档：{x.get("档", "")}；置信：{x.get("置信", "")}；来源：{x.get("来源", "")}）')
        recs.append({
            'id': f'TPL-{x["id"]}', 'line': '录入',   # 52 条全是 docx 探测/切割/抽离判据
            'scene': x['scene'], 'rule': x['rule'], 'why': x.get('why', ''),
            'source_ref': ref, 'status': '现行', 'superseded_by': None,
        })
    n_general = sum(1 for x in d['判据'] if '系列通用' in x.get('档', ''))
    fingerprint = next((x['rule'] for x in d['判据'] if x['id'] == 'A1'), '')
    tpl_row = {
        'id': 'IT-方言A-2026',
        'name': d['模板名'],
        'layout_traits': f'{d["适用"]}｜识别指纹：{fingerprint}｜52 条判据中 {n_general} 条标「系列通用」｜'
                         f'🔴 铁律：{d["铁律"]}',
        'rules_ref': 'prd\\PRD-001-教辅整书切割测试\\产物\\模板规则.json（+ 同卡 脚本\\）',
        'sample_ref': f'prd\\PRD-001-教辅整书切割测试\\产物\\切割结果.json；实证来源：{d["实证来源"]}',
        'status': '在用',
    }
    return recs, tpl_row


# ══════════════════════════════════════════════════════════════════════
# 来源③ 手写补录（三大坑 + 两条替代条 + 两条废止示范）
# ══════════════════════════════════════════════════════════════════════
def load_manual():
    return [
        {'id': 'CUT-01', 'line': '录入', 'status': '现行', 'superseded_by': None,
         'scene': '读 docx 段落文本（上下标 w:vertAlign）',
         'rule': '必须读 XML run 级并单独保 `w:rPr/w:vertAlign`（上标→^{}、下标→_{}）；禁用 python-docx 的 `paragraph.text`',
         'why': '上下标丢了不是「缺口」是**静默改错数值**：科学记数法四个选项 `0.1×10¹¹…` 被读成 `0.1×1011…` 全变成看起来合法的错数；'
                '`﹣11²+22×11＝121` 被读成 `﹣112+22×11＝121`（算术不自洽，-112+242=130≠121）。'
                '这种坏法文本通顺、数字齐全、无乱码，只有算才知道错，下游 LLM 会误判成「原卷有错」。全书 423 段中 112 段（26.5%）两种读法不一致',
         'source_ref': CUT_REPORT + ' §5-①（_对照结果.txt）'},

        {'id': 'CUT-02', 'line': '录入', 'status': '现行', 'superseded_by': None,
         'scene': '读 docx 公式（OMML 不在文本流里）',
         'rule': '公式必须单独走 `m:oMath`/`m:r`/`m:t` 取，绝不能只收 `w:r/w:t`；相邻 `m:oMath` 合并成一个表达，序列化时防 `$..$$..$` 被误判块级',
         'why': '`paragraph.text` 一个字都不收 OMML：整组选项读出来是 `A．　B．　C．　D．`（全空）、`（2）解方程：．`；'
                '有的卷连普通数字都塞进 OMML（`【解析】 ．` ← 实为 `$830000=8.3\\times 10^{5}$`）。整行解析凭空消失且无报错',
         'source_ref': CUT_REPORT + ' §5-②/§5-⑨'},

        {'id': 'CUT-03', 'line': '录入', 'status': '现行', 'superseded_by': None,
         'scene': '读 docx 表格单元格（拍平丢图）',
         'rule': '单元格里装**块列表**（递归含嵌套表 + 格内图 + 格内公式），禁止在解析期拍平成字符串；凡「拍平」操作必配守恒闸',
         'why': '第一版 `table_to_block` 把单元格渲成纯文本，题 23（项目学习题）的示意图当场丢 1 张，'
                '靠图片零丢失闸报 `FAIL 28/27` 才抓出来——拍平就是丢信息的地方，没有闸就是静默丢',
         'source_ref': CUT_REPORT + ' §5-③（图片守恒闸 §4.1）'},

        # —— 两条替代条（现行），供下面的废止条挂 superseded_by ——
        {'id': 'CUT-04', 'line': '录入', 'status': '现行', 'superseded_by': None,
         'scene': '公式重的 docx 走哪条链',
         'rule': '🔴 有文字层的 docx 一律本地直读（python-docx + lxml 直读 word/document.xml），**公式越重越该直读**；OCR 只用于无文字层的源',
         'why': 'v2 实测 OMML→LaTeX 129/129、9 卷 0 失败、未识别标签 0；把公式重的 docx 送 OCR 是白花钱且引入识别错',
         'source_ref': '认知\\数据结构.md §2.7 D-18；' + CUT_REPORT + ' §4.2/§7-④'},

        {'id': 'CUT-05', 'line': '录入', 'status': '现行', 'superseded_by': None,
         'scene': '图片/扫描/拍照源走哪个 OCR 引擎',
         'rule': '🔴 一律本地 MinerU；TextIn 云 OCR 只作**显式手动**逃生通道，不进任何自动回落链',
         'why': '2026-08-13 拍板：本地实测已够用、免费不出网；且云链的乱序闸对拼贴卷必误报，自动回落＝白花钱又引噪音',
         'source_ref': '认知\\数据结构.md §2.7 D-18（图片链继承老区 skill 版面OCR抽取/试卷OCR重排 的分流判据与闸设计）'},

        # —— 两条废止示范（废止不删，带替代链可回查）——
        {'id': 'DEP-01', 'line': '录入', 'status': '废止', 'superseded_by': 'CUT-04',
         'scene': '公式重的 docx 走哪条链（老规则）',
         'rule': '【已废止】`oMath ≥ 8` 判「公式重」⇒ 跳过本地直转、直接送 OCR（老区 OMATH_HEAVY=8 分流）',
         'why': '那是老区**没有可信 OMML 通道**时的补偿动作，不是最优解；'
                '老区实现见 `.claude/skills/版面OCR抽取/scripts/ingest.py:31-32,264-265`（注释写「超过」实际代码是 `>=`）。'
                'v2 已实测直读 129/129 零失败 ⇒ 本条推翻，替代条 CUT-04',
         'source_ref': '认知\\数据结构.md §2.7（明文「废止老规则」）；认知\\考古\\备课帮坑清单.md R66/§7-⑫'},

        {'id': 'DEP-02', 'line': '录入', 'status': '废止', 'superseded_by': 'CUT-05',
         'scene': '图片/扫描源 OCR 引擎（老规则）',
         'rule': '【已废止】本地 OCR 失败即**自动回落** TextIn 云 OCR',
         'why': '2026-08-13 用户拍板 TextIn 退出自动回落链：本地 MinerU 已够用、免费不出网，'
                '云链对拼贴卷的乱序闸必误报（该闸同批降级为只警告不拦）⇒ 本条推翻，替代条 CUT-05',
         'source_ref': '认知\\数据模型草案.md D-13「生命周期闸：经验会被推翻（实例：TextIn 退场、乱序闸降级）」'},
    ]


# ══════════════════════════════════════════════════════════════════════
# 写库（幂等）
# ══════════════════════════════════════════════════════════════════════
def upsert(conn, rec, now, dry):
    row = conn.execute(
        'SELECT id, why, source_ref, status, superseded_by FROM criterion WHERE line=? AND scene=? AND rule=?',
        (rec['line'], rec['scene'], rec['rule'])).fetchone()
    if row:
        cur = {'why': row[1], 'source_ref': row[2], 'status': row[3], 'superseded_by': row[4]}
        want = {'why': rec['why'], 'source_ref': rec['source_ref'], 'status': rec['status'],
                'superseded_by': cur['superseded_by']}   # superseded_by 走第二遍统一挂
        if cur == want:
            return row[0], '沿用'
        if not dry:
            conn.execute('UPDATE criterion SET why=?, source_ref=?, status=? WHERE id=?',
                         (rec['why'], rec['source_ref'], rec['status'], row[0]))
        return row[0], '更新'
    if not dry:
        conn.execute(
            'INSERT INTO criterion(id, line, scene, rule, why, source_ref, status, superseded_by, created_at)'
            ' VALUES (?,?,?,?,?,?,?,NULL,?)',
            (rec['id'], rec['line'], rec['scene'], rec['rule'], rec['why'],
             rec['source_ref'], rec['status'], now))
    return rec['id'], '新增'


def upsert_template(conn, t, now, dry):
    row = conn.execute('SELECT id FROM ingest_template WHERE id=?', (t['id'],)).fetchone()
    if row:
        if not dry:
            conn.execute('UPDATE ingest_template SET name=?, layout_traits=?, rules_ref=?, sample_ref=?, status=?'
                         ' WHERE id=?',
                         (t['name'], t['layout_traits'], t['rules_ref'], t['sample_ref'], t['status'], t['id']))
        return '更新'
    if not dry:
        conn.execute('INSERT INTO ingest_template(id,name,layout_traits,rules_ref,sample_ref,status,created_at)'
                     ' VALUES (?,?,?,?,?,?,?)',
                     (t['id'], t['name'], t['layout_traits'], t['rules_ref'], t['sample_ref'], t['status'], now))
    return '新增'


def main():
    ap = argparse.ArgumentParser(description='判据首批导入（三来源 → criterion）')
    ap.add_argument('--db', default=str(KB))
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f'🔴 库不存在：{db}——先跑 init_db.py')
        return 2

    keng = load_keng()
    tpl, tpl_row = load_tpl()
    manual = load_manual()
    print(f'来源①备课帮坑清单 §6：{len(keng)} 条　来源②PRD-001 模板规则.json：{len(tpl)} 条　来源③手写补录：{len(manual)} 条')

    conn = sqlite3.connect(str(db))
    conn.execute('PRAGMA foreign_keys=ON')
    now = datetime.now().isoformat(timespec='seconds')
    try:
        idmap, tally = {}, {}
        for label, recs in (('①坑清单', keng), ('②模板规则', tpl), ('③手写补录', manual)):
            per = {}
            for r in recs:
                real_id, act = upsert(conn, r, now, args.dry_run)
                idmap[r['id']] = real_id
                per[act] = per.get(act, 0) + 1
            tally[label] = per
        # 第二遍：挂废止链（替代条此时必已存在）
        chains = 0
        for r in keng + tpl + manual:
            if r.get('superseded_by'):
                target = idmap.get(r['superseded_by'], r['superseded_by'])
                if not args.dry_run:
                    conn.execute('UPDATE criterion SET superseded_by=? WHERE id=?', (target, idmap[r['id']]))
                chains += 1
        tpl_act = upsert_template(conn, tpl_row, now, args.dry_run)
        if not args.dry_run:
            conn.commit()

        print('\n【导入动作】')
        for label, per in tally.items():
            print(f'  {label:<10}' + '　'.join(f'{k} {v}' for k, v in sorted(per.items())))
        print(f'  废止链挂接 {chains} 条　ingest_template：{tpl_act}')

        print('\n【criterion 计数表 · 按线 × 状态】')
        rows = conn.execute('SELECT line, status, COUNT(*) FROM criterion GROUP BY line, status ORDER BY line, status').fetchall()
        lines = sorted({r[0] for r in rows})
        m = {(r[0], r[1]): r[2] for r in rows}
        print(f'  {"线":<8}{"现行":>6}{"废止":>6}{"合计":>6}')
        for ln in lines:
            a, b = m.get((ln, '现行'), 0), m.get((ln, '废止'), 0)
            print(f'  {ln:<8}{a:>6}{b:>6}{a + b:>6}')
        ta = sum(v for k, v in m.items() if k[1] == '现行')
        tb = sum(v for k, v in m.items() if k[1] == '废止')
        print(f'  {"合计":<8}{ta:>6}{tb:>6}{ta + tb:>6}')
        n_tpl = conn.execute('SELECT COUNT(*) FROM ingest_template').fetchone()[0]
        print(f'\n  ingest_template 共 {n_tpl} 条')
        if args.dry_run:
            conn.rollback()
            print('\n（--dry-run：上表是「若真跑」的结果，事务已回滚，库未变）')
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
