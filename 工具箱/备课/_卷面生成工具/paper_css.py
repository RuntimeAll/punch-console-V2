# -*- coding: utf-8 -*-
"""卷面版式定版（2026-08-02 用户拍板）—— 所有生成器统一 import 这一份，改一处全生效。

🔴 三条硬规矩：
  ① **不许大规模涂色**：标题/答案框一律不用背景填充色块（打印费墨、黑白打印发灰）。
     标题＝黑体加粗＋底横线；答案区＝左侧细竖线，靠留白和线条分区，不靠底色。
  ② **标题里不写题数**（「（4 题）」这类计数一律不出现在卷面上）。
  ③ 题目悬挂缩进：折行与题干首字对齐，不跑到题号底下。
"""

PRINT_CSS = """
@page { size: A4; margin: 14mm 13mm; }
* { box-sizing: border-box; }
body { font-family:"SimSun","Songti SC",serif; font-size:11.5pt; line-height:1.68;
       color:#000; margin:0; }
.doc { max-width:184mm; margin:0 auto; }

h1 { text-align:center; font-family:"SimHei","Microsoft YaHei",sans-serif;
     font-size:19pt; letter-spacing:1px; margin:2mm 0 1.5mm; }
.sub { text-align:center; font-size:10pt; color:#444; margin-bottom:6mm;
       padding-bottom:2mm; border-bottom:0.6pt solid #000; }

/* 段标题（思维题 / 同步奥数 / 同步练习）：居中、无编号、无底色 */
.sec { font-family:"SimHei","Microsoft YaHei",sans-serif; font-size:15pt; text-align:center;
       margin:3mm 0 4mm; padding-bottom:1.2mm; border-bottom:1pt solid #000;
       page-break-after:avoid; }
.newpage { page-break-before:always; }

/* 板块标题：黑体加粗 ＋ 底横线，绝不用色块 */
.blk { font-family:"SimHei","Microsoft YaHei",sans-serif; font-size:12.5pt; font-weight:bold;
       margin:6mm 0 2.5mm; padding-bottom:1mm; border-bottom:0.8pt solid #000;
       page-break-after:avoid; }
.blk:first-of-type { margin-top:2mm; }
.blk .tip { font-family:"SimSun","Songti SC",serif; font-size:10pt; font-weight:normal;
            color:#333; }

/* 知识点切片：跟在板块标题后面，小字＋左侧细竖线，不用底色 */
.learn { border-left:1.6pt solid #666; padding:0.4mm 0 0.4mm 3.2mm; margin:0 0 3mm;
         font-size:10pt; line-height:1.62; color:#222; page-break-inside:avoid; }

/* 题目：悬挂缩进，折行与题干首字对齐 */
.q { margin:0 0 1.5mm; padding-left:7.5mm; text-indent:-7.5mm; page-break-inside:avoid; }
.q .no { font-weight:bold; }
.star { font-size:9.5pt; letter-spacing:-0.5px; margin-right:1mm; }

/* 图：居中、跟题目同缩进层级 */
.fig { text-align:center; margin:2mm 0 1.5mm; page-break-inside:avoid; }
.fig img { max-width:100%; vertical-align:middle; margin:0 2mm; }
.cap { text-align:center; font-size:9.5pt; color:#333; margin:0 0 1mm; }

/* 作答留白档位 */
.big { font-size:12.5pt; line-height:1.9; }
.tight { line-height:1.62; }
.sp { height:13mm; } .spm { height:8mm; } .sps { height:5mm; } .sp0 { height:1mm; }

/* 答案区：无底色，靠左竖线＋留白分区 */
.ansbox { border-left:1.6pt solid #666; padding:0.6mm 0 0.6mm 3.2mm;
          margin:1.2mm 0 3.5mm 7.5mm; page-break-inside:avoid; font-size:10.5pt; }
.ansbox .lab { font-family:"SimHei","Microsoft YaHei",sans-serif; font-weight:bold; color:#000; }
.ansbox p { color:#333; margin:0.5mm 0; }
.ansbox b { color:#000; }

/* 目录表（专项册首页） */
table.toc { width:100%; border-collapse:collapse; font-size:10.5pt; }
table.toc th { font-family:"SimHei",sans-serif; font-weight:bold; text-align:left;
               border-bottom:1pt solid #000; padding:1.8mm 2mm; }
table.toc td { border-bottom:0.4pt solid #bbb; padding:1.8mm 2mm; vertical-align:top; }
table.toc td.c { text-align:center; white-space:nowrap; }
.note { margin-top:6mm; border-left:1.6pt solid #666; padding-left:3.2mm;
        font-size:10pt; color:#333; }
"""
