# -*- coding: utf-8 -*-
"""A 账层桥 —— 把 punch-console 的 `资料库.db` 册子账吃进 kb.db（PRD-003 阶段1）。

🔴 三条本脚本自带的红线（是闸不是注释，违例直接抛 BridgeError 拒收）：
  1. **零 LLM**：全程机械映射（字段对位 + 格式包装 + 路径改写），无任何模型/AI 接口调用；
  2. **源库只读**：资料库.db 一律 `file:...?mode=ro` 打开，开库后立刻做写探针自证只读（G0）；
  3. **缺 --apply 一律 dry-run**：只算账、只出报告——**零写库、零拷文件**。
     落盘拷贝（`--copy-assets` / `--copy-sample`）缺 `--apply` 一律拒收（G3 落盘闸，不是"少拷一点"）；
     `--copy-sample` 还必须显式给 `--sample-dest <目录>`（抽样只准落临时目录，不许默认往 v2 根上撒）。

     🔴 dry-run 对账面的承诺（逐字，别再意会）：它审的是**计划态**
     ＝「当前库态 ＋ 本轮计划补挂/新增的投影」，不是当下的库态：
       · 加 `--apply` 就会被补挂修好的失联 → 报「将补挂 N 条」，**不炸**（那不是坏账，是待办）；
       · 计划态里仍对不上的（幽灵；或连 --apply 都补不掉的失联）→ **exit 2**，
         坏账在写库之前就红，不许"dry-run 绿灯放行、--apply 才落坏账"。
     加了 `--apply` 之后，收尾照旧审**库态**硬闸（G4），口径一个字没松。

吃四样（数字取自 2026-08-19 源库实测）：
  doc 82        → artifact（+ punch_map kind='doc'）
  doc_member 24 → artifact_member（两端 id 经 punch_map 翻译）
  material 49   → material（+ punch_map kind='material'）
  asset 735     → 存在性预检 + 拷贝清单 + files_json 落位相对路径（+ punch_map kind='asset'）

用法：
  # 只算账出报告（不写库、不拷文件）
  python bridge_shelf.py --punch 知识库/资料库.db --kb 知识库/kb.db
  # 真吃（写 kb.db；资产仍只落"清单+相对路径"，不搬文件）
  python bridge_shelf.py --punch 知识库/资料库.db --kb 知识库/kb.db --apply
  # 抽样验证拷贝函数（3 个文件真拷到显式指定的临时目录；🔴 必须 --apply + --sample-dest）
  python bridge_shelf.py --punch … --kb … --apply --copy-sample 3 --sample-dest 试验场/…/落位验证
  # 全量搬资产（735 个文件，落 --asset-root 下；🔴 留给主位实跑，本轮不对主位跑）
  python bridge_shelf.py --punch … --kb … --apply --copy-assets

幂等骨架 = punch_map：重跑时 (kind, punch_id) 已在表里的一律跳过——不重建、不覆盖，
人工在 kb 侧改过的字段（尤其 sale_state 这根人工列）绝不会被第二遍冲掉。
🔴 但"跳过"只跳行不跳账：已在库的册若又冒出新资产落位，本轮**增量补挂**它的
`artifact.files_json`（并进去不覆盖），报告单列「增量补挂 N 册」（dry-run 报「将补挂 N 条」）；
收尾拿守恒闸 G4 `files_json ≡ punch_map(kind='asset')` 自查——`--apply` 审库态、
dry-run 审计划态（见上），对不上直接 BridgeError：资产进了 punch_map 却没挂进任何 files_json
= 文件失联，不许静默带过。

🔴 落位正本制（防死指针）：落位路径一经写进 `punch_map(kind='asset')` 即为**正本**，
复吃时凡已登记的资产一律**从登记取、绝不重算**；同册新增资产的落位目录以该册既有登记的
册目录为基准，该册一条登记都没有才现算。源库后来改册名、或来了本同名副册把重名去重格局顶歪，
都不再挪动已吃册的落位——否则重算出的新路径谁都没登记，挂进 files_json 就是一条指向空气的死指针。

闸清单：G0 源库只读｜G1 目标库词表探测｜G2 相对路径｜G3 落盘须 --apply｜
G4 files_json ≡ punch_map(asset)（dry-run 审计划态 / apply 审库态）｜
G5 账→盘（仅 --copy-assets：files_json 的落位指针逐条 is_file() 验真）｜
G6 盘→账（仅 --copy-assets：落位根下的实际文件逐个反查 punch_map，多出的无账文件当场红）｜
孤儿资产守恒闸（开局：asset.doc_id 必须在 doc 表里有主）｜
拷贝失败闸（copy_assets 收尾 failed>0 直接 BridgeError，绝不"报告里记一笔然后 exit 0"）。

🔴 G5 与 G6 是**同一条边的两个方向**，少一个方向就漏一整类坏账：
  · G5 只从账走到盘（账上有、盘上没有 = 死指针）；
  · G6 从盘走回账（盘上有、账上没有 = 无账孤儿——本轮判**拒收**的册照拷下去、
    上一轮的落位改了名没清、别人手工往落位根里塞的文件，G5 全看不见）。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path, PureWindowsPath

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]          # v2 根（工具箱/桥/x.py → 上两级）

# ══════════════════════════════════════════════════════════════════════
# 映射常量（改口径改这里，别散在代码里）
# ══════════════════════════════════════════════════════════════════════
KIND_MAP = {'打卡': '打卡册', '专项': '专项卷', '试卷': '试卷'}
SOURCE_LINE = 'punch-console 吃库'
ARTIFACT_STATUS = '已交付'                           # 82 册都是已出货的历史件
ASSET_REL_ROOT = '产物/历史打卡'                     # 落位根（相对 v2 根）
ILLEGAL_FS = set('\\/:*?"<>|')                      # Windows 文件名非法字符
REPORT_SUBDIR = '记录/PRD-003吃库'

# artifact.note 里除 6 个必带键外，这些源字段非空才随行（保源不丢，不静默丢字段）
NOTE_EXTRA_FIELDS = ('科目', '年级', '考点', 'layout_key', 'day_spec', '源文件路径', '备注')
JSON_LIKE_FIELDS = ('考点',)                         # 这些源字段本身是 JSON 串，落 note 时解析成结构

# 🔴 老区绝对路径落 note 的改名规矩：源列叫「源文件路径」，落库改叫「punch_溯源路径」，
#    并强制带兄弟键说明——键名叫"源文件路径"会被后人当成文件指针去 open()，
#    而它指的是老区（D:\workplace\ai-bkb\…，只读、随时可能挪窝）。真指针只有 files_json 的相对路径。
TRACE_SRC_FIELD = '源文件路径'
TRACE_NOTE_KEY = 'punch_溯源路径'
TRACE_NOTE_MEMO_KEY = 'punch_溯源路径_说明'
TRACE_NOTE_MEMO = '仅溯源非指针'


class BridgeError(Exception):
    """桥闸违例——一律拒收，不静默降级。"""


class CopyFailed(BridgeError):
    """拷贝失败闸：带着本次的 (done, skipped, failed) 现场一起抛，报告先落地再炸。"""

    def __init__(self, msg, result):
        super().__init__(msg)
        self.result = result


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ══════════════════════════════════════════════════════════════════════
# 闸 G0　源库只读闸（不是靠"我记得加了 mode=ro"，是开完就拿写探针实测）
# ══════════════════════════════════════════════════════════════════════
def open_punch_ro(path):
    p = Path(path).resolve()
    if not p.exists():
        raise BridgeError(f'源库不存在：{p}')
    conn = sqlite3.connect('file:' + p.as_posix() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('CREATE TABLE _只读探针(x)')
    except sqlite3.OperationalError:
        return conn                                  # 探针被拒 = 真只读，闸过
    conn.close()
    raise BridgeError(f'🔴 只读闸失守：{p} 竟然可写——资料库.db 必须 mode=ro 打开，中止。')


def open_kb(path):
    p = Path(path).resolve()
    if not p.exists():
        raise BridgeError(f'kb.db 不存在：{p}')
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


# ══════════════════════════════════════════════════════════════════════
# 闸 G1　目标库词表闸——kind/sale_state 的合法集合从目标库 CHECK 现读，
#        不写死在脚本里（写死=注释谎言的温床）
#
# 🔴 探测不出词表 = 硬炸，绝不返 None 让调用方拿默认值兜底：
#    兜底会把「探测失败」伪装成「词表容不下」——kind 那条路会把 82 册整批降级成「其他」，
#    sale_state 那条路会拿脚本里的老词表去卡真库的新词表，两条都是一路绿灯的静默错账。
# ══════════════════════════════════════════════════════════════════════
def _db_file(conn):
    for _seq, name, fname in conn.execute('PRAGMA database_list'):
        if name == 'main':
            return fname or '(内存库)'
    return '(未知)'


def check_vocab(conn, table, col):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row:
        raise BridgeError(f'目标库缺表 {table}——先在主位跑 工具箱/库/apply_ddl_263.py')
    m = re.search(r'\b' + re.escape(col) + r'\b[^,]*?CHECK\s*\(\s*' + re.escape(col) +
                  r'\s+IN\s*\(([^)]*)\)', row[0], re.S)
    vocab = tuple(re.findall(r"'([^']*)'", m.group(1))) if m else ()
    if not vocab:
        db = _db_file(conn)
        probe = ("python -c \"import sqlite3,sys;sys.stdout.reconfigure(encoding='utf-8');"
                 "print(sqlite3.connect(r'{db}').execute("
                 "'SELECT sql FROM sqlite_master WHERE name=?',('{table}',)).fetchone()[0])\""
                 ).format(db=db, table=table)
        raise BridgeError(
            f'🔴 词表探测闸：{table}.{col} 没读出 CHECK 词表'
            f'（该列没装 CHECK，或 DDL 写法变了正则接不住）——桥拒绝拿默认词表兜底，'
            f'否则「探测失败」会伪装成「词表容不下」，整批静默降级还一路绿灯。\n'
            f'   人工核对（照抄跑，看 {table} 的建表 SQL 里 {col} 到底有没有 CHECK(... IN (...))）：\n'
            f'   {probe}\n'
            f'   缺 CHECK → 到主位跑 工具箱/库/apply_ddl_263.py 补齐 DDL；'
            f'DDL 写法变了 → 改本函数正则（公共契约件，归主位定），改完再吃。')
    return vocab


def assert_tables(conn, tables):
    have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    miss = [t for t in tables if t not in have]
    if miss:
        raise BridgeError(f'目标库缺表 {miss}——先在主位跑 工具箱/库/apply_ddl_263.py（§2.6c DDL）')
    cols = {r[1] for r in conn.execute('PRAGMA table_info(artifact)')}
    if 'sale_state' not in cols:
        raise BridgeError('artifact 缺 sale_state 列——先在主位跑 apply_ddl_263.py 补列')


# ══════════════════════════════════════════════════════════════════════
# id 铸法（照抄 工具箱/挂账/artifact_tool.py：前缀 + 8 位日期 + 6 位 hex）
# 差别只有一处：hex 由源 id 决定性哈希得来，不用 uuid4——桥要可复现，
# 同一条 punch 行在 punch_map 写下之前重跑也铸出同一个 id。
# 🔴 id 全链路字符串（雪花 double 截尾血案）。
# ══════════════════════════════════════════════════════════════════════
def mint_id(prefix, seed, taken):
    day = datetime.now().strftime('%Y%m%d')
    h = hashlib.md5(seed.encode('utf-8')).hexdigest()
    for off in range(0, 26):
        cand = f'{prefix}{day}{h[off:off + 6]}'
        if cand not in taken:
            taken.add(cand)
            return cand
    raise BridgeError(f'id 铸造闸：{seed} 连撞 26 次，人工介入')


# ══════════════════════════════════════════════════════════════════════
# 闸 G2　相对路径闸（老货架 717 行绝对路径全断的复发防护）
# ══════════════════════════════════════════════════════════════════════
def assert_rel(rel):
    if not rel:
        raise BridgeError('空路径')
    if re.match(r'^[A-Za-z]:', rel) or rel.startswith('/') or rel.startswith('\\'):
        raise BridgeError(f'🔴 文件指针必须相对 v2 根，拿到绝对路径：{rel}')
    if '\\' in rel:
        raise BridgeError(f'🔴 路径必须正斜杠（跨平台+入库同构）：{rel}')
    if '..' in rel.split('/'):
        raise BridgeError(f'🔴 路径含 .. 越界：{rel}')
    return rel


def sanitize(name):
    s = ''.join(('_' if ch in ILLEGAL_FS else ch) for ch in str(name or '')).strip()
    s = s.rstrip('. ')
    return s or '_'


def unique_tails(paths):
    """源绝对路径 → 册内唯一的最短尾段（保住 A浅水印/B深水印 这种只靠父目录区分的对儿）。

    🔴 这是 A/B 双号隔离的物理落点：拍平成 basename 会让 A 号图覆盖 B 号图，
    所以拍平必配守恒闸——尾段一路加长直到册内唯一为止。"""
    parts = {p: PureWindowsPath(p).parts for p in paths}
    result, remaining, n = {}, set(paths), 1
    while remaining:
        tails = {p: '/'.join(parts[p][-n:]) for p in remaining}
        cnt = Counter(tails.values())
        done = [p for p in remaining if cnt[tails[p]] == 1]
        for p in done:
            result[p] = tails[p]
            remaining.discard(p)
        n += 1
        if n > 12 and remaining:
            raise BridgeError(f'落位去重闸：{len(remaining)} 条路径 12 段仍不唯一 {sorted(remaining)[:3]}')
    return result


# ══════════════════════════════════════════════════════════════════════
# 规划层（dry-run 与 apply 共用同一份账，报告与写库不可能漂移）
# ══════════════════════════════════════════════════════════════════════
def load_punch(pconn):
    return {
        'doc': [dict(r) for r in pconn.execute('SELECT * FROM doc ORDER BY id')],
        'doc_member': [dict(r) for r in pconn.execute('SELECT * FROM doc_member ORDER BY id')],
        'material': [dict(r) for r in pconn.execute('SELECT * FROM material ORDER BY id')],
        'asset': [dict(r) for r in pconn.execute('SELECT * FROM asset ORDER BY id')],
    }


def assert_asset_docs(data):
    """闸·孤儿资产（开局就审，别等算落位时才炸）：asset.doc_id 必须在 doc 表里找得到主。

    🔴 以前没这道闸：孤儿资产一路裸奔到 `book_dirs[did]` 才 KeyError——rc=1、零报告，
    错话是个光秃秃的整数，人得自己猜那数字是 doc_id 还是别的。而它本质是源库侧的账坏了
    （删册漏删资产 / doc_id 写错），桥没有任何合法办法替它猜归属：猜出来的册目录谁都没登记，
    挂进 files_json 就是死指针。故前移成守恒闸，点名到具体行，拒收整批。"""
    have = {d['id'] for d in data['doc']}
    orph = [a for a in data['asset'] if a['doc_id'] not in have]
    if orph:
        head = '、'.join(f'asset#{a["id"]}→doc#{a["doc_id"]}' for a in orph[:8])
        raise BridgeError(
            f'🔴 孤儿资产守恒闸：{len(orph)} 条 asset 的 doc_id 在 doc 表里查无此册'
            f'（源库删册漏删资产，或 doc_id 写错）：{head}'
            + (f'…（另有 {len(orph) - 8} 条）' if len(orph) > 8 else '')
            + '。桥不替源库猜归属——猜出来的落位册目录谁都没登记，挂进 files_json 就是死指针；'
              '请先在源库侧把资产归属对齐再吃。')


def plan_book_dirs(docs):
    """册目录名：名称去非法字符；重名册补「·版本名」，仍重名补「#punch_id」。"""
    by_name = Counter(d['名称'] for d in docs)
    dirs = {}
    for d in docs:
        base = sanitize(d['名称'])
        if by_name[d['名称']] > 1 and d.get('版本名'):
            base = f"{base}·{sanitize(d['版本名'])}"
        dirs[d['id']] = base
    dup = {k for k, v in Counter(dirs.values()).items() if v > 1}
    for did, v in list(dirs.items()):
        if v in dup:
            dirs[did] = f'{v}#{did}'
    if len(set(dirs.values())) != len(dirs):
        raise BridgeError('册目录唯一闸：去重后仍撞名，人工介入')
    return dirs


