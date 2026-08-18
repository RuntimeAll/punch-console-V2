# -*- coding: utf-8 -*-
"""
③b 预览（左原文连续流 / 右归属树+题卡+抽离账） + ④ 导出还原（打印件 HTML → PDF）
🔴 题面一律从 block['text'] 渲染（= 抽离**之后**的题面），这样导出件就是
   「存进去的东西原样拿出来」的真实检验，而不是拿原始 spans 作弊。
"""
import sys, os, re, json, base64, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')

ROOT = J.ROOT
OUT = os.path.join(ROOT, '产物')
IMGDIR = os.path.join(OUT, 'images')
SRC = os.path.join(ROOT, '原料', '空白', '四下数学同步讲义1-9单元（原卷版）162页 人教版.docx')

R = json.load(open(os.path.join(OUT, '切割结果.json'), encoding='utf-8'))
cards = R['题卡']
tree = R['归属树']
stats = R['统计']

def b64(src):
    p = os.path.join(OUT, src.replace('/', os.sep))
    if not os.path.exists(p):
        return None
    ext = os.path.splitext(p)[1].lstrip('.').lower()
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'gif': 'image/gif', 'bmp': 'image/bmp', 'wmf': 'image/wmf'}.get(ext, 'application/octet-stream')
    return 'data:%s;base64,%s' % (mime, base64.b64encode(open(p, 'rb').read()).decode('ascii'))

def esc(s):
    return html.escape(s or '')

def txt_html(t):
    """文本块 -> HTML。保留 NBSP/全角空格（作答留白），半角空格串转 nbsp 防 CSS 折叠。"""
    s = esc(t)
    s = s.replace('\xa0', '&nbsp;')
    s = re.sub(r'  +', lambda m: '&nbsp;' * len(m.group(0)), s)
    return s.replace('\n', '<br>')

def render_blocks(blocks, cls='', maxw=460):
    out = []
    for b in blocks:
        if b['type'] == 'text':
            if not b.get('text', '').strip():
                if b.get('emptied'):
                    out.append('<p class="shell">〔本块内容已全部抽离进元信息〕</p>')
                continue
            out.append('<p class="tb %s">%s</p>' % (cls, txt_html(b['text'])))
        elif b['type'] == 'figure':
            d = b64(b.get('src') or '')
            w = min(max(b.get('w_px') or 220, 60), maxw)
            if d:
                out.append('<figure class="fg"><img src="%s" style="width:%dpx"></figure>' % (d, w))
            else:
                out.append('<div class="miss">[图丢失 %s]</div>' % esc(str(b.get('src'))))
        elif b['type'] == 'table':
            out.append('<div class="tbl">%s</div>' % esc(b.get('flat_text') or '[表]'))
    return ''.join(out)

# ============================================================
# 一、预览页
# ============================================================
stream, base = J.build_stream(SRC, os.path.join(ROOT, '_tmp_img_book2'))
a, b_ = stats['段区间']
left = []
for nd in stream[a:b_]:
    k, meta = J.classify(nd['head'])
    tag = {'unit': '单元', 'kp': '考点', 'part': '部分', 'explain': '点拨',
           'example': '典例', 'practice': '练习'}.get(k, '')
    blocks = []
    for blk in nd['blocks']:
        if blk['type'] == 'figure':
            # 左栏用同一批图（切割时已按 rId 缓存，文件名一致）
            blocks.append(blk)
        else:
            blocks.append(blk)
    body = render_blocks([{'type': 'text', 'text': J.C.spans_to_flat(bb.get('spans', []))}
                          if bb['type'] == 'text' else bb for bb in nd['blocks']], maxw=300)
    left.append('<div class="src" id="p%d"><span class="pno">%d</span>'
                '%s%s</div>' % (nd['i'], nd['i'],
                                ('<span class="mk mk-%s">%s</span>' % (k, tag)) if tag else '',
                                body or '<span class="empty">·</span>'))

