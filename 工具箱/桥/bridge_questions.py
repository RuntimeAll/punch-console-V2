# -*- coding: utf-8 -*-
"""B 题层桥（PRD-003 阶段2）——把 punch-console `资料库.db` 的题机械吃进 kb.db。

🔴 四条本文件的铁律（违一条=坏账）：
  ① **零 LLM**：全文件没有任何模型/AI 调用，规则全是查表 + 正则 + 确定性字符串变换；
  ② **不另开入库路**：题一律经 `工具箱/回流/ingest_flow.py::ingest_one` 入库
     （三闸 + D-21 等级审 + match_key 相似前查原样跑），本桥只负责「转换 + 映射 + 记账」；
  ③ **源库只读**：资料库.db 一律 `file:…?mode=ro` 打开；写只进 kb.db；
  ④ **零向量**：桥的写库循环整个跑在一个 `BEGIN` 事务里，事务内**绝不调 `ingest_flow.autovec`**——
     它内部的 `embed_tool.save_vecs` 收尾有一句 `conn.commit()`，在事务里调 = 把 dry-run 半路
     插入的题一起提交，「dry-run 零写入」当场变成真写库。向量由收尾显式跑 `embed_tool.py build` 补。

范围（口径写死在 SQL 里，改口径先改这三行）：
  · `answer` 非空                     —— 无答案的题不入库（PRD-003 §4 待办1）
  · `doc_id NOT IN (11, 12)`          —— 三升四每日一练两册 620 题 answer 全空，整册不入
  · 其余 14 册 2948 题为本桥的全集

三堆账（互斥且穷尽，三堆相加 == 全集）：
  待入-规则未覆盖 → 块流转换规则表覆盖不到的题（HTML/SVG 混排等），不猜不入
  待入-考点未挂   → 考点为空 或 任一考点名 resolve 不到「现行叶子」，按叶子闸纪律不入
  应吃             → 两关都过，走 ingest_one 入库

🔴 **本桥只吃题，一张卷都不建**（paper/paper_item 零写入，见 PRD-003 待办「历史册载体重建」）：
   载体重建是一件独立的设计活（layout 的 sections 从哪来、部分吃进的卷能不能盖「定稿」、
   铺枝后重跑往定稿卷追加算不算改稿、跨天同题与组卷查重闸怎么共处），机械桥答不了这四问，
   答不了就不许写——写了就是假账。
   代价是**原料必须一次留够**：每题 prov_json 带全 punch_doc/punch_day/punch_section/punch_seq
   （＋ punch_question 反查源 id），日后重建载体不必回源库重查，也不怕源库再变。

幂等（可重入）双保险：
  · `punch_map(kind='question', punch_id=<资料库 question.id>)` 已有 → 整题跳过；
  · 同 match_key 的题（源库内 279 组重复题面，全在册内、答案零冲突）→ 复用既有 kb 题，
    只补 punch_map 一行，不再建第二条 question；
  · 剩下的交给 ingest_one 自己的 match_key 相似前查（撞库即拒，不静默）。

用法（默认 dry-run，只出账不写库）：
  python bridge_questions.py --punch <资料库.db> --kb <kb.db>
  python bridge_questions.py --punch <资料库.db> --kb <kb.db> --apply
  python bridge_questions.py --punch <资料库.db> --kb <kb.db> --survey   # 只survey块形，供改规则表
"""
import argparse
import collections
import json
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]          # <v2根>
sys.path.insert(0, str(ROOT / '工具箱' / '库'))
sys.path.insert(0, str(ROOT / '工具箱' / '回流'))
import ingest_flow                                   # noqa: E402  🔴 入库唯一门
from gates import LeafKpError, assert_leaf_kp        # noqa: E402

DEFAULT_PUNCH = ROOT / '知识库' / '资料库.db'
DEFAULT_KB = ROOT / '知识库' / 'kb.db'
REPORT_DIR = ROOT / '记录' / 'PRD-003吃库'
BRIDGE_DIR = Path(__file__).resolve().parent

EXCLUDE_DOCS = (11, 12)          # answer 全空的三升四两册
SOURCE_LINE = 'PRD-003·资料库合并吃库'
CONFIDENCE = 95                  # 源库 question.实算 全库='绿'（机器验算过），据此给 95；非绿一律不入


# ══════════════════════════════════════════════════════════════════════
# 一、块流转换规则（🔴 确定性：同一输入永远同一输出，没有任何"看情况"）
# ══════════════════════════════════════════════════════════════════════
CJK_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')
HTML_RE = re.compile(r'<[A-Za-z/!][^>]*>')
LATEX_RE = re.compile(r'\\[A-Za-z]+|\\[{}\[\]|,;!\s]')
PAREN_RE = re.compile(r'\\\(|\\\)')
DIGIT_RE = re.compile(r'[0-9]')
# 数学安全字符集：出了这个集合就不是"整段可以塞进 $…$ 的算式"（全角符号/○/中文一律出局）
MATH_SAFE = set(
    '0123456789'
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    '+-*/=<>()[]{}.,;:!?\'"^_|\\%~& \t°'
)

# 🔴 题面禁指令词：清单式机械剥前缀（栏目名/指令词属载体不属题面）
INSTRUCTION_PREFIXES = (
    '分解：', '看图列式：', '计算：', '口算：', '脱式计算：', '简便计算：',
    '解方程：', '列式计算：', '填空：', '直接写得数：', '怎样简便怎样算：',
)

SHAPE_DESC = {
    'bare_math': '裸算式（无中文、字符全在数学安全集）→ 整段包 $…$',
    'paren': '源用 \\(…\\) 行内公式 → 机械换成 $…$（文本段不得残留反斜杠）',
    'plain': '纯文字/全角符号题（无 LaTeX 标记）→ 原样不包',
    'math_head_text_tail': '「算式 + 中文尾巴」（如「\\frac{1}{3} 的相反数是」）→ 只包算式头',
    'html': '含 HTML/SVG 标签 —— 规则不覆盖（配图应走 figure 块+asset，本卡不做）',
    'dollar': '源里已经带 $ —— 规则不覆盖（不重包、也不敢当纯文本）',
    'unsupported': '中文与 LaTeX 交错且不止一次转折 —— 规则不覆盖，不猜切分点',
    'empty': '空串 —— 规则不覆盖',
}

