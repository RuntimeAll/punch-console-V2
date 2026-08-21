# -*- coding: utf-8 -*-
"""第6课 周期问题：题目卷 + 答案卷（思维题·生肖三关 ＋ 专项10 ＋ 同步应用专场10）"""
import os

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第6课-周期问题-20260726'
os.makedirs(OUT, exist_ok=True)

def clock_svg():
    """七格怪钟：一圈 7 格，格线标 0~6，指针指向 0"""
    import math
    R, C = 33, 40
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{C*2}" height="{C*2}" viewBox="0 0 {C*2} {C*2}" style="margin:2mm 0">']
    p.append(f'<circle cx="{C}" cy="{C}" r="{R}" fill="none" stroke="#444" stroke-width="2"/>')
    for i in range(7):
        a = -90 + i * 360 / 7
        rad = math.radians(a)
        x1, y1 = C + R * 0.92 * math.cos(rad), C + R * 0.92 * math.sin(rad)
        x2, y2 = C + R * math.cos(rad), C + R * math.sin(rad)
        xt, yt = C + R * 0.78 * math.cos(rad), C + R * 0.78 * math.sin(rad)
        p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#444" stroke-width="2"/>')
        p.append(f'<text x="{xt:.1f}" y="{yt+4:.1f}" text-anchor="middle" font-size="12" font-family="SimSun">{i}</text>')
    p.append(f'<line x1="{C}" y1="{C}" x2="{C}" y2="{C-R*0.62:.1f}" stroke="#c0392b" stroke-width="3"/>')
    p.append(f'<circle cx="{C}" cy="{C}" r="3" fill="#c0392b"/>')
    p.append('</svg>')
    return ''.join(p)

SHENGXIAO = ('<div style="background:#eef7ee;border-left:3px solid #7cb87c;padding:1.5mm 3mm;margin:1.5mm 0;font-size:10.5pt">'
             '十二生肖顺序：鼠 → 牛 → 虎 → 兔 → 龙 → 蛇 → <b>马</b> → 羊 → 猴 → 鸡 → 狗 → 猪（12 年一轮，今年 2026 年是<b>马年</b>）</div>')

SIWEI = [
    dict(d=1, stem="<b>第 1 关 · 一百年后</b>：今年 2026 年是马年。100 年后的 2126 年，是什么生肖年？",
         fig=SHENGXIAO,
         answer="狗年", analyze="生肖 12 年一个周期。100÷12＝8（轮）……4（年），从马往后数 4 个：羊、猴、鸡、狗——2126 年是狗年。坑：余数是往'后'数（未来方向）。"),
    dict(d=2, stem="<b>第 2 关 · 爷爷的生肖</b>：爷爷说他是 1962 年出生的。爷爷属什么？",
         fig='',
         answer="属虎", analyze="2026－1962＝64（年），64÷12＝5（轮）……4（年），这次要从马往'回'数 4 个：蛇、龙、兔、虎——爷爷属虎。坑：方向和第 1 关相反，往过去数。"),
    dict(d=3, stem="<b>第 3 关 · 生肖读心术（压轴）</b>：一位叔叔说：“我今年过完生日是 24 岁。”你能马上说出他属什么吗？为什么这么快？",
         fig='',
         answer="属马（和今年一样）", analyze="巧在这里：24 正好是 12 的倍数（24＝12×2），转了整整两轮，生肖和今年一样——直接答马年，根本不用算 2026－24＝2002。验证：2002 年确实是马年。追问：25 岁的人属什么？（往回多数 1 个：蛇。）"),
]