def book_dir_of(rel):
    """落位相对路径 → 册目录段（`产物/历史打卡/<册目录>/…` 中间那段）；不合规矩返 None。"""
    root = ASSET_REL_ROOT.split('/')
    parts = str(rel or '').split('/')
    if len(parts) >= len(root) + 2 and parts[:len(root)] == root:
        return parts[len(root)]
    return None


def load_locked_assets(kconn):
    """闸·落位正本：punch_map 里已登记的资产落位 {punch asset id: 落位相对路径}。

    🔴 登记即正本，复吃一律从这里取、绝不重算。重算的诱因在源库侧天天发生：
    册名被编辑一下、或来了本同名副册（把 plan_book_dirs 的重名去重格局顶歪），
    `产物/历史打卡/<册目录>/…` 的中间那段就会变。而 punch_map 里那条老落位不会跟着变——
    重算出的新路径谁都没登记，一挂进 files_json 就是一条指向空气的死指针（幽灵），
    G4 当场失守，且已提交的坏账要人工去捡。"""
    return {str(r[0]): r[1] for r in kconn.execute(
        "SELECT punch_id, kb_id FROM punch_map WHERE kind='asset'")}


def anchor_order(dircnt):
    """已登记册目录分布 → 定序清单 [(目录, 条数), …]：条数降序、同数按目录名升序。

    🔴 定序是可复现性的全部：没有 key 的 `max(dircnt, key=dircnt.get)` 取的是 dict 插入序里
    第一个最大值，同一批资产换个读取顺序就换个落位目录——新落位谁都没登记 = 死指针。"""
    return sorted(dircnt.items(), key=lambda kv: (-kv[1], kv[0]))


