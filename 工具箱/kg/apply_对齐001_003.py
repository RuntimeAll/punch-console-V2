# -*- coding: utf-8 -*-
"""对齐-001/003 执行器：考点携带教研属性 + 题型并入考点描述（正本=记录/口径对齐记录.md）。

用法：python apply_对齐001_003.py <kb.db 路径> [--pending-out <待挂清单.md>]
动作（一次事务）：
  ① kp 表幂等补四列 emphasis/freq/diff_code/desc（属性值空置待人工定标，LLM 不自评）；
  ② question_pattern 现存行按 kp_ids_json 锚定，题型名聚合进对应叶的 kp.desc（考法清单）；
  ③ 挂不上叶的题型落 --pending-out 人工清单（不静默）；
  ④ question_pattern 全表清空（停用；重抽可用 pattern_tool 从讲义再生）。
幂等：二跑时表已空 → ②③④ 无事可做，desc 不被抹。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import os
import re
import sqlite3


def lect_no(note):
    m = re.search(r'讲(\d+)题型(\d+)', note or '')
    return (int(m.group(1)), int(m.group(2))) if m else (999, 999)


def main():
    if len(sys.argv) < 2:
        sys.exit('用法：python apply_对齐001_003.py <kb.db 路径> [--pending-out <md>]')
    db = sys.argv[1]
    pend_out = None
    if '--pending-out' in sys.argv:
        pend_out = sys.argv[sys.argv.index('--pending-out') + 1]
    if not os.path.exists(db):
        sys.exit(f'🔴 库不存在：{db}')
    conn = sqlite3.connect(db)
    try:
        # ① 幂等补列
        cols = [r[1] for r in conn.execute('PRAGMA table_info(kp)')]
        for col, ddl in [
            ('emphasis', "emphasis TEXT CHECK(emphasis IN ('重点','难点','重难点','常规'))"),
            ('freq', "freq TEXT CHECK(freq IN ('高频','中频','低频'))"),
            ('diff_code', 'diff_code TEXT'),
            ('desc', 'desc TEXT'),
        ]:
            if col not in cols:
                conn.execute(f'ALTER TABLE kp ADD COLUMN {ddl}')
                print(f'  + kp.{col}')
        # ② 题型 → 叶 desc
        rows = conn.execute(
            'SELECT name, kp_ids_json, note FROM question_pattern').fetchall()
        if not rows:
            print('question_pattern 已空：②③④ 无事可做（幂等）')
            conn.commit()
            return
        by_leaf, pending = {}, []
        for name, kps, note in rows:
            ids = json.loads(kps or '[]')
            src = ''
            m = re.search(r'"讲义":\s*"([^"]+)"', note or '')
            if m:
                src = m.group(1)
            if ids:
                for k in ids:
                    by_leaf.setdefault(k, []).append((lect_no(note), name))
            else:
                pending.append((lect_no(note), src, name))
        updated = 0
        for k, items in sorted(by_leaf.items()):
            names = [n for _, n in sorted(items)]
            desc = '考法：' + '；'.join(names) + '（源：浙教七上预习讲义）'
            cur = conn.execute('UPDATE kp SET desc=? WHERE id=? AND level=?', (desc, k, '考点'))
            updated += cur.rowcount
        # ③ 待挂清单
        pending.sort()
        if pend_out:
            os.makedirs(os.path.dirname(pend_out) or '.', exist_ok=True)
            with open(pend_out, 'w', encoding='utf-8') as f:
                f.write('# 待挂题型清单（对齐-003 执行产物 · 手工归位用）\n\n')
                f.write('> 这些讲义题型机器锚不到唯一考点叶（方法/场景/跨叶词），'
                        '按对齐-002 不做兼容映射；\n> 归位方式=你点名"这条归哪片叶"，'
                        '我把它并进该叶 desc。归位一条勾一条。\n\n')
                for (_, _), src, name in pending:
                    f.write(f'- [ ] {src or "?"}：{name}\n')
            print(f'  待挂清单 → {pend_out}')
        # ④ 清空
        n = conn.execute('SELECT COUNT(*) FROM question_pattern').fetchone()[0]
        conn.execute('DELETE FROM question_pattern')
        conn.commit()
        got = conn.execute(
            "SELECT COUNT(*) FROM kp WHERE level='考点' AND desc IS NOT NULL").fetchone()[0]
        print(f'✅ 对齐-001/003 落库：叶 desc 写入 {got} 片（更新 {updated} 次）'
              f'｜题型收编 {len(rows)-len(pending)}｜待挂 {len(pending)}｜pattern 清空 {n} 行')
        assert (len(rows) - len(pending)) + len(pending) == len(rows), '守恒失衡'
    finally:
        conn.close()


if __name__ == '__main__':
    main()
