# -*- coding: utf-8 -*-
"""v2 三闸（纯函数库，供 skill / 脚本 import）。

    from gates import validate_blocks, assert_leaf_kp, execution_valve

判据出处（一切靠闸不靠注释，CLAUDE.md §3）：
  · 块流校验器  ← 认知/数据结构.md §2.1②（照老区 BlockJsonValidator 做成入库硬闸）
  · 考点叶子闸  ← 认知/数据结构.md §2.1③（老区 62% 挂章级 = 分轨分母失真）
  · 执行阀五条  ← 认知/数据结构.md §2.7 D-21 / 认知/业务流程.md §四

约定：闸一律「返回结构化结果」或「抛异常带原话」，绝不静默降级、绝不自动规整。
"""
import json
import re
import sqlite3

# ── 值域（与 认知/数据结构.md 一致，改这里=改契约）──────────────────────
BLOCK_TYPES = ('text', 'figure', 'option', 'table')      # 块型白名单
ROLES = ('题面', '答案', '解析', '点拨', '栏目')            # 块级 role 枚举
OPTION_LABELS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

# 🔴 题面首块不得以题号/分值前缀开头（老区「录入必跑前缀清洗」的 v2 落点：
#    SQLite 无 REGEXP，闸前移到入库前的纯函数层，这就是老区 REGEXP=0 口径的 v2 实现）
RE_QNO_PREFIX = re.compile(r'^\s*[0-9０-９]+\s*[、．.](?!\d)')
RE_SCORE_PREFIX = re.compile(r'^\s*[（(]\s*[0-9０-９]+(?:[.．][0-9０-９]+)?\s*分\s*[）)]')
# 宽度：百分比（0<v≤100）或带单位的绝对值
RE_WIDTH_PCT = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*%\s*$')
RE_WIDTH_ABS = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(px|pt|mm|cm|em|rem)\s*$')
# GFM 表：行首竖线 + 分隔行
RE_TABLE_LINE = re.compile(r'^\s*\|')
RE_TABLE_SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')


class GateError(Exception):
    """闸拒收（带原话）。"""


class LeafKpError(GateError):
    """考点叶子闸拒收。"""


# ══════════════════════════════════════════════════════════════════════
# 闸①　块流 v2 校验器
# ══════════════════════════════════════════════════════════════════════
def validate_blocks(blocks_json, *, is_stem=True):
    """校验块流 v2。

    参数：
      blocks_json —— JSON 字符串 或 已解析的 dict（{"v":2,"rows":[{"cells":[…]}]}）
      is_stem     —— 是否题面流（True 才跑「题号/分值前缀」闸；答案/解析流不跑）

    返回：(ok: bool, errors: list[str])  —— 不抛异常、不自动规整，问题原样列清楚。
    """
    errors = []

    # -- 0. 解析 --
    if isinstance(blocks_json, (bytes, bytearray)):
        blocks_json = blocks_json.decode('utf-8', 'replace')
    if isinstance(blocks_json, str):
        try:
            doc = json.loads(blocks_json)
        except Exception as e:
            return False, [f'块流不是合法 JSON：{e}']
    elif isinstance(blocks_json, dict):
        doc = blocks_json
    else:
        return False, [f'块流类型非法：{type(blocks_json).__name__}（要 JSON 字符串或 dict）']

    if not isinstance(doc, dict):
        return False, ['块流顶层必须是对象 {v, rows}']

    # -- 1. schema 版本位 --
    if doc.get('v') != 2:
        errors.append(f'v 必须 == 2（实际 {doc.get("v")!r}）——块流规范 v2，没有版本位就没法演进')

    # -- 2. rows / cells 结构 --
    rows = doc.get('rows')
    if not isinstance(rows, list) or not rows:
        errors.append('rows 必须是非空数组')
        return False, errors

    option_labels = []          # 全流按序收集，供标号连续闸
    first_text_md = None        # 题面首个正文块（供前缀闸）

    for ri, row in enumerate(rows):
        tag = f'rows[{ri}]'
        if not isinstance(row, dict):
            errors.append(f'{tag} 必须是对象 {{cells:[…]}}')
            continue
        cells = row.get('cells')
        if not isinstance(cells, list) or not cells:
            errors.append(f'{tag}.cells 必须是非空数组')
            continue
        for ci, cell in enumerate(cells):
            ctag = f'{tag}.cells[{ci}]'
            got_md = _check_cell(cell, ctag, errors, option_labels, depth=0)
            if first_text_md is None and got_md:
                first_text_md = got_md

    # -- 3. option 标号连续（不自动规整：跳号一律报 FAIL 交人审）--
    if option_labels:
        want = list(OPTION_LABELS[:len(option_labels)])
        if option_labels != want:
            errors.append(
                f'option 标号不连续：实际 {option_labels} / 应为 {want}'
                '——不自动规整（老区规整后「是否漏抽」变得不可验证），一律人工审')

    # -- 4. 题面首块前缀闸 --
    if is_stem and first_text_md is not None:
        m = RE_QNO_PREFIX.match(first_text_md)
        if m:
            errors.append(f'题面首块带题号前缀 {m.group(0)!r}——题号属载体不属题（question 表根本没有 qno 列），录入必剥')
        m = RE_SCORE_PREFIX.match(first_text_md if not m else first_text_md[m.end():])
        if m:
            errors.append(f'题面首块带分值前缀 {m.group(0)!r}——分值属载体位置（落 paper_item.score），不进题面')

    return (not errors), errors


