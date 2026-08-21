# -*- coding: utf-8 -*-
"""同步段题源模块（四上第五单元 平行四边形和梯形）—— 供课次生成器 import。

题源 = `平四梯形专项/u5_questions.json` ＋ `figs/`（71 张题图，本地零网络依赖）。
本模块只做三件事：① 按板块挑题（手工索引）② 把 block_json 渲成 HTML ③ 避重断言。

挑题三条口径（2026-08-02 用户拍板「题量太多、简单的去掉」）：
  ① 砍同质简单题（考点七的伸缩门/晾衣架/推拉门/折叠椅四题同模，整组不要）
  ② 避开第 7 课已用过的 10 题（USED_L7）
  ③ 避开与同课奥数段同质的（和差/和倍/靠墙那几道），留原书里最有教学价值的
"""
import html
import json
import os
import re

SRC = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\平四梯形专项'
_DATA = json.load(open(os.path.join(SRC, 'u5_questions.json'), encoding='utf-8'))
KP, ITEMS, IMG_MAP = _DATA['kp'], _DATA['items'], _DATA['img']

# 板块 = (标题, 知识点切片, [(考点, 原索引列表)])
# 知识点切片＝打卡册《四上平四梯形单元过关》D3–D10 的「学习点拨」原文，跟着板块标题走
BLOCKS = [
    ('垂线的应用',
     '<b>垂线段最短</b>：从直线外一点到这条直线，垂线段最短——取水、接水管、修路都是作垂线。'
     '<br><b>不是连端点</b>：两点之间连线段，只在「两点都给出」时才用。'
     '<br><b>平行线间最大的正方形</b>：边长＝两平行线之间的距离，先作垂线量出来。',
     [('四', [2]), ('十二', [3])]),

    ('画长方形正方形 · 认识平四和梯形',
     '<b>画指定长宽</b>：先画一条边，再用三角尺过端点作两条垂线；注意<b>单位换算</b>（10 毫米＝1 厘米）。'
     '<br><b>平行四边形</b>：两组对边分别平行；<b>梯形</b>：只有一组对边平行。'
     '<br><b>梯形各部分</b>：平行的两条边是上底和下底，不平行的两条边是腰。平四容易变形（不稳定性）。',
     [('五', [2]), ('六', [2])]),

    ('梯形的分类与数图形',
     '<b>直角梯形</b>：有一个角是直角；<b>等腰梯形</b>：两条腰相等，同一底上的两个角也相等。'
     '<br><b>四边形内角和</b>是 360°。'
     '<br><b>数图形</b>：按大小分类数——先数单个的，再数两个拼的、三个拼的，做到不重不漏。',
     [('八', [1, 3]), ('十三', [2])]),

    ('找高与作高',
     '<b>高</b>＝从一条边上任一点向<b>对边</b>作的垂线段，垂足所在的那条边才是底。'
     '<br>🔴 <b>斜着的边不是高</b>——图上给的斜边数据是来骗人的，这是本单元最大的丢分点。'
     '<br>平四有<b>无数条高</b>，不同的底对应不同的高；梯形的高＝两底之间的距离。画高用<b>虚线</b>＋直角符号。',
     [('九', [2, 3, 7])]),

    ('画图与裁剪',
     '<b>方格纸上画</b>：先定一组平行边（数格子保证平行），再连另外两条边；画高别忘了标直角。'
     '<br><b>平四剪成两个梯形</b>：剪的线要<b>与一组对边平行</b>。'
     '<br><b>梯形剪成平四＋三角形</b>：从上底的端点向下底作<b>与腰平行</b>的线。',
     [('十', [2]), ('十一', [3])]),

    ('平行四边形的周长与反求',
     '<b>周长</b>＝(邻边和)×2，只用两条相邻的边，别把四条边都当成不同的。'
     '<br><b>反求邻边</b>＝周长÷2－已知边——「<b>周长的一半</b>」是这类题的钥匙。'
     '<br><b>易错</b>：「比它短 3 米」「比它长 6 米」要先算出邻边，再代进周长公式。',
     [('十四', [1, 6, 4, 9])]),

    ('梯形的周长与反求',
     '<b>梯形周长</b>＝上底＋下底＋两腰；等腰梯形＝上底＋下底＋腰×2。'
     '<br><b>反求腰</b>＝(周长－上底－下底)÷2。'
     '<br><b>靠墙只围三面</b>：少围的是靠墙那条边；要最省，就让<b>最长的边靠墙</b>。',
     [('十六', [4, 5, 10, 11])]),

    ('变化问题 · 综合过关',
     '<b>拉伸</b>：长方形框拉成平行四边形，边没变所以<b>周长不变</b>，但面积变小了。'
     '<br><b>拼接</b>：两个完全一样的梯形一定能拼成平行四边形；<b>拼合处的边消失了，周长不是两倍</b>。'
     '<br><b>底边变化</b>：上底延长后变成平四或长方形，<b>延长的长度＝下底－上底</b>。',
     [('十五', [1]), ('十七', [1, 3]), ('十八', [1])]),
]

