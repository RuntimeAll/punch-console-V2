# -*- coding: utf-8 -*-
"""第7课 行程问题：题目卷 + 答案卷（思维题·小狗折返跑三关 ＋ 专项12 ＋ 同步过关8）"""
import os

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\第7课-行程问题-20260726'
os.makedirs(OUT, exist_ok=True)

SIWEI = [
    dict(d=1, stem="<b>第 1 关 · 迎面出发</b>：甲、乙两地相距 10 千米。小明每小时走 4 千米，爷爷每小时走 6 千米，两人同时从两地出发、相向而行。几小时后相遇？",
         fig='',
         answer="1 小时", analyze="相向而行速度相加：4＋6＝10（千米/时），10÷10＝1（小时）。热身，为第 2 关搭台。"),
    dict(d=3, stem="<b>第 2 关 · 停不下来的小狗</b>：两人出发的同时，小明身边的小狗以每小时 15 千米的速度向爷爷跑去，碰到爷爷立刻掉头跑向小明，碰到小明再掉头跑向爷爷……就这样来回不停地跑，直到两人相遇才停下。小狗一共跑了多少千米？",
         fig='',
         answer="15 千米", analyze="坑：去追小狗的每一段折返——段数无穷多，算不完。巧：狗一刻没停，它跑的<b>时间</b>就是两人相遇的时间（第 1 关已算出＝1 小时），所以狗跑了 15×1＝15（千米）。算时间，不追路线。（这是数学家冯·诺依曼的名题——据说有人用无穷级数硬算，他一秒答出，靠的就是换角度。）"),
    dict(d=4, stem="<b>第 3 关 · 反过来考你（压轴）</b>：第二天他们换了一条路。小明每小时走 5 千米，爷爷每小时走 7 千米，小狗还是每小时跑 18 千米、照样来回跑。这次小狗一共跑了 36 千米。这条路有多长？",
         fig='',
         answer="24 千米", analyze="逆用第 2 关的巧法：狗跑的时间＝36÷18＝2（小时），这也是两人的相遇时间；两人 2 小时共走完全程，(5＋7)×2＝24（千米）。会正着用还要会倒着用，才算真懂。"),
]

