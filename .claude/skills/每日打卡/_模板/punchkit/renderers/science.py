# -*- coding: utf-8 -*-
"""
punchkit.renderers.science —— 科学题型渲染器
============================================
🔴 **状态：骨架已就位、题型待定**（2026-08-03 立）。
用户已明确「等下我们还要录入科学的打卡」，先把接缝留出来，**但槽位的最终形态必须等真实题源**
——照着数学的槽位硬套科学，必然做出一套没人用的东西（数学的「口算/脱式/解方程」在科学里
一个都不成立）。

## 开工前必须先问清（照 skill §1「三级规格」的科学版）

1. **哪一套教材** —— 浙教版初中科学？教科版小学科学？两者章节体系完全不同。
2. **每天的结构** —— 科学打卡不像计算题能"每天同构"。是
   「概念填空 + 选择 + 实验读图 + 简答」这种固定四节？还是跟课本节次走一节一张？
3. **配图怎么办** —— 科学题大量依赖装置图/曲线图/表格。这是与数学最大的差别：
   数学题面是纯公式（MathJax 现渲），科学题面**可能需要外部图片资产**。
   要先定：图从哪来（题库 `biz_question` 的配图？现画？），本地渲染怎么内联（base64）。
4. **答案形态** —— 科学答案常是一句话/一个词，不是数值，所以
   「独立重算」那套闸在科学线**不成立**，得换成别的质量闸（如与教材原文比对）。

## 已经能定的两条

- **骨架照用不误**：`boxed_sections` / `plain_sections` / `dual_slip` 的 `SPEC['学科']`
  都是 `'通用'`——分几节、有没有边框、留白怎么分，与学科无关。**不要为科学再造骨架。**
- **答案标记不用走 MathJax**：科学题面多半不含公式，普通 `<b class="a">` 就能加粗着色，
  没有数学那个「MathJax 不吃外层 CSS」的限制。
  🔴 **但新标记必须补进 `core.ANSWER_ONLY_CLASSES`**，否则「题目卷不泄答案」那道闸对科学失效
  （`class="a"` 已于 2026-08-20 补登记）。

## 下面是占位实现

槽位名先按最可能的四类摆出来，**每个都会抛 NotImplementedError**——
宁可开工时报错逼人回来对规格，也不要让人以为"科学已经能用了"然后产出一堆错东西。
"""
SUBJECT = '科学'
STATUS = '🔴 待定：槽位需按真实科学题源定稿（见模块 docstring 四问）'

ANSWER_COLOR = '#c0272d'

CSS = """
  /* 科学题面常带配图与选项，这些是数学没有的 */
  .sci-fig { display: block; margin: 1.5mm auto; max-width: 100%; }
  .sci-opts { display: grid; grid-template-columns: repeat(2, 1fr);
              column-gap: 4mm; row-gap: .8mm; margin-top: .8mm; }
  b.a { color: __ANS__; font-weight: bold; }
""".replace('__ANS__', ANSWER_COLOR)


def head(ctx=None):
    return ''


def answer_mark(html):
    """🔴 科学不走 MathJax，普通标签即可。
    class="a" **已登记进 core.ANSWER_ONLY_CLASSES**（2026-08-20 补——此前只在注释里
    写着"必须补进去"而实际没补，闸对科学整个失效，正是"注释谎言"那一类）。"""
    return '<b class="a">%s</b>' % html


def _todo(name):
    def f(it, i, ans, ctx=None):
        raise NotImplementedError(
            '🔴 科学槽位「%s」还没定稿。先按 renderers/science.py 顶部四问对齐规格'
            '（教材版本 / 每天结构 / 配图来源 / 答案形态与质量闸），再来实现。' % name)
    return f


SLOTS = {
    'fill': _todo('fill'),      # 概念填空
    'choice': _todo('choice'),  # 选择题（含选项网格）
    'figure': _todo('figure'),  # 读图/实验装置题
    'short': _todo('short'),    # 简答
}