USED_L7 = {  # 🔴 第 7 课同步卷 184 已用掉的 10 题，绝不重复
    '2077049964126547970', '2077049965619720194', '2077049982434684929',
    '2077050001648791554', '2077050002739310594', '2077050003653668865',
    '2077050006962974721', '2077050008460341249', '2077050005859872769',
    '2077050014646939649',
}


def demath(t):
    """行内 LaTeX（$ABCD$ / $126$ / $\\angle ABC$ / $135^\\circ$）→ 干净 HTML。
    🔴 不处理会在卷面上裸露美元符号（实测讲义题面里有）。"""
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


FIG_DST = None      # 设了它 → 题图复制到该目录并用相对路径


def use_local_figs(dst):
    """🔴 把题图复制进课次自己的 figs/ 并改用相对路径。
    不这么做就得引 file:/// 绝对路径，而**浏览器默认禁止 file 页面加载其他 file 资源**，
    直接打开 HTML 会整片图裂掉、看着像文字被截断（实测踩过）。"""
    global FIG_DST
    FIG_DST = dst
    os.makedirs(dst, exist_ok=True)


def _img_src(rel):
    if FIG_DST:
        import shutil
        name = os.path.basename(rel)
        dst = os.path.join(FIG_DST, name)
        if not os.path.exists(dst):
            shutil.copy(os.path.join(SRC, rel), dst)
        return f'figs/{name}'
    return 'file:///' + os.path.join(SRC, rel).replace('\\', '/')


def render_stem(bj):
    out = []
    try:
        obj = json.loads(bj) if isinstance(bj, str) else (bj or {})
    except Exception:
        return ''
    for row in obj.get('rows', []):
        for cell in row.get('cells', []):
            if cell.get('type') == 'image':
                rel = IMG_MAP.get(cell.get('url', ''))
                src = _img_src(rel) if rel else cell.get('url', '')
                w = cell.get('width') or 40
                out.append(f'<div class="fig"><img src="{src}" style="width:{min(int(w) * 1.15, 82)}%"></div>')
                if cell.get('caption'):
                    out.append(f'<div class="cap">{esc(cell["caption"])}</div>')
            else:
                md = cell.get('md') or cell.get('text') or ''
                out.append(esc(re.sub(r'!\[\]\(([^)]+)\)', '', md)))
    return ''.join(out)


def field(item, *names):
    for n in names:
        if item.get(n) not in (None, ''):
            return item[n]
    return ''


def selection():
    """→ [(板块名, 知识点切片, [qid...])]；撞第 7 课用题或本卷内重复 → 直接 AssertionError。"""
    res, seen = [], set()
    for name, learn, groups in BLOCKS:
        ids = []
        for kpno, idxs in groups:
            key = next(k for k in KP if k.startswith(f'【考点{kpno}】'))
            src = KP[key]
            for i in idxs:
                qid = src[i]
                assert qid not in USED_L7, f'撞第7课已用题：考点{kpno}[{i}] {qid}'
                assert qid not in seen, f'本卷内重复：考点{kpno}[{i}] {qid}'
                seen.add(qid)
                ids.append(qid)
        res.append((name, learn, ids))
    return res


SEL = selection()
TOTAL = sum(len(v) for _, _, v in SEL)


def emit(h, ans, start_no=0):
    """把同步段渲进 h（HTML 片段列表）：板块标题 → 知识点切片 → 题目。返回结束题号。"""
    n = start_no
    for name, learn, ids in SEL:
        h.append(f'<div class="blk">{name}</div>')
        if learn:
            h.append(f'<div class="learn">{learn}</div>')
        for qid in ids:
            n += 1
            it = ITEMS.get(str(qid))
            if not it:
                h.append(f'<div class="q"><span class="no">{n}．</span>[题 {qid} 缺失]</div>')
                continue
            body = render_stem(field(it, 'blockJson', 'block_json')) or esc(field(it, 'stemText', 'stem_text'))
            h.append(f'<div class="q"><span class="no">{n}．</span>{body}</div>')
            if ans:
                a, z = esc(field(it, 'answer')), esc(field(it, 'analyze'))
                p = f'<p><span class="lab">【答案】</span>{a}</p>'
                if z:
                    p += f'<p><span class="lab">【解析】</span>{z}</p>'
                h.append(f'<div class="ansbox">{p}</div>')
            else:
                qt = field(it, 'questionType', 'question_type')
                h.append(f'<div class="{"sp" if qt in (5, 6, 3) else "spm"}"></div>')
    return n
