# -*- coding: utf-8 -*-
"""渲染出件 · render-pack 消费器（PRD-002「库中心产线」第二件：渲染从库读）
==============================================================================
🔴 **本工具不连库取题**。组卷侧（`工具箱/组卷/paper_tool.py render-pack`）把
   `paper + paper_item + question.blocks_json/answer/analysis` 一次性导成
   `render-pack/v1` JSON，本工具只吃那个文件出件 —— 渲染与库读写彻底解耦，
   worktree 里跑也绝不碰主位两库（唯一的库动作是可选的 skill_log 落账，`--db` 参数化）。

管线位置：出题→过三闸入库→组卷（库里取题）→**导 render-pack**→〔本工具〕→双 PDF→挂账。

用法
----
    python 工具箱/渲染/render_paper.py <render-pack.json> --out-dir <目录>
           [--stem <文件名主干>] [--sample-ord N] [--png]
           [--db <kb.db>] [--asset-root <目录>] [--no-log]

出件
----
    <out-dir>/<stem>.pdf          题目卷
    <out-dir>/<stem>（答案）.pdf   答案卷
    <out-dir>/_源/                 中间 HTML 与目检 PNG（core 落这里）

figure 的 asset 怎么落到文件（2026-08-20 实装，口径见 §一·五 AssetResolver）
------------------------------------------------------------------------
    figure.asset（内容 hash）→ ① pack 顶层 `assets` 带 rel_path 就直接用；
    ② 否则**只读**开 --db 查 `asset.rel_path`；③ rel_path 一律相对 v2 根，
    拼 --asset-root（缺省 = v2 根）转绝对 → `file:///…` 进 <img src>。
    查不到 / 盘上没这个文件 → 拒渲，绝不出一份缺图的卷。

🔴 拒渲清单（一切靠闸不靠注释，违例一律非零退出，绝不静默降级）
  · contract ≠ render-pack/v1
  · blocks 里 `$` 数目为奇数 / 出现 `$$` 显示公式
  · figure 缺 asset / 缺 width / width 无单位 / asset 库里查不到 / 文件不在盘上
  · figure 的 rel_path 是绝对路径或跳出资产根（文件指针一律相对）
  · table 块既无 md 也无 rows / GFM 无 |---| 分隔行 / 列数对不上 / 单元格被拍平成字符串
  · text 块的 md 里夹 GFM 表（表要用 table 块，混在正文里会印成一堆竖线）
  · expr/oral 槽位的题面里出现 figure/table（那两个槽只吃一条算式，图表题走 fill/word/choice）
  · item.section 不在该 paper 的 layout.sections 里
  · 解析的「＝」行不是纯公式（中文不许混进 LaTeX —— 渲染出件 SKILL.md §4）
  · expr/oral 槽位既无解析＝链也无答案公式（会出一份没有答案的答案卷）
  · 单节题数 > 10（渲染器答案卷圈码只有 ①~⑩）
"""
import argparse
import html as _html
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 本文件在 <v2根>/工具箱/渲染/ → 上跳 2 层 = v2 根（worktree 里就是 worktree 根）
ROOT = Path(__file__).resolve().parents[2]
PUNCHKIT_HOME = ROOT / '.claude' / 'skills' / '每日打卡' / '_模板'
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
CONTRACT = 'render-pack/v1'

sys.path.insert(0, str(PUNCHKIT_HOME))
from punchkit import core, layouts, renderers          # noqa: E402


class PackError(Exception):
    """render-pack 不合契约 / 数据渲不了 —— 一律拒渲，不静默兜底。"""


class Html(str):
    """**已经渲成 HTML 的一行**（figure / table 块的产物），带 `kind`（figure|table）。

    md_lines 的返回值本来全是 md 串，下游会拿去数 `$`、剥定界、判「是不是纯公式」；
    图与表不是 md，用这个 str 子类打标：`md_to_delim` 见到它原样透出，
    `pure_formula` / `first_formula` 一律返回 None（它压根不是公式）。
    🔴 不给它做「HTML→md 反推」——存取同构，渲成什么就是什么，没有回转层。
    """

    __slots__ = ('kind',)

    def __new__(cls, s, kind='html'):
        o = super(Html, cls).__new__(cls, s)
        o.kind = kind
        return o


# ══════════════════════════════════════════════════════════════════════
# 一、md → 渲染层定界串（$…$ → \(…\)）
# ══════════════════════════════════════════════════════════════════════
# 渲染层吃 MathJax，core.build_html 只声明了 inlineMath=[["\\(","\\)"]]，
# 而库里存的是 blocks_json 规范 v2 的 md + 内联 $LaTeX$（数据结构 §2.1②）。
# 这一层是**唯一**的形态转换点，别在别处再转一次。

def _dollars(md):
    """未转义 `$` 的下标表。`\\$` 不算定界；`$$` 直接拒（本版不支持显示公式）。"""
    pos, i, n = [], 0, len(md)
    while i < n:
        c = md[i]
        if c == '\\' and i + 1 < n:              # \x 整体跳过（含 \$ \\ \( 等）
            i += 2
            continue
        if c == '$':
            if i + 1 < n and md[i + 1] == '$':
                raise PackError('出现 `$$` 显示公式，本版只吃内联 $…$：%s' % md[:60])
            pos.append(i)
        i += 1
    return pos


def _math_safe(tex):
    """公式段内的三处硬伤（渲染出件 SKILL.md §4）：
       `<`/`>` 必须转 \\lt/\\gt（裸尖括号在 HTML 里会被当标签起头）；`&` 转实体
       （DOM textContent 解码回 `&`，MathJax 拿到的仍是原字符）。"""
    return tex.replace('&', '&amp;').replace('<', r'\lt ').replace('>', r'\gt ')


def _text_safe(s):
    """文字段：`\\$` 还原成字面 `$`，再做 HTML 转义。"""
    return _html.escape(s.replace('\\$', '$'), quote=False)


def md_to_delim(md, where='?'):
    """整段 md → HTML 串，`$…$` 换成 `\\(…\\)`。奇数个 `$` 拒渲。

    🔴 已渲好的块（figure/table 的 Html）原样透出——它不是 md，别再解析一遍。"""
    if isinstance(md, Html):
        return str(md)
    md = md or ''
    try:
        pos = _dollars(md)
    except PackError as e:
        raise PackError('[%s] %s' % (where, e))
    if len(pos) % 2:
        raise PackError('[%s] `$` 数目为奇数（%d 个），公式定界不成对：%s'
                        % (where, len(pos), md[:60]))
    out, prev, inside = [], 0, False
    for p in pos:
        seg = md[prev:p]
        out.append(_math_safe(seg) if inside else _text_safe(seg))
        out.append('\\)' if inside else '\\(')
        inside = not inside
        prev = p + 1
    out.append(_text_safe(md[prev:]))
    return ''.join(out)


