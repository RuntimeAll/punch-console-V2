import type { CauseDeposit, ErrorCause, ExamModel, Question } from '@/mock'
import {
  causeDeposits,
  errorCauses,
  examModels,
  firstTextOf,
  flattenTree,
  labelPathMap,
  modelsOfQuestion,
  questionsUnderPath,
} from '@/mock'

/**
 * 🔴 溯源正本（第三轮判词⑤）——「错因 / 考察模型 / 题目虽然内容不同，都要能向上溯源到知识图谱；
 * 考点详情 = 聚合落点」。这三样各自散在 /cause /model /questions，
 * 唯一把它们接起来的东西就是**考点叶名**，所以换算与聚合只许有一份实现，放这儿。
 *
 * 🔴 依赖方向是**单向**的：/model /cause /questions/:id → 本文件 → @/mock。
 *   本文件绝不反过来 import 那三个页面组的东西（那样就成了环，谁也拆不动）。
 *   放在 kg 目录下是因为知识图谱是溯源的**落点**，不是因为它归 kg 页私有。
 *
 * 🔴 不含 JSX（组件在同目录 KpTraceLink.tsx / KpTraceSections.tsx）——
 *   混着写会让 Vite Fast Refresh 退化成整页刷新。
 */

/** 最近沉淀只取这么几条：考点详情要的是「有没有、最近是什么」，不是全量账本 */
const RECENT_DEPOSIT_LIMIT = 3

/**
 * key → label 路径，**模块顶层算一次**。
 * 🔴 labelPathMap() 每调一次就把整棵树重新递归一遍；本文件的函数是在 render 里调的
 *   （/kg 每次重渲、/model 每行、/cause 每行），不缓存就是白烧。树是静态 mock，建完不会变。
 */
const PATH_BY_KEY: Record<string, string[]> = labelPathMap()

/**
 * 考点名 → 树 key。
 * 🔴 已核：kg-tree.ts 上 58 片考点叶的 label **全树唯一**，所以这张表不会丢东西；
 *   万一将来有人铺出同名叶，以树上**先出现**的那片为准（并且那本身就是该治理的重名事故）。
 * 🔴 只收 kind === '考点' 的叶子：溯源链的落点是叶，不是单元/小节。
 */
const KP_KEY_BY_NAME: Record<string, string> = (() => {
  const acc: Record<string, string> = {}
  for (const n of flattenTree()) {
    if (n.kind !== '考点') continue
    if (acc[n.label] === undefined) acc[n.label] = n.key
  }
  return acc
})()

/**
 * 考点名 → 树 key；树上没有这片叶就是 undefined。
 * 🔴 undefined 不是「查失败」，是**溯源断点**：这条错因 / 这个模型说的考点，
 *   教材树上还没铺。页面必须如实标出来（灰掉、不给点），不许静默当成没这回事。
 */
export function kpKeyOf(name: string): string | undefined {
  return KP_KEY_BY_NAME[name]
}

/**
 * 考点名 → /kg 的落地 URL（判词⑤ 约定的参数名就是 ?kp=<树key>）。
 * 断点时返回 undefined，调用方据此渲成不可点。
 */
export function kgHrefOf(name: string): string | undefined {
  const key = kpKeyOf(name)
  return key === undefined ? undefined : `/kg?kp=${encodeURIComponent(key)}`
}

/**
 * /kg 收到的 ?kp= 值 → 合法树 key。
 * 先按 key 认（KpTraceLink 发出去的一律是 key），认不上再按考点名兜一手——
 * 手敲 URL / 从别处粘个考点名过来时不至于白跳一趟。都认不上返回 ''（= 没选中）。
 */
export function resolveKpParam(raw: string): string {
  if (!raw) return ''
  if (PATH_BY_KEY[raw] !== undefined) return raw
  return KP_KEY_BY_NAME[raw] ?? ''
}

/**
 * 一片考点叶挂着的**全部家当**（考点详情四小节的取数层）。
 * 🔴 四样都给，空的也给空数组 —— 页面照样把小节渲出来写「暂无」。
 *   用户要看的就是「这个考点挂着什么家当」，藏起来等于没回答。
 */
export interface KpTrace {
  /** 树上的原名（不是本页临时改的名：溯源匹配认的是持久化的那个词） */
  name: string
  key: string
  path: string[]
  /** ① 关联题目：归属挂在这片叶（含下级）的题，前缀口径 */
  questions: Question[]
  /** ② 关联考察模型：两路并集（见 modelsOfKp） */
  models: ExamModel[]
  /** ③ 关联错因：kpNames 里写了这片叶名的错因 */
  causes: ErrorCause[]
  /** ④ 最近批改沉淀：经 ③ 的错因间接挂上来的，已截到最近 RECENT_DEPOSIT_LIMIT 条 */
  deposits: CauseDeposit[]
  /** ④ 的全量条数（页面要写「最近 3 条 / 共 N 条」，别让人以为一共就这几条） */
  depositTotal: number
}

