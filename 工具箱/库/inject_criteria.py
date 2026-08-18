# -*- coding: utf-8 -*-
"""判据按线注入器（横切机制：agent 开工按线全量注入 criterion 现行判据）。

用法：
  python 工具箱/库/inject_criteria.py 出题        # 出题线现行判据全量
  python 工具箱/库/inject_criteria.py 渲染 录入   # 可多线
线 ∈ 录入/批改/出题/渲染。废止判据不注入（superseded_by 链留档在库）。
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / '知识库' / 'kb.db'

LINES = ('录入', '批改', '出题', '渲染')


def main():
    lines = [x for x in sys.argv[1:] if x in LINES]
    if not lines:
        sys.exit(f'用法：python inject_criteria.py <线…>　线∈{LINES}')
    conn = sqlite3.connect(str(DB))
    for line in lines:
        rows = conn.execute(
            "SELECT id, scene, rule, why FROM criterion WHERE line=? AND status='现行' ORDER BY id",
            (line,)).fetchall()
        print(f'══ {line} 线现行判据 {len(rows)} 条 ══')
        for cid, scene, rule, why in rows:
            w = f'（why: {why}）' if why else ''
            print(f'· [{cid}] {scene} → {rule}{w}')
    conn.close()


if __name__ == '__main__':
    main()
