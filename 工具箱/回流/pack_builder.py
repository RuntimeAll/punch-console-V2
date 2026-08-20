# -*- coding: utf-8 -*-
"""结构化件 → ingest 包 的确定性转换器（PRD-008 §一② 第4条配套，零 LLM）。

定位：**试卷处理管线（出结构化件）** 与 **ingest_flow（入库过三闸）** 之间的那一段接力，
以前是每次战役现写 scratchpad 脚本（demo 态），本文件把它转正。

  测试数据/试卷/<卷>/结构化.json ──pack_builder build──▶ packs/<卷>.json ──ingest_flow ingest──▶ kb.db

🔴 四条硬纪律（全部是闸，不是注释）：
  ① **零 LLM**：只做机械映射（字典翻译 / kg resolve / prov 组键 / figure 注入），
     一个判断都不问模型——同一份结构化件跑一百遍出同一个包（字节级可复算）。
  ② **不硬挂不编造**：考点名走 kg_tool 的 resolve 通路（名字精确→别名精确→LIKE兜底），
     只有「名字/别名精确且唯一命中」才硬挂；LIKE 兜底单命中要 --accept-like 显式放行；
     多命中/零命中一律不挂，进低置信清单（题号+原名+候选）交人裁。
  ③ **不产半残包**：含图题没给 figure manifest ⇒ **整题滞留**（进待图清单），
     绝不产出「图没了但题进库了」的半残题——老区图丢了没人发现，题就永远错着。
  ④ **守恒闸**：输入题数 == 包内题数 + 滞留题数，不平**拒转**（一个字节都不写）。

用法：
  # ① 先出 figure manifest 骨架（含图题的题号已预填，人/上游把 sha256+rel_path 填上）
  python pack_builder.py manifest 测试数据/七上试卷/卷7/结构化.json --out 卷7-figures.json

  # ② 转换（--db 只读：查字典值域 / resolve 考点 / 撞库预检 / asset 悬空预检）
  python pack_builder.py build 测试数据/七上试卷/卷7/结构化.json \
      --db 知识库/kb.db --out packs/卷7.json --report packs/卷7-清单.md \
      --textbook-ver 浙教 --ver-conf 高 --ver-basis "卷面自证【浙教版】/章节指纹" --ver-tier "一级·浙教" \
      [--figure-manifest 卷7-figures.json] [--accept-like]

  # ③ 入库（本工具不碰库；写动作全归 ingest_flow）
  python 工具箱/回流/ingest_flow.py check  packs/卷7.json --db <库>
  python 工具箱/回流/ingest_flow.py ingest packs/卷7.json --db <库>

退出码：0=全量进包；1=有滞留（包已出，滞留清单在报告里）；2=拒转（守恒不平/入参非法，未写任何文件）。
"""
import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import validate_blocks  # noqa: E402  （只 import，闸的正本在 gates.py）

ROOT = Path(__file__).resolve().parents[2]

# ── prov 规范键（结构化件契约固定八键，键名与序照 测试数据/七上试卷/*/目检.md）──
PROV_8 = ('来源', '卷', '题号', '页', '卷名', '大题', '卷面分值', '页文件')
# ── 教材版本治理四键（迁移记录 2026-08-20 窗E/窗F 落库口径）──────────────
PROV_VER = ('教材版本', '版本置信', '版本判定依据', '版本使用级')

RE_SHA256 = re.compile(r'^[0-9a-f]{64}$')
RE_WIDTH = re.compile(r'^\s*\d+(?:\.\d+)?\s*(?:%|px|pt|mm|cm|em|rem)\s*$')
RE_MINUTES = re.compile(r'(\d+)')


class Refuse(Exception):
    """拒转（守恒不平 / 入参非法）——一个字节都不写。"""


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def rel_of(p):
    """任意路径 → 相对 v2 根的正斜杠相对路径（🔴 文件指针全相对路径）。"""
    s = str(p).replace('\\', '/').strip()
    try:
        q = Path(s)
        if q.is_absolute():
            s = str(q.resolve().relative_to(ROOT)).replace('\\', '/')
    except Exception:                                   # noqa: BLE001 —— 不在根下=原样留证，由闸去报
        pass
    return s


