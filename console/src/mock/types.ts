/**
 * 🔴 唯一类型正本 —— 页面组不许改本文件，只许 import。
 *
 * 需要新字段：先找地基工加，不许各页私自扩展类型或用 as any 绕过。
 *
 * 🔴🔴 第四轮（数据结构对齐）起，本文件的题目域**照 `ai-bkb-v2/数据结构.md` 定稿抄**，
 * 不再是「前端先行反推」的草案：块流 v2（§2.1②）、question 字段（§2.1①）、
 * 考点绑定 anchor（§2.1③）、标签 tag/question_tag（§2.1⑥）、题型目录与解题模型（§2.1④）、
 * 录入等级与执行阀（D-18/D-21）、待办表（D-14）、student 扩表（§一）都以那份文档为准。
 * 本文件与定稿有出入 = 本文件错，改这里，别在页面里兜。
 */

// ═══════════════════════════════════════════════════════════════
// 一、块流 v2（数据结构.md §2.1②）
// ═══════════════════════════════════════════════════════════════

/**
 * 🔴 一个单元格 = 块流的最小单元。四种块型是**白名单**，别的一律不许出现
 *（定稿 §三b 纪律⑥：块型白名单外的拒收）。
 *
 * - text   Markdown + 内联 `$LaTeX$`（本原型只按纯文本渲，不解析 md，够走查用）
 * - figure 图**只存指针**（asset = 资产哈希），宽度按百分比走
 *          🔴 width 不许省：老区 5467 个图块个个带百分比宽，丢了出纸质件全靠猜、宽图撑破版面
 * - option 选项**结构化**：一项一 cell，label 是标号，blocks 是这一项的内容（可含图）
 *          🔴 渲染层按行流式排布 ⇒ 短选项并排、长选项整体折行，但**一个 option 不许被拆散**
 * - table  真表格：行 → 单元格，支持跨行跨列与表头
 */
export type Cell = CellText | CellFigure | CellOption | CellTable

export interface CellText {
  type: 'text'
  /** Markdown（含内联 $LaTeX$）。存进来什么样、印出去什么样（定稿 D-21 执行阀③存取同构） */
  md: string
}

export interface CellFigure {
  type: 'figure'
  /** 资产哈希：真身在 asset 表（mock 里 = assets.ts 的内联 SVG），块流里只留指针 */
  asset: string
  /** 百分比宽度，如 '48%'。🔴 以载体宽度为基准，不是像素 */
  width: string
  caption?: string
}

export interface CellOption {
  type: 'option'
  /** 选项标号 A/B/C/D。🔴 不自动规整（定稿 §三b 纪律⑨：规整了「是否漏抽」就不可验证） */
  label: string
  /** 这一项的内容，可以是文字、也可以是图（313 个选项含图是老区实测） */
  blocks: Cell[]
}

export interface CellTable {
  type: 'table'
  rows: TableRow[]
}

export interface TableRow {
  cells: TableCell[]
}

/** 表格单元格：md 文本 + 跨列/跨行/是否表头 */
export interface TableCell {
  md: string
  colspan?: number
  rowspan?: number
  isHeader?: boolean
}

/** 块流的一行；一行里多个 cell = 天然的「一行多项」，换行交给渲染层 */
export interface BlockRow {
  cells: Cell[]
}

/**
 * 🔴 块流文档 = 题面 / 答案 / 解析各一份，形状完全一样。
 * v 是 schema 版本位（老区有、我 v1 草案漏了，将来无法演进）；本轮起一律 v: 2。
 */
export interface Block {
  v: 2
  rows: BlockRow[]
}

// ═══════════════════════════════════════════════════════════════
// 二、题目（数据结构.md §2.1①③⑥）
// ═══════════════════════════════════════════════════════════════

/**
 * 题源类 vs 生成类（定稿 D-9）：
 * - scan / manual    = 题源类（扫的、手录的）—— 题库页默认只看这两类
 * - model / pipeline = 生成类（模型生成的变式、管线批量产的）
 */