def _check_cell(cell, tag, errors, option_labels, depth):
    """校验单个块；返回该块的正文文本（仅 text 块，供前缀闸取首块）。"""
    if not isinstance(cell, dict):
        errors.append(f'{tag} 必须是对象')
        return None
    btype = cell.get('type')
    if btype not in BLOCK_TYPES:
        errors.append(f'{tag}.type={btype!r} 不在白名单 {BLOCK_TYPES}——白名单外一律拒收')
        return None

    role = cell.get('role')
    if role is not None and role not in ROLES:
        errors.append(f'{tag}.role={role!r} 不在枚举 {ROLES}')

    if btype == 'text':
        md = cell.get('md')
        if not isinstance(md, str) or not md.strip():
            errors.append(f'{tag}.md 为空——text 块必须有正文')
            return None
        _check_gfm_table_blank_lines(md, tag, errors)
        return md

    if btype == 'figure':
        asset = cell.get('asset')
        if not isinstance(asset, str) or not asset.strip():
            errors.append(f'{tag}.asset 缺失——figure 必须指向 asset（图在流内，库里只存指针）')
        width = cell.get('width')
        if width is None:
            errors.append(f'{tag}.width 缺失——老区 5467 个图块 100% 带宽度，丢了出纸质件全靠猜、宽图撑破版面')
        else:
            _check_width(width, tag, errors)
        return None

    if btype == 'option':
        label = cell.get('label')
        if not isinstance(label, str) or label not in OPTION_LABELS:
            errors.append(f'{tag}.label={label!r} 非法（要 A/B/C/… 单字母）')
        else:
            option_labels.append(label)
        subs = cell.get('blocks')
        if not isinstance(subs, list) or not subs:
            errors.append(f'{tag}.blocks 必须是非空数组（一项一 cell，结构化）')
            return None
        if depth >= 1:
            errors.append(f'{tag} option 不允许嵌套 option')
            return None
        nfig = 0
        for si, sub in enumerate(subs):
            if isinstance(sub, dict) and sub.get('type') == 'figure':
                nfig += 1
            _check_cell(sub, f'{tag}.blocks[{si}]', errors, [], depth + 1)
        if nfig > 1:
            errors.append(f'{tag} 含 {nfig} 张图——每个选项至多 1 图')
        return None

    if btype == 'table':
        # 🔴 裁量：SSOT 只把 table 列进块型白名单，未给出内部 schema。
        #    此处按最保守口径：要么 md（GFM 全表），要么 rows（cell 装块列表，禁拍平成字符串）。
        md = cell.get('md')
        trows = cell.get('rows')
        if isinstance(md, str) and md.strip():
            lines = md.splitlines()
            if not any(RE_TABLE_SEP.match(x) for x in lines):
                errors.append(f'{tag}.md 是表格块却没有 |---| 分隔行')
        elif isinstance(trows, list) and trows:
            for ri, trow in enumerate(trows):
                if not isinstance(trow, list):
                    errors.append(f'{tag}.rows[{ri}] 必须是 cell 数组')
                    continue
                for ci, tcell in enumerate(trow):
                    if not isinstance(tcell, list):
                        errors.append(f'{tag}.rows[{ri}][{ci}] 必须是块列表（cell 装块列表，禁拍平成字符串：拍平必丢格内图）')
                        continue
                    for bi, blk in enumerate(tcell):
                        _check_cell(blk, f'{tag}.rows[{ri}][{ci}][{bi}]', errors, [], depth + 1)
        else:
            errors.append(f'{tag} 表格块必须有 md（GFM）或 rows（结构化 cell 块列表）')
        return None

    return None