# 右栏：归属树 + 题卡
right = []
right.append('<div class="tree"><h3>归属树（考点名为机器预挂）</h3>')
for kp in tree['考点']:
    right.append('<div class="kp"><b>【考点%s】%s</b> <small>%d 题</small></div>'
                 % (esc(kp['序']), esc(kp['考点名']), len(kp['题'])))
    for q in kp['题']:
        right.append('<div class="tq">%s%s <a href="#%s">%s</a> <em>%s</em>%s</div>'
                     % (esc(q['栏目']), esc(q['栏目序号'] or ''), q['qid'], q['qid'],
                        esc(q['题型']),
                        (' ← 配 %s' % q['配对典例']) if q['配对典例'] else ''))
right.append('</div>')

for c in cards:
    lc = c['低置信']
    right.append('<div class="card %s" id="%s">' % ('low' if lc else '', c['qid']))
    right.append('<div class="ch"><b>%s</b> · %s%s · <em>%s</em>'
                 ' <small>%s → 【考点%s】%s</small>%s</div>'
                 % (c['qid'], esc(c['栏目']), esc(c['栏目序号'] or ''), esc(c['题型']),
                    esc(c['归属']['单元']), esc(c['归属']['考点序']), esc(c['归属']['考点名']),
                    (' <span class="pair">配 %s</span>' % c['配对典例']) if c['配对典例'] else ''))
    if c['标题']:
        right.append('<div class="ttl">标题（已抽离）：%s</div>' % esc(c['标题']))
    right.append('<div class="qbody">%s</div>' % render_blocks(c['块流']))
    if c['剥离账']:
        rows = ''.join('<tr><td>%s</td><td><code>%s</code></td><td>%s</td></tr>'
                       % (esc(l['类']), esc(l['原文']),
                          esc(json.dumps(l['值'], ensure_ascii=False)))
                       for l in c['剥离账'])
        right.append('<details class="led" open><summary>抽离账 %d 条（原文可回贴 ⇒ 守恒）</summary>'
                     '<table>%s</table></details>' % (len(c['剥离账']), rows))
    if lc:
        right.append('<div class="warn">低置信：%s</div>'
                     % esc('；'.join('%s=%s(%s)' % (x['项'], x['值'], x['置信']) for x in lc)))
    right.append('</div>')

gates_html = ''.join('<span class="gate %s">%s %s</span>'
                     % ('ok' if g['过'] else 'bad', '✅' if g['过'] else '❌', esc(g['闸']))
                     for g in stats['闸'])