export type SourceKind = 'scan' | 'manual' | 'model' | 'pipeline'

/**
 * 🔴 题目状态四态：ingest 只入**草稿**，promote 才可见（老区实锤：录完看不见就是漏了这步）；
 * **退役 = 软删且真的只软删**，禁物理删。
 */
export type QuestionStatus = '草稿' | '已审' | '上架' | '退役'

/**
 * 🔴 标签域（定稿 D-19，2026-08-17 首发四个域已拍板）。
 * 标签 = 不成树、不定量的维度，一等公民、可索引、**开新域零改表**（这就是「预留维度」的实现法）。
 * 标签只做归类不做树 —— 要上树的东西是考点，别混。
 */
export type TagDomain = '场景' | '方法' | '思想' | '图形特征'

/** 🔴 标签域正本：页面要渲域筛选就吃这一个数组，别各写各的 */
export const TAG_DOMAINS: TagDomain[] = ['场景', '方法', '思想', '图形特征']

/** 一条标签 = 域 + 名（同名不同域是两条标签，如 方法·分类讨论 与 思想·分类讨论） */
export interface QuestionTag {
  domain: TagDomain
  name: string
}

/**
 * 🔴 考点挂靠的来历（定稿 §2.1③ anchor_json）：记住「这个挂靠是怎么来的、有多可信」。
 * - stage      哪一步挂上去的（录入解析 / 人工指定 / 母题继承 …）
 * - fallback   是不是退而求其次挂的（true = 没命中叶子只好兜底，要进审核台）
 * - confidence 0~1，低置信进审核台（录入执行阀①：< 0.85 滞留待审）
 */
export interface KpAnchor {
  stage: string
  fallback: boolean
  confidence: number
}

/**
 * 题↔考点绑定。
 * 🔴 kpId 必须是**叶子**（定稿的叶子闸）：挂在章级 = 学情分母失真，这是 v2 头号目标的命门。
 * 🔴 主考点恰一（isPrimary=true 的只能有一条）。
 * 🔴 这里存 id 不存名字：要显示名字走 kpNameOf(kpId)，别把名字冗余进题里。
 */
export interface QuestionKp {
  kpId: string
  isPrimary: boolean
  anchor: KpAnchor
}

/**
 * 题目（定稿 §2.1①）。
 *
 * 🔴🔴 两个**刻意没有**的字段，谁都别加回来：
 * - 没有 `score`（分值）—— 分值属于**载体位置**（同一道题在不同卷里分值可以不同），落卷的 item 上；
 * - 没有 `qno`（题号）—— 题号只是切分锚点，位置由载体的 ord 承载。
 *   ⇒ 用户判词「题号分值要抽离出来」的落点：**抽离不是挪个字段，是根本不进 question**。
 *   ⇒ 连带铁律：mock 的题面块流里也**不许**写「1. 」「（5 分）」这类前缀。
 *
 * 字段口径：
 * - qtypeCode / diffCode 走字典（dict.ts），不写死中文（老区四套题型编码并存的教训）
 * - patternId  题型目录（「这类题长什么样」），与 SolutionModel（「怎么解这类题」）分工不同
 * - sourceRaw  来源原文，如「2024 杭州十三中二模」「四上·空间与图形单元卷 P2」
 * - motherQid / variantOp  血缘：母题 + 变式算子（🔴 母题以本字段为 SSOT，不另建 trace 表）
 * - matchKey   排重键（认卷撞库 / 册内查重都吃它）
 * - treePath   教材树整条路径（版本→年级学期→单元→小节→考点），**归属**轴；
 *              与 kps（**能力标签**轴）并存、各管一头，末段常同名但不强制。
 */
