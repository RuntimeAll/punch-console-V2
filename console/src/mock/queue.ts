import type { Batch, BatchState, Student, Track } from './types'
import { HUMAN_STATES, STATE_MACHINE, stateMetaOf } from './types'
import { NOW, allBatches } from './students'

/**
 * 批改队列的取数层 —— 队列页 /grading/queue 只吃这里，不自己从 students 里捞。
 *
 * 🔴 第三轮判词①：**整条队列展示，状态外置明确**。
 * 队列不是「待办清单」：机器在飞的（收件中/待认卷/批改中/已确认/待出件）也全摆出来，
 * 让人一眼看见「这条链现在跑到哪了」；只是它们不该我动手，所以 actor 分得死死的。
 * 🔴 该我动手的只有三态（HUMAN_STATES）→ pendingMine()，队列页 ?mine=1 就是它。
 */

/** 近期终态取几条：已出件是终态，队列里只留最近这么多条当「刚跑完」的尾巴，不然队列会被历史淹掉 */
const RECENT_DONE_LIMIT = 5

/** 队列一行：学员 / 轨 / 轨内天 / 状态 / 停留时长 / 存疑数（页面照渲，别再算一遍） */
export interface QueueRow {
  batchId: string
  /** 学员代号（🔴 代号制，不出现真名） */
  student: string
  track: string
  trackId: string
  /** 轨内第几天 */
  dayInTrack: number
  /** 收卷日期 */
  date: string
  state: BatchState
  /** 🔴 谁的活：'人' = 不点它永远不动；'系统' = 机器在跑，看着就行；'终态' = 到头了 */
  actor: '系统' | '人' | '终态'
  /** 停留原因（照抄状态机那行的大白话） */
  reason: string
  /** 出口（条件 → 去哪） */
  exits: string[]
  /** 停留起点（ISO 串）；终态可以没有 */
  stuckSince?: string
  /** 停留了多少分钟；没有停留起点时为 null */
  stuckMinutes: number | null
  /** 停留时长的人话，如「2 天 13 小时」「9 分钟」；算不出给 '—' */
  stuckText: string
  /** 存疑题数（机器判不了、要人拍板的题） */
  doubts: number
  /** 机器初判分；没出分给 null */
  score: { right: number; total: number } | null
  /** 只有「待人工认卷」有：候选卷名 */
  candidates?: string[]
  /** 状态附注（故障原文 / 撞库说明），🔴 机器原话 */
  note?: string
}

/** 状态在状态机里的次序（同组排序的兜底，保证链路上游排在下游前面） */
const STATE_ORDER: Record<string, number> = Object.fromEntries(STATE_MACHINE.map((m, i) => [m.state, i]))

/** 分组权重：人的活排最前，系统在飞居中，终态垫底 */
function groupWeight(actor: QueueRow['actor']): number {
  if (actor === '人') return 0
  if (actor === '系统') return 1
  return 2
}

/** 停留分钟数：两个时刻都按本地时区解析，差值与时区无关 */
function minutesSince(since: string | undefined, now: string): number | null {
  if (!since) return null
  const a = new Date(since).getTime()
  const b = new Date(now).getTime()
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  return Math.max(0, Math.round((b - a) / 60000))
}

/** 分钟 → 人话（「9 分钟」「3 小时 12 分」「2 天 13 小时」） */
export function stuckLabel(minutes: number | null): string {
  if (minutes === null) return '—'
  if (minutes < 60) return `${minutes} 分钟`
  if (minutes < 60 * 24) {
    const h = Math.floor(minutes / 60)
    const m = minutes % 60
    return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`
  }
  const d = Math.floor(minutes / (60 * 24))
  const h = Math.floor((minutes % (60 * 24)) / 60)
  return h > 0 ? `${d} 天 ${h} 小时` : `${d} 天`
}

/** 一条批次 → 一行队列 */
function toRow(student: Student, track: Track, batch: Batch): QueueRow {
  const meta = stateMetaOf(batch.state)
  const stuckMinutes = minutesSince(batch.stuckSince, NOW)
  const row: QueueRow = {
    batchId: batch.id,
    student: student.code,
    track: track.name,
    trackId: track.id,
    dayInTrack: batch.dayInTrack,
    date: batch.date,
    state: batch.state,
    actor: meta?.actor ?? '系统',
    reason: meta?.reason ?? '',
    exits: meta?.exits ?? [],
    stuckMinutes,
    stuckText: stuckLabel(stuckMinutes),
    doubts: batch.doubts ?? 0,
    score: batch.score ?? null,
  }
  if (batch.stuckSince) row.stuckSince = batch.stuckSince
  if (batch.candidates) row.candidates = batch.candidates
  if (batch.note) row.note = batch.note
  return row
}

/** 在飞 = 还没到终态（已出件之外的八态都算在飞） */
function isInFlight(state: BatchState): boolean {
  return state !== '已出件'
}

/**
 * 🔴 队列全量：**全部在飞批次** + 近期终态若干条（最近 5 条已出件当尾巴）。
 * 排序 = 人的活 → 系统在飞 → 终态；同组里停得久的排前面（终态按日期倒序）。
 */
export function queueRows(): QueueRow[] {
  const all = allBatches()
  const inFlight = all.filter((r) => isInFlight(r.batch.state))
  const recentDone = all
    .filter((r) => !isInFlight(r.batch.state))
    .sort((a, b) => b.batch.date.localeCompare(a.batch.date))
    .slice(0, RECENT_DONE_LIMIT)

  return [...inFlight, ...recentDone]
    .map((r) => toRow(r.student, r.track, r.batch))
    .sort((a, b) => {
      const g = groupWeight(a.actor) - groupWeight(b.actor)
      if (g !== 0) return g
      if (a.actor === '终态') return b.date.localeCompare(a.date)
      const am = a.stuckMinutes ?? -1
      const bm = b.stuckMinutes ?? -1
      if (am !== bm) return bm - am
      return (STATE_ORDER[a.state] ?? 99) - (STATE_ORDER[b.state] ?? 99)
    })
}

/**
 * 🔴 该我动手的行：只有三态（待人工认卷 / 待终审 / 故障）。
 * 队列页 ?mine=1 就是把 queueRows() 收窄到这一把——同一条数据、同一套排序，只是少了系统在飞的行。
 */
export function pendingMine(): QueueRow[] {
  return queueRows().filter((r) => HUMAN_STATES.includes(r.state))
}