def _check_width(width, tag, errors):
    if isinstance(width, (int, float)):
        errors.append(f'{tag}.width={width!r} 无单位——必须写 "48%" 或 "60mm" 这类带单位值')
        return
    if not isinstance(width, str):
        errors.append(f'{tag}.width 类型非法（{type(width).__name__}）')
        return
    m = RE_WIDTH_PCT.match(width)
    if m:
        v = float(m.group(1))
        if not (0 < v <= 100):
            errors.append(f'{tag}.width={width!r} 百分比越界（要 0<v≤100）')
        return
    if RE_WIDTH_ABS.match(width):
        return
    errors.append(f'{tag}.width={width!r} 非法——只认 "NN%" 或 "NN px|pt|mm|cm|em|rem"')


def _check_gfm_table_blank_lines(md, tag, errors):
    """GFM 表前后必须空行（老区 121 处病根：缺空行会把表格后的整段吞成表格行）。"""
    lines = md.split('\n')
    i = 0
    while i < len(lines):
        if RE_TABLE_LINE.match(lines[i]):
            j = i
            while j < len(lines) and RE_TABLE_LINE.match(lines[j]):
                j += 1
            block = lines[i:j]
            if any(RE_TABLE_SEP.match(x) for x in block):
                if i > 0 and lines[i - 1].strip() != '':
                    errors.append(f'{tag} GFM 表前缺空行（第 {i + 1} 行起）——缺空行会吞掉相邻整段，内容一字不差却是错的')
                if j < len(lines) and lines[j].strip() != '':
                    errors.append(f'{tag} GFM 表后缺空行（第 {j} 行后）——同上')
            i = j
        else:
            i += 1


# ══════════════════════════════════════════════════════════════════════
# 闸②　考点叶子闸
# ══════════════════════════════════════════════════════════════════════
def assert_leaf_kp(conn, kp_id):
    """kp_id 必须存在且无子节点，否则抛 LeafKpError（带原话）。通过返回 True。"""
    if not isinstance(kp_id, str) or not kp_id.strip():
        raise LeafKpError(
            f'考点叶子闸：kp_id={kp_id!r} 非法——每题必挂考点，挂不上就不入库，绝不裸题入库。')
    row = conn.execute('SELECT id, name, level FROM kp WHERE id = ?', (kp_id,)).fetchone()
    if row is None:
        raise LeafKpError(
            f'考点叶子闸：kp_id={kp_id!r} 在 kp 表里不存在——kp_id 必 resolve（名/别名→叶子），'
            f'严禁编造；挂不上就不入库，绝不裸题入库。')
    n = conn.execute('SELECT COUNT(*) FROM kp WHERE parent_id = ?', (kp_id,)).fetchone()[0]
    if n:
        name, level = row[1], row[2]
        raise LeafKpError(
            f'考点叶子闸：kp_id={kp_id!r}（{name}，level={level}）有 {n} 个子节点，不是叶子。'
            f'老区 dim1_kp_id 的注释写「挂叶子」，实测 62% 挂在章级（322 个被用考点里 108 个有子节点）——'
            f'这直接威胁「学情按考点分轨」：分母是考点集，挂章级就等于分母失真。违例拒收不静默。')
    return True


# ══════════════════════════════════════════════════════════════════════
# 闸③　入库执行阀（五条硬闸，全过才入）
# ══════════════════════════════════════════════════════════════════════
# 🔴 存取同构：除块流三件外的任何「第二载体」字段一律拒收
#    （老区三载体并存 stem_text/block_json/text_content，15674 题 46% 一点答案都没有）
SECOND_CARRIERS = (
    'stem_text', 'text_content', 'stem_html', 'html', 'content_html', 'stem_md',
    'answer_text', 'analysis_text', 'answer_html', 'analysis_html', 'block_json', 'text',
)
CONF_MIN = 85.0