CSS = """
*{box-sizing:border-box}body{margin:0;font:14px/1.75 "Microsoft YaHei",sans-serif;background:#f4f5f7;color:#1c1f23}
header{padding:10px 16px;background:#22272e;color:#e6edf3;position:sticky;top:0;z-index:9}
header h1{margin:0 0 6px;font-size:16px}
.gate{display:inline-block;margin:2px 6px 2px 0;padding:1px 8px;border-radius:10px;font-size:12px}
.gate.ok{background:#1a7f37;color:#fff}.gate.bad{background:#cf222e;color:#fff}
.wrap{display:flex;gap:10px;padding:10px;align-items:flex-start}
.pane{flex:1;min-width:0;background:#fff;border:1px solid #d8dee4;border-radius:6px}
.pane h2{margin:0;padding:8px 12px;font-size:14px;border-bottom:1px solid #eaeef2;background:#f6f8fa;position:sticky;top:56px}
.body{padding:10px 12px;max-height:calc(100vh - 120px);overflow:auto}
.src{padding:2px 0 2px 46px;position:relative;border-bottom:1px dashed #eee}
.pno{position:absolute;left:0;top:2px;color:#9aa4ae;font-size:11px}
.mk{display:inline-block;margin-right:6px;padding:0 6px;border-radius:3px;font-size:11px;color:#fff}
.mk-unit{background:#8250df}.mk-kp{background:#0969da}.mk-part{background:#6e7781}
.mk-explain{background:#bf8700}.mk-example{background:#1a7f37}.mk-practice{background:#cf222e}
.tb{margin:2px 0}.empty{color:#ccc}
.fg{margin:4px 0}.fg img{max-width:100%;border:1px solid #eee;background:#fff}
.miss{color:#cf222e}
.card{border:1px solid #d8dee4;border-radius:6px;margin:0 0 10px;padding:8px 10px;background:#fff}
.card.low{background:#fff8c5;border-color:#d4a72c}
.ch{font-size:13px;border-bottom:1px solid #eee;padding-bottom:4px;margin-bottom:6px}
.ch em{color:#0969da;font-style:normal}.ch small{color:#6e7781}
.pair{background:#ddf4ff;padding:0 5px;border-radius:3px}
.ttl{color:#8250df;font-size:12px}
.shell{color:#9aa4ae;font-size:12px}
.led{margin-top:6px;font-size:12px}.led table{border-collapse:collapse;width:100%}
.led td{border:1px solid #eee;padding:2px 5px;vertical-align:top}
.led code{background:#f6f8fa;padding:0 3px}
.warn{margin-top:6px;color:#9a6700;font-size:12px}
.tree{border:1px solid #d8dee4;border-radius:6px;padding:8px 10px;margin-bottom:10px;background:#fff}
.tree h3{margin:0 0 6px;font-size:13px}
.kp{margin-top:6px}.tq{padding-left:16px;font-size:12px;color:#57606a}
.tbl{white-space:pre-wrap;background:#f6f8fa;padding:4px}
"""

doc = """<!doctype html><meta charset="utf-8"><title>%s · 切割预览</title><style>%s</style>
<header><h1>教辅整书切割测试 · %s <small style="font-weight:400;opacity:.7">%s ｜ 纯确定性规则，未调用任何 LLM</small></h1>
<div>%s <span class="gate ok">题卡 %d</span> <span class="gate ok">考点 %d</span>
<span class="gate %s">低置信 %d</span></div></header>
<div class="wrap">
<div class="pane"><h2>左 · 原文档顺序连续预览（图在流内原位）</h2><div class="body">%s</div></div>
<div class="pane"><h2>右 · 归属树 + 题目卡 + 抽离账（黄底 = 低置信）</h2><div class="body">%s</div></div>
</div>""" % (esc(stats['单元']), CSS, esc(stats['单元']), esc(stats['原件']), gates_html,
             len(cards), len(tree['考点']),
             'bad' if stats['低置信题数'] else 'ok', stats['低置信题数'],
             ''.join(left), ''.join(right))
open(os.path.join(OUT, '预览.html'), 'w', encoding='utf-8').write(doc)
print('预览.html 写好', len(doc), 'B')

# ============================================================
# 二、导出还原：从块流渲染回打印件（题目卷，不带答案）
# ============================================================
PCSS = """
@page{size:A4;margin:16mm 14mm 14mm}
*{box-sizing:border-box}
body{margin:0;font:11.5pt/1.85 "SimSun","Songti SC",serif;color:#000}
h1{font:bold 17pt/1.5 "SimHei",sans-serif;text-align:center;margin:0 0 2mm}
.sub{text-align:center;font:10pt/1.5 "SimHei",sans-serif;color:#333;margin-bottom:5mm}
.kp{font:bold 13pt/1.8 "SimHei",sans-serif;margin:6mm 0 2mm;padding:1mm 2mm;
    border-left:4px solid #000;background:#f0f0f0;page-break-after:avoid}
.ex{font:bold 11.5pt/1.8 "SimHei",sans-serif;margin:3mm 0 1mm;page-break-after:avoid}
.pr{font:bold 11.5pt/1.8 "SimHei",sans-serif;margin:2.5mm 0 1mm;page-break-after:avoid}
.tip{border:1px dashed #888;padding:1.5mm 3mm;margin:1mm 0 3mm;font-size:10.5pt;background:#fafafa}
.tip b{font-family:"SimHei",sans-serif}
.q{margin-bottom:1mm}
.fg{page-break-inside:avoid}
.tb{margin:0.6mm 0;text-indent:0}
.sub-no{font-weight:bold}
.fg{margin:1.2mm 0;text-align:left}
.fg img{max-width:100%;height:auto}
.ans{height:14mm;border-bottom:0}
.shell{display:none}
.miss{color:#c00}
.foot{margin-top:6mm;font-size:9pt;color:#666;text-align:center;border-top:1px solid #ccc;padding-top:2mm}
"""

