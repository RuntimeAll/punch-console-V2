import type { CauseDeposit, ErrorCause } from './types'

/**
 * mock 错因词表 + 批改沉淀。
 *
 * 🔴 走查判词原话：**学生批改后的沉淀 = 精华**。一张卷子批完，分数是一次性的，
 * 真正留得下来的是「这孩子在哪类错误上反复栽跟头」。所以这里分两层：
 * - errorCauses  = 词表层（全局唯一一份，低频维护，改一次影响全部历史沉淀的归类）
 * - causeDeposits = 事实层（一条 = 某学员某轨某天某题命中了某条错因，只增不改）
 *
 * 🔴 铁律③照旧管着这里：每条 deposit 自带 track，按错因汇总时**只做计数**，
 * 绝不把不同轨的沉淀拉平算正确率、更不画成一条跨轨趋势线。
 */
export const errorCauses: ErrorCause[] = [
  {
    id: 'ec-sign',
    name: '符号处理错',
    definition:
      '去括号 / 移项 / 除法转乘法时正负号丢失或取反，数值运算本身没错。判定只认**第一处**符号出错的行，之后被带偏的连带错误不重复计入。',
    kpNames: ['有理数加减混合运算', '符号法则', '去括号与添括号', '绝对值的化简'],
    mappedCodes: ['E-SIGN-01', 'E-SIGN-02', 'E-SIGN-07'],
  },
  {
    id: 'ec-order',
    name: '运算顺序错',
    definition:
      '同级运算不按从左往右算，或先算了括号外的乘除。特征是**每一步单看都对、整体答案错**——这类错最容易被「看着都会」蒙混过去。',
    kpNames: ['四则混合运算的运算顺序', '运算顺序判断', '有理数乘除混合运算'],
    mappedCodes: ['E-ORDER-01', 'E-ORDER-03'],
  },
  {
    id: 'ec-carry',
    name: '进退位错',
    definition:
      '竖式笔算里进位没往上加、或退位后被减数忘记减 1。错位固定落在某一个数位上，方法与符号都对，只是这一位算漏了。',
    kpNames: ['三位数乘两位数的计算', '三位数除以两位数的计算', '20 以内退位减法'],
    mappedCodes: ['E-CARRY-01', 'E-CARRY-02', 'E-BORROW-01'],
  },
  {
    id: 'ec-copy',
    name: '誊写笔误',
    definition:
      '题面抄错，或上一行的数抄到下一行时抄错，方法与运算全对。🔴 判定口径：**按学生自己抄下来的题面核算**——抄错了但按抄错的题算对了，判对，只记一条誊写提醒，不算错题。kpNames 为空 = 跨考点通用错因。',
    kpNames: [],
    mappedCodes: ['E-COPY-01', 'E-COPY-02'],
  },
  {
    id: 'ec-concept',
    name: '概念混淆',
    definition:
      '把两个相邻概念当成一个用：(-2)³ 与 -2³、梯形的高与斜腰、平行与垂直、除以 a 与乘 a。属于知识性错误，**不是手滑**，讲一遍就能消一批。',
    kpNames: ['乘方与混合运算', '梯形的特征与分类', '平行与垂直的判断', '多边形的内角和问题'],
    mappedCodes: ['E-CONCEPT-02', 'E-CONCEPT-05'],
  },
  {
    id: 'ec-miss',
    name: '漏项',
    definition:
      '分类讨论少写一种情况、分配律展开漏乘一项、多小问只答了前半。已写的部分是对的，问题在于**没写完**。',
    kpNames: ['含字母的绝对值化简', '乘法分配律的应用', '分类讨论'],
    mappedCodes: ['E-MISS-01', 'E-MISS-04'],
  },
]

/**
 * mock 批改沉淀。
 * 🔴 每条都对得上 students.ts 里真实存在的学员 / 轨 / 天 / 题号——
 * 走查时可以从错因管理页点回批改批次抽屉，两边说的必须是同一件事。
 */
