# -*- coding: utf-8 -*-
"""平四梯形一轮 · 同步课卷一条命令生成器（2026-08-07 由 gen_l10 泛化定版）
用法：
    python gen_同步课.py l11            # 按预填配置出双卷 HTML
    python gen_同步课.py l11 --out DIR  # 输出到指定目录（默认按配置里的 out）
出 PDF（Edge 无头，写盘异步，转完 sleep 2 再 QA）：
    msedge --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="....pdf" "file:///....html"
题源 = 平四梯形专项/u5_questions.json（102 题 + 本地 figs/，零网络依赖）。
框架正本 = ../_单元框架/平行四边形和梯形·一轮教学框架.md（五次课排布 L9-13）。
热身位 = 当周学情弱点（上课后用户说哪个考点不会，就把它填进下一课 warmup）。
"""
import html
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

SRC = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\平四梯形专项'
ROOT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课'

DATA = json.load(open(os.path.join(SRC, 'u5_questions.json'), encoding='utf-8'))
KP, ITEMS, IMG_REL = DATA['kp'], DATA['items'], DATA['img']
IMG = {url: 'file:///' + os.path.join(SRC, rel).replace(os.sep, '/') for url, rel in IMG_REL.items()}

# 个别题图宽度矫正（%），键=图文件名尾巴
WIDTH_OVERRIDE = {'a7091d8012c7d472.png': 55}

# 考点内难度重排（与 gen_zhuanxiang_pstx.py 的 PERM 同源）
PERM = {
    '一': [0, 1, 10, 8, 9, 11, 2, 3, 7, 4, 5, 6], '二': [0, 3, 2, 1], '三': [0, 1, 2, 3],
    '四': [0, 1, 2, 3], '五': [0, 3, 1, 2], '六': [0, 1, 2, 3], '七': [0, 1, 2, 3],
    '八': [0, 2, 3, 1], '九': [0, 1, 2, 3, 4, 6, 5, 7], '十': [0, 3, 1, 2], '十一': [0, 2, 1, 3],
    '十二': [0, 1, 2, 3], '十三': [0, 1, 2, 3], '十四': [0, 2, 3, 1, 6, 7, 5, 4, 8, 10, 9, 11],
    '十五': [0, 2, 1, 3], '十六': [0, 1, 3, 2, 4, 5, 7, 6, 8, 9, 11, 10],
    '十七': [0, 4, 2, 1, 3], '十八': [0, 2, 1, 3, 4],
}

