# -*- coding: utf-8 -*-
"""从原书 PDF 抽第五单元（p99-119）做题目卷；解析版整本即本单元，做答案卷。"""
import fitz, os, shutil

SRC = r"D:\workplace\ai-bkb\测试数据\小学数学所有内容\新四上人教版数学同步典例考点讲义\第一套\空白题目\26新版四上同步讲义汇总（原卷版）162页 人教版 .pdf"
ANS = r"D:\workplace\ai-bkb\测试数据\小学数学所有内容\新四上人教版数学同步典例考点讲义\答案\第五单元 平行四边形和梯形（解析版）.pdf"
OUT = r"D:\workplace\ai-bkb-v2\备课\苏俊宇-暑期课\平四梯形专项"
os.makedirs(OUT, exist_ok=True)

# 题目卷：抽 99-119（1-based）
src = fitz.open(SRC)
dst = fitz.open()
dst.insert_pdf(src, from_page=98, to_page=118)
p = os.path.join(OUT, "平行四边形和梯形·专项·原书题目卷.pdf")
dst.save(p)
print("题目卷", dst.page_count, "页 ->", p)
dst.close(); src.close()

# 答案卷：解析版整本
a = fitz.open(ANS)
print("解析版", a.page_count, "页")
head = a[0].get_text().splitlines()
print("首页:", " | ".join([x.strip() for x in head if x.strip()][:4]))
tail = a[a.page_count - 1].get_text().splitlines()
print("末页:", " | ".join([x.strip() for x in tail if x.strip()][:3]))
a.close()
shutil.copy(ANS, os.path.join(OUT, "平行四边形和梯形·专项·原书答案卷（解析版）.pdf"))
print("答案卷已复制")