export const causeDeposits: CauseDeposit[] = [
  // ── 小崽子 · 七上混合运算（已完结 6 天）──────────────────
  { date: '2026-07-14', student: '小崽子', track: '七上混合运算', dayInTrack: 1, qno: 3, causeId: 'ec-sign',
    note: '括号内先算这一步对了，但把 -(3-8) 抄成 -(3+8)，符号在抄的时候翻了' },
  { date: '2026-07-14', student: '小崽子', track: '七上混合运算', dayInTrack: 1, qno: 8, causeId: 'ec-carry',
    note: '竖式 36×24 的十位进位漏加，写成 828（应为 864）；方法与符号都对，只错这一位' },
  { date: '2026-07-14', student: '小崽子', track: '七上混合运算', dayInTrack: 1, qno: 18, causeId: 'ec-order',
    note: '先算了乘法再算乘方，2×3² 算成 (2×3)²＝36；乘方是第一级，必须先算' },
  { date: '2026-07-15', student: '小崽子', track: '七上混合运算', dayInTrack: 2, qno: 6, causeId: 'ec-miss',
    note: '分配律展开只乘了括号里第一项，-2×(5-7) 写成 -10-7；漏乘不是符号错，归漏项' },
  { date: '2026-07-16', student: '小崽子', track: '七上混合运算', dayInTrack: 3, qno: 2, causeId: 'ec-sign',
    note: '第二行起负号整体丢失，后面三行全是连带错——按口径只记这一条，不逐行计' },
  { date: '2026-07-16', student: '小崽子', track: '七上混合运算', dayInTrack: 3, qno: 5, causeId: 'ec-order',
    note: '24÷4×2 算成 24÷8＝3；同级运算擅自把后面的乘法先算了' },
  { date: '2026-07-16', student: '小崽子', track: '七上混合运算', dayInTrack: 3, qno: 8, causeId: 'ec-concept',
    note: '除号改乘号后没取倒数，÷(2/3) 写成 ×(2/3)；这是「除以 a ＝ 乘 a 的倒数」没立住，属概念' },
  { date: '2026-07-16', student: '小崽子', track: '七上混合运算', dayInTrack: 3, qno: 14, causeId: 'ec-sign',
    note: '连续减法没变加，5-(-9)-2 的第一个减号照抄成减，后面全歪' },
  { date: '2026-07-17', student: '小崽子', track: '七上混合运算', dayInTrack: 4, qno: 9, causeId: 'ec-concept',
    note: '(-2)³ 与 -2³ 混淆，两处都按 -8 算；讲过一次仍复发，建议进错题靶子' },
  { date: '2026-07-18', student: '小崽子', track: '七上混合运算', dayInTrack: 5, qno: 4, causeId: 'ec-sign',
    note: '通分后分子没加括号，(a-b)/2 展开成 a-b/2；括号一丢符号跟着错' },

  // ── 小崽子 · 绝对值化简求值（进行中）──────────────────────
  { date: '2026-08-12', student: '小崽子', track: '绝对值化简求值', dayInTrack: 1, qno: 3, causeId: 'ec-miss',
    note: '没讨论 a 的正负直接去绝对值，只写了 a>0 一种；分类讨论少一支＝漏项' },
  { date: '2026-08-12', student: '小崽子', track: '绝对值化简求值', dayInTrack: 1, qno: 7, causeId: 'ec-concept',
    note: '数轴上点的位置判断错，把 -3 画在 -2 右边；数轴方向这个概念还没稳' },
  { date: '2026-08-13', student: '小崽子', track: '绝对值化简求值', dayInTrack: 2, qno: 5, causeId: 'ec-miss',
    note: '分类讨论只写了一种情况（与 8-12 第 3 题同型，两天内复发）' },
  { date: '2026-08-13', student: '小崽子', track: '绝对值化简求值', dayInTrack: 2, qno: 10, causeId: 'ec-miss',
    note: '化简后没合并同类项就收尾，答案停在 2a-3a+5；步骤对但没写完' },

  // ── 洛天熙 · 有理数混合运算（进行中）────────────────────
  { date: '2026-08-13', student: '洛天熙', track: '有理数混合运算', dayInTrack: 1, qno: 4, causeId: 'ec-sign',
    note: '去括号变号只改了第一项，-(3-5+2) 写成 -3-5+2' },
  { date: '2026-08-13', student: '洛天熙', track: '有理数混合运算', dayInTrack: 1, qno: 6, causeId: 'ec-copy',
    note: '题单 5-(-9)-2 誊成 5-(-9-2)，按题单核算无误，判对记誊写提醒' },
  { date: '2026-08-13', student: '洛天熙', track: '有理数混合运算', dayInTrack: 1, qno: 9, causeId: 'ec-concept',
    note: '乘方底数取错，-3² 当成 (-3)²；与小崽子 7-17 那条是同一类，可以合并讲' },
]

/** 按 id 取错因；找不到返回 undefined */
export function findErrorCause(id: string): ErrorCause | undefined {
  return errorCauses.find((c) => c.id === id)
}

/**
 * 每条错因的沉淀条数（错因管理页的主表就吃这个口径）。
 * 🔴 只计数、不算率——跨轨算正确率是禁区。
 */
export function depositCountByCause(): Record<string, number> {
  const acc: Record<string, number> = {}
  for (const c of errorCauses) acc[c.id] = 0
  for (const d of causeDeposits) acc[d.causeId] = (acc[d.causeId] ?? 0) + 1
  return acc
}

/** 某条错因下的全部沉淀（按日期倒序，页面点开抽屉用） */
export function depositsOfCause(causeId: string): CauseDeposit[] {
  return causeDeposits
    .filter((d) => d.causeId === causeId)
    .sort((a, b) => b.date.localeCompare(a.date) || a.qno - b.qno)
}
