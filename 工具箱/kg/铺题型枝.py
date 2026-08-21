# -*- coding: utf-8 -*-
"""铺题型枝（窗L · 2026-08-21）——把讲义题型原料铺成 kp 第六层「题型」节点。

原料＝工具箱/kg/题型锚定映射.json（173 键，其中带 kp_id 的已锚定到具体考点叶）。
每个已锚定键在它的考点叶下建一个题型子节点；父叶一旦长出题型子节点，按「就近可挂」
（gates.assert_leaf_kp，2026-08-21 改）它自己就不再收新挂载，新题必须挂到题型层。

🔴🔴 节点 id ＝ 父叶 id + 3 位序号（001 起，同父内按讲序稳定排）——**过渡编号口径**：
   纯粹为了兼容现有按 id 前缀选题的通路（工具箱/组卷/draft_paper.py 单元维度 kp_id LIKE '前缀%'），
   让 15 位题型 id 天然落进父叶/单元的前缀集里。**下一窗映射表落地后，新节点改无位置 id**
   （kp+日期+hex 风格，位置只活在映射表/parent_id+ord 里，见 KG弹性机制设计.md 机制1），
   本次铺的这批 id 届时原样冻结，不再新增 15 位位置 id。

规则：
  · 题型名与父叶名相同 → 跳过（冗余：讲义题型就是那片叶本身，再建一层没有信息量）；
  · 多个键锚同一叶且题型名相同 → 只建一个；不同题型名同父 → 各建一个；
  · 追加四个「待归位」题型（映射件里 kp_id 为 null，调度中心裁定落点，note 记低置信待人审）；
  · 幂等：按 (parent_id, name) 查在即跳，重跑零重复（DDL 的 UNIQUE(parent_id,name) 兜底）。

用法（🔴 必须显式点名库，无默认——防误敲主位）：
    python 工具箱\\kg\\铺题型枝.py --db 试验场\\2026-08-21-七上发布闭环\\窗L沙盘.db
    python 工具箱\\kg\\铺题型枝.py --db 知识库\\kb.db --dry-run     # 只打清单不写库
前置：kp.level 的 CHECK 已扩 '题型'（先跑 工具箱/库/apply_ddl_窗L题型层.py）。
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
DEFAULT_MAP = HERE / '题型锚定映射.json'

# 四个待归位题型：映射件里 kp_id=null，2026-08-21 调度中心裁定落点（低置信，待人审复核）
待归位 = [
    ('钟表的夹角问题', '100006003002', '讲21题型7'),            # 角度制及其计算
    ('角的个数探究', '100006003001', '讲21题型8'),              # 角的概念
    ('线段、射线条数的规律探究', '100006002002', '讲20题型8'),   # 射线的概念
    ('立体图形的分类', '100006001001', '讲19题型2'),            # 几何图形的认识
]
待归位NOTE = '低置信·调度中心裁定待人审'


def main():
    ap = argparse.ArgumentParser(description='铺 kp 题型层（第六层）')
    ap.add_argument('--db', required=True, help='目标库路径（沙盘或主位，必须显式给）')
    ap.add_argument('--map', default=str(DEFAULT_MAP), help='题型锚定映射.json 路径')
    ap.add_argument('--dry-run', action='store_true', help='只打清单不写库')
    args = ap.parse_args()
    if not os.path.exists(args.db):
        sys.exit(f'🔴 库不存在：{args.db}')

    raw = json.loads(Path(args.map).read_text(encoding='utf-8'), object_pairs_hook=OrderedDict)
    conn = sqlite3.connect(args.db)
    conn.execute('PRAGMA foreign_keys=ON')
    t0 = time.time()
    try:
        # 前置闸：CHECK 必须已扩 题型
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='kp'").fetchone()[0]
        if "'题型''" not in sql and "'题型'" not in sql:
            sys.exit('🔴 kp.level 的 CHECK 还没扩 「题型」——先跑 工具箱/库/apply_ddl_窗L题型层.py')

        kp = {r[0]: (r[1], r[2], r[3]) for r in conn.execute('SELECT id,name,level,status FROM kp')}
        n_kp0 = len(kp)
        n_qkp0 = conn.execute('SELECT COUNT(*) FROM question_kp').fetchone()[0]

        # ── 排计划（父叶 → [(题型名, 来源键)]，讲序稳定）────────────────
        plan = OrderedDict()
        stat = {'键总数': len(raw), '已锚定': 0, '与父同名跳过': 0, '叶内重名跳过': 0, '待归位': 0}
        skipped_same = []
        for key, v in raw.items():
            pid = v.get('kp_id')
            if not pid:
                continue
            stat['已锚定'] += 1
            if pid not in kp:
                sys.exit(f'🔴 映射件 {key} 锚到不存在的 kp {pid}——拒绝盲建')
            pname, plevel, pstatus = kp[pid]
            if plevel != '考点' or pstatus != '现行':
                sys.exit(f'🔴 映射件 {key} 锚到 {pid}（{pname}）level={plevel} status={pstatus}，不是现行考点叶')
            name = v['题型名']
            if name == pname:
                stat['与父同名跳过'] += 1
                skipped_same.append((key, pid, name))
                continue
            bucket = plan.setdefault(pid, [])
            if any(n == name for n, _ in bucket):
                stat['叶内重名跳过'] += 1
                continue
            bucket.append((name, key))
        for name, pid, key in 待归位:
            if pid not in kp:
                sys.exit(f'🔴 待归位 {name} 的落点 {pid} 不存在')
            bucket = plan.setdefault(pid, [])
            if any(n == name for n, _ in bucket):
                continue
            bucket.append((name, key + '·待归位'))
            stat['待归位'] += 1

        # ── 落库（幂等：按 parent_id+name 查在即跳）────────────────────
        made, skipped, per_leaf = 0, 0, []
        for pid, items in plan.items():
            used = [r[0] for r in conn.execute(
                'SELECT id FROM kp WHERE parent_id=? AND length(id)=length(?)+3', (pid, pid))]
            seq = max([int(s[-3:]) for s in used], default=0)
            names_here = []
            for name, key in items:
                hit = conn.execute('SELECT id FROM kp WHERE parent_id=? AND name=?', (pid, name)).fetchone()
                if hit:
                    skipped += 1
                    names_here.append(f'={hit[0]} {name}')
                    continue
                seq += 1
                nid = f'{pid}{seq:03d}'
                note = {'来源': '题型锚定映射.json', '键': key.replace('·待归位', ''), '窗': '窗L'}
                if key.endswith('·待归位'):
                    note['低置信'] = 待归位NOTE
                if not args.dry_run:
                    conn.execute(
                        'INSERT INTO kp(id,name,parent_id,level,ord,status,note) VALUES (?,?,?,?,?,?,?)',
                        (nid, name, pid, '题型', seq, '现行', json.dumps(note, ensure_ascii=False)))
                made += 1
                names_here.append(f'+{nid} {name}' + ('  ⚠️低置信' if '低置信' in note else ''))
            per_leaf.append((pid, kp[pid][0], names_here))

        if not args.dry_run:
            try:
                conn.execute(
                    'INSERT INTO skill_log(skill, action, args_digest, result, detail, duration_ms, created_at) '
                    'VALUES (?,?,?,?,?,?,?)',
                    ('KG维护', '铺题型枝', f'db={os.path.basename(args.db)} map={os.path.basename(args.map)}',
                     '成功', f'新建 {made} / 已在跳过 {skipped} / 覆盖父叶 {len(plan)}',
                     int((time.time() - t0) * 1000), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            except sqlite3.Error as e:
                print(f'⚠️ skill_log 落账失败（不挡主流程）：{e}')
            conn.commit()

        # ── 清单与守恒 ────────────────────────────────────────────────
        print(f'库：{args.db}{"（DRY-RUN 未写）" if args.dry_run else ""}')
        print(f'原料：{args.map}　{stat}')
        print(f'\n—— 每父叶下的题型（+新建 =已在）——')
        for pid, pname, names in per_leaf:
            print(f'{pid} {pname}（{len(names)}）：' + '；'.join(names))
        print(f'\n新建 {made} 个 / 已在跳过 {skipped} 个 / 覆盖父叶 {len(plan)} 片')
        if skipped_same:
            print(f'\n与父叶同名跳过 {len(skipped_same)} 条（冗余不建）：'
                  + '；'.join(f'{k}:{n}' for k, _p, n in skipped_same))
            # 🔴 如实报：这类叶若同时有别的题型子节点，该「同名题型」将无处可挂（新挂载必须落题型层）
            clash = [(p, n) for _k, p, n in skipped_same
                     if p in plan and len(plan[p]) > 0]
            if clash:
                print(f'⚠️ 低置信提醒：以下父叶既跳过了同名题型、又长了别的题型子节点，'
                      f'该同名题型今后没有专属挂载点（旧挂载仍合法，新题需人工择型）：{clash}')
        n_kp1 = conn.execute('SELECT COUNT(*) FROM kp').fetchone()[0]
        n_qkp1 = conn.execute('SELECT COUNT(*) FROM question_kp').fetchone()[0]
        print(f'\nkp 行数 {n_kp0} → {n_kp1}（+{n_kp1 - n_kp0}）；question_kp {n_qkp0} → {n_qkp1}（必须不变）')
        ok = (n_qkp1 == n_qkp0) and (args.dry_run or n_kp1 - n_kp0 == made)
        fk = conn.execute('PRAGMA foreign_key_check').fetchall()
        print(f'外键违例：{fk if fk else "0 条"}')
        print('=== ' + ('全绿' if ok and not fk else '🔴 守恒不过，人工裁决') + ' ===')
        sys.exit(0 if ok and not fk else 1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
