# -*- coding: utf-8 -*-
"""第11课 平行四边形和梯形 × 条形统计图
  一 · 思维题：小棒摆梯形阵（梯形 × 等差数列，三关）
  二 · 同步：第五单元 16 题（按用户点名的 6 个考点取，题源 = 本地 u5_questions.json）
  三 · 条形统计图：第六单元「从后往前」4 题（考点七·统计图表综合应用全组，原书裁图）

🔴 取题避重：第 7 课 10 题 / 第 10 课 24 题都已登记，命中即报错（考点十三是用户点名要 4 个＝全量，
   其中 1 道第 10 课练过，按二刷放行并在卷面标注）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pegboard as pb
import u5_pick as U
from paper_css import PRINT_CSS

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第11课-平四梯形与统计图'
FIG = os.path.join(OUT, 'figs')
os.makedirs(FIG, exist_ok=True)
U.use_local_figs(FIG)          # 🔴 题图复制进本课 figs/ 并用相对路径，HTML 直接打开也能看图

# ── 思维题配图：关1 的小棒阵（题目卷只给阵形，答案卷才画梯形轮廓＋标注）──
_c1 = list(range(3, 11))                      # 3,4,…,10 共 8 行
pb.draw_stick_rows(_c1).save(os.path.join(FIG, 'sw_rows.png'))
pb.draw_stick_rows(_c1, outline=True, label=True).save(os.path.join(FIG, 'sw_rows_marked.png'))

# ── 第 10 课已用掉的 24 题（避重用；命中要显式放行）──
USED_L10 = {(k, i) for k, idxs in {
    '四': [2], '十二': [3], '五': [2], '六': [2], '八': [1, 3], '十三': [2],
    '九': [2, 3, 7], '十': [2], '十一': [3], '十四': [1, 6, 4, 9],
    '十六': [4, 5, 10, 11], '十五': [1], '十七': [1, 3], '十八': [1],
}.items() for i in idxs}

# ── 一 · 同步：6 个板块 16 题（用户点名）──
SYNC = [
    ('裁剪平行四边形和梯形', '考点十一',
     '<b>平四剪成两个梯形</b>：剪的线要<b>与一组对边平行</b>。'
     '<br><b>梯形剪成平四＋三角形</b>：从上底的端点向下底作<b>与腰平行</b>的线。'
     '<br><b>剪成两个三角形</b>：沿对角线剪。画完记得标出平行或直角记号。',
     [('十一', [0, 1, 2])]),

    ('数平行四边形和梯形', '考点十三',
     '<b>按大小分类数</b>：先数 1 个基本图形的，再数 2 个拼起来的、3 个拼起来的，做到不重不漏。'
     '<br><b>平行线之间</b>：先看清有几组平行边——只有一组平行的是梯形，两组都平行的是平行四边形。',
     [('十三', [0, 1, 2, 3])]),

    ('平行四边形的周长及反求（难）', '考点十四',
     '<b>周长</b>＝(邻边和)×2；<b>反求邻边</b>＝周长÷2－已知边——「<b>周长的一半</b>」是钥匙。'
     '<br><b>易错</b>：「比它长 6 厘米」要先算出邻边，再代进周长公式，别拿原来那条边直接乘。',
     [('十四', [7, 10])]),

    ('梯形的周长及反求', '考点十六',
     '<b>梯形周长</b>＝上底＋下底＋两腰；等腰梯形＝上底＋下底＋腰×2。'
     '<br><b>反求腰</b>＝(周长－上底－下底)÷2。'
     '<br><b>靠墙只围三面</b>：少围的就是靠墙那条边，先看清图上哪条边贴着墙。',
     [('十六', [0, 3, 9])]),

    ('梯形的拼接问题', '考点十七',
     '两个<b>完全一样</b>的梯形一定能拼成一个平行四边形；两个完全一样的直角梯形还能拼成长方形。'
     '<br>🔴 <b>拼合处的两条边藏到里面去了</b>——拼成的图形周长<b>不是</b>两个梯形周长之和。',
     [('十七', [0, 4])]),

    ('梯形底边的变化问题', '考点十八',
     '上底<b>延长</b>后变成平行四边形（或长方形、正方形），说明：'
     '<br><b>延长的那一段长度 ＝ 下底 － 上底</b>。抓住这句话，题目就从「变化」回到「求边长」。',
     [('十八', [0, 3])]),
]

# ── 二 · 条形统计图：原书裁图 4 题 ──
U6 = [
    dict(d=3, fig='figs/u6_q1.png', h=104,
         answer='（1）<b>5</b> 万人次　（2）<b>1</b> 日，多 <b>6</b> 万人次　（3）开放题，言之有据即可',
         analyze='（1）竖轴从 0 到 25 一共 5 格，25÷5＝<b>5</b>（万人次/格）——'
                 '<b>画图之前必须先把「每格代表几」定下来</b>。<br>'
                 '（2）逐日比：1 日 21＞15（太原多 6）、2 日 15＜16、3 日 15＜20、4 日 14＜25。'
                 '只有 <b>1 日</b>太原比洛阳多，多 21－15＝<b>6</b>（万人次）。<br>'
                 '（3）参考答案：洛阳这 4 天<b>一直在涨</b>（15→16→20→25），太原<b>一直在跌</b>（21→15→15→14）；'
                 '4 天合计洛阳 76＞太原 65。'),
    dict(d=3, fig='figs/u6_q2.png', h=132,
         answer='①<b>黄豆</b>　②<b>碳水化合物</b>　③建议多吃<b>黄豆</b>制品',
         analyze='①蛋白质：黄豆 350＞花生 270 → <b>黄豆</b>高。<br>'
                 '②1 千克花生里：蛋白质 270、脂肪 410、碳水化合物 230 → 最低的是 <b>碳水化合物</b>。<br>'
                 '③花生脂肪 410 克，是黄豆 200 克的两倍多；身材肥胖要控制脂肪，所以建议多吃<b>黄豆</b>制品。'
                 '<br>🔴 这一问要<b>先找出该看哪一栏</b>（肥胖↔脂肪），再比数据——这是统计题的核心能力。'),
    dict(d=3, fig='figs/u6_q3.png', h=98,
         answer='（1）补画美食节：男生 12、女生 32　（2）开放题',
         analyze='（1）表里 4 组数据，统计图上美食节两根直条还空着：男生画到 <b>12</b>、女生画到 <b>32</b>；'
                 '直条<b>宽度要和前面一样、间隔也一样</b>，画完在直条上方标数。<br>'
                 '（2）参考：「女生比男生多多少人？」女生 31＋30＋14＋32＝107，男生 28＋16＋28＋12＝84，'
                 '女生比男生多 107－84＝23（人）。'),
    dict(d=4, fig='figs/u6_q4.png', h=118,
         answer='（2）<b>50</b> 人　（3）<b>坐位体前屈</b>　（4）<b>仰卧起坐</b>　（5）开放题',
         analyze='（2）50m 跑<b>全部达标</b>，所以全班人数＝这一项的男生＋女生＝25＋25＝<b>50</b>（人）。'
                 '🔴 这一问是全卷最难的一步：题目没直接给班级人数，要<b>借「全部达标」这句话</b>把某一项的达标人数'
                 '当成全班人数。<br>'
                 '（3）逐项算差：50m 跑 0、跳绳 23－19＝4、坐位体前屈 20－15＝<b>5</b>、仰卧起坐 14－11＝3 '
                 '→ 差距最大是 <b>坐位体前屈</b>。<br>'
                 '（4）看达标总人数：50m 50、跳绳 42、坐位体前屈 35、仰卧起坐 25 → 最少的是 <b>仰卧起坐</b>，'
                 '最需要加强。<br>'
                 '（5）参考：坐位体前屈男生只有 15 人达标，不到全班的一半。'),
]

# ── 思维题：收电池 · 移多补少三关（验算＝_验算/l11_siwei_verify.py，ALL PASS）──
# 🔴 题目卷不留任何提示，关名也不泄底；巧法与坑全写在答案卷解析里
SIWEI = [
    dict(d=2, stem="<b>第 1 关</b>：用同样长的小棒摆图形。第 1 行摆 <b>3</b> 根，"
                   "往下每一行都比上一行<b>多 1 根</b>，一共摆了 <b>8</b> 行（如图）。"
                   "这一堆小棒一共有多少根？",
         fig='<div class="fig"><img src="figs/sw_rows.png" style="height:44mm"></div>',
         ansfig='<div class="fig"><img src="figs/sw_rows_marked.png" style="height:46mm"></div>',
         answer="52 根",
         analyze="先找出最后一行：从 3 开始，往下加了 7 次 1，所以第 8 行是 3＋7＝<b>10</b>（根）。"
                 "<br>再求总数：(3＋10)×8÷2＝<b>52</b>（根）。"
                 "<br>🔴 <b>再看一眼这堆小棒的样子</b>：上面一行短、下面一行长，两边斜着下去——"
                 "把它的外框描出来（见右图虚线），正好是一个<b>梯形</b>！<br>"
                 "再把两个公式并排放：<br>"
                 "　　等差数列求和 ＝ (<b>首项</b>＋<b>末项</b>) × <b>项数</b> ÷ 2<br>"
                 "　　梯 形 面 积 ＝ (<b>上底</b>＋<b>下底</b>) × <b>高</b> ÷ 2<br>"
                 "<b>长得一模一样</b>——第一行就是上底、最后一行就是下底、行数就是高。"
                 "所以这两个公式<b>本来就是同一个道理</b>，记住一个就等于记住两个。"),
    dict(d=3, stem="<b>第 2 关</b>：另一堆小棒也这样摆：最上面一行 <b>5</b> 根，"
                   "最下面一行 <b>21</b> 根，每一行都比上一行<b>多 2 根</b>。"
                   "（1）这一堆一共摆了多少行？（2）一共用了多少根小棒？",
         answer="（1）9 行　（2）117 根",
         analyze="（1）🔴 <b>坑在这里</b>：从 5 加到 21 一共多了 21－5＝16（根），"
                 "每次多 2 根，所以<b>加了</b> 16÷2＝8（次）。"
                 "但「加了 8 次」不等于「8 行」——第一行是不用加就有的，"
                 "所以行数 ＝ 8＋1＝<b>9</b>（行）。<b>漏掉这个 ＋1，答案就全错。</b>"
                 "<br>回头验一验：5、7、9、11、13、15、17、19、21，数一数正好 9 个 ✓"
                 "<br>（2）用上一关的钥匙——上底 5、下底 21、高 9："
                 "(5＋21)×9÷2＝26×9÷2＝<b>117</b>（根）。"),
    dict(d=4, stem="<b>第 3 关</b>：小明也这样摆了一堆：最上面一行 <b>4</b> 根，"
                   "每一行都比上一行<b>多 3 根</b>，最后<b>正好用完 175 根</b>小棒。"
                   "（1）他摆了多少行？（2）最下面一行有多少根？",
         answer="（1）10 行　（2）31 根",
         analyze="这一关是<b>倒过来问</b>：前两关是给了行数求总数，这一关是给了总数求行数。"
                 "<br><b>办法：从「平均每行」下手试算。</b>把这堆看成梯形，"
                 "(首行＋末行)÷2 就是「中间那一行」的根数，也就是<b>平均每行多少根</b>；"
                 "再用总数除以它，就该等于行数。"
                 "<br>试 8 行：末行 4＋3×7＝25，总数 (4＋25)×8÷2＝116，<b>少了</b>；"
                 "<br>试 10 行：末行 4＋3×9＝<b>31</b>，总数 (4＋31)×10÷2＝<b>175</b>，<b>正好</b> ✓"
                 "<br>（再往上试 11 行是 209，已经超了，所以只有 10 行这一种摆法。）"
                 "<br>🔴 <b>倒着问的题，就正着试</b>——从一个大概的行数开始算，"
                 "偏小就往上调、偏大就往下调，两三次就能卡住。"),
    dict(d=4, stem="<b>第 4 关</b>：今年是 <b>2026</b> 年。小明想摆一个 <b>2026 行</b>的梯形阵："
                   "第 1 行 1 根，第 2 行 2 根，第 3 行 3 根……一直到第 2026 行 2026 根。"
                   "（1）把第 1 行和第 2026 行凑成一对，第 2 行和第 2025 行凑成一对，"
                   "这样一直凑下去——<b>每一对</b>是多少根？一共能凑成多少对？"
                   "（2）这一堆小棒<b>一共</b>有多少根？",
         answer="（1）每对都是 2027 根，一共 1013 对　（2）2 053 351 根",
         analyze="行数太多，一行一行加是加不完的，得用<b>凑对</b>的办法。"
                 "<br>（1）第 1 行＋第 2026 行＝1＋2026＝<b>2027</b>；第 2 行＋第 2025 行＝2＋2025＝<b>2027</b>；"
                 "第 3 行＋第 2024 行＝3＋2024＝<b>2027</b>……"
                 "<br>🔴 <b>为什么每一对都一样？</b>因为往里走一对，前面那个<b>加 1</b>、后面那个正好<b>减 1</b>，"
                 "一加一减抵消了，和当然不变。"
                 "<br>2026 行是<b>双数</b>，正好两两凑完、不剩单的：2026÷2＝<b>1013</b>（对）。"
                 "<br>（2）总数＝2027×1013。这个乘法拆开算："
                 "<br>　　2027×1013 ＝ 2027×1000 ＋ 2027×13"
                 "<br>　　　　　　　＝ 2 027 000 ＋ 26 351 ＝ <b>2 053 351</b>（根）"
                 "<br>　　（其中 2027×13＝2027×10＋2027×3＝20 270＋6 081＝26 351）"
                 "<br>🔴 <b>回到梯形再看一眼</b>：上底 1、下底 2026、高 2026，"
                 "(1＋2026)×2026÷2＝2027×1013——<b>跟凑对算出来的一模一样</b>。"
                 "凑对法和梯形公式，本来就是同一件事的两种说法。"),
]

U6_LEARN = ('<b>复式条形统计图</b>：两组数据用两种颜色（或底纹）的直条<b>并排</b>画，🔴 必须标<b>图例</b>；'
            '直条宽度一致、间隔相同，画完在上方标数。'
            '<br><b>动笔前先定「每格代表几」</b>：看最大的那个数据，格数够用又不浪费。'
            '<br><b>读图三步</b>：① 先看图例 → ② 再看竖轴每格代表几 → ③ 最后才比高低。')

# 🔴 统计图裁图占版面大：宽度按 U6_W% 排，直接决定分页。76 → 题目卷统计图段 2 页
U6_W = 66

CSS = PRINT_CSS + """
/* 🔴 统计图题：题号＋原书裁图必须绑成一个不可拆块，否则分页会把题号和图分到两页 */
.u6item { page-break-inside:avoid; margin:0 0 2.5mm; }
.u6item .q { margin:0 0 0.8mm; font-size:10.5pt; }
.u6item .fig { margin:0; }
"""


def pick():
    """→ [(板块名, 考点号, 知识点切片, [qid...])]，带避重检查。"""
    res, reused = [], []
    for name, kpname, learn, groups in SYNC:
        ids = []
        for kpno, idxs in groups:
            key = next(k for k in U.KP if k.startswith(f'【考点{kpno}】'))
            src = U.KP[key]
            for i in idxs:
                qid = src[i]
                assert qid not in U.USED_L7, f'撞第7课已用题：考点{kpno}[{i}]'
                if (kpno, i) in USED_L10:
                    reused.append(f'考点{kpno}[{i}]')
                ids.append(qid)
        res.append((name, kpname, learn, ids))
    return res, reused


SEL, REUSED = pick()
TOTAL = sum(len(v) for _, _, _, v in SEL)


def build(ans):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>第11课</title>'
         f'<style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>第11课 · 平行四边形和梯形 · 条形统计图</h1>')
    h.append(f'<div class="sub">四年级上册 第五单元 ＋ 第六单元'
             f'{"　教师用 · 含答案解析" if ans else ""}</div>')

    # ── 一 · 思维题 ──
    h.append('<div class="sec">一 · 思维题</div><div class="big">')
    for i, q in enumerate(SIWEI, 1):
        h.append(f'<div class="q"><span class="no">{i}．</span>'
                 f'<span class="star">{"★" * q["d"]}</span>{q["stem"]}</div>')
        if q.get('fig'):
            h.append(q['fig'])
        if ans:
            if q.get('ansfig'):
                h.append(q['ansfig'])
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}</p>'
                     f'<p><span class="lab">【解析】</span>{q["analyze"]}</p></div>')
        else:
            h.append('<div class="sp"></div>')
    h.append('</div>')

    h.append('<div class="sec newpage">二 · 同步 · 平行四边形和梯形</div><div class="tight">')
    n = 0
    for name, kpname, learn, ids in SEL:
        h.append(f'<div class="blk">{name}<span class="tip">　{kpname}</span></div>')
        h.append(f'<div class="learn">{learn}</div>')
        for qid in ids:
            n += 1
            it = U.ITEMS.get(str(qid))
            body = U.render_stem(U.field(it, 'blockJson', 'block_json')) or U.esc(
                U.field(it, 'stemText', 'stem_text'))
            h.append(f'<div class="q"><span class="no">{n}．</span>{body}</div>')
            if ans:
                a, z = U.esc(U.field(it, 'answer')), U.esc(U.field(it, 'analyze'))
                p = f'<p><span class="lab">【答案】</span>{a}</p>'
                if z:
                    p += f'<p><span class="lab">【解析】</span>{z}</p>'
                h.append(f'<div class="ansbox">{p}</div>')
            else:
                qt = U.field(it, 'questionType', 'question_type')
                h.append(f'<div class="{"sp" if qt in (5, 6, 3) else "spm"}"></div>')
    h.append('</div>')

    h.append('<div class="sec newpage">三 · 条形统计图</div>')
    h.append(f'<div class="learn">{U6_LEARN}</div><div class="tight">')
    for i, q in enumerate(U6, 1):
        h.append(f'<div class="u6item"><div class="q"><span class="no">{i}．</span>'
                 f'<span class="star">{"★" * q["d"]}</span></div>'
                 f'<div class="fig"><img src="{q["fig"]}" style="width:{U6_W}%"></div></div>')
        if ans:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}</p>'
                     f'<p><span class="lab">【解析】</span>{q["analyze"]}</p></div>')
    h.append('</div></div></body></html>')
    return '\n'.join(h)


for suffix, flag in (('题目卷', False), ('答案卷', True)):
    with open(os.path.join(OUT, f'第11课·平四梯形与统计图·{suffix}.html'), 'w', encoding='utf-8') as f:
        f.write(build(flag))
print(f'HTML done | 同步 {TOTAL} 题 ＋ 统计图 {len(U6)} 题'
      + (f' | ⚠️ 与第10课重复（二刷）：{", ".join(REUSED)}' if REUSED else ''))
