# -*- coding: utf-8 -*-
"""等差数列巧算·三关思维题（学生挑战卡 + 教师引导卷）——第5课思维题"""
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
    # 高亮框：列3-5（8,9,10 / 15,16,17 / 22,23,24），行1-3
    fx, fy = MX+CW*3, MY+CH*2
    p.append(f'<rect x="{fx}" y="{fy+2}" width="{CW*3}" height="{CH*3}" fill="#1268b322" stroke="#1268b3" stroke-width="2.5" rx="4"/>')
    p.append('</svg>')
    return ''.join(p)

CSS = """
@page { size: A4; margin: 13mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 12pt; line-height: 1.75; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 19pt; margin: 3mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 4mm; }
.lv { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 13pt; margin: 5mm 0 1.5mm; page-break-after: avoid; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.sp { height: 16mm; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 2mm 3mm; margin: 1.5mm 0 3.5mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
.coach { background: #fff8e6; border-left: 3px solid #e6c86e; padding: 2mm 3mm; margin: 1.5mm 0 3.5mm; font-size: 11pt; color: #6b5300; page-break-inside: avoid; }
.coach b { font-family: "SimHei","Microsoft YaHei",sans-serif; }
.foot { text-align: center; color: #999; font-size: 9pt; margin-top: 5mm; }
"""

LEVELS = [
    dict(title='第 1 关 · 小高斯的懒办法',
         stem='两百多年前，10 岁的高斯几秒钟就算出了 1＋2＋3＋…＋99＋100。他没有一个一个加——你能找到他的懒办法吗？答案是多少？',
         fig='', sp=True,
         answer='5050。首尾配对：1＋100＝101，2＋99＝101……共 50 对，101×50＝5050。',
         coach='<b>带法：</b>别急着教，先让他加 30 秒感受"笨办法太慢"，再问"第一个和最后一个加起来是多少？第二个和倒数第二个呢？"让配对自己冒出来。<b>坑：</b>配成多少对容易答 100 对——追问"100 个数两两一组，是几组？"'),
    dict(title='第 2 关 · 配不成对怎么办',
         stem='算一算：3＋7＋11＋15＋…＋95＋99（从 3 开始，每次加 4，一直加到 99）。<br>提示：先想清楚一共有多少个数——再想想，如果个数是单数、配不成整对，有没有更巧的办法？',
         fig='', sp=True,
         answer='1275。项数＝(99－3)÷4＋1＝25 个；25 是单数配不成整对，用更巧的"中间数法"：中间那个数（第 13 个）＝51，和＝51×25＝1275。（配对法也行：(3＋99)×25÷2。）',
         coach='<b>两个坑一个巧：</b>坑① 项数忘＋1（间隔 24 个、数有 25 个——就是植树问题）；坑② 25 个配不成整对，很多孩子卡死。巧＝<b>中间数×个数</b>：等差数列里中间的数正好是"平均个头"。让他先猜中间数是谁，再验证 3 和 99 的平均、7 和 95 的平均都是 51——"人人都向中间看齐"。'),
    dict(title='第 3 关 · 日历上的读心术（压轴）',
         stem='爷爷说："你在日历上随便框一个 3×3 的方框（9 个日期），只要告诉我这 9 个数的和，我立刻说出你框的是哪几天！"<br>（1）研究下图的方框，找出爷爷的秘密；<br>（2）我框了一个方框，9 个数的和是 126——框里最大的日期是几号？<br>（3）9 个数的和可能是 100 吗？为什么？',
         fig=calendar_svg(), sp=True,
         answer='（1）9 个数的和＝正中间的数×9（中间数上下差 7、左右差 1，八个邻居两两配对都补成中间数）；（2）126÷9＝14，中间是 14 号，方框是 6、7、8／13、14、15／20、21、22，最大是 22 号；（3）不可能——和一定是 9 的倍数，100 不是 9 的倍数。',
         coach='<b>本关是"中间数法"的二维升级：</b>横着看每行是等差（差 1），竖着看每列也是等差（差 7），所以全体的"平均个头"就是正中心。让他先用图中方框（8+9+10+15+16+17+22+23+24＝144＝16×9）验证，再自己框一个验证。<b>（2）逆向：</b>先除以 9 找中心，再还原整框——注意中心必须四周都有日期（不能贴边）。<b>（3）判定：</b>是第一次接触"用整除性排除不可能"，点破"读心术＝数学结构"。<b>课后彩蛋：</b>换成 2×2 方框还有类似秘密吗？（和＝4 个数平均×4，但平均数不在日历上——留他想。）'),
]

def build(teacher):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>等差数列·三关思维挑战</title><style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>思维挑战 · 算得快不如算得巧</h1>')
    h.append(f'<div class="sub">第5课 · 等差数列巧算{"　（教师引导卷·含答案与带教提示）" if teacher else ""}</div>')
    for lv in LEVELS:
        h.append(f'<div class="lv">{lv["title"]}</div>')
        h.append(f'<div class="q">{lv["stem"]}</div>')
        if lv['fig']:
            h.append(lv['fig'])
        if teacher:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{lv["answer"]}</p></div>')
            h.append(f'<div class="coach">{lv["coach"]}</div>')
        elif lv.get('sp'):
            h.append('<div class="sp"></div>')
    if teacher:
        h.append('<div class="coach"><b>三关的巧劲一条线：</b>配对（首尾互补）→ 中间数（平均个头）→ 二维中间数＋整除判定（结构读心术）。'
                 '每关都先让他"笨算受挫"再引出巧法，巧才有冲击力。第 3 关直接用手机日历或台历实物更带感。总时长约 15 分钟，放在专项卷之前当开场。</div>')
    h.append('<div class="foot">— 完 —</div></div></body></html>')
    return '\n'.join(h)

with open(os.path.join(OUT, '思维题·三关挑战卡.html'), 'w', encoding='utf-8') as f: f.write(build(False))
with open(os.path.join(OUT, '思维题·三关教师卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
print('HTML done')