def anchor_dir(dircnt):
    """众数目录（一条登记都没有则 None）。"""
    o = anchor_order(dircnt)
    return o[0][0] if o else None


def plan_assets(data, book_dirs, locked=None):
    """735 条资产 → 逐条 {源绝对路径, 落位相对路径, 源是否存在}。

    落位取值两条路，顺序不可颠倒：
      ① 已登记（punch_map kind='asset' 有行）→ **原样取回，不重算**（正本，见 load_locked_assets）；
      ② 没登记的新资产 → 现算，但册目录以「该册既有登记落位册目录的**众数**」为基准；
         该册一条登记都没有，才用 plan_book_dirs 现算的目录。
    效果：增量补挂进来的新资产与该册老资产同目录，源库改名/加同名副册都不再把已吃册的落位挪窝。

    🔴 anchor 取**众数**而不是「按 punch_id 最小那条」：源库把一条别册资产改挂到本册时
    （doc_id 一改，它那条登记着外册目录的老落位就跟着进来），最小 id 取法会被这一条带歪，
    整册后续新增资产全落进外册目录里——一条错账污染一整册。众数只会被"多数派"决定。
    并列时按（条数降序，目录名升序）定序取第一个：不看 dict 插入序，同一份输入必出同一个结果。
    🔴 登记落位跨 >1 个目录本身就是异常信号，plan() 会单开一条人审事由点名各目录各多少条。"""
    locked = locked or {}
    per_doc = defaultdict(list)
    for a in data['asset']:
        per_doc[a['doc_id']].append(a)
    plans = []
    for did, rows in per_doc.items():
        tails = unique_tails([r['路径'] for r in rows])
        dircnt = Counter()                            # 该册已登记落位的册目录分布（正本基准）
        for r in sorted(rows, key=lambda x: int(x['id'])):
            b = book_dir_of(locked.get(str(r['id'])))
            if b:
                dircnt[b] += 1
        anchor = anchor_dir(dircnt)
        bdir = anchor or book_dirs[did]
        for r in rows:
            pid = str(r['id'])
            tail = '/'.join(sanitize(x) for x in tails[r['路径']].split('/'))
            rel = assert_rel(locked[pid] if pid in locked else f'{ASSET_REL_ROOT}/{bdir}/{tail}')
            plans.append({
                'punch_id': pid, 'doc_id': did, 'type': r['类型'],
                'src': r['路径'], 'rel': rel,
                'locked': pid in locked, 'bookdir': bdir, 'anchored': anchor is not None,
                'anchor_dirs': dict(dircnt),
                'ext': os.path.splitext(r['路径'])[1].lower(),
                'exists': os.path.exists(r['路径']),
            })
    plans.sort(key=lambda x: int(x['punch_id']))
    dupe = [k for k, v in Counter(p['rel'] for p in plans).items() if v > 1]
    if dupe:                                          # 守恒闸：落位不许互相盖
        raise BridgeError(f'落位唯一闸：{len(dupe)} 条落位路径重复，首条 {dupe[0]}'
                          f'（新资产现算的落位撞上了已登记的正本落位 → 人工核对，桥不替谁改名）')
    if len(plans) != len(data['asset']):
        raise BridgeError(f'资产守恒闸：源 {len(data["asset"])} 条 → 规划 {len(plans)} 条')
    return plans


def build_note(doc, kind_src, kind_fallback):
    note = {
        '提取码': doc['提取码'],
        '版本名': doc['版本名'],
        '组名': doc['组名'],
        '册型': doc['册型'],
        '线上book_id': str(doc['线上book_id']) if doc['线上book_id'] else None,  # 🔴 字符串，防雪花截尾
        'punch_doc': str(doc['id']),
        'punch_类型': kind_src,
    }
    if kind_fallback:
        note['kind_降级'] = True
    for f in NOTE_EXTRA_FIELDS:
        v = doc.get(f)
        if v in (None, ''):
            continue
        if f == TRACE_SRC_FIELD:
            # 🔴 改名 + 强制带说明：老区绝对路径只作溯源凭证，谁都别拿它当指针 open()
            note[TRACE_NOTE_KEY] = v
            note[TRACE_NOTE_MEMO_KEY] = TRACE_NOTE_MEMO
            continue
        if f in JSON_LIKE_FIELDS:
            try:
                note[f] = json.loads(v)
                continue
            except (ValueError, TypeError):
                pass
        note[f] = v
    return note


def _load_files(raw, who):
    """artifact.files_json → list[str]；歪了就炸，不静默当空列表（当空=下一步整册重挂，账更乱）。"""
    if raw in (None, ''):
        return []
    try:
        arr = json.loads(raw)
    except (ValueError, TypeError) as e:
        raise BridgeError(f'files_json 不是合法 JSON（{who}）：{e}')
    if not isinstance(arr, list) or any(not isinstance(x, str) for x in arr):
        raise BridgeError(f'files_json 不是字符串数组（{who}）：{raw[:120]}')
    return arr


# ══════════════════════════════════════════════════════════════════════
# 闸 G4　files_json ≡ punch_map(kind='asset') 守恒闸
#
# 一条资产只要进了 punch_map，就必须能在某本已吃册的 files_json 里被指到；反之亦然。
# 缺 = 文件失联（增量复吃时最容易漏的那一刀）；多 = 幽灵落位（指向没登记的文件）。
#
# 🔴 语义分层（同一把尺，量的对象不同，别混）：
#   · `--apply` 收尾 → 审**库态**：写完这一刻库里两边必须严丝合缝，硬闸，口径没松过；
#   · dry-run     → 审**计划态** ＝ 当前库态 + 本轮计划补挂/新增的投影。
#     加 --apply 就会被补挂修好的失联，在计划态里已经补上了 → 报「将补挂 N 条」不炸（那是待办不是坏账）；
#     计划态里仍对不上的（幽灵，或连 --apply 都补不掉的失联）→ 照炸 exit 2，
#     让坏账在**写库之前**就红，堵死"dry-run 绿灯放行、--apply 才落坏账"这条路。
# ══════════════════════════════════════════════════════════════════════
def _eaten_files(kconn, override=None):
    """已吃册（punch_map kind='doc'）的 files_json 里落在本桥落位根下的指针集合。

    override={kb_id: files 列表} 用来把本轮计划的补挂投影上去（dry-run 审计划态用）。
    只管 `产物/历史打卡/` 下的指针，别的产线挂在同一本 artifact 上的文件不越权管。"""
    override = override or {}
    fj = set()
    for aid, raw in kconn.execute(
            "SELECT a.id,a.files_json FROM punch_map p JOIN artifact a ON a.id=p.kb_id WHERE p.kind='doc'"):
        arr = override[aid] if aid in override else _load_files(raw, f'artifact {aid}')
        fj |= {rel for rel in arr if rel.startswith(ASSET_REL_ROOT + '/')}
    return fj


def audit_files_json(kconn):
    """G4·库态（--apply 收尾跑）。"""
    pm = {r[0] for r in kconn.execute("SELECT kb_id FROM punch_map WHERE kind='asset'")}
    fj = _eaten_files(kconn)
    return {'scope': '库态', 'scope_note': '（写完这一刻库里的两本账）',
            'pm': len(pm), 'fj': len(fj),
            'missing': sorted(pm - fj), 'ghost': sorted(fj - pm)}


def audit_planned(kconn, p):
    """G4·计划态（dry-run 跑）＝ 当前库态 + 本轮计划补挂/新增的投影。"""
    pm = {r[0] for r in kconn.execute("SELECT kb_id FROM punch_map WHERE kind='asset'")}
    pm |= {a['rel'] for a in p['assets'] if a['act'] == '入库'}        # 本轮将登记的落位
    override = {d['kb_id']: d['incr_files'] for d in p['docs'] if d.get('incr_files') is not None}
    fj = _eaten_files(kconn, override)                                # 跳过册：补挂后的样子
    for d in p['docs']:                                               # 本轮新建册：将写进去的 files
        if d['act'] == '入库':
            fj |= {rel for rel in d['files'] if rel.startswith(ASSET_REL_ROOT + '/')}
    return {'scope': '计划态', 'scope_note': '（当前库态 + 本轮计划补挂/新增的投影）',
            'pm': len(pm), 'fj': len(fj),
            'missing': sorted(pm - fj), 'ghost': sorted(fj - pm)}