export interface Question {
  id: string
  blocks: Block
  answerBlocks: Block
  analysisBlocks: Block
  qtypeCode: string
  diffCode: string
  patternId?: string
  sourceKind: SourceKind
  sourceRaw: string
  motherQid?: string
  variantOp?: string
  matchKey: string
  status: QuestionStatus
  createdAt: string
  kps: QuestionKp[]
  tags: QuestionTag[]
  treePath?: string[]
}

/** 字典项（定稿 §2.1⑤）：值域一律走字典表，页面别写死中文枚举 */
export interface DictItem {
  domain: 'qtype' | 'difficulty' | 'source' | 'artifact_kind'
  code: string
  label: string
  ord: number
  status: '在用' | '停用'
}

/**
 * 题型目录（定稿 §2.1④ question_pattern）：「这类题长什么样」，识别 / 归类用。
 * 🔴 kpIds **多值**（2026-08-17 用户拍板：模型可能考多个考点，不能说是一个）。
 */
export interface QuestionPattern {
  id: string
  name: string
  kpIds: string[]
  desc: string
  status: '在用' | '停用'
}

/**
 * 金标解题模型（定稿 §2.1④ solution_model）：「怎么解这类题」，举一反三的地基。
 * - triggerFeature   触发特征：看到什么就用它
 * - actionConclusion 动作与结论：怎么做、得到什么
 * - tier / freq      🔴 双旋钮（难度=模型表驱动，LLM 只匹配不自评）
 */
export interface SolutionModel {
  id: string
  name: string
  kpIds: string[]
  triggerFeature: string
  actionConclusion: string
  tier: number
  freq: number
  status: '在用' | '停用'
}

/**
 * 产线错因码 → 错因 的翻译层（定稿 §2.3 err_code_map）。
 * 🔴🔴 复合键 (kpId, code)：**同码两义**是实锤 —— 产线码 `dist`
 * 在「混合运算」线 = 运算律简算用错，在「整式」线 = 去括号/合并同类项，
 * 无作用域的 (code→cause) 映射必然串义，而这个歧义已经印进过交付报告。
 */
export interface ErrCodeMapEntry {
  kpId: string
  code: string
  causeId: string
  /** 这条映射在**本考点作用域**下的人话解释（同码两义就靠这句区分） */
  note: string
}

/** 资料清单的一条成品记录（挂账用，不管生产过程） */
export interface Artifact { id: string; name: string; kind: '打卡册' | '专项卷' | '举一反三' | '讲义';
  status: '在产' | '已交付' | '已上架'; deliveredAt?: string; link?: string; note?: string }

/** 单题判定：qno = 卷面题号（🔴 题号长在**批改的那张卷**上，不长在题上）；verdict 三态，'?' = 存疑待人工 */
export interface ItemVerdict { qno: number; verdict: '√' | '×' | '?'; note?: string; kp?: string }

/**
 * 🔴🔴 批次状态九态 —— **全站唯一口径**（第三轮用户拍板）。
 *
 * 旧的四态（待批/待终审/已确认/已出件）把「机器在干什么」和「谁该动手」糊在一起，
 * 结果队列里一堆「待批」，人根本看不出哪条要自己出手、哪条只是排队。
 * 九态的分法只有一条准绳：**这一格现在卡在谁手上**（见 STATE_MACHINE.actor）。
 *
 * 🔴 只有三态是人的活（actor='人'）：待人工认卷 / 待终审 / 故障。
 *    其余系统态别催人，队列页把它们摆出来是让人「看得见在飞」，不是让人点。
 * 🔴 状态之间只能照 STATE_MACHINE.exits 走，页面不许自造中间态或省略步骤。
 */
export type BatchState =
  | '收件中' | '待认卷' | '待人工认卷' | '批改中' | '待终审'
  | '已确认' | '待出件' | '已出件' | '故障'

/**
 * 状态机一行：这个状态是谁的活、为什么停在这儿、往哪走。
 * - actor  '系统' = 机器推进（人只看）；'人' = 🔴 卡在人手上，不点它就永远不动；'终态' = 到头了
 * - reason 停留原因写**大白话**（队列页直接渲这句，别改写成术语）
 * - exits  出口，写「条件→去哪」，一个状态可以有多个出口
 */
