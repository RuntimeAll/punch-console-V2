# -*- coding: utf-8 -*-
"""窗L 题型层 DDL 执行器（2026-08-21 · KG加层策略 段0）。

干两件事：
  ① kp.level 的 CHECK 扩 '题型'——SQLite 改 CHECK 只能**重建表**
     （新表建→数据搬→旧表删→改名→索引重建→外键验证，照 SQLite 官方 7. Other Schema Changes 流程）；
  ② question_kp(kp_id) 索引巡查：已有就跳过，没有才建（题型层落地后按 kp 反查题的路径会变热）。

用法（🔴 必须显式点名库，无默认值——防 worktree 里误敲主位库）：
    python 工具箱\\库\\apply_ddl_窗L题型层.py --db 试验场\\2026-08-21-七上发布闭环\\窗L沙盘.db
    python 工具箱\\库\\apply_ddl_窗L题型层.py --db 知识库\\kb.db          # 主位（调度中心执行）

幂等：CHECK 里已有 '题型' → 只报「已扩，跳过」不重建；索引 CREATE IF NOT EXISTS。
守恒（不过就红停、事务回滚）：kp 行数不变 + 逐行内容哈希不变 + question_kp 行数不变 +
  PRAGMA foreign_key_check 零违例 + integrity_check ok + 新 CHECK 收 '题型' 拒垃圾值。
🔴 新表 DDL 不手抄：取库内现行 kp 建表语句做**单点文本替换**（只换 level 的 CHECK 括号内容），
   列的顺序/类型/其余 CHECK/UNIQUE 一字不动——手抄漏列是老区级事故。
"""
import argparse
import hashlib
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

OLD_CHECK = "CHECK(level IN ('版本','年级学期','单元','小节','考点'))"
NEW_CHECK = "CHECK(level IN ('版本','年级学期','单元','小节','考点','题型'))"
TMP_TABLE = 'kp_窗L_new'


