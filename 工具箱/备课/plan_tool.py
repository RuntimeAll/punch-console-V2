# -*- coding: utf-8 -*-
"""课程计划工具（备课线第 0 步的 v2 本地载体）—— `get_plan_detail` 的独立生态等价物。

🔴 v2 零交互：老区备课链靠 teacher-mcp 的 `get_plan_detail(plan_id)` 读系统课程计划，  # 体检:豁免
   v2 不调任何备课帮服务。计划正本改为**纯文本文件**：

       备课/<学生代号>-<批次名>/课程计划.md     （契约 course-plan/v1）

   它就是「第 N 课＝什么主题、哪一天、跟哪条课内进度线」的唯一事实源。
   备课动作前先 `show`，等同于老区那句「跳过=事故」的 get_plan_detail。

用法（--plan 给文件路径；或 --student 按代号在 备课/ 下自解析，命中必须恰一）：
  python 工具箱/备课/plan_tool.py init  --student haohao --title 2026秋一对一 --grade 一年级 --shape 低龄七段
  python 工具箱/备课/plan_tool.py list  --student haohao
  python 工具箱/备课/plan_tool.py show  --student haohao --lesson L7        # ← 第 0 步就跑这条
  python 工具箱/备课/plan_tool.py check --student haohao                    # 格式闸 + 撞主题闸

🔴 五道闸（违例拒收不静默，一切靠闸不靠注释）：
  ① 契约闸：文件头缺 `course-plan/v1` 标记 = 不是计划正本，拒读；
  ② 档头闸：学生代号/年级/课时长/课堂范式/产物根 五项必填；
  ③ 表头闸：课次表九列按**列名**齐备（改列名=改契约，不许挪列序糊弄）；
  ④ 课次闸：课次号形如 L<数字> 且全表唯一；日期 ISO 或 `—`（未排期）；状态在值域内；
  ⑤ 🔴 **撞主题闸**（老区 2026-07-26 实锤事故的机器化）：同一课次的「主题」（＝专项/奥数主题）
     与「课内进度线」（＝课内同步跟的线）**不许同值**——四段范式硬拒，低龄范式只报警
     （低龄课新授本身常就是课内进度，同值合法）。
  ⑥ 改判留痕闸：状态＝`已改判` 的课次，其课次号必须在「变更记录」段里出现过
     （改了计划不记账＝没发生）。

本工具**只读写计划 md，不碰两库**（不写 skill_log；skill 级总账由编排层调
`工具箱/库/log_skill.py` 落）。
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
PLAN_ROOT = ROOT / '备课'
CONTRACT = 'course-plan/v1'

# ── 契约值域（改这里=改契约，同改 SKILL.md 的格式表）────────────────────
COLS = ('课次', '日期', '主题', '思维动作', '课内进度线', '料源', '考点锚', '卷', '状态')
HEAD_REQUIRED = ('学生代号', '年级', '课时长', '课堂范式', '产物根')
HEAD_OPTIONAL = ('教材版本', '学情正本', '现行阶段', '备注')
STATUS = ('待备', '已备', '已上', '已改判', '已取消')
EMPTY = ('', '—', '-', '待定', 'TBD')

# 第 0 步核对表（老区那张「字段→决定什么→教训」原样保留，只换取数动作）
CHECKLIST = [
    ('主题', '本课专项/奥数主题＝教学意图。「吃透课」标记=旧题型二刷，靶心在思维动作，不是撒大网',
     '专项与同步是两条线，别混'),
    ('思维动作', '这节课要练的那个动作（如「盯路程和」）；选题围它转', '撒大网=一节课什么都没吃透'),
    ('课内进度线', '🔴 课内同步的主题，**独立于专项主题**，跟学校/教材进度走',
     '2026-07-26：第7课专项是行程，同步也配成行程，被用户点破「你有看我的课程计划吗」'),
    ('日期', '第 N 课是哪一天，一律以计划为准，绝不按「数场次」「内容像什么」自行推断',
     '2026-07-27：好好计划第六课=应用启蒙Ⅰ，按口头关键词做成「简便运算+找规律」，整套返工'),
    ('料源', '这节课的题从哪来（讲义第N周/用户拍页/kb.db 考点枝/自编）',
     '用户当场给料以用户为准，但偏离要写回本表'),
    ('考点锚', 'kb.db 的 kp.id（逗号分隔）＝取题与学情的分母', '没锚点=学情算不出来'),
    ('卷', '已绑的卷（artifact/paper 指针或 PDF 相对路径），别覆盖丢信息', '重出卷=新卷，旧卷留档不删'),
]

TEMPLATE = """# {code} · {title} · 课程计划

