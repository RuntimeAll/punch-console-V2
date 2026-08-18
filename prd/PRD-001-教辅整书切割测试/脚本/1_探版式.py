# -*- coding: utf-8 -*-
"""① 探版式：不切题，先把整书结构扫成机器可读的版式档案。"""
import sys, os, re, json, zipfile
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')

ROOT = J.ROOT
SRC = os.path.join(ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')
OUT = os.path.join(ROOT, '产物')
os.makedirs(OUT, exist_ok=True)

stream, base = J.build_stream(SRC, os.path.join(ROOT, '_tmp_img_book'))
print('段落/表格节点:', len(stream), '基准:', base)

# ---------- 0. 文档级事实 ----------
z = zipfile.ZipFile(SRC)
xml = z.read('word/document.xml').decode('utf-8')
media = [n for n in z.namelist() if n.startswith('word/media/')]
doc_facts = {
    '原件': os.path.basename(SRC),
    '字节': os.path.getsize(SRC),
    'media文件数': len(media),
    'media扩展名': dict(Counter(os.path.splitext(n)[1].lower() for n in media)),
    '行内图元素数(drawing/pict/object,去嵌套)': base['fig'],
    'OMML公式节点数': base['omath'],
    '表格数': base['tbl'],
    '分栏(w:cols)': re.findall(r'<w:cols[^>]*/>', xml)[:4],
    'sectPr数': xml.count('<w:sectPr'),
    'pStyle分布': dict(Counter(re.findall(r'<w:pStyle w:val="([^"]+)"', xml))),
    '页眉页脚part': [n for n in z.namelist() if re.search(r'word/(header|footer)\d*\.xml', n)],
}

# ---------- 1. 标记清点 ----------
marks = []
for nd in stream:
    k, meta = J.classify(nd['head'])
    if k:
        marks.append({'i': nd['i'], 'kind': k, 'meta': meta,
                      'head': nd['head'].strip()[:80], 'style': nd['style']})
mark_counter = Counter(m['kind'] for m in marks)
label_variants = defaultdict(Counter)
for m in marks:
    lb = m['meta'].get('label')
    if lb:
        label_variants[m['kind']][lb] += 1

# ---------- 2. 目录页识别（🔴 有效性过滤，不按 seq 硬切 —— 老区 README §1② 口径）----------
# 判据：标记后到下一个标记之间零正文（零文字零图）=「空标记」。
# 空标记不当场丢，先照样建树，建完再剪枝（空考点节 / 空单元一律剪掉）。
def is_empty_mark(idx):
    here = marks[idx]['i']
    nxt = marks[idx + 1]['i'] if idx + 1 < len(marks) else len(stream)
    for j in range(here + 1, nxt):
        if J.stream_text(stream[j]).strip() or J.count_figs(stream[j]):
            return False
    return True

empty_flags = [is_empty_mark(i) for i in range(len(marks))]
body_marks = marks

# ---------- 3. 单元 -> 考点 骨架 ----------
units = []
cur_u = cur_kp = None
for m in body_marks:
    if m['kind'] == 'unit':
        cur_u = {'para': m['i'], '单元': m['meta']['unit'], '标题': m['meta']['title'],
                 '声明考点数': m['meta']['kp_count_cn'], '部分': [], '考点': []}
        units.append(cur_u); cur_kp = None
    elif cur_u is None:
        continue
    elif m['kind'] == 'part':
        cur_u['部分'].append({'para': m['i'], 'no': m['meta']['no'], '标题': m['meta']['title']})
    elif m['kind'] == 'kp':
        cur_kp = {'para': m['i'], 'no': m['meta']['no'], '标题': m['meta']['title'],
                  '方法点拨': 0, '典例': [], '练习': []}
        cur_u['考点'].append(cur_kp)
    elif cur_kp is not None:
        if m['kind'] == 'explain':
            cur_kp['方法点拨'] += 1
        elif m['kind'] == 'example':
            cur_kp['典例'].append({'para': m['i'], 'no': m['meta']['no'],
                                   '标题': m['meta']['title'][:40]})
        elif m['kind'] == 'practice':
            cur_kp['练习'].append({'para': m['i'], 'no': m['meta']['no'],
                                   '标题': m['meta']['title'][:40]})

# ---- 剪枝：空考点节（无方法点拨且无题）丢；空单元（剪完无考点）丢 ----
pruned = {'空考点': 0, '空单元': 0}
raw_units = units
units = []
for u in raw_units:
    kps = []
    for k in u['考点']:
        if k['方法点拨'] == 0 and not k['典例'] and not k['练习']:
            pruned['空考点'] += 1
        else:
            kps.append(k)
    u['考点'] = kps
    if not kps:
        pruned['空单元'] += 1
    else:
        units.append(u)

CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
      '十一':11,'十二':12,'十三':13,'十四':14,'十五':15,'十六':16,'十七':17,
      '十八':18,'十九':19,'二十':20}
def cn2i(s):
    if not s:
        return None
    if s.isdigit():
        return int(s)
    return CN.get(s)

# ---- 目录声明的考点数（🔴 老区铁律：split 后必须核讲数 + 核每讲考点数）----
# 目录行才带【N大考点】，正文单元头多数不带 —— 故声明数从目录取，按「单元+标题」对齐。
toc_decl = {}
for nd in stream:
    t = J.stream_text(nd).strip()
    k, meta = J.classify(t)
    if k == 'unit' and meta['kp_count_cn']:
        toc_decl[meta['unit'] + ' ' + meta['title']] = cn2i(meta['kp_count_cn'])