# 规则表：(doc_id, 题型) → (题面允许的形, 答案允许的形[, 题面强制形, 答案强制形])
# 🔴 白名单式：形不在表里 = 这册这题型出现了没见过的写法 ⇒ 落待入清单人审，绝不顺手放行。
# 🔴 「强制形」只允许填 'plain'（= 原样不包公式，恒等变换，永远无损）。它的唯一用途是
#    压掉「同一册同一题型里有的包公式有的不包」的分裂输出——如 3204 幼小衔接的
#    「3 分成 1 和 ___」与「___ 分成 2 和 3」本是同一族题，整族按纯文字走才是一致的。
FORCE_OK = ('plain',)
RULE_TABLE = {
    (2062, '口算'): ({'bare_math'}, {'bare_math'}),
    (2062, '计算'): ({'bare_math'}, {'bare_math'}),
    (2063, '计算'): ({'bare_math'}, {'bare_math'}),
    (2064, '口算'): ({'bare_math', 'math_head_text_tail'}, {'bare_math'}),
    (2064, '计算'): ({'bare_math'}, {'bare_math'}),
    (2065, '口算'): ({'bare_math'}, {'bare_math'}),
    (2065, '计算'): ({'bare_math'}, {'bare_math'}),
    (2066, '计算'): ({'bare_math'}, {'bare_math'}),
    (2067, '计算'): ({'bare_math'}, {'bare_math'}),
    (2068, '口算'): ({'bare_math'}, {'bare_math'}),
    (2068, '计算'): ({'bare_math'}, {'bare_math'}),
    (2069, '计算'): ({'bare_math'}, {'bare_math'}),
    (2070, '计算'): ({'bare_math'}, {'bare_math'}),
    (2071, '计算'): ({'bare_math'}, {'bare_math'}),
    (2072, '口算'): ({'bare_math'}, {'bare_math'}),
    (2072, '计算'): ({'bare_math'}, {'bare_math'}),
    (2801, '计算'): ({'bare_math'}, {'bare_math'}),
    # 幼小衔接整册按纯文字走：题面里的 3/1/2 是「数一数」的量词不是算式，包 $ 反而分裂版式
    (3204, '5以内的分解'): ({'plain', 'math_head_text_tail'}, {'bare_math'}, 'plain', None),
    (3204, '10以内的数字比大小'): ({'plain'}, {'plain'}),
    (3204, '10以内巧填符号'): ({'plain'}, {'plain'}),
    (3204, '10以内的加减法'): ({'plain'}, {'bare_math'}),
    (3204, '6以内的加减法看图列式'): ({'plain'}, {'plain'}),
    (4010, 'oral'): ({'bare_math'}, {'bare_math'}),
    (4010, 'expr'): ({'bare_math'}, {'bare_math'}),
    (4010, 'equation'): ({'bare_math'}, {'bare_math'}),
    (4010, 'fill'): ({'paren', 'plain'}, {'paren'}),
    (4010, 'word'): ({'paren'}, {'bare_math'}),
    (4010, 'word_multi'): ({'paren'}, {'paren'}),
}

# 题型 → kb dict_item(domain='qtype') 的 label（机械查表，表外一律落待入）
QTYPE_MAP = {
    '计算': '计算题', '口算': '计算题', 'expr': '计算题', 'oral': '计算题',
    'equation': '计算题', '10以内的加减法': '计算题',
    'fill': '填空题', '5以内的分解': '填空题', '10以内的数字比大小': '填空题',
    '10以内巧填符号': '填空题', '6以内的加减法看图列式': '填空题',
    'word': '应用题', 'word_multi': '应用题',
}

# 来源 → source_kind（有序子串规则，命中即停；全不命中 ⇒ 落待入不猜）
SOURCE_KIND_RULES = (
    ('DSL', 'model', '来源含「DSL」= DSL 出题路径'),
    ('出题器', 'model', '来源含「出题器」= 生成器出题'),
    ('自编', 'manual', '来源含「自编」= 人（agent）手写题'),
    ('母题=', 'model', '来源含「母题=」= 母题参数化平行改编，机器出题路径'),
)


def classify(s):
    """字符串 → 形（shape）。纯函数，无状态，无 IO。"""
    if s is None or not str(s).strip():
        return 'empty'
    s = str(s)
    if HTML_RE.search(s):
        return 'html'
    if '$' in s:
        return 'dollar'
    if PAREN_RE.search(s):
        return 'paren'
    m = CJK_RE.search(s)
    if not m:
        if set(s) <= MATH_SAFE and (DIGIT_RE.search(s) or LATEX_RE.search(s)):
            return 'bare_math'
        return 'plain'
    head, tail = s[:m.start()], s[m.start():]
    if ('\\' not in tail and '$' not in tail and head.strip()
            and set(head) <= MATH_SAFE and (DIGIT_RE.search(head) or LATEX_RE.search(head))):
        return 'math_head_text_tail'
    if not LATEX_RE.search(s):
        return 'plain'
    return 'unsupported'


def _paren_to_dollar(s):
    """`\\(…\\)` → `$…$`；成对性与「文本段不得残留反斜杠」都验，违一条即 (None, 原因)。"""
    marks = PAREN_RE.findall(s)
    for i, mk in enumerate(marks):
        want = '\\(' if i % 2 == 0 else '\\)'
        if mk != want:
            return None, f'\\( \\) 不成对（第 {i + 1} 个标记是 {mk!r}，应为 {want!r}）'
    if len(marks) % 2:
        return None, f'\\( \\) 数量为奇数（{len(marks)} 个）'
    out = s.replace('\\(', '$').replace('\\)', '$')
    segs = out.split('$')
    for i, seg in enumerate(segs):
        if i % 2 == 0 and '\\' in seg:
            return None, f'公式外的文本段仍带反斜杠：{seg.strip()[:30]!r}'
    return out, None


def to_md(s, shape):
    """按形做确定性变换 → markdown（md + $LaTeX$）。返回 (md, 原因|None)。"""
    s = str(s)
    if shape == 'bare_math':
        return '$' + s.strip() + '$', None
    if shape == 'plain':
        return s.strip(), None
    if shape == 'paren':
        return _paren_to_dollar(s.strip())
    if shape == 'math_head_text_tail':
        m = CJK_RE.search(s)
        head, tail = s[:m.start()].strip(), s[m.start():].strip()
        return '$' + head + '$ ' + tail, None
    return None, f'形 {shape!r} 没有确定性变换（不猜）'


def strip_instruction(stem):
    """机械剥题面指令词前缀。返回 (剥后文本, 剥掉的前缀|None)。"""
    t = stem.lstrip()
    for p in INSTRUCTION_PREFIXES:
        if t.startswith(p):
            return t[len(p):].lstrip(), p
    return stem, None


def blocks_of(md, role):
    return {'v': 2, 'rows': [{'cells': [{'type': 'text', 'role': role, 'md': md}]}]}


def source_kind_of(src):
    for key, kind, why in SOURCE_KIND_RULES:
        if key in (src or ''):
            return kind, why
    return None, f'来源 {src!r} 不匹配任何 source_kind 规则'


# ══════════════════════════════════════════════════════════════════════
# 二、考点映射（机械对 kp.name / kp_alias.alias，精确 + 去空格；不猜不模糊匹配）
# ══════════════════════════════════════════════════════════════════════
def _norm(w):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(w or '')))


class KpResolver:
    """名 → 现行叶子 id。命中口径：kp.name 或 kp_alias.alias，精确匹配 或 去空白后匹配。

    🔴 只认「恰一个现行叶子」：0 命中 / 多命中 / 命中的不是叶子（章节级）都算未命中，
       未命中的题不入库（考点叶子闸纪律，老区 62% 挂章级 = 学情分母失真）。
    """

    def __init__(self, conn):
        self.conn = conn
        self.cache = {}
        self.by_norm = collections.defaultdict(set)
        for kid, name in conn.execute('SELECT id, name FROM kp'):
            self.by_norm[_norm(name)].add(kid)
        for kid, alias in conn.execute('SELECT kp_id, alias FROM kp_alias'):
            self.by_norm[_norm(alias)].add(kid)

    def resolve(self, word):
        """→ (leaf_id|None, 原因|None)"""
        if word in self.cache:
            return self.cache[word]
        hits = sorted(self.by_norm.get(_norm(word), ()))
        leaves, blocked = [], []
        for h in hits:
            try:
                assert_leaf_kp(self.conn, h)
                leaves.append(h)
            except LeafKpError as e:
                blocked.append(f'{h}:{str(e).split("——")[0].strip()}')
        if len(leaves) == 1:
            out = (leaves[0], None)
        elif not hits:
            out = (None, '零命中（kp.name / kp_alias.alias 都没有这个名）')
        elif not leaves:
            out = (None, '命中了但都不是现行叶子 → ' + '；'.join(blocked))
        else:
            out = (None, f'多命中 {leaves}——不自动挑，先并叶或补别名消歧')
        self.cache[word] = out
        return out