# ══════════════════════════════════════════════════════════════════════
# 闸 G5　账→盘·落位盘账（仅 --copy-assets 时跑；反方向是下面的 G6）
#
# G4 只对得起"账对账"：files_json 与 punch_map 两本账一致，不代表盘上真有那个文件。
# 全量搬完必须再逐条 is_file() 验真——拷贝失败闸抓的是"这一轮拷坏的"，
# G5 抓的是"账上有、盘上没有"的一切（上一轮拷漏的、事后被人删的、被目录占位的）。
# ══════════════════════════════════════════════════════════════════════
def audit_landed(kconn, asset_root):
    root = Path(asset_root)
    rels = sorted(_eaten_files(kconn))
    return {'root': str(root), 'total': len(rels),
            'missing': [r for r in rels if not (root / r).is_file()]}


# ══════════════════════════════════════════════════════════════════════
# 闸 G6　盘→账（仅 --copy-assets 时跑）——G5 的反方向，少了它就漏一整类
#
# G5 只从账走到盘（账上有、盘上没有）。反方向"盘上有、账上没有"它一个都看不见：
#   · 本轮判**拒收**的册（类型无映射/人工态越词表/源文件缺）照拷下去 → 落位根里一堆孤儿；
#   · 上一轮落位改过名、旧文件没清；别人手工往落位根里塞的东西。
# 这些文件谁都不认领，将来清理时不敢删（怕删着真货）、发布时又会跟着一起打包出去。
# 故：落位根下的实际文件逐个反查 punch_map，多出的当场点名 exit 2。
# ══════════════════════════════════════════════════════════════════════
def audit_disk_orphans(kconn, asset_root):
    root = Path(asset_root) / ASSET_REL_ROOT
    known = {r[0] for r in kconn.execute("SELECT kb_id FROM punch_map WHERE kind='asset'")}
    seen, extra = 0, []
    if root.is_dir():
        for p in sorted(root.rglob('*')):
            if not p.is_file():
                continue
            seen += 1
            rel = ASSET_REL_ROOT + '/' + p.relative_to(root).as_posix()
            if rel not in known:
                extra.append(rel)
    return {'root': str(root), 'total': seen, 'extra': extra}


def plan(kconn, data, book_dirs, asset_plans):
    """算出四段的「入/跳/拒」三分账 + 人审清单。dry-run 与 apply 都吃这份。"""
    kinds_ok = check_vocab(kconn, 'artifact', 'kind')          # 🔴 探不出直接炸，无兜底
    sale_ok = check_vocab(kconn, 'artifact', 'sale_state')     # 🔴 同上
    pmap = {(r[0], r[1]): r[2] for r in kconn.execute('SELECT kind,punch_id,kb_id FROM punch_map')}
    taken = {r[0] for r in kconn.execute('SELECT id FROM artifact')}
    taken |= {r[0] for r in kconn.execute('SELECT id FROM material')}
    art_files = {r[0]: r[1] for r in kconn.execute('SELECT id,files_json FROM artifact')}

    rev = []                                          # 人审清单（拿不准的一律进这里，不静默猜）
    asset_by_doc = defaultdict(list)
    for ap in asset_plans:
        asset_by_doc[ap['doc_id']].append(ap)

    # ── ① doc → artifact ───────────────────────────────────────────────
    docs = []
    for d in data['doc']:
        pid = str(d['id'])
        aps = asset_by_doc.get(d['id'], [])
        # 🔴 登记落位跨多个册目录：多半是源库把别册资产改挂到本册（doc_id 一改，外册落位跟着进来）。
        #    落位是正本一律不挪，但这属于账坏了的信号，单开一条人审事由点名各目录各多少条——
        #    与下面的「源册名已变」是两码事，话术不许混（混了人就看不出是改挂还是改名）。
        adirs = next((a['anchor_dirs'] for a in aps if a['anchor_dirs']), {})
        if len(adirs) > 1:
            order = anchor_order(adirs)
            rev.append(('doc', pid, d['名称'],
                        f'该册已登记落位跨 {len(adirs)} 个册目录（'
                        + '、'.join(f'`{k}`×{v}' for k, v in order) +
                        f'）→ 本轮新增资产按众数目录 `{order[0][0]}` 落位（老落位一律不挪窝）；'
                        f'跨目录多半是源库把别册资产改挂了过来，请人工核对要不要搬文件统一目录'))
        # 🔴 落位正本 vs 现算目录不一致：说明源库那边册名/重名格局变了。落位不跟着变（防死指针），
        #    但绝不静默——进人审清单让人看见"目录跟源册名对不上是故意的"。
        anchors = {a['bookdir'] for a in aps if a['anchored']}
        if anchors and book_dirs[d['id']] not in anchors:
            rev.append(('doc', pid, d['名称'],
                        f'源册名/重名格局已变（现算落位目录 `{book_dirs[d["id"]]}`），'
                        f'但该册落位正本登记在 `{sorted(anchors)[0]}` 下 → 落位一律从登记取不重算，'
                        f'本册新增资产也落这个目录（改落位=造死指针，要挪得人工搬文件+改两本账）'))
        if ('doc', pid) in pmap:
            # 🔴 幂等跳过只跳"建行"，不跳"补账"：册早在库里、但这轮又冒出新资产落位时，
            #    必须把新落位并进它的 files_json，否则文件进了 punch_map 却没人指向 = 失联。
            kb_id = pmap[('doc', pid)]
            e = {'punch_id': pid, 'kb_id': kb_id, 'act': '跳过', 'doc': d}
            if kb_id not in art_files:
                rev.append(('doc', pid, d['名称'],
                            f'punch_map 指到的 artifact `{kb_id}` 已不在 artifact 表里 → 无法增量补挂，人工核对'))
            else:
                cur = _load_files(art_files[kb_id], f'artifact {kb_id}（punch doc {pid}）')
                # 已登记的资产一律算"该挂"（登记即正本，源文件事后不在盘上也不撤指针，
                # 否则 punch_map 有行、files_json 没人指 = 自造失联）；没登记的按源文件在不在盘算。
                want = [a['rel'] for a in aps if a['exists'] or a['locked']]
                seen = set(cur)
                add = [x for x in want if not (x in seen or seen.add(x))]
                if add:
                    e['incr_add'] = add
                    e['incr_files'] = cur + add        # 并进去不覆盖：人工手加的条目原样留着
                    rev.append(('doc', pid, d['名称'],
                                f'册已在库（幂等跳过），但 {len(add)} 条资产落位没挂在 files_json 上 → 本轮增量补挂'))
            docs.append(e)
            continue
        kind_src = d['类型']
        kind = KIND_MAP.get(kind_src)
        if kind is None:
            rev.append(('doc', pid, d['名称'], f'类型 {kind_src!r} 不在映射表里 → 拒收，补映射再吃'))
            docs.append({'punch_id': pid, 'kb_id': None, 'act': '拒收', 'doc': d,
                         'why': f'类型 {kind_src!r} 无映射'})
            continue
        fallback = kind not in kinds_ok
        if fallback:
            # 🔴 不静默：目标库 kind 词表容不下就降级成「其他」，原值原封落 note.punch_类型，
            #    同时进人审清单——要不要给 artifact.kind 扩词是公共契约件，归主位定。
            rev.append(('doc', pid, d['名称'],
                        f'kind 映射 {kind_src}→{kind} 不在 artifact.kind 词表 {kinds_ok} 内，'
                        f'本次降级为「其他」（原值存 note.punch_类型）；扩词表=公共契约件，待主位定'))
            kind = '其他'
        sale = d['人工态']
        if sale not in (None, '') and sale not in sale_ok:
            docs.append({'punch_id': pid, 'kb_id': None, 'act': '拒收', 'doc': d,
                         'why': f'人工态 {sale!r} 不在 {sale_ok}'})
            rev.append(('doc', pid, d['名称'], f'人工态 {sale!r} 越出 sale_state 词表 → 拒收'))
            continue
        files = [a['rel'] for a in aps if a['exists'] or a['locked']]
        gone = [a for a in aps if not a['exists'] and not a['locked']]
        if gone:
            rev.append(('doc', pid, d['名称'], f'{len(gone)} 个源资产文件不在老区磁盘上，未写进 files_json'))
        if d.get('考点'):
            rev.append(('doc', pid, d['名称'], '源带考点文字名，kp_ids_json 本轮留空（考点映射归阶段2）'))
        if book_dirs[d['id']] != sanitize(d['名称']):
            rev.append(('doc', pid, d['名称'],
                        f'册名与他册相撞，落位目录自动改名为 `{book_dirs[d["id"]]}`（版本名去重）→ 请目检认可'))
        docs.append({
            'punch_id': pid, 'act': '入库', 'doc': d,
            'kb_id': mint_id('A', f'punch:doc:{pid}', taken),
            'name': d['名称'], 'kind': kind, 'status': ARTIFACT_STATUS,
            'sale_state': sale or None, 'link': d['网盘链接'] or None,
            'files': files, 'note': build_note(d, kind_src, fallback),
        })
    doc_kb = {x['punch_id']: x['kb_id'] for x in docs if x['kb_id']}

    # ── ② doc_member → artifact_member ────────────────────────────────
    have_mem = {(r[0], r[1]) for r in kconn.execute('SELECT parent_id,member_id FROM artifact_member')}
    mems = []
    for m in data['doc_member']:
        pp, mm = str(m['合刊doc_id']), str(m['成员doc_id'])
        parent, member = doc_kb.get(pp), doc_kb.get(mm)
        if not parent or not member:
            mems.append({'act': '拒收', 'src': m, 'why': f'两端 id 未在 punch_map 翻译出来（{pp}/{mm}）'})
            rev.append(('doc_member', f'{pp}-{mm}', '', '合刊两端有一端没吃进来 → 关系拒收'))
            continue
        mems.append({'act': '跳过' if (parent, member) in have_mem else '入库',
                     'src': m, 'parent': parent, 'member': member, 'ord': m['排序']})

    # ── ③ material → material ─────────────────────────────────────────
    mats = []
    for r in data['material']:
        pid = str(r['id'])
        if ('material', pid) in pmap:
            mats.append({'punch_id': pid, 'act': '跳过', 'kb_id': pmap[('material', pid)], 'src': r})
            continue
        aid = doc_kb.get(str(r['doc_id']))
        if not aid:
            mats.append({'punch_id': pid, 'act': '拒收', 'src': r, 'why': f'所属 doc {r["doc_id"]} 未吃进来'})
            rev.append(('material', pid, '', f'所属册 doc {r["doc_id"]} 没进 artifact → 物料拒收'))
            continue
        title = r['标题']
        if not title:
            # 🔴 kb.material.title NOT NULL；源缺标题不静默编，拿册名占位并进人审清单
            title = next((d['doc']['名称'] for d in docs if d['punch_id'] == str(r['doc_id'])), '（无标题）')
            rev.append(('material', pid, title, '源 material.标题 为空，已用册名占位 → 人工补标题'))
        topics = r['话题词']
        if topics:
            try:
                json.loads(topics)                    # 只验不改：topics_json 原样 JSON 落库
            except (ValueError, TypeError):
                mats.append({'punch_id': pid, 'act': '拒收', 'src': r, 'why': '话题词非合法 JSON'})
                rev.append(('material', pid, title, '话题词不是合法 JSON → 拒收'))
                continue
        mats.append({
            'punch_id': pid, 'act': '入库', 'src': r,
            'kb_id': mint_id('m', f'punch:material:{pid}', taken),
            'artifact_id': aid, 'account': r['账号'],
            'is_active': 1 if r['is_active'] else 0, 'title': title, 'body': r['正文'] or '',
            'topics_json': topics, 'style_seed': r['风格种子'],
            'burned': 1 if r['burned'] else 0, 'product_desc': r['商品描述'],
            'pan_share_text': r['网盘分享语'], 'created_at': r['created_at'],
        })

    # ── ④ asset → punch_map + files_json ──────────────────────────────
    for ap in asset_plans:
        if ('asset', ap['punch_id']) in pmap:
            ap['act'] = '跳过'
        elif not ap['exists']:
            ap['act'] = '拒收'
            ap['why'] = '源文件不在老区磁盘上'
        elif not doc_kb.get(str(ap['doc_id'])):
            ap['act'] = '拒收'
            ap['why'] = f'所属 doc {ap["doc_id"]} 未吃进来'
        else:
            ap['act'] = '入库'
    for ap in asset_plans:
        if ap['act'] == '拒收' and ap.get('why') == '源文件不在老区磁盘上':
            rev.append(('asset', ap['punch_id'], ap['src'], '源文件缺失 → 不落位不挂 files_json'))

    # ── 守恒闸：每段「读入 = 入 + 跳 + 拒」，一条都不许蒸发 ──────────
    for tag, planned, total in (('doc', docs, len(data['doc'])),
                                ('doc_member', mems, len(data['doc_member'])),
                                ('material', mats, len(data['material'])),
                                ('asset', asset_plans, len(data['asset']))):
        c = Counter(x['act'] for x in planned)
        if sum(c.values()) != total:
            raise BridgeError(f'守恒闸 {tag}：源 {total} ≠ 规划 {sum(c.values())}（{dict(c)}）')
    return {'docs': docs, 'mems': mems, 'mats': mats, 'assets': asset_plans,
            'review': rev, 'kinds_ok': kinds_ok, 'sale_ok': sale_ok}