def rows_hash(conn, table):
    """逐行内容哈希（列顺序照库内定义，全列进 hash）——搬表守恒的唯一证据。"""
    cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]
    # 🔴 列名可能撞 SQL 关键字（kp.desc 就是），一律双引号包；NULL 与空串必须区分开
    sel = " || '␟' || ".join(f"""IFNULL(CAST("{c}" AS TEXT), '␀')""" for c in cols)
    h = hashlib.sha256()
    for (line,) in conn.execute(f'SELECT {sel} FROM {table} ORDER BY id'):
        h.update((line + '\n').encode('utf-8'))
    return cols, h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='窗L 题型层 DDL（kp.level CHECK 扩 题型 + question_kp 索引）')
    ap.add_argument('--db', required=True, help='目标库路径（沙盘或主位，必须显式给）')
    args = ap.parse_args()
    if not os.path.exists(args.db):
        sys.exit(f'🔴 库不存在：{args.db}')

    conn = sqlite3.connect(args.db)
    conn.isolation_level = None            # 手动管事务（PRAGMA foreign_keys 在事务内无效）
    fails = []

    def chk(name, got, want):
        ok = got == want
        print(f'[{"PASS" if ok else "FAIL"}] {name}: 实际={got} 期望={want}')
        if not ok:
            fails.append(name)

    try:
        # ── 执行前断言 ────────────────────────────────────────────────
        n_kp = conn.execute('SELECT COUNT(*) FROM kp').fetchone()[0]
        n_qkp = conn.execute('SELECT COUNT(*) FROM question_kp').fetchone()[0]
        n_alias = conn.execute('SELECT COUNT(*) FROM kp_alias').fetchone()[0]
        cols, h0 = rows_hash(conn, 'kp')
        print(f'库：{args.db}')
        print(f'执行前：kp {n_kp} 行 / question_kp {n_qkp} 行 / kp_alias {n_alias} 行')
        print(f'        kp 列={cols}\n        kp 行哈希={h0}')
        if n_kp == 0:
            sys.exit('🔴 kp 表空——不像是真库，红停')

        cur_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='kp'").fetchone()[0]

        # ── ① CHECK 扩 '题型' ─────────────────────────────────────────
        if "'题型'" in cur_sql:
            print("\n= kp.level CHECK 已含 '题型'，跳过重建（幂等）")
        else:
            norm = ' '.join(cur_sql.split())
            if ' '.join(OLD_CHECK.split()) not in norm:
                sys.exit(f'🔴 库内 kp 的 level CHECK 与预期不符，拒绝盲改：\n{cur_sql}')
            new_sql = cur_sql.replace(OLD_CHECK, NEW_CHECK)
            if new_sql == cur_sql:                     # 空白差异 → 退回正则式替换
                sys.exit('🔴 CHECK 文本替换未命中（空白差异），人工裁决')
            head = new_sql[:new_sql.index('(')]
            if 'kp' not in head:
                sys.exit(f'🔴 建表语句头部异常：{head!r}')
            new_sql = new_sql.replace(head, f'CREATE TABLE {TMP_TABLE} ', 1)
            print(f'\n新表 DDL：\n{new_sql}\n')

            keep = conn.execute(
                "SELECT type, name, sql FROM sqlite_master WHERE tbl_name='kp' "
                "AND sql IS NOT NULL AND type IN ('index','trigger')").fetchall()
            print(f'需重建的索引/触发器 {len(keep)} 个：{[k[1] for k in keep]}')
            views = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' AND sql LIKE '%kp%'")]
            if views:
                print(f'⚠️ 检测到可能引用 kp 的视图：{views}（重建后请目检）')

            conn.execute('PRAGMA foreign_keys=OFF')
            conn.execute('BEGIN')
            try:
                conn.execute(new_sql)
                collist = ','.join(f'"{c}"' for c in cols)
                conn.execute(f'INSERT INTO {TMP_TABLE}({collist}) SELECT {collist} FROM kp')
                conn.execute('DROP TABLE kp')
                conn.execute(f'ALTER TABLE {TMP_TABLE} RENAME TO kp')
                for _t, _n, sql in keep:
                    conn.execute(sql)
                conn.execute('COMMIT')
            except Exception:
                conn.execute('ROLLBACK')
                raise
            finally:
                conn.execute('PRAGMA foreign_keys=ON')
            print('✅ kp 表重建完成（CHECK 已扩 题型）')

        # ── ② question_kp(kp_id) 索引 ────────────────────────────────
        idx = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='question_kp' "
            "AND sql IS NOT NULL").fetchall()
        has_kp_idx = any(i[1] and 'kp_id' in i[1].split('(')[-1] for i in idx)
        if has_kp_idx:
            print(f'\n= question_kp(kp_id) 索引已有，跳过：'
                  f'{[i[0] for i in idx if i[1] and "kp_id" in i[1].split("(")[-1]]}')
        else:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_question_kp_kp ON question_kp(kp_id)')
            print('\n+ 已建 idx_question_kp_kp ON question_kp(kp_id)')

        # ── 执行后守恒对账 ────────────────────────────────────────────
        print('\n—— 守恒对账 ——')
        chk('kp 行数不变', conn.execute('SELECT COUNT(*) FROM kp').fetchone()[0], n_kp)
        chk('question_kp 行数不变', conn.execute('SELECT COUNT(*) FROM question_kp').fetchone()[0], n_qkp)
        chk('kp_alias 行数不变', conn.execute('SELECT COUNT(*) FROM kp_alias').fetchone()[0], n_alias)
        cols2, h1 = rows_hash(conn, 'kp')
        chk('kp 列定义不变', cols2, cols)
        chk('kp 逐行内容哈希不变', h1, h0)
        chk('外键 foreign_key_check 零违例', conn.execute('PRAGMA foreign_key_check').fetchall(), [])
        chk('integrity_check', conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        idxnames = sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='kp' AND sql IS NOT NULL"))
        chk('kp 索引齐全', idxnames, ['ix_kp_parent', 'ux_kp_root_name'])

        # CHECK 真收 '题型' / 真拒垃圾（写一笔立刻回滚，不留痕）
        conn.execute('BEGIN')
        try:
            root = conn.execute("SELECT id FROM kp WHERE level='考点' LIMIT 1").fetchone()[0]
            conn.execute("INSERT INTO kp(id,name,parent_id,level,ord,status) VALUES (?,?,?,?,?,?)",
                         ('__probe__', '闸探针题型', root, '题型', 999, '现行'))
            chk("CHECK 收 level='题型'", True, True)
            try:
                conn.execute("INSERT INTO kp(id,name,parent_id,level,ord,status) VALUES (?,?,?,?,?,?)",
                             ('__probe2__', '闸探针垃圾', root, '题目型', 999, '现行'))
                chk("CHECK 拒 level='题目型'", '竟然放行', '拒收')
            except sqlite3.IntegrityError:
                chk("CHECK 拒 level='题目型'", '拒收', '拒收')
        finally:
            conn.execute('ROLLBACK')
        chk('探针已回滚（kp 行数复原）', conn.execute('SELECT COUNT(*) FROM kp').fetchone()[0], n_kp)

        print('\n=== ' + ('全绿，DDL 落库完成' if not fails else f'🔴 {len(fails)} 条 FAIL：{fails}') + ' ===')
        sys.exit(1 if fails else 0)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
