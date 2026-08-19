# -*- coding: utf-8 -*-
"""
punchkit.layouts —— 版式注册表（🔴 造新册时**先来这里选**，不要再 fork 别人的 gen_打卡.py）
=============================================================================

## 🔴 两层结构：骨架 × 渲染器（2026-08-03 立，为「科学打卡」预留）

    版面骨架 layouts/<key>.py     ← **学科无关**：分几节、有没有边框、留白怎么分、一页几天
              ×
    题型渲染器 renderers/<学科>.py ← **学科相关**：一道题怎么变成 HTML

一本册 = 选一个骨架 + 挂一个学科渲染器。**同一个骨架，数学能用，科学也能用**——
「一页两纸条」这种排法与学科毫无关系，没道理为科学再造一遍。

    from punchkit import layouts, renderers
    layouts.show()                          # 骨架菜单
    layouts.show(subject='科学')            # 只看科学能用的
    L = layouts.get('dual_slip')
    R = renderers.get('math')               # 或 'science'

## 骨架模块的契约

| 名字 | 类型 | 说明 |
|---|---|---|
| `SPEC` | dict | 见下，**注册表靠它生成菜单**，漏了就上不了菜单 |
| `css(pt=None)` | fn → str | 解析好的 CSS |
| `render_card(i, data, ans, ctx)` | fn → html | 渲一张卡（= 一天；一页两纸条时 = 一页） |
| `guard(html, days, ctx)` | fn，可选 | 骨架自己的闸（如版面宽度估算），只在题目卷跑 |
| `EXTRA_LEAK_MARKS` | tuple，可选 | 该骨架独有的答案卷专有标记 |

`SPEC` 必填：`key / name / 学科 / 长相 / 适合 / 每页 / 槽位 / 数据形状 / 用过的册`。

- **`学科`** 填 `'通用'`（骨架与学科无关，科学也能挂）或具体学科（骨架本身绑死了学科特征）。
  **默认应当是 `'通用'`**——写具体学科前先问一句「这排法换个学科真的不成立吗」。
- **`槽位`** = 这个骨架会摆哪几类题（如 `口算×10 / 竖式×4 / 应用×2`），
  渲染器按槽位名给出 HTML。骨架**不认识**「什么是口算」，它只知道「第一节放 10 个格子」。
- **`数据形状`** 由骨架自己声明并解释，core 不碰——各册 qbank/days 结构本就不同
  （list-of-list / dict-keyed），强行统一等于把所有册的题库重写，不划算。

## 加一个新骨架（=「自动拓宽模版类型」的正规姿势）

1. 抄一份最接近的现有骨架 → `layouts/<新key>.py`，改 CSS 与 `render_card`
2. 填好 `SPEC`（🔴 `学科` 先考虑填 `'通用'`）
3. 在本文件 `_MODULES` 里加一行
4. `python -m punchkit.layouts` 确认菜单里出现了
5. 🔴 **别在册子的 `_源/` 里私长 CSS**——那正是本库要消灭的东西

## 加一个新学科（如科学）

**多半不用新加骨架**，只需 `renderers/<学科>.py` 实现该学科的题型渲染，
再在骨架的 `SPEC['学科']` 确认是 `'通用'`。详见 `renderers/__init__.py`。

## 🔴🔴 本库定位：本地先行，不是过渡方案（2026-08-03 用户拍板）

**先本地快速搭工具和管道 → 用起来 → 用久了 → 稳定了 → 再决定要不要合进产品。**
不是什么功能都要往系统里集成。教训 = 太快上线，结果没什么用、代码还不稳定。

- 🟢 本库是**正规主路**；🟡 上架系统是**可选的后置动作**；⏸️ PRD-017 暂不推进。
- 🔴 **别把"和线上一致"当质量标准**——版式好不好看印出来好不好用。
- `daily_v1` 虽移植自线上 `punch-v1`，但**定制后已不等于线上那套**，按本地需要长。
- 真要上线那天：是「把本地已经稳的版式搬过去」，且**要开 PRD 卡走部署链**。
"""
import importlib

# key → 模块路径（加新骨架在这里挂一行）
# 🔴 DEFAULT = 全库默认模版（2026-08-03 用户拍板）。册子不显式指定 LAYOUT 时用它。
DEFAULT = 'daily_v1'

_MODULES = {
    'daily_v1': '.daily_v1',                  # 🔴 默认：每日一练定版（移植自线上 punch-v1 + 六处定制）
    'dense_sections': '.dense_sections',      # 三上混合运算原生：无框极简·大留白
    'boxed_sections': '.boxed_sections',
    'sync_kaodian': '.sync_kaodian',          # 同步考点型：考点名随天变，跟课本节次走
    'two_col_spread': '.two_col_spread',      # 两列平摊开：一列一节、8~10 道过程题一页
    'preschool_v1': '.preschool_v1',          # 彩边大字·学前：幼小衔接页型，题目自带作答格
    'preschool_v2': '.preschool_v2',          # 通栏节头·学前B版：与 v1 配对做 A/B 双号
    'exam_paper': '.exam_paper',              # A4 真卷：卷头+评分表+大题节标题带分值+题号全卷连号
}

