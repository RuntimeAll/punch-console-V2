# -*- coding: utf-8 -*-
"""
③ 试切一个单元：题目卡（块流）+ 归属树（预挂考点名）+ 例题↔练习配对
   + 题干元信息抽离（栏目前缀/小问号剥离带账）+ 守恒闸。
🔴 不入库、不调 LLM、不 OCR。产物只落本卡目录。
用法：python 3_切单元.py [单元关键字]   默认 = 三角形·特性篇
"""
import sys, os, re, json, hashlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')

ROOT = J.ROOT
OUT = os.path.join(ROOT, '产物')
IMGDIR = os.path.join(OUT, 'images')
SRC = os.path.join(ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
UNIT_KEY = sys.argv[1] if len(sys.argv) > 1 else '三角形·特性篇'

# ============================================================
# 元信息抽离的正则（🔴 每条都带守卫，见 模板规则.md 判据表）
# ============================================================
# 栏目前缀：【典型例题N】/【对应练习N】—— 整段最前面，N 可空
RE_COL_PREFIX = re.compile(r'^[\s　]*(【(典型例题|典例分析|典例精讲|例题|对应练习|变式训练|变式|巩固练习|课后练习)[\s　]*(\d*)】)')
# 例题/练习后紧跟的「纯标签」（其一。/问题二：边长的最值。）——记为标题，不是题面
RE_PURE_LABEL = re.compile(r'^(其[一二三四五六七八九十]+|问题[一二三四五六七八九十\d]+)[：:．.。]?(.{0,20}?)[。．]?$')
# 小问号四形态
RE_SUB = [
    ('全角N．', re.compile(r'^[\s　]*(\d{1,2}．)')),                 # 全角句点：本书永非小数点（老区§12）
    ('半角N.',  re.compile(r'^[\s　]*(\d{1,2}\.(?!\d))')),           # 🔴 (?!\d) 防 1.5 被剥成 5（老区§15.8）
    ('（N）',   re.compile(r'^[\s　]*([（(]\d{1,2}[）)])')),
    ('圈号',    re.compile(r'^[\s　]*([①-⑳])')),
]
# 分值 / 来源标记（本书预期为 0，仍设闸，切别的书时自动生效）
RE_SCORE = re.compile(r'[（(]\s*\d+(?:\.\d+)?\s*分\s*[）)]')
RE_SOURCE = re.compile(r'菁优网|著作权属|【来源】|（\d{4}[·•].{2,12}）')
# 选项 / 空槽 / 判断
# 🔴 选项字母必须行首或前接空白 —— 否则「用字母A、B、C分别表示」会被判成选择题
#    （本卡 2026-08-18 实测 q001/q002 就是这么误判的）
RE_OPTION = re.compile(r'(?:^|(?<=[\s　 ]))([A-DＡ-Ｄ])[．.、]', re.M)
RE_BLANK_SLOT = re.compile(r'[（(][\s　\xa0]*[）)]|[＿_]{2,}')

WS = set(' \t\r\n　\xa0​')

def visible(s):
    return Counter(c for c in (s or '') if c not in WS)

def blocks_text(blocks):
    """块流 -> 可读全文（figure 不出字，table 出线性化文本）"""
    out = []
    for b in J.C.iter_blocks(blocks):
        if b['type'] == 'text':
            out.append(b['text'])
        elif b['type'] == 'table':
            out.append(b.get('flat_text') or '')
    return '\n'.join(out)

def blocks_visible(blocks):
    return visible(blocks_text(blocks))

def count_kind(blocks, t):
    return sum(1 for b in J.C.iter_blocks(blocks) if b['type'] == t)

# ============================================================
# 1. 定位单元正文
# ============================================================
stream, base = J.build_stream(SRC, IMGDIR)
marks = [(nd['i'], *J.classify(nd['head'])) for nd in stream]
mark_at = {i: (k, meta) for i, k, meta in marks if k}

unit_heads = [i for i, k, m in marks if k == 'unit' and UNIT_KEY in (m.get('title') or '')]
# 正文单元头 = 其后 30 段内出现 explain 的那个（目录里的单元头后面只有考点清单）
body_head = None
for h in unit_heads:
    for j in range(h + 1, min(h + 40, len(stream))):
        k = mark_at.get(j, (None,))[0]
        if k == 'explain':
            body_head = h
            break
        if k == 'unit':
            break
    if body_head is not None:
        break
assert body_head is not None, '找不到 %s 的正文单元头' % UNIT_KEY
nxt_units = [i for i, k, m in marks if k == 'unit' and i > body_head]
unit_end = nxt_units[0] if nxt_units else len(stream)
unit_meta = mark_at[body_head][1]
print('单元正文段区间 [%d, %d)  %s %s' % (body_head, unit_end, unit_meta['unit'], unit_meta['title']))

# 单元级基准（守恒闸的"原件真值"）
unit_nodes = stream[body_head:unit_end]
BASE = {
    '段落节点': len(unit_nodes),
    '图槽': sum(J.count_figs(nd) for nd in unit_nodes),
    '表格': sum(1 for nd in unit_nodes if nd['kind'] == 'tbl'),
    '公式(OMML)': sum(1 for nd in unit_nodes for b in J.C.iter_blocks(nd['blocks'])
                      if b['type'] == 'text' and any(s.get('k') == 'math' for s in b.get('spans', []))),
}
BASE_CHARS = Counter()
for nd in unit_nodes:
    BASE_CHARS += blocks_visible(nd['blocks'])
print('单元基准：', BASE, ' 可见字符数', sum(BASE_CHARS.values()))

# ============================================================
# 2. 切段：单元 -> 考点 -> 栏目段（方法点拨/典例/练习）
# ============================================================
SEG_KINDS = ('unit', 'part', 'kp', 'explain', 'example', 'practice')
seg_starts = [i for i in range(body_head, unit_end) if mark_at.get(i, (None,))[0] in SEG_KINDS]
segs = []
for n, s in enumerate(seg_starts):
    e = seg_starts[n + 1] if n + 1 < len(seg_starts) else unit_end
    k, meta = mark_at[s]
    segs.append({'start': s, 'end': e, 'kind': k, 'meta': meta,
                 'nodes': stream[s:e]})

# 剪枝：空考点节（无 explain/example/practice 跟随）= 单元开头的考点小目录
kept, i = [], 0
dropped_toc = []
while i < len(segs):
    sg = segs[i]
    if sg['kind'] == 'kp':
        j = i + 1
        has_body = False
        while j < len(segs) and segs[j]['kind'] not in ('kp', 'unit', 'part'):
            has_body = True
            j += 1
        if not has_body:
            dropped_toc.append('【考点%s】%s' % (sg['meta'].get('no') or '',
                                                sg['meta'].get('title') or ''))
            i += 1
            continue
    kept.append(sg)
    i += 1
segs = kept
print('段数 %d（剪掉考点小目录 %d 行）' % (len(segs), len(dropped_toc)))

# ============================================================
# 3. 元信息抽离（带账）
# ============================================================
def extract_meta(seg, strip_sub=True):
    """
    从栏目段抽离元信息，返回 (题面块流, 账本)。
    🔴 账本口径：每剥一处，把**被剥掉的原文串**原样记下，
       使 multiset(题面) + Σ multiset(剥离原文) == multiset(原文)。
    strip_sub=False 用于【方法点拨】：讲解块里的 "1. 2. 3." 是**行文层级**不是小问号，
    剥了会让导出还原件丢编号（本卡 2026-08-18 目检实测到的还原缺陷）。
    """
    ledger = []          # [{'类':.., '原文':.., 'para':.., '值':..}]
    body = []
    first = True
    for nd in seg['nodes']:
        for b in nd['blocks']:
            if b['type'] != 'text':
                body.append(dict(b))
                continue
            t = b['text']
            # --- ① 栏目前缀（只在本段第一个文本块）---
            if first:
                m = RE_COL_PREFIX.match(t)
                if m:
                    ledger.append({'类': '栏目前缀', '原文': m.group(1), 'para': nd['i'],
                                   '值': {'栏目': m.group(2), '序号': m.group(3)}})
                    t = t[m.end():]
                else:
                    m2 = J.RE_EXPLAIN.match(t)
                    if m2:
                        raw = t[:t.index('】') + 1]
                        ledger.append({'类': '栏目前缀', '原文': raw, 'para': nd['i'],
                                       '值': {'栏目': m2.group(1), '序号': ''}})
                        t = t[len(raw):]
                first = False
            # --- ② 分值（本书预期 0）---
            for mm in RE_SCORE.finditer(t):
                ledger.append({'类': '分值', '原文': mm.group(0), 'para': nd['i'], '值': mm.group(0)})
            t = RE_SCORE.sub('', t)
            # --- ③ 来源标记（本书预期 0）---
            for mm in RE_SOURCE.finditer(t):
                ledger.append({'类': '来源', '原文': mm.group(0), 'para': nd['i'], '值': mm.group(0)})
            t = RE_SOURCE.sub('', t)
            # --- ④ 小问号（逐行，行首才认）---
            lines, out_lines = t.split('\n'), []
            for ln in lines:
                for name, rx in (RE_SUB if strip_sub else []):
                    mm = rx.match(ln)
                    if mm:
                        ledger.append({'类': '小问号', '原文': mm.group(1), 'para': nd['i'],
                                       '值': {'形态': name, '号': mm.group(1)}})
                        ln = ln[:mm.start(1)] + ln[mm.end(1):]
                        break
                out_lines.append(ln)
            t = '\n'.join(out_lines)
            nb = dict(b)
            nb['text'] = t
            if t.strip():
                body.append(nb)
            elif b['text'].strip():
                # 整块被剥空（如整段只有一个 "（1）"）：留空壳记账，不静默丢
                nb['text'] = ''
                nb['emptied'] = True
                body.append(nb)
    return body, ledger

def guess_qtype(text, nfig):
    """题型判定（老区 README §3 口径 + 本卡选项守卫，确定性，优先级从上到下）"""
    labs = [m.group(1) for m in RE_OPTION.finditer(text)]
    if len(set(labs)) >= 2 and labs[:2] == sorted(labs[:2]):
        return '选择'
    if '判断' in text or ('对' in text and '错' in text and ('√' in text or '×' in text)):
        return '判断'
    if RE_BLANK_SLOT.search(text):
        return '填空'
    return '解答'

# ============================================================
# 4. 建树 + 配对 + 题卡
# ============================================================
tree = {'书': '四下数学同步典例考点讲义（人教版）',
        '单元': unit_meta['unit'] + ' ' + unit_meta['title'],
        '考点': []}
cards = []
cur_kp = None
cur_part = None
last_example_qid = None
qseq = 0
low_conf = []

for sg in segs:
    k = sg['kind']
    if k == 'unit':
        continue
    if k == 'part':
        cur_part = '【第%s部分】%s' % (sg['meta']['no'], sg['meta']['title'])
        continue
    if k == 'kp':
        cur_kp = {'序': sg['meta']['no'], '考点名': sg['meta']['title'],
                  '部分': cur_part, 'para': sg['start'],
                  '方法点拨': None, '题': []}
        tree['考点'].append(cur_kp)
        last_example_qid = None
        continue
    if cur_kp is None:
        low_conf.append({'para': sg['start'], '因': '栏目段出现在任何考点头之前，无处归属'})
        continue
    if k == 'explain':
        body, ledger = extract_meta(sg, strip_sub=False)
        cur_kp['方法点拨'] = {'块流': body, '剥离账': ledger, '标签': sg['meta']['label']}
        continue

    # ---- 题卡 ----
    qseq += 1
    body, ledger = extract_meta(sg)
    col = sg['meta']['label']
    colno = sg['meta']['no']
    qid = 'u-%s-k%s-%s%s' % (unit_meta['title'], sg['meta'].get('no') or '', k, qseq)
    qid = 'q%03d' % qseq

    # 标题（纯标签）判定：剥进 meta 并记账，题面不留「其一。」
    title = None
    conf = []
    if body and body[0]['type'] == 'text':
        head_line = body[0]['text'].split('\n')[0]
        hl = head_line.strip()
        if hl and RE_PURE_LABEL.match(hl) and len(hl) <= 22:
            title = hl
            ledger.append({'类': '栏目标题', '原文': head_line,
                           'para': body[0].get('pidx'), '值': title})
            rest = body[0]['text'].split('\n')[1:]
            body[0] = dict(body[0])
            body[0]['text'] = '\n'.join(rest)
            if not body[0]['text'].strip():
                body[0]['emptied'] = True
            conf.append({'项': '首行判为标题非题面（已剥进 meta）', '值': title, '置信': '中'})

    text = blocks_text(body)
    nfig = count_kind(body, 'figure')
    ntbl = count_kind(body, 'table')
    qtype = guess_qtype(text, nfig)

    # 配对
    pair = None
    if k == 'example':
        last_example_qid = qid
    else:
        if last_example_qid:
            pair = last_example_qid
        else:
            conf.append({'项': '练习无上文典例可配', '值': None, '置信': '低'})

    # 小问
    subs = [l['值']['号'] for l in ledger if l['类'] == '小问号']

    # 题面为空（只有图）——低置信
    if not text.strip():
        conf.append({'项': '题面无文字（纯图题）', '值': None, '置信': '低'})

    card = {
        'qid': qid,
        '归属': {'书': tree['书'], '单元': tree['单元'], '部分': cur_part,
                 '考点序': cur_kp['序'], '考点名': cur_kp['考点名']},
        '栏目': col, '栏目序号': colno,
        '配对典例': pair,
        '标题': title,
        '题型': qtype,
        '块流': body,
        '小问号': subs,
        '剥离账': ledger,
        '图数': nfig, '表数': ntbl,
        'para区间': [sg['start'], sg['end']],
        '低置信': conf,
    }
    cards.append(card)
    cur_kp['题'].append({'qid': qid, '栏目': col, '栏目序号': colno,
                         '配对典例': pair, '题型': qtype, '图数': nfig})
    if conf:
        low_conf.append({'qid': qid, '项': conf})

# ============================================================
# 5. 守恒闸
# ============================================================
gates = []

def gate(name, ok, detail):
    gates.append({'闸': name, '过': bool(ok), '详情': detail})
    print(('  ✅ ' if ok else '  ❌ ') + name + ' :: ' + detail)

print('\n== 守恒闸 ==')
# 5.1 图守恒
got_fig = sum(c['图数'] for c in cards)
got_fig += sum(count_kind(kp['方法点拨']['块流'], 'figure') for kp in tree['考点'] if kp['方法点拨'])
gate('图守恒', got_fig == BASE['图槽'],
     '原件 %d 槽 / 切出 %d（题 %d + 点拨 %d）' %
     (BASE['图槽'], got_fig, sum(c['图数'] for c in cards), got_fig - sum(c['图数'] for c in cards)))

# 5.2 表守恒
got_tbl = sum(c['表数'] for c in cards)
got_tbl += sum(count_kind(kp['方法点拨']['块流'], 'table') for kp in tree['考点'] if kp['方法点拨'])
gate('表守恒', got_tbl == BASE['表格'], '原件 %d / 切出 %d' % (BASE['表格'], got_tbl))

# 5.3 可见字符多重集守恒（题面 + 剥离账 + 点拨 + 考点/单元标题行）
got_chars = Counter()
for c in cards:
    got_chars += blocks_visible(c['块流'])
    for l in c['剥离账']:
        got_chars += visible(l['原文'])
for kp in tree['考点']:
    if kp['方法点拨']:
        got_chars += blocks_visible(kp['方法点拨']['块流'])
        for l in kp['方法点拨']['剥离账']:
            got_chars += visible(l['原文'])
    got_chars += visible('【考点%s】%s' % (kp['序'], kp['考点名']))
got_chars += visible(unit_meta['unit'] + unit_meta['title'])
for t in dropped_toc:
    pass    # 考点小目录行是重复的结构噪音，单独记账（见下）
toc_chars = Counter()
for sg_title in dropped_toc:
    toc_chars += visible(sg_title)

diff_lost = BASE_CHARS - (got_chars + toc_chars)
diff_extra = (got_chars + toc_chars) - BASE_CHARS
gate('可见字符多重集守恒', not diff_lost and not diff_extra,
     '原件 %d 字符 / 复原 %d（含目录行 %d）；丢 %d 种 %s；多 %d 种 %s' %
     (sum(BASE_CHARS.values()), sum(got_chars.values()), sum(toc_chars.values()),
      len(diff_lost), dict(list(diff_lost.items())[:8]),
      len(diff_extra), dict(list(diff_extra.items())[:8])))

# 5.4 剥离账自平衡（每题：原文 == 题面 + 账）
bal_bad = []
for c in cards:
    a, b = c['para区间']
    src = Counter()
    for nd in stream[a:b]:
        src += blocks_visible(nd['blocks'])
    got = blocks_visible(c['块流'])
    for l in c['剥离账']:
        got += visible(l['原文'])
    if src != got:
        bal_bad.append({'qid': c['qid'], '丢': dict((src - got).items()), '多': dict((got - src).items())})
gate('剥离账逐题平衡', not bal_bad, '%d/%d 题平衡；不平衡 %s' % (len(cards) - len(bal_bad), len(cards), bal_bad[:3]))

# 5.5 REGEXP=0：剥完之后题面**不许**再以栏目标记/小问号开头
regexp_hits = []
for c in cards:
    txt = blocks_text(c['块流'])
    if not txt.strip():
        continue
    head = txt.lstrip()
    if RE_COL_PREFIX.match(head):
        regexp_hits.append({'qid': c['qid'], '型': '栏目前缀残留', '文': head[:30]})
    for name, rx in RE_SUB:
        if rx.match(head):
            regexp_hits.append({'qid': c['qid'], '型': '小问号残留(' + name + ')', '文': head[:30]})
            break
gate('REGEXP=0（题面无残留题号/栏目前缀）', not regexp_hits, '命中 %d 例 %s' % (len(regexp_hits), regexp_hits[:3]))

# 5.6 误剥闸：小数不许被当成题号剥走
mis = []
for c in cards:
    for l in c['剥离账']:
        if l['类'] != '小问号':
            continue
        a, b = c['para区间']
        for nd in stream[a:b]:
            for blk in J.C.iter_blocks(nd['blocks']):
                if blk['type'] != 'text':
                    continue
                for ln in blk['text'].split('\n'):
                    s = ln.lstrip()
                    if s.startswith(l['原文']):
                        rest = s[len(l['原文']):]
                        if l['原文'].endswith('.') and rest[:1].isdigit():
                            mis.append({'qid': c['qid'], '剥': l['原文'], '后接': rest[:10]})
gate('无误剥（小数/年份未被当题号）', not mis, '命中 %d 例 %s' % (len(mis), mis[:3]))

# 5.7 归属完整：每题都有考点名
noattr = [c['qid'] for c in cards if not c['归属']['考点名']]
gate('归属完整（每题预挂考点名）', not noattr, '缺归属 %d 题 %s' % (len(noattr), noattr[:5]))

# 5.8 配对
unpaired = [c['qid'] for c in cards if c['栏目'] != '典型例题' and not c['配对典例']]
gate('例题↔练习配对', not unpaired, '未配对练习 %d 题 %s' % (len(unpaired), unpaired[:5]))

# ============================================================
# 6. 落盘
# ============================================================
stats = {
    '原件': os.path.basename(SRC),
    '单元': tree['单元'],
    '段区间': [body_head, unit_end],
    '基准': BASE,
    '考点数': len(tree['考点']),
    '题卡数': len(cards),
    '典例数': sum(1 for c in cards if c['栏目'] == '典型例题'),
    '练习数': sum(1 for c in cards if c['栏目'] != '典型例题'),
    '题型分布': dict(Counter(c['题型'] for c in cards)),
    '剥离账条数': dict(Counter(l['类'] for c in cards for l in c['剥离账'])),
    '低置信题数': len([c for c in cards if c['低置信']]),
    '闸': gates,
    '剪掉的考点小目录行': dropped_toc,
}
result = {'统计': stats, '归属树': tree, '题卡': cards}
with open(os.path.join(OUT, '切割结果.json'), 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

print('\n== 结果 ==')
print(json.dumps({k: v for k, v in stats.items() if k != '闸'}, ensure_ascii=False, indent=1))
used = set()
for c in cards:
    for b in J.C.iter_blocks(c['块流']):
        if b['type'] == 'figure' and b.get('src'):
            used.add(os.path.basename(b['src']))
for kp in tree['考点']:
    if kp['方法点拨']:
        for b in J.C.iter_blocks(kp['方法点拨']['块流']):
            if b['type'] == 'figure' and b.get('src'):
                used.add(os.path.basename(b['src']))
removed = 0
for fn in os.listdir(IMGDIR):
    if fn not in used:
        os.remove(os.path.join(IMGDIR, fn)); removed += 1
print('产物：产物/切割结果.json ；本单元用图 %d 张 -> 产物/images/（清掉全书其余 %d 张）'
      % (len(used), removed))