# ══════════════════════════════════════════════════════════════════════
# 一、结构化件标准态归一（两派顶层键 → 唯一标准态）
# ══════════════════════════════════════════════════════════════════════
# 标准态（SKILL.md 契约定版 2026-08-20）：
#   卷名 / 卷 / 来源 / source_kind / 页数 / 页文件[数组] / 卷面{} / 题目[] / 守恒{}
# 兼容读的历史别名（只读不写，产新件一律用标准键）：
TOP_ALIAS = {
    '卷': ('卷', '卷目录'),
    '卷面': ('卷面', '卷头'),
}


def normalize_top(raw, path):
    """两派顶层键归一到标准态。返回 (std, diffs)；diffs = 本件与标准态的差异如实记录。"""
    diffs = []
    std = {}

    std['卷名'] = raw.get('卷名')
    for key, cands in TOP_ALIAS.items():
        hit = next((c for c in cands if c in raw), None)
        if hit and hit != key:
            diffs.append(f'顶层键 {hit!r} = 标准键 {key!r} 的历史别名（已兼容读）')
        std[key] = raw.get(hit) if hit else None
    std['来源'] = raw.get('来源') or str(Path(path).parent).replace('\\', '/')
    std['source_kind'] = raw.get('source_kind')
    std['页数'] = raw.get('页数')

    # 页文件：卷7 = 字典 {"1": 相对路径}；卷8 = 数组 [{页,文件,相对路径}] ⇒ 标准态取数组
    pf = raw.get('页文件')
    pages = {}
    if isinstance(pf, dict):
        diffs.append('页文件 = 字典态 {页号: 路径}（标准态为数组 [{页,文件,相对路径}]，已兼容读）')
        for k, v in pf.items():
            pages[str(k)] = rel_of(v)
    elif isinstance(pf, list):
        for e in pf:
            if isinstance(e, dict):
                pages[str(e.get('页'))] = rel_of(e.get('相对路径') or e.get('文件'))
    std['页文件'] = pages

    # 卷面：卷7 卷头{标题,副标题,考查范围,时间,满分}；卷8 卷面{满分,考试时间分钟,教材版本,范围,卷型}
    cover = std.get('卷面') or {}
    mins = cover.get('考试时间分钟')
    if mins is None and cover.get('时间'):
        m = RE_MINUTES.search(str(cover['时间']))
        mins = int(m.group(1)) if m else None
        diffs.append(f'卷面时长写作 {cover["时间"]!r}（标准态 考试时间分钟={mins}），已归一')
    std['卷面归一'] = {'标题': cover.get('标题') or std['卷名'], '满分': cover.get('满分'),
                       '考试时间分钟': mins, '教材版本': cover.get('教材版本'),
                       '范围': cover.get('范围') or cover.get('考查范围'), '卷型': cover.get('卷型')}
    std['题目'] = raw.get('题目') or []
    std['守恒'] = raw.get('守恒') or {}
    if not std['题目']:
        raise Refuse(f'🔴 {path}：题目数组为空——没有可转的题')
    if not std['卷']:
        raise Refuse(f'🔴 {path}：顶层缺 卷/卷目录 键——prov「卷」键无来源，不猜')

    # 题目层键差异（卷7 逐题带 来源/source_kind；卷8 不带，回落顶层）
    q0 = std['题目'][0]
    for k in ('来源', 'source_kind'):
        if k not in q0:
            diffs.append(f'题目层无 {k!r} 键（卷7 派有），已回落顶层/CLI')
    return std, diffs


# ══════════════════════════════════════════════════════════════════════
# 二、考点 resolve（kg_tool 同一通路：名字精确 → 别名精确 → LIKE 兜底，只认叶子）
# ══════════════════════════════════════════════════════════════════════
def _leaves_only(conn, ids):
    return [i for i in ids if conn.execute(
        'SELECT 1 FROM kp k WHERE k.id=? AND k.status!=? AND NOT EXISTS'
        '(SELECT 1 FROM kp c WHERE c.parent_id=k.id)', (i, '退役')).fetchone()]


