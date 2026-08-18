import type { ExamModel, Question, SolutionModel } from '@/mock'
import { examModels, findQuestion, firstTextOf, kpNameOf, modelsOfKpId, questionsOfPattern } from '@/mock'

/**
 * 考察模型组内的纯函数（不含 JSX —— 与组件分文件是为了 Vite Fast Refresh）。
 * 归属：维护组「考察模型」自用，其它页面组别 import。
 */

/**
 * 记录**现态**：mock 的 status 只有 active / draft 两态，本页多一个「已停用」。
 * 🔴 停用 ≠ 草稿，别拿 draft 凑数：
 * - 草稿   = 参数表写完了但没接出题器（还没出过题）
 * - 已停用 = 接过、出过题，现在不让它再出了（历史题还在库里）
 * 两者的 questionCount 一个是 0、一个可能上百，混成一态就白记了。
 */
export type LiveStatus = '在用' | '草稿' | '已停用'

export type StatusMap = Record<string, LiveStatus>

/** 初始现态 = 照抄 mock 的 status（本页的转正 / 停用只在这张表上改，不落库） */
export function initialStatus(): StatusMap {
  const acc: StatusMap = {}
  for (const m of examModels) acc[m.id] = m.status === 'active' ? '在用' : '草稿'
  return acc
}

/** 取现态；表里没有就回落到 mock 的 status */
export function statusOf(map: StatusMap, m: ExamModel): LiveStatus {
  return map[m.id] ?? (m.status === 'active' ? '在用' : '草稿')
}

/**
 * 状态 Tag 颜色。
 * 🔴 风格口径「禁大色块」：在用是常态，不给颜色（默认灰）才不抢眼；
 *   只有「草稿」（还没接出题器）给橙色提醒，「已停用」保持默认灰。
 */
export function statusTagColor(s: LiveStatus): string | undefined {
  return s === '草稿' ? 'orange' : undefined
}

/** 状态的一句话解释（表格与抽屉共用一份口径，别两处各写各的） */
export function statusHint(s: LiveStatus): string {
  if (s === '在用') return '已接出题器，正在产题'
  if (s === '草稿') return '参数表已写、未接出题器 —— 不是「这个模型没用」'
  return '接过也出过题，现在不让它再出；历史题原地不动'
}

/** 现态下的挂题合计（停用的模型不再产新题，但它管着的历史题还算它的账） */
export function totalQuestions(): number {
  return examModels.reduce((n, m) => n + m.questionCount, 0)
}

/** 母题：id → 题（题被删了就只剩 id，如实标出来而不是静默跳过） */
export function motherQuestions(m: ExamModel): { id: string; q?: Question }[] {
  return m.originQuestionIds.map((id) => ({ id, q: findQuestion(id) }))
}

/**
 * 题面首行摘要（**纯文本**，只给母题清单当扫读用）。
 * 🔴 这不是「渲染题目」：题目内容真要渲染一律走 <BlockFlow>，本页不渲题面。
 */
export function stemSummary(q: Question): string {
  // 🔴 块流 v2 起挑首行文字走 @/mock 的读取器，页面不自己递归 rows/cells
  return firstTextOf(q.blocks)
}

// ═══════════════════════════════════════════════════════════════
// 第四轮：本页扩成三段式（题型目录 / 考察模型 / 解题模型）后新增的小件
// 🔴 三样东西分工别混（数据结构.md §2.1④ + mock/patterns.ts 顶部）：
//   QuestionPattern = 这类题**长什么样**（识别归类，题挂 patternId）
//   ExamModel       = 这类题**怎么造**（出题 DSL 配方，本目录原有那张表）
//   SolutionModel   = 这类题**怎么解**（举一反三地基，难度靠 tier/freq 表驱动算）
// ═══════════════════════════════════════════════════════════════

/**
 * kpId 数组 → 考点名数组。
 * 🔴 定稿起 pattern / solutionModel 存的是 **kpId**（不存名），而溯源链的唯一渲法
 *   <KpTraceLink> 认的是**考点名**（它内部再把名换回树 key）。所以这里做一次 id → 名，
 *   剩下的判断（树上有没有这片叶 / 点不点得动）一律交给 KpTraceLink，本页不自己判。
 * 🔴 kpNameOf 查不到会如实吐 `未知考点(<id>)`，别在这儿吞掉——脏 id 就该在页面上看得见。
 */
export function kpNamesOfIds(kpIds: string[]): string[] {
  return kpIds.map(kpNameOf)
}

/**
 * 一个题型目录底下挂着的题（**现算**，不落计数字段 ——
 * 老区 free_tag 的 use_count 143 个里 74 个是错的，计数字段一旦落库就开始骗人）。
 * 题被删/没录就只剩 id，如实标出来而不是静默跳过。
 */
export function questionsOfPatternRows(patternId: string): { id: string; summary?: string }[] {
  return questionsOfPattern(patternId).map((id) => {
    const q = findQuestion(id)
    return { id, summary: q ? firstTextOf(q.blocks) : undefined }
  })
}

/**
 * 与这个题型**共考点**的解题模型（「长什么样」→「怎么解」这一跳）。
 * 🔴 这是现算的**弱关联**，不是数据结构里的外键：题型与解题模型各自挂考点（kpIds 多值），
 *   共了考点才推得出「这类题大概用哪个模型解」。所以页面上要写成「解法参考」而不是「它的解法」。
 */
export function solutionsForPattern(kpIds: string[]): SolutionModel[] {
  const seen = new Set<string>()
  const out: SolutionModel[] = []
  for (const kpId of kpIds) {
    for (const m of modelsOfKpId(kpId)) {
      if (seen.has(m.id)) continue
      seen.add(m.id)
      out.push(m)
    }
  }
  return out
}

/**
 * 双旋钮的一句话解释（tier = 阶，freq = 频次）。
 * 🔴 难度 = **模型表驱动**（阶 + 稀有度算出来），LLM 只负责匹配到哪个模型、**不自评难度**。
 *   所以这两个数字是「控制面板」，页面只如实显示，不在这儿另算一个难度出来。
 */
export function tierHint(tier: number): string {
  return `阶 ${tier}：模型本身的复杂度层级，越高越难（难度主轴）`
}

export function freqHint(freq: number): string {
  return `频次 ${freq}：这个模型在真题里出现得有多勤，越低越稀有；稀有度是难度的第二个旋钮`
}
