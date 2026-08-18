# -*- coding: utf-8 -*-
"""`python -m punchkit` —— 打印模版菜单（骨架 + 学科渲染器）

用法：
    cd .claude/skills/每日打卡/templates
    python -m punchkit                # 全部
    python -m punchkit 科学            # 只看科学能用的骨架
"""
import sys

from . import layouts, renderers

subject = sys.argv[1] if len(sys.argv) > 1 else None
layouts.show(subject=subject)
renderers.show()
