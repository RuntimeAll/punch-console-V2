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
}

export interface KbQuestionPage {
  total: number
  page: number
  size: number
  kp_filter: { id: string; name: string; level: string; status: string; matched_by: string; word: string } | null
  /** 🔴 这个考点词在库里 resolve 不到（页面照实标，别当"没筛"糊过去） */
  kp_unresolved: string | null
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
