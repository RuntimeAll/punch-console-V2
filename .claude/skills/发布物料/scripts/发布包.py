# -*- coding: utf-8 -*-
r"""按**号**聚合发布包：`_交付/发布包-A号/` 与 `_交付/发布包-B号/`。

    python .claude\skills\发布物料\scripts\发布包.py <册目录>
    python .claude\skills\发布物料\scripts\发布包.py 六上分数乘除法打卡        # 只给册名也认
    python .claude\skills\发布物料\scripts\发布包.py <册目录> --书名 一本通    # 一册多本书时指定

## 🔴 v2 平移标注（2026-08-18）
从老区 `.claude\skills\发布物料\scripts\发布包.py` 平移。**逻辑一字未改**，只改了四处指路：

| # | 老区 | v2 |
|---|---|---|
| ① | 册目录随手放（举一反三产物/打卡/…） | 册目录约定 = `D:\workplace\ai-bkb-v2\产物\打卡\<册名>\`；只给册名时自动补前缀 |
| ② | 往上找 `网盘分发记录\分享链接总表.md` | 往上找 `记录\网盘分发\分享链接总表.md`，找不到再兜底主位绝对路径 |
| ③ | 收尾提示跑 `.claude\skills\每日打卡\templates\AB隔离闸.py` | 改指 `.claude\skills\发布物料\scripts\AB隔离闸.py`（v2 里闸归发布物料） |
| ④ | 「网盘 --force 见 SKILL §3.5」 | 改指 v2 skill「网盘分发」（改版重传必 --force + 验 fs_id 那条铁律的正本） |

册**内**结构约定（`_交付/A版|B版/`、`_交付/小红书图·<书名>/A|B/`、`_交付/发布物料·<书名>.md`）
**原样保留**，与老区一致 —— 这是产线各环共用的握手协议，改一处全线断。
🔴 本脚本只读册目录、只写 `_交付/发布包-*号/`，**不碰 kb.db / grading.db**。

## 🔴 为什么要有这个
产物按**版**（版面骨架）分目录，发布按**号**（账号）做，两者**故意交叉**：

    A 号（老号）→ B 版骨架（无框）→ 成品在 `_交付/B版/`
    B 号（新号）→ A 版骨架（外框）→ 成品在 `_交付/A版/`

交叉是历史分配、改不得（改了两个号的历史版面就对不上）。但它极其反直觉 ——
要发 B 号，第一反应就是去 `B版/` 拿，拿到的却是 A 号那套；
而 `B版/` 里还常躺着 `xxx·题目合集.pdf` 这类**审阅件**（全量拼装、无封面、可能旧标题），
长得又特别像成品。用户 2026-08-10 连着找错两次，第二次差点把 130 页审阅合集发出去。

**光靠注释和口头提醒解决不了这种坑，得把东西摆到正确的名字下面。**

🔴 发布包是**投影不是正本** —— `_交付/A版|B版/` 仍是产物正区，发布包随时可删可重生成。
   书一改就重跑：出书 → 出图（含 `合成封面.py`）→ 本脚本。

## 认的册子结构
    <册>/_交付/A版/<书名>（题目卷|答案卷）.pdf
    <册>/_交付/B版/…                       ← 同名
    <册>/_交付/小红书图·<书名>/A|B/*.png     ← 首图 `0_封面.png` 由 合成封面.py 出
    <册>/_交付/发布物料·<书名>.md           ← 节名是「## A版」「## B版」但**指的是号**
"""
import argparse
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 🔴 v2 主位（唯一运行位）。本脚本在 worktree 里也跑得动：
#    优先按 __file__ 上溯四层拿到所在仓根，兜底才用这个绝对路径。
V2主位 = r'D:\workplace\ai-bkb-v2'
# .../<仓根>/.claude/skills/发布物料/scripts/发布包.py → 上溯 4 层 = 仓根
仓根 = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))
册区 = os.path.join(V2主位, '产物', '打卡')          # 🔴 册目录约定位（运行态只在主位）
总表相对 = os.path.join('记录', '网盘分发', '分享链接总表.md')

# 号 → 用哪一版的骨架（🔴 交叉，见文件头）
号用版 = {'A': 'B版', 'B': 'A版'}
图前缀 = '小红书图·'
物料前缀 = '发布物料·'


def 认册目录(arg):
    """认三种写法：绝对/相对路径、或光一个册名（补 `产物\\打卡\\` 前缀）。

    🔴 只给册名时**必须**落到 `D:\\workplace\\ai-bkb-v2\\产物\\打卡\\<册名>\\` ——
       v2 的产线出品全在那儿，别去别处找同名目录（老区同名册子还在，找过去就是跨生态）。
    """
    if os.path.isdir(arg):
        return os.path.abspath(arg)
    cand = os.path.join(册区, arg)
    if os.path.isdir(cand):
        return cand
    sys.exit('🔴 找不到册目录：%s\n   也不在册区 %s 下 —— 册目录约定 = %s\\<册名>\\'
             % (arg, 册区, 册区))