/** 按 id 去重并保持先来后到 */
function dedupeModels(list: ExamModel[]): ExamModel[] {
  const seen = new Set<string>()
  const out: ExamModel[] = []
  for (const m of list) {
    if (seen.has(m.id)) continue
    seen.add(m.id)
    out.push(m)
  }
  return out
}

/**
 * 一片叶挂着的考察模型 = **两路并集**：
 * ① 模型的 kpNames 里直接写了这片叶名（模型自己认领的挂靠）；
 * ② 模型的母题正好归属在这片叶下（modelsOfQuestion）。
 * 🔴 两路都要：em-003 两样都占，而有的模型只写了 kpNames 没有母题（em-005 那种手写模型），
 *   只走一路必漏。先排①再排②，认领过的排前面。
 */
export function modelsOfKp(name: string, underLeaf: Question[]): ExamModel[] {
  const byName = examModels.filter((m) => m.kpNames.includes(name))
  const byMother = underLeaf.flatMap((q) => modelsOfQuestion(q.id))
  return dedupeModels([...byName, ...byMother])
}

/** 一片叶挂着的错因（kpNames 空数组 = 跨考点通用错因，不算挂在任何一片叶上，故自然不命中） */
export function causesOfKp(name: string): ErrorCause[] {
  return errorCauses.filter((c) => c.kpNames.includes(name))
}

/** 沉淀按日期倒序（同日按学员、题号，保证顺序稳定），与 /cause 那边同一把尺 */
function sortDeposits(rows: CauseDeposit[]): CauseDeposit[] {
  return [...rows].sort(
    (a, b) => b.date.localeCompare(a.date) || a.student.localeCompare(b.student) || a.qno - b.qno,
  )
}

/**
 * 考点叶的聚合落点。传的不是考点叶（或 key 树上没有）返回 undefined。
 * 🔴 沉淀是**间接**挂上来的：考点 → 错因 → 沉淀。deposit 自己不带考点字段，
 *   这一跳就是溯源链真正的价值所在（判词⑤ 说的「都要能向上溯源」）。
 * 🔴 铁律③照旧：沉淀这里只**列**、只**计数**，不跨轨算率、不画趋势线，所以每条都带轨名。
 */
export function traceOfKpKey(key: string): KpTrace | undefined {
  const path = PATH_BY_KEY[key]
  if (path === undefined || path.length === 0) return undefined
  const name = path[path.length - 1]

  const qs = questionsUnderPath(path)
  const causes = causesOfKp(name)
  const causeIds = new Set(causes.map((c) => c.id))
  const hit = causeDeposits.filter((d) => causeIds.has(d.causeId))

  return {
    name,
    key,
    path,
    questions: qs,
    models: modelsOfKp(name, qs),
    causes,
    deposits: sortDeposits(hit).slice(0, RECENT_DEPOSIT_LIMIT),
    depositTotal: hit.length,
  }
}

/**
 * 溯源断点盘点（维护区页头用一句话交代欠账）。
 * - modelsWithoutKp  一片叶都没挂的模型（ExamModel.kpNames 空数组）—— 断得最彻底的一种
 * - offTreeKpNames   模型/错因写了名字、但教材树上找不到同名叶的考点词
 * 🔴 这两样都是**活儿**，不是正常态（types.ts 里写着「空数组 = 溯源断点」）。
 */
export function traceGaps(): { modelsWithoutKp: ExamModel[]; offTreeKpNames: string[] } {
  const off = new Set<string>()
  for (const m of examModels) for (const k of m.kpNames) if (kpKeyOf(k) === undefined) off.add(k)
  for (const c of errorCauses) for (const k of c.kpNames) if (kpKeyOf(k) === undefined) off.add(k)
  return {
    modelsWithoutKp: examModels.filter((m) => m.kpNames.length === 0),
    offTreeKpNames: Array.from(off),
  }
}

/**
 * 题面首行摘要（**纯文本**，只给溯源清单当扫读用）。
 * 🔴 这不是「渲染题目」：题目内容真要渲染一律走 <BlockFlow>，溯源小节不渲题面。
 */
export function traceStemSummary(q: Question): string {
  // 🔴 块流 v2 起挑首行文字走 @/mock 的读取器，页面不自己递归 rows/cells
  return firstTextOf(q.blocks)
}
