# -*- coding: utf-8 -*-
"""A 账层桥自证（PRD-003 阶段1）——一键复跑，全在沙盘副本上，不碰主位两库。

跑法（worktree 根执行）：
  python 工具箱/桥/bridge_shelf_test.py

每次从主位**新拷**一份 kb.db / 资料库.db 进沙盘，保证起点干净、结果可复现。
🔴 主位库只被 shutil.copy2 读一次；资料库.db 的每一个 sqlite 连接都是 mode=ro。
🔴 WAL 边车：拷之前先清沙盘的 -wal/-shm 残留，拷之后立刻对**副本**做 wal_checkpoint(TRUNCATE)
   （主位只读没法 checkpoint，只能在副本这一侧把 WAL 折进主库文件）——见 T10 与快照说明。
🔴 账面基线一律拿"本次副本的起点"现算（base/c1/c2 三个快照），不写死昨天的数字——
   主位 kb.db 天天在动（KG 铺枝之类），写死数字的断言迟早变成假红。

自证清单（正例 + 每条修复配的反例）：
  T1  只读闸：写探针打在 mode=ro 连接上必须被拒
  T2  dry-run 数字对（82/24/49/735）且**零写库**
  T3  dry-run 报告两份都落地，且含缺失清单与拷贝清单
  T4  --apply 后各表行数与 punch_map 全对上
  T5  幂等：再跑一遍 --apply，四表零新增、punch_map 零新增、artifact 内容零变更
  T6  抽 5 条 artifact 目检字段（kind/status/sale_state/link/note/files_json）
  T7  落位路径闸：files_json 里 735 条落位路径全相对、全正斜杠、全唯一
  T8  抽样拷贝：3 个真文件拷进沙盘临时目录（🔴 须 --apply + 显式 --sample-dest）
  T9  零 LLM 静态闸：桥脚本源码里不许出现任何模型/AI 接口调用
  T10 WAL 边车：种下的 4 个假边车重置后必须消失（期望清单=字面常量，与被测函数不同源）
  T11 反例·落盘闸：缺 --apply 的 --copy-sample / --copy-assets 必炸，且落位目录零新文件
  T12 反例·抽样落位闸：--copy-sample 缺 --sample-dest 必炸；判据=跑前快照 vs 跑后对比（零新增）
  T13 反例·词表探测闸：artifact.kind 的 CHECK 被剥掉后必炸（不许兜底降级），错话给人工核对命令
  T14 守恒闸 G4·库态 + 增量补挂自愈：失联可补 → dry-run 绿并预告，--apply 真补；幽灵 → 照炸
  T15 溯源键改名：note 里没有「源文件路径」，只有 punch_溯源路径 + 兄弟键「仅溯源非指针」
  T16 反例·落位正本闸：源库改册名 / 加同名副册后复吃，落位一律从 punch_map 取，不重算不漂移
  T17 反例·G4 语义分层：同一份坏账，源行还在 → dry-run 绿并预告补挂；源行没了 → dry-run 就红；
      幽灵 → dry-run 就红（坏账在写库之前红，不许"dry-run 绿灯、--apply 才落坏账"）
  T18 反例·拷贝失败闸 + 盘账闸 G5：占位一个落位 → exit 2 且点名；账对账绿但盘上没文件 → G5 揪出来
  T19 反例·「已登记即该挂」：源文件事后从盘上消失，也绝不撤 files_json 指针（钉 want 的 locked 半边）
  T20 反例·apply 收尾审**库态**：把补挂 UPDATE 摘掉注入桥副本 → --apply 必 exit 2 且错话说"库态"；
      顺带钉 anchor 定序/众数的可复现性（并列时按目录名升序，不看 dict 插入序）
  T21 反例·盘→账闸 G6：判**拒收**的册资产一个都不许落盘；手工塞一个无账文件 → exit 2 且点名
  T22 反例·anchor 众数：源库把一条外册资产改挂过来，不许把整册新资产带歪到外册目录；跨目录单开人审
  T23 反例·孤儿资产守恒闸：asset.doc_id 查无此册 → exit 2 点名（不是裸 KeyError rc=1 零报告）
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import json
import os
import re
import shutil
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                                   # worktree 根
BRIDGE = HERE / 'bridge_shelf.py'
sys.path.insert(0, str(HERE))
import bridge_shelf as BS                                # 纯函数层直调（anchor 定序/众数、sanitize）
MAIN_KB = Path(r'D:\workplace\ai-bkb-v2\知识库\kb.db')
MAIN_PUNCH = Path(r'D:\workplace\ai-bkb-v2\知识库\资料库.db')
SAND = ROOT / '试验场' / '2026-08-19-prd003沙盘' / 'A-账层桥'
KB = SAND / 'kb.db'
PUNCH = SAND / '资料库.db'
PRISTINE_KB = SAND / 'kb-起点副本.db'                    # 未吃过的起点，给 T18 迷你库用
NOVOCAB_KB = SAND / 'kb-反例-无kind词表.db'
DRIFT_KB = SAND / 'kb-反例-落位漂移.db'
DRIFT_PUNCH = SAND / '资料库-反例-改名加副册.db'
DRIFT_ASSET = SAND / '反例-增量新增资产.png'             # T16 新增资产的真源文件
LESS_KB = SAND / 'kb-反例-分层.db'
LESS_PUNCH = SAND / '资料库-反例-源缺资产行.db'
GHOST_KB = SAND / 'kb-反例-幽灵.db'
MINI_KB = SAND / 'kb-反例-盘账.db'
MINI_PUNCH = SAND / '资料库-迷你.db'
MINI_PUNCH2 = SAND / '资料库-迷你-少一行.db'
T19_KB = SAND / 'kb-反例-locked半边.db'
T19_PUNCH = SAND / '资料库-反例-源文件已不在盘.db'
T20_KB = SAND / 'kb-反例-补挂漏刀.db'
LEAK_BRIDGE = SAND / 'bridge_shelf-注入漏刀.py'          # 摘掉补挂 UPDATE 的桥副本（T20 反例造具）
T21_KB = SAND / 'kb-反例-无账孤儿.db'
T21_PUNCH = SAND / '资料库-迷你-带拒收册.db'
T22_KB = SAND / 'kb-反例-改挂外册.db'
T22_PUNCH = SAND / '资料库-反例-改挂外册.db'
T22_ASSET = SAND / '反例-改挂后新增资产.png'
T23_KB = SAND / 'kb-反例-孤儿资产.db'
T23_PUNCH = SAND / '资料库-反例-孤儿资产.db'
REPORT_DIR = SAND / '报告'
COPY_ROOT = SAND / '落位验证'
DRY_DEST = SAND / '落位验证-反例dryrun'                  # 反例专用：跑完必须一个文件都没有
FAIL_DEST = SAND / '落位验证-反例拷贝失败'
MINI_DEST = SAND / '落位验证-迷你全量'
G6_DEST = SAND / '落位验证-G6盘账'
SNAP_NOTE = REPORT_DIR / '沙盘副本快照说明.md'

EXPECT = {'doc': 82, 'doc_member': 24, 'material': 49, 'asset': 735}
SIDECARS = ('-wal', '-shm')
# 🔴 T10 的期望清单写**字面常量**，绝不与被测的 sidecar_paths() 同源——
#    同源写法是恒真断言：函数返回空列表时 planted==purged==[] 照样绿，等于没测。
EXPECT_SIDECARS = ('kb.db-wal', 'kb.db-shm', '资料库.db-wal', '资料库.db-shm')
# T12 的落位泼溅监视区：跑前快照 / 跑后对比，判据是"本轮零新增"，不是"这目录不存在"
WATCH_DIRS = (ROOT / '产物', ROOT / '知识库')

_fail = []
_pass = []


def check(name, ok, detail=''):
    (_pass if ok else _fail).append(name)
    print(f'{"✅" if ok else "🔴"} {name}' + (f' —— {detail}' if detail else ''))


def eq(name, got, want):
    ok = got == want
    cut = 4000 if not ok else 110                      # 过了就只留一眼，挂了才铺全量证据
    check(name, ok, f'实得 {got!r}'[:cut] + f' / 应得 {want!r}'[:cut])


def run_bridge_raw(*extra, kb=None, punch=None, script=None):
    cmd = [sys.executable, str(script or BRIDGE), '--punch', str(punch or PUNCH), '--kb', str(kb or KB),
           '--report-dir', str(REPORT_DIR)] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', cwd=str(ROOT))
    return r.returncode, r.stdout, r.stderr


def run_bridge(*extra, kb=None, punch=None):
    rc, out, err = run_bridge_raw(*extra, kb=kb, punch=punch)
    if rc != 0:
        print(out)
        print(err, file=sys.stderr)
        raise SystemExit(f'桥退出码 {rc}')
    return out


def kb_counts(db=None):
    conn = sqlite3.connect(str(db or KB))
    try:
        out = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
               for t in ('artifact', 'artifact_member', 'material', 'punch_map')}
        out['punch_map_by_kind'] = dict(conn.execute(
            'SELECT kind, COUNT(*) FROM punch_map GROUP BY 1').fetchall())
        return out
    finally:
        conn.close()


def artifact_snapshot():
    conn = sqlite3.connect(str(KB))
    try:
        return {r[0]: r[1:] for r in conn.execute(
            'SELECT id,name,kind,status,files_json,source_line,link,note,sale_state FROM artifact')}
    finally:
        conn.close()


def q(sql, args=(), db=None):
    conn = sqlite3.connect(str(db or KB))
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def files_of(aid, db=None):
    raw = q('SELECT files_json FROM artifact WHERE id=?', (aid,), db)[0][0]
    return json.loads(raw) if raw else []


def set_files(aid, arr, db=None):
    conn = sqlite3.connect(str(db or KB))
    try:
        conn.execute('UPDATE artifact SET files_json=? WHERE id=?',
                     (json.dumps(arr, ensure_ascii=False), aid))
        conn.commit()
    finally:
        conn.close()


def art_of_doc(pid, db=None):
    return q("SELECT kb_id FROM punch_map WHERE kind='doc' AND punch_id=?", (str(pid),), db)[0][0]


def all_landing(db=None):
    """库里所有跟本桥有关的落位指针（punch_map 登记 + 已吃册 files_json）。"""
    pm = {r[0] for r in q("SELECT kb_id FROM punch_map WHERE kind='asset'", (), db)}
    fj = set()
    for (raw,) in q("SELECT a.files_json FROM punch_map p JOIN artifact a ON a.id=p.kb_id "
                    "WHERE p.kind='doc' AND a.files_json IS NOT NULL", (), db):
        fj |= {x for x in json.loads(raw) if x.startswith('产物/历史打卡/')}
    return pm, fj


def section(txt, head):
    """报告里截一段（`## X` 到下一个 `## ` 之前）。

    🔴 缺段就返空串——判据该红要红，不许拿 IndexError/异常当结论。"""
    return txt.split(head)[-1].split('\n## ')[0] if head in txt else ''


def landed_rels(dest):
    """落位根 dest 下真实落地的文件 → 落位相对路径清单（跟 files_json 同口径）。"""
    base = dest / '产物' / '历史打卡'
    if not base.is_dir():
        return []
    return sorted('产物/历史打卡/' + p.relative_to(base).as_posix()
                  for p in base.rglob('*') if p.is_file())


def tree_snap(*roots):
    """跑前/跑后目录快照：不存在记 None，存在记全量相对路径清单（文件+目录都算）。"""
    return {str(r): (sorted(str(p.relative_to(r)) for p in r.rglob('*')) if r.exists() else None)
            for r in roots}


def sidecar_paths():
    return [SAND / (n + s) for n in ('kb.db', '资料库.db') for s in SIDECARS]


def reset_sandbox():
    """沙盘重置：清残留 → 拷主位（.db + -wal）→ 副本侧 checkpoint(TRUNCATE) → 边车归零。

    🔴 顺序不能换：上一轮遗留的 -wal 会被 sqlite 当成新拷进来那份库的 WAL 去回放，
    页号对不上轻则读到旧账、重则库像坏了。主位这一侧不做任何写动作（只读连接不能 checkpoint）。"""
    SAND.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for d in (COPY_ROOT, DRY_DEST, FAIL_DEST, MINI_DEST, G6_DEST):
        if d.exists():
            shutil.rmtree(d)
    for f in (NOVOCAB_KB, DRIFT_KB, DRIFT_PUNCH, DRIFT_ASSET, LESS_KB, LESS_PUNCH,
              GHOST_KB, MINI_KB, MINI_PUNCH, MINI_PUNCH2, PRISTINE_KB,
              T19_KB, T19_PUNCH, T20_KB, LEAK_BRIDGE, T21_KB, T21_PUNCH,
              T22_KB, T22_PUNCH, T22_ASSET, T23_KB, T23_PUNCH):
        if f.exists():
            f.unlink()

    # ── 反例种子：先种 4 个假边车（kb 与资料库各两个）。
    #    purged 记的是"拷库之前真删掉的那几个"——修复前只删资料库那两个，kb.db 的边车会带着
    #    残留去接新拷进来的库；T10 拿 purged 跟**字面常量**比，直接抓这一刀。
    for p in sidecar_paths():
        p.write_bytes(b'STALE-SIDECAR-\x00\x01\x02')
    planted = [p.name for p in sidecar_paths()]
    purged = []
    for p in sidecar_paths():
        if p.exists():
            p.unlink()
            purged.append(p.name)

    snap = []
    for src, dst in ((MAIN_KB, KB), (MAIN_PUNCH, PUNCH)):
        shutil.copy2(src, dst)
        wal = Path(str(src) + '-wal')
        carried = None
        if wal.exists() and wal.stat().st_size > 0:
            # 主位处 WAL 模式：只拷 .db 会丢掉还压在 -wal 里的已提交事务，故边车随行；
            # -shm 不拷（可由 -wal 重建，且它被主位进程占着，跟着拷只会添乱）
            shutil.copy2(wal, Path(str(dst) + '-wal'))
            carried = wal.stat().st_size
        conn = sqlite3.connect(str(dst))
        try:
            mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
            ckpt = conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
            qc = conn.execute('PRAGMA quick_check').fetchone()[0]
        finally:
            conn.close()
        for s in SIDECARS:                             # 干净关闭后 sqlite 自删边车；兜底再扫一遍
            p = Path(str(dst) + s)
            if p.exists():
                p.unlink()
        snap.append({'库': dst.name, 'journal_mode': mode, '随行-wal字节': carried,
                     'wal_checkpoint(TRUNCATE)': list(ckpt), 'quick_check': qc,
                     '副本字节': dst.stat().st_size, '源字节': src.stat().st_size})
    shutil.copy2(KB, PRISTINE_KB)                      # 留一份"没吃过"的起点给 T18
    return planted, purged, snap


def write_snapshot_note(planted, purged, snap):
    L = ['# 沙盘副本快照一致性说明（A 账层桥自证）', '',
         '本文件由 `工具箱/桥/bridge_shelf_test.py` 每次跑测时重写。', '',
         '## 取快照的办法（为什么是这个办法）', '',
         '- 主位两库都是 **WAL 模式**，已提交但没 checkpoint 的事务压在 `-wal` 边车里；',
         '- 🔴 主位只准只读：**只读连接跑不了 `wal_checkpoint`**（checkpoint 是写动作），',
         '  所以「拷之前先把主位 checkpoint 干净」这条路直接堵死，不可行；',
         '- 改走的路：**先清沙盘边车残留 → 拷 `.db` + `-wal`（`-shm` 不拷，可重建）→ '
         '打开副本立刻 `PRAGMA wal_checkpoint(TRUNCATE)` → 关连接后边车归零**，',
         '  副本因此是一份「单文件、自洽、可复现」的快照，后续所有只读连接都不再生成新边车残留。', '',
         f'- 本次重置前种下的假边车 {len(planted)} 个：`{"`、`".join(planted)}`；'
         f'**拷库前实删 {len(purged)} 个**：`{"`、`".join(purged) if purged else "（一个都没删）"}`',
         '  （T10 反例种子，用来证明重置真的在拷库前删边车，而不是"正好没有"；'
         '  期望清单在测试里是**字面常量**，不与被测函数同源，避免恒真断言）。', '',
         '## 本次快照', '',
         '| 库 | journal_mode | 随行 -wal 字节 | wal_checkpoint(TRUNCATE) 返回 | quick_check | 副本字节 | 源字节 |',
         '|---|---|---:|---|---|---:|---:|']
    for s in snap:
        L.append(f'| `{s["库"]}` | {s["journal_mode"]} | {s["随行-wal字节"] if s["随行-wal字节"] else 0} | '
                 f'`{s["wal_checkpoint(TRUNCATE)"]}`（busy, wal总帧, 已折帧） | {s["quick_check"]} | '
                 f'{s["副本字节"]} | {s["源字节"]} |')
    L += ['', '## 一致性的边界（说清楚，不含糊）', '',
          '- 快照 = 「拷贝那一瞬间」的主位状态。若拷贝进行中主位正好在写，副本可能落后一个事务；',
          '  本沙盘只做**映射关系自证**（82/24/49/735 的对位与闸），不做金额级对账，这点漂移可接受；',
          '- `quick_check=ok` 是副本自洽的机器判据：`-wal` 已折进主库文件、页面结构完好；',
          '- 主位在整个过程中**只被 read**（`shutil.copy2` 读 + 只读连接），零写入、零 checkpoint。', '']
    SNAP_NOTE.write_text('\n'.join(L) + '\n', encoding='utf-8')


def make_novocab_kb():
    """反例造具：把 artifact.kind 的 CHECK 从建表 SQL 里剥掉（writable_schema 改 sqlite_master）。"""
    shutil.copy2(KB, NOVOCAB_KB)
    conn = sqlite3.connect(str(NOVOCAB_KB))
    try:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='artifact'").fetchone()[0]
        stripped = re.sub(r'\s*CHECK\(kind IN \([^)]*\)\)', '', sql)
        if stripped == sql:
            raise SystemExit('反例造具失败：没能从 artifact 建表 SQL 里剥掉 kind 的 CHECK')
        ver = conn.execute('PRAGMA schema_version').fetchone()[0]
        conn.execute('PRAGMA writable_schema=ON')
        conn.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name='artifact'", (stripped,))
        conn.execute(f'PRAGMA schema_version={ver + 1}')
        conn.execute('PRAGMA writable_schema=OFF')
        conn.commit()
    finally:
        conn.close()
    conn = sqlite3.connect(str(NOVOCAB_KB))
    try:
        return 'CHECK(kind IN' not in conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='artifact'").fetchone()[0]
    finally:
        conn.close()


def make_drift_punch():
    """反例造具（T16）：照 adv2/adv3c 的手法把源库的册名格局搅乱，再给已吃册塞一条新资产。

      ① 改名：把 B 册（资产第二多）改名 → 现算落位目录会变成新名字；
      ② 加同名副册：给 A 册（资产最多）插一本同名不同版本名的册 → plan_book_dirs 的重名去重
         会把**老册 A** 的目录从 `名称` 顶成 `名称·版本名`（老行一个字没改，落位却漂了）；
      ③ 给 A 册加一条新资产（真文件在沙盘里）→ 验它是不是乖乖落进 A 的**既有登记目录**。
    返回 (A册punch_id, A册名, B册punch_id, B册新名, 新资产落位应在的目录前缀)。"""
    shutil.copy2(PUNCH, DRIFT_PUNCH)
    conn = sqlite3.connect(str(DRIFT_PUNCH))
    conn.row_factory = sqlite3.Row
    try:
        tops = conn.execute('SELECT doc_id, COUNT(*) c FROM asset GROUP BY 1 ORDER BY c DESC LIMIT 2').fetchall()
        a_id, b_id = tops[0]['doc_id'], tops[1]['doc_id']
        a = dict(conn.execute('SELECT * FROM doc WHERE id=?', (a_id,)).fetchone())
        b_old = conn.execute('SELECT 名称 FROM doc WHERE id=?', (b_id,)).fetchone()[0]
        b_new = b_old + '（改名）'
        conn.execute('UPDATE doc SET 名称=? WHERE id=?', (b_new, b_id))          # ① 改名
        cols = [k for k in a if k != 'id']
        a['版本名'] = '副册'                                                      # ② 同名副册
        newid = conn.execute('SELECT MAX(id)+1 FROM doc').fetchone()[0]
        conn.execute('INSERT INTO doc(id,{}) VALUES(?,{})'.format(
            ','.join('"%s"' % k for k in cols), ','.join('?' * len(cols))),
            [newid] + [a[k] for k in cols])
        # ③ 新资产：真源文件放沙盘里（绝对路径，跟老区资产同构），basename 册内唯一
        src = conn.execute('SELECT 路径 FROM asset WHERE doc_id=? ORDER BY id LIMIT 1',
                           (a_id,)).fetchone()[0]
        shutil.copy2(src, DRIFT_ASSET)
        acols = [d[0] for d in conn.execute('SELECT * FROM asset LIMIT 1').description]
        row0 = dict(conn.execute('SELECT * FROM asset WHERE doc_id=? ORDER BY id LIMIT 1',
                                 (a_id,)).fetchone())
        row0['路径'] = str(DRIFT_ASSET)
        newaid = conn.execute('SELECT MAX(id)+1 FROM asset').fetchone()[0]
        ac = [k for k in acols if k != 'id']
        conn.execute('INSERT INTO asset(id,{}) VALUES(?,{})'.format(
            ','.join('"%s"' % k for k in ac), ','.join('?' * len(ac))),
            [newaid] + [row0[k] for k in ac])
        conn.commit()
        return str(a_id), a['名称'], str(b_id), b_new, str(newaid)
    finally:
        conn.close()


def make_mini_punch(dst, keep_docs):
    """反例造具（T18）：只留几本小册的迷你源库——全量 --copy-assets 才拷得起（几百 KB）。"""
    shutil.copy2(PUNCH, dst)
    conn = sqlite3.connect(str(dst))
    try:
        ph = ','.join('?' * len(keep_docs))
        conn.execute(f'DELETE FROM asset WHERE doc_id NOT IN ({ph})', keep_docs)
        conn.execute(f'DELETE FROM material WHERE doc_id NOT IN ({ph})', keep_docs)
        conn.execute('DELETE FROM doc_member')
        conn.execute(f'DELETE FROM doc WHERE id NOT IN ({ph})', keep_docs)
        conn.commit()
        return conn.execute('SELECT COUNT(*) FROM asset').fetchone()[0]
    finally:
        conn.close()


def main():
    # ── 沙盘重置（主位只读，绝不回写）────────────────────────────────
    planted, purged, snap = reset_sandbox()
    write_snapshot_note(planted, purged, snap)
    base = kb_counts()
    print(f'沙盘就绪：kb 起点 {base}\n')

    # ── T10 WAL 边车（🔴 期望清单=字面常量，与 sidecar_paths() 不同源）──
    eq('T10 种下的假边车正是那 4 个（字面常量比对）', sorted(planted), sorted(EXPECT_SIDECARS))
    eq('T10 反例：拷库前把那 4 个残留边车全删了（kb.db 那两个不许漏）',
       sorted(purged), sorted(EXPECT_SIDECARS))
    eq('T10 副本 checkpoint 后无 -wal/-shm 残留',
       [n for n in EXPECT_SIDECARS if (SAND / n).exists()], [])
    eq('T10 两份副本 quick_check 全 ok', [s['quick_check'] for s in snap], ['ok', 'ok'])
    check('T10 副本快照一致性说明落地', SNAP_NOTE.exists(), str(SNAP_NOTE))
    check('T10 说明里写清了「主位只读跑不了 checkpoint，改在副本侧折 WAL」',
          '只读连接跑不了' in SNAP_NOTE.read_text(encoding='utf-8')
          and 'wal_checkpoint(TRUNCATE)' in SNAP_NOTE.read_text(encoding='utf-8'))

    # ── T1 只读闸 ────────────────────────────────────────────────────
    conn = sqlite3.connect('file:' + PUNCH.as_posix() + '?mode=ro', uri=True)
    try:
        conn.execute('CREATE TABLE _只读探针(x)')
        check('T1 只读闸：mode=ro 连接拒绝写', False, '写探针竟然成功了')
    except sqlite3.OperationalError as e:
        check('T1 只读闸：mode=ro 连接拒绝写', True, str(e))
    finally:
        conn.close()

    # ── T2 dry-run 数字对 + 零写库 ──────────────────────────────────
    out = run_bridge()
    m = dict(re.findall(r'^\s{2}(\S+)\s+入库\s+(\d+)', out, re.M))
    for t, want in EXPECT.items():
        eq(f'T2 dry-run {t} 计划入库 = {want}', int(m.get(t, -1)), want)
    eq('T2 dry-run 零写库（kb 四表行数原样）', kb_counts(), base)
    check('T2 dry-run 自报「未写库、未拷文件」', '未写库、未拷文件' in out)

    # ── T3 报告落地 ─────────────────────────────────────────────────
    r1 = REPORT_DIR / '预检-资产PDF.md'
    r2 = REPORT_DIR / '吃库报告-A账层桥.md'
    check('T3 预检报告落地', r1.exists(), str(r1))
    check('T3 运行报告落地', r2.exists(), str(r2))
    t1 = r1.read_text(encoding='utf-8')
    check('T3 预检含存在性小节', '## ① 存在性预检' in t1)
    check('T3 预检含缺失清单小节', '缺失清单' in t1)
    check('T3 预检含拷贝清单表头', '落位（相对 v2 根）' in t1)
    eq('T3 拷贝清单 735 行落位路径', t1.count('| `产物/历史打卡/'), 735)

    # ── T4 --apply 后行数与 punch_map 全对上 ────────────────────────
    run_bridge('--apply')
    c1 = kb_counts()
    eq('T4 artifact 新增 82', c1['artifact'] - base['artifact'], 82)
    eq('T4 artifact_member 新增 24', c1['artifact_member'] - base['artifact_member'], 24)
    eq('T4 material 新增 49', c1['material'] - base['material'], 49)
    eq('T4 punch_map 新增 866（82+49+735）', c1['punch_map'] - base['punch_map'], 82 + 49 + 735)
    eq('T4 punch_map 分 kind', c1['punch_map_by_kind'], {'doc': 82, 'material': 49, 'asset': 735})

    conn = sqlite3.connect(str(KB))
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        eq('T4 外键自检零违例', conn.execute('PRAGMA foreign_key_check').fetchall(), [])
        eq('T4 artifact 全 source_line=punch-console 吃库',
           conn.execute("SELECT COUNT(*) FROM artifact WHERE source_line='punch-console 吃库'").fetchone()[0], 82)
        eq('T4 artifact 全 status=已交付',
           conn.execute("SELECT COUNT(*) FROM artifact WHERE source_line='punch-console 吃库' "
                        "AND status='已交付'").fetchone()[0], 82)
        eq('T4 sale_state 分布 = 源人工态（在售17/待整理36/空29）',
           dict(conn.execute("SELECT COALESCE(sale_state,'(空)'), COUNT(*) FROM artifact "
                             "WHERE source_line='punch-console 吃库' GROUP BY 1").fetchall()),
           {'在售': 17, '待整理': 36, '(空)': 29})
        eq('T4 kind 分布（试卷1条降级为其他）',
           dict(conn.execute("SELECT kind, COUNT(*) FROM artifact WHERE source_line='punch-console 吃库' "
                             "GROUP BY 1").fetchall()),
           {'打卡册': 41, '专项卷': 40, '其他': 1})
        eq('T4 有网盘链接的册 = 31',
           conn.execute("SELECT COUNT(*) FROM artifact WHERE source_line='punch-console 吃库' "
                        "AND link IS NOT NULL").fetchone()[0], 31)
        eq('T4 material 账号分布 A31/B18',
           dict(conn.execute('SELECT account, COUNT(*) FROM material GROUP BY 1').fetchall()),
           {'A': 31, 'B': 18})
        eq('T4 material 全部挂到真 artifact 上',
           conn.execute('SELECT COUNT(*) FROM material m JOIN artifact a ON a.id=m.artifact_id').fetchone()[0], 49)
        eq('T4 artifact_member 两端全是吃进来的册',
           conn.execute("SELECT COUNT(*) FROM artifact_member m JOIN artifact p ON p.id=m.parent_id "
                        "JOIN artifact c ON c.id=m.member_id").fetchone()[0], 24)
        eq('T4 合刊父册 = 3 本', conn.execute(
            'SELECT COUNT(DISTINCT parent_id) FROM artifact_member').fetchone()[0], 3)
        eq('T4 punch_map 的 doc kb_id 全在 artifact 里', conn.execute(
            "SELECT COUNT(*) FROM punch_map p JOIN artifact a ON a.id=p.kb_id WHERE p.kind='doc'").fetchone()[0], 82)
        eq('T4 punch_map 的 material kb_id 全在 material 里', conn.execute(
            "SELECT COUNT(*) FROM punch_map p JOIN material m ON m.id=p.kb_id "
            "WHERE p.kind='material'").fetchone()[0], 49)
        eq('T4 id 全字符串（无整型 id）', conn.execute(
            "SELECT COUNT(*) FROM artifact WHERE typeof(id)<>'text'").fetchone()[0], 0)

        # ── T6 抽 5 条 artifact 目检 ───────────────────────────────
        print('\n—— T6 目检抽样（5 条 artifact）——')
        picks = ['1', '11', '12', '3430', '2219']              # 有链/重名册两本/试卷降级/合刊
        okall = True
        for pid in picks:
            row = conn.execute(
                'SELECT a.id,a.name,a.kind,a.status,a.sale_state,a.link,a.note,a.files_json,a.source_line '
                'FROM punch_map p JOIN artifact a ON a.id=p.kb_id WHERE p.kind=? AND p.punch_id=?',
                ('doc', pid)).fetchone()
            if not row:
                okall = False
                print(f'  🔴 punch doc {pid} 没映射出 artifact')
                continue
            note = json.loads(row[6])
            files = json.loads(row[7]) if row[7] else []
            print(f'  punch#{pid} → {row[0]}')
            print(f'     name={row[1]!r} kind={row[2]} status={row[3]} sale_state={row[4]!r}')
            print(f'     link={(row[5] or "")[:52]!r}')
            print(f'     note={json.dumps(note, ensure_ascii=False)[:160]}')
            print(f'     files({len(files)}) 首条={files[0] if files else "无"}')
            if note.get('punch_doc') != pid or row[8] != 'punch-console 吃库':
                okall = False
        check('T6 抽样 5 条字段齐、note.punch_doc 回指正确', okall)

        # ── T7 落位路径闸 ─────────────────────────────────────────
        allrel = []
        for (fj,) in conn.execute("SELECT files_json FROM artifact WHERE files_json IS NOT NULL "
                                  "AND source_line='punch-console 吃库'"):
            allrel += json.loads(fj)
        bad = [r for r in allrel if r.startswith('/') or '\\' in r or re.match(r'^[A-Za-z]:', r)
               or '..' in r.split('/') or not r.startswith('产物/历史打卡/')]
        eq('T7 files_json 落位路径全相对/正斜杠/在 产物/历史打卡 下', bad[:3], [])
        eq('T7 files_json 落位路径总数 = 735', len(allrel), 735)
        eq('T7 落位路径互不覆盖（全唯一）', len(set(allrel)), 735)
        pm = [r[0] for r in conn.execute("SELECT kb_id FROM punch_map WHERE kind='asset'")]
        eq('T7 punch_map.asset 的 kb_id 与 files_json 是同一批路径', sorted(pm), sorted(allrel))

        # ── T15 溯源键改名（源列「源文件路径」→ note 键 punch_溯源路径 + 兄弟说明键）──
        notes = [json.loads(r[0]) for r in conn.execute(
            "SELECT note FROM artifact WHERE source_line='punch-console 吃库'")]
    finally:
        conn.close()

    eq('T15 note 里彻底不见「源文件路径」这个键（老区绝对路径不许长得像指针）',
       sum(1 for n in notes if '源文件路径' in n), 0)
    eq('T15 82 册全带 punch_溯源路径', sum(1 for n in notes if 'punch_溯源路径' in n), 82)
    eq('T15 每个 punch_溯源路径 都带兄弟键「仅溯源非指针」',
       sum(1 for n in notes if n.get('punch_溯源路径_说明') == '仅溯源非指针'), 82)
    eq('T15 溯源路径确实是老区绝对路径（所以更要标死"非指针"）',
       sum(1 for n in notes if str(n.get('punch_溯源路径', '')).startswith(r'D:\workplace\ai-bkb')), 82)
    t2 = r2.read_text(encoding='utf-8')
    check('T15 运行报告人审段补了溯源路径说明',
          'punch_溯源路径' in t2 and '仅溯源非指针' in t2 and '别拿它 open()' in t2)

    snapshot = artifact_snapshot()

    # ── T5 幂等 ─────────────────────────────────────────────────────
    out2 = run_bridge('--apply')
    c2 = kb_counts()
    eq('T5 幂等：第二遍 kb 四表零新增', {k: c2[k] for k in ('artifact', 'artifact_member', 'material', 'punch_map')},
       {k: c1[k] for k in ('artifact', 'artifact_member', 'material', 'punch_map')})
    got2 = {t: (int(i), int(s)) for t, i, s in
            re.findall(r'^ {2}(\S+)\s+入库\s+(\d+)｜跳过\s+(\d+)', out2, re.M)}
    eq('T5 幂等：第二遍规划为「全跳过」', got2,
       {'doc': (0, 82), 'doc_member': (0, 24), 'material': (0, 49), 'asset': (0, 735)})
    eq('T5 幂等：artifact 内容逐字节零变更', artifact_snapshot(), snapshot)
    check('T5 幂等：第二遍增量补挂 0 册（账已齐，不该无中生有）', '增量补挂 0 册' in out2)

    # ── T8 抽样拷贝（🔴 须 --apply + 显式 --sample-dest）────────────
    run_bridge('--apply', '--copy-sample', '3', '--sample-dest', str(COPY_ROOT))
    landed = sorted(p for p in COPY_ROOT.rglob('*') if p.is_file())
    eq('T8 抽样拷贝落地 3 个文件', len(landed), 3)
    pconn = sqlite3.connect('file:' + PUNCH.as_posix() + '?mode=ro', uri=True)
    try:
        srcmap = {str(r[0]): r[1] for r in pconn.execute('SELECT id,路径 FROM asset')}
    finally:
        pconn.close()
    head = q("SELECT punch_id, kb_id FROM punch_map WHERE kind='asset' "
             "ORDER BY CAST(punch_id AS INTEGER) LIMIT 3")
    ids = [r[0] for r in head]
    rels = [r[1] for r in head]
    okall = True
    for pid, rel in zip(ids, rels):
        dst = COPY_ROOT / rel
        src = srcmap[pid]
        good = dst.exists() and dst.stat().st_size == os.path.getsize(src)
        okall &= good
        print(f'  {"✔" if good else "✘"} {rel}  {dst.stat().st_size if dst.exists() else "缺"} B '
              f'/ 源 {os.path.getsize(src)} B')
    check('T8 抽样 3 个文件字节数与源一致', okall)
    check('T8 老区源文件零改动（只读拷出）',
          all(os.path.exists(srcmap[i]) for i in ids))

    # ── T11 反例·落盘闸：缺 --apply 一律零拷贝 ──────────────────────
    DRY_DEST.mkdir(parents=True, exist_ok=True)
    rc, _o, err = run_bridge_raw('--copy-sample', '3', '--sample-dest', str(DRY_DEST))
    eq('T11 反例：缺 --apply 的 --copy-sample 被落盘闸拒收（退出码 2）', rc, 2)
    check('T11 反例：错话点名落盘闸 + 必须 --apply', '落盘闸' in err and '--apply' in err, err.strip()[:150])
    eq('T11 反例：dry-run 后 --sample-dest 目录零新文件',
       [str(p.relative_to(DRY_DEST)) for p in DRY_DEST.rglob('*') if p.is_file()], [])
    rc, _o, err = run_bridge_raw('--copy-assets', '--asset-root', str(DRY_DEST))
    eq('T11 反例：缺 --apply 的 --copy-assets 同样被拒（退出码 2）', rc, 2)
    eq('T11 反例：dry-run 后 --asset-root 目录零新文件',
       [str(p.relative_to(DRY_DEST)) for p in DRY_DEST.rglob('*') if p.is_file()], [])
    eq('T11 反例：被拒的两次 dry-run 零写库', kb_counts(), c2)

    # ── T12 反例·抽样落位闸：--copy-sample 必须显式 --sample-dest ───
    #    🔴 判据 = 跑前快照 vs 跑后对比（本轮零新增文件/目录）。
    #    旧判据是"worktree 根的 产物/历史打卡 不存在"——那是恒不恒真全看无关状态：
    #    别的产线哪天在 worktree 根落一个 产物/ 目录，这条就无辜变红，跟被测的闸一点关系没有。
    before = tree_snap(*WATCH_DIRS)
    rc, _o, err = run_bridge_raw('--apply', '--copy-sample', '3')
    eq('T12 反例：--copy-sample 缺 --sample-dest 必炸（退出码 2）', rc, 2)
    check('T12 反例：错话点名 --sample-dest', '--sample-dest' in err, err.strip()[:150])
    rc, _o, err = run_bridge_raw('--apply', '--sample-dest', str(DRY_DEST))
    eq('T12 反例：--sample-dest 空放（没配 --copy-sample）也炸', rc, 2)
    after = tree_snap(*WATCH_DIRS)
    eq('T12 反例：两次被拒之后，worktree 根监视区零新增文件/目录（跑前快照 vs 跑后对比）',
       {k: v for k, v in after.items() if v != before[k]}, {})
    shutil.rmtree(DRY_DEST)                            # 测试自建的东西，测完自己收拾
    check('T12 测试自建的 --sample-dest 反例目录已清理', not DRY_DEST.exists(), str(DRY_DEST))

    # ── T13 反例·词表探测闸：CHECK 被剥掉必须硬炸，不许兜底降级 ─────
    check('T13 反例造具：artifact.kind 的 CHECK 已从副本剥掉', make_novocab_kb(), str(NOVOCAB_KB))
    rc, _o, err = run_bridge_raw(kb=NOVOCAB_KB)
    eq('T13 反例：kind 词表探测失败 → 硬炸（退出码 2，不是静默降级为「其他」）', rc, 2)
    check('T13 反例：错话点名词表探测闸 + artifact.kind', '词表探测闸' in err and 'artifact.kind' in err,
          err.strip()[:200])
    check('T13 反例：错话给出人工核对命令（能直接照抄跑）',
          '人工核对' in err and 'sqlite3.connect' in err and 'sqlite_master' in err)
    eq('T13 反例：炸在词表闸上，没顺手改主沙盘 kb', kb_counts(), c2)

    # ── T14 守恒闸 G4 + 增量补挂自愈 ────────────────────────────────
    aid, fj = q("SELECT a.id,a.files_json FROM punch_map p JOIN artifact a ON a.id=p.kb_id "
                "WHERE p.kind='doc' AND a.files_json IS NOT NULL "
                "ORDER BY LENGTH(a.files_json) DESC LIMIT 1")[0]
    full = json.loads(fj)
    # ①「失联可补」：从一本已在库的册里抠掉 3 条落位——这 3 条在 punch_map 里有登记却没人指。
    #   源行还在 → --apply 就能补回来 → dry-run 审计划态：报「将补挂 3 条」，**不炸**。
    set_files(aid, full[:2] + full[5:])
    rc, out14a, err = run_bridge_raw()
    eq('T14 ①失联可补：dry-run 不炸（退出码 0）——那是待办不是坏账', rc, 0)
    check('T14 ①失联可补：dry-run 预告「将补挂 3 条」', '将补挂 3 条' in out14a,
          '；'.join(l for l in out14a.splitlines() if '补挂' in l))
    check('T14 ①失联可补：dry-run 的 G4 自报审的是计划态', '（计划态）' in out14a)
    eq('T14 ①失联可补：dry-run 没偷偷补挂（库里仍缺 3 条）', len(files_of(aid)), len(full) - 3)

    out14 = run_bridge('--apply')
    check('T14 --apply 增量补挂 1 册（跳过册也补账）', '增量补挂 1 册' in out14,
          '；'.join(l for l in out14.splitlines() if '增量补挂' in l))
    eq('T14 补挂后 files_json 与失联前是同一批落位', sorted(files_of(aid)), sorted(full))
    t2b = r2.read_text(encoding='utf-8')
    check('T14 运行报告单列「增量补挂 1 册」小节', '## 增量补挂 1 册' in t2b)
    check('T14 补挂后守恒闸 G4 复绿（apply 审的是库态）',
          '守恒闸 G4：punch_map 资产 735 ≡ files_json 735 ✅（库态）' in out14)
    eq('T14 补挂只动 files_json，四表行数一根不变', kb_counts(), c2)

    # ②「幽灵」：files_json 里塞一条没在 punch_map 登记的落位——桥不许静默替人删，必须炸
    ghost = '产物/历史打卡/幽灵册/幽灵.png'
    set_files(aid, files_of(aid) + [ghost])
    rc, _o, err = run_bridge_raw('--apply')
    eq('T14 ②幽灵：--apply 照炸（退出码 2）', rc, 2)
    check('T14 ②幽灵：错话点名幽灵条数与首条', '幽灵 1 条' in err and ghost in err, err.strip()[:220])
    check('T14 ②幽灵：桥没静默替人删掉幽灵条目（归人工核对）', ghost in files_of(aid))
    set_files(aid, [x for x in files_of(aid) if x != ghost])       # 收拾现场，回到全绿态
    out14c = run_bridge('--apply')
    check('T14 现场收拾后守恒闸 G4 全绿', '≡ files_json 735 ✅' in out14c)

    # ── T16 反例·落位正本闸：源库改名/加同名副册都不许挪动已吃册的落位 ──
    #    这是 adv2 / adv3c 两条对抗手法的合体。修复前：落位跟着现算的册目录漂移，
    #    漂出来的新路径谁都没登记 → 一挂进 files_json 就是 46 条幽灵，--apply 当场落坏账。
    shutil.copy2(KB, DRIFT_KB)
    a_pid, a_name, b_pid, b_new, new_asset_pid = make_drift_punch()
    a_art, b_art = art_of_doc(a_pid, DRIFT_KB), art_of_doc(b_pid, DRIFT_KB)
    a_files0, b_files0 = files_of(a_art, DRIFT_KB), files_of(b_art, DRIFT_KB)
    a_dirs0 = {x.split('/')[2] for x in a_files0}
    print(f'\n—— T16 造具：A 册 punch#{a_pid}「{a_name}」{len(a_files0)} 条落位（登记目录 {sorted(a_dirs0)}）；'
          f'源库给它加了本同名副册 + 一条新资产 punch#{new_asset_pid}；'
          f'B 册 punch#{b_pid} 改名成「{b_new}」')

    rc, out16a, err16a = run_bridge_raw(kb=DRIFT_KB, punch=DRIFT_PUNCH)
    eq('T16 改名+同名副册后 dry-run 不炸（退出码 0）', rc, 0)
    check('T16 dry-run 自报「落位正本…不重算」并数出漂移条数', '落位正本' in out16a and '不挪窝' in out16a,
          '；'.join(l for l in out16a.splitlines() if '落位正本' in l))
    check('T16 dry-run 预告只补挂 1 条（新资产），不是整册重挂', '将补挂 1 条' in out16a,
          '；'.join(l for l in out16a.splitlines() if '补挂' in l))

    rc, out16, err16 = run_bridge_raw('--apply', kb=DRIFT_KB, punch=DRIFT_PUNCH)
    eq('T16 --apply 复吃不炸（退出码 0）', rc, 0)
    pm16, fj16 = all_landing(DRIFT_KB)
    eq('T16 零幽灵（files_json 里没有一条没登记的落位）', sorted(fj16 - pm16), [])
    eq('T16 零失联（登记了的落位条条有册指着）', sorted(pm16 - fj16), [])
    eq('T16 落位总数 = 735 + 1 条新资产', len(pm16), 736)
    a_files1 = files_of(a_art, DRIFT_KB)
    add = [x for x in a_files1 if x not in a_files0]
    eq('T16 A 册只多了 1 条落位（老落位一条没动）', len(a_files1) - len(a_files0), 1)
    eq('T16 老落位原样保留', a_files1[:len(a_files0)], a_files0)
    eq('T16 新增资产落进该册**既有登记目录**（不是现算出来的 `名称·版本名`）',
       [x.split('/')[2] for x in add], [sorted(a_dirs0)[0]])
    eq('T16 B 册（被改名的那本）落位一条没动', files_of(b_art, DRIFT_KB), b_files0)
    eq('T16 全库落位里没有一条带「（改名）」或「·副册」的漂移路径',
       sorted(x for x in pm16 | fj16 if '（改名）' in x or '·副册' in x), [])
    check('T16 G4 收尾绿（库态 736 ≡ 736）',
          '守恒闸 G4：punch_map 资产 736 ≡ files_json 736 ✅（库态）' in out16)
    t16 = r2.read_text(encoding='utf-8')
    check('T16 人审清单点名「落位正本登记在…不重算」（漂移不静默）',
          '落位正本登记在' in t16 and '造死指针' in t16)
    rc, out16b, _e = run_bridge_raw('--apply', kb=DRIFT_KB, punch=DRIFT_PUNCH)
    eq('T16 再复吃一遍仍绿（退出码 0）', rc, 0)
    check('T16 再复吃增量补挂 0 册（幂等，不无中生有）', '增量补挂 0 册' in out16b)

    # ── T17 反例·G4 语义分层：同一份坏账，能补的绿、补不掉的红 ─────────
    #    A/B 对照跑在**同一个 kb 副本**上，只换源库，把"审计划态"这件事钉死。
    shutil.copy2(KB, LESS_KB)
    victim_pid, victim_rel = q("SELECT punch_id, kb_id FROM punch_map WHERE kind='asset' "
                               "ORDER BY CAST(punch_id AS INTEGER) LIMIT 1", (), LESS_KB)[0]
    owner = q("SELECT a.id FROM artifact a WHERE a.files_json LIKE ?",
              ('%' + victim_rel + '%',), LESS_KB)[0][0]
    set_files(owner, [x for x in files_of(owner, LESS_KB) if x != victim_rel], LESS_KB)
    rc, out17a, _e = run_bridge_raw(kb=LESS_KB)
    eq('T17 ①源行还在 → dry-run 绿（--apply 补得回来）', rc, 0)
    check('T17 ①绿的同时预告「将补挂 1 条」（不是闷声放行）', '将补挂 1 条' in out17a,
          '；'.join(l for l in out17a.splitlines() if '补挂' in l))
    shutil.copy2(PUNCH, LESS_PUNCH)
    conn = sqlite3.connect(str(LESS_PUNCH))
    conn.execute('DELETE FROM asset WHERE id=?', (victim_pid,))
    conn.commit()
    conn.close()
    rc, _o, err17 = run_bridge_raw(kb=LESS_KB, punch=LESS_PUNCH)
    eq('T17 ②源行没了 → 同一份坏账 dry-run 就红（退出码 2）', rc, 2)
    check('T17 ②错话说明审的是计划态、且 --apply 也补不掉',
          '计划态' in err17 and '补不掉' in err17 and victim_rel in err17, err17.strip()[:240])
    eq('T17 ②dry-run 红也没写库（files_json 仍缺那一条）',
       victim_rel in files_of(owner, LESS_KB), False)
    shutil.copy2(KB, GHOST_KB)
    gaid = q("SELECT a.id FROM punch_map p JOIN artifact a ON a.id=p.kb_id "
             "WHERE p.kind='doc' AND a.files_json IS NOT NULL LIMIT 1", (), GHOST_KB)[0][0]
    set_files(gaid, files_of(gaid, GHOST_KB) + [ghost], GHOST_KB)
    rc, _o, err17b = run_bridge_raw(kb=GHOST_KB)
    eq('T17 ③幽灵 → dry-run 就红（坏账在写库之前红，不等 --apply）', rc, 2)
    check('T17 ③错话点名幽灵那条路径', '幽灵 1 条' in err17b and ghost in err17b, err17b.strip()[:200])

    # ── T18 反例·拷贝失败闸 + 盘账闸 G5 ─────────────────────────────
    #    ① 照 adv4 手法：把一个落位先用目录占着 → copy2 落不下去 → 必须 exit 2 且点名那条路径
    victim_rel3 = rels[0]
    (FAIL_DEST / victim_rel3).mkdir(parents=True, exist_ok=True)
    rc, _o, err18 = run_bridge_raw('--apply', '--copy-sample', '3', '--sample-dest', str(FAIL_DEST))
    eq('T18 ①占位一个落位 → 拷贝失败闸炸（退出码 2，不是"记一笔然后 exit 0"）', rc, 2)
    check('T18 ①错话点名拷贝失败闸与那条落位', '拷贝失败闸' in err18 and victim_rel3 in err18,
          err18.strip()[:220])
    eq('T18 ①另外 2 条照样落到位（闸只拦收场，不回滚已落文件）',
       sum(1 for r in rels[1:] if (FAIL_DEST / r).is_file()), 2)

    #    ② 盘账闸 G5：迷你库全量搬一遍（几百 KB）→ 绿；再让一条落位在盘上消失 → 必须红。
    #       这条是 G4 抓不到的：账对账两边都在，只是盘上没文件（死指针）。
    small = [r[0] for r in q('SELECT doc_id FROM asset GROUP BY 1 '
                             'ORDER BY COUNT(*) ASC, doc_id ASC LIMIT 4', (), PUNCH)]
    n_asset = make_mini_punch(MINI_PUNCH, small)
    shutil.copy2(PRISTINE_KB, MINI_KB)
    rc, out18b, err18b = run_bridge_raw('--apply', '--copy-assets', '--asset-root', str(MINI_DEST),
                                        kb=MINI_KB, punch=MINI_PUNCH)
    eq('T18 ②迷你库全量 --copy-assets 一次过（退出码 0）', rc, 0)
    eq('T18 ②文件真落地', sum(1 for p in MINI_DEST.rglob('*') if p.is_file()), n_asset)
    check(f'T18 ②盘账闸 G5 绿：{n_asset} 条落位指针逐条 is_file() 验真',
          f'盘账闸 G5：{n_asset} 条落位指针逐条 is_file() 验真 ✅' in out18b,
          '；'.join(l for l in out18b.splitlines() if 'G5' in l))
    gone_pid, gone_rel = q("SELECT punch_id, kb_id FROM punch_map WHERE kind='asset' "
                           "ORDER BY CAST(punch_id AS INTEGER) DESC LIMIT 1", (), MINI_KB)[0]
    shutil.copy2(MINI_PUNCH, MINI_PUNCH2)
    conn = sqlite3.connect(str(MINI_PUNCH2))
    conn.execute('DELETE FROM asset WHERE id=?', (gone_pid,))
    conn.commit()
    conn.close()
    (MINI_DEST / gone_rel).unlink()                    # 盘上的文件被人删了，两本账都还在
    rc, out18c, err18c = run_bridge_raw('--apply', '--copy-assets', '--asset-root', str(MINI_DEST),
                                        kb=MINI_KB, punch=MINI_PUNCH2)
    eq('T18 ②账对账仍齐、但盘上少一个文件 → G5 炸（退出码 2）', rc, 2)
    check('T18 ②错话点名盘账闸 G5 与那条落位', '盘账闸 G5' in err18c and gone_rel in err18c,
          err18c.strip()[:240])
    t18 = r2.read_text(encoding='utf-8')
    g4_sec = section(t18, '## 守恒闸 G4')
    g5_sec = section(t18, '## 盘账闸 G5')
    check('T18 ②同一份报告里 G4 绿、G5 红——证明 G5 抓的正是 G4 抓不到的那类死指针',
          '✅ 两边对齐。' in g4_sec and '失联（进了 punch_map 却没人指）：**0** 条' in g4_sec
          and gone_rel in g5_sec, g4_sec.strip().splitlines()[-1][:80])
    check('T18 ②运行报告单列 G5 小节并列出缺的那条', '## 盘账闸 G5' in t18 and gone_rel in g5_sec)

    # ── T19 反例·「已登记即该挂」：源文件事后没了也不撤指针 ─────────────
    #    钉的是 want 里 `or a['locked']` 那半边。摘掉它，这 3 条就永远补不回 files_json：
    #    punch_map 有登记、没人指 → G4 当场失联，而且是**加 --apply 也补不掉**的那种红。
    shutil.copy2(KB, T19_KB)
    shutil.copy2(PUNCH, T19_PUNCH)
    aid19, fj19 = q("SELECT a.id,a.files_json FROM punch_map p JOIN artifact a ON a.id=p.kb_id "
                    "WHERE p.kind='doc' AND a.files_json IS NOT NULL "
                    "ORDER BY LENGTH(a.files_json) DESC LIMIT 1", (), T19_KB)[0]
    full19 = json.loads(fj19)
    lost19 = full19[2:5]                               # 被抠掉的 3 条（登记在案）
    set_files(aid19, full19[:2] + full19[5:], T19_KB)
    lost_pids = [q("SELECT punch_id FROM punch_map WHERE kind='asset' AND kb_id=?",
                   (r,), T19_KB)[0][0] for r in lost19]
    conn = sqlite3.connect(str(T19_PUNCH))
    try:                                               # 这 3 条的源文件从老区磁盘上消失
        for i, pid in enumerate(lost_pids):
            conn.execute('UPDATE asset SET 路径=? WHERE id=?',
                         (r'D:\workplace\ai-bkb\_源文件已被删_%d.png' % i, pid))
        conn.commit()
    finally:
        conn.close()
    print(f'\n—— T19 造具：册 {aid19} 的 {len(full19)} 条落位被抠掉 3 条，'
          f'且这 3 条（punch asset {lost_pids}）的源文件已不在盘上')
    rc, out19a, err19a = run_bridge_raw(kb=T19_KB, punch=T19_PUNCH)
    eq('T19 失联 3 条 + 源文件已没了：dry-run 仍绿（登记即正本，补得回来）', rc, 0)
    check('T19 dry-run 预告「将补挂 3 条」', '将补挂 3 条' in out19a,
          '；'.join(l for l in out19a.splitlines() if '补挂' in l))
    rc, out19b, err19b = run_bridge_raw('--apply', kb=T19_KB, punch=T19_PUNCH)
    eq('T19 --apply 也绿（退出码 0）', rc, 0)
    eq(f'T19 补齐回 {len(full19)} 条落位（源文件没了照样不撤指针——撤了就是自造失联）',
       sorted(files_of(aid19, T19_KB)), sorted(full19))
    eq('T19 那 3 条源文件已消失的落位，一条不少地挂了回来',
       sorted(x for x in files_of(aid19, T19_KB) if x in lost19), sorted(lost19))
    check('T19 --apply 收尾 G4 库态复绿', '≡ files_json 735 ✅（库态）' in out19b)

    # ── T20 反例·apply 收尾审的是**库态**（把补挂 UPDATE 摘掉注入桥副本）──
    shutil.copy2(KB, T20_KB)
    aid20, fj20 = q("SELECT a.id,a.files_json FROM punch_map p JOIN artifact a ON a.id=p.kb_id "
                    "WHERE p.kind='doc' AND a.files_json IS NOT NULL "
                    "ORDER BY LENGTH(a.files_json) DESC LIMIT 1", (), T20_KB)[0]
    full20 = json.loads(fj20)
    set_files(aid20, full20[:2] + full20[5:], T20_KB)
    src_bridge = BRIDGE.read_text(encoding='utf-8')
    leak, n_cut = re.subn(
        r"\n(\s*)kconn\.execute\('UPDATE artifact SET files_json=\? WHERE id=\?',\n"
        r"\s*\(json\.dumps\(d\['incr_files'\][^\n]*\n",
        "\n\\1pass  # 注入漏刀：补挂 UPDATE 被摘掉\n", src_bridge, count=1)
    eq('T20 反例造具：在桥副本里定位并摘掉补挂 UPDATE 这一刀（摘中 1 处）', n_cut, 1)
    LEAK_BRIDGE.write_text(leak, encoding='utf-8')
    rc, out20a, err20 = run_bridge_raw('--apply', kb=T20_KB, script=LEAK_BRIDGE)
    eq('T20 反例：补挂 UPDATE 漏刀 → --apply 收尾必炸（退出码 2）', rc, 2)
    check('T20 反例：错话点名守恒闸 G4 且自报**审的是库态**（收尾量的是库，不是计划）',
          '守恒闸 G4 失守' in err20 and '审的是库态' in err20, err20.strip()[:200])
    check('T20 反例：报告 G4 段也自报库态、失联 3 条（播报口径不许自己现编）',
          '本次审的是 **库态**' in section(r2.read_text(encoding='utf-8'), '## 守恒闸 G4')
          and '失联（进了 punch_map 却没人指）：**3** 条' in
              section(r2.read_text(encoding='utf-8'), '## 守恒闸 G4'))
    eq('T20 反例：漏刀跑完 files_json 确实没被补（证明摘的正是那一刀）',
       len(files_of(aid20, T20_KB)), len(full20) - 3)
    rc, out20b, _e = run_bridge_raw('--apply', kb=T20_KB)
    eq('T20 正例对照：换回真桥，同一份坏账当场补挂修好（退出码 0）', rc, 0)
    eq('T20 正例对照：3 条补齐', sorted(files_of(aid20, T20_KB)), sorted(full20))

    #    🔴 收尾播报的口径标签必须取 audit['scope'] 本身，不许按 args.apply 现编。
    #    这条只能用**静态闸**钉（同 T9 那类），原因是摘除演练实测出来的：
    #    只把标签换回现编、而被审对象没漂时，全量自证一条都不红（现编的恰好与真尺一致）；
    #    价值全在"将来漂了才现形"——同一次演练里把被审对象也改漂（多一条分支就够），
    #    取 audit['scope'] 的版本 6 条红（T14/T16/T19 的「库态」断言当场翻脸），
    #    现编标签的版本只剩 3 条红：那 3 条一边印着「库态」一边审的是计划态，全绿地说谎。
    lines20 = src_bridge.splitlines()
    i20 = next((i for i, l in enumerate(lines20) if '守恒闸 G4：punch_map 资产' in l), -1)
    blk20 = '\n'.join(lines20[i20:i20 + 2]) if i20 >= 0 else ''
    check('T20 静态闸：G4 收尾播报的标签取 audit["scope"]，不按 args.apply 现编',
          'audit["scope"]' in blk20 and 'args.apply' not in blk20, blk20.strip()[:160])

    #    顺带钉 anchor 定序/众数的可复现性——直调纯函数，判据不经库不经盘
    eq('T20 anchor 定序：条数降序 + 同数按目录名升序（不看 dict 插入序）',
       BS.anchor_order({'ZZZ目录': 2, 'AAA目录': 2, 'MMM目录': 3}),
       [('MMM目录', 3), ('AAA目录', 2), ('ZZZ目录', 2)])
    eq('T20 anchor 众数：3 票的目录压过 2 票的', BS.anchor_dir({'少数派': 2, '多数派': 3}), '多数派')
    eq('T20 anchor 一条登记都没有 → None（回落现算目录）', BS.anchor_dir({}), None)

    def anchor_case(rows, locked, bookdirs):
        return {p['punch_id']: p['bookdir']
                for p in BS.plan_assets({'asset': rows}, bookdirs, locked)}

    mode_rows = [{'id': 1, 'doc_id': 7, '路径': r'D:\老区\a.png', '类型': '图'},
                 {'id': 2, 'doc_id': 7, '路径': r'D:\老区\b.png', '类型': '图'},
                 {'id': 3, 'doc_id': 7, '路径': r'D:\老区\c.png', '类型': '图'},
                 {'id': 4, 'doc_id': 7, '路径': r'D:\老区\d.png', '类型': '图'}]
    mode_locked = {'1': '产物/历史打卡/外册目录/a.png',      # 🔴 最小 punch_id 偏偏是那条外册的
                   '2': '产物/历史打卡/本册目录/b.png',
                   '3': '产物/历史打卡/本册目录/c.png'}
    got_mode = anchor_case(mode_rows, mode_locked, {7: '现算目录'})
    eq('T20 anchor 众数生效：新资产落「本册目录」（旧的最小 id 取法会落「外册目录」）',
       got_mode['4'], '本册目录')
    tie_rows = [{'id': 10, 'doc_id': 8, '路径': r'D:\老区\x.png', '类型': '图'},
                {'id': 11, 'doc_id': 8, '路径': r'D:\老区\y.png', '类型': '图'},
                {'id': 12, 'doc_id': 8, '路径': r'D:\老区\z.png', '类型': '图'}]
    tie_locked = {'10': '产物/历史打卡/ZZZ目录/x.png',       # 插入序 ZZZ 在前，票数 1:1 打平
                  '11': '产物/历史打卡/AAA目录/y.png'}
    got_tie = anchor_case(tie_rows, tie_locked, {8: '现算目录'})
    eq('T20 anchor 并列定序：1:1 打平取目录名升序的 AAA（无 key 的 max 会取插入序的 ZZZ）',
       got_tie['12'], 'AAA目录')
    eq('T20 anchor 可复现：同一份输入连算 5 遍结果一模一样',
       len({json.dumps(anchor_case(tie_rows, tie_locked, {8: '现算目录'}), ensure_ascii=False)
            for _ in range(5)}), 1)

    # ── T21 反例·盘→账闸 G6：拒收册不许落盘 + 无账文件当场红 ────────────
    small21 = [r[0] for r in q('SELECT doc_id FROM asset GROUP BY 1 '
                               'ORDER BY COUNT(*) ASC, doc_id ASC LIMIT 4', (), PUNCH)]
    n21 = make_mini_punch(T21_PUNCH, small21)
    conn = sqlite3.connect(str(T21_PUNCH))
    try:
        rej_doc = conn.execute('SELECT doc_id FROM asset GROUP BY 1 '
                               'ORDER BY COUNT(*) DESC LIMIT 1').fetchone()[0]
        rej_name = conn.execute('SELECT 名称 FROM doc WHERE id=?', (rej_doc,)).fetchone()[0]
        n_rej = conn.execute('SELECT COUNT(*) FROM asset WHERE doc_id=?', (rej_doc,)).fetchone()[0]
        conn.execute('UPDATE doc SET 类型=? WHERE id=?', ('未登记型', rej_doc))   # → 类型无映射 → 拒收
        conn.commit()
    finally:
        conn.close()
    shutil.copy2(PRISTINE_KB, T21_KB)
    print(f'\n—— T21 造具：迷你库 {n21} 条资产，其中册「{rej_name}」（{n_rej} 条资产）'
          f'类型改成「未登记型」→ 必拒收；它的资产源文件全在盘上（`exists` 一律为真）')
    rc, out21, err21 = run_bridge_raw('--apply', '--copy-assets', '--asset-root', str(G6_DEST),
                                      kb=T21_KB, punch=T21_PUNCH)
    eq('T21 拒收册在场时全量搬运照样绿（退出码 0）', rc, 0)
    eq(f'T21 拒收册「{rej_name}」的 {n_rej} 个资产一个都没落盘（只筛 exists 会全拷下去）',
       len(landed_rels(G6_DEST)), n21 - n_rej)
    eq('T21 盘上文件 ≡ punch_map 登记（一个无账孤儿都没有）',
       landed_rels(G6_DEST),
       sorted(r[0] for r in q("SELECT kb_id FROM punch_map WHERE kind='asset'", (), T21_KB)))
    check('T21 拒收册的落位册目录压根没被创建',
          not (G6_DEST / '产物' / '历史打卡' / BS.sanitize(rej_name)).exists(),
          str(G6_DEST / '产物' / '历史打卡' / BS.sanitize(rej_name)))
    check(f'T21 G6 绿：落位根下 {n21 - n_rej} 个实际文件逐个反查 punch_map',
          f'盘→账闸 G6：落位根下 {n21 - n_rej} 个实际文件逐个反查 punch_map ✅' in out21,
          '；'.join(l for l in out21.splitlines() if 'G6' in l))
    orphan_rel = '产物/历史打卡/无账册/无账落位.png'
    (G6_DEST / orphan_rel).parent.mkdir(parents=True, exist_ok=True)
    (G6_DEST / orphan_rel).write_bytes(b'\x89PNG\r\nno-ledger-orphan')
    rc, out21b, err21b = run_bridge_raw('--apply', '--copy-assets', '--asset-root', str(G6_DEST),
                                        kb=T21_KB, punch=T21_PUNCH)
    eq('T21 反例：手工塞一个无账文件 → G6 炸（退出码 2）', rc, 2)
    check('T21 反例：错话点名盘→账闸 G6 与那个无账文件',
          '盘→账闸 G6' in err21b and orphan_rel in err21b, err21b.strip()[:240])
    t21 = r2.read_text(encoding='utf-8')
    check('T21 反例：同一份报告里 G4 绿、G5 绿、G6 红——G6 抓的正是 G5 反方向那类',
          '✅ 两边对齐。' in section(t21, '## 守恒闸 G4')
          and '✅ 每一条落位指针在盘上都是真文件。' in section(t21, '## 盘账闸 G5')
          and orphan_rel in section(t21, '## 盘→账闸 G6'))
    check('T21 反例：预检报告的拷贝清单标出了「拒收」判定（人看得见谁没被搬）',
          '| 判定 |' in (REPORT_DIR / '预检-资产PDF.md').read_text(encoding='utf-8')
          and '| 拒收 |' in (REPORT_DIR / '预检-资产PDF.md').read_text(encoding='utf-8'))

    # ── T22 反例·anchor 众数：一条被改挂过来的外册资产不许把整册带歪 ────
    shutil.copy2(KB, T22_KB)
    shutil.copy2(PUNCH, T22_PUNCH)
    conn = sqlite3.connect(str(T22_PUNCH))
    conn.row_factory = sqlite3.Row
    try:
        alien = dict(conn.execute('SELECT * FROM asset ORDER BY CAST(id AS INTEGER) LIMIT 1').fetchone())
        # 收方册：资产最多、且自己的资产 id 全部大于 alien —— 这样旧的「最小 id 取法」必被带歪
        host = conn.execute(
            'SELECT doc_id, COUNT(*) c, MIN(CAST(id AS INTEGER)) mn FROM asset GROUP BY 1 '
            'HAVING mn>? ORDER BY c DESC LIMIT 1', (int(alien['id']),)).fetchone()
        host_id, host_n, host_min = host['doc_id'], host['c'], host['mn']
        conn.execute('UPDATE asset SET doc_id=? WHERE id=?', (host_id, alien['id']))  # 改挂到收方册
        shutil.copy2(alien['路径'], T22_ASSET)                                        # 再加一条新资产
        acols = [k for k in alien if k != 'id']
        row = dict(alien, doc_id=host_id, 路径=str(T22_ASSET))
        new22 = conn.execute('SELECT MAX(id)+1 FROM asset').fetchone()[0]
        conn.execute('INSERT INTO asset(id,{}) VALUES(?,{})'.format(
            ','.join('"%s"' % k for k in acols), ','.join('?' * len(acols))),
            [new22] + [row[k] for k in acols])
        conn.commit()
    finally:
        conn.close()
    host_art = art_of_doc(host_id, T22_KB)
    host_files0 = files_of(host_art, T22_KB)
    host_dir = host_files0[0].split('/')[2]
    alien_rel = q("SELECT kb_id FROM punch_map WHERE kind='asset' AND punch_id=?",
                  (str(alien['id']),), T22_KB)[0][0]
    alien_dir = alien_rel.split('/')[2]
    print(f'—— T22 造具：把 punch asset#{alien["id"]}（登记在 `{alien_dir}` 下）改挂到收方册 '
          f'punch#{host_id}（{host_n} 条资产、登记目录 `{host_dir}`），再给收方册加 1 条新资产')
    check('T22 造具前提：被改挂那条的 id 比收方册所有资产都小（旧最小 id 取法必被它带歪）',
          int(alien['id']) < int(host_min), f'alien id={alien["id"]} < 收方册最小 id={host_min}')
    rc, out22, err22 = run_bridge_raw('--apply', kb=T22_KB, punch=T22_PUNCH)
    eq('T22 改挂外册资产后复吃不炸（退出码 0）', rc, 0)
    pm22, fj22 = all_landing(T22_KB)
    eq('T22 零幽灵', sorted(fj22 - pm22), [])
    eq('T22 零失联', sorted(pm22 - fj22), [])
    add22 = [x for x in files_of(host_art, T22_KB) if x not in host_files0]
    eq('T22 收方册净增 2 条（被改挂过来的老落位 + 1 条新资产）', len(add22), 2)
    eq('T22 新资产落进**众数目录**（不是被那一条外册资产带歪到外册目录）',
       [x for x in add22 if x.endswith(T22_ASSET.name)],
       [f'产物/历史打卡/{host_dir}/{T22_ASSET.name}'])
    check('T22 被改挂那条的老落位一个字没动（登记即正本）', alien_rel in files_of(host_art, T22_KB))
    eq('T22 老落位一条没挪窝', files_of(host_art, T22_KB)[:len(host_files0)], host_files0)
    t22 = r2.read_text(encoding='utf-8')
    rev22 = section(t22, '## 人审清单')
    check('T22 人审单开「跨 N 个册目录」事由并点名各目录各多少条',
          '已登记落位跨 2 个册目录' in rev22
          and f'`{host_dir}`×{host_n}' in rev22 and f'`{alien_dir}`×1' in rev22,
          '；'.join(l[:150] for l in rev22.splitlines() if '跨 2 个册目录' in l))
    check('T22 跨目录事由没复用「源册名已变」话术（改挂≠改名，两码事）',
          '源册名/重名格局已变' not in rev22)

    # ── T23 反例·孤儿资产守恒闸（开局就红，不是裸 KeyError rc=1 零报告）──
    shutil.copy2(PRISTINE_KB, T23_KB)
    shutil.copy2(PUNCH, T23_PUNCH)
    conn = sqlite3.connect(str(T23_PUNCH))
    try:
        orph_pid = conn.execute('SELECT MIN(id) FROM asset').fetchone()[0]
        conn.execute('UPDATE asset SET doc_id=? WHERE id=?', (999999, orph_pid))
        conn.commit()
    finally:
        conn.close()
    rc, out23, err23 = run_bridge_raw(kb=T23_KB, punch=T23_PUNCH)
    eq('T23 反例：孤儿资产（doc_id 查无此册）→ 硬炸（退出码 2）', rc, 2)
    check('T23 反例：错话点名孤儿 asset id 与它那个查无此册的 doc_id',
          '孤儿资产守恒闸' in err23 and f'asset#{orph_pid}→doc#999999' in err23, err23.strip()[:220])
    check('T23 反例：死法是闸不是崩（stderr 里没有 Traceback / KeyError）',
          'Traceback' not in err23 and 'KeyError' not in err23, err23.strip()[:120])
    eq('T23 反例：炸在开局守恒闸上，没顺手改 kb', kb_counts(T23_KB), kb_counts(PRISTINE_KB))

    # ── T9 零 LLM 静态闸 ────────────────────────────────────────────
    src = BRIDGE.read_text(encoding='utf-8')
    banned = [w for w in ('openai', 'anthropic', 'claude', 'langchain', 'transformers',
                          'requests.post', 'httpx', 'urllib.request', 'ollama', 'gpt-')
              if re.search(re.escape(w), src, re.I)]
    eq('T9 零 LLM：桥源码无任何模型/网络接口字样', banned, [])

    # ── 收尾清理：测试自建的落位目录不留（报告与副本库留作证据）──────
    for d in (FAIL_DEST, MINI_DEST, G6_DEST):
        if d.exists():
            shutil.rmtree(d)
    eq('测后清理：测试自建的落位目录已收拾',
       [d.name for d in (DRY_DEST, FAIL_DEST, MINI_DEST, G6_DEST) if d.exists()], [])

    print('\n' + '=' * 62)
    print(f'通过 {len(_pass)} 条｜失败 {len(_fail)} 条')
    if _fail:
        for f in _fail:
            print('  🔴 ' + f)
        return 1
    print('全绿 ✅')
    return 0


if __name__ == '__main__':
    sys.exit(main())