# ── 每课配置：sections = (节标题, 方法点拨, 考点号, 置换或None=用PERM, 选题下标或None=全量) ──
CONFIGS = {
    'l10': dict(
        lesson='第10课 · 尺规作图', date='2026年8月9日 · 四年级上册 第五单元（同步）',
        out=os.path.join(ROOT, '第10课-尺规作图-20260809'), stem='第10课·尺规作图',
        key='三角尺＋直尺两个标准动作：作垂线（直角边贴线滑动）、作平行线（直尺固定、三角尺平移）。'
            '<b>最佳路线一律作垂线，不是连端点</b>；画完必须标直角符号；注意单位换算。',
        sections=[
            ('热身 · 数平行线与垂线', '按顺序数，不重不漏；有的线要先<b>延长</b>，再判断相交和垂直。', '二', None),
            ('垂线的应用：最短路线',
             '从直线外一点到这条直线，<b>垂线段最短</b>。取水最近、接水管最省材料，都是过这个点向线作垂线，'
             '<b>不是连到端点</b>。两点之间要修最近的路，才是连线段。', '四', None),
            ('画指定长、宽的长方形和正方形',
             '先画一条边，再用三角尺的直角边过端点作垂线。注意<b>单位换算</b>（10毫米＝1厘米），画完标上直角符号。', '五', None),
            ('平行线之间画最大的正方形', '先作垂线量出<b>平行线之间的距离</b>，以这个距离为边长画正方形。', '十二', None),
        ]),
    'l11': dict(
        lesson='第11课 · 平行四边形和梯形的认识', date='2026年8月16日 · 四年级上册 第五单元（同步）',
        out=os.path.join(ROOT, '第11课-认识与分类-20260816'), stem='第11课·认识与分类',
        key='正方形 ⊂ 长方形 ⊂ 平行四边形；梯形<b>只有一组</b>对边平行，独立在外。'
            '平四<b>不稳定（易变形）</b>——伸缩门、晾衣架、推拉门、折叠椅全考这个；'
            '等腰梯形同一底上两底角相等，四边形内角和 360°。数图形要<b>分类、有序、不重不漏</b>。',
        warn='⚠️ 第7课(卷184)已用过考点七×1（纯文字·平四不稳定性，伸缩门或折叠椅那道），出卷前对照卷184剔重；热身位按上课后学情填。',
        sections=[
            # ('热身 · <上周弱点>', '<点拨>', '<考点号>', None),   ← 周日上完课按学情填这行
            ('平行四边形和梯形的认识', '互相平行的一组对边是梯形的上底和下底，不平行的是腰；先认名称再谈性质。', '六', None),
            ('平行四边形的特性', '平行四边形容易变形（<b>不稳定性</b>）——伸缩门、晾衣架、折叠椅都是它。', '七', None),
            ('梯形的分类', '有一个角是直角的是<b>直角梯形</b>；两腰相等的是<b>等腰梯形</b>。', '八', None),
            ('数平行四边形和梯形', '按大小分类数：单个的→两个拼的→更多拼的，<b>有序、不重不漏</b>。', '十三', None),
        ]),
    'l12': dict(
        lesson='第12课 · 高与画图', date='2026年8月23日 · 四年级上册 第五单元（同步）',
        out=os.path.join(ROOT, '第12课-高与画图-20260823'), stem='第12课·高与画图',
        key='高＝从一条边上任一点向<b>对边</b>作的垂线段，垂足所在的边才是底。'
            '<b>斜边不是高</b>——这是本单元最大的丢分点；不同的底对应不同的高；'
            '梯形的高＝两底之间的距离。画高用<b>虚线</b>并标直角符号。',
        warn='本课是单元最大难点（读图找高最坑），热身位按上课后学情填。',
        sections=[
            ('找底和高', '先认底：垂足所在的边才是底。图上给一堆数据时，<b>斜着的边不是高</b>。', '九', None),
            ('画平行四边形和梯形', '点子图上画平四和梯形：先定一组平行边，再对格数画。', '十', None),
            ('裁剪平行四边形和梯形', '裁剪线怎么画看要求：平四剪一刀出两个梯形，剪的线要<b>与一组对边平行</b>。', '十一', None),
        ]),
    'l13': dict(
        lesson='第13课 · 周长与变化', date='2026年8月30日 · 四年级上册 第五单元（同步）',
        out=os.path.join(ROOT, '第13课-周长与变化-20260830'), stem='第13课·周长与变化',
        key='平四周长＝(邻边和)×2，<b>反求：邻边＝周长÷2－已知边</b>；梯形反求腰＝(周长－两底)÷2。'
            '拉伸→<b>周长不变</b>；拼接→<b>拼合处的边消失，周长不是两倍</b>；靠墙只围三面，最长边靠墙最省。',
        warn='⚠️ 本模块38题只上12题左右，且第7课(卷184)已用掉 十四×3、十五×1、十六×2、十八×1——'
             '出卷前必须对照卷184剔重后精选（每类各挑易/中/压轴，砍中间难度）。sections 里的 pick 待选题后填下标。',
        sections=[
            ('平行四边形的周长', '周长＝(邻边和)×2；反求邻边＝周长÷2－已知边。', '十四', None),
            ('拉伸问题', '长方形框拉成平四：<b>周长不变</b>，面积变小。', '十五', None),
            ('梯形的周长', '周长＝上底＋下底＋两腰；等腰梯形反求腰＝(周长－两底)÷2。', '十六', None),
            ('拼接与底边变化', '两个完全一样的梯形能拼成平行四边形；<b>拼合处的边消失</b>，周长不是两倍。', '十七', None),
            ('底边的变化', '上底延长后变成平四/长方形：延长的长度＝下底与上底的差。', '十八', None),
        ]),
}

CSS = """
@page { size: A4; margin: 13mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 11.5pt; line-height: 1.65; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 20pt; margin: 3mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 4mm; }
.kp { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 13pt;
      border-bottom: 1px solid #cfe0f0; margin: 4.5mm 0 1.5mm; padding-bottom: 0.8mm; page-break-after: avoid; }
.tip { background: #fff8e6; border-left: 3px solid #e0b64a; padding: 1.6mm 3mm; margin: 1.5mm 0 2.5mm;
       font-size: 10.5pt; color: #5a4300; page-break-inside: avoid; }
.tip .lab { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #8a6a00; }
.keybox { background: #fff8e6; border-left: 3px solid #e0b64a; padding: 2mm 3mm; margin: 2mm 0 3mm;
          font-size: 10.5pt; color: #5a4300; page-break-inside: avoid; }
.keybox .lab { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #8a6a00; }
.q { margin: 0 0 1.2mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.fig { margin: 1mm 0 1mm 6mm; page-break-inside: avoid; }
.fig img { max-width: 100%; }
.sp { height: 12mm; } .spm { height: 7mm; } .spl { height: 28mm; }
.pline { width: 78mm; border-bottom: 1.6px solid #111; height: 0; margin: 15mm 0 2mm 10mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 1.6mm 3mm; margin: 1mm 0 2.5mm;
          page-break-inside: avoid; font-size: 10.5pt; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.4mm 0; }
.note { color: #888; font-size: 9.5pt; margin: 1mm 0 3mm; }
.foot { text-align: center; color: #999; font-size: 9pt; margin-top: 6mm; }
"""


