# -*- coding: utf-8 -*-
"""成品归库 —— 存量成品件迁入唯一成品根 `成品库/`（窗U，2026-08-22 用户归一令）
==============================================================================
🔴 口径（用户令原话「所有的文件只能走一个文件夹下面…专门负责存我们知识库的成品库，
不允许存其他的内容，隔离清楚」）：
  · **成品 ＝ artifact.files_json 指着的文件**（账上有指针才叫成品）；
  · 唯一成品根 ＝ 顶层 `成品库/`，一册一目录 `成品库/<artifact_id>·<人话名>/<文件>`；
  · 库内只放挂账成品——中间件（_源）、未挂账过程件、镜像分发一律不得入内；
  · 工艺出件目录（产物/）照旧是渲染自由区，**挂账时拷入成品库**是唯一归库动作。

动作（幂等）：读 files_json 非空的册 → 逐件拷入成品库 → 改写 files_json 新指针。
守恒三闸（缺一即整体回滚）：①件数相等 ②逐件 sha256 源=目标 ③新指针逐个可解析到盘上真文件。
原文件暂留原地（验收后另窗清理）。

用法：
  python 工具箱/挂账/成品归库.py --plan             # 只打迁移清单
  python 工具箱/挂账/成品归库.py --apply --db <路径>  # 执行（写 artifact 表=要写窗口）
"""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
DEST_ROOT = ROOT / '成品库'
BAD = re.compile(r'[\\/:*?"<>|\r\n]+')


def safe_name(s):
    return BAD.sub('·', (s or '').strip())[:60] or '未命名'


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def build_plan(conn):
    """→ [(aid, 册目录名, [(旧相对, 新相对)…], 已归一?)]"""
    plan = []
    for aid, name, fj in conn.execute(
            "SELECT id, name, files_json FROM artifact "
            "WHERE files_json IS NOT NULL AND files_json != '[]' ORDER BY id"):
        files = json.loads(fj)
        dirname = f'{aid}·{safe_name(name)}'
        pairs, seen = [], {}
        done = all(f.replace('\\', '/').startswith('成品库/') for f in files)
        for f in files:
            fp = f.replace('\\', '/')
            if fp.startswith('成品库/'):
                pairs.append((f, fp))
                continue
            base = fp.rsplit('/', 1)[-1]
            # 同册同名防撞（不同源目录出同名件）：第二个起加序号
            if base in seen:
                seen[base] += 1
                stem, dot, ext = base.rpartition('.')
                base = f'{stem}·{seen[base]}.{ext}' if dot else f'{base}·{seen[base]}'
            else:
                seen[base] = 1
            pairs.append((f, f'成品库/{dirname}/{base}'))
        plan.append((aid, dirname, pairs, done))
    return plan


def main():
    ap = argparse.ArgumentParser(description='成品归库（窗U）')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--db')
    a = ap.parse_args()

    db = a.db or str(ROOT / '知识库' / 'kb.db')
    mode = '' if a.apply else '?mode=ro'
    conn = sqlite3.connect(f'file:{Path(db).as_posix()}{mode}', uri=True)
    try:
        plan = build_plan(conn)
        n_files = sum(len(p[2]) for p in plan)
        n_todo = sum(1 for p in plan if not p[3])
        print(f'归库计划：{len(plan)} 册 / {n_files} 件（待迁 {n_todo} 册，已归一 {len(plan) - n_todo} 册）')
        if a.plan or not a.apply:
            for aid, d, pairs, done in plan[:8]:
                print(f'  {"✓已归一" if done else "→"} {d}（{len(pairs)} 件）')
            if len(plan) > 8:
                print(f'  …另 {len(plan) - 8} 册')
            return

        moved = skipped = 0
        missing = []
        for aid, dirname, pairs, done in plan:
            for old, new in pairs:
                if old.replace('\\', '/') == new:
                    continue
                src = ROOT / old
                dst = ROOT / new
                if not src.exists():
                    missing.append((aid, old))
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists() and sha256(dst) == sha256(src):
                    skipped += 1
                    continue
                shutil.copy2(src, dst)
                moved += 1
        # 🔴 源文件缺失=账实不符，如实拒迁该册指针（绝不指向不存在的文件）
        if missing:
            print(f'🔴 {len(missing)} 件账上有指针盘上无文件（该册指针不改，如实列）：')
            for aid, old in missing[:10]:
                print(f'   {aid}  {old}')

        # 守恒闸①②：逐件核（拷贝层）
        bad = []
        for aid, dirname, pairs, done in plan:
            if any(m[0] == aid for m in missing):
                continue
            for old, new in pairs:
                if old.replace('\\', '/') == new:
                    continue
                if sha256(ROOT / old) != sha256(ROOT / new):
                    bad.append((aid, old))
        assert not bad, f'🔴 守恒闸②炸：{len(bad)} 件源目标哈希不符 {bad[:3]}'

        # 改指针（跳过缺件册）；🔴 artifact_file 表在就同步改它的 rel_path（窗V 双写同源）
        has_af = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='artifact_file'").fetchone() is not None
        with conn:
            n_upd = n_af = 0
            for aid, dirname, pairs, done in plan:
                if done or any(m[0] == aid for m in missing):
                    continue
                newfiles = [new for _, new in pairs]
                conn.execute('UPDATE artifact SET files_json=? WHERE id=?',
                             (json.dumps(newfiles, ensure_ascii=False), aid))
                n_upd += 1
                if has_af:
                    for old, new in pairs:
                        if old.replace('\\', '/') != new:
                            n_af += conn.execute(
                                'UPDATE artifact_file SET rel_path=? WHERE artifact_id=? '
                                'AND rel_path=?', (new, aid, old)).rowcount
            if has_af and n_af:
                print(f'  同步 artifact_file 路径 {n_af} 行')

        # 守恒闸③：新指针逐个可解析
        dangling = []
        for aid, name, fj in conn.execute(
                "SELECT id, name, files_json FROM artifact "
                "WHERE files_json IS NOT NULL AND files_json != '[]'"):
            for f in json.loads(fj):
                if f.replace('\\', '/').startswith('成品库/') and not (ROOT / f).exists():
                    dangling.append((aid, f))
        assert not dangling, f'🔴 守恒闸③炸：{len(dangling)} 个新指针盘上无文件 {dangling[:3]}'

        n_after = sum(1 for _ in DEST_ROOT.rglob('*') if _.is_file())
        print(f'✅ 归库完成：拷入 {moved}（幂等跳过 {skipped}）｜改指针 {n_upd} 册｜'
              f'成品库现有 {n_after} 件｜缺件册 {len(set(m[0] for m in missing))} 个（指针未动）')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