export interface StateMeta { state: BatchState; actor: '系统' | '人' | '终态'; reason: string; exits: string[] }

/** 🔴 九行状态机正本：页面照渲，别在页面里重写一份状态说明 */
export const STATE_MACHINE: StateMeta[] = [
  { state: '收件中', actor: '系统', reason: '照片落收件箱，90 秒判稳防拍一半', exits: ['判稳 → 待认卷'] },
  { state: '待认卷', actor: '系统', reason: '排队等编排器（串行 WIP=1）', exits: ['命中 → 批改中', '零命中 / 多命中 → 待人工认卷'] },
  { state: '待人工认卷', actor: '人', reason: '题面认不出是哪张卷', exits: ['人工指定 → 批改中'] },
  { state: '批改中', actor: '系统', reason: '无头 session 整页直读 + 机器复核', exits: ['全绿 → 已确认（静默）', '存疑 → 待终审'] },
  { state: '待终审', actor: '人', reason: '逐题 √/×/去掉，可整批打回', exits: ['确认 → 已确认', '打回 → 批改中（轮次 +1）'] },
  { state: '已确认', actor: '系统', reason: '判定定稿', exits: ['→ 待出件'] },
  { state: '待出件', actor: '系统', reason: 'agent 写总结 → 渲报告 → 推送', exits: ['→ 已出件'] },
  { state: '已出件', actor: '终态', reason: '报告挂批次', exits: [] },
  { state: '故障', actor: '人', reason: '任何环节异常就地挂起，不自动重试', exits: ['retry → 回原状态'] },
]

/** 🔴 该我动手的三态（队列页 mine=1、学员卡待办数、工作台待办全吃这一个口径，别各写各的） */
export const HUMAN_STATES: BatchState[] = ['待人工认卷', '待终审', '故障']

/** 查某状态的那行说明（状态是九态闭集，查不到说明传了脏值，返回 undefined 让调用方自己兜） */
export function stateMetaOf(state: BatchState): StateMeta | undefined {
  return STATE_MACHINE.find((m) => m.state === state)
}

/**
 * 一天的批改批次（挂在某学员的某条轨的第 dayInTrack 天）。
 *
 * - stuckSince  🔴 **停留起点**（进入当前状态的时刻，ISO 串）：队列页的「停留多久」全靠它算。
 *   已出件这类终态可以不写；在飞的批次必须写，否则队列上看不出谁卡住了。
 * - candidates  只有「待人工认卷」用：编排器撞出来的候选卷名（多命中时人就照这个选）
 * - note        这一格的状态附注（故障原文 / 认卷撞库说明）。🔴 写机器原话，别改写成客气话
 */
export interface Batch { id: string; dayInTrack: number; date: string; state: BatchState;
  score?: { right: number; total: number }; doubts?: number; items: ItemVerdict[];
  stuckSince?: string; candidates?: string[]; note?: string }

/** 🔴 轨 = 考点/专项（如「有理数混合运算」）；学情按轨分账，跨轨不混算 */
export interface Track { id: string; name: string; bookRef?: string; status: '进行中' | '已完结'; days: Batch[] }

/**
 * 学员（定稿 §一 student 扩表，2026-08-17 用户点名「学员统一管理必须做，实体要非常全面」）。
 *
 * 🔴 红线不变：**一律代号制**，真名 / 联系方式永不入库、mock 里更不许出现；
 *    触达家长永远在用户手机侧按代号对应。
 * - textbookVer 教材版本（出题与认卷都要）
 * - serviceTier 服务档位（订阅特训 7 天 / 21 天 / 一对一 / 打卡客户…）
 * - profile     🔴 肖像特征句数组（「先看后算防硬算」「计算准思维欠」），备课与出题的个性化依据
 */