ZX = [
    dict(d=2, stem="2028 年 6 月 1 日是星期四，那么 2028 年 7 月 1 日是星期几？2028 年 8 月 1 日呢？",
         answer="7 月 1 日是星期六；8 月 1 日是星期二", analyze="星期以 7 天为周期。6 月有 30 天，30÷7＝4……2，星期四往后 2 天＝星期六；7 月有 31 天，31÷7＝4……3，星期六往后 3 天＝星期二。"),
    dict(d=2, stem="有一列数：1，4，2，8，5，7，1，4，2，8，5，7，…<br>（1）这列数的第 80 个数是多少？<br>（2）这列数前 80 个数的和是多少？",
         answer="（1）4　（2）356", analyze="周期是 6 个数，每周期的和＝1＋4＋2＋8＋5＋7＝27。（1）80÷6＝13……2，第 80 个＝周期里第 2 个＝4。（2）13×27＝351，加余下的 1＋4＝5，共 356。"),
    dict(d=2, stem="如下所示，三个数字 1，2，3 与两个字母 A，B 依次不断重复出现，一个数字与一个字母为一组。第 25 组和第 42 组分别是什么数字和字母？<br><table class=\"vt\" style=\"margin:1mm 0\"><tr><td>1</td><td>2</td><td>3</td><td>1</td><td>2</td><td>3</td><td>1</td><td>2</td><td>3</td><td>…</td></tr><tr><td>A</td><td>B</td><td>A</td><td>B</td><td>A</td><td>B</td><td>A</td><td>B</td><td>A</td><td>…</td></tr></table>",
         answer="第 25 组：数字 1、字母 A；第 42 组：数字 3、字母 B", analyze="数字周期 3、字母周期 2，两行分开算。25÷3 余 1→数字 1；25÷2 余 1→字母 A。42÷3 整除→周期末位 3；42÷2 整除→周期末位 B。双周期各算各的，别搅在一起。"),
    dict(d=3, stem="将编号为 1～2024 的 2024 名学生按下列方法排成五列。编号为 2024 的学生排在第几列？<br><table class=\"vt\" style=\"margin:1mm 0\"><tr><td>一</td><td>二</td><td>三</td><td>四</td><td>五</td></tr><tr><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td></tr><tr><td>9</td><td>8</td><td>7</td><td>6</td><td></td></tr><tr><td></td><td>10</td><td>11</td><td>12</td><td>13</td></tr><tr><td>17</td><td>16</td><td>15</td><td>14</td><td></td></tr><tr><td></td><td>18</td><td>19</td><td>20</td><td>21</td></tr><tr><td>…</td><td></td><td></td><td></td><td></td></tr></table>",
         answer="第二列", analyze="来回蛇形，每 8 个编号一个周期（列的顺序：一二三四五四三二）。2024÷8＝253 整除，与周期第 8 个位置相同——第 8 个在第二列。"),
    dict(d=2, stem="丽丽买了一本童话书，她发现这本童话书每 2 页文字之间有 4 页插图，也就是说 4 页插图前后各有 1 页文字。如果这本童话书有 126 页，且第 1 页是文字，则插图共有多少页？",
         answer="100 页", analyze="排法是“1 页文字＋4 页插图”不断重复，周期 5 页。126÷5＝25（组）……1（页），余下 1 页按顺序是文字。插图共 25×4＝100（页）。"),
    dict(d=2, stem="把一些数按这样的规律排列：1，1，2，2，3，3，…<br>（1）第 25 个数是奇数还是偶数？你知道它是多少吗？<br>（2）第 51 个数是奇数还是偶数？你知道它是多少吗？",
         answer="（1）奇数，是 13　（2）偶数，是 26", analyze="每个数连续出现 2 次，第 n 个数＝(n＋1)÷2 取整。第 25 个＝(25＋1)÷2＝13，奇数；第 51 个＝(51＋1)÷2＝26，偶数。"),
    dict(d=3, stem="请同学们伸出左手，从大拇指开始依次数数（拇指→食指→中指→无名指→小指，再折回：无名指→中指→食指→拇指→食指→…来回地数），数到 100 时，数在哪根手指上？",
         answer="无名指", analyze="来回数：1 拇指、2 食指、3 中指、4 无名指、5 小指、6 无名指、7 中指、8 食指，第 9 个又回到拇指——周期是 8。100÷8＝12……4，与第 4 个相同，落在无名指上。"),
    dict(d=3, stem="用 1～5 这五个数字可以组成 120 个不同的五位数，把这些五位数按从小到大的顺序排列，第 50 个数是多少？",
         answer="31254", analyze="以 1 开头的有 24 个（第 1～24），以 2 开头的有 24 个（第 25～48），第 49 个起是 3 开头：第 49 个＝31245，第 50 个＝31254。按'开头分块'有序数，别一个个列。"),
    dict(d=3, stem='<span style="float:right;margin:0 0 1mm 3mm">' + clock_svg() + '</span>有一只怪钟（如图所示），一圈有 7 个格子，格线上依次标着 0～6。钟面上只有一根指针，指针每分钟跳一次，一次顺时针方向跳 3 个格子（例如从 2 跳到 5）。开始时，指针指向 0。过 1 个小时，指针指向哪个数字？',
         answer="5", analyze="1 小时＝60 分钟，共跳 60×3＝180（格）。一圈 7 格，180÷7＝25（圈）……5（格），从 0 多走 5 格，指向 5。"),
    dict(d=4, stem="把从 1 开始的自然数按下面的方式排列，那么 4951 是第几行第几个数？<br><span style=\"font-family:monospace;font-size:10.5pt;line-height:1.5;display:inline-block\">第1行：1　2　4　7　11　…<br>第2行：3　5　8　12　…<br>第3行：6　9　13　…<br>第4行：10　14　…<br>第5行：15　…</span>",
         answer="第 1 行第 100 个数", analyze="按斜线看：第 1 条斜线 1 个数，第 2 条 2 个……第 n 条 n 个，且每条斜线的第 1 个数都在第 1 行。前 99 条斜线共 1＋2＋…＋99＝(1＋99)×99÷2＝4950（个）数，所以 4951 正好是第 100 条斜线的开头——第 1 行第 100 个数。（等差求和又立功了。）"),
]