# ══════════════════════════════════════════════════════════════════════
# 写库层（只有 --apply 走这里）
# ══════════════════════════════════════════════════════════════════════
def apply_plan(kconn, p):
    ts = now()
    n = Counter()
    try:
        for d in p['docs']:
            if d['act'] == '跳过' and d.get('incr_files') is not None:
                # 增量补挂：只动 files_json 一列，人工列（sale_state 等）一根不碰
                kconn.execute('UPDATE artifact SET files_json=? WHERE id=?',
                              (json.dumps(d['incr_files'], ensure_ascii=False), d['kb_id']))
                n['artifact.files_json 增量补挂(册)'] += 1
                n['artifact.files_json 增量补挂(条)'] += len(d['incr_add'])
                continue
            if d['act'] != '入库':
                continue
            kconn.execute(
                'INSERT INTO artifact(id,name,kind,status,files_json,source_line,template_id,'
                'kp_ids_json,delivered_at,link,note,created_at,sale_state) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (d['kb_id'], d['name'], d['kind'], d['status'],
                 json.dumps(d['files'], ensure_ascii=False) if d['files'] else None,
                 SOURCE_LINE, None, None, None,        # template/kp/delivered_at 无源，留空不编
                 d['link'], json.dumps(d['note'], ensure_ascii=False), ts, d['sale_state']))
            kconn.execute('INSERT INTO punch_map(kind,punch_id,kb_id,note,created_at) VALUES (?,?,?,?,?)',
                          ('doc', d['punch_id'], d['kb_id'], d['name'], ts))
            n['doc'] += 1
        for m in p['mems']:
            if m['act'] != '入库':
                continue
            kconn.execute('INSERT INTO artifact_member(parent_id,member_id,ord) VALUES (?,?,?)',
                          (m['parent'], m['member'], m['ord']))
            n['doc_member'] += 1
        for r in p['mats']:
            if r['act'] != '入库':
                continue
            kconn.execute(
                'INSERT INTO material(id,artifact_id,account,is_active,title,body,topics_json,'
                'style_seed,burned,product_desc,pan_share_text,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (r['kb_id'], r['artifact_id'], r['account'], r['is_active'], r['title'], r['body'],
                 r['topics_json'], r['style_seed'], r['burned'], r['product_desc'],
                 r['pan_share_text'], r['created_at']))
            kconn.execute('INSERT INTO punch_map(kind,punch_id,kb_id,note,created_at) VALUES (?,?,?,?,?)',
                          ('material', r['punch_id'], r['kb_id'], r['title'][:120], ts))
            n['material'] += 1
        for a in p['assets']:
            if a['act'] != '入库':
                continue
            kconn.execute('INSERT INTO punch_map(kind,punch_id,kb_id,note,created_at) VALUES (?,?,?,?,?)',
                          ('asset', a['punch_id'], a['rel'], a['type'], ts))
            n['asset'] += 1
        kconn.commit()
    except Exception:
        kconn.rollback()
        raise
    return n