def 猜书名(deliv, 想要=None):
    """从 `_交付/小红书图·<书名>/` 反推书名。

    一本 → 自动；多本 → 必须指定（**不猜**：一个册子里十几条管线各是独立商品，
    猜错就是把 A 商品的书配上 B 商品的文案发出去）。
    `想要` 支持**子串模糊匹配**（打「一本通」就够，不用敲全名），命中多个仍然报错。
    """
    cands = [d[len(图前缀):] for d in os.listdir(deliv)
             if d.startswith(图前缀) and os.path.isdir(os.path.join(deliv, d))]
    if not cands:
        sys.exit('🔴 %s 下没有 `%s<书名>/` 目录，认不出书名 —— 先出配图，或用 --书名 指定'
                 % (deliv, 图前缀))
    if 想要:
        hit = [c for c in cands if c == 想要] or [c for c in cands if 想要 in c]
        if len(hit) == 1:
            return hit[0]
        if not hit:
            sys.exit('🔴 没有书名含「%s」。这个册子里有：\n   %s'
                     % (想要, '\n   '.join(cands)))
        sys.exit('🔴 「%s」命中 %d 本（%s），说得更具体些' % (想要, len(hit), '、'.join(hit)))
    if len(cands) == 1:
        return cands[0]
    sys.exit('🔴 这个册子有 %d 本书，用 --书名 指定一本（支持子串，如 --书名 一本通）：\n   %s'
             % (len(cands), '\n   '.join(cands)))


def 取文案(md_path, 号):
    """抠出该号那一节 + 全局的网盘分享语与商品描述。

    🔴 物料 md 的节名是「## A版」「## B版」，但**指的是号不是版**
       （历史命名，产线解析器认这个字样，改不得）。
    """
    if not os.path.exists(md_path):
        return None
    md = open(md_path, encoding='utf-8').read()
    m = re.search(r'^## %s版\s*$(.+?)^## ' % 号, md, re.M | re.S)
    if not m:
        return None
    seg = m.group(1)
    标题 = re.search(r'\*\*标题\*\*：(.+)', seg)
    正文 = re.search(r'```\s*\n(.+?)```', seg, re.S)
    话题 = re.search(r'^话题：(.+)', seg, re.M)
    网盘 = re.search(r'```\s*\n(通过百度网盘分享的文件：.+?)```', md, re.S)
    商品 = re.search(r'## 六、商品上架描述.*?```\s*\n(.+?)```', md, re.S)
    out = ['【标题】（复制这一行）\n%s\n' % (标题.group(1).strip() if 标题 else '🔴 缺'),
           '\n【正文】（复制整段）\n%s' % (正文.group(1) if 正文 else '🔴 缺\n'),
           '\n【话题】🔴 在 App 里逐个输入、从下拉选，**不要粘进正文**\n%s\n'
           % (话题.group(1).strip() if 话题 else '🔴 缺')]
    if 网盘:
        out.append('\n【网盘分享语】（一条链接双号共用）\n%s' % 网盘.group(1))
    if 商品:
        out.append('\n【商品上架描述】（上架商品时用，不发笔记）\n%s' % 商品.group(1))
    return ''.join(out)


def 找总表(book):
    """定位 v2 的「分享链接总表」。

    ① 从册目录往上找含 `记录\\网盘分发\\分享链接总表.md` 的那层
       （册在 `产物\\打卡\\<册名>` 时，上溯三层正好是 v2 仓根）；
    ② 再试本脚本所在仓根（worktree 里跑也认）；
    ③ 兜底主位绝对路径 `D:\\workplace\\ai-bkb-v2\\记录\\网盘分发\\分享链接总表.md`。
    """
    d = os.path.abspath(book)
    for _ in range(6):
        cand = os.path.join(d, 总表相对)
        if os.path.exists(cand):
            return cand
        d = os.path.dirname(d)
    for root in (仓根, V2主位):
        cand = os.path.join(root, 总表相对)
        if os.path.exists(cand):
            return cand
    return None


