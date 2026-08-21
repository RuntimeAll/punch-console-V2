# -*- coding: utf-8 -*-
"""七月小测·综合测试卷 v2（40分钟·100分·22题）：正规试卷版式＋数字谜竖式化"""
import os

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第8课-七月小测-20260726'
os.makedirs(OUT, exist_ok=True)

def vt(rows):
    """竖式表格：rows=[(op, '6?37'), 'HR', ...]，'?'渲染成□方格，其余原样；列右对齐"""
    width = max(len(r[1]) for r in rows if r != 'HR')
    h = ['<table class="vt2"><tbody>']
    for r in rows:
        if r == 'HR':
            h.append(f'<tr><td class="op"></td>{"".join(f"<td class=hr></td>" for _ in range(width))}</tr>')
            continue
        op, digits = r
        pad = width - len(digits)
        cells = ['<td></td>'] * pad
        for ch in digits:
            cells.append('<td class="bx">&nbsp;</td>' if ch == '?' else f'<td>{ch}</td>')
        h.append(f'<tr><td class="op">{op}</td>{"".join(cells)}</tr>')
    h.append('</tbody></table>')
    return ''.join(h)

MI1A = vt([('', '6?37'), ('＋', '3??'), 'HR', ('', '7183')])
MI1B = vt([('', '?0??'), ('－', '1?49'), 'HR', ('', '3079')])
MI2A = vt([('', '同学们'), ('×', '好'), 'HR', ('', '1257')])
MI2B = vt([('', '春夏秋冬'), ('×', '4'), 'HR', ('', '冬秋夏春')])

TIANKONG = [
    dict(stem="116°的角比平角小（　　）°，比直角大（　　）°。",
         answer="64；26", analyze="180°－116°＝64°；116°－90°＝26°。"),
    dict(stem="一列火车长 300 米，以每分钟 600 米的速度通过一座长 900 米的隧道，需要（　　）分钟。",
         answer="2", analyze="总路程＝车长＋隧道长＝1200 米，1200÷600＝2（分钟）。"),
    dict(stem="规定 [x] 表示取数 x 十位上的数字，例如 [37]＝3；|y| 表示取数 y 百位上的数字，例如 |628|＝6。若 x＝423，y＝1518，则 3[x]＋2|y|＝（　　）。",
         answer="16", analyze="[423]＝2（十位），|1518|＝5（百位），3×2＋2×5＝6＋10＝16。"),
    dict(stem="有一个等差数列：4，10，16，22，…，580。这个等差数列共有（　　）项。",
         answer="97 项", analyze="公差＝6，项数＝(580－4)÷6＋1＝96＋1＝97（项）。坑：别忘＋1。"),
    dict(stem="2028 年 6 月 1 日是星期四，那么 2028 年 7 月 1 日是星期（　　），8 月 1 日是星期（　　）。",
         answer="六；二", analyze="6 月 30 天，30÷7 余 2，星期四往后 2 天＝星期六；7 月 31 天，31÷7 余 3，再往后 3 天＝星期二。"),
    dict(stem="珊珊把一些花按“2 朵红花，4 朵黄花，3 朵紫花”的顺序排列。那么第 38 朵花是（　　）色，前 38 朵花中有（　　）朵黄花。",
         answer="红；16", analyze="周期 9 朵，38÷9＝4……2，余下第 2 朵还在红花段；黄花＝4×4＝16（朵），余下 2 朵都是红花。"),
    dict(stem="一个平行四边形的周长是 36 厘米，其中一条边的长度是 12 厘米，与它相邻的另一条边的长度是（　　）厘米。",
         answer="6", analyze="36÷2－12＝6（厘米）。"),
    dict(stem="甲、乙两数相乘，豆豆错把甲数个位上的 9 看成 6、十位上的 6 看成 9，使得计算结果多了 1296。乙数是（　　）。",
         answer="48", analyze="看错后甲数变化＝96－69＝27（其余数位不变），多算的＝27×乙＝1296，乙＝1296÷27＝48。"),
]

XUANZE = [
    dict(stem="一个乘法算式的积是 40，一个因数不变，另一个因数乘 12，现在的积是（　　）。",
         opts=["52", "480", "400", "120"],
         answer="B", analyze="一个因数不变，另一个因数乘 12，积也乘 12：40×12＝480。"),
    dict(stem="有一列数：1，4，2，8，5，7，1，4，2，8，5，7，…这列数的第 80 个数是（　　）。",
         opts=["1", "2", "4", "8"],
         answer="C", analyze="周期 6，80÷6＝13……2，与周期第 2 个相同，是 4。"),
    dict(stem="定义新运算：a▼b＝20×(a＋b)－19×(a－b)。那么 20▼19＝（　　）。",
         opts=["761", "741", "780", "799"],
         answer="A", analyze="20×39－19×1＝780－19＝761。"),
    dict(stem="环形跑道长 600 米，甲每分钟跑 140 米，乙每分钟跑 110 米，两人同时同地同向出发，甲第一次追上乙需要（　　）分钟。",
         opts=["20", "12", "30", "60"],
         answer="A", analyze="环形同向追上一次＝多跑一整圈：600÷(140－110)＝20（分钟）。"),
]

