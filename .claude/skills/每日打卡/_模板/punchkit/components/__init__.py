# -*- coding: utf-8 -*-
"""
punchkit.components —— **组件层**（模版三层的最底层：组件 → 版式 → 配方）
=============================================================================

一个组件 = 一个**跨版式通用的版面部件**（页脚、选项列位、公式块这类）。
它自己不出卷，被版式（layouts/）引用；改一处，引用它的版式全体受益。

## 与 layouts / renderers 的分工

    components/  版面部件（页脚、页眉…）    ← 跨版式通用，学科无关
    layouts/     整页骨架（分几节、留白怎么分）
    renderers/   一道题怎么变 HTML          ← 学科相关

## 组件契约

| 名字 | 类型 | 说明 |
|---|---|---|
| `SPEC` | dict | 注册表菜单靠它；必填 key/name/用途/适用/结构 |
| `css(**kw)` | fn → str | 该组件的 CSS（版式把它拼进自己的 CSS） |
| `html(...)` | fn → str | 该组件的 HTML |

用法：

    from punchkit import components
    F = components.get('page_footer')
    CSS = MY_CSS + F.css(inset_x='19mm', bottom='8mm')
    ... F.html(left='第 3 天', watermark='玉米训练营')
"""
from . import page_footer

_REG = {m.SPEC['key']: m for m in (page_footer,)}


def get(key):
    if key not in _REG:
        raise KeyError('没有这个组件：%r；在库的：%s' % (key, sorted(_REG)))
    return _REG[key]


def show():
    print('\n═══ 版面组件菜单 ═══\n')
    for k, m in sorted(_REG.items()):
        s = m.SPEC
        print('● %-14s %s' % (k, s['name']))
        for f in ('用途', '适用', '结构', '旋钮', '用过的版式'):
            if s.get(f):
                print('    %-8s %s' % (f, s[f]))
        print()