def parse_kp(raw):
    """考点列 → 名字数组。返回 (names, 原因|None)。"""
    if raw is None or not str(raw).strip():
        return [], '源库考点为空'
    try:
        v = json.loads(raw)
    except Exception as e:
        return [], f'考点列不是合法 JSON：{e}'
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list) or not v:
        return [], f'考点列不是非空数组：{raw!r}'
    names = [str(x).strip() for x in v if str(x).strip()]
    return names, (None if names else '考点数组去空后为空')


# ══════════════════════════════════════════════════════════════════════
# 三、主流程
# ══════════════════════════════════════════════════════════════════════
def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def open_punch(path):
    """🔴 源库一律只读打开（对正本和副本一视同仁）。"""
    p = Path(path).resolve()
    if not p.exists():
        sys.exit(f'🔴 源库不存在：{p}')
    conn = sqlite3.connect('file:' + p.as_posix() + '?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def open_kb(path):
    p = Path(path).resolve()
    if not p.exists():
        sys.exit(f'🔴 kb.db 不存在：{p}（先跑 工具箱/库/init_db.py）')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def load_rows(punch, only_docs=None):
    """only_docs：试刀用的源册白名单（punch doc id 集合）。🔴 给了它就是部分跑，
    报告一律走 .partial 通道不碰正本——保护逻辑与 --limit 同一条（emit 的 partial 标记）。"""
    extra = ''
    if only_docs:
        extra = f'AND doc_id IN ({",".join(str(int(x)) for x in only_docs)}) '
    sql = (
        'SELECT id, doc_id, day, section, seq, stem, answer, steps, 考点, 题型, 难度, 来源, 实算 '
        'FROM question '
        "WHERE answer IS NOT NULL AND TRIM(answer)<>'' "
        f'AND doc_id NOT IN ({",".join(str(x) for x in EXCLUDE_DOCS)}) '
        + extra +
        'ORDER BY id'
    )
    return [dict(r) for r in punch.execute(sql)]


def _forced(shape, force, trace, side):
    """强制形只对「本来就能转」的形生效，且只能强制成 'plain'（恒等变换）。
    html/dollar/unsupported/empty 这些「规则不覆盖」的形一律不许被强制掩盖。"""
    if not force or shape in ('html', 'dollar', 'unsupported', 'empty'):
        return shape
    if force not in FORCE_OK:
        raise SystemExit(f'🔴 RULE_TABLE 强制形只允许 {FORCE_OK}，实际 {force!r}')
    if force != shape:
        trace[side + '强制形'] = force
    return force


# 🔴 载体重建原料：本桥不建 paper/paper_item，这五个字段就是日后重建载体的全部输入。
#    键名单名制（punch_* 前缀）；值一律字符串（None 保留 None，别拿 '' 冒充「源库没写」）。
PROV_CARRIER_KEYS = ('punch_doc', 'punch_day', 'punch_section', 'punch_seq')


def _s(v):
    return None if v is None else str(v)


def prov_of(row):
    """一行源题 → prov dict。载体四件（doc/day/section/seq）+ 反查源 id + 源库来源原文。"""
    return {
        'punch_doc': _s(row['doc_id']),
        'punch_day': _s(row['day']),
        'punch_section': _s(row['section']),
        'punch_seq': _s(row['seq']),
        'punch_question': _s(row['id']),
        '来源': row['来源'],
    }


def build_item(row):
    """一行源题 → (ingest 题目包 item, 转换留痕 dict, 拒收原因清单)。零 LLM，全查表。"""
    trace, errs = {}, []
    doc_id, qtype_raw = row['doc_id'], row['题型']

    rule = RULE_TABLE.get((doc_id, qtype_raw))
    if rule is None:
        errs.append(f'规则表无 (doc={doc_id}, 题型={qtype_raw!r}) 这一格——没见过的册/题型组合')
        return None, trace, errs
    stem_ok, ans_ok, stem_force, ans_force = (tuple(rule) + (None, None))[:4]

    # ── 题面 ──
    stem_raw, stripped = strip_instruction(str(row['stem'] or ''))
    trace['剥前缀'] = stripped
    s_shape = classify(stem_raw)
    trace['题面形'] = s_shape
    if s_shape not in stem_ok:
        errs.append(f'题面形={s_shape}（{SHAPE_DESC.get(s_shape, "?")}）不在本册本题型允许集 {sorted(stem_ok)}')
    stem_md, why = to_md(stem_raw, _forced(s_shape, stem_force, trace, '题面'))
    if why:
        errs.append(f'题面转换失败：{why}')

    # ── 答案 ──
    ans_raw = str(row['answer'] or '')
    a_shape = classify(ans_raw)
    trace['答案形'] = a_shape
    if a_shape not in ans_ok:
        errs.append(f'答案形={a_shape}（{SHAPE_DESC.get(a_shape, "?")}）不在本册本题型允许集 {sorted(ans_ok)}')
    ans_md, why = to_md(ans_raw, _forced(a_shape, ans_force, trace, '答案'))
    if why:
        errs.append(f'答案转换失败：{why}')

    # ── 字段映射 ──
    qtype_label = QTYPE_MAP.get(qtype_raw)
    if qtype_label is None:
        errs.append(f'题型 {qtype_raw!r} 不在 QTYPE_MAP——不猜题型')
    src_kind, why_src = source_kind_of(row['来源'])
    if src_kind is None:
        errs.append(why_src)
    if (row['实算'] or '') != '绿':
        errs.append(f'源库 实算={row["实算"]!r} 非「绿」——未过机器验算的题不给 {CONFIDENCE} 置信')
    # steps 全库为空 ⇒ 不建解析块（有值反而说明源库变了，如实拒收）
    if str(row['steps'] or '').strip():
        errs.append('源库 steps 非空——本桥按「steps 全空」口径写的，出现有值一律人审')

    if errs:
        return None, trace, errs

    item = {
        'id': f'qpunch{int(row["id"]):08d}',            # 🔴 id 全链路字符串，且可反查源 id
        'blocks': blocks_of(stem_md, '题面'),
        'answer_blocks': blocks_of(ans_md, '答案'),
        'qtype': qtype_label,
        'difficulty': row['难度'],                      # 源库全空 ⇒ None ⇒ diff_code 留空（不编难度）
        'source_kind': src_kind,
        'source_raw': row['来源'],
        # 🔴 载体原料一次留够：本桥不建 paper，日后重建载体全靠这五个字段（缺一条就得回源库重查）
        'prov': prov_of(row),
        'confidence': CONFIDENCE,
        'mother_qid': None,
        'variant_op': None,
    }
    return item, trace, []


def run(args):
    t0 = time.time()
    punch = open_punch(args.punch)
    kb = open_kb(args.kb)
    only_docs = None
    if getattr(args, 'only_doc', None):
        only_docs = [int(x) for x in str(args.only_doc).split(',') if x.strip()]
    rows = load_rows(punch, only_docs)
    if args.limit:
        rows = rows[:args.limit]
    # 部分跑标记（--limit / --only-doc 任一即部分跑）：报告走 .partial 不碰正本
    part_tag = None
    if args.limit:
        part_tag = f'--limit {args.limit}'
    if only_docs:
        part_tag = (part_tag + ' ' if part_tag else '') + f'--only-doc {args.only_doc}'

    # ── survey 模式：只统计块形，供核对/改规则表 ──────────────────────
    if args.survey:
        obs = collections.defaultdict(collections.Counter)
        for r in rows:
            st, _ = strip_instruction(str(r['stem'] or ''))
            obs[(r['doc_id'], r['题型'], '题面')][classify(st)] += 1
            obs[(r['doc_id'], r['题型'], '答案')][classify(str(r['answer'] or ''))] += 1
        print(f'survey：{len(rows)} 题')
        for k in sorted(obs, key=lambda x: (x[0], str(x[1]), x[2])):
            allowed = RULE_TABLE.get((k[0], k[1]))
            allow = (allowed[0] if k[2] == '题面' else allowed[1]) if allowed else None
            forced = ((tuple(allowed) + (None, None))[2 if k[2] == '题面' else 3]) if allowed else None
            if forced:
                allow = set(allow) | {forced}
            bad = [s for s in obs[k] if allow is None or s not in allow]
            flag = '  🔴 表外形：' + ','.join(bad) if bad else ''
            print(f'  {k[0]} {k[1]!r:<26}{k[2]} {dict(obs[k])}{flag}')
        return {'survey': {k: dict(v) for k, v in obs.items()}, 'code': 0}

    resolver = KpResolver(kb)
    docs = {r['id']: dict(r) for r in punch.execute('SELECT * FROM doc')}

    # ── 已吃过的（幂等第一道）────────────────────────────────────────
    mapped = {pid: kid for pid, kid in kb.execute(
        "SELECT punch_id, kb_id FROM punch_map WHERE kind='question'")}

    bucket_rule, bucket_kp, plan = [], [], []
    kp_hit, kp_miss = {}, {}
    stripped_log = collections.Counter()

    for r in rows:
        item, trace, errs = build_item(r)
        if errs:
            bucket_rule.append((r, trace, errs))
            continue
        if trace.get('剥前缀'):
            stripped_log[trace['剥前缀']] += 1
        names, why = parse_kp(r['考点'])
        if why:
            bucket_kp.append((r, [], [why]))
            continue
        ids, miss = [], []
        for nm in names:
            kid, e = resolver.resolve(nm)
            if kid:
                ids.append(kid)
                kp_hit[nm] = kid
            else:
                miss.append(f'{nm}：{e}')
                kp_miss[nm] = e
        if miss:
            bucket_kp.append((r, names, miss))
            continue
        ids = list(dict.fromkeys(ids))
        item['kp'] = ids
        item['primary_kp'] = ids[0]
        plan.append((r, item, trace))

    total = len(rows)
    print(f'【B 题层桥】源题全集 {total}（answer 非空 · 排除 doc {EXCLUDE_DOCS}）')
    print(f'  待入-规则未覆盖 {len(bucket_rule)}')
    print(f'  待入-考点未挂   {len(bucket_kp)}')
    print(f'  应吃            {len(plan)}')
    print(f'  三堆合计 {len(bucket_rule) + len(bucket_kp) + len(plan)}'
          f'  {"== 全集 ✓" if len(bucket_rule) + len(bucket_kp) + len(plan) == total else "🔴 对不上"}')
    if stripped_log:
        print('  机械剥指令词前缀：' + '  '.join(f'{k!r}×{v}' for k, v in stripped_log.most_common()))
    print(f'  考点名命中 {len(kp_hit)} / 未命中 {len(kp_miss)}')
    already = sum(1 for r, _, _ in plan if str(r['id']) in mapped)
    print(f'  其中 punch_map 已有映射（本轮跳过）{already}')

    # ── 出四份件（dry-run 也出，账先给人看）────────────────────────────
    # 🔴 --limit 是部分跑：四份件一律改写 <正本名>.partial.md，正本一个都不覆盖
    written = write_reports(punch, bucket_rule, bucket_kp, resolver, docs, part_tag)

    stats = {'新建': 0, '复用既有题': 0, '已映射跳过': already, '闸拒收': 0}
    rejects = []

    kb.execute('BEGIN')
    try:
        for r, item, trace in plan:
            pid = str(r['id'])
            if pid in mapped:
                continue
            mk = ingest_flow.match_key_of(item['blocks'])
            dup = kb.execute("SELECT id FROM question WHERE match_key=? AND status!='退役'",
                             (mk,)).fetchone() if mk else None
            if dup:
                # 源库册内重复题面（幼小衔接刻意重复练）——复用既有题，只补映射，不建第二条
                kb.execute('INSERT OR REPLACE INTO punch_map(kind,punch_id,kb_id,note,created_at) '
                           'VALUES (?,?,?,?,?)',
                           ('question', pid, dup[0], f'复用既有题（match_key 同）doc={r["doc_id"]}', now()))
                mapped[pid] = dup[0]
                stats['复用既有题'] += 1
                continue
            qid, errs, grade = ingest_flow.ingest_one(kb, item, r['id'], allow_dup=False,
                                                      skip_review=False)
            # 🔴🔴 这里绝不许调 ingest_flow.autovec（D 线跨线审查实锤的事务炸弹）：
            #   autovec → embed_tool.save_vecs，而 save_vecs 收尾有一句 `conn.commit()`。
            #   本循环整个跑在上面的 `kb.execute('BEGIN')` 里，那句 commit 会把**本轮已插入的
            #   全部 question/question_kp/punch_map 一起提交**——dry-run 末尾的 rollback 再也
            #   收不回来，「dry-run 零写入」当场变成真写库（且是半截脏账）。
            #   桥的口径是**零向量**：向量不在事务里算，由收尾显式跑 embed_tool.py build 补
            #   （见本函数末尾的「待补」播报）。这也正是「桥零 LLM/零模型」的字面意思。
            if errs:
                stats['闸拒收'] += 1
                rejects.append((r, errs))
                continue
            kb.execute('INSERT OR REPLACE INTO punch_map(kind,punch_id,kb_id,note,created_at) '
                       'VALUES (?,?,?,?,?)',
                       ('question', pid, qid, f'吃库 doc={r["doc_id"]} day={r["day"]} '
                                              f'seq={r["seq"]} 等级={grade["name"]}', now()))
            mapped[pid] = qid
            stats['新建'] += 1

        # 🔴 到此为止：本桥不建 paper/paper_item（见文件头「只吃题，一张卷都不建」）。
        #    载体重建的原料已随 prov_json 逐题落库（punch_doc/day/section/seq）。
        if args.apply:
            kb.commit()
        else:
            kb.rollback()
    except Exception:
        kb.rollback()
        raise

    print()
    # 🔴 dry-run 的口径是「kb.db 零写入」，不是「一个字节都没写」——报告件是照写的，如实列出来。
    print(('【--apply 已写库】' if args.apply else '【dry-run 已回滚：kb.db 零写入】')
          + '  ' + '  '.join(f'{k}={v}' for k, v in stats.items()))
    if rejects:
        print(f'🔴 过闸拒收 {len(rejects)} 题（应吃却没进去，别当没看见）：')
        for r, errs in rejects[:20]:
            print(f'  ✗ punch#{r["id"]} doc={r["doc_id"]} {errs[0]}')
        if len(rejects) > 20:
            print(f'  …另有 {len(rejects) - 20} 条')
        written.append(write_rejects(rejects, part_tag))
    print(f'📄 本次写/覆盖报告件 {len(written)} 份'
          + (f'（{part_tag} 部分跑：只写 .partial.md，正本一个都没动）' if part_tag else '（全量跑：写正本）')
          + '：')
    for p in written:
        print(f'    · {p}')

    if args.apply:
        if stats['新建']:
            # 🔴 本桥不碰向量：语意向量要跑本地 bge 模型，与「桥全是机械映射、零模型」的口径冲突，
            #    故只把待补命令印出来，由人/收尾步骤显式跑，不在桥里偷偷起模型。
            print(f'📌 待补：本轮新入 {stats["新建"]} 题还没有语意向量（D-20 第③层检索会漏掉它们）——'
                  f'请显式跑 `python 工具箱\\检索\\embed_tool.py build --db {args.kb}`（只补缺的）')
        log_skill(kb, stats, total, t0)
    punch.close()
    kb.close()
    return {'total': total, '待入规则': len(bucket_rule), '待入考点': len(bucket_kp),
            '应吃': len(plan), '考点命中名': len(kp_hit), '考点未命中名': len(kp_miss),
            'stats': stats, 'rejects': len(rejects),
            'reports': [str(p) for p in written], 'partial': bool(part_tag),
            'code': 0 if not rejects else 1}


def log_skill(kb, stats, total, t0):
    kb.execute(
        'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) '
        'VALUES (?,?,?,?,?,?,?)',
        ('资料库吃库·题层桥', 'bridge-questions', f'全集={total}', '成功',
         ' '.join(f'{k}={v}' for k, v in stats.items())[:500],
         int((time.time() - t0) * 1000), now()))
    kb.commit()


# ══════════════════════════════════════════════════════════════════════
# 四、出件
# ══════════════════════════════════════════════════════════════════════
def _hdr(title, lines):
    return [f'# {title}', '', f'> 生成：{now()}（工具箱/桥/bridge_questions.py 自动出件，改数据请改源头重跑）', ''] + lines


def emit(base, title, lines, limit):
    """写一份报告件，返回真正写到的路径。

    🔴 `--limit N` 是部分跑：三堆账、聚合表、排行全是前 N 题的口径，不是交付口径。
       所以部分跑**一律不碰正本**，改写同目录的 `<正本名>.partial.md`，并在文件头第一行
       大字标注，让人不可能把它当全量件用。全量跑（无 --limit）才写正本。
    """
    base = Path(base)
    if not limit:
        path = base
        head = []
    else:
        path = base.with_name(base.stem + '.partial' + base.suffix)
        head = [f'# 🔴🔴 部分跑（{limit}），非完整口径 🔴🔴', '',
                f'> **这不是交付件**：本件由部分跑参数 `{limit}` 生成，只看了源库的一个子集，'
                f'下面每一个计数、每一张聚合表都只是该子集的口径。',
                f'> 全量正本是同目录的 `{base.name}`（只有全量跑才会写它，本次没动它）。', '']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(head + _hdr(title, lines)) + '\n', encoding='utf-8')
    return path