TB = [
    dict(d=1, stem="学校要购买 26 套课桌椅，桌子每张 138 元，椅子每张 86 元。一共需要多少元？",
         answer="5824 元", analyze="每套一桌一椅：(138＋86)×26＝224×26＝5824（元）。先凑“每套价”再乘，比分开算两次快。"),
    dict(d=1, stem="果园里有梨树 125 棵，苹果树的棵数是梨树的 17 倍，果园里苹果树和梨树共有多少棵？",
         answer="2250 棵", analyze="苹果树 125×17＝2125（棵），共 2125＋125＝2250（棵）。也可以巧算：125×(17＋1)＝125×18＝2250。"),
    dict(d=2, stem="国庆假期，笑笑一家去旅行，伙食费花了 350 元，其它各项费用比伙食费的 12 倍还多 60 元，这次旅行共花多少元？",
         answer="4610 元", analyze="其它费用＝350×12＋60＝4260（元），共花 4260＋350＝4610（元）。坑：别忘了把伙食费本身加回去。"),
    dict(d=2, stem="甲、乙两个城市之间相距 335 千米，王叔叔开车从甲城到乙城，行驶了 3 小时，距离乙城还有 50 千米。王叔叔平均每小时开车多少千米？",
         answer="95 千米/时", analyze="3 小时实际行了 335－50＝285（千米），285÷3＝95（千米/时）。坑：335 不能直接除以 3——那 50 千米还没走。"),
    dict(d=3, stem="小芳从家到学校 450 米，她上学要走 4 分钟，回家比上学多用 1 分钟，她往返一趟平均每分钟走多少米？",
         answer="100 米", analyze="总路程 450＋450＝900（米），总时间 4＋(4＋1)＝9（分钟），900÷9＝100（米/分）。平均速度＝总路程÷总时间，不能把两个速度加起来除以 2。"),
    dict(d=2, stem="喜迎门生活广场以 85 元的价格进了 50 个电热水壶，以 110 元的价格售出。在售出 35 个后，恰逢国庆节酬宾，便将剩下的电热水壶以 98 元的价格全部售完。一共赚了多少元？",
         answer="1070 元", analyze="前 35 个每个赚 110－85＝25（元），共 25×35＝875（元）；剩 15 个每个赚 98－85＝13（元），共 13×15＝195（元）。合计 875＋195＝1070（元）。按“每个赚多少”算比先算总收入更省事。"),
    dict(d=3, stem="博美超市以每台 275 元的批发价购进 35 台相同的随身听，每台随身听的售价是 325 元。卖出 18 台后，开始降价，以每台 230 元的价格把剩下的全部卖出。那么请你算一算，博美超市是赚了还是亏了？",
         answer="赚了（赚 135 元）", analyze="成本 275×35＝9625（元）；收入 325×18＋230×17＝5850＋3910＝9760（元）。9760＞9625，赚了 9760－9625＝135（元）。降价卖也可能整体是赚的——要算总账，不能只看降价那部分。"),
    dict(d=2, stem="商场举行迎“端午”促销活动，全场毛巾买 5 条送 1 条，每条毛巾的单价是 11 元，刘阿姨要买 15 条毛巾，至少需要花多少元？",
         answer="143 元", analyze="买 5 送 1＝每 6 条只付 5 条的钱。15÷6＝2（组）……3（条），2 组付 5×2＝10 条，余 3 条照付，共付 (10＋3)×11＝143（元）。"),
    dict(d=3, stem="元旦各超市都搞促销活动，体育王老师准备为学校购置 18 个足球，到哪家超市买更便宜？<br><table class=\"vt\" style=\"margin:1mm 0\"><tr><td>A 超市</td><td>一个 50 元，买 5 送 1</td></tr><tr><td>B 超市</td><td>一箱 6 个，一箱 260 元</td></tr></table>",
         answer="A 超市（A 750 元＜B 780 元）", analyze="A：买 5 送 1＝每 6 个付 5 个的钱，18÷6＝3（组），付 5×3＝15（个），15×50＝750（元）。B：18÷6＝3（箱），260×3＝780（元）。750＜780，A 超市更便宜。"),
    dict(d=3, stem="商店里举行特卖活动。有一款西服，单买上衣一件 225 元，单买裤子一条 145 元；如果成套买，每套 349 元。一家酒店想为员工购买 38 件上衣、45 条裤子，最少要用多少钱？",
         answer="14277 元", analyze="成套买每套省 225＋145－349＝21（元），所以能成套尽量成套：38 套（上衣全配对）349×38＝13262（元），剩 45－38＝7 条裤子单买 145×7＝1015（元），共 13262＋1015＝14277（元）。压轴考“怎么组合最省”。"),
]

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 12pt; line-height: 1.72; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 19pt; margin: 4mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 4mm; }
.sec { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 17pt; text-align: center; margin: 1mm 0 4mm; page-break-after: avoid; }
.newpage { page-break-before: always; }
.big { font-size: 14pt; line-height: 2.0; }
.big .q { margin-bottom: 3mm; }
.tight { line-height: 1.55; }
.tight .q { margin-bottom: 1mm; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.star { color: #b8860b; font-size: 10pt; margin-right: 1.5mm; }
.sp { height: 13mm; } .spm { height: 9mm; } .sps { height: 5mm; } .sp0 { height: 1mm; }
.vt { border-collapse: collapse; font-size: 10.5pt; }
.vt td { border: 1px solid #999; min-width: 20px; padding: 0.2mm 1.6mm; text-align: center; }
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
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>第6课·周期问题</title><style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>第6课 · 周期问题</h1>')
    h.append(f'<div class="sub">2026年7月26日{"（教师用·含答案解析）" if with_answers else ""}</div>')
    h.append('<div class="sec">思维题 · 生肖读心术三关</div>')
    h.append('<div class="big">')
    emit(SIWEI, with_answers, h, spacer='sps')
    h.append('</div>')
    h.append('<div class="sec newpage">奥数专项 · 周期问题</div>')
    h.append('<div class="tight">')
    emit(ZX, with_answers, h, spacer='sp0')
    h.append('</div>')
    h.append('<div class="sec newpage">同步练习 · 三位数乘两位数应用专场</div>')
    emit(TB, with_answers, h, spacer='sps')
    h.append('</div></body></html>')
    return '\n'.join(h)

with open(os.path.join(OUT, '第6课·题目卷.html'), 'w', encoding='utf-8') as f: f.write(build(False))
with open(os.path.join(OUT, '第6课·答案卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
print('HTML done')