def esc(t):
    return html.escape(t or '').replace('\n', '<br>')


def render_blocks(bj):
    """返回 (html, has_draw_area)。文本里 3+ 连续下划线视作给定的平行线，转成真横线。"""
    out = []
    has_draw = False
    try:
        obj = json.loads(bj) if isinstance(bj, str) else (bj or {})
    except Exception:
        return '', False
    for row in obj.get('rows', []):
        for cell in row.get('cells', []):
            if cell.get('type') == 'image':
                url = cell.get('url', '')
                src = IMG.get(url, url)
                w = cell.get('width') or 40
                for tail, ow in WIDTH_OVERRIDE.items():
                    if url.endswith(tail):
                        w = ow
                out.append(f'<div class="fig"><img src="{src}" style="width:{min(int(w) * 1.15, 82)}%"></div>')
                has_draw = True
            elif cell.get('type') == 'option':
                parts = ''.join(c.get('md') or '' for c in cell.get('content', []))
                out.append(f'　{cell.get("label", "")}．{esc(parts)}')
            else:
                md = cell.get('md') or cell.get('text') or ''
                md = re.sub(r'!\[\]\(([^)]+)\)', '', md)
                t = esc(md)
                if re.search(r'[＿_]{3,}', t):
                    t = re.sub(r'(<br>)*[＿_]{3,}(<br>)*', '<div class="pline"></div>', t)
                    has_draw = True
                out.append(t)
    return ''.join(out), has_draw


def g(item, *names):
    for n in names:
        if item.get(n) not in (None, ''):
            return item[n]
    return ''


def build(cfg, with_answers):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{cfg["lesson"]}</title>'
         f'<style>{CSS}</style></head><body><div class="doc">']
    h.append(f'<h1>{cfg["lesson"]}</h1>')
    h.append(f'<div class="sub">{cfg["date"]}{"（教师用 · 含答案解析）" if with_answers else ""}</div>')
    if with_answers:
        h.append(f'<div class="keybox"><span class="lab">【本课的钥匙】</span>{cfg["key"]}</div>')
        h.append('<div class="note">作图题的示范图请翻《平行四边形和梯形·专项·原书答案卷（解析版）》对应考点。</div>')
    n = 0
    for title, tip, kp_no, pick in cfg['sections']:
        key = next(k for k in KP if k.startswith(f'【考点{kp_no}】'))
        ids = KP[key]
        perm = PERM.get(kp_no, list(range(len(ids))))
        ordered = [ids[i] for i in perm]
        if pick is not None:
            ordered = [ordered[i] for i in pick]
        h.append(f'<div class="kp">{title}</div>')
        h.append(f'<div class="tip"><span class="lab">【方法点拨】</span>{tip}</div>')
        for qid in ordered:
            n += 1
            it = ITEMS[str(qid)]
            body, has_draw = render_blocks(g(it, 'blockJson', 'block_json'))
            if not body:
                body, has_draw = esc(g(it, 'stemText', 'stem_text')), False
            h.append(f'<div class="q"><span class="no">{n}．</span>{body}</div>')
            if with_answers:
                ans = esc(g(it, 'answer'))
                ana = esc(g(it, 'explain', 'analyze'))
                p = f'<p><span class="lab">【答案】</span>{ans}</p>'
                if ana:
                    p += f'<p><span class="lab">【解析】</span>{ana}</p>'
                h.append(f'<div class="ansbox">{p}</div>')
            else:
                qt = g(it, 'questionType', 'question_type')
                if qt in (5, 6, 3) and not has_draw:
                    sp = 'spl'
                elif qt in (5, 6, 3):
                    sp = 'sp'
                else:
                    sp = 'spm'
                h.append(f'<div class="{sp}"></div>')
    h.append('<div class="foot">— 完 —</div></div></body></html>')
    return '\n'.join(h)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args or args[0] not in CONFIGS:
        print('用法: python gen_同步课.py', '|'.join(CONFIGS))
        sys.exit(1)
    cfg = CONFIGS[args[0]]
    out = cfg['out']
    if '--out' in sys.argv:
        out = sys.argv[sys.argv.index('--out') + 1]
    os.makedirs(out, exist_ok=True)
    if cfg.get('warn'):
        print(cfg['warn'])
    for suffix, flag in (('题目卷', False), ('答案卷', True)):
        fn = f'{cfg["stem"]}·{suffix}.html'
        with open(os.path.join(out, fn), 'w', encoding='utf-8') as f:
            f.write(build(cfg, flag))
    print('HTML done ->', out)