def pure_formula(md, where='?'):
    """整段就是**一个** `$…$` 时返回里面的裸 tex；否则 None。图/表块永远 None。"""
    if isinstance(md, Html):
        return None
    s = (md or '').strip()
    if len(s) < 2 or not s.startswith('$'):
        return None
    try:
        pos = _dollars(s)
    except PackError as e:
        raise PackError('[%s] %s' % (where, e))
    if pos == [0, len(s) - 1]:
        return _math_safe(s[1:-1])
    return None


def first_formula(md, where='?'):
    """取该行第一个 `$…$` 的裸 tex；整行无公式返回 None。图/表块永远 None。"""
    if isinstance(md, Html):
        return None
    t = pure_formula(md, where)
    if t is not None:
        return t
    pos = _dollars(md or '')
    if len(pos) < 2:
        return None
    return _math_safe(md[pos[0] + 1:pos[1]])


def stem_tex(md, where='?'):
    """做成可直接塞进渲染器 `M()`（= 外面还会包一层 `\\(…\\)`）的串。

    · 纯公式 → 裸 tex（正常路，expr/oral 槽位的常态）；
    · 中文与公式混排 → 🔴 **不能**把定界串直接塞进去（会 `\\(计算：\\(3+5\\)\\)` 嵌套失效），
      也不许把中文包进 `\\text{}`（"中文不混进 LaTeX"，渲染出件 SKILL.md §4）。
      办法：首尾各"先关后开"，让渲染器外包的那对定界退化成两个**空公式**（零宽无痕），
      中间照常是「文字 + \\(公式\\)」的混排 HTML。
    """
    t = pure_formula(md, where)
    if t is not None:
        return t
    return '\\)' + md_to_delim(md, where) + '\\('


# ══════════════════════════════════════════════════════════════════════
# 一·五、figure / table 两个块型（2026-08-20 实装，此前显式拒渲）
# ══════════════════════════════════════════════════════════════════════
# 🔴 闸口径同源于 工具箱/库/gates.py（RE_WIDTH_PCT / RE_WIDTH_ABS / RE_TABLE_SEP）。
#    这里**不 import 闸库** —— 渲染与库彻底解耦是本工具的立身之本（见文件头）；
#    代价是改闸时两处一起改，所以每条都在报错里写清出处，别让它们悄悄漂开。
_RE_W_PCT = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*%\s*$')
_RE_W_ABS = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*(px|pt|mm|cm|em|rem)\s*$')
_RE_TBL_SEP = re.compile(r'^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$')
_RE_TBL_LINE = re.compile(r'^\s*\|')

# 答案卷里顶掉题面图的占位（省纸口径：题面图不在答案卷重印一遍）
FIG_IN_Q = '（图见题目卷）'


def fig_style(width, tag):
    """块 width → `<img>` 的 style。

    🔴 百分比 = **按块宽限宽**（闸口径 0<v≤100），绝对值原样落；两者都再压一道
       `max-width:100%` —— 版心比图窄时宁可缩，不许撑破版面（老区宽图撑版的原病）。
    """
    if width is None:
        raise PackError('[%s] figure 缺 width —— 老区 5467 个图块 100%% 带宽度，'
                        '丢了出纸质件全靠猜、宽图撑破版面，拒渲' % tag)
    if not isinstance(width, str):
        raise PackError('[%s] figure.width=%r 无单位/类型非法 —— 只认 "48%%" 或 "60mm" 这类带单位值'
                        % (tag, width))
    m = _RE_W_PCT.match(width)
    if m:
        v = float(m.group(1))
        if not (0 < v <= 100):
            raise PackError('[%s] figure.width=%r 百分比越界（要 0<v≤100），拒渲' % (tag, width))
        return 'width:%g%%;max-width:100%%' % v
    m = _RE_W_ABS.match(width)
    if m:
        return 'width:%g%s;max-width:100%%' % (float(m.group(1)), m.group(2))
    raise PackError('[%s] figure.width=%r 非法 —— 只认 "NN%%" 或 "NN px|pt|mm|cm|em|rem"，拒渲'
                    % (tag, width))