def write_reports(punch, bucket_rule, bucket_kp, resolver, docs, limit=None):
    """出四份件，返回真正写到的路径清单（给 run 如实播报用）。"""
    return [
        write_rule_pending(bucket_rule, docs, limit),
        write_kp_pending(bucket_kp, docs, limit),
        write_kp_map(punch, resolver, docs, limit),
        write_branch_draft(punch, resolver, docs, limit),
    ]


def write_rule_pending(bucket, docs, limit=None):
    L = [f'共 **{len(bucket)}** 题。判据=块流转换规则表（bridge_questions.py `RULE_TABLE` / `classify`）覆盖不到。',
         '🔴 这些题**没入库**，也**没猜**——补完规则（或补 figure/asset 通路）后重跑桥即自动吃进。', '']
    by = collections.defaultdict(list)
    for r, trace, errs in bucket:
        by[(r['doc_id'], r['题型'], errs[0])].append((r, trace))
    L += ['## 按 册×题型×原因 聚合', '',
          '| 册 | 名称 | 题型 | 原因 | 题数 | 样例 punch_id |', '|---|---|---|---|---:|---|']
    for (doc_id, qt, why), lst in sorted(by.items(), key=lambda x: -len(x[1])):
        sample = ' '.join(str(r['id']) for r, _ in lst[:3])
        L.append(f'| {doc_id} | {docs[doc_id]["名称"]} | {qt} | {why} | {len(lst)} | {sample} |')
    L += ['', '## 逐题清单', '',
          '| punch_id | 册 | day | section | 题面形 | 答案形 | 原因 | 题面原文（前 60 字） |',
          '|---|---:|---:|---|---|---|---|---|']
    for r, trace, errs in bucket:
        stem = str(r['stem'] or '').replace('|', '\\|').replace('\n', ' ')[:60]
        L.append(f'| {r["id"]} | {r["doc_id"]} | {r["day"]} | {r["section"]} | '
                 f'{trace.get("题面形", "-")} | {trace.get("答案形", "-")} | '
                 f'{"；".join(errs).replace("|", "/")} | `{stem}` |')
    return emit(REPORT_DIR / '待入-规则未覆盖.md', '待入队列 · 规则未覆盖（PRD-003 题层桥）', L, limit)