def execution_valve(item, conn=None):
    """入库执行阀五条。

    item 期望字段：
        blocks_json / blocks       题面块流（必需）
        answer_blocks_json / analysis_blocks_json   可选，同构
        confidence                 置信度（0-100；≤1 视为比例自动×100）
        kp_ids                     考点 id 数组（或 kp_id 单值）
        primary_kp                 可选，主考点（须在 kp_ids 内）
        is_pure_figure             可选，显式标注纯图题；不给则从块流自动判定
        reviewed / review_skipped_by_user   纯图题的过审痕迹
    conn —— 可选 sqlite3 连接（给了才跑叶子闸的库查；不给则只查「有没有挂」）

    返回：(ok: bool, results: list[dict])，每条 {'no','name','ok','detail'}。
    """
    results = []

    def add(no, name, ok, detail):
        results.append({'no': no, 'name': name, 'ok': bool(ok), 'detail': detail})

    if not isinstance(item, dict):
        add(0, '入参', False, f'item 必须是 dict（实际 {type(item).__name__}）')
        return False, results

    # ①置信度 ≥ 85%
    conf = item.get('confidence')
    if conf is None:
        add(1, '置信度≥85', False, '缺 confidence——不许静默入，低置信滞留待审')
    elif not isinstance(conf, (int, float)) or isinstance(conf, bool):
        add(1, '置信度≥85', False, f'confidence 类型非法：{conf!r}')
    else:
        v = float(conf) * 100 if 0 <= float(conf) <= 1 else float(conf)
        add(1, '置信度≥85', v >= CONF_MIN, f'confidence={v:.1f}（阈值 {CONF_MIN:.0f}）')

    # ②格式清晰：块流过校验器
    raw = item.get('blocks_json', item.get('blocks'))
    if raw is None:
        add(2, '块流校验器', False, '缺 blocks_json——题面正文只有块流一份')
        stem_doc = None
    else:
        ok2, errs = validate_blocks(raw, is_stem=True)
        for key, label in (('answer_blocks_json', '答案'), ('analysis_blocks_json', '解析')):
            sub = item.get(key)
            if sub:
                ok_sub, errs_sub = validate_blocks(sub, is_stem=False)
                ok2 = ok2 and ok_sub
                errs += [f'[{label}] {e}' for e in errs_sub]
        add(2, '块流校验器', ok2, '全过' if ok2 else '；'.join(errs[:4]) + ('…' if len(errs) > 4 else ''))
        stem_doc = _safe_load(raw)

    # ③存取同构：无第二载体字段
    dirty = [k for k in SECOND_CARRIERS if item.get(k) not in (None, '', [], {})]
    add(3, '存取同构', not dirty,
        '所见=所存=所印，无第二载体' if not dirty
        else f'检出第二载体字段 {dirty}——存进库的格式=直接使用的格式，没有出库转换层')

    # ④纯图题标记需审
    pure = item.get('is_pure_figure')
    if pure is None:
        pure = _is_pure_figure(stem_doc)
    passed_review = bool(item.get('reviewed')) or bool(item.get('review_skipped_by_user'))
    if pure:
        add(4, '纯图题需审', passed_review,
            '纯图题面且已过审/用户明说跳过' if passed_review
            else '纯图片题面可入，但必须过审——或用户明确说跳过审核才免')
    else:
        add(4, '纯图题需审', True, '非纯图题，不适用')

    # ⑤必挂叶子考点
    kp_ids = item.get('kp_ids')
    if kp_ids is None and item.get('kp_id'):
        kp_ids = [item['kp_id']]
    if not kp_ids or not isinstance(kp_ids, (list, tuple)):
        add(5, '必挂叶子考点', False, '未挂考点——挂不上就不入库，绝不裸题入库')
    else:
        detail, ok5 = [], True
        primary = item.get('primary_kp')
        if primary is not None and primary not in kp_ids:
            ok5 = False
            detail.append(f'primary_kp={primary!r} 不在 kp_ids 内')
        if conn is None:
            detail.append(f'已挂 {len(kp_ids)} 个考点（未给 conn，叶子闸未查库）')
        else:
            for kid in kp_ids:
                try:
                    assert_leaf_kp(conn, kid)
                except LeafKpError as e:
                    ok5 = False
                    detail.append(str(e))
            if ok5:
                detail.append(f'{len(kp_ids)} 个考点全是叶子')
        add(5, '必挂叶子考点', ok5, '；'.join(detail))

    return all(r['ok'] for r in results), results


def _safe_load(raw):
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return None


def _is_pure_figure(doc):
    """题面只有图、没有任何正文字 ⇒ 纯图题。"""
    if not isinstance(doc, dict):
        return False
    has_fig = has_text = False
    for row in doc.get('rows') or []:
        for cell in (row or {}).get('cells') or []:
            if not isinstance(cell, dict):
                continue
            t = cell.get('type')
            if t == 'figure':
                has_fig = True
            elif t == 'text' and str(cell.get('md') or '').strip():
                has_text = True
            elif t == 'table':
                has_text = True
            elif t == 'option':
                for sub in cell.get('blocks') or []:
                    if isinstance(sub, dict):
                        if sub.get('type') == 'figure':
                            has_fig = True
                        elif sub.get('type') == 'text' and str(sub.get('md') or '').strip():
                            has_text = True
    return has_fig and not has_text


def open_kb(db_path):
    """便捷：按纪律打开 kb.db（外键强制开）。"""
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn
