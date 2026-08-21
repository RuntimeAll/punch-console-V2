# -*- coding: utf-8 -*-
"""pattern_tool —— 🔴🔴【已停用·勿跑】题型簇抽取入库（question_pattern 唯一写入通路）。

停用裁决（2026-08-19 对齐-003，正本=记录/口径对齐记录.md）：不设与考点**平行**的题型实体层；
question_pattern 表停用（173 行已清空）。🔴 跑它=往停用表写数据（违例）。
🔴 2026-08-21 窗L 后续（数据结构 §2.2b）：题型改用 **kp 树的第六层**表达（考点之下、非平行表）——
本脚本的锚定产物 题型锚定映射.json 已被 工具箱/kg/铺题型枝.py 消费成 95 个题型节点；
抽取逻辑（正则锚点+叶锚定三级回退）仍是资产，后续讲义再抽题型走「补映射件→铺题型枝」通路，
不再直写任何表。改造前本文件只读不执行。

--- 以下为停用前原文档 ---
2026-08-19 用户拍板：题型与考点平行、成簇状、携教研属性（emphasis/freq/diff_code 空置待人工定标）。
用法：
    python pattern_tool.py build --pdf <讲义.pdf> --db <kb.db> [--apply]
零 LLM：正则锚点（第N讲 / 知识点N： / 题型N：）+ 叶锚定三级回退：
  ①叶 note.讲义 == "讲L知N"（新铺四单元带锚） ②知识点标题 kp.name/kp_alias 精确单命中（讲1~8走别名）
  ③该讲唯一叶（如讲18单叶承接） —— 全不中 = kp_ids '[]' 待挂，落人审段不静默。
幂等：id = QP+sha1(讲L题型N|名)前8，INSERT OR IGNORE；重跑零新增。
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')   # 停用闸走 stderr，GBK 控制台会把中文压成转义
import argparse
import hashlib
import json
import re
import sqlite3
import time

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def cn2int(s):
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s in CN:
        return CN[s]
    if s.startswith('十'):                       # 十一 ~ 十九
        return 10 + (CN.get(s[1:], 0) if len(s) > 1 else 0)
    if s.endswith('十'):                         # 二十
        return CN[s[0]] * 10
    if '十' in s:                                # 二十一
        a, b = s.split('十')
        return CN[a] * 10 + CN[b]
    raise ValueError(f'讲号解析不了：{s!r}')


def extract(pdf_path):
    """扫全册：返回 [(讲号int, 题型号int, 题型名, 知识点号int|None)]，守恒=正文题型标题全收。"""
    import fitz
    rows, lect, kpn = [], None, None
    doc = fitz.open(pdf_path)
    for i, pg in enumerate(doc):
        if i < 2:                                # 目录两页跳过（目录里的题型行无正文语境）
            continue
        for line in pg.get_text().splitlines():
            line = line.strip()
            m = re.match(r'^第(.{1,3}?)讲', line)
            if m:
                try:
                    lect, kpn = cn2int(m.group(1)), None
                except ValueError:
                    pass
                continue
            m = re.match(r'^知识点\s*(\d+)\s*[:：]', line)
            if m:
                kpn = int(m.group(1))
                continue
            m = re.match(r'^题型\s*(\d+)\s*[:：]\s*(.+)$', line)
            if m and lect is not None:
                rows.append((lect, int(m.group(1)), m.group(2).strip(), kpn))
    doc.close()
    # 同讲同号去重（跨页重复标题）
    seen, out = set(), []
    for r in rows:
        if r[:2] not in seen:
            seen.add(r[:2])
            out.append(r)
    return out


def anchor_leaf(conn, lect, kpn, cache):
    """三级回退定挂靠叶；返回 (kp_id|None, 方式)。"""
    key = (lect, kpn)
    if key in cache:
        return cache[key]
    res = (None, '待挂')
    if kpn is not None:
        tag = f'讲{lect}知{kpn}'
        hit = conn.execute("SELECT id FROM kp WHERE level='考点' AND status='现行' "
                           "AND note LIKE ?", (f'%"讲义": "{tag}%',)).fetchall()
        if len(hit) == 1:
            res = (hit[0][0], 'note锚')
    if res[0] is None:
        # 该讲唯一叶（note.讲义 以 讲L知 开头的叶恰一片）
        hits = conn.execute("SELECT id FROM kp WHERE level='考点' AND status='现行' "
                            "AND note LIKE ?", (f'%"讲义": "讲{lect}知%',)).fetchall()
        if len(hits) == 1:
            res = (hits[0][0], '讲级唯一叶')
    cache[key] = res
    return res


def main():
    raise SystemExit(
        '🔴 pattern_tool 已停用（2026-08-19 对齐-003）：不设题型簇实体层，讲义题型归 kp.desc。\n'
        '   要复用抽取逻辑请改造为「考点描述补齐工具」（写入目标 kp.desc，走 kg_tool 通路），\n'
        '   改造时删除本闸并在 记录/口径对齐记录.md 勾销对应执行项。')


def _main_停用前原文():
    ap = argparse.ArgumentParser(description='题型簇抽取入库（question_pattern 唯一写入通路）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--pdf', required=True)
    b.add_argument('--db', required=True, help='kb.db 路径（显式点名，无默认）')
    b.add_argument('--apply', action='store_true', help='真写库（缺省 dry-run）')
    args = ap.parse_args()

    rows = extract(args.pdf)
    conn = sqlite3.connect(args.db)
    cache, plan, pend = {}, [], []
    # 讲1~8 的知识点标题→别名精确命中，需要标题文本：二次扫描拿知识点标题
    import fitz
    titles = {}
    doc = fitz.open(args.pdf)
    lect = None
    for i, pg in enumerate(doc):
        if i < 2:
            continue
        for line in pg.get_text().splitlines():
            line = line.strip()
            m = re.match(r'^第(.{1,3}?)讲', line)
            if m:
                try:
                    lect = cn2int(m.group(1))
                except ValueError:
                    pass
            m = re.match(r'^知识点\s*(\d+)\s*[:：]\s*(.+)$', line)
            if m and lect is not None:
                titles.setdefault((lect, int(m.group(1))), m.group(2).strip())
    doc.close()

    def alias_hit(title):
        h = conn.execute("SELECT id FROM kp WHERE level='考点' AND status='现行' AND name=?",
                         (title,)).fetchall()
        if len(h) != 1:
            h = conn.execute(
                "SELECT DISTINCT a.kp_id FROM kp_alias a JOIN kp k ON k.id=a.kp_id "
                "WHERE a.alias=? AND k.level='考点' AND k.status='现行'", (title,)).fetchall()
        return h[0][0] if len(h) == 1 else None

    for lect, n, name, kpn in rows:
        kp_id, how = anchor_leaf(conn, lect, kpn, cache)
        if kp_id is None and kpn is not None and (lect, kpn) in titles:
            a = alias_hit(titles[(lect, kpn)])
            if a:
                kp_id, how = a, '知识点名/别名'
        pid = 'QP' + hashlib.sha1(f'讲{lect}题型{n}|{name}'.encode()).hexdigest()[:8]
        note = {'讲义': f'讲{lect}题型{n}'}
        if kp_id is None:
            note['待挂'] = f'知识点定位失败（知识点{kpn}）'
            pend.append((lect, n, name))
        plan.append((pid, name, json.dumps([kp_id] if kp_id else [], ensure_ascii=False),
                     json.dumps(note, ensure_ascii=False), how))

    hows = {}
    for *_, how in plan:
        hows[how] = hows.get(how, 0) + 1
    print(f'抽取 {len(rows)} 个题型｜锚定方式分布 {hows}')
    assert len(plan) == len(rows), '守恒失衡'
    if not args.apply:
        print('dry-run：零写库（--apply 真吃）')
        for l, n, name in pend[:10]:
            print(f'  待挂样例：讲{l}题型{n} {name}')
        return
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    ins = 0
    for pid, name, kps, note, _ in plan:
        cur = conn.execute(
            "INSERT OR IGNORE INTO question_pattern(id,name,kp_ids_json,status,note,created_at) "
            "VALUES(?,?,?,'在用',?,?)", (pid, name, kps, note, now))
        ins += cur.rowcount
    conn.commit()
    total = conn.execute('SELECT COUNT(*) FROM question_pattern').fetchone()[0]
    print(f'--apply：新增 {ins}｜跳过 {len(plan)-ins}｜表内共 {total}｜待挂 {len(pend)}（人审段见 note.待挂）')
    conn.close()


if __name__ == '__main__':
    main()
