# -*- coding: utf-8 -*-
"""
punchkit.renderers —— 题型渲染器（**学科相关**的那一层）
========================================================
骨架（`layouts/`）只管「第一节放 10 个格子」，**不认识什么叫口算**。
一道题长什么样、公式怎么排、配图怎么放、答案怎么着色 —— 全在这里。

    from punchkit import renderers
    R = renderers.get('math')       # 数学：MathJax 行内公式
    R = renderers.get('science')    # 科学：文字题干 + 配图 + 选项

## 🔴 一个渲染器要提供什么（契约）

| 名字 | 说明 |
|---|---|
| `SUBJECT` | 学科名，如 `'数学'` / `'科学'` |
| `SLOTS` | dict：槽位名 → 渲染函数 `f(item, i, ans, ctx) -> html`。骨架按槽位名取用 |
| `CSS` | 该学科**额外**需要的 CSS（配图、选项网格等）；骨架 CSS 之外追加，别覆盖骨架的布局 |
| `head(ctx)` | 可选：要往 `<head>` 塞的东西（如数学的 MathJax，科学若无需公式可返回空） |
| `answer_mark(tex_or_html)` | 把「这是答案」这件事标出来（数学=`\\color`/`\\mathbf` 进公式；科学可用 `<b class="a">`） |

🔴 **`answer_mark` 产出的标记必须进 `core.ANSWER_ONLY_TEX`（宏）或
`core.ANSWER_ONLY_CLASSES`（class 令牌）**，否则「题目卷不泄答案」那道闸对该学科失效。
加新学科时**务必回头补这一条**，并用 `core.answer_marks_in(该槽答案卷输出)` 自证非空。

🔴 标记只认**渲染层注入物**（着色宏 / 容器类），不认裸词：题面 md 原文里的
「解：」「答：」是阅读理解类题的正当内容，2026-08-20 已从名单摘除（口径见 core.py §⑥）。

## 为什么数学的答案标记要进公式里

MathJax 渲出来的公式**不吃外层 CSS 的 `font-weight` / `color`**（踩过两次），
所以数学的答案着色只能 `\\color{...}{...}` 或 `\\mathbf{...}` 写进 LaTeX。
科学若不走 MathJax 就没这个限制，普通 `<b>` 即可 —— 这正是要分学科的原因之一。

## 加一个学科

1. 抄 `math.py` → `<学科>.py`，改 `SLOTS` 里每个槽位的渲染
2. 把该学科的答案标记补进 `core.ANSWER_ONLY_MARKS`
3. 在本文件 `_MODULES` 挂一行
4. 🔴 骨架**不用改**（它们的 `SPEC['学科']` 是 `'通用'`）
"""
import importlib

_MODULES = {
    'math': '.math',
    'science': '.science',
    'preschool': '.preschool',      # 学前（幼小衔接）：分解树/看图列式/圆圈填符号，不走 MathJax
}


def get(key):
    if key not in _MODULES:
        raise KeyError('没有渲染器「%s」。可选：%s' % (key, '、'.join(_MODULES)))
    return importlib.import_module(_MODULES[key], __name__)


def show():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print('\n═══ 学科渲染器 ═══\n')
    for k in _MODULES:
        m = get(k)
        print('● %-10s %s' % (k, getattr(m, 'SUBJECT', '?')))
        print('    槽位  %s' % '、'.join(getattr(m, 'SLOTS', {})))
        print('    状态  %s' % getattr(m, 'STATUS', '🟢 可用'))
        print()


if __name__ == '__main__':
    show()
