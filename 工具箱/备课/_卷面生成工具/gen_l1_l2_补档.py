# -*- coding: utf-8 -*-
"""第1/2课档案补齐：L1=最值专项(重构版)；L2=三段全量(系统卷142/143/144重排)"""
import os

ROOT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课'

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 12pt; line-height: 1.8; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 19pt; margin: 4mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 5mm; }
.sec { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 13.5pt; margin: 7mm 0 2.5mm; page-break-after: avoid; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.star { color: #b8860b; font-size: 10pt; margin-right: 1.5mm; }
.sp { height: 14mm; } .sps { height: 5mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 2mm 3mm; margin: 1.5mm 0 4mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
.note { background: #fff8e6; border-left: 3px solid #e6c86e; padding: 2mm 3mm; margin: 3mm 0; font-size: 10.5pt; color: #7a5c00; }
.foot { text-align: center; color: #999; font-size: 9pt; margin-top: 6mm; }
"""

L1_ZUIZHI = [
    dict(d=1, stem="已知两个非零自然数的和是 39，这两个自然数的积最大是多少？最小是多少？",
         answer="最大 380，最小 38", analyze="和一定时，两数越接近积越大、越悬殊积越小。最大：19×20＝380；最小：1×38＝38。"),
    dict(d=1, stem="李大爷要用长 30 米的篱笆围成一个长方形养鸡场，围得的养鸡场的面积最大是多少平方米？（长和宽均取整米数）",
         answer="56 平方米", analyze="周长 30，长＋宽＝15。和一定时长宽越接近面积越大，取整数 7×8＝56 平方米。"),
    dict(d=2, stem="用长 36 米的篱笆靠墙围成一块长方形菜地（长、宽均取整米数），这块长方形菜地的面积最大是多少？",
         answer="162 平方米", analyze="靠墙只围三边：设垂直墙的宽为 a，则 2a＋长＝36，面积＝a×(36−2a)。取整数试算 a＝9 时 9×18＝162 最大。"),
    dict(d=2, stem="用 1，3，5，7，8，9 这六个数字分别组成两个三位数，使这两个三位数的积最大。积最大是多少？",
         answer="830223（951×873）", analyze="积最大：大数字放高位，且两数尽量接近，得 951 与 873，积 951×873＝830223。"),
    dict(d=2, stem="在六位数 865473 的某一位数字后面插入一个同样的数字，可以得到一个七位数，这个七位数最小是多少？最大是多少？",
         answer="最小 8654473，最大 8865473", analyze="要最小→在尽量靠前处复制较小的数字：复制 4 得 8654473；要最大→复制最高位 8 得 8865473。"),
    dict(d=2, stem="把 16 拆分成几个自然数的和，这几个自然数的积最大是（　　）。",
         answer="324", analyze="拆数求积最大：尽量拆成 3，余 4 时拆两个 2（不留 1）。16＝3×4＋2×2，积＝3⁴×2²＝324。"),
    dict(d=3, stem="用 1~9 这九个数字分别组成三个不同的三位数，使这三个三位数的积最小。",
         answer="147×258×369＝13994694", analyze="积最小：最小数字 1、2、3 放百位；再让各数尽量小又均衡，得 147、258、369。"),
    dict(d=3, stem="四个互不相同的自然数的积是 546，这四个自然数的和最大是多少？",
         answer="97", analyze="和最大→把乘积集中到一个大因数：546＝1×2×3×91，和＝1＋2＋3＋91＝97。"),
    dict(d=3, stem="一个三位数除以 43，商是 a，余数是 b（a，b 都是整数），求 a＋b 的最大值。",
         answer="64", analyze="余数 b＜43，b 最大 42；43a＋b≤999：a＝22 时 946＋42＝988 成立，a＋b＝64；a＝23 时装不下 42。"),
    dict(d=3, stem="用若干根长为 2 厘米的小棒围成一个周长为 100 厘米的长方形，这个长方形的面积最大是多少平方厘米？",
         answer="624 平方厘米", analyze="长＋宽＝50；每边由 2 厘米小棒拼成，边长必为偶数，25 不行，退到 24×26＝624。约束发现后要收口算完。"),
    dict(d=4, stem="已知 12345678910111213…282930 是一个多位数（把 1 到 30 依次连写），从中画去 40 个数字，使剩下的数字（顺序不变）组成一个多位数，这个多位数最大是多少？最小是多少？",
         answer="最大 99627282930，最小 10012222220", analyze="原数 51 位，画去 40 剩 11 位。贪心法：求最大从左到右每次在“后面还够位”的前提下取最大数字；求最小首位取最小非零、其余尽量取小。"),
    dict(d=4, stem="有一个电子表用 5 个两位数来表示时间，如 14:32:45/08/28 表示 8 月 28 日 14 时 32 分 45 秒。当电子表上显示的 10 个数字都不同时，这 5 个两位数的和最大是多少？",
         answer="153", analyze="10 位数字用尽 0~9，和＝9×(十位之和)＋45。受时≤23、月≤12、日≤31、分秒≤59 限制，十位最优取 5、4、2、1、0，如 16:59:48/03/27，和＝153。"),
]

L2_SIWEI = [
    dict(d=3, stem="在下面算式合适的位置添上“＋”“－”“×”“÷”或“（　）”，使算式成立：<br>8　8　8　8　8　8　8　8　8　8　8　8 ＝ 2000",
         answer="一种填法：8888÷8＋888＋8÷8＋8－8＝2000", analyze="12 个 8。先用 8888÷8＝1111 造主体，再＋888＝1999，＋8÷8（＝1）补到 2000，最后＋8－8 抵消剩下两个 8。答案不唯一，凑到 2000 且恰好用完 12 个 8 即可。"),
]

L2_ZX = [
    dict(d=1, stem="对于两个数 A、B，规定 A⊕B＝A×B÷2，那么 6⊕4＝（　　）。",
         answer="12", analyze="直接代入定义：6⊕4＝6×4÷2＝24÷2＝12。"),
    dict(d=1, stem="对于两个数 a、b，规定 a☆b＝a＋4b。4☆5☆6＝（　　）。",
         answer="48", analyze="连续新运算从左往右算：4☆5＝4＋4×5＝24；再算 24☆6＝24＋4×6＝48。"),
    dict(d=1, stem="定义新运算：a▼b＝20×(a＋b)－19×(a－b)。20▼19＝（　　）。",
         answer="761", analyze="20▼19＝20×39－19×1＝780－19＝761。"),
    dict(d=1, stem="规定 [x] 表示取数 x 十位上的数字，例如 [37]＝3；|y| 表示取数 y 百位上的数字，例如 |628|＝6。若 x＝423，y＝1518，则 3[x]＋2|y|＝（　　）。",
         answer="16", analyze="[423]＝2，|1518|＝5，3×2＋2×5＝16。"),
    dict(d=2, stem="已知 3⊙4＝3×4×5×6，6⊙2＝6×7，2⊙5＝2×3×4×5×6，则 2023⊙2＝（　　）。",
         answer="4094552", analyze="规律：a⊙b＝从 a 开始连乘 b 个连续自然数。2023⊙2＝2023×2024＝4094552。"),
    dict(d=2, stem="定义新运算：1△2＝1＋2＝3，2△3＝2＋3＋4＝9，3△4＝3＋4＋5＋6＝18。若 x△4＝22，则 x＝（　　）。",
         answer="4", analyze="x△4＝x＋(x＋1)＋(x＋2)＋(x＋3)＝4x＋6＝22，得 x＝4。逆向题：先把规律写成含 x 的式子再解。"),
    dict(d=2, stem="对于两个数 a 与 b，规定 a⊕b＝(a＋1)＋(a＋2)＋…＋(a＋b)，如果 x⊕5＝75，求 x。",
         answer="12", analyze="x⊕5＝5x＋(1＋2＋3＋4＋5)＝5x＋15＝75，x＝12。"),
    dict(d=3, stem="对于任意自然数 a、b 定义新运算：若 a、b 的奇偶性相同，则 a☆b＝(a＋b)÷2；若 a、b 的奇偶性不同，则 a☆b＝(a＋b＋1)÷2。1☆2☆3☆4☆5☆…☆99☆100＝（　　）。",
         answer="100", analyze="逐步算发现每一步结果 k 与下一个数 k＋1 奇偶必不同，k☆(k＋1)＝k＋1，即每步结果都等于刚吃进来的那个数，滚动到最后＝100。"),
]

L2_TB = [
    dict(d=1, stem="把下面各数改写成用“万”作单位的数：<br>（1）50000＝（　）万　（2）1800000＝（　）万　（3）60040000＝（　）万",
         answer="（1）5万　（2）180万　（3）6004万", analyze="改写＝去掉万位后面 4 个 0 换成“万”字，数的大小不变。"),
    dict(d=1, stem="把下面各数改写成用“亿”作单位的数：<br>（1）700000000＝（　）亿　（2）3400000000＝（　）亿",
         answer="（1）7亿　（2）34亿", analyze="去掉亿位后面 8 个 0 换成“亿”字。"),
    dict(d=2, stem="省略下面各数万位后面的尾数，求出它的近似数：<br>（1）49200≈（　）　（2）83500≈（　）　（3）725000≈（　）",
         answer="（1）5万　（2）8万　（3）73万", analyze="看千位四舍五入：49200 千位 9 进 1≈5万；83500 千位 3 舍≈8万；725000 千位 5 进 1≈73万。"),
    dict(d=2, stem="省略下面各数亿位后面的尾数，求出它的近似数：<br>（1）1963000000≈（　）　（2）496200000≈（　）",
         answer="（1）20亿　（2）5亿", analyze="看千万位四舍五入：19 亿进 1≈20亿；4 亿进 1≈5亿。"),
    dict(d=2, stem="某工厂去年生产零件 5080000 个，今年生产 5086000 个。（1）去年的产量改写成用“万”作单位的数是（　）万个；（2）今年的产量省略万位后面的尾数，约是（　）万个。",
         answer="（1）508万　（2）509万", analyze="改写不改变大小用＝；求近似数四舍五入用≈——这正是两者的区别。"),
]

def emit(qs, with_answers, h, spacer='sp'):
    i = 0
    for q in qs:
        i += 1
        h.append(f'<div class="q"><span class="no">{i}．</span><span class="star">{"★"*q["d"]}</span>{q["stem"]}</div>')
        if with_answers:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}</p><p><span class="lab">【解析】</span>{q["analyze"]}</p></div>')
        else:
            h.append(f'<div class="{spacer}"></div>')

def page(title, date, sections, with_answers, note=''):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title><style>{CSS}</style></head><body><div class="doc">']
    h.append(f'<h1>{title}</h1>')
    h.append(f'<div class="sub">{date}{"（教师用·含答案解析）" if with_answers else ""}</div>')
    if note:
        h.append(f'<div class="note">{note}</div>')
    for sec, qs, spacer in sections:
        h.append(f'<div class="sec">&#128214; {sec}</div>')
        emit(qs, with_answers, h, spacer)
    h.append('<div class="foot">— 完 —</div></div></body></html>')
    return '\n'.join(h)

JOBS = [
    ('第1课-统筹与最值-20260705', '第1课 · 统筹与最值', '2026年7月5日',
     [('【奥数专项】最值问题', L1_ZUIZHI, 'sp')],
     '档案重构版（2026-07-14 按第1课原题池整理）：原思维题与课内过关卷未留档，本卷为当课奥数专项完整题池。'),
    ('第2课-定义新运算-20260707', '第2课 · 定义新运算', '2026年7月7日',
     [('【思维题】开场热身', L2_SIWEI, 'sp'), ('【奥数专项】定义新运算', L2_ZX, 'sp'), ('【课内过关】大数的改写和近似数', L2_TB, 'sps')],
     '档案补排版（2026-07-14 由系统备课卷 142/143/144 重排）。'),
]

for folder, title, date, sections, note in JOBS:
    out = os.path.join(ROOT, folder)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, '题目卷.html'), 'w', encoding='utf-8') as f:
        f.write(page(title, date, sections, False, note))
    with open(os.path.join(out, '答案卷.html'), 'w', encoding='utf-8') as f:
        f.write(page(title, date, sections, True, note))
    print('done', folder)