def write_kp_pending(bucket, docs, limit=None):
    L = [f'共 **{len(bucket)}** 题。判据=考点叶子闸：考点为空，或任一考点名在 kp/kp_alias 里 resolve 不到「现行叶子」。',
         '🔴 这些题**没入库**（挂不上考点就不入库，绝不裸题入库）。',
         '**补法**：按 `工具箱/桥/铺枝草案-吃库.md` 铺枝/加别名（走 KG维护 skill）→ 重跑本桥，靠 punch_map 幂等自动吃进。', '']
    by = collections.defaultdict(list)
    for r, names, miss in bucket:
        by[(r['doc_id'], tuple(names), tuple(sorted(m.split('：')[0] for m in miss)))].append(r)
    L += ['## 按 册×考点组合 聚合', '',
          '| 册 | 名称 | 源考点组合 | 卡住的考点名 | 题数 |', '|---|---|---|---|---:|']
    for (doc_id, names, miss), lst in sorted(by.items(), key=lambda x: -len(x[1])):
        L.append(f'| {doc_id} | {docs[doc_id]["名称"]} | {"、".join(names) or "（空）"} | '
                 f'{"、".join(miss)} | {len(lst)} |')
    L += ['', '## 卡住的考点名 · 题数排行', '', '| 考点名 | 卡住题数 | 出现册 | resolve 结论 |', '|---|---:|---|---|']
    per_name = collections.Counter()
    per_doc = collections.defaultdict(set)
    why_of = {}
    for r, names, miss in bucket:
        for m in miss:
            nm = m.split('：')[0]
            per_name[nm] += 1
            per_doc[nm].add(r['doc_id'])
            why_of[nm] = m.split('：', 1)[1] if '：' in m else m
    for nm, c in per_name.most_common():
        L.append(f'| {nm} | {c} | {"、".join(str(x) for x in sorted(per_doc[nm]))} | '
                 f'{why_of[nm].replace("|", "/")} |')
    L += ['', '## 全量 punch_id（按册，重跑桥用不到，留给人核对）', '']
    ids = collections.defaultdict(list)
    for r, _, _ in bucket:
        ids[r['doc_id']].append(str(r['id']))
    for doc_id in sorted(ids):
        L += [f'- **doc {doc_id}**（{len(ids[doc_id])} 题）：{",".join(ids[doc_id])}', '']
    return emit(REPORT_DIR / '待入-考点未挂.md', '待入队列 · 考点未挂（PRD-003 题层桥）', L, limit)