class AssetResolver(object):
    """🔴 figure 的 `asset`（内容 hash）→ 可直接给 `<img src>` 的 `file:///` 绝对 URL。

    口径三步，任何一步塌了都**拒渲**（缺图的卷=废纸，绝不静默丢图）：
      ① **pack 自带优先**：pack 顶层 `assets`（`{hash: rel_path}` 或
         `{hash: {"rel_path": …}}`）里有就直接用，一次库都不查
         —— 组卷侧将来把 rel_path 一起导出来，渲染端就彻底不碰库；
      ② **否则只读查库**：`sqlite3.connect(file:…?mode=ro, uri=True)` 查
         `SELECT rel_path FROM asset WHERE hash=?`。mode=ro 是硬要求：渲染端对库
         **一个数据字节都不写**，worktree/沙盘里跑也不会改主位的库。
         ⚠️ 实测口径（2026-08-20，别当成"完全不碰盘"）：kb.db 是 WAL 库，
         `-shm`/`-wal` 旁挂文件若不存在，**mode=ro 的读者也会把它们建出来**——
         那是读 WAL 库的必要开销，不是数据变更。`immutable=1` 能躲开这一笔，
         但它会**看不见还没 checkpoint 的新行**（刚入库的图查不到 → 假拒渲），
         比建两个旁挂文件坏得多，所以不用它。这条写在这儿，免得注释撒谎。
      ③ **rel_path 一律相对 v2 根**（schema_kb.sql asset.rel_path 的原话）：
         绝对路径 / 跳出根 一律拒；拼 `asset_root`（缺省 = 本文件自解析的 v2 根）
         转绝对，文件必须真的在盘上，再转 `file:///…`。

    注：`asset_root` 独立于 `--db` 是有意的 —— 沙盘自测时库是副本、资产也是副本，
    两者都要能整体挪窝；主位跑不给这个参数，就是 v2 根，与 rel_path 的定义一致。
    """

    def __init__(self, pack=None, db=None, root=None):
        self.root = Path(root) if root else ROOT
        self.db = Path(db) if db else None
        self.inline = {}
        raw = (pack or {}).get('assets') or {}
        if isinstance(raw, dict):
            for h, v in raw.items():
                rel = v.get('rel_path') if isinstance(v, dict) else v
                if isinstance(rel, str) and rel.strip():
                    self.inline[str(h)] = rel.strip()
        self._cache = {}
        self._conn = None

    def _rel_from_db(self, h, tag):
        import sqlite3
        if self.db is None:
            raise PackError('[%s] figure 的 asset=%s 要查库拿 rel_path，但没给 --db，'
                            'pack 里也没带 assets 表 —— 拒渲，不静默丢图' % (tag, h))
        if not self.db.exists():
            raise PackError('[%s] figure 的 asset=%s 要查的库不存在：%s —— 拒渲' % (tag, h, self.db))
        if self._conn is None:
            try:
                self._conn = sqlite3.connect(self.db.resolve().as_uri() + '?mode=ro', uri=True)
            except Exception as e:
                raise PackError('[%s] 只读打开库失败（%s）：%s' % (tag, self.db, e))
        try:
            row = self._conn.execute('SELECT rel_path FROM asset WHERE hash=?', (h,)).fetchone()
        except Exception as e:
            raise PackError('[%s] 查 asset 表失败（%s）：%s' % (tag, self.db, e))
        if not row or not row[0]:
            raise PackError('[%s] asset=%s 在库里查不到（%s）—— 图指针悬空，拒渲不静默丢图'
                            % (tag, h, self.db))
        return row[0]

    def url(self, h, tag):
        if h in self._cache:
            return self._cache[h]
        rel = self.inline.get(h)
        src = 'pack.assets' if rel else 'asset 表'
        if not rel:
            rel = self._rel_from_db(h, tag)
        s = str(rel).replace('\\', '/').strip()
        if not s:
            raise PackError('[%s] asset=%s 的 rel_path 是空串（%s），拒渲' % (tag, h, src))
        if s.startswith('/') or s.startswith('file:') or re.match(r'^[A-Za-z]:', s):
            raise PackError('[%s] asset=%s 的 rel_path 是绝对路径 %r（%s）—— 🔴 文件指针一律相对 v2 根'
                            '（老货架 717 行绝对路径全断的血案），拒渲' % (tag, h, rel, src))
        base = self.root.resolve()
        full = (base / s).resolve()
        try:
            full.relative_to(base)
        except ValueError:
            raise PackError('[%s] asset=%s 的 rel_path %r 跳出了资产根 %s，拒渲' % (tag, h, rel, base))
        if not full.exists():
            raise PackError('[%s] asset=%s 的文件不在盘上：%s（rel_path=%r 来自 %s，根=%s）—— '
                            '拒渲，绝不出一份缺图的卷' % (tag, h, full, rel, src, base))
        u = 'file:///' + str(full).replace('\\', '/')
        self._cache[h] = u
        return u

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def figure_html(cell, tag, assets):
    """figure 块 → `<img class="fig">`（一行一图，Html 打标 kind='figure'）。"""
    asset = cell.get('asset')
    if not isinstance(asset, str) or not asset.strip():
        raise PackError('[%s] figure 缺 asset —— 图在流内、库里只存指针（gates.py 闸口径），拒渲' % tag)
    asset = asset.strip()
    style = fig_style(cell.get('width'), tag)
    if assets is None:
        raise PackError('[%s] 出现 figure（asset=%s）但没有 asset 解析器 —— '
                        '给 --db <kb.db> 或让 pack 带 assets 表，拒渲不静默丢图' % (tag, asset))
    return Html('<img class="fig" src="%s" style="%s" alt="figure %s">'
                % (assets.url(asset, tag), style, _html.escape(asset, quote=True)),
                kind='figure')


