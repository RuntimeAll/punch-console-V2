# -*- coding: utf-8 -*-
"""钉子板五关探究：皮筋围正方形（学生挑战卡 + 教师引导卷）"""
import os

OUT = r'D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\教具-钉子板探究-20260714'
os.makedirs(OUT, exist_ok=True)

SP = 34; M = 22; R = 4

def grid(n, bands=(), dashed=(), w=None):
    """n×n 钉阵 SVG。bands=[(color,[(x,y)..])]；dashed=虚线多边形；坐标左下为(0,0)"""
    size = M*2 + SP*(n-1)
    def px(p): return (M + p[0]*SP, M + (n-1-p[1])*SP)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}" style="margin:2mm 6mm 2mm 2mm;vertical-align:top">']
    for color, pts in dashed:
        s = ' '.join(f'{px(p)[0]},{px(p)[1]}' for p in pts)
        parts.append(f'<polygon points="{s}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="6 4"/>')
    for color, pts in bands:
        s = ' '.join(f'{px(p)[0]},{px(p)[1]}' for p in pts)
        parts.append(f'<polygon points="{s}" fill="{color}22" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>')
    for i in range(n):
        for j in range(n):
            x, y = px((i, j))
            parts.append(f'<circle cx="{x}" cy="{y}" r="{R}" fill="#4a4a4a"/>')
    parts.append('</svg>')
    return ''.join(parts)

F1 = grid(3, bands=[('#c0392b', [(0,0),(1,0),(1,1),(0,1)])])
F2 = grid(3, bands=[('#1268b3', [(1,0),(2,1),(1,2),(0,1)])])
F3 = grid(4) + grid(4)
F4 = grid(5, bands=[('#1e8449', [(1,0),(3,1),(2,3),(0,2)])], dashed=[('#999', [(0,0),(3,0),(3,3),(0,3)])])

CSS = """
@page { size: A4; margin: 13mm 12mm; }
* { box-sizing: border-box; }
body { font-family: "SimSun","Songti SC",serif; font-size: 12pt; line-height: 1.75; color: #111; margin: 0; }
.doc { max-width: 186mm; margin: 0 auto; }
h1 { text-align: center; font-family: "SimHei","Microsoft YaHei",sans-serif; font-size: 19pt; margin: 3mm 0 1mm; }
.sub { text-align: center; color: #555; font-size: 10.5pt; margin-bottom: 4mm; }
.lv { font-family: "SimHei","Microsoft YaHei",sans-serif; color: #1268b3; font-size: 13pt; margin: 5mm 0 1.5mm; page-break-after: avoid; }
.q { margin: 0 0 1.5mm; page-break-inside: avoid; }
.rule { background: #eef7ee; border-left: 3px solid #7cb87c; padding: 2mm 3mm; margin: 2mm 0 3mm; font-size: 11pt; }
.ansbox { background: #e8f1fb; border-left: 3px solid #9ec5e8; padding: 2mm 3mm; margin: 1.5mm 0 3.5mm; page-break-inside: avoid; }
.ansbox .lab { color: #c00000; font-weight: bold; font-family: "SimHei","Microsoft YaHei",sans-serif; }
.ansbox p { color: #c00000; margin: 0.5mm 0; }
.coach { background: #fff8e6; border-left: 3px solid #e6c86e; padding: 2mm 3mm; margin: 1.5mm 0 3.5mm; font-size: 11pt; color: #6b5300; page-break-inside: avoid; }
.coach b { font-family: "SimHei","Microsoft YaHei",sans-serif; }
.figrow { display: block; }
.foot { text-align: center; color: #999; font-size: 9pt; margin-top: 5mm; }
"""

INTRO = ('<div class="rule">🎯 玩法约定：皮筋套在钉子上围图形，正方形的<b>四个角必须都挂在钉子上</b>。'
         '斜着放的正方形也算正方形！每一关先动手围，再回答问题。</div>')

