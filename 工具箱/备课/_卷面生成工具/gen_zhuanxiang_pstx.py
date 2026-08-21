# -*- coding: utf-8 -*-
"""《平行四边形和梯形 · 专项》题目卷 + 答案卷
题源＝书架书《四上数学同步典例考点讲义（人教版）》第五单元 18 考点 102 题（连图取自题库）。
结构＝五大板块（认知台阶重排）→ 18 考点 → 考点内难度爬坡。
"""
import html
import json
import os
import re

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\平四梯形专项'
DATA = json.load(open(os.path.join(OUT, 'u5_questions.json'), encoding='utf-8'))
KP, ITEMS, IMG = DATA['kp'], DATA['items'], DATA['img']

# ── 考点内难度重排（索引置换，原序 = 书上顺序）──
PERM = {
    '一': [0, 1, 10, 8, 9, 11, 2, 3, 7, 4, 5, 6],
    '二': [0, 3, 2, 1],
    '三': [0, 1, 2, 3],
    '四': [0, 1, 2, 3],
    '五': [0, 3, 1, 2],
    '六': [0, 1, 2, 3],
    '七': [0, 1, 2, 3],
    '八': [0, 2, 3, 1],
    '九': [0, 1, 2, 3, 4, 6, 5, 7],
    '十': [0, 3, 1, 2],
    '十一': [0, 2, 1, 3],
    '十二': [0, 1, 2, 3],
    '十三': [0, 1, 2, 3],
    '十四': [0, 2, 3, 1, 6, 7, 5, 4, 8, 10, 9, 11],
    '十五': [0, 2, 1, 3],
    '十六': [0, 1, 3, 2, 4, 5, 7, 6, 8, 9, 11, 10],
    '十七': [0, 4, 2, 1, 3],
    '十八': [0, 2, 1, 3, 4],
}

# ── 五大板块（认知台阶）──
BLOCKS = [
    dict(no='一', name='位置关系', sub='地基：平行、垂直、点到直线的距离',
         key='同一平面内，垂直于同一条直线的两条直线互相平行；点到直线的距离＝垂线段最短。'
             '数组数时记得把线<b>延长</b>再判断，别只数看得见相交的。',
         kps=['一', '二']),
    dict(no='二', name='尺规作图', sub='基本功：作垂线、作平行线、最佳路线、最大正方形',
         key='三角尺＋直尺两个标准动作：作垂线（直角边贴线滑动）、作平行线（直尺固定、三角尺平移）。'
             '<b>最佳路线一律作垂线，不是连端点</b>；画完必须标直角符号；注意单位换算。',
         kps=['三', '四', '五', '十二']),
    dict(no='三', name='认识与分类', sub='概念网：各部分名称、性质、分类、数图形',
         key='正方形 ⊂ 长方形 ⊂ 平行四边形；梯形<b>只有一组</b>对边平行，独立在外。'
             '平四<b>不稳定（易变形）</b>——伸缩门、晾衣架、推拉门、折叠椅全考这个；'
             '等腰梯形同一底上两底角相等，四边形内角和 360°。数图形要<b>分类、有序、不重不漏</b>。',
         kps=['六', '七', '八', '十三']),
    dict(no='四', name='高与画图', sub='难点：找高、作高、画图形、裁剪',
         key='高＝从一条边上任一点向<b>对边</b>作的垂线段，垂足所在的边才是底。'
             '<b>斜边不是高</b>——这是本单元最大的丢分点；不同的底对应不同的高；'
             '梯形的高＝两底之间的距离。画高用<b>虚线</b>并标直角符号。',
         kps=['九', '十', '十一']),
    dict(no='五', name='周长与变化', sub='重头：周长、反求、拉伸、拼接、底边变化',
         key='平四周长＝(邻边和)×2，<b>反求：邻边＝周长÷2－已知边</b>（"周长的一半"是钥匙）；'
             '梯形周长＝上底＋下底＋两腰，反求腰＝(周长－两底)÷2。'
             '拉伸→<b>周长不变</b>（面积变）；拼接→<b>拼合处的边消失，周长不是两倍</b>；'
             '靠墙只围三面，要最省就让<b>最长边靠墙</b>。',
         kps=['十四', '十五', '十六', '十七', '十八']),
]

from paper_css import PRINT_CSS

CSS = PRINT_CSS + """
/* 本册特有：板块大标题（黑体加粗＋上下双线，不用色块）＋ 考点小标题 ＋ 钥匙框 */
.bsec { margin: 0 0 3.5mm; page-break-after: avoid; }
.bsec .bt { font-family:"SimHei","Microsoft YaHei",sans-serif; font-size:15pt; font-weight:bold;
            display:block; padding:1.6mm 0; border-top:1.2pt solid #000; border-bottom:1.2pt solid #000; }
.bsec .bs { font-size:10pt; color:#333; padding:1.2mm 0 0; }
.keybox { border-left:1.6pt solid #666; padding:0.6mm 0 0.6mm 3.2mm; margin:2.5mm 0 3.5mm;
          font-size:10pt; color:#333; page-break-inside:avoid; }
.keybox .lab { font-family:"SimHei","Microsoft YaHei",sans-serif; font-weight:bold; color:#000; }
.kp { font-family:"SimHei","Microsoft YaHei",sans-serif; font-size:12pt; font-weight:bold;
      border-bottom:0.6pt solid #666; margin:4.5mm 0 2mm; padding-bottom:0.8mm; page-break-after:avoid; }
.toc { font-size:10.5pt; line-height:1.85; }
.toc .b { font-family:"SimHei","Microsoft YaHei",sans-serif; font-weight:bold; }
"""