JISUAN = [
    dict(stem="<div class='exprs' style='margin-left:0'>602×14＋218<span></span>9860－236×38</div>",
         answer="8646；892", analyze="602×14＝8428，8428＋218＝8646；236×38＝8968，9860－8968＝892。", sp=12),
    dict(stem="计算：1＋2＋3＋…＋2023＋2024",
         answer="2049300", analyze="首尾配对：(1＋2024)×2024÷2＝2025×1012＝2049300。", sp=13),
    dict(stem="计算：(1＋3＋5＋…＋2025)－(2＋4＋6＋…＋2024)",
         answer="1013", analyze="错位配对：1＋(3－2)＋(5－4)＋…＋(2025－2024)＝1＋1012 个 1＝1013。硬算也行：奇数和 1013×1013，偶数和 1012×1013，差＝1013。", sp=13),
]

SHUZIMI = [
    dict(stem="在下列算式的 □ 里填上合适的数字。<br><div class='mirow'>" + MI1A + MI1B + "</div>",
         answer="6837＋346＝7183；5028－1949＝3079",
         analyze="加法：加数 3□□ 在 300～399 之间，被加数百位只能是 8，7183－6837＝346。减法：被减数＝3079＋1□49，只有 3079＋1949＝5028 的百位是 0，符合 □0□□。", sp=3),
    dict(stem="下列算式中的汉字分别代表什么数字？（相同的汉字代表相同的数字，不同的汉字代表不同的数字）<br><div class='mirow'>" + MI2A + MI2B + "</div>",
         answer="左：同＝4，学＝1，们＝9，好＝3（419×3＝1257）；右：春＝2，夏＝1，秋＝7，冬＝8（2178×4＝8712）",
         analyze="左：用整除特征逐个排除乘数——1257 是奇数排除 2/4/6/8，末位 7 排除 5，数字和 15 能被 3 不能被 9 故排除 9 保留 3，再试 7 不整除，所以乘数只能是 3，1257÷3＝419（唯一解）。右：四位数×4 仍是四位数→千位×4＜10，千位只能是 1 或 2；若千位是 1，积的末位（即原数千位）也是 1，但 4 的倍数末位必为偶数或 0，矛盾→千位是 2，再由进位定个位是 8，逐位推得 2178×4＝8712（唯一解）。", sp=4),
]

YINGYONG = [
    dict(stem="某商店洗手液原价每瓶 15 元，现在进行促销，买 4 瓶送一瓶。学校想要采购 120 瓶洗手液，实际每瓶比原价便宜了多少钱？",
         answer="3 元", analyze="每 5 瓶只付 4 瓶的钱：120÷5＝24（组），实付 24×4×15＝1440（元），每瓶 1440÷120＝12（元），便宜 15－12＝3（元）。", sp=9),
    dict(stem="一辆汽车从静止开始加速，第 1 分钟行 300 米，以后每分钟都比前一分钟多行 20 米。<br>（1）第 10 分钟行多少米？<br>（2）前 10 分钟一共行了多少米？<br>（3）照这样加速，1 小时一共能行多少米？",
         answer="（1）480 米　（2）3900 米　（3）53400 米（合 53.4 千米）", analyze="每分钟行的路程组成公差 20 的等差数列。（1）第 10 分钟＝300＋20×(10－1)＝480（米）。（2）前 10 分钟＝(300＋480)×10÷2＝3900（米）。（3）1 小时＝60 分钟，第 60 分钟＝300＋20×59＝1480（米），总路程＝(300＋1480)×60÷2＝1780×30＝53400（米），合 53.4 千米——先算末项再求和，项数从 10 拉到 60 是本题的加深处。", sp=13),
    dict(stem="小明每分钟走 80 米，小刚每分钟走 70 米，两人从两地相向而行，第二次相遇时共走了 3600 米。两地相距多少米？",
         answer="1200 米", analyze="第二次相遇两人共走 3 个全程：3600÷3＝1200（米）。", sp=9),
    dict(stem="一串彩灯按红、黄、蓝、绿的顺序循环排列。第 1 盏灯亮 1 秒，第 2 盏灯亮 2 秒，第 3 盏灯亮 3 秒，……第 n 盏灯亮 n 秒。前 40 盏灯里，蓝灯一共亮了多少秒？",
         answer="210 秒", analyze="周期是 4，蓝灯在第 3、7、11、…、39 盏——公差 4 的等差数列，项数＝(39－3)÷4＋1＝10（盏）。总秒数＝3＋7＋…＋39＝(3＋39)×10÷2＝210（秒）。周期定位＋等差求和两步融合。", sp=8),
]

