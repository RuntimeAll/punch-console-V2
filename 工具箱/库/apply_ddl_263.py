# -*- coding: utf-8 -*-
"""发布运营域 DDL 执行器（数据结构 §2.6c · PRD-003 阶段0）。

用法：python apply_ddl_263.py <kb.db 路径>
幂等：CREATE 全带 IF NOT EXISTS；ALTER 先 pragma 探测列存在才补。
🔴 主位执行只允许显式点名路径，不做默认值——防止在 worktree 里误敲打到主位库。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import sqlite3

DDL = [
    """CREATE TABLE IF NOT EXISTS material (
      id             TEXT PRIMARY KEY,
      artifact_id    TEXT NOT NULL REFERENCES artifact(id),
      account        TEXT NOT NULL CHECK(account IN ('A','B')),
      is_active      INTEGER NOT NULL DEFAULT 1,
      title          TEXT NOT NULL,
      body           TEXT NOT NULL,
      topics_json    TEXT,
      style_seed     TEXT,
      burned         INTEGER NOT NULL DEFAULT 0,
      product_desc   TEXT,
      pan_share_text TEXT,
      created_at     TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_material_artifact ON material(artifact_id, account, is_active)",
    """CREATE TABLE IF NOT EXISTS publish_log (
      id           INTEGER PRIMARY KEY,
      material_id  TEXT NOT NULL REFERENCES material(id),
      published_on TEXT,
      result       TEXT,
      note         TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS ix_publish_log_material ON publish_log(material_id)",
    """CREATE TABLE IF NOT EXISTS artifact_member (
      parent_id TEXT NOT NULL REFERENCES artifact(id),
      member_id TEXT NOT NULL REFERENCES artifact(id),
      ord       INTEGER,
      PRIMARY KEY (parent_id, member_id)
    )""",
    """CREATE TABLE IF NOT EXISTS punch_map (
      kind      TEXT NOT NULL CHECK(kind IN ('doc','material','question','asset')),
      punch_id  TEXT NOT NULL,
      kb_id     TEXT NOT NULL,
      note      TEXT,
      created_at TEXT,
      PRIMARY KEY (kind, punch_id)
    )""",
]


def main():
    if len(sys.argv) != 2:
        sys.exit('用法：python apply_ddl_263.py <kb.db 路径>（必须显式点名，无默认）')
    db = sys.argv[1]
    if not os.path.exists(db):
        sys.exit(f'🔴 库不存在：{db}')
    conn = sqlite3.connect(db)
    try:
        for stmt in DDL:
            conn.execute(stmt)
        cols = [r[1] for r in conn.execute('PRAGMA table_info(artifact)')]
        if 'sale_state' not in cols:
            conn.execute("ALTER TABLE artifact ADD COLUMN sale_state TEXT "
                         "CHECK(sale_state IN ('在售','待整理','停售'))")
            print('  + artifact.sale_state 已补列')
        else:
            print('  = artifact.sale_state 已存在，跳过')
        conn.commit()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('material','publish_log','artifact_member','punch_map') ORDER BY name")]
        print(f'✅ §2.6c DDL 落库 {db}：{tables}')
        if len(tables) != 4:
            sys.exit('🔴 表数不对，检查！')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
