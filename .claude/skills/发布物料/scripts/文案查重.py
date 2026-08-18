# -*- coding: utf-8 -*-
"""跨篇文案查重闸 —— 防同质化限流（2026-08-07 立，起因：三升四两册被判重限流）

**为什么要有这道闸**：此前所有闸都只管单篇（字数 / 违禁词 / 买家四问 / 标题长度），
没有一道管「两篇像不像」。结果照口径填模板写出来的两册文案，
**8 字连续片段重合 59%、结构指纹逐位相同、四行逐字一样** —— 平台判重复内容直接限流。

三道判据（任一红灯即 FAIL）：
  ① **8 字连续片段重合率** > 15%
  ② **逐字相同的整行**（>8 字）存在
  ③ **结构指纹相同**（行首形态序列一致 = 一个模子刻的）

🔴 最狠的一条是 ③：换掉所有词但保持「痛点→路线→📅规格→✅特点→📖版本」的顺序，
   ①② 都能过，平台照样判重。**结构必须换，不是换词就行。**

用法：
  python 文案查重.py                       # 查正本全部小红书正文，两两比
  python 文案查重.py <某个发布物料.md> ...   # 查指定文件（可多个）
"""
import itertools
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

MASTER = pathlib.Path(r'D:\workplace\ai-bkb-v2\记录\发布物料正本.md')
NGRAM = 8
MAX_OVERLAP = 0.15
EMO = '📅✅❌👇📌📖✏️🖨️'


def extract(path):
    """取出所有「小红书正文」代码块：含 #标签行、且不是网盘分享语/商品描述"""
    txt = pathlib.Path(path).read_text(encoding='utf-8')
    out = {}
    # 用最近的一个「标题：xxx」给块命名，认不出就用序号
    parts = re.split(r'```', txt)
    title, head = None, None
    for i, seg in enumerate(parts):
        if i % 2 == 0:                                  # 代码块外
            h = re.findall(r'^#{2,4}\s*(.+)$', seg, re.M)
            if h:
                head = h[-1].strip()
            m = re.findall(r'\*\*标题\*\*[：:]\s*(.+)', seg)
            if m:
                title = m[-1].strip()
            continue
        body = re.sub(r'^(powershell|python|bash|json|md)\n', '', seg.lstrip('\n'))
        # 🔴 认「小红书正文」的判据（2026-08-07 改）：原先靠「含 #标签行」认，
        #    标签撤出正文后那条判据全线失效、四篇被静默跳过——闸看着全绿其实一篇没查。
        #    改成排除法：网盘分享语 / 商品描述（一整行，以固定话术开头）/ 命令块，剩下的就是正文。
        if '百度网盘' in body or body.strip().startswith(('cd ', 'python ', '$')):
            continue
        if body.count('\n') < 4:                        # 商品描述是一整行；分享语只有三行
            continue
        name = title or ('%s·无标题' % (head or '块%d' % i))
        while name in out:
            name += '′'
        out[name] = body
        title = None
    return out


def norm(s):
    """归一化：去标签行、去空白、去 emoji —— 比的是「话」，不是排版"""
    s = re.sub(r'#\S+', '', s)
    s = re.sub(r'[%s]' % EMO, '', s)
    return re.sub(r'\s+', '', s)


def grams(s, n=NGRAM):
    s = norm(s)
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def sig(body):
    """结构指纹 = 每行的形态（emoji 种类 / 路线行 / 纯文字 / 引出行）"""
    out = []
    for ln in body.split('\n'):
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        if re.match(r'^(Day\s*\d|第\s*\d+\s*天)', ln):
            out.append('路线')
        elif ln[0] in EMO:
            out.append(ln[0])
        elif ln.endswith('👇'):
            out.append('引')
        else:
            out.append('文')
    return out


def emoji_set(body):
    return {c for c in body if c in EMO}


def main():
    files = sys.argv[1:] or [MASTER]
    copies = {}
    for f in files:
        for k, v in extract(f).items():
            copies['%s' % k] = v
    if len(copies) < 2:
        print('只找到 %d 篇，无从比对' % len(copies))
        return 0

    print('共 %d 篇：' % len(copies))
    for k in copies:
        print('  · %s   结构=%s   emoji=%s'
              % (k, ' '.join(sig(copies[k])), ''.join(sorted(emoji_set(copies[k]))) or '无'))

    fails, pairs = [], []
    for a, b in itertools.combinations(copies, 2):
        ga, gb = grams(copies[a]), grams(copies[b])
        if not ga or not gb:
            continue
        r = len(ga & gb) / min(len(ga), len(gb))
        pairs.append((r, a, b))
        if r > MAX_OVERLAP:
            fails.append('片段重合 %.0f%%：%s × %s' % (r * 100, a, b))
        if sig(copies[a]) == sig(copies[b]):
            fails.append('结构指纹相同：%s × %s（换词没用，必须换骨架）' % (a, b))

    # 🔴 只报越线的 + 最高的几对；120 对全打出来没人看，闸就废了
    pairs.sort(reverse=True)
    print('\n=== 片段重合（%d 字连续，闸线 %d%%）· 只列最高 5 对 ===' % (NGRAM, int(MAX_OVERLAP * 100)))
    for r, a, b in pairs[:5]:
        print('  %s %.0f%%  %s × %s' % ('🔴' if r > MAX_OVERLAP else '🟢', r * 100, a, b))

    print('\n=== 逐字相同的整行 ===')
    lines = {}
    for k, v in copies.items():
        for ln in v.split('\n'):
            ln = ln.strip()
            if len(norm(ln)) > 8 and not ln.startswith('#'):
                lines.setdefault(norm(ln), []).append(k)
    dup = {l: ks for l, ks in lines.items() if len(ks) > 1}
    if not dup:
        print('  🟢 无')
    for l, ks in dup.items():
        print('  🔴 [%s] %s' % ('/'.join(ks), l[:40]))
        fails.append('整行复用：%s' % l[:24])

    print()
    if fails:
        print('🔴 FAIL %d 条：' % len(fails))
        for f in fails:
            print('   - ' + f)
        print('\n改法见 发布物料正本.md §0.1「反同质化」：换风格种子，不是换同义词。')
        return 1
    print('🟢 全绿：无整行复用、无结构撞车、片段重合均在 %d%% 内' % int(MAX_OVERLAP * 100))
    return 0


if __name__ == '__main__':
    sys.exit(main())
