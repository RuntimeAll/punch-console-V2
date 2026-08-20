/**
 * 真库页类型 —— kb 薄读 API（console/server/kb-read-api.mjs）响应形状的 TS 镜像。
 *
 * 🔴 为什么另立一份而不改 `@/mock/types.ts`：
 *   mock/types.ts 是**公共契约件**（原型走查用的一份），改它会牵动全部 mock 页；
 *   真库页吃的是库里的真形状（含 API 现拼的中文标签、分页壳、断链标记），
 *   两者形状本就不同 —— 各自一份，谁也不兜谁。
 *
 * 🔴 块流的表格形状以 `工具箱/库/gates.py` 的校验器为准（它是入库硬闸，
 *   库里存的必然是它认的形状）：`table.rows = [行][格][块列表]`。
 *   mock/types.ts 里那份 `{cells:[{md,isHeader}]}` 是原型期草案，**与闸不一致**——
 *   本文件按闸走，同时对草案形状做兼容读（见 KbBlocks），不静默渲成空表。
 */

// ── 块流 v2 ─────────────────────────────────────────────────────────────
export type KbCell = KbCellText | KbCellFigure | KbCellOption | KbCellTable

/** 块级 role 枚举（数据结构 §2.1② 第三条路）：标"这块是什么"，可缺省 */
export type KbRole = '题面' | '答案' | '解析' | '点拨' | '栏目'

export interface KbCellText {
  type: 'text'
  /** Markdown + 内联 $LaTeX$（存取同构：存什么用什么） */
  md: string
  role?: KbRole
}

export interface KbCellFigure {
  type: 'figure'
  /** 资产哈希；真身在 asset 表 + 知识库/资产/ 下 */
  asset: string
  width?: string
  caption?: string
  role?: KbRole
}

export interface KbCellOption {
  type: 'option'
  label: string
  blocks: KbCell[]
  role?: KbRole
}

/** 表格块：闸认两种载荷——GFM 整表 md，或结构化 rows[行][格][块列表] */
export interface KbCellTable {
  type: 'table'
  md?: string
  rows?: KbCell[][][] | { cells?: { md?: string; isHeader?: boolean; colspan?: number; rowspan?: number }[] }[]
  role?: KbRole
}

export interface KbRow {
  cells: KbCell[]
}

/** 一份块流文档；parse_error 有值 = 库里那条 JSON 坏了（API 如实报，页面必须显式标） */
export interface KbDoc {
  v: number
  rows: KbRow[]
  parse_error?: string
}

// ── /api/kb/stats ───────────────────────────────────────────────────────
export interface KbStats {
  db_path: string
  readonly: boolean
  table_total: number
  nonempty_total: number
  rows: { table: string; count: number }[]
}

// ── /api/kb/kg/tree ─────────────────────────────────────────────────────
export interface KbKpNode {
  id: string
  name: string
  level: '版本' | '年级学期' | '单元' | '小节' | '考点'
  ord: number | null
  status: '现行' | '未铺' | '退役'
  note: string | null
  alias_count: number
  /** 直挂本节点的题数（叶子闸下应只有考点层有值） */
  q_count: number
  /** 子树合计题数 */
  q_total: number
  children: KbKpNode[]
}

export interface KbTree {
  roots: KbKpNode[]
  kp_total: number
  leaf_total: number
  unbuilt_total: number
}

// ── /api/kb/kg/aliases ──────────────────────────────────────────────────
export interface KbAliasRow {
  kp_id: string
  alias: string
  alias_kind: string | null
  kp_name: string | null
  kp_level: string | null
  kp_status: string | null
  /** 🔴 别名挂了个不存在的叶＝断链 */
  missing: boolean
}

export interface KbAliases {
  total: number
  shown: number
  covered_kp: number
  kind_stat: { kind: string; count: number }[]
  /** 一词多挂：同一别名指向两片以上叶 ⇒ resolve 二义（空数组=闸绿） */
  ambiguous: { alias: string; kp_count: number }[]
  broken_total: number
  filters: { kp_id: string | null; kind: string | null; q: string | null }
  rows: KbAliasRow[]
}