export interface Student {
  code: string
  grade: string
  textbookVer: string
  status: '试听' | '在读' | '暂停' | '结课'
  serviceTier: string
  joinedAt: string
  profile: string[]
  note?: string
  tracks: Track[]
}

// ───────────────────────────────────────────────────────────────
// 以下为 V2.1 第二轮扩展（走查判词：低频但要记账的东西也得有地方落）
// ───────────────────────────────────────────────────────────────

/** 教材树节点的五种层级，顺序固定：版本 → 年级学期 → 单元 → 小节 → 考点 */
export type TreeKind = '版本' | '年级学期' | '单元' | '小节' | '考点'

/**
 * 教材树节点（题库多级目录 + 知识图谱页共用同一棵树）。
 * - key   全树唯一，形如 'renjiao/g4a/u5/s2/k1'，可直接当 antd Tree 的 key
 *         🔴 考点叶的 key **就是** Question.kps[].kpId（两处同一套 id，别再造第二套）
 * - kind  见 TreeKind；'考点' 一律是叶子，其余层级可以有 children
 * - children 缺省 = 这一枝还没铺（页面上要标「未铺」，别渲成空目录假装铺好了）
 */
export interface TreeNode { key: string; label: string; kind: TreeKind; children?: TreeNode[] }

/**
 * 考察模型 = 「一类题怎么造」的参数化配方（举一反三 / 打卡册的产题底座）。
 * 🔴 与 SolutionModel（怎么解）、QuestionPattern（长什么样）三者分工别混：本表管**怎么造**。
 * - paramSummary 参数表的人话摘要（不是完整 DSL，完整的在 dslRef 指的文件里）
 * - originQuestionIds 这个模型是从哪几道母题蒸馏出来的（可空 = 手写立的模型）
 * - status 'draft' = 参数表写了但没接出题器，questionCount 通常为 0
 * - kpNames 🔴 维护区三样（错因/考察模型/题目）都要能溯源到知识图谱。
 *   **空数组 = 溯源断点**，维护区要把它当活儿看，不是当正常态。
 */
export interface ExamModel { id: string; name: string; paramSummary: string;
  status: 'active' | 'draft'; questionCount: number; originQuestionIds: string[];
  kpNames: string[]; dslRef: string; note: string }

/**
 * 错因（词表层）：批改沉淀下来的错误类型，全局唯一一份。
 * - kpNames    这条错因常发生在哪些考点上；**空数组 = 跨考点通用错因**（如誊写笔误）
 * - mappedCodes 机器批改输出的原始错因码。🔴 真正的翻译权威是 errCodeMap 的
 *   **复合键 (kpId, code)**（同码两义），本字段只是错因页「这条错因收编了哪些码」的展示口径。
 */
export interface ErrorCause { id: string; name: string; definition: string;
  kpNames: string[]; mappedCodes: string[] }

/**
 * 批改沉淀：一条 = 某学员某轨某天某题命中了某条错因。
 * 🔴 铁律③仍然管着这里：deposit 自带 track，按错因汇总时只做**计数**，
 * 绝不把不同轨的沉淀拉平算正确率或画一条趋势线。
 */
export interface CauseDeposit { date: string; student: string; track: string;
  dayInTrack: number; qno: number; causeId: string; note: string }

/** 录入逐题灯：绿 = 直接进库；黄 = 进库但挂着工单，核过才转正；红 = 拦下隔离，不进主表 */
export type IngestLight = '绿' | '黄' | '红'

/**
 * 🔴 录入源分类（定稿 D-18）：闸口径完全不同。
 * - 文字层  docx / 文字型 PDF → 确定性直读，有**守恒闸**（图数/公式数/字符多重集可对基准）
 * - 图片OCR 无文字层 → MinerU 本地 OCR，**没有守恒基准** ⇒ 置信度 + 双跑对照 + 人审必过
 */
export type IngestSrcKind = '文字层' | '图片OCR'