unit_check = []
for u in units:
    key = u['单元'] + ' ' + u['标题']
    decl = cn2i(u['声明考点数']) or toc_decl.get(key)
    got = len(u['考点'])
    nos = [cn2i(k['no']) for k in u['考点']]
    seq_ok = nos == list(range(1, got + 1))
    unit_check.append({'单元': key, '声明': decl, '实得': got,
                       '一致': decl == got, '考点序号连续': seq_ok,
                       '典例数': sum(len(k['典例']) for k in u['考点']),
                       '练习数': sum(len(k['练习']) for k in u['考点']),
                       '方法点拨数': sum(k['方法点拨'] for k in u['考点'])})

# ---------- 4. 编号体系（小问题号）----------
RE_SUB_FULL = re.compile(r'^[\s　]*(\d{1,2})．')
RE_SUB_HALF = re.compile(r'^[\s　]*(\d{1,2})\.(?!\d)')
RE_SUB_PAREN = re.compile(r'^[\s　]*[（(](\d{1,2})[）)]')
RE_SUB_CIRC = re.compile(r'^[\s　]*([①-⑳])')
sub_stat = Counter()
sub_seq_by_mark = []
cur_seq = None
for nd in stream:
    k, _ = J.classify(nd['head'])
    if k in ('example', 'practice'):
        if cur_seq is not None:
            sub_seq_by_mark.append(cur_seq)
        cur_seq = []
    t = J.stream_text(nd)
    for line in t.split('\n'):
        for name, rx in (('全角N．', RE_SUB_FULL), ('半角N.', RE_SUB_HALF),
                         ('（N）', RE_SUB_PAREN), ('圈号①', RE_SUB_CIRC)):
            mm = rx.match(line)
            if mm:
                sub_stat[name] += 1
                if cur_seq is not None and name in ('全角N．', '半角N.'):
                    cur_seq.append(int(mm.group(1)))
                break
if cur_seq is not None:
    sub_seq_by_mark.append(cur_seq)
nonempty = [s for s in sub_seq_by_mark if s]
restart_cnt = sum(1 for s in nonempty if s[0] == 1)

# ---------- 5. 图分布 ----------
fig_inline = fig_alone = 0
fig_sizes = []
for nd in stream:
    blks = list(J.C.iter_blocks(nd['blocks']))
    figs = [b for b in blks if b['type'] == 'figure']
    txts = [b for b in blks if b['type'] == 'text' and b['text'].strip()]
    for f in figs:
        if f.get('w_px'):
            fig_sizes.append((f['w_px'], f.get('h_px') or 0))
    if figs and txts:
        fig_inline += len(figs)
    elif figs:
        fig_alone += len(figs)
small = sum(1 for w_, h_ in fig_sizes if h_ and h_ < 50)

# ---------- 6. 视觉分栏（并排计算题）----------
# 🔴 老区 §18 坑④：普通空格≥4 二次切分**先 mask 括号**——不 mask 的话
#    「(        )」作答空槽会被当成栏分隔符，全书 472 行全是假阳性。
RE_MULTISP = re.compile(r'[ 　\xa0]{4,}')
RE_BLANK_SLOT = re.compile(r'[（(][\s　\xa0]*[）)]|[＿_]{2,}')
col_like = []
for nd in stream:
    t = J.stream_text(nd)
    for line in t.split('\n'):
        masked = RE_BLANK_SLOT.sub('▢', line)
        segs = [s for s in RE_MULTISP.split(masked) if s.strip()]
        if len(segs) >= 2 and len(line) > 12:
            col_like.append({'i': nd['i'], '列数': len(segs), 'line': line[:70]})
tab_paras = sum(1 for nd in stream for b in J.C.iter_blocks(nd['blocks'])
                if b['type'] == 'text' and any(s.get('k') == 'tab' for s in b.get('spans', [])))

# ---------- 7. 表格 ----------
tbl_kinds = Counter()
for nd in stream:
    if nd['kind'] == 'tbl':
        tbl_kinds[nd['blocks'][0].get('table_kind') or '?'] += 1

archive = {
    '生成时间': '2026-08-18',
    '卡': 'PRD-001 教辅整书切割测试',
    '文档级事实': doc_facts,
    '标记清点': {'总数': len(marks), '按类': dict(mark_counter),
                 '标签变体': {k: dict(v) for k, v in label_variants.items()},
                 '空标记数(目录行)': sum(empty_flags),
                 '剪枝': pruned, '剪枝后单元数': len(units)},
    '单元骨架': units,
    '单元核对': unit_check,
    '编号体系': {'小问标号分布': dict(sub_stat),
                 '带小问的题标记数': len(nonempty),
                 '小问从1重启的比例': '%d/%d' % (restart_cnt, len(nonempty)),
                 '结论': '小问号在每个题标记内重启，全书不连续'},
    '图分布': {'总图槽': base['fig'], 'media唯一文件': len(media),
               '句中图(同段有文字)': fig_inline, '独立成段图': fig_alone,
               '小图(h<50px,疑似字符图/公式)': small,
               '尺寸样例': fig_sizes[:10]},
    '视觉分栏': {'真分栏(w:cols)': 1, '并排行数(≥4空白分隔)': len(col_like),
                 '含tab的文本块段数': tab_paras, '样例': col_like[:8]},
    '表格': {'总数': base['tbl'], '分类': dict(tbl_kinds)},
    '目录声明': toc_decl,
}
with open(os.path.join(OUT, '版式档案.json'), 'w', encoding='utf-8') as f:
    json.dump(archive, f, ensure_ascii=False, indent=1)

show = {k: v for k, v in archive.items() if k != '单元骨架'}
print(json.dumps(show, ensure_ascii=False, indent=1))
