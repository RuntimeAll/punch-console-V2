# -*- coding: utf-8 -*-
"""第5课 等差数列巧算：题目卷 + 答案卷（专项12＋课内10；思维题另有三关挑战卡）"""
import os

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第5课-等差数列巧算-20260719'
os.makedirs(OUT, exist_ok=True)

def calendar_svg():
    """2026年7月 日历，高亮 3×3 方框（8-10/15-17/22-24）"""
    CW, CH, MX, MY = 46, 34, 14, 30
    days = ['日', '一', '二', '三', '四', '五', '六']
    rows = [[None,None,None,1,2,3,4],[5,6,7,8,9,10,11],[12,13,14,15,16,17,18],
            [19,20,21,22,23,24,25],[26,27,28,29,30,31,None]]
    W = MX*2 + CW*7; H = MY + CH*6 + 10
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="margin:2mm 0">']
    p.append(f'<text x="{W/2}" y="16" text-anchor="middle" font-size="13" font-family="SimHei" fill="#333">2026 年 7 月</text>')
    for i, d in enumerate(days):
        p.append(f'<text x="{MX+CW*i+CW/2}" y="{MY+14}" text-anchor="middle" font-size="12" fill="#888" font-family="SimSun">{d}</text>')
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v is None: continue
            x, y = MX+CW*c, MY+CH*(r+1)
            p.append(f'<text x="{x+CW/2}" y="{y+22}" text-anchor="middle" font-size="13" font-family="SimSun" fill="#222">{v}</text>')
    fx, fy = MX+CW*3, MY+CH*2
    p.append(f'<rect x="{fx}" y="{fy+2}" width="{CW*3}" height="{CH*3}" fill="#1268b322" stroke="#1268b3" stroke-width="2.5" rx="4"/>')
    p.append('</svg>')
    return ''.join(p)

SIWEI = [
    dict(d=1, stem="<b>第 1 关 · 小高斯的懒办法</b>：两百多年前，10 岁的高斯几秒钟就算出了 1＋2＋3＋…＋99＋100。他没有一个一个加——你能找到他的懒办法吗？答案是多少？",
         fig='',
         answer="5050", analyze="首尾配对：1＋100＝101，2＋99＝101……共 50 对，101×50＝5050。坑：配成几对易答成 100 对。"),
    dict(d=2, stem="<b>第 2 关 · 升级挑战</b>：算一算 3＋7＋11＋15＋…＋95＋99（从 3 开始，每次加 4，一直加到 99）。",
         fig='',
         answer="1275", analyze="项数＝(99－3)÷4＋1＝25 个（坑：忘＋1）；25 个配不成整对，用中间数法：中间第 13 个数＝51，和＝51×25＝1275。等差数列里中间的数就是'平均个头'。"),
    dict(d=3, stem="<b>第 3 关 · 日历上的读心术（压轴）</b>：爷爷说：“你在日历上随便框一个 3×3 的方框（9 个日期），只要告诉我这 9 个数的和，我立刻说出你框的是哪几天！”<br>（1）研究下图的方框，找出爷爷的秘密；<br>（2）我框了一个方框，9 个数的和是 126——框里最大的日期是几号？<br>（3）9 个数的和可能是 100 吗？为什么？",
         fig=calendar_svg(),
         answer="（1）9 数之和＝正中间的数×9　（2）126÷9＝14，方框 6-8/13-15/20-22，最大 22 号　（3）不可能，和必是 9 的倍数而 100 不是",
         analyze="横看每行等差（差1）、竖看每列等差（差7），八个邻居两两配对都补成中间数，所以和＝中心×9（用图中方框验证：144＝16×9）。（2）先除以 9 找中心再还原整框（中心不能贴日历边）。（3）第一次用整除性排除不可能——读心术＝数学结构。"),
]

