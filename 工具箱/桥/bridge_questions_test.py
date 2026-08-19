# -*- coding: utf-8 -*-
"""B 题层桥自证测试（一键复跑）。

跑法（在 worktree 根或任意目录）：
    python 工具箱/桥/bridge_questions_test.py
    python 工具箱/桥/bridge_questions_test.py --sandbox <沙盘目录>

🔴 测试只碰沙盘：沙盘目录里要有 `资料库.db`（只读）与 `kb.pristine.db`（干净底库快照）。
   每个场景都从 kb.pristine.db 拷一份新库跑，跑完不留脏；出件目录也改到沙盘内，
   绝不覆盖 工具箱/桥/*.md 与 记录/PRD-003吃库/*.md 这些真交付件。

🔴 断言名与断言体必须逐字对得上：名说 A 就得断言 A。名与体不符 = 绿灯谎言，
   比红灯还坏（老区「注释谎言」血案的测试版）。
"""
import argparse
import contextlib
import hashlib
import inspect
import io
import json
import shutil
import sqlite3
import sys
import types
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / '工具箱' / '库'))
import bridge_questions as B                     # noqa: E402
import ingest_flow                                # noqa: E402  （桥的入库唯一门，零 LLM 自证要照它）
from gates import validate_blocks                 # noqa: E402

DEFAULT_SANDBOX = ROOT / '试验场' / '2026-08-19-prd003沙盘' / 'B-题层桥'

# 四份交付件的正本名（--limit 部分跑一份都不许碰）
DELIVERABLES = ('待入-规则未覆盖.md', '待入-考点未挂.md', '考点映射表.md', '铺枝草案-吃库.md')

PASS, FAIL = [], []
REAL_AUTOVEC = ingest_flow.autovec            # 见 install_no_model_guard：护栏装上后真身存这