def kp_path(conn, kid):
    parts, cur = [], kid
    while cur:
        row = conn.execute('SELECT name, parent_id FROM kp WHERE id=?', (cur,)).fetchone()
        if not row:
            break
        parts.append(row[0])
        cur = row[1]
    return '/'.join(reversed(parts))


def resolve_word(conn, word):
    """→ (via, hits)。via ∈ 名字精确|别名精确|LIKE兜底|零命中。hits 只含现行叶子。"""
    w = str(word).strip()
    if re.fullmatch(r'\d{6,15}', w):
        return ('id直填', _leaves_only(conn, [w]))
    hits = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name=?', (w,))]
    hits = _leaves_only(conn, list(dict.fromkeys(hits)))
    if hits:
        return ('名字精确', hits)
    hits = [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (w,))]
    hits = _leaves_only(conn, list(dict.fromkeys(hits)))
    if hits:
        return ('别名精确', hits)
    like = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name LIKE ? ORDER BY id', (f'%{w}%',))]
    like += [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias LIKE ?', (f'%{w}%',))]
    hits = _leaves_only(conn, list(dict.fromkeys(like)))
    return ('LIKE兜底' if hits else '零命中', hits)


def dict_label_ok(conn, domain, label):
    """标签能不能翻成库口径码。返回 (code|None, 全部在用标签)。"""
    labels = [r[0] for r in conn.execute(
        'SELECT label FROM dict_item WHERE domain=? AND status=? ORDER BY code', (domain, '在用'))]
    if not label:
        return None, labels
    row = conn.execute('SELECT code FROM dict_item WHERE domain=? AND label=? AND status=?',
                       (domain, label, '在用')).fetchone()
    return (row[0] if row else None), labels


# ══════════════════════════════════════════════════════════════════════
# 三、figure manifest
# ══════════════════════════════════════════════════════════════════════
def has_figure_need(q):
    """本题要不要图：图题标记 或 图字段非空——两者取并（题面图与作答区图都要落位）。"""
    return bool(q.get('图题')) or bool(q.get('图'))


def load_manifest(path):
    """manifest：{"figures": {"6": {...}|[{...}]}} 或直接 {"6": {...}}。
    条目键：rel_path（相对 v2 根，必）/ sha256（64 位十六进制，必）/ width（缺省 CLI）/ 插入行（缺省 1）。"""
    if not path:
        return {}
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    figs = doc.get('figures') if isinstance(doc.get('figures'), dict) else \
        {k: v for k, v in doc.items() if not str(k).startswith('_') and k not in ('卷', '卷名', '来源')}
    out = {}
    for qno, ent in figs.items():
        lst = ent if isinstance(ent, list) else [ent]
        keep = []
        for e in lst:
            if not isinstance(e, dict):
                raise Refuse(f'🔴 manifest 题{qno} 条目非对象：{e!r}')
            if not e.get('rel_path') or not e.get('sha256'):
                continue                                # 骨架未填完 = 视为没给（该题照旧滞留）
            keep.append(e)
        if keep:
            out[str(qno)] = keep
    return out


def check_fig_entry(conn, qno, e, default_width):
    """manifest 单条体检 → (figure_cell, 错误清单)。"""
    errs = []
    sha = str(e.get('sha256') or '').strip().lower()
    rel = rel_of(e.get('rel_path'))
    if not RE_SHA256.match(sha):
        errs.append(f'题{qno} sha256={e.get("sha256")!r} 非法（要 64 位十六进制）')
    if Path(rel).is_absolute() or re.match(r'^[A-Za-z]:', rel) or '..' in rel.split('/'):
        errs.append(f'题{qno} rel_path={rel!r} 不是干净相对路径（🔴 老货架 717 行绝对路径全断）')
    width = str(e.get('width') or default_width)
    if not RE_WIDTH.match(width):
        errs.append(f'题{qno} width={width!r} 非法（要 "46%" 或 "60mm" 这类带单位值）')
    if not (ROOT / rel).exists():
        errs.append(f'题{qno} 图文件不在盘：{rel}')
    if conn is not None:
        row = conn.execute('SELECT rel_path FROM asset WHERE hash=?', (sha,)).fetchone()
        if not row:
            errs.append(f'题{qno} asset {sha[:12]}… 不在 asset 表（先 ingest_flow asset-add 登记，figure 不许悬空）')
        elif rel_of(row[0]) != rel:
            errs.append(f'题{qno} asset 表 rel_path={row[0]!r} ≠ manifest {rel!r}（同 hash 两义，人裁）')
    cell = {'type': 'figure', 'asset': sha, 'width': width}
    return cell, errs


def inject_figures(blocks, cells_with_pos):
    """把 figure 行插进块流（不改原对象）。默认插入行=1（题干首行之后，选项之前）。"""
    rows = [dict(r) for r in blocks.get('rows') or []]
    for at, cell in sorted(cells_with_pos, key=lambda x: x[0], reverse=True):
        at = max(0, min(int(at), len(rows)))
        rows.insert(at, {'cells': [cell]})
    return {'v': blocks.get('v', 2), 'rows': rows}


# ══════════════════════════════════════════════════════════════════════
# 四、逐题转换
# ══════════════════════════════════════════════════════════════════════
def build_item(conn, std, q, args, manifest, ledger):
    """单题 → (item|None, 滞留原因|None)。ledger 收集 kp 映射/低置信/待图等留痕。"""
    qno = str(q.get('题号'))
    hold = []                                          # 滞留原因（非空即滞留）

    # —— 1. 块流：rows 必须带 cells 包层（PRD-008 §一② 第4条契约修正点）——
    blocks = q.get('blocks')
    if not isinstance(blocks, dict) or not isinstance(blocks.get('rows'), list) or not blocks['rows']:
        hold.append('blocks 缺失或 rows 非非空数组')
    else:
        naked = [i for i, r in enumerate(blocks['rows'])
                 if not isinstance(r, dict) or not isinstance(r.get('cells'), list) or not r['cells']]
        if naked:
            hold.append(f'rows{naked} 缺 cells 包层（结构化件契约：rows[].cells[] 两层，禁把块直接摊在 rows 里）')

    # —— 2. figure：含图题必须有 manifest 条目，否则整题滞留（不产半残包）——
    fig_cells = []
    if has_figure_need(q):
        ents = manifest.get(qno)
        if not ents:
            hold.append('含图题但 manifest 无条目（--figure-manifest 补齐后再转）')
            ledger['待图'].append({
                '题号': qno, '图题': bool(q.get('图题')), '图数': len(q.get('图') or []),
                '页': q.get('页'),
                '描述': (q.get('图') or [{}])[0].get('描述') or (q.get('图') or [{}])[0].get('内容描述') or '',
            })
        else:
            for e in ents:
                cell, errs = check_fig_entry(conn if args.verify_asset else None, qno, e, args.figure_width)
                if errs:
                    hold += errs
                else:
                    fig_cells.append((int(e.get('插入行', 1)), cell))

    # —— 3. 字典值域（qtype / difficulty 翻不出就滞留，绝不猜）——
    qtype = args.qtype_map.get(q.get('qtype'), q.get('qtype'))
    diff = args.diff_map.get(q.get('难度建议'), q.get('难度建议'))
    for domain, label, name in (('qtype', qtype, 'qtype'), ('difficulty', diff, '难度建议')):
        code, all_labels = dict_label_ok(conn, domain, label)
        if not code:
            hold.append(f'{name}={label!r} 字典翻不出（在用值域：{all_labels}）')

    # —— 4. 考点：只认精确唯一命中；其余进低置信清单，不硬挂 ——
    kp_ids = []
    for w in (q.get('考点建议') or []):
        via, hits = resolve_word(conn, w)
        rec = {'题号': qno, '原名': w, 'via': via,
               '候选': [{'id': h, '路径': kp_path(conn, h)} for h in hits]}
        if via in ('名字精确', '别名精确', 'id直填') and len(hits) == 1:
            kp_ids.append(hits[0])
            ledger['kp映射'].setdefault(w, {'id': hits[0], '路径': kp_path(conn, hits[0]),
                                            'via': via, '用于': []})['用于'].append(qno)
        elif via == 'LIKE兜底' and len(hits) == 1 and args.accept_like:
            kp_ids.append(hits[0])
            rec['处置'] = 'LIKE兜底挂载（--accept-like 显式放行，仍列低置信待人复核）'
            ledger['低置信'].append(rec)
            ledger['kp映射'].setdefault(w, {'id': hits[0], '路径': kp_path(conn, hits[0]),
                                            'via': via, '用于': []})['用于'].append(qno)
        else:
            # 🔴 处置话术按「真规则」写，别只看 via：多命中就算加了 --accept-like 也不挂
            if len(hits) > 1:
                rec['处置'] = f'不挂（{len(hits)} 个候选，不自动挑；--accept-like 也不放行，改 KG 铸别名或题目包写 id 消歧）'
            elif via == '零命中':
                rec['处置'] = '不挂（KG 先 add-leaf/alias 补翻译，绝不编造 id）'
            else:
                rec['处置'] = '不挂（LIKE 兜底=子串近似，--accept-like 才放行）'
            ledger['低置信'].append(rec)
    kp_ids = list(dict.fromkeys(kp_ids))
    if not kp_ids:
        hold.append('零个考点挂得上（挂不上就不入库，绝不裸题入库）')

    if hold:
        return None, '；'.join(hold)

    # —— 5. prov：规范八键 + 版本四键 + 留痕键 ——
    src_p = q.get('prov') or {}
    page = q.get('页')
    page_file = rel_of(std['页文件'].get(str(page)) or src_p.get('页文件') or '')
    prov = {
        '来源': args.prov_source,
        '卷': std['卷'],
        '题号': qno,
        '页': page,
        '卷名': std['卷名'],
        '大题': q.get('大题'),
        '卷面分值': src_p.get('卷面分值'),
        '页文件': page_file,
    }
    if not args.no_version_keys:
        prov.update({'教材版本': args.textbook_ver, '版本置信': args.ver_conf,
                     '版本判定依据': args.ver_basis, '版本使用级': args.ver_tier})
    for k in ('题源标注', '跨页'):
        if src_p.get(k) is not None:
            prov[k] = src_p[k]
    if q.get('备注'):
        prov['结构化备注'] = q['备注']
    if q.get('低置信'):
        prov['转写低置信'] = True
        if q.get('低置信原因'):
            prov['低置信原因'] = q['低置信原因']
    if q.get('考点置信'):
        prov['考点置信'] = q['考点置信']
    if fig_cells:
        prov['图注入'] = [{'asset': c['asset'], 'width': c['width'], '插入行': at} for at, c in fig_cells]
    # 🔴 这里不写时间戳：包要字节级可复算（跑两遍 diff 为空才叫确定性），时间只落报告
    prov['转换器'] = 'pack_builder'

    conf = args.conf_low if (q.get('低置信') or q.get('考点置信') == '低') else args.conf_high
    item = {
        'blocks': inject_figures(blocks, fig_cells) if fig_cells else blocks,
        'qtype': qtype,
        'difficulty': diff,
        'source_kind': q.get('source_kind') or std.get('source_kind') or args.source_kind,
        'source_raw': f'{args.source_raw_prefix}·{std["卷"]}·{std["卷名"]}·题{qno}',
        'kp': kp_ids,
        'primary_kp': kp_ids[0],
        'prov': prov,
        'confidence': conf,
    }
    # —— 6. 出包前自跑块流闸（不产过不了闸的包）——
    ok, errs = validate_blocks(item['blocks'], is_stem=True)
    if not ok:
        return None, '块流校验器拒收：' + '；'.join(errs[:4])
    return item, None


# ══════════════════════════════════════════════════════════════════════
# 五、命令
# ══════════════════════════════════════════════════════════════════════
def cmd_manifest(args):
    raw = json.loads(Path(args.src).read_text(encoding='utf-8'))
    std, _ = normalize_top(raw, args.src)
    figs = {}
    for q in std['题目']:
        if not has_figure_need(q):
            continue
        qno = str(q.get('题号'))
        ents = []
        for g in (q.get('图') or [{}]):
            ents.append({
                'rel_path': '', 'sha256': '', 'width': args.figure_width, '插入行': 1,
                '_页': g.get('页') or q.get('页'),
                '_页文件': rel_of(g.get('页文件') or std['页文件'].get(str(q.get('页')), '')),
                '_区域': g.get('区域') or g.get('像素区域'),
                '_描述': g.get('描述') or g.get('内容描述') or '',
                '_读图必需': g.get('读图必需'),
            })
        figs[qno] = ents if len(ents) > 1 else ents[0]
    doc = {'卷': std['卷'], '卷名': std['卷名'], '_说明': 'rel_path/sha256 填完才生效；下划线键只是抄给人看的线索',
           'figures': figs}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'figure manifest 骨架 → {args.out}（含图题 {len(figs)} 道：{" ".join(figs)}）')
    print('  🔴 rel_path 相对 v2 根、sha256 与 asset 表一致；填完才注入，没填的题照旧滞留。')
    return 0


