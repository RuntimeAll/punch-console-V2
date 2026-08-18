import type { Batch, CauseDeposit, ItemVerdict, Track } from '@/mock'
import { causeDeposits, findStudent } from '@/mock'

/**
 * 错因组内的纯函数（不含 JSX —— 与组件分文件是为了 Vite Fast Refresh）。
 * 归属：维护组「错因管理」自用，其它页面组别 import。
 */

/**
 * 一条沉淀的唯一键。CauseDeposit 没有 id（它是事实层，只增不改），
 * 用「学员 + 轨 + 第几天 + 第几题」定位——这四项在 mock 里就是唯一的，
 * 也正好是这条沉淀在批改账本上的坐标。
 */
export function depositKey(d: CauseDeposit): string {
  return `${d.student}|${d.track}|${d.dayInTrack}|${d.qno}`
}

/**
 * 一条沉淀在批改账本上的**完整判定上下文**。
 * 🔴 沉淀不是孤立的一行字：它背后有一次真实的批改（哪一批、机器判了什么、当天错了几道）。
 *   抽屉要能把这层还原出来，否则「沉淀 = 精华」这句话就落不到地上。
 * 查不到就是 undefined —— 说明沉淀与批改账本对不上，如实标出来而不是编一个。
 */
export type DepositContext = {
  track?: Track
  batch?: Batch
  item?: ItemVerdict
}

export function contextOf(d: CauseDeposit): DepositContext {
  const student = findStudent(d.student)
  const track = student?.tracks.find((t) => t.name === d.track)
  const batch = track?.days.find((b) => b.dayInTrack === d.dayInTrack)
  const item = batch?.items.find((it) => it.qno === d.qno)
  return { track, batch, item }
}

/** 出现过的学员代号（筛选下拉从事实层现算，不另立一份写死的名单） */
export function studentOptions(): string[] {
  return Array.from(new Set(causeDeposits.map((d) => d.student)))
}

/** 沉淀按日期倒序（同一天按学员、题号排，保证顺序稳定） */
export function sortDeposits(rows: CauseDeposit[]): CauseDeposit[] {
  return [...rows].sort(
    (a, b) => b.date.localeCompare(a.date) || a.student.localeCompare(b.student) || a.qno - b.qno,
  )
}

/**
 * 判定符号的颜色。
 * 🔴 「禁大色块」：只给字上色，不铺底色；√ 用常规文字色，× 才给红。
 */
export function verdictHue(v?: ItemVerdict['verdict']): string {
  if (v === '×') return '#cf1322'
  if (v === '?') return '#d46b08'
  return 'rgba(0,0,0,0.88)'
}