<!-- {contract} -->

> 🔴 本文件＝本条备课线的**计划正本**：第 N 课是什么主题、哪一天、跟哪条课内进度线，只认这里。
> 任何选题/出卷/建课次目录之前先读它（`plan_tool.py show --student {code} --lesson L<N>`）。
> 计划与用户口头指令对不上 → **停下问清楚**，不猜、不硬造、不擅自挪课次。

## 档头

| 项 | 值 |
|---|---|
| 学生代号 | {code} |
| 年级 | {grade} |
| 教材版本 | {textbook} |
| 课时长 | {minutes} |
| 课堂范式 | {shape} |
| 学情正本 | 批改产线/grading.db → student.profile_json（code={code}）+ track |
| 产物根 | 备课/{code}-{title}/ |
| 现行阶段 | 阶段一（照 SKILL 的路线模板填） |

## 课次表

> 🔴 「主题」＝专项/奥数主题；「课内进度线」＝课内同步跟的线。**两列各走各的，不许对齐成一件事**
> （四段范式下同值会被 `check` 硬拒）。未排期的格子填 `—`，不要留空。

| 课次 | 日期 | 主题 | 思维动作 | 课内进度线 | 料源 | 考点锚 | 卷 | 状态 |
|---|---|---|---|---|---|---|---|---|
| L1 | {today} | — | — | — | — | — | — | 待备 |

## 变更记录

> 改了计划（换主题/换日期/换卷）必须在这里补一行，状态改 `已改判`——不记账＝没发生。

| 日期 | 课次 | 改了什么 | 为什么 |
|---|---|---|---|

## 遗留与回收

> 上节课的不足点在哪一课回收；来源＝批改产线的错因或课后反馈单。