YAZHOU = [
    dict(stem="把自然数 1，2，3，…按每行 7 个排成数表：第 1 行是 1～7，第 2 行是 8～14，第 3 行是 15～21，……<br>（1）第 15 行第 3 个数是多少？<br>（2）100 在第几行第几个？<br>（3）某一行 7 个数的和是 469，这一行的第 1 个数是多少？",
         answer="（1）101　（2）第 15 行第 2 个　（3）64", analyze="（1）前 14 行共 14×7＝98 个数，第 15 行第 3 个＝98＋3＝101。（2）100÷7＝14……2，在第 15 行第 2 个。（3）一行 7 个数是公差 1 的等差数列，和＝中间数（第 4 个）×7：中间数＝469÷7＝67，第 1 个＝67－3＝64（验证：64＋65＋…＋70＝469 ✓）。周期数表＋等差＋中间数法三合一，第（3）问是中间数法的逆用。", sp=2),
]

CSS = """
@page { size: A4; margin: 12mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 11.5pt; line-height: 1.45; color: #000; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 17pt; margin: 1mm 0 0.5mm; letter-spacing: 1px; }
.sub { text-align: center; font-size: 10.5pt; margin: 0 0 2.5mm; }
table.score { border-collapse: collapse; margin: 0 auto 3.5mm; }
table.score td { border: 1.2px solid #000; width: 17mm; height: 6mm; text-align: center; font-size: 10.5pt; }
table.score td.h { font-family: "SimHei","Microsoft YaHei",sans-serif; height: 6mm; }
.sec { font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 12.5pt; margin: 2mm 0 1mm; padding-bottom: 0.5mm; border-bottom: 1.2px solid #000; page-break-after: avoid; }
.newpage { page-break-before: always; }
.q { margin: 0 0 1.2mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.pts { color: #444; font-size: 9.5pt; margin-right: 0.5mm; }
.opts { margin: 0.2mm 0 0.8mm 7mm; }
.opts span { display: inline-block; min-width: 38mm; }
.exprs { margin: 0.5mm 0 0 4mm; }
.exprs span { display: inline-block; width: 14mm; }
.mirow { margin: 1.5mm 0 0.5mm 6mm; }
table.vt2 { border-collapse: collapse; display: inline-table; margin: 0 14mm 0 0; vertical-align: top; }
table.vt2 td { width: 8.2mm; height: 8.2mm; text-align: center; font-size: 13pt; padding: 0; }
table.vt2 td.op { width: 7mm; }
table.vt2 td.bx { border: 1.2px solid #000; }
table.vt2 td.hr { border-bottom: 2px solid #000; height: 1.5mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 1.5mm 3mm; margin: 1mm 0 2.5mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
"""

SCORES = [3,3,3,3,3,3,3,3,3,3,3,3,6,6,6,6,6,6,7,7,7,7]

def build(with_answers):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>七月小测·综合测试卷</title><style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>七月小测 · 综合测试卷</h1>')
    h.append(f'<div class="sub">四年级数学　　考试时间：40 分钟　　满分：100 分{"　　<b>（教师用·含答案）</b>" if with_answers else ""}</div>')
    h.append('<table class="score"><tr><td class="h">题次</td><td class="h">一</td><td class="h">二</td><td class="h">三</td><td class="h">四</td><td class="h">五</td><td class="h">总分</td></tr>'
             '<tr><td class="h">得分</td><td></td><td></td><td></td><td></td><td></td><td></td></tr></table>')
    n = 0
    def emit(q, sp=0, opts=None):
        nonlocal n; n += 1
        h.append(f'<div class="q"><span class="no">{n}．</span><span class="pts">({SCORES[n-1]}分)</span>{q["stem"]}</div>')
        if opts:
            h.append('<div class="opts">' + ''.join(f'<span>{"ABCD"[i]}．{o}</span>' for i, o in enumerate(opts)) + '</div>')
        if with_answers:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}　<span class="lab">【解析】</span>{q["analyze"]}</p></div>')
        elif sp:
            h.append(f'<div style="height:{sp}mm"></div>')
    h.append('<div class="sec">一、填空题（每题 3 分，共 24 分）</div>')
    for q in TIANKONG: emit(q, sp=1)
    h.append('<div class="sec">二、选择题（每题 3 分，共 12 分）</div>')
    for q in XUANZE: emit(q, opts=q['opts'])
    h.append('<div class="sec">三、计算题（每题 6 分，共 18 分）</div>')
    for q in JISUAN: emit(q, sp=q['sp'])
    h.append('<div class="sec">四、数字谜（每题 6 分，共 12 分）</div>')
    for q in SHUZIMI: emit(q, sp=q['sp'])
    h.append('<div class="sec">五、应用题（共 27 分）</div>')
    for q in YINGYONG: emit(q, sp=q['sp'])
    h.append('<div class="sec">六、压轴题（共 7 分）</div>')
    for q in YAZHOU: emit(q, sp=q['sp'])
    h.append('</div></body></html>')
    return '\n'.join(h)

with open(os.path.join(OUT, '七月小测·题目卷.html'), 'w', encoding='utf-8') as f: f.write(build(False))
with open(os.path.join(OUT, '七月小测·答案卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
print('HTML done')
