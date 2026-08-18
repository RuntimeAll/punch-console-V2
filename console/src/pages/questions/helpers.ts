import type { KpAnchor, Question, QuestionTag, TagDomain } from '@/mock'
import {
  findTreeNode, firstTextOf, hasFigureIn, isStub, kpNameOf, kpVocabulary,
  labelPathMap, plainTextOf, questions, questionsUnderPath, TAG_DOMAINS, tagText,
} from '@/mock'

/**
 * 题库组内的纯函数小件（不含 JSX —— 与 parts.tsx 分开是为了 Vite Fast Refresh：
 * 一个文件里混着组件和普通导出会让热更新退化成整页刷新）。
 * 归属：题库组自用（列表页 + 详情页），其它页面组别 import。
 *
 * 🔴 第四轮起块流是 `{ v:2, rows:[{cells}] }`：挑文字 / 判含图一律调 @/mock 的读取器
 *（firstTextOf / plainTextOf / hasFigureIn），**页面不许自己递归 rows/cells**。
 */

/** 来源一行：来源原文（题上不再有 doc/page 两截，就是一条 sourceRaw） */
export function sourceText(q: Question): string {
  return q.sourceRaw
}

/**
 * 题面首行摘要（**纯文本**，只给表格单元格当扫读用）。
 *
 * 🔴 这不是「渲染题目」：真正的题目内容渲染必须走 <BlockFlow>（块流原位混排）。
 * 表格行展开后渲的才是完整题面，摘要只负责让人一行扫过去认出是哪道题。
 */
export function summaryText(q: Question): string {
  return firstTextOf(q.blocks)
}

/** 这题的块流里有没有配图（列表里打个「含图」标记，提示展开能看到混排效果） */
export function hasFigure(q: Question): boolean {
  return hasFigureIn(q.blocks)
}

/** 全文检索用的可搜文本：题号 + 题面文字（含选项） + 考点名 + 标签 + 来源原文 */
export function searchableText(q: Question): string {
  return [
    q.id,
    plainTextOf(q.blocks),
    ...q.kps.map((k) => kpNameOf(k.kpId)),
    ...q.tags.map(tagText),
    q.sourceRaw,
  ]
    .join(' ')
    .toLowerCase()
}

// ── 教材树相关的小件（第二轮：左树右表 + 详情页「树位置」）────────────────

/**
 * 逆表的键 = JSON.stringify(labelPath)。
 * 🔴 不许用 path.join('/') 之类拼键：label 里本来就带空格和括号
 * （「第五单元 平行四边形和梯形」「内角和（拓展）」），拿分隔符拼键早晚撞车；
 * JSON 串天然带引号分隔，且肉眼可读，不用去挑什么不可见字符当分隔符。
 */
function pathKey(path: string[]): string {
  return JSON.stringify(path)
}

/** labelPathMap() 的逆表，懒建一次（树是静态 mock，建完不会变） */
let reverseCache: Record<string, string> | undefined

function reverseMap(): Record<string, string> {
  if (!reverseCache) {
    const acc: Record<string, string> = {}
    for (const [key, path] of Object.entries(labelPathMap())) acc[pathKey(path)] = key
    reverseCache = acc
  }
  return reverseCache
}

/**
 * label 路径 → 树 key（labelPathMap() 的逆向查表）。
 *
 * 🔴 用途：Question.treePath 存的是 label，而树控件与 URL 参数认的是 key，
 * 详情页「树位置」要跳回列表带筛选（/questions?tree=<key>）就得先换算回去。
 * 🔴 绝不用 key.split('/') 反推 label —— 单元名里带空格，切出来必错（页面组约定 §1）。
 * 树上找不到这条路径 = 这题的 treePath 编错了，返回 undefined，页面按「不可点」处理。
 */
export function keyOfLabelPath(path?: string[]): string | undefined {
  if (!path || path.length === 0) return undefined
  return reverseMap()[pathKey(path)]
}

/**
 * 这个树 key 是不是「未铺」的空壳枝（列表页空态要据此换一套说法）。
 * 找不到节点 = key 不合法，按「不是空壳」处理，交给上层的路径校验去兜。
 */
export function isStubKey(key: string): boolean {
  const path = labelPathMap()[key]
  if (!path) return false
  const node = findTreeNode(path)
  return node ? isStub(node) : false
}

/**
 * 一条 treePath 的每一段各自对应的树 key（详情页面包屑逐段可点用）。
 * 返回值与入参等长；某段查不到就是 undefined（那一段渲成纯文字、不给点）。
 */
export function treePathKeys(path?: string[]): (string | undefined)[] {
  if (!path) return []
  return path.map((_, i) => keyOfLabelPath(path.slice(0, i + 1)))
}

