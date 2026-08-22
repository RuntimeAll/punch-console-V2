/**
 * 真库取数口 —— 只有 GET，一个写口都没有（写动作归 agent/skill/工具箱脚本）。
 * dev 下走 vite 代理 /api/kb → http://127.0.0.1:4310（见 vite.config.ts）。
 */
import type {
  KbAliases,
  KbArtifactDetail,
  KbArtifactList,
  KbCriteria,
  KbDeliverables,
  KbKgPatterns,
  KbKpDetail,
  KbModels,
  KbPaperDetail,
  KbPapers,
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
  artifacts: () => get<KbArtifactList>('/artifacts'),
  artifact: (id: string) => get<KbArtifactDetail>(`/artifacts/${encodeURIComponent(id)}`),
  /** 卷库列表（paper 级）：卷名 / 题数 / 满分 / 时长 / 所属册 */
  papers: (q: { kind?: string; status?: string; artifact_id?: string } = {}) => {
    const p = new URLSearchParams()
    if (q.kind) p.set('kind', q.kind)
    if (q.status) p.set('status', q.status)
    if (q.artifact_id) p.set('artifact_id', q.artifact_id)
    const s = p.toString()
    return get<KbPapers>(`/papers${s ? `?${s}` : ''}`)
  },
  paper: (id: string) => get<KbPaperDetail>(`/papers/${encodeURIComponent(id)}`),
  /** 讲义 173 题型的下落（对齐-003）：103 已锚进 kp.desc / 70 待人工归位 */
  kgPatterns: () => get<KbKgPatterns>('/kg/patterns'),
  /** 成品速览：artifact.files_json 拉平成「一件一行」。ext 多值（图=png+jpg+jpeg）逗号传 */
  deliverables: (q: { ext?: string[]; kind?: string; q?: string; page?: number; size?: number } = {}) => {
    const p = new URLSearchParams()
    if (q.ext?.length) p.set('ext', q.ext.join(','))
    if (q.kind) p.set('kind', q.kind)
    if (q.q) p.set('q', q.q)
    p.set('page', String(q.page ?? 1))
    p.set('size', String(q.size ?? 50))
    return get<KbDeliverables>(`/deliverables?${p.toString()}`)
  },
}

/**
 * 成品件原文件的直读地址（PDF 内嵌 / 图放大 / md 取文本都用它）。
 * 🔴 它**不是** `get<T>()` 那条 JSON 通路——服务端直吐字节（全站唯一非 JSON 出口）。
 *   路径越出 `成品库/` 或扩展名不在白名单，服务端一律 403（前端不许自己"修"路径去绕）。
 */
export const kbFileUrl = (path: string) => `${BASE}/file?path=${encodeURIComponent(path)}`

/** 成品「类型」筛子：库里只有 pdf/png/jpg/jpeg/md 五种扩展名，图三种合并成一档 */
export const DELIVERABLE_KINDS = [
  { value: '', label: '全部', exts: [] as string[] },
  { value: 'pdf', label: 'PDF', exts: ['pdf'] },
  { value: 'img', label: '图', exts: ['png', 'jpg', 'jpeg'] },
  { value: 'md', label: '文档', exts: ['md'] },
] as const

/** 册细类的中文说明（页签下的一句话，值域正本 = artifact.细类 的 CHECK） */
export const ARTIFACT_SUBKINDS = [
  { value: '组卷册', label: '组卷册', desc: 'v2 产线组出来的卷——库里挂着 paper，能逐题看' },
  { value: '发布包', label: '发布包', desc: '打包上架的销售件——note 里带宣发字段（标题候选 / 商品描述 / 网盘链接）' },
  { value: '历史册', label: '历史册', desc: '从 punch 资料库吃进来的老货——只有账没有卷' },
] as const

/** 状态/来源的中文选项（值域正本=库里的 CHECK 与 dict_item；这里只做筛选器下拉） */
export const QUESTION_STATUS = ['草稿', '已审', '上架', '退役']
export const SOURCE_KINDS = [
  { value: 'scan', label: '扫描/拍照录入' },
  { value: 'manual', label: '人工录入' },
  { value: 'model', label: '模型生成' },
  { value: 'pipeline', label: '管线生成' },
]