// ── /api/kb/kp/:id ──────────────────────────────────────────────────────
export interface KbKpDetail {
  id: string
  name: string
  level: string
  ord: number | null
  status: string
  note: string | null
  /** 🔴 对齐-003 起「这类题长什么样」归 kp 自己这四列（题型实体层停用） */
  emphasis: string | null
  freq: string | null
  diff_code: string | null
  diff_label: string | null
  desc: string | null
  path: { id: string; name: string; level: string }[]
  is_leaf: boolean
  children: { id: string; name: string; level: string; status: string; q_count: number }[]
  leaf_total: number
  zero_mount_leaves: { id: string; name: string; level: string; status: string; q_count: number }[]
  q_count: number
  q_total: number
  aliases: { alias: string; alias_kind: string | null }[]
  exam_models: { id: string; name: string; dsl_ref: string | null; status: string }[]
  solution_models: { id: string; name: string; tier: number | null; freq: number | null; status: string }[]
  patterns: { id: string; name: string; status: string }[]
  questions: {
    id: string
    stem: string
    status: string
    is_primary: boolean
    qtype_label: string | null
    diff_label: string | null
  }[]
}

// ── /api/kb/models ──────────────────────────────────────────────────────
/** 模型挂的考点引用；missing=true 表示 kp_ids_json 指了个库里没有的 id（断链） */
export interface KbKpRef {
  id: string
  name: string | null
  level: string | null
  status: string | null
  missing: boolean
}

export interface KbExamModel {
  id: string
  name: string
  kps: KbKpRef[]
  kp_parse_error: string | null
  kp_broken: number
  dsl_ref: string | null
  params: Record<string, unknown> | null
  params_raw: string | null
  note: string | null
  status: string
  question_count: number
}

export interface KbSolutionModel {
  id: string
  name: string
  kps: KbKpRef[]
  kp_parse_error: string | null
  kp_broken: number
  trigger_feature: string
  action_conclusion: string
  tier: number | null
  freq: number | null
  status: string
}

export interface KbPatternRow {
  id: string
  name: string
  kps: KbKpRef[]
  desc: string | null
  emphasis: string | null
  freq: string | null
  diff_code: string | null
  diff_label: string | null
  status: string
}

export interface KbModels {
  exam: { total: number; in_use: number; question_total: number; rows: KbExamModel[] }
  solution: { total: number; in_use: number; rows: KbSolutionModel[] }
  /** 🔴 对齐-003 起停用：如实回 disabled + 零行，页面写「停用」，不许拿别的东西把空表装满 */
  pattern: {
    total: number
    disabled: boolean
    disabled_note: string
    question_with_pattern_id: number
    kp_desc_total: number
    rows: KbPatternRow[]
  }
  trace_gap: {
    exam_no_kp: number
    exam_broken_kp: number
    solution_no_kp: number
    solution_broken_kp: number
  }
}

// ── /api/kb/criteria ────────────────────────────────────────────────────
export interface KbCriterion {
  id: string
  line: string
  scene: string
  rule: string
  why: string | null
  source_ref: string | null
  status: '现行' | '废止'
  superseded_by: string | null
  superseded_by_info: {
    id: string
    scene: string | null
    line: string | null
    status: string | null
    missing: boolean
  } | null
  created_at: string | null
}

export interface KbCriteria {
  total: number
  live_total: number
  dead_total: number
  shown: number
  line_stat: { line: string; total: number; live: number; dead: number }[]
  filters: { line: string | null; status: string | null; q: string | null }
  rows: KbCriterion[]
}

// ── /api/kb/templates ───────────────────────────────────────────────────
export interface KbTemplate {
  id: string
  name: string | null
  purpose: string | null
  book_kinds: string | null
  params: Record<string, unknown> | null
  params_raw: string | null
  pitfalls: string | null
  version: string | null
  status: '在用' | '停用'
  sample_asset: string | null
  sample_rel_path: string | null
  registered_by: string | null
  updated_at: string | null
  artifact_count: number
}

export interface KbTemplates {
  total: number
  in_use: number
  with_sample: number
  shown: number
  filters: { status: string | null }
  rows: KbTemplate[]
}

// ── /api/kb/semantic/health ─────────────────────────────────────────────
export interface KbSemanticHealth {
  ok: boolean
  port: number
  health?: { model?: string; dim?: number; uptime_s?: number; served?: number }
  error?: string
  hint?: string
}

// ── /api/kb/questions ───────────────────────────────────────────────────
export interface KbQuestionRow {
  id: string
  stem: string
  qtype_code: string | null
  qtype_label: string | null
  diff_code: string | null
  diff_label: string | null
  source_kind: string | null
  source_label: string | null
  source_raw: string | null
  kps: { id: string; name: string; is_primary: boolean }[]
  status: string
  has_mother: boolean
  variant_count: number
  has_lineage: boolean
  variant_op: string | null
  created_at: string | null
  // ── PRD-007 来源三维（prov 现取；来源册是 API 现推的，推法随行带出来） ──
  textbook: string | null
  use_level: string | null
  version_conf: string | null
  src_book: string | null
  src_book_from: string | null
  /** 挂在这道题上的审核工单（待处理的必须在列表里看得见） */
  tickets: { id: string; kind: string; status: string; note: string | null; created_at: string | null }[]
  ticket_open: number
  /** 语意搜索时的余弦相似度（非 --like 查询为 undefined） */
  score?: number | null
}

