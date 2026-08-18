import type { Todo } from './types'

/**
 * 待办列表（数据结构.md D-14 todo 表）。
 *
 * 🔴 这张表与工作台那份「待办」**是两回事，并列不合并**：
 * - 工作台的待办 = **业务现算视图**（卡在人手上的批次：待人工认卷/待终审/故障），机器算出来的，没有表；
 * - 本表 = **自由事项**，人和 agent 都能写：想起来要干的活、欠的债、要问用户的事。
 *
 * 🔴 页面**只读**（你只查看）。增删改走 skill/agent 直接写库 —— 展示台从头到尾不做 CRUD。
 * 🔴 mock 时间全部写死（NOW=2026-08-17），不许用 Date.now()，否则每次走查数字都在跳。
 */
export const todos: Todo[] = [
  {
    id: 'td-001',
    title: 'q-4003 撞名叶子二选一，等你拍板挂哪片',
    detail:
      '机器只有 0.52 的把握：「四则混合运算的运算顺序」与「运算顺序判断」两片叶名字太近。挂错会让这道题在学情分母里跑到别的轨去。',
    line: '录入',
    status: '待办',
    priority: '高',
    due: '2026-08-18',
    ref: 'q-4003',
    createdBy: 'agent',
    createdAt: '2026-08-14',
  },
  {
    id: 'td-002',
    title: '「破十法」要不要新建考点叶',
    detail:
      '一上退位减那批题挂不上现有叶子（置信度 0.41）。新建叶子是动 KG 树的事，得你点头；不建就只能兜底挂到「20 以内退位减法」，学情会糊。',
    line: '录入',
    status: '待办',
    priority: '中',
    ref: 'em-004',
    createdBy: 'agent',
    createdAt: '2026-08-13',
  },
  {
    id: 'td-003',
    title: '小崽子 D3 待终审卡了两天多',
    detail: '2 题存疑（一题末行被涂改看不清、一题纸张折角遮住作答区），要你逐题拍板 √/×/去掉。',
    line: '批改',
    status: '待办',
    priority: '高',
    due: '2026-08-17',
    ref: 'b-jd-3',
    createdBy: 'agent',
    createdAt: '2026-08-14',
  },
  {
    id: 'td-004',
    title: '小铁蛋 D2 故障：无头 session 超时被杀',
    detail: '整页直读到第 5 题无响应，已就地挂起不自动重试。retry 前先确认照片是不是拍糊了。',
    line: '批改',
    status: '进行中',
    priority: '高',
    ref: 'b-td-2',
    createdBy: 'agent',
    createdAt: '2026-08-16',
  },
  {
    id: 'td-005',
    title: 'ib-002 那 10 道手绘几何图逐一核对',
    detail: '整批落在待图审队列，核过才转正。核的是图与讲义原稿是否同一位置、编号方向一致。',
    line: '录入',
    status: '进行中',
    priority: '中',
    due: '2026-08-19',
    ref: 'ib-002',
    createdBy: '人',
    createdAt: '2026-08-11',
  },
  {
    id: 'td-006',
    title: '合刊册的录入模板还没落规则脚本',
    detail: '同一页混排两个来源册的题、题号各自独立，现在靠现切。下次再来一本合刊之前要把切割规则固化。',
    line: '录入',
    status: '待办',
    priority: '低',
    ref: 'it-hekan',
    createdBy: '人',
    createdAt: '2026-08-15',
  },
  {
    id: 'td-007',
    title: '绝对值压轴册出第 6~10 天',
    detail: '前 5 天已交付，学员反馈分类讨论那一支还是漏。第 6~10 天要把 a＝0 单独铺一天。',
    line: '出题',
    status: '待办',
    priority: '中',
    due: '2026-08-20',
    ref: 'af-002',
    createdBy: '人',
    createdAt: '2026-08-16',
  },
  {
    id: 'td-008',
    title: '四上角度专练卷的答案页要不要随卷发',
    detail: '现在默认不随学生卷下发。要问一下你：家长群里发的那版要不要带答案速查页。',
    line: '资料',
    status: '待办',
    priority: '低',
    ref: 'af-003',
    createdBy: 'agent',
    createdAt: '2026-08-17',
  },
  {
    id: 'td-009',
    title: '把 dist 同码两义写进判据库',
    detail: '「dist 在混合运算 = 运算律简算、在整式 = 去括号合并」这条已经印错过一次报告，要落成判据留链。',
    line: '批改',
    status: '已完成',
    priority: '中',
    ref: 'cr-012',
    createdBy: 'agent',
    createdAt: '2026-08-15',
    doneAt: '2026-08-16',
  },
  {
    id: 'td-010',
    title: '录题时顺手把分值也存进题里',
    detail:
      '已取消：分值属于载体位置（同一道题在不同卷里分值可以不同），题上不存分值也不存题号 —— 这是定稿铁律，别再提。',
    line: '录入',
    status: '已取消',
    priority: '低',
    createdBy: '人',
    createdAt: '2026-08-12',
    doneAt: '2026-08-17',
  },
]

/** 按状态取（页面分页签用）；传空数组 = 全部 */
export function todosOf(status: Todo['status'][]): Todo[] {
  return status.length === 0 ? todos : todos.filter((t) => status.includes(t.status))
}

/** 还没做完的（待办 + 进行中）—— 菜单角标 / 工作台提示用同一个口径 */
export function openTodos(): Todo[] {
  return todos.filter((t) => t.status === '待办' || t.status === '进行中')
}

/** 按产线分组计数（页头概览条用） */
export function todoCountByLine(): Record<Todo['line'], number> {
  const acc: Record<Todo['line'], number> = { 录入: 0, 批改: 0, 出题: 0, 资料: 0, 其他: 0 }
  for (const t of openTodos()) acc[t.line] += 1
  return acc
}
