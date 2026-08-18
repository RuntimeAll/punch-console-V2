# -*- coding: utf-8 -*-
"""
punchkit —— 打卡册版式库
========================
造新册时**先来这里选模版**，不要再 fork 别人的 `gen_打卡.py`。

    import sys; sys.path.insert(0, r'D:\\workplace\\ai-bkb-v2\\.claude\\skills\\每日打卡\\_模板')
    from punchkit import core, layouts, renderers

    layouts.show()                    # 看有哪些版面骨架
    layouts.show(subject='科学')      # 只看科学能用的
    renderers.show()                  # 看有哪些学科渲染器

    core.render_book(out_dir=..., stem=..., title=...,
                     layout=layouts.get('boxed_sections'),
                     days=days.DAYS,
                     ctx={'renderer': renderers.get('math'), ...},
                     expect_pages=len(days.DAYS), png=True)

## 两层结构

    版面骨架 layouts/   ← **学科无关**：分几节、有没有边框、留白怎么分、一页几天
              ×
    题型渲染器 renderers/ ← **学科相关**：一道题怎么变成 HTML（数学要 MathJax，科学要配图/选项）

一本册 = 一个骨架 + 一个学科渲染器。同一个骨架，数学能用，科学也能用。

## 册子那边还剩什么

`_源/` 里只留**内容**，不再有版式：
  `qbank.py`（DSL 题库 + verify 闸）· `days.py`（排班表）· `gen_打卡.py`（**瘦到只剩配置**）

## 命令行

    python -m punchkit.layouts        # 骨架菜单
    python -m punchkit.renderers      # 渲染器菜单
"""
from . import core, layouts, renderers   # noqa: F401

__all__ = ['core', 'layouts', 'renderers']