def 查网盘链接(book, 各号文案):
    """把文案里的网盘链接与「分享链接总表」对一遍。

    🔴 为什么要查：买家真正拿到的是网盘里那份 PDF，笔记只是入口 ——
       这一环错了就是**直接发错货，而且错得很安静**。两天内踩到的三种：
         · 改版重传没加 `--force` → 一个字节没传，网盘还是旧版（脚本却报 PASS）
         · 规格变了、目录名还写着老数字 → 换了目录换了链接，物料里却是旧链
         · 建完链忘回填总表 → 下次没人知道这册用的是哪条
    这里能查的是**登记与一致性**（纯文本比对），查不了"网盘上那份是不是最新" ——
    那个只能靠 `--force` + 看 fs_id，见 v2 skill「网盘分发」的三条铁律。
    """
    总表 = 找总表(book)
    链接 = {号: set(re.findall(r'https://pan\.baidu\.com/s/\S+?(?=[\s）)】]|$)', t or ''))
            for 号, t in 各号文案.items()}
    全部 = set().union(*链接.values()) if 链接 else set()
    if not 全部:
        print('  🔴 文案里没有网盘链接 —— 这册还没上网盘？（笔记发出去买家拿不到东西）')
        return 1, True
    # 口径：一册一条链接、双号共用
    if len(全部) > 1:
        print('  🔴 两个号的网盘链接不一致（口径是**一册一条双号共用**）：')
        for 号, s in 链接.items():
            print('     %s号：%s' % (号, '、'.join(sorted(s)) or '（无）'))
        return 1, True
    url = 全部.pop()
    if 总表 is None:
        # 🔴 查不了就说查不了，**别顺着打绿灯** —— 闸装死比闸不存在更危险
        print('  ⚠️ 没找到 记录/网盘分发/分享链接总表.md，**登记核对没做**'
              '（册子不在 %s 下？）' % V2主位)
        return 0, False
    if url.split('?')[0] in open(总表, encoding='utf-8').read():
        print('  🟢 网盘链接已登记在总表：%s' % url)
        return 0, True
    print('  🔴 这条链接**没登记在总表**：%s' % url)
    print('     总表=%s（🔴 网盘唯一指引）。多半是临时链接，或者建完链忘了回填。' % 总表)
    return 1, True


def main():
    ap = argparse.ArgumentParser(description='按号聚合发布包（v2）')
    ap.add_argument('book', help=r'册目录（含 _交付/），或光一个册名（默认在 产物\打卡\ 下找）')
    ap.add_argument('--书名', dest='title', default=None)
    a = ap.parse_args()

    book = 认册目录(a.book)
    deliv = os.path.join(book, '_交付')
    if not os.path.isdir(deliv):
        sys.exit('🔴 没有 %s —— 这个册子还没出交付件？' % deliv)
    title = 猜书名(deliv, a.title)
    md_path = os.path.join(deliv, '%s%s.md' % (物料前缀, title))
    print('发布包　%s　《%s》' % (book, title))

    坏, 各号文案 = 0, {}
    for 号, 版 in 号用版.items():
        pack = os.path.join(deliv, '发布包-%s号' % 号)
        if os.path.isdir(pack):
            shutil.rmtree(pack)          # 先清后建：张数/文件名变过不留孤儿
        os.makedirs(os.path.join(pack, '图'), exist_ok=True)

        n书 = 0
        for 卷 in ('题目卷', '答案卷'):
            src = os.path.join(deliv, 版, '%s（%s）.pdf' % (title, 卷))
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(pack, os.path.basename(src)))
                n书 += 1

        n图, d = 0, os.path.join(deliv, 图前缀 + title, 号)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.lower().endswith('.png'):
                    shutil.copy2(os.path.join(d, f), os.path.join(pack, '图', f))
                    n图 += 1

        txt = 取文案(md_path, 号)
        各号文案[号] = txt
        if txt:
            with open(os.path.join(pack, '文案.txt'), 'w', encoding='utf-8') as fh:
                fh.write('# %s 号发布物料 · %s\n'
                         '# 骨架=%s（产物正区在 _交付/%s/，本目录是投影，可删可重生成）\n'
                         '# 🔴 发布动作用手机 App 人工发，别用任何自动化（封号红线）\n'
                         '# 🔴 两个号错开时间发\n\n' % (号, title, 版, 版))
                fh.write(txt)

        缺 = []
        if n书 != 2:
            缺.append('书 %d/2' % n书)
        if n图 == 0:
            缺.append('图 0 张')
        if not txt:
            缺.append('文案')
        if 缺:
            坏 += 1
        print('  发布包-%s号　书 %d / 图 %d 张 / 文案 %s　（骨架=%s）%s'
              % (号, n书, n图, '✓' if txt else '✗', 版,
                 '　🔴 缺：' + '、'.join(缺) if 缺 else ''))

    print()
    n, 查过链接 = 查网盘链接(book, 各号文案)
    坏 += n

    print('\n  → %s' % deliv)
    if 坏:
        sys.exit('🔴 %d 处不合格 —— 先补齐再发（书/图没出？物料节名对不上？网盘链接没登记？）' % 坏)
    print('  🟢 两个包齐备%s。🔴 发前再跑一次 AB 隔离闸：'
          % ('、网盘链接已登记' if 查过链接 else '（⚠️ 网盘链接登记未核对）'))
    print('     python .claude\\skills\\发布物料\\scripts\\AB隔离闸.py "%s"' % book)


if __name__ == '__main__':
    main()