ZX_BLOCKS = [
    dict(title='火车过桥', tip='钥匙：总路程＝桥（隧道）长＋车长——车尾也要出去', qs=[
        dict(d=1, stem="一列火车长 300 米，以每分钟 600 米的速度通过一座长 900 米的隧道，需要多少分钟？",
             answer="2 分钟", analyze="总路程＝车长＋隧道长＝300＋900＝1200（米），1200÷600＝2（分钟）。"),
        dict(d=2, stem="一列长 320 米的火车，以每分钟 900 米的速度通过一座桥，从车头上桥到车尾离桥用了 4 分钟。桥长多少米？",
             answer="3280 米", analyze="4 分钟走的总路程＝900×4＝3600（米），这段路＝车长＋桥长，桥长＝3600－320＝3280（米）。"),
        dict(d=3, stem="两列火车长度分别为 240 米和 260 米，相向而行，速度分别为 20 米/秒和 30 米/秒。从车头相遇到车尾相离需要多少秒？",
             answer="10 秒", analyze="从车头相遇到车尾相离，两车共同走完两个车长之和＝240＋260＝500（米）；相向而行速度相加＝50（米/秒），500÷50＝10（秒）。"),
        dict(d=4, stem="一列火车以相同的速度通过长 400 米的桥和长 600 米的隧道，分别用了 30 秒和 40 秒。火车长多少米？",
             answer="200 米", analyze="差量法：车长相同，多出的路程只来自隧道比桥长的 600－400＝200（米），多用 40－30＝10（秒），速度＝200÷10＝20（米/秒）。车长＝20×30－400＝200（米）。验证：20×40－600＝200 ✓。"),
    ]),
    dict(title='追及问题', tip='钥匙：追及时间＝路程差÷速度差；环形同向追上一次＝多跑一圈', qs=[
        dict(d=2, stem="小红每分钟走 60 米，妈妈每分钟走 90 米，小红先出发 10 分钟后妈妈去追。妈妈追上小红时走了多少米？",
             answer="1800 米", analyze="路程差＝60×10＝600（米），速度差＝90－60＝30（米/分），追及时间＝600÷30＝20（分钟），妈妈走了 90×20＝1800（米）。"),
        dict(d=3, stem="小明先出发 4 分钟，每分钟走 75 米；爸爸骑车去追，5 分钟追上。爸爸每分钟骑多少米？",
             answer="135 米", analyze="逆着用：路程差＝75×4＝300（米），5 分钟追平，速度差＝300÷5＝60（米/分），爸爸速度＝75＋60＝135（米/分）。"),
        dict(d=3, stem="环形跑道长 600 米，甲每分钟跑 140 米，乙每分钟跑 110 米，两人同时同地同向出发，第二次追上时甲跑了多少圈？",
             answer="9 又 1/3 圈（9 圈多 200 米）", analyze="环形同向：每追上一次，甲要比乙多跑整整一圈 600 米。追上一次用 600÷(140－110)＝20（分钟），第二次共 40 分钟。甲跑 140×40＝5600（米），5600÷600＝9（圈）……200（米）。"),
    ]),
    dict(title='流水行船', tip='钥匙：顺水＝船速＋水速，逆水＝船速－水速；水速＝(顺－逆)÷2', qs=[
        dict(d=1, stem="船在静水中每小时行 15 千米，水流速度是每小时 3 千米。这艘船顺水、逆水每小时各行多少千米？",
             answer="顺水 18 千米/时；逆水 12 千米/时", analyze="顺水＝15＋3＝18（千米/时）；逆水＝15－3＝12（千米/时）。水推着走就加，顶着水就减。"),
        dict(d=3, stem="船顺水航行 3 小时行了 90 千米，逆水航行同样的路程需要 5 小时。水流速度是多少千米/时？",
             answer="6 千米/时", analyze="顺水速度＝90÷3＝30，逆水速度＝90÷5＝18（千米/时）。顺水比逆水快的部分是两倍水速，水速＝(30－18)÷2＝6（千米/时）。"),
        dict(d=4, stem="一艘船从 A 港到 B 港逆水用了 10 小时，顺水用了 8 小时，已知顺水速度比逆水速度快 6 千米/时。A、B 两港相距多少千米？",
             answer="240 千米", analyze="顺水行的 8 小时里，每小时比逆水多行 6 千米，共多行 6×8＝48（千米）；这 48 千米正好是逆水还要再行 10－8＝2 小时的路，逆水速度＝48÷2＝24（千米/时），两港相距 24×10＝240（千米）。验证：顺水 30×8＝240 ✓。"),
    ]),
    dict(title='相遇问题', tip='钥匙：相向而行速度相加；第二次相遇＝共走 3 个全程', qs=[
        dict(d=3, stem="小明每分钟走 80 米，小刚每分钟走 70 米，两人从两地相向而行，第二次相遇时共走了 3600 米。两地相距多少米？",
             answer="1200 米", analyze="第一次相遇共走 1 个全程；到第二次相遇共走 3 个全程（各自走到对方端点又折回，多凑出两个全程）。3600÷3＝1200（米）。"),
        dict(d=4, stem="小明和小刚同时从学校出发，沿同一条路回家，小明每分钟走 75 米，小刚每分钟走 60 米。小明到家后立即返回，在离家 180 米处遇到小刚。学校离家有多远？",
             answer="1620 米", analyze="相遇时小明走了全程＋180 米，小刚走了全程－180 米，两人差 180×2＝360（米）；每分钟差 15 米，所以走了 360÷15＝24（分钟）。小刚走 60×24＝1440（米），全程＝1440＋180＝1620（米）。验证：小明 75×24＝1800＝1620＋180 ✓。"),
        dict(d=4, stem="甲、乙两车同时从 A、B 两地相向而行，第一次相遇距 A 地 80 千米，第二次相遇距 B 地 60 千米。A、B 两地相距多少千米？",
             answer="180 千米", analyze="第一次相遇共走 1 个全程，甲走了 80 千米；第二次共走 3 个全程，甲共走 80×3＝240（千米）。甲走完全程到 B 后折返，折返了 240－全程，此时距 B 地 60 千米，所以全程＝240－60＝180（千米）。验证：乙共走 300，走完 180 折返 120，距 A 地 120＝180－60 ✓。"),
    ]),
]