def check(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print(('  √ ' if ok else '  ✗ ') + name + (f'  —— {detail}' if detail else ''))
    return ok


def eq(name, got, want):
    return check(name, got == want, f'实际={got!r} 期望={want!r}')


def fresh_kb(sandbox, tag):
    dst = sandbox / '_test' / f'kb.{tag}.db'
    dst.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ('', '-wal', '-shm'):
        p = Path(str(dst) + suffix)
        if p.exists():
            p.unlink()
    shutil.copy2(sandbox / 'kb.pristine.db', dst)
    return dst


def bridge(punch, kb, apply_=False, survey=False, limit=None):
    return B.run(types.SimpleNamespace(punch=str(punch), kb=str(kb),
                                       apply=apply_, survey=survey, limit=limit))


def bridge_capture(punch, kb, **kw):
    """跑桥并把它印在屏幕上的话原样接住 → (返回值, 打印全文)。播报真伪要照着这个断。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = bridge(punch, kb, **kw)
    return r, buf.getvalue()


def q(db, sql, *a):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(sql, a).fetchone()[0]
    finally:
        conn.close()


# 🔴 dry-run「零写入」的判据必须是**逐表**的：事务里被人 commit 一下，漏出来的不止 question
#    一张表（question_kp/punch_map/artifact_member 全跟着落地）。只数 question 会放跑事务炸弹。
WATCHED_TABLES = ('question', 'question_kp', 'question_vec', 'punch_map',
                  'paper', 'paper_item', 'skill_log', 'artifact', 'artifact_member')


def install_no_model_guard():
    """🔴 全套测试的护栏：任何一处真调到 ingest_flow.autovec 都当场炸红。

    血案：桥曾在 BEGIN 事务里调 autovec，测试一跑就去冷载本地 bge 模型——
    整套测试从 7 秒变成 15 分钟不出声，看起来像「测试很慢」，实际是「桥错了」。
    慢和错必须区分开：装上这个护栏后，摘掉零向量修复的后果是**秒级炸红**，不是干等。
    需要替身的用例（[11] 炸弹替身 / [12] commit 替身）自己就地覆盖再还原，不受影响。
    """
    global REAL_AUTOVEC
    REAL_AUTOVEC = ingest_flow.autovec        # 真身留一份，[12] 要读它的源码作机理自证

    def _no_model(*a, **k):
        raise AssertionError(
            '🔴 测试期触发了 ingest_flow.autovec（会起本地 bge 模型）——'
            '桥的口径是零向量（见 bridge_questions.py 铁律④），出现即缺陷')
    ingest_flow.autovec = _no_model


def snapshot(db):
    """kb.db 逐表行数快照 → {表名: 行数}。跑前跑后一比，多一行都藏不住。"""
    conn = sqlite3.connect(str(db))
    try:
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                for t in WATCHED_TABLES if t in have}
    finally:
        conn.close()


def digest(path):
    p = Path(path)
    return None if not p.exists() else hashlib.sha256(p.read_bytes()).hexdigest()


def tail(out, n=3):
    """播报全文太长，出错时只给最后 n 行非空——够定位，不刷屏。"""
    return ' ⏎ '.join([ln.strip() for ln in out.splitlines() if ln.strip()][-n:])


def src_rows(sandbox):
    """源库全表 {源 id(str): row}，只读打开。"""
    p = sqlite3.connect('file:' + (sandbox / '资料库.db').as_posix() + '?mode=ro', uri=True)
    p.row_factory = sqlite3.Row
    try:
        return {str(r['id']): dict(r) for r in
                p.execute('SELECT id, doc_id, day, section, seq FROM question')}
    finally:
        p.close()


# ══════════════════════════════════════════════════════════════════════
def t_pure_functions():
    print('\n[1] 纯函数：块形判定 / 变换 / 剥前缀 / 来源映射 / prov 原料（确定性，同入同出）')
    cases = [
        ('(-10)+(+6)', 'bare_math', '$(-10)+(+6)$'),
        ('\\left(-\\frac{1}{2}\\right)-\\frac{1}{4}', 'bare_math',
         '$\\left(-\\frac{1}{2}\\right)-\\frac{1}{4}$'),
        ('-7 的相反数是', 'math_head_text_tail', '$-7$ 的相反数是'),
        ('\\frac{1}{3} 的相反数是', 'math_head_text_tail', '$\\frac{1}{3}$ 的相反数是'),
        ('5 ○ 1 ＝ 4（填＋或－）', 'plain', '5 ○ 1 ＝ 4（填＋或－）'),
        ('10 － 6 ＝ ( )', 'plain', '10 － 6 ＝ ( )'),
        ('＞', 'plain', '＞'),
        ('\\(\\frac{2}{3}\\times 1\\ ○\\ \\frac{2}{3}\\)', 'paren',
         '$\\frac{2}{3}\\times 1\\ ○\\ \\frac{2}{3}$'),
        ('学校有科技书 \\(240\\) 本。', 'paren', '学校有科技书 $240$ 本。'),
    ]
    for src, want_shape, want_md in cases:
        sh = B.classify(src)
        md, why = B.to_md(src, sh)
        check(f'classify+to_md {src[:24]!r}', sh == want_shape and md == want_md,
              f'形={sh} md={md!r}')
    # 不覆盖的形一律 (None, 原因)，绝不猜
    for src, want_shape in (('<svg/>图', 'html'), ('$x$', 'dollar'),
                            ('求 \\frac{1}{2} 的值，再算 \\frac{1}{3}', 'unsupported'), ('', 'empty')):
        sh = B.classify(src)
        md, why = B.to_md(src, sh)
        check(f'不覆盖形 {want_shape} → 不猜', sh == want_shape and md is None and why,
              f'形={sh} md={md!r}')
    # 幂等性：同一输入跑两遍完全一致
    check('classify 确定性（同入同出）',
          all(B.classify(s) == B.classify(s) for s, _, _ in cases))
    # 剥指令词
    eq('剥「分解：」', B.strip_instruction('分解：3 分成 1 和 ___'), ('3 分成 1 和 ___', '分解：'))
    eq('剥「看图列式：」', B.strip_instruction('看图列式：左 1 个'), ('左 1 个', '看图列式：'))
    eq('无前缀不动', B.strip_instruction('$1+1$'), ('$1+1$', None))
    # 来源 → source_kind
    eq('来源含 DSL → model', B.source_kind_of('人教版六上…+ 本册 DSL 自出')[0], 'model')
    eq('来源含 出题器 → model', B.source_kind_of('出题器反抽-2026-08')[0], 'model')
    eq('来源含 自编 → manual', B.source_kind_of('自编·2026-08·人教七上 2.1.1')[0], 'manual')
    eq('来源含 母题= → model', B.source_kind_of('母题=用户 2026-08-10 给的教辅照片')[0], 'model')
    eq('来源不匹配 → 不猜', B.source_kind_of('天上掉下来的')[0], None)
    # \( \) 成对性闸
    check('\\( \\) 不成对 → 拒', B._paren_to_dollar('\\(a\\(b\\)')[0] is None)
    check('公式外残留反斜杠 → 拒', B._paren_to_dollar('\\(a\\) \\beta')[0] is None)
    # 强制形只能是 plain，且不许掩盖「不覆盖的形」
    eq('强制形不掩盖 html', B._forced('html', 'plain', {}, '题面'), 'html')
    eq('强制形把 math_head 压成 plain', B._forced('math_head_text_tail', 'plain', {}, '题面'), 'plain')
    # 🔴 载体原料：本卡不建载体，prov 必须一次留够重建载体的全部输入
    eq('prov_of 带全载体四件 + 反查 id + 来源原文',
       B.prov_of({'doc_id': 2064, 'day': 3, 'section': '相反数', 'seq': 7, 'id': 37353, '来源': '自编·X'}),
       {'punch_doc': '2064', 'punch_day': '3', 'punch_section': '相反数', 'punch_seq': '7',
        'punch_question': '37353', '来源': '自编·X'})
    eq('prov_of 的 None 原样留 None（不拿空串冒充「源库没写」）',
       B.prov_of({'doc_id': 4010, 'day': None, 'section': None, 'seq': None, 'id': 1, '来源': None}),
       {'punch_doc': '4010', 'punch_day': None, 'punch_section': None, 'punch_seq': None,
        'punch_question': '1', '来源': None})


def t_survey(sandbox):
    print('\n[2] 规则表覆盖：survey 里除 html 外无「表外形」')
    kb = fresh_kb(sandbox, 'survey')
    r = bridge(sandbox / '资料库.db', kb, survey=True)
    bad = []
    for (doc, qt, side), dist in r['survey'].items():
        rule = B.RULE_TABLE.get((doc, qt))
        if rule is None:
            bad.append((doc, qt, side, '规则表无此格'))
            continue
        allow = set(rule[0] if side == '题面' else rule[1])
        forced = (tuple(rule) + (None, None))[2 if side == '题面' else 3]
        if forced:
            allow.add(forced)
        for shape in dist:
            if shape not in allow and shape != 'html':
                bad.append((doc, qt, side, shape))
    check('规则表覆盖除 html 外的全部块形', not bad, str(bad))


def t_accounting(sandbox):
    print('\n[3] 三堆账：规则未覆盖 + 考点未挂 + 应吃 == 全集；dry-run 对 kb.db 逐表零写入')
    kb = fresh_kb(sandbox, 'dry')
    before = snapshot(kb)
    r, out = bridge_capture(sandbox / '资料库.db', kb)
    # 🔴 只有「全集」与「规则未覆盖」是 KG 无关的定数（源库口径 + RULE_TABLE 说了算），可硬编码；
    #    「应吃 / 考点未挂」随 KG 铺枝进度天天变（今天整册铺枝后叶子从 31 涨到 71），
    #    硬编码上一轮的数字 = 明天必假红。守恒断言只断「三堆之和 == 全集」+ 两头都不许退化。
    eq('全集 = 2948（answer 非空 · 排除 doc 11/12，源库定数）', r['total'], 2948)
    eq('🔴 守恒：待入规则 + 待入考点 + 应吃 == 全集 2948',
       r['待入规则'] + r['待入考点'] + r['应吃'], r['total'])
    eq('待入-规则未覆盖 = 9（doc 4010 的 HTML/SVG 混排，与 KG 无关）', r['待入规则'], 9)
    check('应吃 > 0（守恒不许靠「一题都不吃」凑）', r['应吃'] > 0, f'应吃={r["应吃"]}')
    check('待入-考点未挂 > 0（KG 还没铺全，这堆不该是 0）', r['待入考点'] > 0,
          f'待入考点={r["待入考点"]}')
    print(f'    本轮账面基线（随 KG 进度浮动）：应吃={r["应吃"]} 待入考点={r["待入考点"]} '
          f'考点名命中={r["考点命中名"]}/未命中={r["考点未命中名"]}')

    # 🔴 反例（事务炸弹复活必红）：dry-run 的口径是 kb.db **逐表**零写入，不是「question 表零写入」。
    #    事务里被人 commit 一下（如 autovec→save_vecs），漏的是 question/question_kp/punch_map 一整串。
    after = snapshot(kb)
    eq('dry-run 后 kb.db 逐表行数与跑前完全一致（question/punch_map/skill_log/…）', after, before)

    # 🔴 反例（改口径必红）：dry-run 播报只许说「kb.db 零写入」，不许说「一个字节都没写」——
    #    报告件是照写照覆盖的，说没写就是假话。
    check('dry-run 播报不吹「一个字节都没写」', '一个字节' not in out, tail(out))
    check('dry-run 播报明说「kb.db 零写入」', 'kb.db 零写入' in out, tail(out))
    check('dry-run 如实报出报告件份数', '本次写/覆盖报告件 4 份' in out, tail(out))
    check('播报里逐条列出了本次写的每一个报告文件',
          all(str(p) in out for p in r['reports']), str(r['reports']))
    check('播报列的报告文件真的落在盘上', all(Path(p).exists() for p in r['reports']),
          str([p for p in r['reports'] if not Path(p).exists()]))
    return r


def t_limit_partial(sandbox):
    print('\n[4] --limit 不许碰交付正本：四份件改写 <正本名>.partial.md 且文件头大字标注')
    kb = fresh_kb(sandbox, 'limit')
    # 先全量跑一次把四份正本写出来，留指纹
    full, _ = bridge_capture(sandbox / '资料库.db', kb)
    eq('全量跑写的是正本（reports 里一个 .partial 都没有）',
       [p for p in full['reports'] if '.partial.' in p], [])
    eq('全量跑 partial 标记为假', full['partial'], False)
    canon = {p: digest(p) for p in full['reports']}
    check('四份正本齐（待入两份 + 考点映射表 + 铺枝草案）',
          sorted(Path(p).name for p in canon) == sorted(DELIVERABLES),
          str(sorted(Path(p).name for p in canon)))

    # 🔴 反例（正本被 limit 覆盖必红）：部分跑
    part, out = bridge_capture(sandbox / '资料库.db', kb, limit=200)
    eq('部分跑只看前 200 题', part['total'], 200)
    eq('部分跑 partial 标记为真', part['partial'], True)
    eq('部分跑写的四份件全是 .partial.md',
       [Path(p).name for p in part['reports'] if not p.endswith('.partial.md')], [])
    bad = [p for p, d in canon.items() if digest(p) != d]
    eq('部分跑后四份正本逐字节未变（没被部分口径覆盖）', bad, [])
    heads = {Path(p).name: Path(p).read_text(encoding='utf-8').splitlines()[0] for p in part['reports']}
    check('每份 .partial.md 第一行就是「部分跑 limit=200，非完整口径」大字标注',
          all('部分跑 limit=200，非完整口径' in h for h in heads.values()), str(heads))
    check('部分跑播报明说没动正本', '正本一个都没动' in out, tail(out))


def t_apply_and_idempotent(sandbox, base):
    """base = t_accounting 那次 dry-run 的返回值。🔴 期望值一律从它推，不硬编码上一轮的数字。"""
    print('\n[5] --apply 真入库 → 复跑幂等零新增（期望值从 dry-run 的应吃数推，不硬编码）')
    kb = fresh_kb(sandbox, 'apply')
    base_q = q(kb, 'SELECT COUNT(*) FROM question')
    should_eat = base['应吃']
    r1 = bridge(sandbox / '资料库.db', kb, apply_=True)
    new, reuse = r1['stats']['新建'], r1['stats']['复用既有题']
    eq('应吃的题一条不落地进了库（新建 + 复用既有题 == dry-run 的应吃数）', new + reuse, should_eat)
    eq('闸拒收 0', r1['stats']['闸拒收'], 0)
    eq('question 净增 == 新建数（复用的不建第二条）',
       q(kb, 'SELECT COUNT(*) FROM question') - base_q, new)
    check('确有册内重复题面走了「复用既有题」（这条路不是空跑）', reuse > 0, f'复用={reuse}')
    eq('punch_map(question) == 应吃数（每条应吃题都有映射）',
       q(kb, "SELECT COUNT(*) FROM punch_map WHERE kind='question'"), should_eat)
    eq('入库的题全是草稿态',
       q(kb, "SELECT COUNT(*) FROM question WHERE id LIKE 'qpunch%' AND status<>'草稿'"), 0)
    eq('入库题的考点全是「现行叶子」（level=考点 且 status=现行）',
       q(kb, "SELECT COUNT(*) FROM question_kp qk JOIN kp ON kp.id=qk.kp_id "
             "JOIN question q ON q.id=qk.question_id "
             "WHERE q.id LIKE 'qpunch%' AND (kp.level<>'考点' OR kp.status<>'现行')"), 0)
    eq('难度留空（源库全空，不编难度）',
       q(kb, "SELECT COUNT(*) FROM question WHERE id LIKE 'qpunch%' AND diff_code IS NOT NULL"), 0)
    eq('题型全部翻得出字典码（QTYPE_MAP 表外的题根本进不来，不该有空码）',
       q(kb, "SELECT COUNT(*) FROM question WHERE id LIKE 'qpunch%' AND qtype_code IS NULL"), 0)
    # 🔴 桥零向量：入库这一路不许顺手算 question_vec（算向量=起本地 bge 模型）
    eq('新入的题一条向量都没算（桥零向量，向量由收尾 embed_tool.py build 显式补）',
       q(kb, "SELECT COUNT(*) FROM question_vec WHERE question_id LIKE 'qpunch%'"), 0)

    r2 = bridge(sandbox / '资料库.db', kb, apply_=True)
    eq('复跑：新建 0', r2['stats']['新建'], 0)
    eq('复跑：复用 0', r2['stats']['复用既有题'], 0)
    eq('复跑：已映射跳过 == 应吃数（全靠 punch_map 幂等挡住）',
       r2['stats']['已映射跳过'], should_eat)
    eq('复跑后 question 总数不变（幂等零新增）',
       q(kb, 'SELECT COUNT(*) FROM question') - base_q, new)
    base['新建'] = new
    return kb


def t_prov_carrier(sandbox, kb, base):
    print('\n[6] 载体原料：每题 prov_json 带全 punch_doc/day/section/seq（本卡不建载体，原料必须一次留够）')
    conn = sqlite3.connect(str(kb))
    provs = dict(conn.execute("SELECT id, prov_json FROM question WHERE id LIKE 'qpunch%'"))
    conn.close()
    src = src_rows(sandbox)
    eq('抽到全部新建题的 prov_json（条数 == 本轮新建数）', len(provs), base['新建'])
    missing, wrong = [], []
    for qid, pj in provs.items():
        sid = str(int(qid[len('qpunch'):]))          # qid 自带源 id，反查不靠 punch_map
        d = json.loads(pj or '{}')
        lack = [k for k in B.PROV_CARRIER_KEYS if k not in d]
        if lack:
            missing.append((qid, lack))
            continue
        s = src[sid]
        want = {'punch_doc': str(s['doc_id']), 'punch_day': str(s['day']),
                'punch_section': s['section'], 'punch_seq': str(s['seq']), 'punch_question': sid}
        got = {k: d.get(k) for k in want}
        if got != want:
            wrong.append((qid, got, want))
    # 🔴 反例（prov 少留任一件必红）：少了 day/section/seq，日后重建载体就得回源库重查
    eq('每题 prov_json 四件齐（punch_doc/punch_day/punch_section/punch_seq）', missing, [])
    eq('prov 四件的值与源库逐字段对得上（含 punch_question 反查 id）', wrong[:3], [])
    eq('prov 还留了源库来源原文（来源）',
       sum(1 for pj in provs.values() if '来源' not in json.loads(pj or '{}')), 0)


def t_no_carrier(sandbox):
    """🔴 这一跑必须用**干净底库**：老代码建卷的触发条件是「doc→artifact 映射齐 **且** 本轮真在建新题」。
    拿一个已经吃完的库来跑，新建=0，建卷那段代码根本走不到，`paper_item 净增 0` 就成了空断言——
    摘掉载体修复它也照样绿。（这一条正是退回演练 B 逼出来的：当时只有源码 grep 变红。）"""
    print('\n[7] 本卡不建载体：doc→artifact 映射齐 + 本轮真在建新题，paper/paper_item 仍一行不写')
    kb = fresh_kb(sandbox, 'carrier')
    conn = sqlite3.connect(str(kb))
    conn.execute('PRAGMA foreign_keys=ON')
    for doc_id, name in ((2064, '2.3 相反数、绝对值与多重符号化简'), (3204, '幼小衔接数学综合练习')):
        conn.execute("INSERT OR IGNORE INTO artifact(id,name,kind,status,source_line,created_at) "
                     "VALUES (?,?,?,?,?,datetime('now'))",
                     (f'afake{doc_id}', name, '打卡册', '在产', '沙盘假件·A线未跑'))
        conn.execute("INSERT OR REPLACE INTO punch_map(kind,punch_id,kb_id,note,created_at) "
                     "VALUES ('doc',?,?,'沙盘假映射',datetime('now'))",
                     (str(doc_id), f'afake{doc_id}'))
    conn.commit()
    base_p = conn.execute('SELECT COUNT(*) FROM paper').fetchone()[0]
    base_i = conn.execute('SELECT COUNT(*) FROM paper_item').fetchone()[0]
    n_art = conn.execute("SELECT COUNT(*) FROM punch_map WHERE kind='doc'").fetchone()[0]
    conn.close()
    eq('前置：doc→artifact 映射已备好 2 条（正是老代码建卷的触发条件）', n_art, 2)

    # 🔴 反例（载体代码被复活必红）
    r = bridge(sandbox / '资料库.db', kb, apply_=True)
    check('前置：本轮确实在建新题（否则建卷那段走不到，下面两条就是空断言）',
          r['stats']['新建'] > 0, f'新建={r["stats"]["新建"]}')
    eq('paper 净增 0', q(kb, 'SELECT COUNT(*) FROM paper') - base_p, 0)
    eq('paper_item 净增 0', q(kb, 'SELECT COUNT(*) FROM paper_item') - base_i, 0)
    eq('返回值里没有 paper 计数（stats 只剩四项吃题账）',
       sorted(r['stats']), sorted(['新建', '复用既有题', '已映射跳过', '闸拒收']))
    src = (HERE / 'bridge_questions.py').read_text(encoding='utf-8')
    hit = [w for w in ('INSERT INTO paper', 'INSERT OR REPLACE INTO paper',
                       'def build_papers', 'def paper_id_of') if w in src]
    eq('桥源码里没有任何 paper/paper_item 写入代码', hit, [])
    check('模块也不再导出 build_papers / paper_id_of 符号',
          not hasattr(B, 'build_papers') and not hasattr(B, 'paper_id_of'))


def t_blocks_eyeball(sandbox, kb):
    print('\n[8] 抽 10 题目检块流：过块流校验器 + 存取同构（只有一份 blocks_json）')
    conn = sqlite3.connect(str(kb))
    rows = conn.execute(
        "SELECT id, blocks_json, answer_blocks_json, analysis_blocks_json FROM question "
        "WHERE id LIKE 'qpunch%' ORDER BY id LIMIT 10").fetchall()
    conn.close()
    eq('抽到 10 题', len(rows), 10)
    allok = True
    for qid, b, a, an in rows:
        ok1, e1 = validate_blocks(b, is_stem=True)
        ok2, e2 = validate_blocks(a, is_stem=False)
        doc = json.loads(b)
        cell = doc['rows'][0]['cells'][0]
        shape_ok = (doc.get('v') == 2 and cell['type'] == 'text' and cell['role'] == '题面')
        no_analysis = an is None            # steps 全空 ⇒ 不建解析块
        ok = ok1 and ok2 and shape_ok and no_analysis
        allok &= ok
        print(f'    {qid}  题面={json.loads(b)["rows"][0]["cells"][0]["md"]!r}  '
              f'答案={json.loads(a)["rows"][0]["cells"][0]["md"]!r}'
              + ('' if ok else f'  🔴 {e1}{e2} shape={shape_ok} 解析空={no_analysis}'))
    check('10 题块流全过校验器（题面/答案）且无解析块', allok)


def t_negative(sandbox):
    print('\n[9] 反例：无答案题 / doc 11-12 / HTML-SVG 题，一条都不进')
    kb = fresh_kb(sandbox, 'neg')
    bridge(sandbox / '资料库.db', kb, apply_=True)
    conn = sqlite3.connect(str(kb))
    ids = {r[0] for r in conn.execute("SELECT punch_id FROM punch_map WHERE kind='question'")}
    conn.close()
    p = sqlite3.connect('file:' + (sandbox / '资料库.db').as_posix() + '?mode=ro', uri=True)
    noans = {str(r[0]) for r in p.execute(
        "SELECT id FROM question WHERE answer IS NULL OR TRIM(answer)=''")}
    doc1112 = {str(r[0]) for r in p.execute('SELECT id FROM question WHERE doc_id IN (11,12)')}
    html = {str(r[0]) for r in p.execute(
        "SELECT id FROM question WHERE stem LIKE '%<svg%' OR stem LIKE '%<div%' "
        "OR answer LIKE '%<b %' OR answer LIKE '%<svg%'")}
    p.close()
    eq('无答案题 0 条入库', len(ids & noans), 0)
    eq('doc 11/12 的 620 题 0 条入库', len(ids & doc1112), 0)
    eq('HTML/SVG 题 0 条入库', len(ids & html), 0)
    check('源库确有这三类（反例不是空跑）',
          len(noans) == 620 and len(doc1112) == 620 and len(html) >= 9,
          f'无答案={len(noans)} doc11/12={len(doc1112)} html={len(html)}')


def t_readonly(sandbox):
    print('\n[10] 源库只读：桥对 资料库.db 的连接写不进去')
    conn = B.open_punch(sandbox / '资料库.db')
    try:
        conn.execute("UPDATE question SET answer='X' WHERE id=1")
        check('资料库.db 只读（写应报错）', False, '居然写成功了')
    except sqlite3.OperationalError as e:
        check('资料库.db 只读（写被拒）', 'readonly' in str(e).lower(), str(e))
    finally:
        conn.close()


def t_zero_llm(sandbox, base):
    print('\n[11] 零 LLM：桥源码干净 + 入库这条 import 链（ingest_flow）不触发向量模型')
    src = (HERE / 'bridge_questions.py').read_text(encoding='utf-8')
    banned = ('anthropic', 'openai', 'requests.post', 'urllib.request', 'http://', 'https://',
              'claude', 'gpt-', 'litellm', 'httpx', 'socket')
    hit = [w for w in banned if w.lower() in src.lower()]
    check('bridge_questions.py 无网络/模型调用痕迹', not hit, str(hit))

    # 🔴 只 grep 一个文件不算自证：桥的入库是 import 进来的，得把那条链一起断言。
    #    ingest_flow 有两条入库口径——
    #      · ingest_one：单题过闸入库，**不碰向量**；
    #      · cmd_ingest：批量口径，收尾会调 autovec 起本地 bge 模型算 question_vec。
    #    桥必须走前者，否则「零 LLM/零模型」就是空话（且会在桥里偷偷起模型）。
    check('桥调的是 ingest_flow.ingest_one', 'ingest_flow.ingest_one' in src)
    check('桥全文不出现 cmd_ingest（不走会起模型的批量口径）', 'cmd_ingest' not in src)
    one_src = inspect.getsource(ingest_flow.ingest_one)
    cmd_src = inspect.getsource(ingest_flow.cmd_ingest)
    # 🔴 说明性断言（六条修单第 6 条）：把「桥零 LLM」这句话拆成可机验的三段——
    #    ① 桥只调 ingest_one；② ingest_one 这一层自己不碰向量；③ 会起模型的是 cmd_ingest→autovec
    #    那条路，桥一步都不踏。三段都绿，「桥走 ingest_one 不触发任何向量/模型路径」才算证完。
    check('① 桥的入库门是 ingest_one，且 ingest_one 自身不调 autovec（这一层无向量）',
          'ingest_flow.ingest_one' in src and 'autovec' not in one_src)
    check('② 起模型的 autovec 挂在 cmd_ingest 上（说明这条自证不是空断言）', 'autovec(' in cmd_src)
    check('③ 桥源码里没有 autovec 调用点（事务内调它 = dry-run 真写库，见 [12]）',
          'ingest_flow.autovec(' not in src and 'autovec(kb' not in src)

    # 运行期反例：把 autovec 换成炸弹跑一遍真入库，没炸 = 桥这条路真没碰向量模型
    boomed = []

    def _boom(*a, **k):
        boomed.append(a)
        raise AssertionError('🔴 桥触发了 ingest_flow.autovec（会起本地 bge 模型）')

    orig = ingest_flow.autovec
    ingest_flow.autovec = _boom
    try:
        kb = fresh_kb(sandbox, 'novec')
        r = bridge(sandbox / '资料库.db', kb, apply_=True)
    finally:
        ingest_flow.autovec = orig
    check('--apply 真入库（新建数与 [5] 一致），全程零 autovec 调用',
          not boomed and r['stats']['新建'] == base['新建'],
          f'boomed={len(boomed)} 新建={r["stats"]["新建"]} 期望={base["新建"]}')
    check('embed_tool 始终没被 import 进来（懒加载没被触发）', 'embed_tool' not in sys.modules,
          str([m for m in sys.modules if 'embed' in m]))


def t_txn_bomb(sandbox):
    """🔴 事务炸弹专项：桥的写库循环整个跑在一个 BEGIN 里，事务内任何一句 commit
    都会把 dry-run 本该回滚的半截写入落地。历史实锤=桥曾在事务里调 autovec，
    autovec→embed_tool.save_vecs 收尾一句 conn.commit()，于是 dry-run 真写库。"""
    print('\n[12] 🔴 事务炸弹反例：事务内被 commit 一下 → dry-run 会真写库（桥必须零向量）')

    # ── (a) 机理自证：先证「事务里被 commit 一下，收尾 rollback 就真收不回来」──────
    demo = fresh_kb(sandbox, 'txn')
    conn = sqlite3.connect(str(demo))
    n0 = conn.execute('SELECT COUNT(*) FROM skill_log').fetchone()[0]
    conn.execute('BEGIN')
    conn.execute("INSERT INTO skill_log(skill,action,result,created_at) "
                 "VALUES ('反例·事务炸弹','txn-demo','成功',datetime('now'))")
    conn.commit()        # ← 冒充 embed_tool.save_vecs 收尾那一句
    conn.rollback()      # ← 冒充 dry-run 的收尾回滚
    n1 = conn.execute('SELECT COUNT(*) FROM skill_log').fetchone()[0]
    conn.close()
    eq('机理：BEGIN 里被 commit 一下，后面的 rollback 收不回来（脏行赖在库里）', n1 - n0, 1)

    # ── (b) 静态：那句 commit 真的在 save_vecs 里（证明上面的戒律不是假想敌）────────
    #    🔴 只读源码文本，绝不 import embed_tool——import 它就等于把模型这条链拉进本进程。
    es = (ROOT / '工具箱' / '检索' / 'embed_tool.py').read_text(encoding='utf-8')
    body = es.split('def save_vecs(')[1].split('\ndef ')[0] if 'def save_vecs(' in es else ''
    check('embed_tool.save_vecs 收尾确有 conn.commit()（事务炸弹的引信在这）',
          'conn.commit()' in body)
    check('ingest_flow.autovec 确实会走到 save_vecs（引信接在 autovec 上）',
          'save_vecs(' in inspect.getsource(REAL_AUTOVEC))

    # ── (c) 运行期反例（🔴 摘掉修复必红）：把 autovec 换成「像真 save_vecs 那样 commit 一下」的
    #        替身跑 dry-run。桥若在事务里调它，这一 commit 立刻把半截 question 落地，
    #        下面的逐表对比当场变红；桥不调它，替身根本不会被执行，逐表纹丝不动。
    kb = fresh_kb(sandbox, 'bomb')
    before = snapshot(kb)
    called = []

    def _commit_stub(conn_, qids, *a, **k):
        called.append(tuple(qids))
        conn_.commit()                       # ← 真 save_vecs 就是这么干的
        return len(qids), 'stub'

    orig = ingest_flow.autovec
    ingest_flow.autovec = _commit_stub
    try:
        r = bridge(sandbox / '资料库.db', kb, apply_=False)
    finally:
        ingest_flow.autovec = orig
    after = snapshot(kb)
    eq('替身一次都没被调到（桥的事务里没有 autovec）', called, [])
    eq('🔴 dry-run 后 kb.db 逐表行数与跑前完全一致（事务炸弹复活则此条必红）', after, before)
    check('这一跑不是空跑：桥确实算出了应吃题（有货可漏才谈得上没漏）',
          r['应吃'] > 0, f'应吃={r["应吃"]}')


def t_vec_hint(sandbox):
    print('\n[13] 零向量的另一半：桥不算向量，但必须把「待补向量」的命令印出来，不许静默')
    kb = fresh_kb(sandbox, 'hint')
    r, out = bridge_capture(sandbox / '资料库.db', kb, apply_=True)
    check('--apply 播报点名「待补」语意向量（不静默把新题晾在③层检索外）', '待补' in out, tail(out))
    check('--apply 播报给出可照抄的补向量命令（embed_tool.py build）',
          'embed_tool.py build' in out, tail(out))
    eq('--apply 之后这批题在库里确实一条向量都没有（播报说的是真话）',
       q(kb, "SELECT COUNT(*) FROM question_vec WHERE question_id LIKE 'qpunch%'"), 0)
    check('dry-run 播报不提「待补向量」（一题没入库，没什么可补）',
          '待补' not in bridge_capture(sandbox / '资料库.db', fresh_kb(sandbox, 'hint2'))[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sandbox', default=str(DEFAULT_SANDBOX))
    a = ap.parse_args()
    sandbox = Path(a.sandbox).resolve()
    for f in ('资料库.db', 'kb.pristine.db'):
        if not (sandbox / f).exists():
            sys.exit(f'🔴 沙盘缺 {f}：{sandbox / f}\n'
                     f'   建法：把 主位知识库/资料库.db 拷成 沙盘/资料库.db，'
                     f'主位知识库/kb.db 拷成 沙盘/kb.pristine.db')
    # 🔴 出件改道沙盘，绝不覆盖真交付件
    B.REPORT_DIR = sandbox / '_test' / '出件' / '记录'
    B.BRIDGE_DIR = sandbox / '_test' / '出件' / '桥'
    B.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    B.BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    install_no_model_guard()

    print(f'沙盘：{sandbox}')
    t_pure_functions()
    t_survey(sandbox)
    # 🔴 账面基线一律从这次 dry-run 现取（应吃/待入考点随 KG 铺枝进度天天变），下游全部照它推
    base = t_accounting(sandbox)
    t_limit_partial(sandbox)
    kb = t_apply_and_idempotent(sandbox, base)
    t_prov_carrier(sandbox, kb, base)
    t_no_carrier(sandbox)
    t_blocks_eyeball(sandbox, kb)
    t_negative(sandbox)
    t_readonly(sandbox)
    t_zero_llm(sandbox, base)
    t_txn_bomb(sandbox)
    t_vec_hint(sandbox)

    print(f'\n══ 通过 {len(PASS)} / 失败 {len(FAIL)} ══')
    for f in FAIL:
        print('  ✗ ' + f)
    sys.exit(1 if FAIL else 0)


if __name__ == '__main__':
    main()