def cmd_build(args):
    raw = json.loads(Path(args.src).read_text(encoding='utf-8'))
    std, diffs = normalize_top(raw, args.src)
    if not args.no_version_keys and not all([args.textbook_ver, args.ver_conf, args.ver_basis, args.ver_tier]):
        raise Refuse('🔴 版本四键要么全给（--textbook-ver/--ver-conf/--ver-basis/--ver-tier）'
                     '要么显式 --no-version-keys——版本治理是窗E/窗F 的落库口径，不许半给')
    manifest = load_manifest(args.figure_manifest)
    conn = sqlite3.connect(f'file:{Path(args.db).as_posix()}?mode=ro', uri=True)   # 🔴 只读打开
    ledger = {'kp映射': {}, '低置信': [], '待图': [], '撞库': []}
    items, holds = [], []
    try:
        for q in std['题目']:
            item, why = build_item(conn, std, q, args, manifest, ledger)
            if item is None:
                # 🔴 滞留必须有名有姓：没原因的滞留 = 静默吞题（老区最典型的坏账），拒转
                if not why:
                    raise Refuse(f'🔴 守恒闸：题{q.get("题号")} 既没进包也没给滞留原因'
                                 f'——扔题必留名，拒转')
                holds.append({'题号': str(q.get('题号')), 'qtype': q.get('qtype'), '原因': why})
            else:
                items.append(item)
        # 撞库预检（只报不拦；拦是 ingest_flow 相似前查的活）
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ingest_flow                                                        # noqa: PLC0415
        for it in items:
            mk = ingest_flow.match_key_of(it['blocks'])
            if mk:
                dup = conn.execute('SELECT id FROM question WHERE match_key=? AND status!=?',
                                   (mk, '退役')).fetchone()
                if dup:
                    ledger['撞库'].append({'题号': it['prov']['题号'], '库内题': dup[0]})
    finally:
        conn.close()

    # ── 守恒闸：输入 = 进包 + 滞留，不平拒转（一个字节都不写）──────────────
    n_in, n_ok, n_hold = len(std['题目']), len(items), len(holds)
    if n_in != n_ok + n_hold:
        raise Refuse(f'🔴 守恒闸不平：输入 {n_in} ≠ 进包 {n_ok} + 滞留 {n_hold}——拒转，未写任何文件')
    qnos_in = [str(q.get('题号')) for q in std['题目']]
    qnos_out = [i['prov']['题号'] for i in items] + [h['题号'] for h in holds]
    if sorted(qnos_in) != sorted(qnos_out):
        raise Refuse(f'🔴 守恒闸不平（题号集合不一致）：入 {sorted(qnos_in)} ≠ 出 {sorted(qnos_out)}——拒转')

    pack = {'source_line': args.source_line, 'items': items}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding='utf-8')
    report = write_report(args, std, diffs, items, holds, ledger, n_in)
    print(f'转换 {std["卷"]}｜{std["卷名"]}：输入 {n_in} = 进包 {n_ok} + 滞留 {n_hold} ✅守恒')
    print(f'  包 → {args.out}')
    print(f'  清单 → {report}')
    if ledger['低置信']:
        print(f'  ⚠ 考点低置信 {len(ledger["低置信"])} 条（不硬挂，见清单）：'
              + '、'.join(f'题{r["题号"]}·{r["原名"]}' for r in ledger['低置信'][:8]))
    if holds:
        print('  🔴 滞留：' + '；'.join(f'题{h["题号"]}（{h["原因"][:48]}…）' for h in holds))
    if ledger['撞库']:
        print(f'  ⚠ 撞库预警 {len(ledger["撞库"])} 题：'
              + '、'.join(f'题{d["题号"]}→{d["库内题"]}' for d in ledger['撞库']))
    return 1 if holds else 0