ZX = [
    dict(d=1, stem="有一个等差数列：4，10，16，22，…，580。这个等差数列共有多少项？",
         answer="97 项", analyze="公差＝6。项数＝(580－4)÷6＋1＝96＋1＝97（项）。坑点：除完要＋1（植树问题）。"),
    dict(d=2, stem="有一个等差数列：1，5，9，13，17，21，…<br>（1）它的第 1000 项是多少？<br>（2）4921 是它的第几项？",
         answer="（1）3997　（2）第 1231 项", analyze="公差＝4。（1）1＋4×999＝3997。（2）(4921－1)÷4＋1＝1231（项）。"),
    dict(d=2, stem="一个等差数列，公差是 6，末项是 106，项数是 18。<br>（1）这个等差数列的首项是几？<br>（2）这个数列的第 15 项是多少？",
         answer="（1）4　（2）88", analyze="首项＝106－6×17＝4；第 15 项＝4＋6×14＝88。逆向用通项关系：末项＝首项＋公差×(项数－1)。"),
    dict(d=3, stem="一个等差数列的第 5 项是 19，第 8 项是 61，它的第 11 项是多少？",
         answer="103", analyze="第 5 到第 8 项隔 3 个公差：公差＝(61－19)÷3＝14。第 11 项＝61＋14×3＝103。巧：不必求首项。"),
    dict(d=2, stem="计算：1＋2＋3＋…＋2023＋2024。",
         answer="2049300", analyze="首尾配对：(1＋2024)×2024÷2＝2025×1012＝2049300。"),
    dict(d=2, stem="从 1 开始每隔 4 个自然数写出一个自然数，可以得到一个数列：1，6，11，16，21，…求这个数列前 100 个数的和。",
         answer="24850", analyze="公差＝5，第 100 项＝1＋5×99＝496。和＝(1＋496)×100÷2＝24850。"),
    dict(d=3, stem="计算：(1＋3＋5＋…＋2025)－(2＋4＋6＋…＋2024)。",
         answer="1013", analyze="巧法（错位相减）：1＋(3－2)＋(5－4)＋…＋(2025－2024)＝1＋1×1012＝1013。"),
    dict(d=3, stem="有甲、乙两组数，每组都各有 25 个数。甲组：1，6，11，16，21，…；乙组：…，105，110，115，120，125。甲、乙两组数中所有数的和是多少？",
         answer="3150", analyze="甲组末项＝1＋5×24＝121，和＝(1＋121)×25÷2＝1525；乙组首项＝125－5×24＝5，和＝(5＋125)×25÷2＝1625。总和 3150。"),
    dict(d=3, stem="计算：1998＋1997－1996－1995＋1994＋1993－1992－1991＋…＋198＋197－196－195。",
         answer="1804", analyze="四个一组，每组＝4。共 1998－195＋1＝1804 个数，1804÷4＝451 组，和＝451×4＝1804。"),
    dict(d=4, stem="帆帆进行加法珠算练习，用 1＋2＋3＋4＋…，当加到某个数时，和是 1000。在验算时发现重复加了一个数，这个数是多少？",
         answer="10", analyze="1＋…＋44＝990，1000－990＝10≤44 合理；若加到 43 和＝946，多出 54＞43 不合理。所以重复加的是 10。"),
]