/**
 * 🔴 审核等级（定稿 D-21 矩阵）：复杂度 × 源 决定「要不要人看、看多细」。
 * L0=闸全绿直入 ｜ L1=抽检 ｜ L2=逐题速审 ｜ L3=逐题细审 ｜ 人工=全程人来。
 * 🔴 拍照源整体比文字层源**高一级**（OCR 无守恒基准，天然多一分不确定）；手写稿一律人工。
 */
export type ReviewLevel = 'L0' | 'L1' | 'L2' | 'L3' | '人工'

/**
 * 录入批次里的一行。
 * - questionId  有值 = 这行成了题库里的题（可点进详情）；无值 = 还没成题（隔离/待补）
 * - reason      黄灯红灯必须写原因，绿灯可空
 * - reviewLevel 🔴 逐条定级（同一批里复杂度不同的题等级也不同：纯文本 L0、两图一表 L2…）
 */
export interface IngestItem { seq: number; title: string; light: IngestLight;
  reason?: string; questionId?: string; reviewLevel: ReviewLevel }

/**
 * 录入记录：一次录入动作的账。
 * 🔴 counts 是**题级**口径且必须自洽：accepted + queued + rejected = total。
 * 行级的隔离（解析出来但根本不成题的行）不计入 counts，写在 gateSummary 里、挂到审核台。
 * - srcKind    🔴 源类型决定闸口径（见 IngestSrcKind），图片源批次默认不许直接过
 * - templateId 这批用哪张录入模板切的（空 = 没有对得上的模板，现切的）
 */
export interface IngestBatch { id: string; time: string; source: string; srcKind: IngestSrcKind;
  counts: { total: number; accepted: number; queued: number; rejected: number };
  gateSummary: string; templateId?: string; items: IngestItem[] }

/**
 * 录入模板库（定稿 D-21 ingest_template）= 老区「版式方言」的正规化。
 * - layoutTraits 怎么认出「这版式归我管」
 * - rulesRef     切割规则 / 脚本指针
 */
export interface IngestTemplate { id: string; name: string; layoutTraits: string;
  rulesRef: string; sampleRef?: string; status: '在用' | '停用'; createdAt: string }

/** 审核工单四类：图审 / 题审转正 / 考点低置信 / 隔离行 */
export type ReviewKind = '图审' | '题审转正' | '考点低置信' | '隔离行'

/**
 * 审核台工单。
 * - detail     🔴 尽量写**工单原话**（机器拦下时说了什么），别改写成客气话，人审时要的就是原话
 * - candidates 只有「考点低置信」用：机器给的候选考点，按置信度从高到低
 * - 🔴 questionId / batchId / modelId **至少有一个**，否则这条工单没有着落点，人审点开无处可去。
 *   常见组合：图审=questionId+batchId；隔离行=只有 batchId（还没成题）；
 *   考点低置信=questionId+batchId，或题还没入库时挂 modelId（等某个考察模型先定名）。
 */
export interface ReviewTicket { id: string; kind: ReviewKind; title: string; detail: string;
  batchId?: string; questionId?: string; modelId?: string; candidates?: string[];
  priority: '高' | '中' | '低'; createdAt: string; state: '待处理' | '处理中' }

/**
 * 待办（定稿 D-14 todo 表）：自由事项表，人和 agent 都能往里写。
 * 🔴 页面**只读**（你只查看），增删改走 skill/agent 直接写库；
 *    与「业务现算的待办视图」（工作台那份：卡在人手上的批次）**并列不合并** —— 两回事。
 * - line 归哪条产线；ref 关联指针（批次/题/册/判据，可空）
 */
export interface Todo {
  id: string
  title: string
  detail: string
  line: '录入' | '批改' | '出题' | '资料' | '其他'
  status: '待办' | '进行中' | '已完成' | '已取消'
  priority: '高' | '中' | '低'
  due?: string
  ref?: string
  createdBy: '人' | 'agent'
  createdAt: string
  doneAt?: string
}