LEVELS = [
    dict(title='第 1 关 · 正着围（热身）',
         stem='在钉板左下角的 3×3 钉阵（9 颗钉）里，围出所有<b>正着放</b>的正方形。一共有几个？',
         fig=F1,
         answer='5 个：小正方形（1×1）4 个＋大正方形（2×2）1 个。',
         coach='<b>带法：</b>让他先随便围，再问"怎么保证一个不漏？"逼出按大小分类数（先数小的、再数大的）——这就是有序枚举。<b>常见错：</b>只数出 4 个小的，忘了大的。'),
    dict(title='第 2 关 · 歪着也行',
         stem='还是这个 3×3 钉阵——除了正着放的，还能围出<b>斜着放</b>的正方形吗？找出来，并说明它为什么是正方形。加上它，3×3 钉阵里一共有几个正方形？',
         fig=F2,
         answer='能！四个"边中点"的钉子围成 1 个斜正方形（四条边一样长、四个角都是直角）。加上第 1 关的 5 个，共 6 个。',
         coach='<b>坑点（本关灵魂）：</b>孩子普遍认为正方形必须"正着放"。让他用皮筋量四条边（都是小方格的对角线，一样长），再用三角尺角验证直角。<b>追问：</b>它的面积是多少？（割补：外面 2×2＝4，减 4 个半格三角形＝2 个小方格）——为第 4 关埋伏笔。'),
    dict(title='第 3 关 · 有序大扫荡',
         stem='把范围扩大到 4×4 钉阵（16 颗钉）。正着放＋斜着放的正方形<b>全部</b>数出来，一共多少个？要求：说出你的"不重不漏"清点法。',
         fig=F3,
         answer='20 个。正放：1×1 有 9 个、2×2 有 4 个、3×3 有 1 个，共 14 个；斜放：藏在每个 2×2 框里的斜正方形 4 个＋藏在 3×3 框里的"长斜"正方形（往右歪、往左歪各 1）2 个，共 6 个。14＋6＝20。',
         coach='<b>带法：</b>关键一步是把斜正方形"装进外接的正方形框"里看——每个斜正方形都恰好卡在一个正放的框里。先数框，再看每种框里藏几个斜的。<b>常见错：</b>①漏掉 3×3 框里的两个"长斜"；②左歪右歪当成同一个。数完让他把 20 个按框分类报账，报不齐就回去补。'),
    dict(title='第 4 关 · 造一个"5"出来（构造）',
         stem='在 5×5 钉阵上，围出一个面积<b>恰好等于 5 个小方格</b>的正方形（提示：它一定是斜的），并用"割补法"证明它的面积真的是 5。这样的正方形在 5×5 钉阵上一共能围出几个位置？',
         fig=F4,
         answer='围法：从一颗钉出发"横 2 竖 1"地取四个顶点（如图）。证明：它的外接框是 3×3＝9 个小方格，四角剪掉 4 个两格小三角形（每个面积 1），9－4＝5。位置共 4 个（外接 3×3 框在 5×5 钉阵上能放 4 个位置）。',
         coach='<b>坑点：</b>面积不能数钉子，要用割补——这正好接他前面学的"平移法/割补"。<b>验证仪式：</b>让他先猜面积（多半猜 4 或 9），再割补打脸。<b>延伸问：</b>能不能造面积是 2 的？（第 2 关那个就是）面积 10 呢？（横 3 竖 1，外接 4×4＝16－4×1.5×2…留他课后想）'),
    dict(title='第 5 关 · 终极清点（压轴）',
         stem='5×5 钉阵（25 颗钉）上，正着放＋斜着放的正方形<b>总共</b>有多少个？（提示：用第 3 关的"外接框"办法——先数正放的框，再看每种框里藏几个斜的。）',
         fig=grid(5),
         answer='50 个。正放的框：1×1 有 16、2×2 有 9、3×3 有 4、4×4 有 1，共 30 个；斜的挂在框上：每个 2×2 框藏 1 个（9 个）、每个 3×3 框藏 2 个（8 个）、每个 4×4 框藏 3 个（3 个），共 20 个。30＋20＝50。',
         coach='<b>结构之美（一定点破）：</b>每个 s×s 的框里恰好住着 s 个正方形——1 个正的＋(s－1) 个斜的（斜的顶点在框边上滑动，滑几步就有几个）。让他自己发现"框越大藏得越多"的规律，而不是背数。<b>教师彩蛋：</b>整块 8×8 大板总共 336 个（49×1＋36×2＋25×3＋16×4＋9×5＋4×6＋1×7），别当场数，可以当"下次挑战"悬念。'),
]

def build(teacher):
    h = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>钉子板探究·皮筋围正方形</title><style>{CSS}</style></head><body><div class="doc">']
    h.append('<h1>钉子板探究 · 皮筋围正方形五关</h1>')
    h.append(f'<div class="sub">教具：18×18cm 实木钉子板＋彩色皮筋{"　（教师引导卷·含答案与带教提示）" if teacher else ""}</div>')
    h.append(INTRO)
    for lv in LEVELS:
        h.append(f'<div class="lv">{lv["title"]}</div>')
        h.append(f'<div class="q">{lv["stem"]}</div>')
        h.append(f'<div class="figrow">{lv["fig"]}</div>')
        if teacher:
            h.append(f'<div class="ansbox"><p><span class="lab">【答案】</span>{lv["answer"]}</p></div>')
            h.append(f'<div class="coach">{lv["coach"]}</div>')
    if teacher:
        h.append('<div class="coach"><b>整场节奏建议（约 25-30 分钟）：</b>第 1、2 关各 4 分钟（热身＋破"正方形必须正着放"的执念）；'
                 '第 3 关 8 分钟（本场核心，逼出外接框方法）；第 4 关 6 分钟（动手构造最有成就感，皮筋换个颜色）；'
                 '第 5 关做不完可以只立框架当悬念。全程让他动手围、你只问"怎么保证不漏？"。'
                 '与课程的暗线：有序枚举（第4课思维动作）→ 割补求面积（同步奥数学过）→ 图形计数（第11课预热）。</div>')
    h.append('<div class="foot">— 完 —</div></div></body></html>')
    return '\n'.join(h)

with open(os.path.join(OUT, '学生挑战卡.html'), 'w', encoding='utf-8') as f: f.write(build(False))
with open(os.path.join(OUT, '教师引导卷.html'), 'w', encoding='utf-8') as f: f.write(build(True))
print('HTML done')