def write_rejects(rejects, limit=None):
    L = ['本轮**规则与考点都过了、却被三闸/等级审拦下**的题。闸拦下是对的，这里只是把它摆明。', '',
         '| punch_id | 册 | day | 拒收原话 |', '|---|---:|---:|---|']
    for r, errs in rejects:
        L.append(f'| {r["id"]} | {r["doc_id"]} | {r["day"]} | {"；".join(errs).replace("|", "/")} |')
    return emit(REPORT_DIR / '过闸拒收.md', '过闸拒收清单（PRD-003 题层桥）', L, limit)


def survey_kp_all(punch):
    """全库（含 doc 11/12、含无答案题）的考点名 → (总题数, {doc: 题数})。"""
    cnt = collections.Counter()
    per_doc = collections.defaultdict(collections.Counter)
    for doc_id, raw, ans in punch.execute(
            "SELECT doc_id, 考点, answer FROM question WHERE 考点 IS NOT NULL AND TRIM(考点)<>''"):
        try:
            v = json.loads(raw)
        except Exception:
            continue
        for nm in (v if isinstance(v, list) else [v]):
            nm = str(nm).strip()
            if not nm:
                continue
            cnt[nm] += 1
            per_doc[nm][doc_id] += 1
    return cnt, per_doc


def write_kp_map(punch, resolver, docs, limit=None):
    cnt, per_doc = survey_kp_all(punch)
    in_scope = collections.Counter()
    for doc_id, raw in punch.execute(
            "SELECT doc_id, 考点 FROM question WHERE 考点 IS NOT NULL AND TRIM(考点)<>'' "
            "AND answer IS NOT NULL AND TRIM(answer)<>'' "
            f'AND doc_id NOT IN ({",".join(str(x) for x in EXCLUDE_DOCS)})'):
        try:
            v = json.loads(raw)
        except Exception:
            continue
        for nm in (v if isinstance(v, list) else [v]):
            in_scope[str(nm).strip()] += 1
    hit = miss = 0
    L = [f'全库 `question.考点` 去重后 **{len(cnt)}** 个文字名（含 doc 11/12 与无答案题）。',
         '机械对法：`kp.name` 与 `kp_alias.alias`，**精确匹配 + NFKC 去空白匹配**，两条都不猜、不做模糊。',
         '判定「命中」的唯一口径：恰一个 **现行叶子**（`gates.assert_leaf_kp` 说了算）。',
         '章级/小节级同名（如「有理数的乘法」在 KG 里是小节）一律算**未命中**——挂章级=学情分母失真，老区血案。', '',
         '| # | 考点名 | 命中叶 id | 叶名 | 本桥在管的题数 | 全库题数 | 出现册 | 未命中原因 |',
         '|---:|---|---|---|---:|---:|---|---|']
    for i, (nm, c) in enumerate(sorted(cnt.items(), key=lambda x: (-in_scope.get(x[0], 0), -x[1], x[0])), 1):
        kid, why = resolver.resolve(nm)
        if kid:
            hit += 1
            leaf = resolver.conn.execute('SELECT name FROM kp WHERE id=?', (kid,)).fetchone()[0]
            tail = f'| `{kid}` | {leaf} |'
            why_s = '—'
        else:
            miss += 1
            tail = '| — | — |'
            why_s = why.replace('|', '/')
        dl = '、'.join(f'{d}({n})' for d, n in sorted(per_doc[nm].items()))
        L.append(f'| {i} | {nm} {tail} {in_scope.get(nm, 0)} | {c} | {dl} | {why_s} |')
    L = L[:4] + [f'**命中 {hit} / 未命中 {miss}**（未命中的题一律不入库，落 `记录/PRD-003吃库/待入-考点未挂.md`）。'] + L[4:]
    L += ['', '## 册号对照', '', '| doc_id | 名称 | 年级 | 本桥口径 |', '|---:|---|---|---|']
    for d in sorted(docs):
        scope = '排除（answer 全空，PRD-003 §4 待办1）' if d in EXCLUDE_DOCS else '在管'
        if not punch.execute('SELECT 1 FROM question WHERE doc_id=? LIMIT 1', (d,)).fetchone():
            continue
        L.append(f'| {d} | {docs[d]["名称"]} | {docs[d]["年级"]} | {scope} |')
    return emit(BRIDGE_DIR / '考点映射表.md', '考点映射表（资料库 → kb KG）', L, limit)


# ── 铺枝草案：号段聚类规则（🔴 只是查表建议，本文件绝不建枝）────────────
SEG_RULES_4010 = (
    ('MS', '分数乘法·简便计算', lambda n: n.startswith('简便计算：')),
    ('DS', '分数除法·简便计算', lambda n: n.startswith('基本简便计算：') or n.startswith('复杂的分数除法巧算：')),
    ('L', '量率对应', lambda n: n.startswith('量率对应')),
    ('U', '单位「1」的转化', lambda n: n.startswith('单位“1”转化') or n == '常见的单位“1”转化问题'),
    ('R', '倒数', lambda n: n.startswith('倒数')),
    ('G', '工程问题', lambda n: ('工程问题' in n or '合作' in n or '请假问题' in n
                                 or n.startswith('先由一人') or n.startswith('先合作')
                                 or n.startswith('先单独'))),
    ('MA', '分数乘法·实际应用', lambda n: n in {
        '求一个数的几分之几是多少', '连续求一个数的几分之几是多少',
        '已知单位“1”，求比一个数多几分之几，是多少', '已知单位“1”，求比一个数少几分之几，是多少',
        '已知单位“1”，求比一个数多几分之几，多多少', '已知单位“1”，求比一个数少几分之几，少多少',
        '求比一个数的几分之几多或少多少，是多少', '关于单位“1”与等量关系式',
        '分数乘法基本问题：混合型问题', '分量和分率的区分问题',
        '分率变化问题其一', '分率变化问题其二', '复杂的分数乘法应用题',
        '单位“1”变化问题：基础型', '单位“1”变化问题：进阶型', '单位“1”变化问题：拓展型'}),
    ('M', '分数乘法·意义与计算', lambda n: n in {
        '分数与整数相乘', '分数乘分数', '分数乘小数', '分数连乘运算', '分数四则混合运算',
        '积与因数的大小关系', '分数乘法与单位换算',
        '分数乘法列式计算（文字式）', '分数乘法列式计算（图形式）'}),
    ('D', '分数除法·意义与计算', lambda n: n in {
        '分数除以整数', '一个数除以分数', '分数连除运算', '分数乘除混合',
        '分数除法四则混合运算', '商与被除数的大小关系', '分数除法与解方程',
        '分数除法列式计算（文字式）', '分数除法列式计算（图形式）'}),
    ('DA', '分数除法·实际应用', lambda n: n in {
        '已知一个数的几分之几是多少，求这个数',
        '已知一个数连续的几分之几是多少，求这个数（分数连除）',
        '已知比一个数多几分之几的数是多少，求这个数',
        '已知比一个数少几分之几的数是多少，求这个数',
        '已知比一个数的几分之几多多少是多少，求这个数',
        '已知比一个数的几分之几少多少是多少，求这个数',
        '求一个数是（占）另一个数的几分之几',
        '已知两个数，求一个数比另一个数多或少几分之几',
        '分数除法中的归一问题', '分数乘除混合应用题',
        '分数除法基本问题混合型其一', '分数除法基本问题混合型其二',
        '分数除法基本问题混合型其三：计算盈利或亏损',
        '分量和分率区分问题（分数平均分）'}),
)