/** 来源三维下拉的候选值（🔴 全库口径，不随当前筛选缩水） */
export interface KbQuestionFacets {
  textbook: { value: string | null; label: string; count: number }[]
  use_level: { value: string | null; label: string; count: number }[]
  src_book: { value: string | null; label: string; count: number }[]
  status: { value: string | null; label: string; count: number }[]
  ticket_open_total: number
  question_total: number
}

export interface KbQuestionPage {
  total: number
  page: number
  size: number
  kp_filter: { id: string; name: string; level: string; status: string; matched_by: string; word: string } | null
  /** 🔴 这个考点词在库里 resolve 不到（页面照实标，别当"没筛"糊过去） */
  kp_unresolved: string | null
  unresolved: Record<string, string[]> | null
  filters: {
    kp: string | null
    status: string | null
    source_kind: string | null
    qtype: string[]
    difficulty: string[]
    tag: string[]
    unused: boolean | null
    textbook: string[]
    use_level: string[]
    src_book: string[]
    ticket: boolean | null
    like: string | null
  }
  /** --like 语意搜索的说明（未用语意搜索时为 null）；missing=候选里还没算向量的题数 */
  semantic: {
    model: string
    dim: number
    candidates: number
    vectored: number
    missing: number
    serve_ms: number | null
    query: string
    sql_candidates: number
  } | null
  facets: KbQuestionFacets
  rows: KbQuestionRow[]
}

// ── /api/kb/questions/:id ───────────────────────────────────────────────
export interface KbKpBinding {
  id: string
  name: string
  is_primary: boolean
  anchor: { stage?: string; fallback?: boolean; confidence?: number } | null
  path: { id: string; name: string; level: string }[]
}

export interface KbQuestionDetail {
  id: string
  blocks: KbDoc | null
  answer: KbDoc | null
  analysis: KbDoc | null
  qtype_code: string | null
  qtype_label: string | null
  diff_code: string | null
  diff_label: string | null
  pattern_id: string | null
  source_kind: string | null
  source_label: string | null
  source_raw: string | null
  prov: Record<string, unknown> | null
  variant_op: string | null
  match_key: string | null
  status: string
  created_at: string | null
  updated_at: string | null
  kps: KbKpBinding[]
  tags: { id: string; domain: string; name: string }[]
  lineage: {
    mother: { id: string; stem?: string; status?: string; missing?: boolean } | null
    variants: { id: string; stem: string; variant_op: string | null; status: string }[]
  }
  papers: {
    paper_id: string
    title: string
    kind: string
    paper_ord: number | null
    paper_status: string
    item_ord: number
    section: string | null
    score: number | null
    artifact_id: string | null
    artifact_name: string | null
  }[]
}

// ── /api/kb/artifacts ───────────────────────────────────────────────────
export interface KbArtifactRow {
  id: string
  name: string
  kind: string
  status: string
  source_line: string | null
  template_id: string | null
  kp_ids: string[]
  delivered_at: string | null
  link: string | null
  note: string | null
  created_at: string | null
  paper_count: number
  item_count: number
}

export interface KbArtifactDetail extends Omit<KbArtifactRow, 'paper_count' | 'item_count'> {
  files: Record<string, string> | null
  papers: {
    id: string
    kind: string
    title: string
    ord: number | null
    status: string
    layout: Record<string, unknown> | null
    created_at: string | null
    items: {
      ord: number
      section: string | null
      score: number | null
      question_id: string
      q_status: string | null
      stem: string
    }[]
  }[]
}

// ── /api/kb/papers/:id ──────────────────────────────────────────────────
export interface KbPaperDetail {
  id: string
  title: string
  kind: string
  ord: number | null
  status: string
  created_at: string | null
  layout: Record<string, unknown> | null
  artifact: { id: string; name: string; kind: string; status: string } | null
  items: {
    ord: number
    section: string | null
    score: number | null
    note: string | null
    question_id: string
    q_status: string | null
    missing: boolean
    qtype_label: string | null
    diff_label: string | null
    blocks: KbDoc | null
    answer: KbDoc | null
    analysis: KbDoc | null
  }[]
}
