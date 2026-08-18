import type { IngestSrcKind, ReviewKind, ReviewLevel, ReviewTicket } from '@/mock'
import { findIngestBatch } from '@/mock'

/**
 * 审核台（/review）的纯逻辑层：页签口径、本地处理记录、payload 组装。
 * 放在 .ts 里而不是 .tsx，是为了让 cards.tsx 只导出组件（oxlint 的 only-export-components）。
 */

/** 四类页签的固定顺序，也是 ?tab= 允许的取值（多一类少一类都要先找用户拍板） */
export const KINDS: ReviewKind[] = ['图审', '题审转正', '考点低置信', '隔离行']

/** ?tab= 落地：认得的就用，认不得（拼错/没带）一律回落第一个页签 */
export function tabFromParam(raw: string | null): ReviewKind {
  return KINDS.find((k) => k === raw) ?? KINDS[0]
}

/**
 * 一条工单被处理后的本地记录。
 * 🔴 mock 阶段只有本地状态：刷新页面就回到初始，页面上要明说，别让走查的人以为真存了。
 */
export interface DoneMark {
  /** 处理动作，如「通过」「驳回」「收编为别名」 */
  action: string
  /** 处理时填的话（驳回理由 / 定稿口径 / 收编成哪个叶子），有的动作必填 */
  note?: string
  /** 处理时间 */
  at: string
}

/** 「都不对，建新叶子」的哨兵值（不能跟真候选串名） */
export const NEW_LEAF = '__new_leaf__'

/** 四类清空时的贺词（空态别只写「暂无数据」，走查时那句话什么也不说明） */
export const CLEARED_WORD: Record<ReviewKind, string> = {
  图审: '这一批图都过了人眼：图在题面里的位置、图上的标注与题面对得上，可以放心拿去出卷。',
  题审转正: '草稿区清了：该转正的转正、该退回的退回，题库里没有悬着口径不定的题。',
  考点低置信: '考点都定了名：机器不确定的那几道，现在都挂在真叶子上，学情统计不会再糊。',
  隔离行: '隔离区清空了：拦下的行要么归位到题上，要么明确废弃，没有无主的碎片留在管线里。',
}

/** 处理时间戳——🔴 纪律：mock 时间一律取写死基准（禁 Date.now/new Date，走查数字必须可复现） */
export function nowText(): string {
  return '2026-08-17 09:45'
}

/**
 * 「隔离行」卡片折叠展示的原始 payload：
 * 这条工单的原始记录 + 它挂着的批次上下文（人审要判的就是这堆没被美化过的字段）。
 */
export function payloadOf(t: ReviewTicket): string {
  const b = t.batchId ? findIngestBatch(t.batchId) : undefined
  return JSON.stringify(
    {
      ticket_id: t.id,
      kind: t.kind,
      gate: 'preflight',
      priority: t.priority,
      created_at: t.createdAt,
      state: t.state,
      title: t.title,
      detail: t.detail,
      batch: b
        ? { id: b.id, time: b.time, source: b.source, counts: b.counts, gate_summary: b.gateSummary }
        : null,
    },
    null,
    2,
  )
}

// ── 来源等级（定稿 D-18 / D-21）：这条工单是从哪种源、哪一级审核等级来的 ──

/**
 * 一条工单的「来源等级」。
 * 🔴 为什么工单行要看这个：同样一条图审工单，**文字层源**的图有守恒基准（图数能对上原件，人审只是复核），
 * **图片OCR 源**没有基准（不知道原件本该有几张图），得逐图核 —— 源不同，人审该花的力气差一截。
 * 等级同理：L1 抽检看一眼就过，L3 逐题细审要对着原件抠。审之前先知道该用多大力气。
 */
export interface SrcLevel {
  /** 工单挂的那个批次的源类型 */
  srcKind: IngestSrcKind
  /** 🔴 逐题定级：只有工单指到批次里那一行（questionId 对得上）时才有；对不上说明这条工单管的是行级碎片或整题重录 */
  level?: ReviewLevel
}

/** 取工单的来源等级：没挂批次（如只挂考察模型的那种）返回 undefined，页面照实写「无来源批次」 */
export function srcLevelOf(t: ReviewTicket): SrcLevel | undefined {
  const b = t.batchId ? findIngestBatch(t.batchId) : undefined
  if (!b) return undefined
  const item = t.questionId ? b.items.find((it) => it.questionId === t.questionId) : undefined
  return { srcKind: b.srcKind, level: item?.reviewLevel }
}

/**
 * 审核等级的色阶与人话。
 * 🔴 口径正本 = 数据结构.md D-21；录入记录页 /ingest 有一份同口径的副本 ——
 * 两页各在各自目录里放一份是纪律（页面组只改自己目录），改口径两边一起改。
 */
export const LEVEL_COLOR: Record<ReviewLevel, string> = {
  L0: 'green',
  L1: 'blue',
  L2: 'gold',
  L3: 'orange',
  人工: 'red',
}

export const LEVEL_WORD: Record<ReviewLevel, string> = {
  L0: '直入',
  L1: '抽检',
  L2: '逐题速审',
  L3: '逐题细审',
  人工: '全程人来',
}

/** 源类型为什么要出现在工单行上（鼠标移上去看的那句） */
export const SRC_WHY: Record<IngestSrcKind, string> = {
  文字层: '文字层直读源：有守恒基准（图数 / 公式数 / 字符多重集可对账），人审只复核报警处。',
  图片OCR: '图片 OCR 源：🔴 没有守恒基准，判法是「置信度 + 双跑对照 + 人审必过」，同复杂度的审核等级比文字层高一级。',
}