def copy_assets(plans, asset_root, limit=None, apply=False):
    """资产平移（拷贝非引用）。老区只读：只 read 源文件，绝不动它。

    🔴 闸 G3 落盘闸就装在函数第一行：缺 apply=True 一律拒收。
    装在这里而不是只装在 main 的参数校验里——因为"dry-run 却真拷了文件"这条已经犯过一次，
    调用方将来多一条分支就会再犯，闸必须贴着落盘动作本身。

    🔴 拷贝失败闸装在最后一行：failed>0 直接 CopyFailed（exit 2）并列清单。
    "失败几个 → 报告里记一笔 → 照样 exit 0" 是最坏的一种静默：库里 files_json 指着那条落位，
    盘上却没有文件，账面还一路绿灯——正是"靠闸不靠注释"要挡的东西。

    🔴 只拷**本轮判入库/跳过**的（act 过滤）：只筛 `exists` 会把判**拒收**的资产也拷下去
    （类型无映射的册、人工态越词表的册，它们的资产源文件好端端在盘上，`exists` 一律为真），
    落位根里就多出一堆两本账都不认领的孤儿——G4 是账对账，压根看不见它们；
    将来清理不敢删、发布还跟着打包出去。收尾的 G6 盘→账闸是这条过滤的反向复核。"""
    if not apply:
        raise BridgeError('🔴 落盘闸：拷贝属于落盘写动作，必须 --apply；缺 --apply 一律零拷贝（dry-run 只算账出报告）')
    if any('act' not in a for a in plans):
        raise BridgeError('🔴 拷贝闸：拷贝清单必须先过 plan() 定出「入库/跳过/拒收」三分账再拷——'
                          '没有 act 就没法把拒收件挡在盘外，那正是无账孤儿的来路。')
    root = Path(asset_root).resolve()
    done, skipped, failed = [], [], []
    todo = [a for a in plans if a['exists'] and a['act'] in ('入库', '跳过')]
    if limit is not None:
        todo = todo[:limit]
    for a in todo:
        dst = root / a['rel']
        try:
            if dst.exists() and dst.stat().st_size == os.path.getsize(a['src']):
                skipped.append(a['rel'])
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a['src'], dst)
            if not dst.exists() or dst.stat().st_size != os.path.getsize(a['src']):
                raise OSError('落位大小对不上')
            done.append(a['rel'])
        except OSError as e:
            failed.append((a['rel'], str(e)))
    if failed:
        lines = '\n'.join(f'    ✘ {rel} —— {why}' for rel, why in failed[:20])
        more = f'\n    …（另有 {len(failed) - 20} 条，全量见预检报告 ③ 段）' if len(failed) > 20 else ''
        raise CopyFailed(
            f'🔴 拷贝失败闸：{len(failed)} 个文件没落到位（真拷 {len(done)}｜已在位 {len(skipped)}），'
            f'落位根 {root}。files_json 已经/即将指着这些落位，盘上却没有文件 = 死指针，'
            f'不许"记一笔然后 exit 0"。清单：\n{lines}{more}',
            (done, skipped, failed))
    return done, skipped, failed


