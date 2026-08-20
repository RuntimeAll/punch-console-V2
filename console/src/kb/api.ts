/**
 * 真库取数口 —— 只有 GET，一个写口都没有（写动作归 agent/skill/工具箱脚本）。
 * dev 下走 vite 代理 /api/kb → http://127.0.0.1:4310（见 vite.config.ts）。
 */
import type {
  KbAliases,
  KbArtifactDetail,
  KbArtifactRow,
  KbCriteria,
  KbKpDetail,
  KbModels,
  KbPaperDetail,
  KbQuestionDetail,
  KbQuestionPage,
  KbSemanticHealth,
  KbStats,
  KbTemplates,
  KbTree,
} from './types'

const BASE = '/api/kb'

/** API 挂了要**看得见**：不静默返回空壳，一律抛出让页面渲错误条 */
async function get<T>(path: string): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, { headers: { Accept: 'application/json' } })
  } catch (e) {
    throw new Error(`连不上读 API（:4310 起了吗？）：${String(e)}`)
  }
  const text = await res.text()
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch {
    throw new Error(`读 API 返回的不是 JSON（HTTP ${res.status}）：${text.slice(0, 120)}`)
  }
  if (!res.ok) {
    const msg = (body as { error?: string })?.error ?? `HTTP ${res.status}`
    throw new Error(msg)
  }
  return body as T
}

export const kbApi = {
  stats: () => get<KbStats>('/stats'),
  tree: () => get<KbTree>('/kg/tree'),
  aliases: (q: { kp_id?: string; kind?: string; q?: string } = {}) => {
    const p = new URLSearchParams()
    if (q.kp_id) p.set('kp_id', q.kp_id)
    if (q.kind) p.set('kind', q.kind)
    if (q.q) p.set('q', q.q)
    const s = p.toString()
    return get<KbAliases>(`/kg/aliases${s ? `?${s}` : ''}`)
  },
  kp: (id: string) => get<KbKpDetail>(`/kp/${encodeURIComponent(id)}`),
  models: () => get<KbModels>('/models'),
  criteria: (q: { line?: string; status?: string; q?: string } = {}) => {
    const p = new URLSearchParams()
    if (q.line) p.set('line', q.line)
    if (q.status) p.set('status', q.status)
    if (q.q) p.set('q', q.q)
    const s = p.toString()
    return get<KbCriteria>(`/criteria${s ? `?${s}` : ''}`)
  },
  templates: (q: { status?: string } = {}) => {
    const p = new URLSearchParams()
    if (q.status) p.set('status', q.status)
    const s = p.toString()
    return get<KbTemplates>(`/templates${s ? `?${s}` : ''}`)
  },
  /** 语意 serve 探活：挂了不抛错，回 {ok:false}——页面据此把 --like 搜索框收起来 */
  semanticHealth: () =>
    get<KbSemanticHealth>('/semantic/health').catch(
      (e): KbSemanticHealth => ({ ok: false, port: 4315, error: String(e?.message ?? e) }),
    ),
  questions: (q: {
    kp?: string
    status?: string
    source_kind?: string
    textbook?: string[]
    use_level?: string[]
    src_book?: string[]
    ticket?: boolean
    like?: string
    page?: number
    size?: number
  }) => {
    const p = new URLSearchParams()
    if (q.kp) p.set('kp', q.kp)
    if (q.status) p.set('status', q.status)
    if (q.source_kind) p.set('source_kind', q.source_kind)
    for (const v of q.textbook ?? []) p.append('textbook', v)
    for (const v of q.use_level ?? []) p.append('use_level', v)
    for (const v of q.src_book ?? []) p.append('src_book', v)
    if (q.ticket) p.set('ticket', '1')
    if (q.like) p.set('like', q.like)
    p.set('page', String(q.page ?? 1))
    p.set('size', String(q.size ?? 20))
    return get<KbQuestionPage>(`/questions?${p.toString()}`)
  },
  question: (id: string) => get<KbQuestionDetail>(`/questions/${encodeURIComponent(id)}`),
  artifacts: () => get<{ total: number; rows: KbArtifactRow[] }>('/artifacts'),
  artifact: (id: string) => get<KbArtifactDetail>(`/artifacts/${encodeURIComponent(id)}`),
  paper: (id: string) => get<KbPaperDetail>(`/papers/${encodeURIComponent(id)}`),
}

/** 状态/来源的中文选项（值域正本=库里的 CHECK 与 dict_item；这里只做筛选器下拉） */
export const QUESTION_STATUS = ['草稿', '已审', '上架', '退役']
export const SOURCE_KINDS = [
  { value: 'scan', label: '扫描/拍照录入' },
  { value: 'manual', label: '人工录入' },
  { value: 'model', label: '模型生成' },
  { value: 'pipeline', label: '管线生成' },
]
