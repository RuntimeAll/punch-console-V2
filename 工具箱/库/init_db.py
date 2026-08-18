# -*- coding: utf-8 -*-
"""建库脚本：创建 知识库/kb.db 与 批改产线/grading.db，并 seed dict_item。

用法（在 v2 根或任意目录跑均可，路径按脚本位置自解析）：
    python 工具箱\\库\\init_db.py            # 正常路径：不存在才建；已存在且空则补齐结构+seed
    python 工具箱\\库\\init_db.py --check    # 只体检不动库
    python 工具箱\\库\\init_db.py --only kb  # 只处理一个库（kb / grading）
    python 工具箱\\库\\init_db.py --force    # 🔴 允许重建有数据的库（先备份再重建）

🔴 空库保护（老区「收敛 DDL 清空 prod」血案的落点）：
    目标库已存在且**任一表有数据** ⇒ 直接拒绝执行并列出各表行数，必须显式 --force 才继续；
    --force 也不裸删：先把原库改名成 <库名>.bak-<时间戳> 留证，再重建。
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]          # …/ai-bkb-v2
SQL_DIR = Path(__file__).resolve().parent           # …/工具箱/库

DBS = {
    'kb':      {'schema': SQL_DIR / 'schema_kb.sql',      'path': ROOT / '知识库' / 'kb.db'},
    'grading': {'schema': SQL_DIR / 'schema_grading.sql', 'path': ROOT / '批改产线' / 'grading.db'},
}

# ── dict_item seed ────────────────────────────────────────────────────
# 域 qtype：🔴 照抄老区现行字典 biz_question_type（考古/题目结构考古-DB层.md §4.1 的 9 值），
#           不照主表注释（老区注释与字典互相矛盾，填空/判断码是反的，这个漂移真的伤过人）。
#           code 用 q1..q9 保住老区数字码的对应关系，同时保证跨域不撞码。
QTYPE = [
    ('q1', '选择题',   1), ('q2', '判断题',     2), ('q3', '应用题', 3),
    ('q4', '填空题',   4), ('q5', '解答题',     5), ('q6', '作图题', 6),
    ('q7', '计算题',   7), ('q8', '证明题',     8), ('q9', '实验探究题', 9),
]
# 域 difficulty：v2 四档口径（送分/巩固/中档/压轴）——与老区字典标签（基础/中等/较难/压轴）不同，
#           以 v2 口径为准（难度=模型表驱动 rubric 的四档）。
DIFFICULTY = [
    ('d1', '送分', 1), ('d2', '巩固', 2), ('d3', '中档', 3), ('d4', '压轴', 4),
]
# 域 source：值域 = question.source_kind 的 CHECK（数据结构 §2.1①，D-9 题源类 vs 生成类）
SOURCE = [
    ('scan', '扫描/拍照录入', 1), ('manual', '人工录入', 2),
    ('model', '模型生成', 3), ('pipeline', '管线生成', 4),
]
SEED = {'qtype': QTYPE, 'difficulty': DIFFICULTY, 'source': SOURCE}


def table_names(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def row_counts(conn):
    return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in table_names(conn)}


def apply_schema(db_path: Path, schema: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema.read_text(encoding='utf-8'))
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        conn.commit()
    finally:
        conn.close()


def seed_dict(db_path: Path):
    """只对 kb.db 有效；幂等（INSERT OR IGNORE），重跑不翻倍。"""
    conn = sqlite3.connect(str(db_path))
    try:
        before = conn.execute('SELECT COUNT(*) FROM dict_item').fetchone()[0]
        for domain, rows in SEED.items():
            conn.executemany(
                'INSERT OR IGNORE INTO dict_item(domain, code, label, ord, status) VALUES (?,?,?,?,?)',
                [(domain, c, lab, o, '在用') for c, lab, o in rows])
        conn.commit()
        after = conn.execute('SELECT COUNT(*) FROM dict_item').fetchone()[0]
        per = dict(conn.execute('SELECT domain, COUNT(*) FROM dict_item GROUP BY domain').fetchall())
        return before, after, per
    finally:
        conn.close()


def handle(key: str, force: bool, check_only: bool) -> bool:
    spec = DBS[key]
    db_path, schema = spec['path'], spec['schema']
    rel = db_path.relative_to(ROOT)
    print(f'\n=== {key} · {rel} ===')

    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            counts = row_counts(conn)
        finally:
            conn.close()
        nonempty = {t: n for t, n in counts.items() if n > 0}
        print(f'已存在：{len(counts)} 表，有数据的表 {len(nonempty)} 张')
        for t, n in sorted(nonempty.items(), key=lambda x: -x[1]):
            print(f'    {t:<18} {n} 行')
        if nonempty and not force:
            print('🔴 拒绝执行：该库已有数据。重建会毁数据——确认要重建请显式加 --force（会先备份再重建）。')
            return False
        if check_only:
            print('（--check：只体检，未动库）')
            return True
        if nonempty and force:
            bak = db_path.with_name(db_path.name + '.bak-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
            db_path.rename(bak)
            print(f'⚠️ --force：原库已备份为 {bak.name}，现重建空库')
        else:
            print('库存在但全表为空 → 按 IF NOT EXISTS 补齐结构')
    else:
        if check_only:
            print('不存在（--check：未创建）')
            return True
        print('不存在 → 新建')

    apply_schema(db_path, schema)
    conn = sqlite3.connect(str(db_path))
    try:
        tabs = table_names(conn)
    finally:
        conn.close()
    print(f'结构就绪：{len(tabs)} 表')
    print('    ' + ' '.join(tabs))

    if key == 'kb':
        before, after, per = seed_dict(db_path)
        print(f'dict_item seed：{before} → {after} 行（新增 {after - before}）')
        for d, n in sorted(per.items()):
            print(f'    domain={d:<11} {n} 条')
    return True


def main():
    ap = argparse.ArgumentParser(description='v2 两库建库脚本（带空库保护）')
    ap.add_argument('--only', choices=list(DBS), help='只处理一个库')
    ap.add_argument('--force', action='store_true', help='🔴 允许重建有数据的库（先备份）')
    ap.add_argument('--check', action='store_true', help='只体检不动库')
    args = ap.parse_args()

    keys = [args.only] if args.only else list(DBS)
    ok = all(handle(k, args.force, args.check) for k in keys)
    print('\n' + ('全部完成' if ok else '🔴 有库被空库保护拦下，未做任何修改'))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