# ══════════════════════════════════════════════════════════════════════
# 报告层
# ══════════════════════════════════════════════════════════════════════
def _md_cell(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')


def write_asset_report(path, data, plans, book_dirs, copy_result, asset_root):
    docs = {d['id']: d for d in data['doc']}
    ext = Counter(a['ext'] for a in plans)
    miss = [a for a in plans if not a['exists']]
    L = ['# PRD-003 吃库 · 资产存在性预检与拷贝清单（A 账层桥）', '',
         f'生成：{now()}｜源 `资料库.db` asset 表 **{len(plans)}** 条｜落位根 `{ASSET_REL_ROOT}/`（相对 v2 根）',
         f'｜本次拷贝目标根 `{asset_root if asset_root else "（本次零拷贝）"}`', '',
         '> 🔴 卡面写的「735 个 PDF」与实测不符：735 条资产里 '
         f'**{ext.get(".pdf", 0)} 个 PDF + {ext.get(".png", 0)} 个 PNG**'
         '（PNG 是小红书配图/页图/封面）。本桥按 735 条全量做预检与落位，不按扩展名筛。', '',
         '## ① 存在性预检', '',
         f'- 逐条 `os.path.exists()` 实测老区绝对路径：**存在 {len(plans) - len(miss)} / 缺失 {len(miss)}**',
         f'- 扩展名分布：' + '、'.join(f'`{k or "(无)"}` {v}' for k, v in ext.most_common()), '']
    if miss:
        L += ['### 🔴 缺失清单（不静默、不拦整批——缺的不写 files_json，其余照吃）', '',
              '| punch asset id | 册（punch doc id） | 类型 | 老区源路径 |', '|---|---|---|---|']
        L += [f'| {a["punch_id"]} | {_md_cell(docs[a["doc_id"]]["名称"])}（{a["doc_id"]}） | '
              f'{a["type"]} | `{_md_cell(a["src"])}` |' for a in miss]
        L.append('')
    else:
        L += ['### 缺失清单', '', '**空**——735 条源路径逐条实测，全部在盘。', '']

    per = defaultdict(list)
    for a in plans:
        per[a['doc_id']].append(a)
    L += ['## ② 按册汇总', '',
          '| punch doc id | 册名 | 类型 | 落位册目录 | 资产数 | PDF | PNG | 存在 | 缺失 |',
          '|---|---|---|---|---:|---:|---:|---:|---:|']
    for did in sorted(per, key=lambda x: -len(per[x])):
        rows = per[did]
        d = docs[did]
        L.append(f'| {did} | {_md_cell(d["名称"])} | {d["类型"]} | `{_md_cell(book_dirs[did])}` | '
                 f'{len(rows)} | {sum(1 for r in rows if r["ext"] == ".pdf")} | '
                 f'{sum(1 for r in rows if r["ext"] == ".png")} | '
                 f'{sum(1 for r in rows if r["exists"])} | {sum(1 for r in rows if not r["exists"])} |')
    noasset = [d for d in data['doc'] if d['id'] not in per]
    L += ['', f'- 有资产的册 **{len(per)}/{len(data["doc"])}**；无资产的册 {len(noasset)} 本：'
              + ('、'.join(f'{d["名称"]}({d["id"]})' for d in noasset) or '无'), '']

    L += ['## ③ 拷贝清单（老区源绝对路径 → 落位相对路径）', '',
          '> 落位规则：`产物/历史打卡/<册目录>/<册内唯一最短尾段>`。'
          '尾段而非纯文件名，是因为同册内 `小红书图-A浅水印/01第一天.png` 与 `-B深水印/01第一天.png` '
          '同名——拍平会让 A 号图盖掉 B 号图（A/B 双号隔离的物理落点），故配去重闸。', '',
          '> 🔴 `--copy-assets` 只搬**判定=入库/跳过**的：判**拒收**的资产源文件照样在盘上'
          '（`源在盘 ✔`），但两本账都不认领它，拷下去就是无账孤儿——收尾 G6 盘→账闸反向复核这一条。', '',
          '| punch asset id | 类型 | 判定 | 源（老区绝对路径） | 落位（相对 v2 根） | 源在盘 |',
          '|---|---|---|---|---|---|']
    L += [f'| {a["punch_id"]} | {a["type"]} | {a.get("act", "?")} | `{_md_cell(a["src"])}` | '
          f'`{_md_cell(a["rel"])}` | {"✔" if a["exists"] else "✘"} |' for a in plans]
    L += ['', '## ④ 抽样拷贝验证', '',
          '> 🔴 落盘闸：`--copy-sample` / `--copy-assets` 都必须配 `--apply`，'
          '缺 `--apply` 直接拒收（零拷贝）；`--copy-sample` 还必须显式给 `--sample-dest <目录>`。', '']
    if copy_result is None:
        L.append('本次未跑拷贝（`--copy-sample` / `--copy-assets` 都没给，或缺 `--apply` 被落盘闸挡下）。')
    else:
        done, skipped, failed = copy_result
        L += [f'- 真拷 **{len(done)}** 个、已在位跳过 {len(skipped)} 个、失败 {len(failed)} 个',
              f'- 校验口径：落位文件存在 且 字节数与源一致', '']
        for r in done:
            L.append(f'  - ✔ `{r}`')
        for r, e in failed:
            L.append(f'  - ✘ `{r}` —— {e}')
    L += ['', '---', '🔴 全量 735 个文件的真实拷贝留给**主位实跑**'
          f'（`python 工具箱/桥/bridge_shelf.py --punch … --kb … --apply --copy-assets`）；本轮只出清单+抽样。', '']
    Path(path).write_text('\n'.join(L) + '\n', encoding='utf-8')


def write_run_report(path, mode, data, p, applied, audit, landed=None, orphan=None):
    def tally(rows):
        c = Counter(x['act'] for x in rows)
        return c, f'入库 {c["入库"]}｜跳过(幂等) {c["跳过"]}｜拒收 {c["拒收"]}'

    cd, sd = tally(p['docs']); cm, sm = tally(p['mems'])
    cma, sma = tally(p['mats']); ca, sa = tally(p['assets'])
    incr = [d for d in p['docs'] if d.get('incr_files') is not None]
    incr_n = sum(len(d['incr_add']) for d in incr)
    L = ['# PRD-003 吃库 · A 账层桥运行报告', '',
         f'生成：{now()}｜模式：**{mode}**', '',
         '## 账面', '',
         '| 段 | 源行数 | 结果 |', '|---|---:|---|',
         f'| doc → artifact | {len(data["doc"])} | {sd} |',
         f'| doc_member → artifact_member | {len(data["doc_member"])} | {sm} |',
         f'| material → material | {len(data["material"])} | {sma} |',
         f'| asset → punch_map/files_json | {len(data["asset"])} | {sa} |', '',
         f'- 目标库 artifact.kind 词表：{p["kinds_ok"]}',
         f'- 目标库 artifact.sale_state 词表：{p["sale_ok"]}',
         f'- sale_state 取值分布（本次规划）：'
         + '、'.join(f'{k or "(空)"}×{v}' for k, v in
                    Counter(d.get('sale_state') for d in p['docs'] if d['act'] == '入库').most_common()), '']

    # ── 增量补挂（跳过册的 files_json 补账）——单列一段，不许混进"跳过"里看不见 ──
    L += ['## 增量补挂 {} 册'.format(len(incr)), '',
          '> 幂等跳过只跳"建行"不跳"补账"：册早在库、这轮又冒出新资产落位时，'
          '把新落位**并进**（不覆盖）它的 `artifact.files_json`。', '']
    if incr:
        L += [f'- 本次补挂 **{len(incr)} 册 / {incr_n} 条落位**'
              + ('' if applied is not None else f'（dry-run：**将补挂 {incr_n} 条**，只算不写，要真补加 --apply）'), '',
              '| punch doc id | 册名 | 新挂条数 | 首条落位 |', '|---|---|---:|---|']
        L += [f'| {d["punch_id"]} | {_md_cell(d["doc"]["名称"])} | {len(d["incr_add"])} | '
              f'`{_md_cell(d["incr_add"][0])}` |' for d in incr]
        L.append('')
    else:
        L += ['- 本次补挂 **0 册**（跳过册的 files_json 与资产落位已经对齐）。', '']

    if applied is not None:
        L += ['## 实写入', '', '| 表/动作 | 行数 |', '|---|---:|']
        L += [f'| {k} | {v} |' for k, v in sorted(applied.items())]
        L.append('')

    # ── 守恒闸自查（G4）：apply 审库态，dry-run 审计划态 ──────────────
    L += ['## 守恒闸 G4：`files_json` ≡ `punch_map(kind=\'asset\')`', '',
          f'- 本次审的是 **{audit["scope"]}**{audit["scope_note"]}'
          + ('' if applied is not None else
             '——「加 --apply 就会补挂修好」的失联不算坏账'
             + (f'（上一段已预告 **将补挂 {incr_n} 条**）' if incr_n else '（本轮没有待补挂的）')
             + '；计划态里仍对不上的照炸，坏账在写库之前就红。'),
          f'- punch_map 资产落位 **{audit["pm"]}** 条｜已吃册 files_json 里落在 `{ASSET_REL_ROOT}/` 下的 '
          f'**{audit["fj"]}** 条',
          f'- 失联（进了 punch_map 却没人指）：**{len(audit["missing"])}** 条'
          + ('' if not audit['missing'] else '　首条 `%s`' % audit['missing'][0]),
          f'- 幽灵（files_json 里有却没登记）：**{len(audit["ghost"])}** 条'
          + ('' if not audit['ghost'] else '　首条 `%s`' % audit['ghost'][0]),
          '',
          ('✅ 两边对齐。' if not (audit['missing'] or audit['ghost'])
           else '🔴 **对不上——本次运行以 BridgeError 收场**（详见 stderr）。'), '']

    # ── 盘账闸 G5：账对上了不等于盘上真有文件（仅 --copy-assets 跑）──
    if landed is not None:
        L += ['## 盘账闸 G5：files_json 落位指针逐条 `is_file()` 验真', '',
              f'- 验真根 `{landed["root"]}`｜受检落位 **{landed["total"]}** 条'
              f'｜盘上缺 **{len(landed["missing"])}** 条', '']
        if landed['missing']:
            L += ['| # | 账上有、盘上没有的落位 |', '|---:|---|']
            L += [f'| {i + 1} | `{_md_cell(r)}` |' for i, r in enumerate(landed['missing'][:50])]
            if len(landed['missing']) > 50:
                L.append(f'| … | 另有 {len(landed["missing"]) - 50} 条 |')
            L += ['', '🔴 **本次运行以 BridgeError 收场**：账对账（G4）绿不代表盘上真有文件，'
                  '这类才是真死指针。', '']
        else:
            L += ['✅ 每一条落位指针在盘上都是真文件。', '']

    # ── 盘→账闸 G6：G5 的反方向——盘上有、账上没有（仅 --copy-assets 跑）──
    if orphan is not None:
        L += ['## 盘→账闸 G6：落位根下的实际文件逐个反查 `punch_map`', '',
              '> G5 只从账走到盘；反方向「盘上有、账上没有」它一个都看不见：本轮判**拒收**的册'
              '若被拷了下来、上一轮改名没清的旧落位、别人手工塞进来的文件——全是无账孤儿。', '',
              f'- 扫描根 `{orphan["root"]}`｜盘上实际文件 **{orphan["total"]}** 个'
              f'｜查无此账 **{len(orphan["extra"])}** 个', '']
        if orphan['extra']:
            L += ['| # | 盘上有、punch_map 里查无此账的文件 |', '|---:|---|']
            L += [f'| {i + 1} | `{_md_cell(r)}` |' for i, r in enumerate(orphan['extra'][:50])]
            if len(orphan['extra']) > 50:
                L.append(f'| … | 另有 {len(orphan["extra"]) - 50} 个 |')
            L += ['', '🔴 **本次运行以 BridgeError 收场**：无账文件将来清理不敢删、发布还跟着打包，'
                  '必须当场认领或清走。', '']
        else:
            L += ['✅ 落位根下每一个文件都在 `punch_map` 里查得到账。', '']

    rev = p['review']
    trace_n = sum(1 for d in p['docs'] if d['act'] == '入库' and TRACE_NOTE_KEY in d['note'])
    L += [f'## 人审清单（{len(rev)} 条）', '',
          '> 拿不准的一律进这张单子，脚本绝不静默猜。', '',
          f'> 🔴 **老区绝对路径只作溯源**：源列 `doc.源文件路径` 落 `artifact.note` 时改名 '
          f'`{TRACE_NOTE_KEY}`，并强制同行落兄弟键 `{TRACE_NOTE_MEMO_KEY}="{TRACE_NOTE_MEMO}"`。'
          f'本次新入库 {trace_n} 册带此键（幂等跳过的册不重写 note）。'
          f'它指的是老区 `D:\\workplace\\ai-bkb\\…`（**只读、随时可能挪窝**），'
          f'谁都别拿它 open()——本库唯一的文件指针是 `files_json` 里的相对路径。', '']
    if rev:
        L += ['| 域 | punch id | 对象 | 事由 |', '|---|---|---|---|']
        L += [f'| {a} | {b} | {_md_cell(c)[:60]} | {_md_cell(d)} |' for a, b, c, d in rev]
    else:
        L.append('**空**。')
    L += ['', '## 幂等口径', '',
          '- 骨架 = `punch_map(kind, punch_id)`：重跑时已在表里的一律跳过——不重建、不覆盖；',
          '- `artifact_member` 无 punch_map 位（表的 kind CHECK 只认 doc/material/question/asset），',
          '  幂等靠主键 `(parent_id, member_id)` 先查后插；',
          '- 🔴 `sale_state` 是人工列，桥只在**首次建行**时写源值，第二遍绝不回写——',
          '  「能发≠已发」的血案不许在吃库时复发。', '']
    Path(path).write_text('\n'.join(L) + '\n', encoding='utf-8')


# ══════════════════════════════════════════════════════════════════════
# 闸 G3　落盘闸的参数侧（函数侧在 copy_assets 第一行，两处都装）
# ══════════════════════════════════════════════════════════════════════
def gate_copy_args(args):
    if args.copy_sample < 0:
        raise BridgeError(f'--copy-sample 不能是负数：{args.copy_sample}')
    if args.copy_assets and args.copy_sample > 0:
        raise BridgeError('--copy-assets 与 --copy-sample 二选一（全量搬 vs 抽样验，别混着跑）')
    if args.copy_sample > 0 and not args.sample_dest:
        raise BridgeError('🔴 --copy-sample 必须显式给 --sample-dest <目录>：'
                          '抽样是验拷贝函数的，只准落临时/沙盘目录，不许默认往 v2 根上撒文件。')
    if args.sample_dest and args.copy_sample <= 0:
        raise BridgeError('--sample-dest 只配 --copy-sample 用（没抽样就别指落位）')
    if (args.copy_assets or args.copy_sample > 0) and not args.apply:
        raise BridgeError('🔴 落盘闸：--copy-assets / --copy-sample 都是落盘写动作，必须配 --apply；'
                          '缺 --apply 一律零拷贝——dry-run 的定义就是"只算账、只出报告，零写库零拷文件"。')


def main(argv=None):
    ap = argparse.ArgumentParser(description='A 账层桥：资料库.db 册子账 → kb.db（PRD-003 阶段1）')
    ap.add_argument('--punch', required=True, help='源 资料库.db（一律 mode=ro 打开）')
    ap.add_argument('--kb', required=True, help='目标 kb.db')
    ap.add_argument('--apply', action='store_true', help='真写库+准落盘；不给=dry-run 零写库零拷文件')
    ap.add_argument('--report-dir', default=None, help=f'报告目录，默认 <v2根>/{REPORT_SUBDIR}')
    ap.add_argument('--asset-root', default=None, help='--copy-assets 的落位根，默认 v2 根')
    ap.add_argument('--copy-assets', action='store_true', help='全量搬 735 个文件（须 --apply；留给主位实跑）')
    ap.add_argument('--copy-sample', type=int, default=0,
                    help='只抽 N 个文件真拷验证拷贝函数（须 --apply 且须显式 --sample-dest）')
    ap.add_argument('--sample-dest', default=None, help='--copy-sample 的落位根（必给，一般给沙盘临时目录）')
    args = ap.parse_args(argv)

    t0 = time.time()
    mode = 'apply（真写库）' if args.apply else 'dry-run（只出报告，零写库零拷文件）'
    try:
        gate_copy_args(args)                          # 🔴 落盘闸前置：开库前就把不合规的拷贝请求挡回去
    except BridgeError as e:
        print(f'🔴 桥闸拦下：{e}', file=sys.stderr)
        return 2
    report_dir = Path(args.report_dir) if args.report_dir else ROOT / REPORT_SUBDIR
    report_dir.mkdir(parents=True, exist_ok=True)
    asset_root = Path(args.asset_root).resolve() if args.asset_root else ROOT

    pconn = open_punch_ro(args.punch)
    kconn = open_kb(args.kb)
    try:
        assert_tables(kconn, ('artifact', 'artifact_member', 'material', 'punch_map'))
        data = load_punch(pconn)
        print(f'源库读入：doc {len(data["doc"])}｜doc_member {len(data["doc_member"])}｜'
              f'material {len(data["material"])}｜asset {len(data["asset"])}')
        assert_asset_docs(data)                        # 🔴 开局守恒闸：孤儿资产（doc_id 查无此册）
        book_dirs = plan_book_dirs(data['doc'])
        locked = load_locked_assets(kconn)             # 🔴 已登记落位=正本，复吃不重算
        asset_plans = plan_assets(data, book_dirs, locked)
        p = plan(kconn, data, book_dirs, asset_plans)
        if locked:
            drift = sum(1 for a in asset_plans if a['anchored'] and a['bookdir'] != book_dirs[a['doc_id']])
            print(f'落位正本：punch_map 已登记 {len(locked)} 条落位一律原样取回不重算'
                  + (f'；其中 {drift} 条的源册名/重名格局已变，落位仍按登记不挪窝' if drift else ''))

        incr = [d for d in p['docs'] if d.get('incr_files') is not None]
        applied = None
        if args.apply:
            applied = apply_plan(kconn, p)
            print('写入：' + ('｜'.join(f'{k} +{v}' for k, v in sorted(applied.items())) or '零新增'))
        else:
            print('dry-run：未写库、未拷文件（要真吃加 --apply）')
        incr_n = sum(len(d['incr_add']) for d in incr)
        print(f'增量补挂 {len(incr)} 册'
              + (f'（{incr_n} 条落位'
                 + ('已写入）' if args.apply else f'，dry-run 未写：将补挂 {incr_n} 条）') if incr else ''))

        copy_result, copy_root, copy_err = None, None, None
        if args.copy_assets:                          # 到这里必已过 G3（gate_copy_args + copy_assets 双闸）
            copy_root = asset_root
        elif args.copy_sample > 0:
            copy_root = Path(args.sample_dest).resolve()
        if copy_root is not None:
            try:
                copy_result = copy_assets(asset_plans, copy_root, apply=args.apply,
                                          limit=(args.copy_sample if args.copy_sample > 0 else None))
            except CopyFailed as e:                   # 🔴 拷贝失败闸：先接住现场，报告落地后再炸
                copy_result, copy_err = e.result, e
        if copy_result:
            print(f'拷贝：真拷 {len(copy_result[0])}｜已在位 {len(copy_result[1])}｜失败 {len(copy_result[2])}'
                  f'｜落位根 {copy_root}')

        # 🔴 G4 分层：--apply 收尾审库态（硬闸）；dry-run 审计划态（当前库态 + 本轮计划投影）
        audit = audit_files_json(kconn) if args.apply else audit_planned(kconn, p)
        # 🔴 G5 账→盘 / G6 盘→账：只有真搬过全量文件才谈得上"盘上有没有"，故仅 --copy-assets 时跑
        landed = audit_landed(kconn, asset_root) if args.copy_assets else None
        orphan = audit_disk_orphans(kconn, asset_root) if args.copy_assets else None

        r1 = report_dir / '预检-资产PDF.md'
        r2 = report_dir / '吃库报告-A账层桥.md'
        write_asset_report(r1, data, asset_plans, book_dirs, copy_result, copy_root)
        write_run_report(r2, mode, data, p, applied, audit, landed, orphan)
        for tag, rows in (('doc', p['docs']), ('doc_member', p['mems']),
                          ('material', p['mats']), ('asset', p['assets'])):
            c = Counter(x['act'] for x in rows)
            print(f'  {tag:<11} 入库 {c["入库"]:>4}｜跳过 {c["跳过"]:>4}｜拒收 {c["拒收"]:>4}')
        print(f'人审清单 {len(p["review"])} 条')
        print(f'报告：{r1}\n      {r2}')
        # ── 报告先落地再炸：现场证据留给人看，退出码照样是 2，绝不"警告一下继续" ──
        if copy_err:
            raise copy_err
        if landed and landed['missing']:
            raise BridgeError(
                f'🔴 盘账闸 G5 失守：files_json 的 {landed["total"]} 条落位指针里，'
                f'{len(landed["missing"])} 条在盘上不是文件（验真根 {landed["root"]}）；'
                f'首条 {landed["missing"][0]}'
                + (f'（另有 {len(landed["missing"]) - 1} 条，见报告 {r2}）' if len(landed['missing']) > 1 else '')
                + '。账对账（G4）绿只说明两本账一致，这一条说明盘上真没有那个文件——'
                  '死指针必须当场红，不许交付。')
        if orphan and orphan['extra']:
            raise BridgeError(
                f'🔴 盘→账闸 G6 失守：落位根 {orphan["root"]} 下 {orphan["total"]} 个实际文件里，'
                f'{len(orphan["extra"])} 个在 punch_map 里查无此账；'
                f'首条 {orphan["extra"][0]}'
                + (f'（另有 {len(orphan["extra"]) - 1} 个，见报告 {r2}）'
                   if len(orphan['extra']) > 1 else '')
                + '。无账文件的来路一般是：本轮判**拒收**的册被拷了下来、上一轮落位改名旧文件没清、'
                  '或有人手工往落位根里塞了东西。它们两本账都不认领——清理时不敢删、发布还跟着打包，'
                  '必须当场认领或清走，不许交付。')
        if audit['missing'] or audit['ghost']:
            raise BridgeError(
                f'🔴 守恒闸 G4 失守（审的是{audit["scope"]}）：'
                f'punch_map 资产落位 {audit["pm"]} 条 vs files_json 指到 {audit["fj"]} 条；'
                f'失联 {len(audit["missing"])} 条'
                + (f'（首条 {audit["missing"][0]}）' if audit['missing'] else '')
                + f'、幽灵 {len(audit["ghost"])} 条'
                + (f'（首条 {audit["ghost"][0]}）' if audit['ghost'] else '')
                + '。失联=资产登记了却没册指向它'
                + ('（增量复吃漏挂，加 --apply 重跑本桥自动补挂）；'
                   if args.apply else
                   '——算的是**计划态**，所以这些是加 --apply 也补不掉的（该资产没进本轮规划：'
                   '源行没了/源文件缺了/所属册没吃进来），需人工核对；')
                + f'幽灵=files_json 指着没登记的落位（人工改过 files_json 或 punch_map 被删行，需人工核对）。'
                  f'明细见报告 {r2}')
        # 🔴 标签取 audit['scope'] 本身，不按 args.apply 现编：编出来的标签哪天与真跑的那把尺
        #    走岔了（多一条分支就够），播报会理直气壮地报错口径，还没人看得出来。
        print(f'守恒闸 G4：punch_map 资产 {audit["pm"]} ≡ files_json {audit["fj"]} ✅'
              f'（{audit["scope"]}）')
        if landed is not None:
            print(f'盘账闸 G5：{landed["total"]} 条落位指针逐条 is_file() 验真 ✅')
        if orphan is not None:
            print(f'盘→账闸 G6：落位根下 {orphan["total"]} 个实际文件逐个反查 punch_map ✅')
        print(f'用时 {int((time.time() - t0) * 1000)} ms｜模式 {mode}')
    except BridgeError as e:
        print(f'🔴 桥闸拦下：{e}', file=sys.stderr)
        return 2
    finally:
        pconn.close()
        kconn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