TB = [
    dict(d=1, stem="直线 a 和直线 b 互相平行，记作（　）；直线 m 和直线 n 互相垂直，记作（　）。",
         answer="a∥b；m⊥n", analyze="平行记号“∥”，垂直记号“⊥”。"),
    dict(d=1, stem="在同一平面内，直线 a 垂直直线 m，直线 a 垂直直线 n，那么直线 m 和直线 n（　）。",
         answer="互相平行", analyze="同一平面内，垂直于同一条直线的两条直线互相平行。"),
    dict(d=1, stem="伸缩门就是利用平行四边形（　）的特点制作的。",
         answer="容易变形（不稳定性）", analyze="平行四边形不稳定、易变形——伸缩门、晾衣架、折叠椅都用这个特性；三角形才稳定。"),
    dict(d=2, stem="平行四边形相邻的两条边分别是 5 厘米、4 厘米，它的周长是（　）。",
         answer="18 厘米", analyze="平行四边形对边相等，周长＝(5＋4)×2＝18（厘米）。"),
    dict(d=2, stem="一个平行四边形的周长是 36 厘米，其中一条边的长度是 12 厘米，与它相邻的另一条边的长度是（　）厘米。",
         answer="6 厘米", analyze="反过来求：36÷2－12＝6（厘米）。周长的一半＝相邻两边之和。"),
    dict(d=2, stem="王阿姨有一块平行四边形的菜地，这块菜地的一边长 12 米，它的邻边比它短 3 米。这块菜地的周长是多少米？",
         answer="42 米", analyze="邻边＝12－3＝9（米），周长＝(12＋9)×2＝42（米）。"),
    dict(d=2, stem="一个等腰梯形的上底是 6 厘米，下底是 9 厘米，一条腰是 12 厘米，这个梯形的周长是（　）。",
         answer="39 厘米", analyze="等腰梯形两腰相等：6＋9＋12×2＝39（厘米）。"),
    dict(d=3, stem="一个等腰梯形的周长是 100 厘米，上底 17 厘米，下底 33 厘米，它的一条腰长（　）厘米。",
         answer="25 厘米", analyze="两腰之和＝100－17－33＝50（厘米），一条腰＝50÷2＝25（厘米）。"),
    dict(d=3, stem="用细木条钉成一个长方形框，长 12 厘米，宽 7 厘米，如果把它拉成一个平行四边形，它的周长是（　）厘米。",
         answer="38 厘米", analyze="拉动时四条木条的长度不变，只是形状变了，周长仍＝(12＋7)×2＝38（厘米）。（面积变小了——这是下学期的伏笔。）"),
    dict(d=4, stem="一个等腰梯形，下底是上底的 3 倍，把上底延长 6 厘米，恰好变成一个周长 26 厘米的平行四边形。原来梯形的一条腰长（　）厘米。",
         answer="4 厘米", analyze="上底延长 6 厘米后与下底相等，说明下底－上底＝6（厘米）；又下底＝上底×3，所以上底＝3、下底＝9（厘米）。变成的平行四边形两组对边是 9 和腰，(9＋腰)×2＝26，腰＝26÷2－9＝4（厘米）。"),
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
.tight { line-height: 1.6; }
.tight .q { margin-bottom: 1mm; }
.blk { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 12.5pt; margin: 2.5mm 0 1mm; page-break-after: avoid; }
.blk .tip { font-family: "SimSun","Songti SC",serif; color: #6b5300; font-size: 10.5pt; font-weight: normal; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.q .no { font-weight: bold; }
.star { color: #b8860b; font-size: 10pt; margin-right: 1.5mm; }
.sp { height: 13mm; } .spm { height: 9mm; } .sps { height: 5mm; } .sp0 { height: 1mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 2mm 3mm; margin: 1.5mm 0 4mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
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
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>第7课·行程问题</title><style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>第7课 · 行程问题</h1>')
    h.append(f'<div class="sub">2026年7月26日{"（教师用·含答案解析）" if with_answers else ""}</div>')
    h.append('<div class="sec">思维题 · 停不下来的小狗</div>')
    h.append('<div class="big">')
    emit(SIWEI, with_answers, h, spacer='sps')
    h.append('</div>')
    h.append('<div class="sec newpage">奥数专项 · 行程问题</div>')
    h.append('<div class="tight">')
    n = 0
    for blk in ZX_BLOCKS:
        tip = f'　<span class="tip">{blk["tip"]}</span>' if with_answers else ''
        h.append(f'<div class="blk">【{blk["title"]}】{tip}</div>')
        for q in blk['qs']:
            n += 1
            h.append(f'<div class="q"><span class="no">{n}．</span><span class="star">{"★"*q["d"]}</span>{q["stem"]}</div>')
            if with_answers:
                h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{q["answer"]}</p><p><span class="lab">【解析】</span>{q["analyze"]}</p></div>')
            else:
                h.append('<div class="sp0"></div>')
    h.append('</div>')
    h.append('<div class="sec newpage">同步练习 · 平行四边形和梯形</div>')
    emit(TB, with_answers, h, spacer='sps')
    h.append('</div></body></html>')
    return '\n'.join(h)

with open(os.path.join(OUT, '第7课·题目卷.html'), 'w', encoding='utf-8') as f: f.write(build(False))
with open(os.path.join(OUT, '第7课·答案卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
print('HTML done')
