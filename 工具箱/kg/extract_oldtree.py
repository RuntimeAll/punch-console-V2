# -*- coding: utf-8 -*-
"""老区 biz_subject dump → 树 JSON 抽取器（只读老区文件，产出落 v2）。

用途：KG 建树「沿用老区 id 契约」的数据源——从 SQL dump 抽某棵册根树，
供人工整理成 branch spec（新名字 + ord + 别名）后交给 kg_tool.py build-branch。

用法：
  python extract_oldtree.py <dump.sql> <根前缀 如 100> <输出.json>

dump 来源（老区只读）：
  D:\\workplace\\ai-bkb\\数据库清理-2026-08\\备份\\dev\\_bak206_biz_subject.sql（2026-08-05 快照）
🔴 注意：dump 里的 DDL 注释「1学科 2教材 3章 4节 5知识点」是老区过期注释，
   实际层义=1册根 2章 3节 4知识点 5细分点（考古正本：认知/考古/KG命名体例-老区实况.md §1.0）。
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# INSERT 行里的一条记录：('100', NULL, '数学七年级上(浙教2024)', 1, 0, '0', ...)
# 只取前 6 个字段：id, parent_id, name, level, sort, status
ROW_RE = re.compile(
    r"\(\s*'(?P<id>\d+)'\s*,\s*"
    r"(?:'(?P<pid>\d+)'|NULL)\s*,\s*"
    r"'(?P<name>(?:[^'\\]|\\.|'')*)'\s*,\s*"
    r"(?P<level>\d+)\s*,\s*"
    r"(?P<sort>-?\d+)\s*,\s*"
    r"'(?P<status>[^']*)'"
)


def unescape(s):
    return s.replace("\\'", "'").replace("''", "'").replace('\\\\', '\\').replace('\\n', '\n')


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    dump_path, prefix, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    text = open(dump_path, encoding='utf-8', errors='replace').read()

    nodes = []
    for m in ROW_RE.finditer(text):
        nid = m.group('id')
        if not nid.startswith(prefix):
            continue
        nodes.append({
            'id': nid,
            'parent_id': m.group('pid'),
            'name': unescape(m.group('name')),
            'level': int(m.group('level')),
            'sort': int(m.group('sort')),
            'status': m.group('status'),
        })

    nodes.sort(key=lambda n: n['id'])
    # 自检：每 3 位一层（level == len(id)/3）——对不上的如实列出，不静默
    bad = [n for n in nodes if len(n['id']) != n['level'] * 3]
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'source': dump_path, 'prefix': prefix,
                   'count': len(nodes), 'level_mismatch': bad, 'nodes': nodes},
                  f, ensure_ascii=False, indent=1)
    print(f'抽出 {len(nodes)} 节点 → {out_path}')
    if bad:
        print(f'⚠️ {len(bad)} 个节点 id 长度与 level 不符（如实列在 level_mismatch）')
    for n in nodes:
        if n['level'] <= 3:
            print(' ' * (n['level'] - 1) * 2 + f"{n['id']} {n['name']}")


if __name__ == '__main__':
    main()