/**
 * 归属轴 vs 能力标签轴的**差额**（页面组约定 §1 的具象化）。
 *
 * 同一个考点名有两条口径：
 * - 归属（treePath 前缀）：这题长在教材哪根枝上 —— 树筛的就是它；
 * - 能力标签（kps）：这题考什么，可以跨枝、可以是副考点 —— 考点下拉筛的是它。
 * 🔴 两者对不上时页面必须说出来，否则用户点了「角度计算问题」这片叶子看到 0 道，
 *   会以为库里根本没这类题（实际有 5 道，只是归属挂在别的枝上当副考点）。
 *
 * 只在「标签数 > 归属数」时返回（相等就别啰嗦）；考点词不在 kpVocabulary 里也返回
 * undefined —— 下拉里根本没这个选项，切过去等于把筛选器搞成空档。
 */
export function crossAxisKp(key: string): { name: string; byPath: number; byTag: number } | undefined {
  const path = labelPathMap()[key]
  if (!path) return undefined
  const node = findTreeNode(path)
  if (!node || node.kind !== '考点' || !kpVocabulary.includes(node.label)) return undefined
  const byPath = questionsUnderPath(path).length
  const byTag = questions.filter((q) => q.kps.some((k) => kpNameOf(k.kpId) === node.label)).length
  return byTag > byPath ? { name: node.label, byPath, byTag } : undefined
}

/**
 * 表格「章节」列的取值 = treePath 倒数第二级（五段路径里的**小节**）。
 * 🔴 不取单元、也不取考点：单元太粗（一个单元十几道题看不出差别），
 * 考点已经有单独一列，而且那列是**能力标签**口径，与本列的**归属**口径不是一回事。
 */
export function chapterOf(q: Question): string | undefined {
  const path = q.treePath
  return path && path.length >= 2 ? path[path.length - 2] : undefined
}

// ── 第五轮（定稿对齐）：来源类口径 / 置信度闸 / 标签分组 ────────────────
// 🔴 这三样是「题库列表」与「题目详情」共用的口径，两页都从这里取，别各写各的。

/**
 * 🔴 生成类判定（定稿 D-9）：model / pipeline = 机器产的（变式、管线批量）。
 * 题库页**默认只看题源类**（scan / manual），生成类要开开关才见 ——
 * 否则「我录了多少题」这本账会被自己产的变式冲掉。
 */
export function isGenerated(q: Question): boolean {
  return q.sourceKind === 'model' || q.sourceKind === 'pipeline'
}

/** 来源类的人话（四种 sourceKind 各有说法，别只分两类糊过去） */
export function sourceKindText(kind: Question['sourceKind']): string {
  if (kind === 'scan') return '扫描 / 拍照录入'
  if (kind === 'manual') return '手工录入'
  if (kind === 'model') return '模型生成（举一反三）'
  return '管线批量生成'
}

/**
 * 🔴 入库执行阀①（定稿 D-21）：置信度 ≥ 0.85 才许直入，低于就该滞留待审。
 * 页面按同一条线标黄 —— 阈值只此一处，别在页面里再抄一个 0.85。
 */
export const CONF_GATE = 0.85

/**
 * 这条考点挂靠该不该标黄：置信度不到闸 **或** 是兜底挂的。
 * 🔴 兜底（fallback）哪怕置信度高也算欠账：它意味着「没命中该挂的叶，退一步挂的」。
 */
export function isLowConf(anchor: KpAnchor): boolean {
  return anchor.fallback || anchor.confidence < CONF_GATE
}

/**
 * 考点挂靠的来历一句话（列表 hover 的 title 与详情页那行小字**共用同一句**）。
 * 🔴 两处各写各的必然漂移：一处说「兜底」一处说「待核」，走查时就成了两套口径。
 */
export function anchorTitle(anchor: KpAnchor): string {
  const parts = [`挂靠来历：${anchor.stage}`, `置信度 ${anchor.confidence}`]
  if (anchor.fallback) parts.push('兜底挂靠（没命中该挂的叶，退一步挂的）')
  if (anchor.confidence < CONF_GATE) parts.push(`低于入库闸 ${CONF_GATE}，该进审核台`)
  return parts.join(' · ')
}

/**
 * 标签按域分组（定稿 D-19：标签是**域 + 名**，一等公民）。
 * 🔴 域的顺序走正本 TAG_DOMAINS，页面别自己写死四个中文；
 *    这题没有的域直接不返回（详情页只渲有货的那几行）。
 */
export function tagsByDomain(tags: QuestionTag[]): { domain: TagDomain; tags: QuestionTag[] }[] {
  return TAG_DOMAINS.map((domain) => ({ domain, tags: tags.filter((t) => t.domain === domain) })).filter(
    (g) => g.tags.length > 0,
  )
}

/**
 * 标签筛选的命中判定：选中的值是 tagText（域·名）。
 * 🔴 多选 = 「与」：题必须**同时**带上这几个标签。
 *    用「或」的话选两个标签反而命中更多，筛选器越用范围越大，与人的直觉相反。
 */
export function matchesTags(q: Question, picked: string[]): boolean {
  if (picked.length === 0) return true
  const own = q.tags.map(tagText)
  return picked.every((p) => own.includes(p))
}