def demath(t):
    """行内 LaTeX（$ABCD$ / $126$ / $\\angle ABC$ / $135^\\circ$）→ 干净 HTML。
    🔴 不处理会在卷面上裸露美元符号。"""
    def inner(m):
        s = m.group(1)
        for a, b in (('\\angle', '∠'), ('^\\circ', '°'), ('\\times', '×'), ('\\div', '÷'),
                     ('\\cdot', '·'), ('\\%', '%'), ('\\,', ''), ('\\ ', '')):
            s = s.replace(a, b)
        s = re.sub(r'\s+', '', s)
        return f'<i>{s}</i>' if re.search(r'[A-Za-z]', s) else s
    return re.sub(r'\$([^$]{1,60})\$', inner, t)


def esc(t):
    return demath(html.escape(t or '')).replace('\n', '<br>')


def render_blocks(bj):
    """block_json → HTML（text 段 + image 段）。"""
    out = []
    try:
        obj = json.loads(bj) if isinstance(bj, str) else (bj or {})
    except Exception:
        return ''
    for row in obj.get('rows', []):
        for cell in row.get('cells', []):
            if cell.get('type') == 'image':
                url = cell.get('url', '')
                src = IMG.get(url, url)
                w = cell.get('width') or 40
                out.append(f'<div class="fig"><img src="{src}" style="width:{min(int(w) * 1.15, 82)}%"></div>')
                if cell.get('caption'):
                    out.append(f'<div class="cap">{esc(cell["caption"])}</div>')
            else:
                md = cell.get('md') or cell.get('text') or ''
                md = re.sub(r'!\[\]\(([^)]+)\)', '', md)
                out.append(esc(md))
    return ''.join(out)


def g(item, *names):
    for n in names:
        if item.get(n) not in (None, ''):
            return item[n]
    return ''


def kp_entries():
    """返回 [(板块, 考点号, 考点标题, [题id...])]，考点内已按难度重排。"""
    res = []
    for blk in BLOCKS:
        for no in blk['kps']:
            key = next(k for k in KP if k.startswith(f'【考点{no}】'))
            ids = KP[key]
            perm = PERM.get(no, list(range(len(ids))))
            ordered = [ids[i] for i in perm]
            res.append((blk, no, key.split('】', 1)[1], ordered))
    return res


ENTRIES = kp_entries()


def build(with_answers):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>平行四边形和梯形·专项</title>'
         f'<style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>平行四边形和梯形 · 专项</h1>')
    h.append(f'<div class="sub">四年级上册 第五单元 · 18 个考点'
             f'{"　教师用 · 含答案解析" if with_answers else ""}</div>')

    # 目录
    h.append('<div class="toc">')
    cur = None
    n = 0
    for blk, no, name, ids in ENTRIES:
        if blk is not cur:
            cur = blk
            h.append(f'<div class="b">板块{blk["no"]}　{blk["name"]}——{blk["sub"]}</div>')
        h.append(f'　　考点{no}　{name}　<span style="color:#555">第 {n + 1}–{n + len(ids)} 题</span><br>')
        n += len(ids)
    h.append('</div>')

    cur = None
    n = 0
    for blk, no, name, ids in ENTRIES:
        if blk is not cur:
            cur = blk
            h.append(f'<div class="bsec newpage"><span class="bt">板块{blk["no"]}　{blk["name"]}</span>'
                     f'<div class="bs">{blk["sub"]}</div></div>')
            if with_answers:
                h.append(f'<div class="keybox"><span class="lab">【本板块的钥匙】</span>{blk["key"]}</div>')
        h.append(f'<div class="kp">考点{no}　{name}</div>')
        for qid in ids:
            n += 1
            it = ITEMS.get(str(qid))
            if not it:
                h.append(f'<div class="q"><span class="no">{n}．</span>[题 {qid} 缺失]</div>')
                continue
            body = render_blocks(g(it, 'blockJson', 'block_json')) or esc(g(it, 'stemText', 'stem_text'))
            h.append(f'<div class="q"><span class="no">{n}．</span>{body}</div>')
            if with_answers:
                ans = esc(g(it, 'answer'))
                ana = esc(g(it, 'analyze'))
                p = f'<p><span class="lab">【答案】</span>{ans}</p>'
                if ana:
                    p += f'<p><span class="lab">【解析】</span>{ana}</p>'
                h.append(f'<div class="ansbox">{p}</div>')
            else:
                qt = g(it, 'questionType', 'question_type')
                h.append(f'<div class="{"sp" if qt in (5, 6, 3) else "spm"}"></div>')
    h.append('</div></body></html>')
    return '\n'.join(h)


for fn, flag in (('平行四边形和梯形·专项·题目卷.html', False),
                 ('平行四边形和梯形·专项·答案卷.html', True)):
    with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
        f.write(build(flag))
print('HTML done ->', OUT, '| 题数', sum(len(i) for _, _, _, i in ENTRIES))