TB = [
    dict(d=1, stem="估算。<br>482×61≈　　　　　127×43≈　　　　　499×31≈",
         answer="30000；4000；15000", analyze="按最高位估：482≈500、61≈60→30000；127≈100、43≈40→4000；499≈500、31≈30→15000。"),
    dict(d=1, stem="脱式计算。<br>48＋124×3　　　　(96＋8)×79　　　　(50－4)×125",
         answer="420；8216；5750", analyze="先乘后加：48＋372＝420；括号先算：104×79＝8216；46×125＝5750。"),
    dict(d=2, stem="脱式计算。<br>602×14＋218　　　　9860－236×38",
         answer="8646；892", analyze="602×14＝8428，8428＋218＝8646；236×38＝8968，9860－8968＝892。"),
    dict(d=2, stem="□32×22，若积是四位数，则□里最大可以填（　）；若积是五位数，则□里最小可以填（　）。",
         answer="4；5", analyze="试算：432×22＝9504（四位），532×22＝11704（五位）。看最高位相乘是否进位。"),
    dict(d=1, stem="已知 ☆×7＝56，不计算也能知道：☆×70＝（　），☆×700＝（　）。",
         answer="560；5600", analyze="积的规律其一：一个因数不变，另一个因数乘 10、乘 100，积也乘 10、乘 100。"),
    dict(d=2, stem="两个数相乘，一个因数不变，另一个因数乘 7 后，积变成 336，那么原来的积是（　）。",
         answer="48", analyze="逆向用积的规律：积也被乘了 7，原来的积＝336÷7＝48。"),
    dict(d=2, stem="甲数乘乙数，积是 12，如果甲数扩大为原来的 2 倍，乙数扩大为原来的 5 倍，所得的新积是（　）。",
         answer="120", analyze="积的规律其二：两个因数分别乘 2 和 5，积就乘 2×5＝10，12×10＝120。"),
    dict(d=2, stem="168×34＝5712，如果 168 乘 2，要使积不变，34 要变成（　）。",
         answer="17", analyze="积的规律其三（积不变）：一个因数乘 2，另一个因数除以 2。34÷2＝17。"),
    dict(d=3, stem="请在图中的每个方框中填入适当的数字，使得乘法竖式成立。那么乘积是（　）。",
         fig='<img src="mi1.png" style="height:26mm">',
         answer="2754", analyze="第一个因数百位必是 1（□□□×7 只得三位数□1□）；第二部分 1□□×□＝20□ 推出乘数十位是 2；再由积的十位是 1 定出 102×7＝714。所以是 102×27＝2754。"),
    dict(d=3, stem="如图数字谜中，相同的汉字表示的数字相同，不同的汉字表示的数字不同。那么“好玩”表示的两位数是（　）。",
         fig='<img src="mi2.png" style="height:27mm">',
         answer="89", analyze="第二部分 2□好×1＝□0□，说明被乘数是 20好；再由 好×玩 的积末两位带 7 推出 8×9：208×9＝1872 成立。所以 好＝8、玩＝9，208×19＝3952，“好玩”＝89。"),
]

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 12pt; line-height: 1.8; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 19pt; margin: 4mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 4mm; }
.note { background: #fff8e6; border-left: 3px solid #e6c86e; padding: 1.5mm 3mm; margin: 2mm 0 3mm; font-size: 10.5pt; color: #7a5c00; }
.sec { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 17pt; text-align: center; margin: 2mm 0 6mm; page-break-after: avoid; }
.newpage { page-break-before: always; }
.big { font-size: 14pt; line-height: 2.0; }
.big .q { margin-bottom: 3mm; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.star { color: #b8860b; font-size: 10pt; margin-right: 1.5mm; }
.sp { height: 13mm; } .spm { height: 9mm; } .sps { height: 5mm; } .sp0 { height: 2mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 2mm 3mm; margin: 1.5mm 0 4mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
.foot { text-align: center; color: #999; font-size: 9pt; margin-top: 6mm; }
"""

def emit(qs, with_answers, h, spacer='sp'):
    i = 0
    for q in qs:
        i += 1
        h.append(f'<div class="q"><span class="no">{i}．</span><span class="star">{"★"*q["d"]}</span>{q["stem"]}</div>')
        if q.get('fig'):
            h.append(q['fig'])
        if with_answers:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}</p><p><span class="lab">【解析】</span>{q["analyze"]}</p></div>')
        else:
            h.append(f'<div class="{spacer}"></div>')

def build(with_answers):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>第5课·等差数列巧算</title><style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>第5课 · 等差数列巧算</h1>')
    h.append(f'<div class="sub">2026年7月19日{"（教师用·含答案解析）" if with_answers else ""}</div>')
    h.append('<div class="sec">思维题 · 三关挑战（算得快不如算得巧）</div>')
    h.append('<div class="big">')
    emit(SIWEI, with_answers, h, spacer='sps')
    h.append('</div>')
    h.append('<div class="sec newpage">奥数专项 · 等差数列巧算</div>')
    emit(ZX, with_answers, h, spacer='spm')
    h.append('<div class="sec newpage">同步练习 · 三位数乘两位数计算专场</div>')
    emit(TB, with_answers, h, spacer='sps')
    h.append('</div></body></html>')
    return '\n'.join(h)

with open(os.path.join(OUT, '第5课·题目卷.html'), 'w', encoding='utf-8') as f: f.write(build(False))
with open(os.path.join(OUT, '第5课·答案卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
print('HTML done')
