/**
 * 队列页（/grading/queue）自留展示口径。
 * 归属：页面组「批改 · 队列」——只被本目录 import，不是公共件。
 *
 * 🔴 追加①：**停留时长一律吃 mock 备好的 row.stuckMinutes / row.stuckText**。
 *   本文件不算时间、不碰 Date.now()；本地动作（重试/认卷/收卷）产生的新行把停留写成常量「刚刚」，
 *   那是「刚发生」这个事实，不是算出来的时长。
 * 🔴 追加②：「该我动手」只认 HUMAN_STATES，本文件不另列状态名。
 */
import type { BatchState, QueueRow } from '@/mock'
import { NOW, stateMetaOf, students } from '@/mock'

/** 停留超过这个分钟数就加深提示（2 小时）——判词：卡太久的行要显眼 */
export const STUCK_ALERT_MINUTES = 120

/** mock 基准时刻的钟点：本地动作的时间线只盖这一个戳，保证每次走查看到的数字一模一样 */
export const MOCK_CLOCK = NOW.slice(11, 16)

/** mock 基准日：收卷新行的日期 */
export const MOCK_DATE = NOW.slice(0, 10)

/**
 * 🔴 故障 retry 的去处 = **回原状态**（状态机出口那行）。
 * mock 里唯一那条故障（b-td-2）死在「批改中」，note 也写着 retry 后回批改中，
 * 所以这里写死批改中；真实现要读批次的原状态，不是常量。
 */
export const RETRY_BACK_TO: BatchState = '批改中'

/**
 * trackId → 册名。
 * 🔴 队列行本身只吃 queueRows()，绝不从 students 里重捞一份队列；
 * 这里只做一次「轨挂哪本册子」的只读查表（QueueRow 不带 bookRef，而轨列要带册名）。
 */
const BOOK_OF_TRACK: Record<string, string> = {}
for (const s of students) {
  for (const t of s.tracks) {
    if (t.bookRef) BOOK_OF_TRACK[t.id] = t.bookRef
  }
}

export function bookRefOf(trackId: string): string | undefined {
  return BOOK_OF_TRACK[trackId]
}

/** 收卷弹窗的学员下拉（在练的轨顺带带出来，让人确认没选错人） */
export interface RosterEntry {
  code: string
  grade: string
  /** 在练的轨名（已完结的不列） */
  running: string[]
}

export const roster: RosterEntry[] = students.map((s) => ({
  code: s.code,
  grade: s.grade,
  running: s.tracks.filter((t) => t.status === '进行中').map((t) => t.name),
}))

/**
 * 本地动作后的行覆盖（mock：只改本地 state，刷新即还原）。
 * 状态一换，actor / 停留原因 / 出口全部重新照 STATE_MACHINE 取——
 * 🔴 页面不许自己编这三样，编了就跟状态机漂移。
 */
export function patchRow(row: QueueRow, state: BatchState, note: string): QueueRow {
  const meta = stateMetaOf(state)
  const next: QueueRow = {
    ...row,
    state,
    actor: meta?.actor ?? '系统',
    reason: meta?.reason ?? '',
    exits: meta?.exits ?? [],
    stuckSince: NOW,
    stuckMinutes: 0,
    stuckText: '刚刚',
    note,
  }
  // 认完卷了，候选就不该再摆着诱人再点一次
  delete next.candidates
  return next
}

/** 卷型：编排器认不出来时的人工提示，默认「自动」＝交给编排器判 */
export type PaperKind = '自动' | '手抄' | '打印'

/**
 * 收卷生成的新行（本地态）。
 * 🔴 状态只能是「收件中」：照片刚落收件箱，90 秒判稳窗口内，轨和第几天都还没认出来——
 * 认卷是编排器的活，所以轨列写「认卷后定」，不许在收卷弹窗里让人替机器把轨填了。
 */
export function intakeRow(seq: number, student: string, files: string[], kind: PaperKind): QueueRow {
  const meta = stateMetaOf('收件中')
  return {
    batchId: `local-in-${seq}`,
    student,
    track: '（认卷后定）',
    trackId: '',
    dayInTrack: 0,
    date: MOCK_DATE,
    state: '收件中',
    actor: meta?.actor ?? '系统',
    reason: meta?.reason ?? '',
    exits: meta?.exits ?? [],
    stuckSince: NOW,
    stuckMinutes: 0,
    stuckText: '刚刚',
    doubts: 0,
    score: null,
    note: `${MOCK_CLOCK} 人工收卷：收到 ${files.length} 张照片（${files.join('、')}）｜卷型 ${kind}；90 秒判稳后转「待认卷」`,
  }
}
