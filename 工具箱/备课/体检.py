# -*- coding: utf-8 -*-
"""备课线代码体检闸 —— 平移件的独立生态合规扫描
==============================================================================
🔴 为什么要有这道闸：备课线代码是从老区整体平移进来的，带着两类"回头路"：
  ① **prod 直连**（www.jpjia.cn / teacher-mcp / book-server / localhost:9290 / 凭据文件）
     ——正面违反 v2 第一原则「独立生态零交互」；
  ② **老区绝对路径**（D:\\workplace\\ai-bkb\\...）——直跑会往**只读的老区**写文件，
     污染老区 = 违反「老区只读」。
一次平移清干净了不等于以后干净：新拷进来的脚本、改了一半的脚本随时会带回来，
所以这是**常驻闸**，不是一次性清理脚本（靠闸不靠注释）。

用法：
    python 工具箱/备课/体检.py            # 扫 工具箱/备课/ 与 备课/，有违规 exit 1
    python 工具箱/备课/体检.py --fix-path  # 仅自动改「老区绝对路径→v2 对应路径」，prod 件一律人工处置
"""
import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = [ROOT / '工具箱' / '备课', ROOT / '备课']

OLD_ROOT = r'D:\workplace\ai-bkb'
# ① prod/老区服务直连（一律人工处置，不自动改）
PROD_PAT = re.compile(
    r'jpjia\.cn|teacher-mcp|book-server|localhost:929\d|127\.0\.0\.1:929\d|'
    r'RUOYI_BASE_URL|book-ai\\password|teacher-prod', re.I)
# ② 老区绝对路径写入（可自动改指 v2）
PATH_PAT = re.compile(r'D:\\+workplace\\+ai-bkb\\+备课产物\\+')
# ③ 老区其它绝对路径（读老区素材=合法只读，仅报不改）
READ_PAT = re.compile(r'D:\\+workplace\\+ai-bkb\\+(?!备课产物)')


SELF = Path(__file__).resolve()
EXEMPT = '体检:豁免'          # 行尾标此记号 = 说明性提及，不是真调用（人工判过才准标）


def scan(fix_path=False):
    prod, writes, reads, fixed = [], [], [], []
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for p in d.rglob('*.py'):
            if p.resolve() == SELF:          # 闸自己的正则串不算违规
                continue
            try:
                src = p.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            rel = p.relative_to(ROOT)
            for i, line in enumerate(src.splitlines(), 1):
                if PROD_PAT.search(line) and EXEMPT not in line:
                    prod.append((rel, i, line.strip()[:90]))
            if PATH_PAT.search(src):
                for i, line in enumerate(src.splitlines(), 1):
                    if PATH_PAT.search(line):
                        writes.append((rel, i, line.strip()[:90]))
                if fix_path:
                    # 🔴 lambda 替换：新路径里的反斜杠会被 re 当转义序列吃掉（实测炸 bad escape）
                    new = str(ROOT / '备课') + '\\'
                    p.write_text(PATH_PAT.sub(lambda m: new, src), encoding='utf-8')
                    fixed.append(rel)
            for i, line in enumerate(src.splitlines(), 1):
                if READ_PAT.search(line):
                    reads.append((rel, i, line.strip()[:90]))
    return prod, writes, reads, fixed


def main():
    ap = argparse.ArgumentParser(description='备课线代码体检闸')
    ap.add_argument('--fix-path', action='store_true',
                    help='把老区备课产物绝对路径改指 v2 备课/（prod 件不动）')
    a = ap.parse_args()

    prod, writes, reads, fixed = scan(a.fix_path)

    print('=' * 78)
    if fixed:
        print('🔧 已改路径的文件 %d 个：' % len(fixed))
        for f in sorted(set(map(str, fixed))):
            print('   ', f)
        prod, writes, reads, _ = scan(False)   # 改完重扫，报现状

    print('① prod/老区服务直连（🔴 零交互红线，必须人工处置）：%d 处' % len(prod))
    for rel, i, line in prod:
        print(f'   {rel}:{i}  {line}')
    print('② 往老区写的绝对路径（🔴 老区只读，--fix-path 可自动改）：%d 处' % len(writes))
    for rel, i, line in writes:
        print(f'   {rel}:{i}  {line}')
    print('③ 读老区素材的绝对路径（合法只读，仅报备）：%d 处' % len(reads))
    for rel, i, line in reads[:12]:
        print(f'   {rel}:{i}  {line}')
    if len(reads) > 12:
        print('    …另 %d 处' % (len(reads) - 12))

    bad = len(prod) + len(writes)
    print('=' * 78)
    if bad:
        print('🔴 体检不过：①+② 共 %d 处违规' % bad)
        return 1
    print('🟢 体检通过：无 prod 直连、无往老区写的路径'
          '（读老区素材 %d 处属合法只读）' % len(reads))
    return 0


if __name__ == '__main__':
    sys.exit(main())