| 来源课次 | 不足点 | 计划回收课次 | 状态 |
|---|---|---|---|
"""


def die(msg):
    sys.exit('🔴 ' + msg)


def rel(p):
    """相对 v2 根显示（文件指针一律相对路径）；跳出根就如实原样印。"""
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# ── 解析 ────────────────────────────────────────────────────────────────
def split_row(line):
    """一行 GFM 表格 → 单元格列表（去首尾竖线，不吃转义竖线场景=如实不支持）。"""
    s = line.strip()
    if not s.startswith('|'):
        return None
    s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    return [c.strip() for c in s.split('|')]


def is_sep(cells):
    return bool(cells) and all(re.fullmatch(r':?-{2,}:?', c) for c in cells if c != '')


def read_tables(text):
    """扫出所有 GFM 表 → [(表头单元格, [行单元格…])]，按出现序。"""
    tables, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        head = split_row(lines[i])
        if head and i + 1 < len(lines) and is_sep(split_row(lines[i + 1]) or []):
            rows, j = [], i + 2
            while j < len(lines):
                r = split_row(lines[j])
                if not r:
                    break
                rows.append(r)
                j += 1
            tables.append((head, rows))
            i = j
        else:
            i += 1
    return tables


def load_plan(path):
    """读计划 md → dict(path, head, lessons, changes, carryover, raw)。过闸①②③。"""
    p = Path(path)
    if not p.exists():
        die(f'计划文件不存在：{p}\n   先建：python 工具箱/备课/plan_tool.py init --student <代号> --title <批次名>')
    raw = p.read_text(encoding='utf-8')
    if CONTRACT not in raw:
        die(f'{p} 里找不到契约标记 `{CONTRACT}`——这不是计划正本（或格式被改坏），拒读。')

    head, lessons, changes, carryover = {}, [], [], []
    for cells, rows in read_tables(raw):
        # 档头表：两列「项/值」
        if len(cells) == 2 and cells[0] == '项' and cells[1] == '值':
            for r in rows:
                if len(r) >= 2 and r[0]:
                    head[r[0]] = r[1]
            continue
        # 课次表：按列名认，不认列序
        if '课次' in cells and '课内进度线' in cells:
            idx = {c: i for i, c in enumerate(cells)}
            miss = [c for c in COLS if c not in idx]
            if miss:
                die(f'{p} 课次表缺列：{"、".join(miss)}（列名即契约，改列名先改 plan_tool.COLS）')
            for r in rows:
                if not r or not r[0].strip():
                    continue
                lessons.append({c: (r[idx[c]] if idx[c] < len(r) else '') for c in COLS})
            continue
        if cells[:2] == ['日期', '课次']:
            changes = [r for r in rows if r and r[0].strip()]
            continue
        if cells and cells[0] == '来源课次':
            carryover = [r for r in rows if r and r[0].strip()]
            continue

    miss = [k for k in HEAD_REQUIRED if not head.get(k) or head[k] in EMPTY]
    if miss:
        die(f'{p} 档头必填项缺：{"、".join(miss)}')
    return {'path': p, 'head': head, 'lessons': lessons, 'changes': changes,
            'carryover': carryover, 'raw': raw}


def resolve_plan_path(args):
    if args.plan:
        return Path(args.plan)
    if not args.student:
        die('要么 --plan <路径>，要么 --student <代号>')
    if not PLAN_ROOT.exists():
        die(f'{PLAN_ROOT} 还不存在——先 init 建计划，或用 --plan 指路径')
    hits = []
    for f in sorted(PLAN_ROOT.glob('*/课程计划.md')):
        txt = f.read_text(encoding='utf-8', errors='ignore')
        if CONTRACT not in txt:
            continue
        m = re.search(r'\|\s*学生代号\s*\|\s*([^|]+?)\s*\|', txt)
        if m and m.group(1).strip() == args.student:
            hits.append(f)
    if not hits:
        die(f'备课/ 下没有学生代号={args.student} 的计划（找的是 备课/*/课程计划.md）')
    if len(hits) > 1:
        die('同一代号命中多份计划，用 --plan 指明是哪一份：\n   ' + '\n   '.join(str(h) for h in hits))
    return hits[0]


# ── 闸 ──────────────────────────────────────────────────────────────────
def gate(plan):
    """返回 (errors, warns)。四段范式撞主题=error；低龄范式撞主题=warn。"""
    errors, warns = [], []
    shape = plan['head'].get('课堂范式', '')
    hard_topic_gate = '四段' in shape

    seen = set()
    for L in plan['lessons']:
        no = L['课次'].strip()
        if not re.fullmatch(r'L\d+', no):
            errors.append(f'课次号「{no}」不合式（要 L1 / L07 这种 L+数字）')
        if no in seen:
            errors.append(f'课次号重复：{no}')
        seen.add(no)

        d = L['日期'].strip()
        if d not in EMPTY and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', d):
            errors.append(f'{no} 日期「{d}」不是 ISO（YYYY-MM-DD）或 —')

        st = L['状态'].strip()
        if st not in STATUS:
            errors.append(f'{no} 状态「{st}」不在值域 {STATUS}')

        topic, sync = L['主题'].strip(), L['课内进度线'].strip()
        if topic not in EMPTY and sync not in EMPTY and topic == sync:
            msg = (f'{no} 🔴 撞主题：专项主题与课内进度线同为「{topic}」'
                   f'——课内同步跟计划的课内进度线走，不跟专项配（2026-07-26 事故）')
            (errors if hard_topic_gate else warns).append(msg)

        if st == '已改判' and not any(no in ''.join(r) for r in plan['changes']):
            errors.append(f'{no} 标了「已改判」但「变更记录」里没有它——改了计划必须记一行')

        if st in ('已备', '已上'):
            if L['考点锚'].strip() in EMPTY:
                warns.append(f'{no} 已备/已上但考点锚为空——学情算不出分母')
            if L['卷'].strip() in EMPTY:
                warns.append(f'{no} 已备/已上但没登记卷')
    return errors, warns


# ── 子命令 ──────────────────────────────────────────────────────────────
def cmd_init(args):
    title = args.title or datetime.now().strftime('%Y%m')
    out = Path(args.out) if args.out else PLAN_ROOT / f'{args.student}-{title}' / '课程计划.md'
    if out.exists():
        die(f'已存在，不覆盖：{out}（要改直接编辑它）')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.format(
        code=args.student, title=title, grade=args.grade or '（填）',
        textbook=args.textbook or '（填）', minutes=args.minutes or '90',
        shape=args.shape or '（四段90分钟 / 低龄七段）',
        contract=CONTRACT, today=datetime.now().strftime('%Y-%m-%d')),
        encoding='utf-8')
    print(f'✅ 计划正本已建：{rel(out)}')
    print('   下一步：把课次表按真实排期填满，再 `plan_tool.py check --student %s` 过闸。' % args.student)


def cmd_list(args):
    plan = load_plan(resolve_plan_path(args))
    h = plan['head']
    print(f"计划正本：{rel(plan['path'])}")
    print(f"学生 {h['学生代号']}｜{h['年级']}｜教材 {h.get('教材版本', '—')}｜"
          f"{h['课时长']}ʹ｜范式 {h['课堂范式']}｜阶段 {h.get('现行阶段', '—')}")
    print(f"产物根 {h['产物根']}")
    print('-' * 92)
    print(f"{'课次':<5}{'日期':<12}{'主题':<18}{'课内进度线':<18}{'状态':<7}卷")
    for L in plan['lessons']:
        print(f"{L['课次']:<5}{L['日期']:<12}{L['主题'][:16]:<18}"
              f"{L['课内进度线'][:16]:<18}{L['状态']:<7}{L['卷'][:40]}")
    if plan['carryover']:
        print('\n遗留与回收：')
        for r in plan['carryover']:
            print('  · ' + ' ｜ '.join(r))
    errors, warns = gate(plan)
    for w in warns:
        print('⚠️  ' + w)
    if errors:
        print('\n🔴 计划有 %d 处违例，先 check 修好：' % len(errors))
        for e in errors:
            print('   · ' + e)
        return 1
    return 0


def cmd_show(args):
    plan = load_plan(resolve_plan_path(args))
    no = args.lesson.strip()
    if re.fullmatch(r'\d+', no):
        no = 'L' + no
    hit = [L for L in plan['lessons'] if L['课次'].strip().lstrip('L').lstrip('0') == no.lstrip('L').lstrip('0')]
    if not hit:
        die(f'计划里没有课次 {no}（有的是：{"、".join(L["课次"] for L in plan["lessons"])}）')
    L, h = hit[0], plan['head']

    print('=' * 78)
    print(f"【第 0 步·读计划】{rel(plan['path'])}　→　{L['课次']}")
    print('=' * 78)
    print(f"学生 {h['学生代号']}｜{h['年级']}｜{h['课时长']}ʹ｜范式 {h['课堂范式']}")
    print(f"产物根 {h['产物根']}｜学情正本 {h.get('学情正本', '—')}")
    print('-' * 78)
    for c in COLS:
        print(f'  {c:<6}：{L[c]}')
    print('-' * 78)
    print('🔴 逐项对齐（对不上就停下问，不猜不硬造）：')
    for field, means, lesson in CHECKLIST:
        print(f'  · {field}｜{means}')
        print(f'      教训：{lesson}')
    print('-' * 78)
    carry = [r for r in plan['carryover'] if len(r) >= 3 and r[2].strip().lstrip('L').lstrip('0')
             == L['课次'].strip().lstrip('L').lstrip('0')]
    if carry:
        print('📌 本课要回收的遗留：')
        for r in carry:
            print('   · ' + ' ｜ '.join(r))
    else:
        print('📌 本课无登记的遗留回收项（若上节有不足点，先补进「遗留与回收」再备）')
    errors, warns = gate(plan)
    mine = [m for m in errors + warns if m.startswith(L['课次'] + ' ')]
    for m in mine:
        print('⚠️  ' + m)
    print('=' * 78)
    return 1 if any(m in errors for m in mine) else 0


def cmd_check(args):
    plan = load_plan(resolve_plan_path(args))
    errors, warns = gate(plan)
    print(f"计划：{rel(plan['path'])}　课次 {len(plan['lessons'])} 条")
    for w in warns:
        print('⚠️  ' + w)
    if errors:
        print('🔴 闸未过（%d 条）：' % len(errors))
        for e in errors:
            print('   · ' + e)
        return 1
    print('✅ 计划闸全绿（契约/档头/表头/课次/撞主题/改判留痕 六道）')
    return 0


def main():
    ap = argparse.ArgumentParser(description='课程计划工具（备课线第 0 步载体，get_plan_detail 的 v2 等价物）')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--plan', help='计划 md 路径')
        p.add_argument('--student', help='学生代号（在 备课/*/课程计划.md 里自解析，须恰一）')

    p = sub.add_parser('init', help='建计划正本模板')
    p.add_argument('--student', required=True)
    p.add_argument('--title', help='批次名，如 2026秋一对一')
    p.add_argument('--grade')
    p.add_argument('--textbook')
    p.add_argument('--minutes')
    p.add_argument('--shape', help='课堂范式：四段90分钟 / 低龄七段')
    p.add_argument('--out')
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser('list', help='看整张课次表')
    common(p)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser('show', help='🔴 第 0 步：读某课次蓝本')
    common(p)
    p.add_argument('--lesson', required=True, help='L7 或 7')
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser('check', help='过六道计划闸')
    common(p)
    p.set_defaults(fn=cmd_check)

    args = ap.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == '__main__':
    main()