def render_q_print(c):
    """打印件的一道题：栏目前缀 + 标题 + 小问号 **原样回贴**（导出=抽离的逆运算）"""
    h = []
    lab = '【%s%s】' % (c['栏目'], c['栏目序号'] or '')
    cls = 'ex' if c['栏目'] == '典型例题' else 'pr'
    h.append('<div class="%s">%s%s</div>' % (cls, esc(lab), esc(c['标题'] or '')))
    # 小问号按记账顺序回贴到各行首
    subs = [l for l in c['剥离账'] if l['类'] == '小问号']
    si = 0
    parts = []
    for b in c['块流']:
        if b['type'] == 'text':
            if not b.get('text', '').strip():
                continue
            lines = b['text'].split('\n')
            outl = []
            for ln in lines:
                # 该行原来是否有小问号：按记账顺序消费（同段同序）
                if si < len(subs) and b.get('pidx') == subs[si]['para'] and ln.strip():
                    outl.append('<span class="sub-no">%s</span>%s'
                                % (esc(subs[si]['原文']), txt_html(ln)))
                    si += 1
                else:
                    outl.append(txt_html(ln))
            parts.append('<p class="tb">%s</p>' % '<br>'.join(outl))
        elif b['type'] == 'figure':
            d = b64(b.get('src') or '')
            w = min(max(b.get('w_px') or 220, 60), 430)
            parts.append('<figure class="fg"><img src="%s" style="width:%dpx"></figure>' % (d, w)
                         if d else '<div class="miss">[图丢失]</div>')
        elif b['type'] == 'table':
            parts.append('<div class="tb">%s</div>' % esc(b.get('flat_text') or ''))
    h.append('<div class="q">%s</div>' % ''.join(parts))
    return ''.join(h)

body = ['<h1>%s</h1>' % esc(tree['单元']),
        '<div class="sub">%s ｜ 题目卷（不含答案）｜ 由块流渲染还原</div>' % esc(tree['书'])]
by_qid = {c['qid']: c for c in cards}
for kp in tree['考点']:
    body.append('<div class="kp">【考点%s】%s</div>' % (esc(kp['序']), esc(kp['考点名'])))
    src_kp = next(k for k in tree['考点'] if k['para'] == kp['para'])
    tip = src_kp.get('方法点拨') or {}
    tipblocks = tip.get('块流') or []
    if tipblocks:
        body.append('<div class="tip"><b>【%s】</b>%s</div>'
                    % (esc(tip.get('标签') or '方法点拨'), render_blocks(tipblocks, maxw=380)))
    for q in kp['题']:
        body.append(render_q_print(by_qid[q['qid']]))
body.append('<div class="foot">导出还原件 · PRD-001 · 源：%s（段 %d-%d）· 题 %d 道 · 图 %d 张</div>'
            % (esc(stats['原件']), stats['段区间'][0], stats['段区间'][1],
               len(cards), sum(c['图数'] for c in cards)))

pdoc = ('<!doctype html><meta charset="utf-8"><title>%s 题目卷</title><style>%s</style>%s'
        % (esc(tree['单元']), PCSS, ''.join(body)))
open(os.path.join(OUT, '导出-题目卷.html'), 'w', encoding='utf-8').write(pdoc)
print('导出-题目卷.html 写好', len(pdoc), 'B')
