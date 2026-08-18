/**
 * 批改三页（/grading、/grading/queue、/grading/:code）共用的展示口径。
 * 归属：页面组「批改」自留件——只被这三个目录 import，不是公共件，别的组别拿。
 *
 * 🔴 铁律③：一切分数聚合只在**轨内**做。本文件只提供 trackRate（轨内正确率），
 * 故意不提供任何「跨轨平均分」函数——跨轨只允许计数（几条轨 / 几个批次 / 几条待办）。
 */
import type { Batch, BatchState, CauseDeposit, Student, Track } from '@/mock'
import { causeDeposits, HUMAN_STATES } from '@/mock'

/**
 * 批次状态 → antd Tag 的 color（默认 token 系，禁自定义主色、禁大色块）。
 * 🔴 配色只表达一件事：**该不该我动手**——三个人工态（待人工认卷/待终审/故障）给暖色，
 * 系统在飞的一律冷色或无色，终态绿。别按「好看」调，调了就读不出轻重。
 */
const STATE_TAG_COLOR: Record<BatchState, string | undefined> = {
  收件中: undefined,
  待认卷: undefined,
  待人工认卷: 'gold',
  批改中: 'processing',
  待终审: 'orange',
  已确认: 'blue',
  待出件: 'cyan',
  已出件: 'green',
  故障: 'red',
}

export function stateTagColor(state: BatchState): string | undefined {
  return STATE_TAG_COLOR[state]
}

/** 批次状态 → 描边/文字用的色值（天格靠 1px 边框区分状态，不铺底色） */
const STATE_HUE: Record<BatchState, string> = {
  收件中: '#bfbfbf',
  待认卷: '#8c8c8c',
  待人工认卷: '#d48806',
  批改中: '#1677ff',
  待终审: '#d46b08',
  已确认: '#1677ff',
  待出件: '#08979c',
  已出件: '#389e0d',
  故障: '#cf1322',
}

export function stateHue(state: BatchState): string {
  return STATE_HUE[state]
}

/** 判定符号 → 文字色（√ 绿 / × 红 / ? 橙） */
export function verdictHue(v: '√' | '×' | '?'): string {
  if (v === '√') return '#389e0d'
  if (v === '×') return '#cf1322'
  return '#d46b08'
}

/**
 * 该批次是否「卡在人手上」= 待人工认卷 / 待终审 / 故障。
 * 🔴 与 mock 的 HUMAN_STATES / pendingBatches() / pendingMine() 同一口径，别在页面里另写一套。
 */
export function isPending(state: BatchState): boolean {
  return HUMAN_STATES.includes(state)
}

/** 学员的待办批次数——跨轨**计数**（允许），不是分数聚合 */
export function pendingCountOf(student: Student): number {
  return student.tracks.reduce((n, t) => n + t.days.filter((d) => isPending(d.state)).length, 0)
}

/** 学员的累计批次数——同上，纯计数 */
export function batchCountOf(student: Student): number {
  return student.tracks.reduce((n, t) => n + t.days.length, 0)
}

/** 🔴 轨内正确率：只把本轨已出分的天加起来，绝不跨轨。没出过分返回 null */
export function trackRate(track: Track): { right: number; total: number; percent: number } | null {
  let right = 0
  let total = 0
  for (const d of track.days) {
    if (!d.score) continue
    right += d.score.right
    total += d.score.total
  }
  if (total === 0) return null
  return { right, total, percent: Math.round((right / total) * 100) }
}

/** 按 batchId 在某学员名下定位「哪条轨的哪一天」——待办页跳过来自动开抽屉要用 */
export function locateBatch(student: Student, batchId: string): { track: Track; batch: Batch } | null {
  for (const track of student.tracks) {
    const batch = track.days.find((d) => d.id === batchId)
    if (batch) return { track, batch }
  }
  return null
}

/** 待办页跳学员页并自动开抽屉的唯一 URL 造法（代号是中文，必须转义） */
export function studentHref(code: string, batchId?: string): string {
  const base = `/grading/${encodeURIComponent(code)}`
  return batchId ? `${base}?batch=${encodeURIComponent(batchId)}` : base
}

// ── 学员档案口径（定稿 §一 student 扩表）──────────────────────────

/**
 * 在读状态 → Tag color。🔴 只给「要留意的两态」上色：在读=蓝（正在服务中）、试听=金（转化窗口内）；
 * 暂停 / 结课一律留白——**不上色本身就是信息**，全上色等于没上色（与禁大色块同一条纪律）。
 */
const STUDENT_STATUS_COLOR: Record<Student['status'], string | undefined> = {
  试听: 'gold',
  在读: 'blue',
  暂停: undefined,
  结课: undefined,
}

export function studentStatusColor(status: Student['status']): string | undefined {
  return STUDENT_STATUS_COLOR[status]
}

/**
 * 学员的报告份数。🔴 定稿 §一：**报告是批次字段**（batch.report_file），没有独立报告表；
 * 「已出件」这一态的定义就是「报告已挂到这个批次上」⇒ 报告数 = 已出件批次数。
 * 跨轨**计数**（允许），不是分数聚合。
 */
export function reportCountOf(student: Student): number {
  return student.tracks.reduce((n, t) => n + t.days.filter((d) => d.state === '已出件').length, 0)
}

/**
 * 学员的沉淀错因记录（cause_deposit 事实层，定稿 §2.3「批改沉淀 = 学生错的精华」）。
 * 🔴 只返回原始行：调用方要么数条数、要么数错因种类——绝不把不同轨的沉淀拉平算率或画趋势（铁律③）。
 */
export function depositsOf(code: string): CauseDeposit[] {
  return causeDeposits.filter((d) => d.student === code)
}
