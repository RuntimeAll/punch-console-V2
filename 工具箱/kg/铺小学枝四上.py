# -*- coding: utf-8 -*-
"""窗N · 小学枝四上 KG 铺枝（源=老区四上讲义解析账，只录图谱不录题）
==============================================================================
源正本：D:\\workplace\\ai-bkb\\录书工作区\\小学数学管线\\_work_4s\\_locator_nodes.json
（老区 A 线 R1~R9 修完的四上讲义节点账：12 册 139 考点节——探路报告实证词表命中 97.8%，
不重切 docx，直接搬结构。老区**只读**。）

口径（2026-08-21 用户令「先录入」）：
  - 🔴 小学不分教材版本 → 版本壳=「小学数学」(id=xxsx)，不立人教版；
  - 目录壳跟讲义走：单元=讲义册（含·篇），考点直挂单元——小学枝**无小节层**
    （六层链里小节/题型皆可选长，正本口径同步 数据结构 §2.2b）；
  - 剔杂：「两位数乘两位数·计算篇/应用篇」两册 27 考点=苏教版三下混入（探路报告 §3 实锤），
    不建；「课后小测」×2 不是考点（探路报告 Q2 口径），不建节点；
  - 准入闸（PRD-009 考点向量建叶）未建 → 先铺后巡检，本批全量 note 带源可追溯。

id 规则（过渡编号，PRD-009 三原语后新节点改无位置 id）：
  版本 xxsx → 年级学期 400 → 单元 400001.. → 考点 = 单元id+3位。

用法：
  python 工具箱/kg/铺小学枝四上.py --plan            # 只打铺枝计划，不碰库
  python 工具箱/kg/铺小学枝四上.py --apply --db <路径>  # 执行（幂等：同名节点跳过）
守恒：只 INSERT kp/kp_alias；question/question_kp 零触碰；存量 kp 行前后逐行哈希一致。
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

SRC = Path(r'D:\workplace\ai-bkb\录书工作区\小学数学管线\_work_4s\_locator_nodes.json')
ROOT_ID, ROOT_NAME = 'xxsx', '小学数学'
TERM_ID, TERM_NAME = '400', '四年级上册'
NOTE = '窗N·四上讲义铺枝(源=_work_4s节点账) 2026-08-21'

RE_UNIT_PREFIX = re.compile(r'^第[一二三四五六七八九十\d]+单元\s*')
RE_KP_PREFIX = re.compile(r'^【考点[^】]*】\s*')
RE_IMG_MARK = re.compile(r'〖[^〗]*〗')
# 源账里的实名缺陷改判（低置信，note 留痕人审）
RENAME = {'统计图表综合应': ('统计图表综合应用', '🔴低置信改名:原账名「统计图表综合应」疑截断')}


def clean_kp(raw):
    s = RE_KP_PREFIX.sub('', raw)
    s = RE_IMG_MARK.sub('', s)
    s = re.sub(r'\s*——\s*', '——', s)
    s = s.strip().rstrip('。．.').strip()
    note = NOTE
    if s in RENAME:
        s, flag = RENAME[s]
        note = flag + '｜' + NOTE
    return s, note


def build_plan():
    nodes = json.loads(SRC.read_text(encoding='utf-8'))
    units = [n for n in nodes if n['node_type'] == 'unit']
    kids = {}
    for n in nodes:
        if n['node_type'] == 'kp':
            kids.setdefault(n['parent_id'], []).append(n)

    plan, dropped = [], {'苏教册': [], '课后小测': 0, '同名撞': []}
    ord_u = 0
    for u in units:
        uname = RE_UNIT_PREFIX.sub('', u['name']).strip().replace(' ', '·')
        if uname.startswith('两位数乘两位数'):
            dropped['苏教册'].append((uname, len(kids.get(u['id'], []))))
            continue
        ord_u += 1
        uid = f'{TERM_ID}{ord_u:03d}'
        plan.append({'id': uid, 'name': uname, 'parent': TERM_ID,
                     'level': '单元', 'ord': ord_u, 'note': NOTE, 'alias': None})
        seen, ord_k = set(), 0
        for k in kids.get(u['id'], []):
            kname, knote = clean_kp(k['name'])
            if kname == '课后小测':
                dropped['课后小测'] += 1
                continue
            if kname in seen:
                dropped['同名撞'].append((uname, kname))
                continue
            seen.add(kname)
            ord_k += 1
            alias = None
            if kname in {v[0] for v in RENAME.values()}:
                alias = RE_IMG_MARK.sub('', RE_KP_PREFIX.sub('', k['name'])).strip()
            plan.append({'id': f'{uid}{ord_k:03d}', 'name': kname, 'parent': uid,
                         'level': '考点', 'ord': ord_k, 'note': knote, 'alias': alias})
    return plan, dropped


def snapshot(conn):
    counts = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
              for t in ('kp', 'kp_alias', 'question', 'question_kp')}
    h = hashlib.sha256()
    for row in conn.execute(
            'SELECT id,name,parent_id,level,ord,status FROM kp ORDER BY id'):
        h.update(repr(tuple(row)).encode('utf-8'))
    return counts, h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='小学枝四上 KG 铺枝（窗N）')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--db')
    a = ap.parse_args()

    plan, dropped = build_plan()
    n_unit = sum(1 for p in plan if p['level'] == '单元')
    n_kp = sum(1 for p in plan if p['level'] == '考点')
    print(f'铺枝计划：版本1 + 年级学期1 + 单元{n_unit} + 考点{n_kp} = {2 + len(plan)} 节点')
    print(f"剔除：苏教册 {[(n, c) for n, c in dropped['苏教册']]}"
          f"｜课后小测 {dropped['课后小测']}｜同名撞 {dropped['同名撞']}")

    if a.plan or not a.apply:
        cur = None
        for p in plan:
            if p['level'] == '单元':
                cur = p
                print(f"\n[{p['id']}] {p['name']}")
            else:
                mark = ' 🔴' + p['note'].split('｜')[0] if p['note'] != NOTE else ''
                print(f"   {p['id']} {p['name']}{mark}")
        return

    assert a.db, '--apply 必须显式给 --db'
    conn = sqlite3.connect(a.db)
    try:
        pre_counts, pre_hash = snapshot(conn)
        pre_ids = {r[0] for r in conn.execute('SELECT id FROM kp')}
        for pid in (ROOT_ID, TERM_ID):
            assert pid in pre_ids or conn.execute(
                'SELECT 1 FROM kp WHERE id=?', (pid,)).fetchone() is None, \
                f'id 撞车：{pid} 已存在但非本枝'

        ins_kp = ins_alias = skip = 0
        inserted_ids = set()
        with conn:
            for pid, name, parent, level, order, note in (
                    (ROOT_ID, ROOT_NAME, None, '版本', 2,
                     '小学不分教材版本（2026-08-21 用户口径）｜' + NOTE),
                    (TERM_ID, TERM_NAME, ROOT_ID, '年级学期', 1, NOTE)):
                row = conn.execute('SELECT id FROM kp WHERE parent_id IS ? AND name=?',
                                   (parent, name)).fetchone()
                if row:
                    skip += 1
                    continue
                conn.execute('INSERT INTO kp(id,name,parent_id,level,ord,status,note) '
                             "VALUES(?,?,?,?,?,'现行',?)",
                             (pid, name, parent, level, order, note))
                ins_kp += 1
                inserted_ids.add(pid)
            for p in plan:
                row = conn.execute('SELECT id FROM kp WHERE parent_id=? AND name=?',
                                   (p['parent'], p['name'])).fetchone()
                if row:
                    skip += 1
                    kp_id = row[0]
                else:
                    conn.execute('INSERT INTO kp(id,name,parent_id,level,ord,status,note) '
                                 "VALUES(?,?,?,?,?,'现行',?)",
                                 (p['id'], p['name'], p['parent'], p['level'],
                                  p['ord'], p['note']))
                    ins_kp += 1
                    inserted_ids.add(p['id'])
                    kp_id = p['id']
                if p['alias']:
                    n = conn.execute('INSERT OR IGNORE INTO kp_alias(kp_id,alias,alias_kind) '
                                     "VALUES(?,?,'老区名')", (kp_id, p['alias'])).rowcount
                    ins_alias += n

        post_counts, _ = snapshot(conn)
        # 守恒闸：存量 kp 行逐行哈希不变（只排掉**本次真插入**的 id——幂等重跑时旧枝已是存量）
        h = hashlib.sha256()
        for row in conn.execute(
                'SELECT id,name,parent_id,level,ord,status FROM kp ORDER BY id'):
            if row[0] not in inserted_ids:
                h.update(repr(tuple(row)).encode('utf-8'))
        assert h.hexdigest() == pre_hash, '🔴 守恒闸炸：存量 kp 行被改动'
        for t in ('question', 'question_kp'):
            assert post_counts[t] == pre_counts[t], f'🔴 守恒闸炸：{t} 行数变了'
        assert post_counts['kp'] - pre_counts['kp'] == ins_kp, '🔴 kp 增量对不上'

        print(f"✅ 铺枝完成：kp +{ins_kp}（幂等跳过 {skip}）alias +{ins_alias}；"
              f"kp {pre_counts['kp']}→{post_counts['kp']}；"
              f"question/question_kp 零触碰（{post_counts['question']}/{post_counts['question_kp']}）")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