def _gfm_cells(line):
    """GFM 一行 → 单元格列表。`\\|` 是格内竖线不切（切错会把一格劈成两格）。"""
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    cells, buf, i, n = [], [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            buf.append('|' if s[i + 1] == '|' else s[i:i + 2])
            i += 2
            continue
        if c == '|':
            cells.append(''.join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    tail = ''.join(buf)
    if tail.strip() or not cells:
        cells.append(tail)
    return [x.strip() for x in cells]


def table_from_gfm(md, tag):
    """GFM 全表 md → HTML 表。表头行 + `|---|` 分隔行 + 若干正文行，列数必须齐。"""
    lines = [x for x in (md or '').split('\n') if x.strip()]
    if len(lines) < 2:
        raise PackError('[%s] GFM 表不足两行（至少「表头行 + |---| 分隔行」），坏表拒渲' % tag)
    seps = [i for i, x in enumerate(lines) if _RE_TBL_SEP.match(x)]
    if not seps:
        raise PackError('[%s] GFM 表没有 |---| 分隔行（gates.py RE_TABLE_SEP 同款判据），坏表拒渲' % tag)
    if seps[0] != 1:
        raise PackError('[%s] GFM 表的 |---| 分隔行落在第 %d 行 —— 必须紧跟表头行（第 2 行），坏表拒渲'
                        % (tag, seps[0] + 1))
    head = _gfm_cells(lines[0])
    ncol = len(head)
    if ncol < 1 or not any(x for x in head):
        raise PackError('[%s] GFM 表头一格内容都没有，坏表拒渲' % tag)
    if len(_gfm_cells(lines[1])) != ncol:
        raise PackError('[%s] GFM 表分隔行 %d 列，表头 %d 列 —— 列数对不上，坏表拒渲'
                        % (tag, len(_gfm_cells(lines[1])), ncol))
    body = []
    for i, ln in enumerate(lines[2:], start=3):
        if not _RE_TBL_LINE.match(ln) and '|' not in ln:
            raise PackError('[%s] GFM 表第 %d 行不是表格行：%s —— 表里混进正文（老区 121 处病根：'
                            '会把整段吞成表格行），坏表拒渲' % (tag, i, ln.strip()[:40]))
        row = _gfm_cells(ln)
        if len(row) != ncol:
            raise PackError('[%s] GFM 表第 %d 行 %d 列，表头 %d 列 —— 列数对不上，坏表拒渲'
                            '（错位的表比没表更坏）' % (tag, i, len(row), ncol))
        body.append(row)
    th = ''.join('<th>%s</th>' % md_to_delim(c, '%s.表头%d' % (tag, j + 1))
                 for j, c in enumerate(head))
    trs = ['<tr>%s</tr>' % ''.join('<td>%s</td>' % md_to_delim(c, '%s.第%d行第%d列'
                                                               % (tag, r + 1, j + 1))
                                   for j, c in enumerate(row))
           for r, row in enumerate(body)]
    return Html('<table class="tbl"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
                % (th, ''.join(trs)), kind='table')


def table_from_rows(rows, tag, assets):
    """结构化 rows（cell 装块列表）→ HTML 表。格内认 text 与 figure，表中表/表中选项拒渲。

    🔴 无表头形态（闸只给了 `rows`，没有「哪行是表头」的信号）—— 一律 `<td>`，
       不猜第一行是不是表头（猜错=卷面撒谎）。要表头就用 GFM 形态。
    """
    trs, ncol = [], None
    for ri, row in enumerate(rows):
        if not isinstance(row, list):
            raise PackError('[%s].rows[%d] 必须是 cell 数组（gates.py 闸口径），坏表拒渲' % (tag, ri))
        if ncol is None:
            ncol = len(row)
        elif len(row) != ncol:
            raise PackError('[%s].rows[%d] 有 %d 格，首行 %d 格 —— 列数对不上，坏表拒渲'
                            % (tag, ri, len(row), ncol))
        tds = []
        for ci, cell in enumerate(row):
            ctag = '%s.rows[%d][%d]' % (tag, ri, ci)
            if not isinstance(cell, list):
                raise PackError('[%s] 必须是块列表（cell 装块列表，禁拍平成字符串：拍平必丢格内图），'
                                '坏表拒渲' % ctag)
            inner = []
            for bi, blk in enumerate(cell):
                btag = '%s[%d]' % (ctag, bi)
                if not isinstance(blk, dict):
                    raise PackError('[%s] 单元格内的块必须是对象，坏表拒渲' % btag)
                t = blk.get('type')
                if t == 'text':
                    inner.append('<br>'.join(md_to_delim(x.strip(), btag)
                                             for x in (blk.get('md') or '').split('\n')
                                             if x.strip()))
                elif t in ('figure', 'image'):
                    inner.append(str(figure_html(blk, btag, assets)))
                else:
                    raise PackError('[%s] 单元格内出现 %r 块 —— 格内只认 text 与 figure'
                                    '（表中表 / 表中选项拒渲），坏表拒渲' % (btag, t))
            tds.append('<td>%s</td>' % ''.join(inner))
        trs.append('<tr>%s</tr>' % ''.join(tds))
    if not ncol:
        raise PackError('[%s].rows 一格都没有，坏表拒渲' % tag)
    return Html('<table class="tbl"><tbody>%s</tbody></table>' % ''.join(trs), kind='table')


def table_html(cell, tag, assets):
    """table 块 → HTML 表。两形态（gates.py 闸口径）：md=GFM 全表 / rows=结构化 cell 块列表。"""
    md = cell.get('md')
    rows = cell.get('rows')
    if isinstance(md, str) and md.strip():
        return table_from_gfm(md, tag)
    if isinstance(rows, list) and rows:
        return table_from_rows(rows, tag, assets)
    raise PackError('[%s] table 块既无 md（GFM 全表）也无 rows（结构化 cell 块列表）—— '
                    '闸口径就这两形态，坏表拒渲' % tag)


def _guard_inline_gfm(md, tag):
    """🔴 text 块的 md 里夹 GFM 表 = 拒渲。

    表要用 `table` 块。混在正文里的下场：渲染端按行拆，卷面印出一堆竖线与减号
    （老区 121 处病根同源）—— 「内容一字不差却是错的」，静默印出去比拒渲坏得多。
    """
    lines = (md or '').split('\n')
    for i, ln in enumerate(lines):
        if _RE_TBL_SEP.match(ln) and i and _RE_TBL_LINE.match(lines[i - 1]):
            raise PackError('[%s] text 块的 md 里夹了 GFM 表（第 %d 行是 |---| 分隔行）—— '
                            '表要用 table 块，混在正文里会印成一堆竖线，拒渲：%s'
                            % (tag, i + 1, lines[i - 1].strip()[:40]))


# ══════════════════════════════════════════════════════════════════════
# 二、blocks_json v2 → 文本行
# ══════════════════════════════════════════════════════════════════════
def md_lines(blocks, where='?', assets=None):
    """blocks_json v2 → 行列表：text 块出 md 串，figure/table 块出已渲好的 `Html`。

    `assets` = AssetResolver（figure 才用得着）；没给而块流里有 figure = 拒渲不静默丢图。
    """
    if blocks in (None, '', {}):
        return []
    if isinstance(blocks, str):
        try:
            blocks = json.loads(blocks)
        except Exception as e:
            raise PackError('[%s] blocks 不是合法 JSON：%s' % (where, e))
    if not isinstance(blocks, dict) or 'rows' not in blocks:
        raise PackError('[%s] blocks 不是 {v,rows} 结构' % where)
    v = blocks.get('v')
    if str(v) != '2':
        raise PackError('[%s] blocks 版本 v=%r，本版只吃 v2（数据结构 §2.1②）' % (where, v))
    out = []
    for r, row in enumerate(blocks.get('rows') or []):
        cells = row.get('cells') or []
        # ── option 行级处理（2026-08-20 补实装：选择题「出」通路）──
        # 同一 row 里的 option 是兄弟选项：拼成卷面样式一行「A. x　B. y　…」；
        # 超长自动折行（>60 字符两选项一行，>120 一选项一行）。选项内只认 text 块，
        # 嵌 figure/table 照旧拒渲不静默（图选项归 figure 通路批次⑥）。
        if any(c.get('type') == 'option' for c in cells):
            pieces = []
            for c, cell in enumerate(cells):
                tag = '%s.row%d.cell%d' % (where, r + 1, c + 1)
                if cell.get('type') == 'text':
                    # 🔴 题干与选项同 row 是入库闸认的合法形（快录包实存）——text 当题干行，不拒
                    _guard_inline_gfm(cell.get('md'), tag)
                    for ln in (cell.get('md') or '').split('\n'):
                        if ln.strip():
                            out.append(ln.strip())
                    continue
                if cell.get('type') != 'option':
                    raise PackError('[%s] option 行里混入 %r 块 —— 只认 text（题干）与 option'
                                    % (tag, cell.get('type')))
                label = (cell.get('label') or '').strip()
                if not label:
                    raise PackError('[%s] option 缺 label' % tag)
                inner = []
                for b in (cell.get('blocks') or []):
                    if b.get('type') != 'text':
                        raise PackError('[%s] option 内嵌 %r 块 —— 图/表选项本版拒渲不静默'
                                        % (tag, b.get('type')))
                    inner.append(' '.join(ln.strip() for ln in (b.get('md') or '').split('\n')
                                          if ln.strip()))
                pieces.append('%s．%s' % (label, ' '.join(x for x in inner if x)))
            total = sum(len(p) for p in pieces)
            per_line = len(pieces) if total <= 60 else (2 if total <= 120 else 1)
            for i in range(0, len(pieces), per_line):
                out.append(' '.join(pieces[i:i + per_line]))
            continue
        for c, cell in enumerate(cells):
            t = cell.get('type')
            tag = '%s.row%d.cell%d' % (where, r + 1, c + 1)
            if t == 'text':
                _guard_inline_gfm(cell.get('md'), tag)
                for ln in (cell.get('md') or '').split('\n'):
                    if ln.strip():
                        out.append(ln.strip())
            elif t in ('figure', 'image'):
                out.append(figure_html(cell, tag, assets))
            elif t == 'table':
                out.append(table_html(cell, tag, assets))
            else:
                raise PackError('[%s] 未知块型 %r' % (tag, t))
    return out


# ══════════════════════════════════════════════════════════════════════
# 三、blocks → 渲染器槽位数据（🔴 适配规则全在这儿，独立可测）
# ══════════════════════════════════════════════════════════════════════
class Tex(object):
    """渲染器 `expr/oral` 槽位要的 `it['stem']` —— 只需一个 `.h` 属性。"""

    __slots__ = ('h',)

    def __init__(self, h):
        self.h = h

    def __repr__(self):
        return 'Tex(%r)' % self.h


def _plain_len(md):
    """选项的**视觉宽度估算**（定列数用）：剥 $ 定界与 LaTeX 命令壳，中文按 2 计。"""
    s = re.sub(r'\\[a-zA-Z]+', 'x', md or '')          # \frac \degree → 单字符占位
    s = re.sub(r'[${}^_\\]', '', s)
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)


def _nospace(s):
    return re.sub(r'\s+', '', s or '')


def split_eq_chain(tex):
    """把 `A=B=C` 这类**行内等号链**在顶层 `=` 处切开（花括号里的等号不切）。

    🔴 解析在库里有两种写法，都得吃（组卷侧实测导的是后一种）：
       ① 分行写：`＝$5-(-5)$` / `＝$10$`；
       ② 整条一个公式：`$(-3)+(-5)-(-2)=-3-5+2=-6$`。
    """
    parts, buf, depth, i, n = [], [], 0, 0, len(tex)
    while i < n:
        c = tex[i]
        if c == '\\' and i + 1 < n:                # \ne \leq \geq 里的字母不误伤
            buf.append(tex[i:i + 2])
            i += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth = max(0, depth - 1)
        if c == '=' and depth == 0:
            parts.append(''.join(buf).strip())
            buf = []
        else:
            buf.append(c)
        i += 1
    parts.append(''.join(buf).strip())
    return [p for p in parts if p]


def chain_lines(analysis, answer, where='?', assets=None):
    """解析 → ＝链。

    · 取 analysis 里**以「＝」（或半角 `=`）开头**的行，剥掉行首等号与 `$` 定界，按序成 lines；
    · 行首不是等号的第一个纯公式行：内部若带顶层 `=` 就当**行内等号链**拆开（见 split_eq_chain），
      否则整条记作 lead（word 槽位拿它当原式，expr 用题面当原式）；
    · 🔴 ＝行必须是纯公式（如 `＝$8+2$`）—— 「＝$4$元」这类中文混进等号行一律拒渲；
    · analysis 缺失 / 一条算式都没有 → 退到 answer 的首个公式，至少让答案卷有答案。
    返回 (lead, lines, 来源说明)。
    """
    lead, lines, src = None, [], '解析＝链'
    for ln in md_lines(analysis, where + '.解析', assets):
        if isinstance(ln, Html):
            # ＝链按定义只收算式行；解析里的图/表进不了链。不静默 —— 喊出来让人看见。
            print('  ⚠️ [%s.解析] 有一个 %s 块 —— ＝链只收算式行，该块不进答案卷'
                  % (where, ln.kind))
            continue
        if ln[0] in '＝=':
            rest = ln[1:].strip()
            t = pure_formula(rest, where + '.解析')
            if t is None:
                raise PackError('[%s.解析] ＝行不是纯公式，中文不许混进 LaTeX：%s'
                                % (where, ln[:50]))
            lines.append(t)
        elif lead is None and not lines:
            t = pure_formula(ln, where + '.解析')
            if t is None:
                continue                           # 说明性文字行，跳过（只取算式）
            parts = split_eq_chain(t)
            if len(parts) >= 2:
                lead, lines, src = parts[0], parts[1:], '解析行内等号链'
            else:
                lead = t
    if lines:
        return lead, lines, src
    for ln in md_lines(answer, where + '.答案', assets):
        t = first_formula(ln, where + '.答案')
        if t is not None:
            return lead, [t], '答案首式（解析无＝链）'
    return lead, [], '无'


def stem_for_answer(stem_ls, where='?'):
    """题面行 → **答案卷版**题面 HTML 行。

    🔴 省纸口径（renderers/math.py `word` 的原话、core.py 残页闸的病根）：
       答案卷不重复题面图 —— 一张线段图重印就多出 122pt，直接把答案卡挤出一张残页。
       图换成「（图见题目卷）」六个字，家长手里本来就有题目卷。
       表**保留**：表格常是题面数据本身，剥了答案就看不懂（且表比图矮得多）。
    """
    out = []
    for x in stem_ls:
        if isinstance(x, Html) and x.kind == 'figure':
            out.append(FIG_IN_Q)
        else:
            out.append(md_to_delim(x, where))
    return out


def adapt_item(item, slot, where='?', assets=None):
    """一道 paper_item → 渲染器槽位数据。slot 决定形状（renderers/math.py 契约）。"""
    q = item.get('question') or {}
    stem_blocks = q.get('blocks')
    ans_blocks = q.get('answer_blocks')
    ana_blocks = q.get('analysis_blocks')
    stem_ls = md_lines(stem_blocks, where + '.题面', assets)
    if not stem_ls:
        raise PackError('[%s] 题面块流为空' % where)

    if slot in ('expr', 'oral'):
        # 🔴 这两个槽位只吃**一条算式**（stem_ls[0] 进 Tex，别的行本来就用不上），
        #    题面里有图/表说明选错槽了 —— 拒渲，绝不静默把图丢掉出一份缺图的卷。
        bad = [x.kind for x in stem_ls if isinstance(x, Html)]
        if bad:
            raise PackError('[%s] %s 槽的题面里有 %s 块 —— 该槽只渲一条算式，图表题请走 '
                            'fill / word / choice 槽，拒渲不静默丢' % (where, slot, '/'.join(bad)))
        # 题面第一个 text 块的 md 当原式；＝链来自解析
        lead, lines, src = chain_lines(ana_blocks, ans_blocks, where, assets)
        if not lines:
            raise PackError('[%s] 既无解析＝链也无答案公式 —— 答案卷会没有答案，拒渲' % where)
        pure = pure_formula(stem_ls[0], where + '.题面')
        # 行内等号链的 lead 通常就是题面原式（渲染器会自己打头），一样才丢；
        # 不一样说明解析从别的形态起步 —— 补进链首，绝不静默丢一步。
        if lead and (pure is None or _nospace(lead) != _nospace(pure)):
            lines = [lead] + lines
        return {'stem': Tex(stem_tex(stem_ls[0], where + '.题面')),
                'lines': lines, '_src': src}

    if slot == 'word':
        lead, lines, src = chain_lines(ana_blocks, ans_blocks, where, assets)
        if lead:
            lines = [lead] + lines
        if not lines:
            raise PackError('[%s] 应用题解析无算式行、答案也无公式，拒渲' % where)
        # word 的答案卷本来就不重印题面（省纸口径），题面图天然不会重复出现
        ansline = '<br>'.join(md_to_delim(x, where + '.答案')
                              for x in md_lines(ans_blocks, where + '.答案', assets)) or '答：见解析。'
        return {'text': '<br>'.join(md_to_delim(x, where + '.题面') for x in stem_ls),
                'lines': lines, 'ansline': ansline, '_src': src}

    if slot == 'fill':
        raw = md_lines(ans_blocks, where + '.答案', assets)
        ans_html = ''
        if raw:
            t = pure_formula(raw[0], where + '.答案')
            # 纯公式 → 着色进公式内部（MathJax 不吃外层 CSS）；混排 → 走 ansv 类 + 内联色，
            # ansv 已在 core.ANSWER_ONLY_MARKS 里，泄答案闸照样能盯住。
            ans_html = ('\\(%s\\)' % ('\\color{%s}{%s}' % (renderers.get('math').ANSWER_COLOR, t))
                        if t is not None else
                        '<span class="ansv" style="color:%s">%s</span>'
                        % (renderers.get('math').ANSWER_COLOR,
                           md_to_delim(raw[0], where + '.答案')))
        # 🔴 fill 是**唯一在答案卷重印题面**的槽（renderers/math.py fill），
        #    所以只有它需要一份剥了图的题面：text_ans（省纸口径不破）。
        return {'text': '<br>'.join(md_to_delim(x, where + '.题面') for x in stem_ls),
                'text_ans': '<br>'.join(stem_for_answer(stem_ls, where + '.题面')),
                'ans': ans_html, '_src': '答案首行'}

    if slot == 'choice':
        # 选择题（2026-08-20 补实装；同日按用户卷面口径改列位制）：
        # 🔴 选项不做流式拼接 —— 每个选项独立占位，按最长选项宽度定列数（4/2/1 列），
        #    正常试卷的排法（参照备课帮展示效果采纳布局思路）。
        # 🔴 答案可空 —— 无答案态（如讲义题目版）出练习卷合法，答案卷印「（待补答案）」。
        stem_html, options = [], []
        if isinstance(stem_blocks, str):
            stem_blocks_d = json.loads(stem_blocks)
        else:
            stem_blocks_d = stem_blocks
        for r, row in enumerate(stem_blocks_d.get('rows') or []):
            cells = row.get('cells') or []
            for c, cell in enumerate(cells):
                tag = '%s.题面.row%d.cell%d' % (where, r + 1, c + 1)
                t = cell.get('type')
                if t == 'text':
                    # 题干与选项同 row 的合法变形：text 归题干
                    _guard_inline_gfm(cell.get('md'), tag)
                    for ln in (cell.get('md') or '').split('\n'):
                        if ln.strip():
                            stem_html.append(md_to_delim(ln.strip(), where + '.题面'))
                elif t == 'option':
                    label = (cell.get('label') or '').strip()
                    for b in (cell.get('blocks') or []):
                        if b.get('type') != 'text':
                            raise PackError('[%s] 选项 %s 里嵌了 %r 块 —— 🔴 图/表选项本版拒渲不静默'
                                            '（选项网格是等宽表格，塞图会撑塌列位）'
                                            % (tag, label or '?', b.get('type')))
                    inner = ' '.join(
                        ' '.join(ln.strip() for ln in (b.get('md') or '').split('\n') if ln.strip())
                        for b in (cell.get('blocks') or []))
                    options.append({'label': label,
                                    'html': md_to_delim(inner, '%s.选项%s' % (where, label)),
                                    '_len': _plain_len(inner)})
                elif t in ('figure', 'image'):
                    # 🔴 配图题干（2026-08-20 实装）：此前这一支被静默跳过，图整个丢了
                    stem_html.append(str(figure_html(cell, tag, assets)))
                elif t == 'table':
                    stem_html.append(str(table_html(cell, tag, assets)))
                else:
                    raise PackError('[%s] 未知块型 %r' % (tag, t))
        if not options:
            raise PackError('[%s] choice 槽但题面无 option 块 —— 选择题包坏形' % where)
        longest = max(o['_len'] for o in options)
        opt_cols = 4 if longest <= 10 else (2 if longest <= 26 else 1)
        for o in options:
            o.pop('_len', None)
        raw = md_lines(ans_blocks, where + '.答案')
        ansline = '；'.join(md_to_delim(x, where + '.答案') for x in raw) if raw else ''
        return {'text': '<br>'.join(stem_html), 'options': options, 'opt_cols': opt_cols,
                'ans': ansline, '_src': '答案' if raw else '无答案态'}

    raise PackError('[%s] 槽位 %r 本版未实装（已实装：expr / oral / word / fill / choice）' % (where, slot))


# ══════════════════════════════════════════════════════════════════════
# 四、多 paper 薄适配层（每张卷自己的节配置 + 自己的标题）
# ══════════════════════════════════════════════════════════════════════
_H1 = re.compile(r'<h1\b[^>]*>.*?</h1>', re.S)


class PerPaperLayout(object):
    """包住骨架，逐卷换 `ctx['sections']` 与标题，其余原样委托。

    为什么要这层：punchkit 骨架的 `ctx['sections']` 是**整册一套**，标题也是
    「册名（第N天）」拼出来的；而 render-pack 里每张 paper 各带自己的
    `layout.sections` 与 `title`（如「第一天·有理数的加减」）。
    做法 = 委托 `render_card` 后把首个 `<h1>` 换成 paper.title —— 不改骨架一行代码
    （骨架是共用件，`layouts/` 里加私货正是 punchkit 要消灭的东西）。
    """

    def __init__(self, base, per_paper):
        self.base = base
        self.per = per_paper                       # [{'sections':…, 'title':…}, …]
        self.EXTRA_LEAK_MARKS = getattr(base, 'EXTRA_LEAK_MARKS', ())

    def css(self, *a, **kw):
        return self.base.css(*a, **kw)

    def guard(self, html_, days, ctx):
        g = getattr(self.base, 'guard', None)
        if g:
            g(html_, days, ctx)

    def render_card(self, idx, data, ans, ctx):
        p = self.per[idx]
        c = dict(ctx)
        c['sections'] = p['sections']
        # 🔴 逐卷把整个 layout_json 递给骨架（2026-08-20 为 `exam_paper` 加）：
        #    试卷骨架要的「满分/考试时长/副标题/姓名行/评分表/装订线」都是**每张卷自己的**，
        #    而 ctx 是整册一套。骨架不认这个键的（打卡册那几套）原样不受影响。
        c['paper_layout'] = p.get('layout') or {}
        # 骨架的中文天序表只有「一…十」十个字，第 11 天起会 IndexError；
        # 反正标题整条要被换掉，这里给它一个安全下标即可。
        cn = getattr(self.base, 'CN', '')
        i2 = idx % len(cn) if cn and idx >= len(cn) else idx
        card = self.base.render_card(i2, data, ans, c)
        title = p['title'] + ('　参考答案' if ans else '')
        new, n = _H1.subn(lambda m: '<h1>%s</h1>' % title, card, count=1)
        if not n:
            print('  ⚠️ 骨架 %s 的卡片里没有 <h1>，paper.title 未能落到卷面'
                  % getattr(self.base, 'SPEC', {}).get('key', '?'))
        return new


# ══════════════════════════════════════════════════════════════════════
# 五、Chrome 出 PDF：补上 core 没管的第四坑
# ══════════════════════════════════════════════════════════════════════
_orig_to_pdf = core.to_pdf


def _to_pdf_safe(html_path, pdf_path, budget_ms=20000):
    """core.to_pdf 的三坑照抄，另加两条（渲染出件 SKILL.md §4）：
       🔴 撞正开着的 Chrome 会**静默不写文件** ⇒ 必须 `--user-data-dir=<临时 profile>`；
       🔴 本机有代理 ⇒ `--no-proxy-server`。出完立刻验文件真的在。"""
    import subprocess
    # 🔴 相对路径必先绝对化（2026-08-19 主位实伤）：file:///产物/… 是废 URL，
    #    Chrome 加载空页、退出码还是 0——"看着成功一个字节没写"。
    html_path = os.path.abspath(str(html_path))
    pdf_path = os.path.abspath(str(pdf_path))
    with tempfile.TemporaryDirectory(prefix='chrome_pdf_') as prof:
        subprocess.run([core.CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--no-proxy-server', '--user-data-dir=' + prof,
                        '--no-pdf-header-footer',
                        '--virtual-time-budget=%d' % budget_ms,
                        '--run-all-compositor-stages-before-draw',
                        '--print-to-pdf=' + pdf_path,
                        'file:///' + html_path.replace('\\', '/')],
                       check=True, capture_output=True, timeout=300)
    if not os.path.exists(pdf_path):
        raise PackError('🔴 Chrome 没写出 PDF：%s' % pdf_path)


core.to_pdf = _to_pdf_safe


# ══════════════════════════════════════════════════════════════════════
# 六、pack → days（分桶 + 排序 + 适配）
# ══════════════════════════════════════════════════════════════════════
def load_pack(path):
    p = Path(path)
    if not p.exists():
        raise PackError('render-pack 不存在：%s' % p)
    try:
        pack = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        raise PackError('render-pack 不是合法 JSON：%s' % e)
    got = pack.get('contract')
    if got != CONTRACT:
        raise PackError('契约不符：contract=%r，本工具只吃 %r' % (got, CONTRACT))
    if not pack.get('papers'):
        raise PackError('papers 为空，没东西可渲')
    return pack


# 🔴 LAYOUT 注册点：题号由骨架自己打全卷连号的版式，不吃渲染器 ①~⑩ 圈码的 10 题上限
#    （`exam_paper` 的 `_renumber` 把节内号整个换掉——真卷选择题常有 11~12 题）
_SELF_NUMBERED_LAYOUTS = {'exam_paper'}


def build_days(papers, assets=None):
    """→ (days, per_paper, layout_key, body_pt, watermark)"""
    days, per = [], []
    keys, pts, wms = set(), [], []
    for pi, paper in enumerate(papers):
        pw = 'paper[%s/%s]' % (paper.get('ord'), paper.get('title', '?'))
        lay = paper.get('layout') or {}
        secs = lay.get('sections') or []
        if not secs:
            raise PackError('[%s] layout.sections 为空' % pw)
        keys.add(lay.get('layout') or layouts.DEFAULT)
        if lay.get('body_pt'):
            pts.append(float(lay['body_pt']))
        if 'watermark' in lay:
            wms.append(lay['watermark'])
        names = [s['name'] for s in secs]
        if len(set(names)) != len(names):
            raise PackError('[%s] layout.sections 里节名重复：%s' % (pw, names))
        bucket = {n: [] for n in names}
        for it in paper.get('items') or []:
            sec = it.get('section')
            if sec is None:
                if len(names) == 1:
                    sec = names[0]
                else:
                    raise PackError('[%s] 第 %s 题没有 section，而本卷有 %d 节，无法归位'
                                    % (pw, it.get('ord'), len(names)))
            if sec not in bucket:
                raise PackError('[%s] 第 %s 题的 section=%r 不在 layout.sections %s 里，拒渲'
                                % (pw, it.get('ord'), sec, names))
            bucket[sec].append(it)
        day = []
        for s in secs:
            grp = sorted(bucket[s['name']], key=lambda x: (x.get('ord') is None, x.get('ord')))
            if not grp:
                print('  ⚠️ [%s] 节「%s」一道题都没有，将渲成空节' % (pw, s['name']))
            if len(grp) > 10 and (lay.get('layout') or layouts.DEFAULT) \
                    not in _SELF_NUMBERED_LAYOUTS:
                raise PackError('[%s] 节「%s」有 %d 题 —— 渲染器答案卷圈码只有 ①~⑩，拒渲'
                                % (pw, s['name'], len(grp)))
            day.append([adapt_item(it, s['slot'],
                                   '%s.%s#%s' % (pw, s['name'], it.get('ord')), assets)
                        for it in grp])
        days.append(day)
        per.append({'sections': secs, 'layout': lay,
                    'title': md_to_delim(paper.get('title') or '第%s天' % (pi + 1), pw)})
    if len(keys) > 1:
        raise PackError('一册里出现多个骨架 %s —— 一册一骨架，拒渲' % sorted(keys))
    if len(set(pts)) > 1:
        print('  ⚠️ 各卷 body_pt 不一致 %s，取第一个 %.2f' % (pts, pts[0]))
    return (days, per, keys.pop(), pts[0] if pts else None,
            wms[0] if wms else '__skip__')


# ══════════════════════════════════════════════════════════════════════
# 七、落账
# ══════════════════════════════════════════════════════════════════════
def log_skill(db, action, digest, result, detail, t0, enabled=True):
    """skill='渲染出件' 落 skill_log（D-15）。🔴 库路径参数化，--no-log 可整条关掉。"""
    if not enabled:
        print('  · --no-log：本次不落账')
        return
    import sqlite3
    p = Path(db)
    if not p.exists():
        print('  ⚠️ 库不存在，跳过落账：%s' % p)
        return
    conn = sqlite3.connect(str(p))
    try:
        conn.execute('INSERT INTO skill_log(skill,action,args_digest,result,detail,'
                     'duration_ms,created_at) VALUES (?,?,?,?,?,?,?)',
                     ('渲染出件', action, str(digest)[:200], result, str(detail)[:500],
                      int((time.time() - t0) * 1000),
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        print('  · skill_log 已落账：渲染出件/%s %s' % (action, result))
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
# 八、主流程
# ══════════════════════════════════════════════════════════════════════
_BAD = re.compile(r'[\\/:*?"<>|]')


def safe_stem(s):
    return _BAD.sub('_', (s or 'paper').strip()) or 'paper'


def main(argv=None):
    ap = argparse.ArgumentParser(description='render-pack/v1 → 题目卷+答案卷双 PDF')
    ap.add_argument('pack', help='render-pack.json 路径')
    ap.add_argument('--out-dir', required=True, help='出件目录（产物/… 由调用方给）')
    ap.add_argument('--stem', help='文件名主干（缺省=artifact.name）')
    ap.add_argument('--sample-ord', type=int, help='只渲这一天/这一卷（按 paper.ord）')
    ap.add_argument('--png', action='store_true', help='额外出目检 PNG')
    ap.add_argument('--db', default=str(DEFAULT_DB),
                    help='skill_log 落账库 + figure 的 asset.rel_path 只读查询库'
                         '（缺省 <v2根>/知识库/kb.db）')
    ap.add_argument('--asset-root', help='asset.rel_path 的解析根（缺省 = v2 根；沙盘/副本资产用）')
    ap.add_argument('--no-log', action='store_true', help='不落 skill_log（沙盘自测用）')
    a = ap.parse_args(argv)
    t0 = time.time()
    digest = '%s ord=%s' % (Path(a.pack).name, a.sample_ord)

    try:
        pack = load_pack(a.pack)
        art = pack.get('artifact') or {}
        papers = pack['papers']
        if a.sample_ord is not None:
            papers = [p for p in papers if p.get('ord') == a.sample_ord]
            if not papers:
                raise PackError('--sample-ord %d 没有对应的 paper' % a.sample_ord)
        # 🔴 asset 解析器（figure 用）：pack 自带 assets 优先，否则只读查 --db；
        #    懒连接 —— 一张图都没有的册子根本不会碰库（沙盘/worktree 里跑得动的关键）。
        assets = AssetResolver(pack, db=a.db, root=a.asset_root)
        days, per, key, body_pt, wm = build_days(papers, assets)
        assets.close()

        L = layouts.get(key)
        R = renderers.get(pack.get('subject') or 'math')
        ctx = {'renderer': R, 'sections': per[0]['sections'],
               'book_title': art.get('name', ''), 'days_total': len(days)}
        if body_pt:
            ctx['body_pt'] = body_pt
        if wm != '__skip__':
            ctx['watermark'] = wm

        stem = a.stem or safe_stem(art.get('name') or art.get('id'))
        out_dir = Path(a.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        # 打卡天=一天一页 ⇒ 题目卷页数必须等于卷数；混排册不断言
        kinds = {p.get('kind') for p in papers}
        expect = len(days) if kinds == {'打卡天'} else None

        print('▶ %s ×%d 卷｜骨架 %s｜渲染器 %s｜正文 %s pt｜断言 %s'
              % (art.get('name', '(未命名)'), len(days), key, R.SUBJECT,
                 body_pt or '默认', expect if expect else '不断言'))
        rep = core.render_book(out_dir=str(out_dir), stem=stem,
                               title=art.get('name', stem),
                               layout=PerPaperLayout(L, per), days=days, ctx=ctx,
                               expect_pages=expect, png=a.png, pt=body_pt)

        # 🔴 出件自检钩子：文件真的在 + 页数 + PNG 路径（数据对不等于渲染对）
        print('── 自检 ──')
        for k, cn in (('question', '题目卷'), ('answer', '答案卷')):
            p = Path(rep[k]['path'])
            if not p.exists():
                raise PackError('%s 没落盘：%s' % (cn, p))
            print('  🟢 %s %d 页  %.0f KB  %s' % (cn, rep[k]['pages'],
                                                 p.stat().st_size / 1024, p))
            for g in rep[k]['png']:
                print('     PNG %s' % g)
        if a.png and not (rep['question']['png'] or rep['answer']['png']):
            print('  ⚠️ 没出 PNG（PyMuPDF 未装？）')
        if rep['answer']['pages'] <= len(days):
            # 🔴 core 的残页闸按**可提取字数**判定，而 MathJax 渲出的公式在 PDF 里
            #    提不出任何文字 ⇒ 纯计算册的答案页常被它误报成"残页"。页数没超卷数
            #    就说明没有夹页，以此为准；真有夹页时页数一定会超。
            print('  · 残页复核：答案卷 %d 页 ≤ %d 卷，无夹页（core 残页闸按字数判，'
                  '公式提不出文字，纯计算册会误报，以页数为准）'
                  % (rep['answer']['pages'], len(days)))

        log_skill(a.db, '出件', digest, '成功',
                  '%s %d卷 题%d页/答%d页 → %s' % (art.get('name', ''), len(days),
                                                rep['question']['pages'],
                                                rep['answer']['pages'], out_dir),
                  t0, enabled=not a.no_log)
        return 0
    except (PackError, AssertionError, KeyError) as e:
        print('🔴 拒渲：%s' % e, file=sys.stderr)
        log_skill(a.db, '出件', digest, '失败', str(e), t0, enabled=not a.no_log)
        return 1


if __name__ == '__main__':
    sys.exit(main())