def write_report(args, std, diffs, items, holds, ledger, n_in):
    L = [f'# 转换清单 · {std["卷"]}｜{std["卷名"]}', '',
         f'- 源件：`{rel_of(args.src)}`　→　包：`{rel_of(args.out)}`',
         f'- 转换器：`工具箱/回流/pack_builder.py`（零 LLM，确定性可复算）　时间：{now()}',
         f'- 参照库（只读）：`{rel_of(args.db)}`'
         + (f'　figure manifest：`{rel_of(args.figure_manifest)}`' if args.figure_manifest else '　figure manifest：未给'),
         f'- 版本四键：{"不写（--no-version-keys）" if args.no_version_keys else f"{args.textbook_ver}／{args.ver_conf}／{args.ver_basis}／{args.ver_tier}"}',
         f'- LIKE 兜底考点：{"放行挂载（--accept-like）" if args.accept_like else "不挂（默认）"}', '',
         '## 守恒闸', '',
         f'**输入 {n_in} = 进包 {len(items)} + 滞留 {len(holds)}** ✅', '']
    if diffs:
        L += ['## 源件与标准态的差异（如实记录，不改源件）', ''] + [f'- {d}' for d in diffs] + ['']
    L += ['## 逐题', '', '| 题号 | qtype | 难度 | 考点挂载 | 去向 |', '|---|---|---|---|---|']
    by_no = {i['prov']['题号']: i for i in items}
    hold_no = {h['题号']: h for h in holds}
    for q in std['题目']:
        qno = str(q.get('题号'))
        if qno in by_no:
            it = by_no[qno]
            L.append(f'| {qno} | {it["qtype"]} | {it["difficulty"]} | {" ".join(it["kp"])} | 进包 |')
        else:
            h = hold_no[qno]
            L.append(f'| {qno} | {q.get("qtype")} | {q.get("难度建议")} | — | 🔴 滞留：{h["原因"]} |')
    L += ['', '## 考点映射表（硬挂的）', '', '| 原名 | 叶 id | 全路径 | 通路 | 用于题号 |', '|---|---|---|---|---|']
    for w, m in sorted(ledger['kp映射'].items()):
        L.append(f'| {w} | {m["id"]} | {m["路径"]} | {m["via"]} | {" ".join(m["用于"])} |')
    L += ['', '## 考点低置信清单（🔴 不硬挂不编造，交人裁）', '']
    if ledger['低置信']:
        L += ['| 题号 | 原名 | 通路 | 候选 | 处置 |', '|---|---|---|---|---|']
        for r in ledger['低置信']:
            cand = '<br>'.join(f'`{c["id"]}` {c["路径"]}' for c in r['候选']) or '（无）'
            L.append(f'| {r["题号"]} | {r["原名"]} | {r["via"]} | {cand} | {r.get("处置", "")} |')
    else:
        L.append('（无）')
    L += ['', '## 待图清单（含图题缺 manifest ⇒ 整题滞留）', '']
    if ledger['待图']:
        L += ['| 题号 | 图题 | 图数 | 页 | 图内容 |', '|---|---|---|---|---|']
        for r in ledger['待图']:
            L.append(f'| {r["题号"]} | {r["图题"]} | {r["图数"]} | {r["页"]} | {str(r["描述"])[:80]} |')
    else:
        L.append('（无）')
    L += ['', '## 撞库预警（match_key 与库内题相同；拦不拦由 ingest_flow 相似前查定）', '']
    if ledger['撞库']:
        L += ['| 题号 | 库内题 |', '|---|---|'] + [f'| {d["题号"]} | {d["库内题"]} |' for d in ledger['撞库']]
    else:
        L.append('（无）')
    L += ['', '## 接力命令', '',
          '```powershell',
          f'python 工具箱\\回流\\ingest_flow.py check  {rel_of(args.out)} --db <库>',
          f'python 工具箱\\回流\\ingest_flow.py ingest {rel_of(args.out)} --db <库>',
          '```', '']
    out = args.report or (str(Path(args.out).with_suffix('')) + '-清单.md')
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text('\n'.join(L), encoding='utf-8')
    return out


