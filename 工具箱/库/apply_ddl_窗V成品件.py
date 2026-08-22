# -*- coding: utf-8 -*-
"""窗V · 成品件硬绑 DDL + 回填（2026-08-22 用户令「关联关系补上去」）
==============================================================================
做两件事（幂等，可反复跑）：
  ① 建表 artifact_file（成品件实体行：外键绑册 + role 角色 + sha256/size + paper_id 血缘）
     + exam_model 补 artifact_id 真外键列（分析模型↔册，此前只在 dsl_ref 字符串里）；
  ② 回填：把 87 册 files_json 的 793 件逐个建行——角色机器判定、哈希实算、卷血缘按册唯一卷绑。

🔴 角色判定（纯机械、可复算，判不准的一律落 '其他' 不猜）：
     文件名含「（答案）/(答案)/答案卷」          → 答案卷
     含「分析图」                                → 分析图
     含「考频分析/·分析.md/报告」（且 .md）      → 分析报告
     含「封面/cover」                            → 封面
     含「样张/初版样张/_chk/目检」               → 样张
     其余 .png 且册细类=历史册（页图流：01第一天.png 这类） → 页图
     其余 .pdf/.md                               → 题目卷
🔴 files_json 不废：它是兼容视图，本表是权威明细；两者同源，末尾守恒闸逐册对账
   （件数相等 + 路径集合相等），不许漂移。

用法：
  python 工具箱/库/apply_ddl_窗V成品件.py --plan            # 只报计划（角色分布/待建行数）
  python 工具箱/库/apply_ddl_窗V成品件.py --apply --db <路径>
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]

DDL_TABLE = """
CREATE TABLE IF NOT EXISTS artifact_file (
  id          TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL REFERENCES artifact(id),
  rel_path    TEXT NOT NULL,
  role        TEXT NOT NULL CHECK(role IN
                ('题目卷','答案卷','分析图','分析报告','页图','封面','样张','其他')),
  ord         INTEGER,
  ext         TEXT,
  bytes       INTEGER,
  sha256      TEXT,
  paper_id    TEXT REFERENCES paper(id),
  note        TEXT,
  created_at  TEXT,
  UNIQUE (artifact_id, rel_path)
);
"""
DDL_IDX = [
    "CREATE INDEX IF NOT EXISTS ix_afile_artifact ON artifact_file(artifact_id)",
    "CREATE INDEX IF NOT EXISTS ix_afile_role     ON artifact_file(role)",
    "CREATE INDEX IF NOT EXISTS ix_afile_sha      ON artifact_file(sha256)",
]

RX = [
    # 🔴 答案卷的三种真实命名（窗V 实测 793 件得出）：v2 产线「（答案）」、
    #    老区平移册「（解析）」、少数「答案卷/·答案」。漏一种就有一批答案卷认成题目卷。
    ('答案卷', re.compile(r'（答案）|\(答案\)|答案卷|·答案|（解析）|\(解析\)|解析版')),
    ('分析图', re.compile(r'分析图')),
    ('分析报告', re.compile(r'考频分析|·分析\.md$|报告')),
    ('封面', re.compile(r'封面|cover', re.I)),
    ('样张', re.compile(r'样张|_chk|目检')),
]


def judge_role(base, ext, 细类):
    for role, rx in RX:
        if rx.search(base):
            # 分析报告只认 md（PDF 版报告归题目卷/其他，避免把卷子误判成报告）
            if role == '分析报告' and ext != 'md':
                continue
            return role
    if ext == 'png':
        return '页图' if 细类 == '历史册' else '其他'
    if ext in ('pdf', 'md'):
        return '题目卷'
    return '其他'


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def collect(conn):
    """→ [(aid, 细类, [(rel, base, ext, role, ord)…])]"""
    out = []
    for aid, 细类, fj in conn.execute(
            "SELECT id, 细类, files_json FROM artifact "
            "WHERE files_json IS NOT NULL AND files_json != '[]' ORDER BY id"):
        rows = []
        for i, f in enumerate(json.loads(fj), 1):
            rel = f.replace('\\', '/')
            base = rel.rsplit('/', 1)[-1]
            ext = base.rsplit('.', 1)[-1].lower() if '.' in base else ''
            rows.append((rel, base, ext, judge_role(base, ext, 细类), i))
        out.append((aid, 细类, rows))
    return out


def main():
    ap = argparse.ArgumentParser(description='窗V 成品件硬绑 DDL+回填')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--db')
    a = ap.parse_args()

    db = a.db or str(ROOT / '知识库' / 'kb.db')
    conn = sqlite3.connect(f'file:{Path(db).as_posix()}'
                           + ('' if a.apply else '?mode=ro'), uri=True)
    try:
        data = collect(conn)
        n_files = sum(len(r[2]) for r in data)
        dist = {}
        for _, _, rows in data:
            for *_x, role, _o in rows:
                dist[role] = dist.get(role, 0) + 1
        print(f'计划：{len(data)} 册 / {n_files} 件；角色分布 '
              + '｜'.join(f'{k} {v}' for k, v in sorted(dist.items(), key=lambda x: -x[1])))
        if a.plan or not a.apply:
            for aid, 细类, rows in data[:3]:
                print(f'  {aid}（{细类}）')
                for rel, base, ext, role, o in rows[:4]:
                    print(f'    [{role}] {base[:56]}')
            return

        # ① DDL
        with conn:
            conn.execute(DDL_TABLE)
            for s in DDL_IDX:
                conn.execute(s)
            cols = [c[1] for c in conn.execute('PRAGMA table_info(exam_model)')]
            if 'artifact_id' not in cols:
                conn.execute('ALTER TABLE exam_model ADD COLUMN artifact_id TEXT '
                             'REFERENCES artifact(id)')
                print('  exam_model +artifact_id 列')

        # 册 → 唯一卷（多卷册不猜血缘，留空）
        paper_of = {}
        for aid, cnt, pid in conn.execute(
                'SELECT artifact_id, COUNT(*), MIN(id) FROM paper '
                'WHERE artifact_id IS NOT NULL GROUP BY artifact_id'):
            if cnt == 1:
                paper_of[aid] = pid

        ins = skip = miss = 0
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with conn:
            for aid, 细类, rows in data:
                for rel, base, ext, role, o in rows:
                    if conn.execute('SELECT 1 FROM artifact_file WHERE artifact_id=? '
                                    'AND rel_path=?', (aid, rel)).fetchone():
                        skip += 1
                        continue
                    p = ROOT / rel
                    if not p.exists():
                        miss += 1
                        print(f'  ⚠️ 盘上无此件，跳过建行：{rel}')
                        continue
                    fid = 'F' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
                    conn.execute(
                        'INSERT INTO artifact_file(id,artifact_id,rel_path,role,ord,ext,'
                        'bytes,sha256,paper_id,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (fid, aid, rel, role, o, ext, p.stat().st_size, sha256_of(p),
                         paper_of.get(aid), '窗V 回填（角色机器判定）', now))
                    ins += 1

            # exam_model 回填册外键（params_json 的源卷 → paper.artifact_id）
            n_em = 0
            for mid, dsl, params in conn.execute(
                    'SELECT id, dsl_ref, params_json FROM exam_model WHERE artifact_id IS NULL'):
                aid = None
                m = re.search(r'--artifact\s+(A\w+)', dsl or '')
                if m:
                    aid = m.group(1)
                elif params:
                    pid = (json.loads(params) or {}).get('源卷')
                    if pid:
                        row = conn.execute('SELECT artifact_id FROM paper WHERE id=?',
                                           (pid,)).fetchone()
                        aid = row[0] if row else None
                if aid and conn.execute('SELECT 1 FROM artifact WHERE id=?', (aid,)).fetchone():
                    conn.execute('UPDATE exam_model SET artifact_id=? WHERE id=?', (aid, mid))
                    n_em += 1

        # 🔴 守恒闸：逐册对账 files_json vs artifact_file（件数+路径集合）
        bad = []
        for aid, 细类, rows in data:
            want = {r[0] for r in rows if (ROOT / r[0]).exists()}
            got = {r[0] for r in conn.execute(
                'SELECT rel_path FROM artifact_file WHERE artifact_id=?', (aid,))}
            if want != got:
                bad.append((aid, len(want), len(got)))
        assert not bad, f'🔴 守恒闸炸：{len(bad)} 册两侧不一致 {bad[:3]}'

        total = conn.execute('SELECT COUNT(*) FROM artifact_file').fetchone()[0]
        by_role = dict(conn.execute('SELECT role, COUNT(*) FROM artifact_file GROUP BY role'))
        dup = conn.execute('SELECT COUNT(*) FROM (SELECT sha256 FROM artifact_file '
                           'GROUP BY sha256 HAVING COUNT(*) > 1)').fetchone()[0]
        print(f'✅ 回填完成：+{ins} 行（幂等跳过 {skip}，盘上缺件 {miss}）；'
              f'artifact_file 共 {total} 行；exam_model 绑册 {n_em} 行')
        print('   角色：' + '｜'.join(f'{k} {v}' for k, v in
                                      sorted(by_role.items(), key=lambda x: -x[1])))
        print(f'   内容重复（同 sha256 多件）：{dup} 组——查重能力上线')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