SEG_UNIT_4010 = {
    'M': ('601001', '分数乘法', '601001001'),
    'MS': ('601001', '分数乘法', '601001002'),
    'MA': ('601001', '分数乘法', '601001003'),
    'R': ('601002', '分数除法', '601002001'),
    'D': ('601002', '分数除法', '601002002'),
    'DS': ('601002', '分数除法', '601002003'),
    'DA': ('601002', '分数除法', '601002004'),
    'L': ('601003', '分数应用专题', '601003001'),
    'U': ('601003', '分数应用专题', '601003002'),
    'G': ('601003', '分数应用专题', '601003003'),
}
SEG_SECTION_NAME = {
    '601001001': '分数乘法的意义与计算', '601001002': '分数乘法的简便计算',
    '601001003': '分数乘法的实际应用',
    '601002001': '倒数', '601002002': '分数除法的意义与计算',
    '601002003': '分数除法的简便计算', '601002004': '分数除法的实际应用',
    '601003001': '量率对应', '601003002': '单位「1」的转化', '601003003': '工程问题',
}

# 七上（doc 2062~2801）19 名的落点建议：一律「挂到既有叶」或「转 tag(domain=方法)」，不新铸叶。
SEG_7SHANG = {
    '相反数': ('100001002003', '相反数', '已命中（无需动作）'),
    '有理数的乘除混合运算': ('100002004002', '有理数的乘除混合运算', '已命中（无需动作）'),
    '简便运算': ('100002001002', '有理数加法的运算律', '建议加别名·中置信：本册=带分数加法的简便运算'),
    '有理数的乘法': ('100002003001', '有理数的乘法法则', '建议加别名·高置信：源名撞 KG 小节名，落到该节首叶'),
    '有理数的减法': ('100002002001', '有理数的减法法则', '建议加别名·高置信：同上'),
    '有理数加减混合运算': ('100002002002', '有理数的加减混合运算', '建议加别名·高置信：只差一个「的」字'),
    '绝对值': ('100001003003', '与绝对值有关的计算', '建议加别名·中置信：本册是绝对值求值口算，不是概念题'),
    '有理数的乘方': ('100002005001', '乘方的概念与运算', '建议加别名·高置信：源名撞小节名'),
    '有理数的乘法运算律': ('100002003002', '有理数乘法的运算律', '建议加别名·高置信：语序差异'),
    '有理数的除法': ('100002004001', '有理数的除法法则', '建议加别名·高置信：源名撞小节名'),
    '有理数的混合运算': ('100002006001', '有理数混合运算的运算顺序', '建议加别名·高置信：源名撞小节名'),
    '符号化简': ('100001002003', '相反数', '建议加别名·低置信：多重符号=相反数嵌套；也可新铸叶「多重符号的化简」，请用户拍板'),
    '多重符号化简': ('100001002003', '相反数', '建议加别名·低置信：同上'),
    '凑整法': ('100002002002', '有理数的加减混合运算', '🔴 方法词非考点：建议 tag(domain=方法)；若走别名则挂此叶'),
    '拆项法': ('100002002002', '有理数的加减混合运算', '🔴 方法词非考点：同上'),
    '组合法': ('100002002002', '有理数的加减混合运算', '🔴 方法词非考点：同上'),
    '乘除连算': ('100002004002', '有理数的乘除混合运算', '🔴 方法词非考点：同上'),
    '先算括号': ('100002006001', '有理数混合运算的运算顺序', '🔴 方法词非考点：同上'),
    '分配律巧算': ('100002003002', '有理数乘法的运算律', '🔴 方法词非考点：同上'),
}

# 幼小衔接：源名全是 2~4 字口语词，不合 KG「叶子=名词短语」的命名契约 ⇒ 建议叶另起干净名，源名转别名
SEG_3204 = {
    '分解': ('900001001', '数的分与合', '5 以内数的分与合'),
    '比大小': ('900001002', '数的大小比较', '10 以内数的大小比较'),
    '加减法': ('900001003', '10 以内的加减法', '10 以内的加减计算'),
    '填符号': ('900001003', '10 以内的加减法', '10 以内的填运算符号'),
    '看图列式': ('900001004', '看图列式', '6 以内的看图列式'),
}


def seg_of(name):
    for code, label, fn in SEG_RULES_4010:
        if fn(name):
            return code, label
    return '?', '待人工归段'