def main():
    ap = argparse.ArgumentParser(description='结构化件 → ingest 包 的确定性转换器（零 LLM）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    m = sub.add_parser('manifest', help='出 figure manifest 骨架（含图题预填）')
    m.add_argument('src'); m.add_argument('--out', required=True)
    m.add_argument('--figure-width', default='46%')

    b = sub.add_parser('build', help='结构化件 → ingest 包')
    b.add_argument('src')
    b.add_argument('--db', required=True, help='参照库（🔴 只读打开：字典值域/考点 resolve/撞库预检/asset 预检）')
    b.add_argument('--out', required=True)
    b.add_argument('--report', help='转换清单 md（缺省 <out>-清单.md）')
    b.add_argument('--figure-manifest', help='题号→{rel_path,sha256,width,插入行}；不给则含图题整题滞留')
    b.add_argument('--figure-width', default='46%')
    b.add_argument('--verify-asset', action='store_true', default=True,
                   help='校验 manifest 的 hash 在 asset 表且文件在盘（缺省开）')
    b.add_argument('--no-verify-asset', dest='verify_asset', action='store_false')
    b.add_argument('--source-line', default='试卷快录')
    b.add_argument('--source-kind', default='scan', choices=['scan', 'manual', 'model', 'pipeline'])
    b.add_argument('--prov-source', default='试卷快录', help='prov.来源（库口径，缺省 试卷快录）')
    b.add_argument('--source-raw-prefix', default='七上试卷')
    b.add_argument('--textbook-ver'); b.add_argument('--ver-conf')
    b.add_argument('--ver-basis'); b.add_argument('--ver-tier')
    b.add_argument('--no-version-keys', action='store_true', help='显式不写版本四键（自产题等无版本场景）')
    b.add_argument('--conf-high', type=float, default=95)
    b.add_argument('--conf-low', type=float, default=88, help='结构化件标 低置信/考点置信=低 的题用此值')
    b.add_argument('--accept-like', action='store_true', help='LIKE 兜底单命中也挂（仍列低置信待复核）')
    b.add_argument('--label-map', help='标签归一表 JSON：{"qtype":{...},"difficulty":{...}}')

    args = ap.parse_args()
    try:
        if args.cmd == 'manifest':
            sys.exit(cmd_manifest(args))
        lm = json.loads(Path(args.label_map).read_text(encoding='utf-8')) if args.label_map else {}
        args.qtype_map = lm.get('qtype', {})
        args.diff_map = lm.get('difficulty', {})
        sys.exit(cmd_build(args))
    except Refuse as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
