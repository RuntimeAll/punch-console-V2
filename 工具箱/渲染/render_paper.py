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
           [--db <kb.db>] [--no-log]

出件
----
    <out-dir>/<stem>.pdf          题目卷
    <out-dir>/<stem>（答案）.pdf   答案卷
    <out-dir>/_源/                 中间 HTML 与目检 PNG（core 落这里）

🔴 拒渲清单（一切靠闸不靠注释，违例一律非零退出，绝不静默降级）
  · contract ≠ render-pack/v1
  · blocks 里 `$` 数目为奇数 / 出现 `$$` 显示公式
  · 题面/答案/解析里出现 figure（图渲染待批次⑥）、option、table 块
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
    """整段 md → HTML 串，`$…$` 换成 `\\(…\\)`。奇数个 `$` 拒渲。"""
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
    """整段就是**一个** `$…$` 时返回里面的裸 tex；否则 None。"""
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
    """取该行第一个 `$…$` 的裸 tex；整行无公式返回 None。"""
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
# 二、blocks_json v2 → 文本行
# ══════════════════════════════════════════════════════════════════════
def md_lines(blocks, where='?'):
    """blocks_json v2 → md 行列表。🔴 非 text 块一律拒渲（不静默丢）。"""
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
        for c, cell in enumerate(row.get('cells') or []):
            t = cell.get('type')
            tag = '%s.row%d.cell%d' % (where, r + 1, c + 1)
            if t == 'text':
                for ln in (cell.get('md') or '').split('\n'):
                    if ln.strip():
                        out.append(ln.strip())
            elif t in ('figure', 'image'):
                raise PackError('[%s] 出现 figure 块 —— 🔴 figure 渲染待批次⑥，'
                                '本版拒渲不静默丢' % tag)
            elif t == 'option':
                raise PackError('[%s] 出现 option 块 —— 选择题槽位本版未实装，拒渲' % tag)
            elif t == 'table':
                raise PackError('[%s] 出现 table 块 —— 表格渲染本版未实装，拒渲' % tag)
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


def chain_lines(analysis, answer, where='?'):
    """解析 → ＝链。

    · 取 analysis 里**以「＝」（或半角 `=`）开头**的行，剥掉行首等号与 `$` 定界，按序成 lines；
    · 行首不是等号的第一个纯公式行：内部若带顶层 `=` 就当**行内等号链**拆开（见 split_eq_chain），
      否则整条记作 lead（word 槽位拿它当原式，expr 用题面当原式）；
    · 🔴 ＝行必须是纯公式（如 `＝$8+2$`）—— 「＝$4$元」这类中文混进等号行一律拒渲；
    · analysis 缺失 / 一条算式都没有 → 退到 answer 的首个公式，至少让答案卷有答案。
    返回 (lead, lines, 来源说明)。
    """
    lead, lines, src = None, [], '解析＝链'
    for ln in md_lines(analysis, where + '.解析'):
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
    for ln in md_lines(answer, where + '.答案'):
        t = first_formula(ln, where + '.答案')
        if t is not None:
            return lead, [t], '答案首式（解析无＝链）'
    return lead, [], '无'


def adapt_item(item, slot, where='?'):
    """一道 paper_item → 渲染器槽位数据。slot 决定形状（renderers/math.py 契约）。"""
    q = item.get('question') or {}
    stem_blocks = q.get('blocks')
    ans_blocks = q.get('answer_blocks')
    ana_blocks = q.get('analysis_blocks')
    stem_ls = md_lines(stem_blocks, where + '.题面')
    if not stem_ls:
        raise PackError('[%s] 题面块流为空' % where)

    if slot in ('expr', 'oral'):
        # 题面第一个 text 块的 md 当原式；＝链来自解析
        lead, lines, src = chain_lines(ana_blocks, ans_blocks, where)
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
        lead, lines, src = chain_lines(ana_blocks, ans_blocks, where)
        if lead:
            lines = [lead] + lines
        if not lines:
            raise PackError('[%s] 应用题解析无算式行、答案也无公式，拒渲' % where)
        ansline = '<br>'.join(md_to_delim(x, where + '.答案')
                              for x in md_lines(ans_blocks, where + '.答案')) or '答：见解析。'
        return {'text': '<br>'.join(md_to_delim(x, where + '.题面') for x in stem_ls),
                'lines': lines, 'ansline': ansline, '_src': src}

    if slot == 'fill':
        raw = md_lines(ans_blocks, where + '.答案')
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
        return {'text': '<br>'.join(md_to_delim(x, where + '.题面') for x in stem_ls),
                'ans': ans_html, '_src': '答案首行'}

    raise PackError('[%s] 槽位 %r 本版未实装（已实装：expr / oral / word / fill）' % (where, slot))


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
    with tempfile.TemporaryDirectory(prefix='chrome_pdf_') as prof:
        subprocess.run([core.CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--no-proxy-server', '--user-data-dir=' + prof,
                        '--no-pdf-header-footer',
                        '--virtual-time-budget=%d' % budget_ms,
                        '--run-all-compositor-stages-before-draw',
                        '--print-to-pdf=' + pdf_path,
                        'file:///' + str(html_path).replace('\\', '/')],
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


def build_days(papers):
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
            if len(grp) > 10:
                raise PackError('[%s] 节「%s」有 %d 题 —— 渲染器答案卷圈码只有 ①~⑩，拒渲'
                                % (pw, s['name'], len(grp)))
            day.append([adapt_item(it, s['slot'],
                                   '%s.%s#%s' % (pw, s['name'], it.get('ord')))
                        for it in grp])
        days.append(day)
        per.append({'sections': secs,
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
    ap.add_argument('--db', default=str(DEFAULT_DB), help='skill_log 库（缺省 <v2根>/知识库/kb.db）')
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
        days, per, key, body_pt, wm = build_days(papers)

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
