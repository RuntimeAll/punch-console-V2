/**
 * mock 数据统一出口。页面组一律 `import { ... } from '@/mock'`，
 * 不要深入 '@/mock/questions' 之类的具体文件（将来换数据源只改本文件）。
 */
export type {
  Artifact, Batch, BatchState, Block, ItemVerdict, Question, StateMeta, Student, Track,
  // 第二轮扩展
  CauseDeposit, ErrorCause, ExamModel, IngestBatch, IngestItem, IngestLight,
  ReviewKind, ReviewTicket, TreeKind, TreeNode,
  // 🔴 第四轮（数据结构定稿对齐）：块流 v2 / 题目字段 / 标签 / 题型目录 / 解题模型 / 录入等级 / 待办
  BlockRow, Cell, CellFigure, CellOption, CellTable, CellText, TableCell, TableRow,
  DictItem, ErrCodeMapEntry, IngestSrcKind, IngestTemplate, KpAnchor, QuestionKp, QuestionPattern,
  QuestionStatus, QuestionTag, ReviewLevel, SolutionModel, SourceKind, TagDomain, Todo,
} from './types'

/** 🔴 九格状态机正本 + 「该我动手」三态，页面照渲，别在页面里重写一份 */
export { HUMAN_STATES, STATE_MACHINE, stateMetaOf } from './types'

/** 🔴 标签四域正本（D-19）：开新域改这一个数组，页面零改 */
export { TAG_DOMAINS } from './types'

export { questions, findQuestion, questionsUnderPath, kpVocabulary, sourceQuestions, variantsOf } from './questions'
export { students, findStudent, allBatches, pendingBatches, NOW } from './students'
export type { PendingRow } from './students'
export { artifacts } from './artifacts'

// ── 第四轮：块流 v2 的构造器与读取器 ─────────────────────────────
// 🔴 造块流用构造器、读文字用读取器；**页面不许自己递归 rows/cells**，渲题只有 <BlockFlow> 一个入口
export {
  EMPTY_DOC, docOf, figure, filterRows, firstTextOf, hasFigureIn, hasOptionIn,
  isEmptyDoc, option, para, plainTextOf, row, rowStartsWith, table, text,
} from './blocks'

// ── 第四轮：字典（题型 8 类 / 难度 4 档）与资产表 ──────────────────
export { DIFF_MAX, dictItems, dictLabel, dictOf, diffLabel, diffOrd, qtypeLabel } from './dict'
export type { Asset } from './assets'
export { assets, findAsset } from './assets'

// ── 第四轮：标签词池 / 题型目录 / 解题模型 / 错因码翻译 / 待办 / 录入模板 ──
export { tagDomains, tagPool, tagText, tagsOfDomain } from './tags'
export { findPattern, findSolutionModel, modelsOfKpId, questionPatterns, questionsOfPattern, solutionModels } from './patterns'
export { ambiguousCodes, codesOfKp, errCodeMap, resolveErrCode } from './err-code-map'
export { openTodos, todoCountByLine, todos, todosOf } from './todos'
export { findIngestTemplate, ingestTemplates } from './ingest-templates'

// ── 第三轮：批改队列取数层（队列页只吃这两个函数）──────────────────
export { queueRows, pendingMine, stuckLabel } from './queue'
export type { QueueRow } from './queue'

// ── 第二轮扩展：教材树 / 考察模型 / 错因 / 录入记录 / 审核队列 ──────────
export {
  kgTree, flattenTree, kpLeaves, findTreeNode, treePathText, isStub, labelPathMap,
  // 🔴 第四轮：题目存 kpId 不存名字，显示名字一律走 kpNameOf
  OFF_TREE_KPS, isOnTreeKp, kpIdOf, kpNameOf,
} from './kg-tree'
export { examModels, findExamModel, modelsOfQuestion } from './exam-models'
export { errorCauses, causeDeposits, findErrorCause, depositCountByCause, depositsOfCause } from './error-causes'
export { autoPassRate, ingestBatches, findIngestBatch, levelTotals, lightTotals } from './ingest'
export { reviewQueue, ticketsOfKind, ticketCountByKind, ticketsOfQuestion, ticketsOfBatch, ticketsOfModel } from './review'