# 尚未迁进本库、但已有可用实现的骨架（登记在册，避免重复造轮子）
# 🔴 迁一个验一个：迁完必须与迁移前的 PDF **文本层逐字比对一致**才算数
#    （boxed_sections 就是这么验的），没验过不许挪进 _MODULES。
_LEGACY = [
    {'key': 'plain_sections', 'name': '无框多节', '学科': '通用',
     '长相': '无边框、纯文字节标题、单行标题带下划线 +（第N天）小字、节多（6 节）',
     '适合': '「计算能力全覆盖」型：口算/竖式/脱式/简便/解方程/应用题一天全过一遍',
     '每页': '1 天',
     '实现在': '举一反三产物/打卡/五上计算强化每日一练/_源/gen_打卡.py',
     '状态': '⚠️ 待迁入本库（含一道**版面宽度闸**很值得一并抽出来：MathJax 行内公式'
             '不换行会直接横向溢出，页数断言查不出）'},
    {'key': 'dual_slip', 'name': '一页两纸条', '学科': '通用',
     '长相': '一页上下两张带框「小纸条」，每张顶部黄底标题条 + 内部蓝色居中小标题',
     '适合': '跟课本节次走的册子：一节一张纸条、题量小、天数多',
     '每页': '**2 天**（页数 = ⌈纸条数÷2⌉，与其余骨架不同）',
     '实现在': '举一反三产物/打卡/五上同步课本小纸条/_源/gen_打卡.py',
     '状态': '⚠️ 待迁入本库（`grid-template-rows:1fr 1fr` 锁两张等高的做法要保留，'
             '那是"两张纸条正好放下一页"的几何保证）'},
    {'key': 'flat_spread', 'name': '平摊开', '学科': '通用',
     '长相': '整页只 5 题、每题均分留白（约 50mm）、单行大标题、无小节',
     '适合': '化简求值/解方程这类**题少过程长**、要写完整步骤的册子',
     '实现在': '举一反三产物/打卡/七上整式化简求值打卡/_源/gen_打卡.py',
     '状态': '⚠️ 待迁入本库'},
    {'key': 'textbook_spread', 'name': '教辅平摊开', '学科': '通用',
     '长相': '红色小节标题 + 两列小问 + 每题等高留白；右上角教材版本角标、页脚页码与署名。'
             '🆕 **两个范式共用这一页型**：'
             'A「题型分组」= 教辅原生（「专项训练一　两数相加」+ 题组行「1. 口算：」，'
             '口算带填空横线）；'
             'B「考点分组」= 讲义同步练习（一考点一节，红标题后跟一条口诀，'
             '🔴 全大题不留横线，逼出完整过程）',
     '适合': '照实体教辅页型的整章计算册（范式 A）；跟课本法则走的单元同步打卡（范式 B）',
     '槽位': '范式 B = 4 考点 × 3 题（2 易 1 中），多项长题面的考点走单列 cols=1 + 加大 w',
     '数据形状': "范式 A：card['secs']；范式 B：card['kaodian'] = "
                 "[{'name','tip','ops','style','cols','w'}, ...] → F.kaodian_secs() 摊开",
     '用过的册': '七上整式的加减打卡 等（范式 A）；七上第二单元打卡册（人教版）（范式 B 首用）',
     '实现在': '举一反三产物/_模板/gen_平摊打卡模板.py（已通用化，可直接 import）',
     '状态': '🟡 已通用化，未并入本库'},
]


def get(key=None):
    """取骨架模块。key 省略 = 默认模版（DEFAULT）。不存在时报错并列出全部可选项。"""
    key = key or DEFAULT
    if key not in _MODULES:
        legacy = {d['key']: d for d in _LEGACY}
        if key in legacy:
            raise KeyError('「%s」尚未迁入本库，现有实现在：%s'
                           % (key, legacy[key]['实现在']))
        raise KeyError('没有骨架「%s」。可选：%s（另有待迁：%s）'
                       % (key, '、'.join(_MODULES), '、'.join(d['key'] for d in _LEGACY)))
    return importlib.import_module(_MODULES[key], __name__)


def all_specs():
    out = []
    for k in _MODULES:
        s = dict(get(k).SPEC)
        s.setdefault('状态', '🔴 在库·**默认**' if k == DEFAULT else '🟢 在库')
        out.append(s)
    return out + [dict(d) for d in _LEGACY]


def show(subject=None):
    """打印骨架菜单。subject 给定时只列「通用」+ 该学科。"""
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    specs = all_specs()
    if subject:
        specs = [s for s in specs if s.get('学科') in ('通用', subject)]
    print('\n═══ 打卡版面骨架菜单%s ═══\n' % ('（学科：%s）' % subject if subject else ''))
    for s in specs:
        print('● %-16s %-12s [%s]  %s'
              % (s['key'], s.get('name', ''), s.get('学科', '?'), s.get('状态', '')))
        for f in ('长相', '适合', '每页', '槽位', '旋钮', '数据形状', '用过的册', '实现在'):
            if s.get(f):
                print('    %-6s %s' % (f, s[f]))
        print()
    print('骨架是学科无关的：选好骨架后再挂学科渲染器 —— renderers.get("math"/"science")')
    print('加新骨架：抄最近的一份 → 改 CSS/render_card → 填 SPEC → 在 layouts/__init__.py 挂一行\n')


if __name__ == '__main__':
    show()