def write_branch_draft(punch, resolver, docs, limit=None):
    cnt, per_doc = survey_kp_all(punch)
    scope_docs = [d for d in docs if d not in EXCLUDE_DOCS]
    names_by_doc = collections.defaultdict(set)
    for nm, dd in per_doc.items():
        for d in dd:
            if d in scope_docs:
                names_by_doc[d].add(nm)
    n4010 = sorted(names_by_doc.get(4010, ()))
    n3204 = sorted(names_by_doc.get(3204, ()))
    n7 = sorted({nm for d in scope_docs if d not in (4010, 3204) for nm in names_by_doc.get(d, ())})

    L = [
        '> 🔴 **本文件只是草案，本桥一根枝都不建**。铺枝/加别名的唯一写入通路=`工具箱/kg/kg_tool.py`（KG维护 skill）。',
        '> 格式学 `工具箱/kg/首枝-浙教七上.json`；id 契约=数字每 3 位一层（年级学期3/单元6/小节9/考点12），',
        '> 版本层用可读串（如 `zjsx2024`）永不与老区数字 id 相撞。',
        '',
        '## 0. 三块料',
        '',
        '| 块 | 未命中名数 | 归宿 | 动作 |',
        '|---|---:|---|---|',
        f'| 七上打卡 11 册（2062~2801） | {len(n7)} | **既有 zjsx2024/100 枝** | 只加 `kp_alias`，不铸新叶 |',
        f'| 六上分数乘除法（4010） | {len(n4010)} | **新铸 `rjsx2024` 版本 + 六上册根** | 铺 3 单元 10 小节，叶按号段落位 |',
        f'| 幼小衔接（3204） | {len(n3204)} | **新铸 `yxxj` 版本 + 学前册根** | 铺 1 单元 4 小节 |',
        '',
        '## 1. 七上 11 册：只加别名（不铸叶）',
        '',
        '源名多是「撞了 KG 小节名」或「方法词」两类。撞小节名的落到该节对应叶；',
        '🔴 方法词（凑整法/拆项法/组合法/乘除连算/先算括号/分配律巧算/简便运算）**本不该占 KG 位**',
        '（KG 契约：教辅栏目/方法词不占 KG 位），正解是 `tag(domain=\'方法\')`；',
        '走别名只是让存量题先能入库的权宜，两条路请用户拍板选一条。',
        '',
        '| 源考点名 | 在管题数 | 建议叶 id | 叶名 | 结论 |',
        '|---|---:|---|---|---|',
    ]
    for nm in sorted(n7, key=lambda x: -cnt[x]):
        kid, leaf, why = SEG_7SHANG.get(nm, ('—', '—', '🔴 未列入建议表——人工裁决'))
        L.append(f'| {nm} | {cnt[nm]} | `{kid}` | {leaf} | {why} |')

    L += ['', '## 2. 六上分数乘除法（doc 4010）：新铸一枝', '',
          '版本层 `rjsx2024`（人教版数学）＋册根 `601`（六年级上册）。',
          '🔴 `601` 这个 3 位册根**须先与老区 id 空间对一遍**再定（老区册根也是 3 位，撞了就是同 id 两义）——',
          '本草案标为待核。号段按源库自身的组织规律切：',
          '',
          '🔴 号段 `R`（倒数 6 名）是本草案新加的一段——原号段表 M/MS/MA/D/DS/DA/L/U/G 里它无处安放，',
          '倒数既是乘法的收尾又是除法的地基，草案把它单列为分数除法单元的第一小节，请用户确认这一段。',
          '',
          '| 号段 | 含义 | 落到小节 | 名数 |', '|---|---|---|---:|']
    segs = collections.defaultdict(list)
    for nm in n4010:
        code, label = seg_of(nm)
        segs[code].append(nm)
    seg_label = {c: lb for c, lb, _ in SEG_RULES_4010}
    for code in ('M', 'MS', 'MA', 'R', 'D', 'DS', 'DA', 'L', 'U', 'G', '?'):
        if code not in segs:
            continue
        if code == '?':
            L.append(f'| ? | 🔴 待人工归段 | — | {len(segs[code])} |')
            continue
        unit, uname, sec = SEG_UNIT_4010[code]
        L.append(f'| {code} | {seg_label.get(code, uname)} | `{sec}` {SEG_SECTION_NAME[sec]} | {len(segs[code])} |')
    L += ['', '### 建枝骨架（spec 片段，抄进 kg_tool build-branch 的 JSON）', '', '```json',
          json.dumps({
              'version': {'id': 'rjsx2024', 'name': '人教版数学', 'ord': 2,
                          'note': {'subject': '数学', 'edition': '人教'}},
              'book': {'id': '601', 'name': '六年级上册', 'ord': 1,
                       'note': {'grade': 6, 'volume': '上', '待核': '3 位册根须先与老区 id 空间对撞检查'}},
              'units': [
                  {'id': u, 'name': un, 'ord': i + 1, 'sections': [
                      {'id': s, 'name': SEG_SECTION_NAME[s], 'ord': j + 1, 'leaves': '见下表'}
                      for j, s in enumerate(sorted({SEG_UNIT_4010[c][2] for c in SEG_UNIT_4010
                                                    if SEG_UNIT_4010[c][0] == u}))]}
                  for i, (u, un) in enumerate(sorted({(v[0], v[1]) for v in SEG_UNIT_4010.values()}))
              ]}, ensure_ascii=False, indent=1),
          '```', '', '### 叶清单（108 名逐行，叶 id 待铺枝时按 ord 顺序补 3 位）', '',
          '| 号段 | 小节 | 源考点名 | 在管题数 |', '|---|---|---|---:|']
    for code in ('M', 'MS', 'MA', 'R', 'D', 'DS', 'DA', 'L', 'U', 'G', '?'):
        for nm in sorted(segs.get(code, ()), key=lambda x: -cnt[x]):
            sec = SEG_UNIT_4010[code][2] if code != '?' else '—'
            secn = SEG_SECTION_NAME.get(sec, '待人工归段')
            L.append(f'| {code} | {secn} | {nm} | {cnt[nm]} |')

    L += ['', '## 3. 幼小衔接（doc 3204）：新铸一枝', '',
          '版本层 `yxxj`（幼小衔接·无教材版本），册根 `900`（学前），单元 `900001`（10 以内数与运算）。',
          '🔴 `900` 同样待与老区 id 空间对撞检查。', '',
          '源名全是 2~4 字口语词（分解/比大小/…），不合 KG「叶子=名词短语」的命名契约 ⇒',
          '建议叶另起干净名，**源名转 `kp_alias`（kind=产线词）**，桥才对得上。', '',
          '| 源考点名 | 在管题数 | 建议小节 id | 小节名 | 建议叶名 | 别名 |', '|---|---:|---|---|---|---|']
    for nm in sorted(n3204, key=lambda x: -cnt[x]):
        sec, secn, leaf = SEG_3204.get(nm, ('—', '🔴 待人工归段', nm))
        L.append(f'| {nm} | {cnt[nm]} | `{sec}` | {secn} | {leaf} | {nm} |')
    # §4 铺枝也救不了的一堆：源库 考点 列本来就是空的
    blank = collections.defaultdict(collections.Counter)
    for doc_id, sec in punch.execute(
            "SELECT doc_id, section FROM question "
            "WHERE (考点 IS NULL OR TRIM(考点)='') AND answer IS NOT NULL AND TRIM(answer)<>'' "
            f'AND doc_id NOT IN ({",".join(str(x) for x in EXCLUDE_DOCS)})'):
        blank[doc_id][sec] += 1
    n_blank = sum(sum(c.values()) for c in blank.values())
    L += ['', '## 4. 🔴 铺枝救不了的一堆：源库 `考点` 列本来就是空的', '',
          f'共 **{n_blank}** 题。这些题在资料库里就没写考点，**铺再多枝也对不上**——',
          '得先给这两册定考点（册级定一次，题级按 section 落）才谈得上入库。',
          '本桥不猜（猜=裸题入库的另一种形态），只把册与节列在这里等用户拍。', '',
          '| 册 | 名称 | 题数 | 节（section）分布 | 册名暗示的考点方向 |', '|---:|---|---:|---|---|']
    for doc_id in sorted(blank):
        secs = '、'.join(f'{s}({n})' for s, n in blank[doc_id].most_common())
        L.append(f'| {doc_id} | {docs[doc_id]["名称"]} | {sum(blank[doc_id].values())} | {secs} | '
                 f'（待用户拍板；册名=「{docs[doc_id]["名称"]}」） |')
    L += ['', '## 5. 铺完之后', '',
          '1. `kg_tool.py build-branch <spec>.json` 铺枝 → `kg_tool.py alias` 补别名；',
          '2. 重跑 `bridge_questions.py --apply`：punch_map 已吃的不动，新命中的自动补吃（幂等）；',
          '3. `记录/PRD-003吃库/待入-考点未挂.md` 会随之缩短，缩到 0 = 这一层吃干净。', '']
    return emit(BRIDGE_DIR / '铺枝草案-吃库.md', 'KG 铺枝草案 · 吃库未命中考点（PRD-003 题层桥）', L, limit)


def main():
    ap = argparse.ArgumentParser(description='B 题层桥：资料库.db question → kb.db（机械转换，零 LLM）')
    ap.add_argument('--punch', default=str(DEFAULT_PUNCH), help='源库 资料库.db（只读打开）')
    ap.add_argument('--kb', default=str(DEFAULT_KB), help='目标 kb.db')
    ap.add_argument('--apply', action='store_true', help='真写库（缺省=dry-run，跑完回滚）')
    ap.add_argument('--survey', action='store_true', help='只统计块形分布，供核对/改 RULE_TABLE')
    ap.add_argument('--limit', type=int, help='只处理前 N 题（调试用）')
    ap.add_argument('--only-doc', dest='only_doc',
                    help='只吃这些源册（punch doc id，逗号分隔）——试刀用；部分跑，报告走 .partial 不碰正本')
    args = ap.parse_args()
    sys.exit(run(args)['code'])


if __name__ == '__main__':
    main()
