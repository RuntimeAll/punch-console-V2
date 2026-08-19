/**
 * kb 薄读 API —— 展示台接真库的唯一数据口（批次⑤前置件）
 * ═══════════════════════════════════════════════════════════════════════
 * 🔴 三条铁律（违反其一这个文件就该被删掉重写）：
 *   ① **只读**：连接一律 SQLITE_OPEN_READONLY（node:sqlite 的 readOnly:true），
 *      写语句在驱动层就被拒（实测报 "attempt to write a readonly database"）。
 *      页面一个写按钮都不许有，写动作全走 工具箱/ 脚本与 skill。
 *   ② **薄**：只做「取数 + 拼形状 + 贴中文标签」，不做业务判断、不落任何缓存表。
 *      口径正本在 认知/数据结构.md，本文件是它的只读投影。
 *   ③ **全参数化**：一切外部输入进 SQL 一律走 ? 占位；唯一的字符串拼接是
 *      /api/kb/stats 的表名——它来自 sqlite_master（库自己的名字，不是用户输入），
 *      且做了双引号转义。
 *
 * 依赖：Node 内置 node:sqlite（本机 node v24.11.1 起可用）。
 *   🔴 不许换 better-sqlite3：这台机器有原生模块编译失败史（punch-console 的 pnpm dev 至今被它拦）。
 *
 * 起法：
 *   node console/server/kb-read-api.mjs                 # 库=<v2根>/知识库/kb.db
 *   $env:KB_DB='D:\...\kb.db'; node console/server/kb-read-api.mjs
 * 前端走 vite 代理 /api/kb → http://127.0.0.1:4310
 */
import { createServer } from 'node:http'
import { DatabaseSync } from 'node:sqlite'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// node:sqlite 仍带 ExperimentalWarning，起服务时刷屏没意义（能力本身已实测可用）
process.removeAllListeners('warning')
process.on('warning', (w) => {
  if (w.name === 'ExperimentalWarning' && /SQLite/i.test(String(w.message))) return
  console.warn(w)
})

const HERE = dirname(fileURLToPath(import.meta.url)) // …/console/server
const V2_ROOT = resolve(HERE, '..', '..') // …/ai-bkb-v2（worktree 里=本位沙盘）
const DB_PATH = process.env.KB_DB ? resolve(process.env.KB_DB) : resolve(V2_ROOT, '知识库', 'kb.db')
const PORT = Number(process.env.KB_API_PORT || 4310)
const HOST = '127.0.0.1'

/** 🔴 只读句柄：每请求开一把、用完就关。SQLite 打开极廉价，换来的是
 *  ①永远看到 agent 刚写进去的新数据 ②绝不长期持锁挡住写方。 */
function openRo() {
  return new DatabaseSync(DB_PATH, { readOnly: true })
}

// ── 小工具 ──────────────────────────────────────────────────────────────
const all = (db, sql, ...p) => db.prepare(sql).all(...p)
const one = (db, sql, ...p) => db.prepare(sql).get(...p)
/** IN (?,?,?) 占位串 */
const marks = (n) => Array.from({ length: n }, () => '?').join(',')

/** 块流 JSON 安全解析：坏数据**如实报**，绝不静默变空块流（老区"静默丢"血案） */
function parseDoc(raw) {
  if (raw === null || raw === undefined || raw === '') return null
  try {
    const d = JSON.parse(raw)
    if (!d || typeof d !== 'object' || !Array.isArray(d.rows)) {
      return { v: 0, rows: [], parse_error: '不是 {v,rows} 形状' }
    }
    return d
  } catch (e) {
    return { v: 0, rows: [], parse_error: String(e.message) }
  }
}

/** 从块流里抽纯文本（text.md / option 内层 / table 单元格），按出现序拼 */
function plainText(doc) {
  if (!doc || !Array.isArray(doc.rows)) return ''
  const out = []
  const eatCell = (c) => {
    if (!c || typeof c !== 'object') return
    if (c.type === 'text') out.push(String(c.md ?? ''))
    else if (c.type === 'option') {
      out.push(`${c.label}.`)
      ;(c.blocks || []).forEach(eatCell)
    } else if (c.type === 'figure') out.push('[图]')
    else if (c.type === 'table') {
      // 表格块两种载荷都吃：md=GFM 整表；rows=[行][格][块列表]（gates.py 认的结构化形状）。
      // 另兼容原型期 {cells:[{md}]}——不认它就抽不出摘要，列表页会莫名其妙空一格。
      if (typeof c.md === 'string') out.push(c.md.replace(/\|/g, ' '))
      for (const r of c.rows || []) {
        if (Array.isArray(r)) r.forEach((tc) => (Array.isArray(tc) ? tc.forEach(eatCell) : eatCell(tc)))
        else (r?.cells || []).forEach((tc) => out.push(String(tc?.md ?? '')))
      }
    }
  }
  doc.rows.forEach((r) => (r.cells || []).forEach(eatCell))
  return out.join(' ').replace(/\s+/g, ' ').trim()
}

/** 题面摘要：整份块流的首个 text 块，超 n 字截断（列表页用） */
function stemBrief(raw, n = 120) {
  const doc = parseDoc(raw)
  if (!doc) return ''
  if (doc.parse_error) return `🔴 块流损坏：${doc.parse_error}`
  const t = plainText(doc)
  return t.length > n ? `${t.slice(0, n)}…` : t
}

/** 字典表 → { code: label }（题型/难度/来源的中文标签一律从库里取，不在代码里写死） */
function dictMap(db) {
  const m = {}
  for (const r of all(db, 'SELECT domain, code, label FROM dict_item')) {
    m[r.code] = r.label
    m[`${r.domain}:${r.code}`] = r.label
  }
  return m
}

// ── kp 树 ───────────────────────────────────────────────────────────────
/** 读全表 kp + 每 kp 直挂题数 / 别名数，拼成嵌套树 */
function buildTree(db) {
  const kps = all(db, 'SELECT id, name, parent_id, level, ord, status, note FROM kp')
  const qcnt = {}
  for (const r of all(db, 'SELECT kp_id, COUNT(DISTINCT question_id) AS c FROM question_kp GROUP BY kp_id')) {
    qcnt[r.kp_id] = r.c
  }
  const acnt = {}
  for (const r of all(db, 'SELECT kp_id, COUNT(*) AS c FROM kp_alias GROUP BY kp_id')) acnt[r.kp_id] = r.c

  const nodes = new Map()
  for (const k of kps) {
    nodes.set(k.id, {
      id: k.id,
      name: k.name,
      level: k.level,
      ord: k.ord,
      status: k.status,
      note: k.note,
      alias_count: acnt[k.id] || 0,
      q_count: qcnt[k.id] || 0, // 直挂本节点的题数（叶子闸下应只有叶子有值）
      q_total: 0, // 子树合计，后面回填
      children: [],
    })
  }
  const roots = []
  for (const k of kps) {
    const n = nodes.get(k.id)
    const p = k.parent_id ? nodes.get(k.parent_id) : null
    if (p) p.children.push(n)
    else roots.push(n)
  }
  const byOrd = (a, b) => (a.ord ?? 0) - (b.ord ?? 0) || String(a.id).localeCompare(String(b.id))
  const sum = (n) => {
    n.children.sort(byOrd)
    n.q_total = n.q_count + n.children.reduce((s, c) => s + sum(c), 0)
    return n.q_total
  }
  roots.sort(byOrd)
  roots.forEach(sum)

  const leaves = kps.length - new Set(kps.filter((k) => k.parent_id).map((k) => k.parent_id)).size
  return {
    roots,
    kp_total: kps.length,
    leaf_total: leaves,
    unbuilt_total: kps.filter((k) => k.status === '未铺').length,
  }
}

/**
 * 考点过滤词 → kp。🔴 含别名 resolve（老区 resolve 命中率 2%~29% 的根因就是缺这层翻译）。
 * 依次试：id 精确 → name 精确 → kp_alias.alias 精确 → name 模糊。
 * 返回 null = 这个词在库里根本查不到（页面要如实标，不许当"全部"糊过去）。
 */
function resolveKp(db, word) {
  const w = String(word).trim()
  if (!w) return null
  let hit = one(db, 'SELECT id, name, level, status FROM kp WHERE id = ?', w)
  if (hit) return { ...hit, matched_by: 'id' }
  hit = one(db, 'SELECT id, name, level, status FROM kp WHERE name = ?', w)
  if (hit) return { ...hit, matched_by: '考点名' }
  const a = one(db, 'SELECT kp_id, alias_kind FROM kp_alias WHERE alias = ? LIMIT 1', w)
  if (a) {
    hit = one(db, 'SELECT id, name, level, status FROM kp WHERE id = ?', a.kp_id)
    if (hit) return { ...hit, matched_by: `别名(${a.alias_kind || '未标来源'})` }
  }
  hit = one(db, 'SELECT id, name, level, status FROM kp WHERE name LIKE ? ORDER BY LENGTH(name) LIMIT 1', `%${w}%`)
  if (hit) return { ...hit, matched_by: '考点名模糊' }
  return null
}

/** 某 kp 的自身 + 全部后代 id（点单元节点要能看到整枝的题；不靠 id 前缀猜，按 parent_id 走） */
function subtreeIds(db, kpId) {
  const kids = new Map()
  for (const r of all(db, 'SELECT id, parent_id FROM kp')) {
    if (!r.parent_id) continue
    if (!kids.has(r.parent_id)) kids.set(r.parent_id, [])
    kids.get(r.parent_id).push(r.id)
  }
  const out = []
  const stack = [kpId]
  while (stack.length) {
    const cur = stack.pop()
    out.push(cur)
    for (const c of kids.get(cur) || []) stack.push(c)
  }
  return out
}

/**
 * 字典标签 → 码（域内精确；已是码值则原样回）。
 * 🔴 翻不出返回 null——调用方必须如实标进 unresolved 并把结果压成 0 条，
 *    绝不当「不过滤」糊过去（那是把「查不到」显示成「全都有」）。
 */
function dictCode(db, domain, word) {
  const w = String(word).trim()
  if (!w) return null
  let r = one(db, 'SELECT code FROM dict_item WHERE domain = ? AND label = ? AND status = ?', domain, w, '在用')
  if (r) return r.code
  r = one(db, 'SELECT code FROM dict_item WHERE domain = ? AND code = ? AND status = ?', domain, w, '在用')
  return r ? r.code : null
}

/** 标签 `域:名` 或 `名` → tag id 表（跨域同名=该条件内 OR）；零命中返回 [] */
function resolveTag(db, spec) {
  const seg = String(spec).split(/[:：]/) // 全角冒号也认（中文输入常态）
  const name = (seg.length > 1 ? seg.slice(1).join(':') : seg[0]).trim()
  const domain = seg.length > 1 ? seg[0].trim() : null
  if (!name) return []
  const rows = domain
    ? all(db, 'SELECT id FROM tag WHERE domain = ? AND name = ?', domain, name)
    : all(db, 'SELECT id FROM tag WHERE name = ?', name)
  return rows.map((r) => r.id)
}

/** kp 全路径（版本 › 年级学期 › 单元 › 小节 › 考点） */
function kpPath(db, kpId) {
  const seg = []
  let cur = kpId
  const guard = new Set()
  while (cur && !guard.has(cur)) {
    guard.add(cur)
    const r = one(db, 'SELECT id, name, level, parent_id FROM kp WHERE id = ?', cur)
    if (!r) break
    seg.unshift({ id: r.id, name: r.name, level: r.level })
    cur = r.parent_id
  }
  return seg
}

// ── 端点实现 ────────────────────────────────────────────────────────────

function epStats(db) {
  const tables = all(
    db,
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name",
  )
  const rows = tables.map((t) => ({
    table: t.name,
    // 表名来自 sqlite_master（库自己的名字，非用户输入）；双引号转义兜底
    count: one(db, `SELECT COUNT(*) AS c FROM "${t.name.replace(/"/g, '""')}"`).c,
  }))
  return {
    db_path: DB_PATH,
    readonly: true,
    table_total: rows.length,
    nonempty_total: rows.filter((r) => r.count > 0).length,
    rows,
  }
}

function epQuestions(db, q) {
  const page = Math.max(1, Number(q.get('page') || 1))
  const size = Math.min(200, Math.max(1, Number(q.get('size') || 20)))
  const where = []
  const args = []
  let kpHit = null
  let kpMiss = null

  const kpWord = q.get('kp')
  if (kpWord) {
    kpHit = resolveKp(db, kpWord)
    if (kpHit) {
      const ids = subtreeIds(db, kpHit.id)
      where.push(`q.id IN (SELECT question_id FROM question_kp WHERE kp_id IN (${marks(ids.length)}))`)
      args.push(...ids)
    } else {
      kpMiss = kpWord
      where.push('1 = 0') // 🔴 resolve 不中就是 0 条，不许静默当"不过滤"
    }
  }
  const status = q.get('status')
  if (status) {
    where.push('q.status = ?')
    args.push(status)
  }
  const sk = q.get('source_kind')
  if (sk) {
    where.push('q.source_kind = ?')
    args.push(sk)
  }

  // ── D-20 找题维度扩参（🔴 口径正本=工具箱/检索/query_core.py，此处是它的 js 孪生：
  //    同一维度的 SQL 形状照抄，改一边必须改另一边，否则页面查到的和组卷取到的会悄悄不一致。
  //    不起 python 子进程——读 API 必须是「进程内一次 SQL」，起子进程会把只读薄口变成慢胖口。）──
  const unresolved = {}
  for (const [key, domain, col] of [
    ['qtype', 'qtype', 'q.qtype_code'],
    ['difficulty', 'difficulty', 'q.diff_code'],
  ]) {
    const vals = q.getAll(key).filter(Boolean) // 同维度多值 = OR
    if (!vals.length) continue
    const codes = vals.map((v) => dictCode(db, domain, v))
    const miss = vals.filter((_v, i) => codes[i] === null)
    if (miss.length) {
      unresolved[key] = miss
      where.push('1 = 0') // 🔴 翻不出就是 0 条，不许静默当"不过滤"
      continue
    }
    where.push(`${col} IN (${marks(codes.length)})`)
    args.push(...codes)
  }
  for (const t of q.getAll('tag').filter(Boolean)) {
    // 多个标签 = AND（标签是收窄用的，与 query_core 同口径）
    const ids = resolveTag(db, t)
    if (!ids.length) {
      ;(unresolved.tag ||= []).push(t)
      where.push('1 = 0')
      continue
    }
    where.push(`q.id IN (SELECT question_id FROM question_tag WHERE tag_id IN (${marks(ids.length)}))`)
    args.push(...ids)
  }
  const unusedRaw = q.get('unused')
  let unused = null
  if (unusedRaw !== null && unusedRaw !== '') {
    unused = !/^(0|false|no|否)$/i.test(unusedRaw) // unused=1/true/空值都算「要未用过的」
    where.push(
      `${unused ? 'NOT EXISTS' : 'EXISTS'} (SELECT 1 FROM paper_item pi WHERE pi.question_id = q.id)`,
    )
  }

  const sql = where.length ? ` WHERE ${where.join(' AND ')}` : ''
  const total = one(db, `SELECT COUNT(*) AS c FROM question q${sql}`, ...args).c
  const rows = all(
    db,
    `SELECT q.id, q.blocks_json, q.qtype_code, q.diff_code, q.source_kind, q.source_raw,
            q.mother_qid, q.variant_op, q.status, q.created_at
     FROM question q${sql}
     ORDER BY q.created_at DESC, q.id
     LIMIT ? OFFSET ?`,
    ...args,
    size,
    (page - 1) * size,
  )

  const dict = dictMap(db)
  const ids = rows.map((r) => r.id)
  const kpByQ = {}
  const varByQ = {}
  if (ids.length) {
    for (const r of all(
      db,
      `SELECT qk.question_id, qk.kp_id, qk.is_primary, kp.name
       FROM question_kp qk JOIN kp ON kp.id = qk.kp_id
       WHERE qk.question_id IN (${marks(ids.length)})
       ORDER BY qk.is_primary DESC, kp.id`,
      ...ids,
    )) {
      ;(kpByQ[r.question_id] ||= []).push({ id: r.kp_id, name: r.name, is_primary: !!r.is_primary })
    }
    for (const r of all(
      db,
      `SELECT mother_qid, COUNT(*) AS c FROM question
       WHERE mother_qid IN (${marks(ids.length)}) GROUP BY mother_qid`,
      ...ids,
    )) {
      varByQ[r.mother_qid] = r.c
    }
  }

  return {
    total,
    page,
    size,
    kp_filter: kpHit ? { ...kpHit, word: kpWord } : null,
    kp_unresolved: kpMiss, // 🔴 词没 resolve 到，页面照实说
    // 🔴 同上：题型/难度/标签翻不出的词原样回给页面，页面必须显示「这个词库里没有」而不是「没有结果」
    unresolved: Object.keys(unresolved).length ? unresolved : null,
    filters: {
      kp: kpWord || null,
      status: status || null,
      source_kind: sk || null,
      qtype: q.getAll('qtype'),
      difficulty: q.getAll('difficulty'),
      tag: q.getAll('tag'),
      unused,
    },
    rows: rows.map((r) => ({
      id: r.id,
      stem: stemBrief(r.blocks_json),
      qtype_code: r.qtype_code,
      qtype_label: r.qtype_code ? dict[r.qtype_code] || r.qtype_code : null,
      diff_code: r.diff_code,
      diff_label: r.diff_code ? dict[r.diff_code] || r.diff_code : null,
      source_kind: r.source_kind,
      source_label: r.source_kind ? dict[r.source_kind] || r.source_kind : null,
      source_raw: r.source_raw,
      kps: kpByQ[r.id] || [],
      status: r.status,
      // 血缘有无 = 有母题 或 有变体（SSOT 就是 question.mother_qid 这一列，不查平行 trace 表）
      has_mother: !!r.mother_qid,
      variant_count: varByQ[r.id] || 0,
      has_lineage: !!r.mother_qid || (varByQ[r.id] || 0) > 0,
      variant_op: r.variant_op,
      created_at: r.created_at,
    })),
  }
}

function epQuestionDetail(db, id) {
  const r = one(db, 'SELECT * FROM question WHERE id = ?', id)
  if (!r) return null
  const dict = dictMap(db)
  const kps = all(
    db,
    `SELECT qk.kp_id, qk.is_primary, qk.anchor_json, kp.name
     FROM question_kp qk JOIN kp ON kp.id = qk.kp_id
     WHERE qk.question_id = ? ORDER BY qk.is_primary DESC, kp.id`,
    id,
  ).map((k) => ({
    id: k.kp_id,
    name: k.name,
    is_primary: !!k.is_primary,
    anchor: k.anchor_json ? parseJson(k.anchor_json) : null,
    path: kpPath(db, k.kp_id),
  }))

  const mother = r.mother_qid
    ? (() => {
        const m = one(db, 'SELECT id, blocks_json, status, variant_op FROM question WHERE id = ?', r.mother_qid)
        return m ? { id: m.id, stem: stemBrief(m.blocks_json), status: m.status } : { id: r.mother_qid, missing: true }
      })()
    : null
  const variants = all(
    db,
    'SELECT id, blocks_json, variant_op, status FROM question WHERE mother_qid = ? ORDER BY created_at, id',
    id,
  ).map((v) => ({ id: v.id, stem: stemBrief(v.blocks_json, 60), variant_op: v.variant_op, status: v.status }))

  const papers = all(
    db,
    `SELECT p.id AS paper_id, p.title, p.kind, p.ord AS paper_ord, p.status AS paper_status,
            pi.ord AS item_ord, pi.section, pi.score,
            a.id AS artifact_id, a.name AS artifact_name
     FROM paper_item pi
     JOIN paper p ON p.id = pi.paper_id
     LEFT JOIN artifact a ON a.id = p.artifact_id
     WHERE pi.question_id = ?
     ORDER BY p.ord, pi.ord`,
    id,
  )

  const tags = all(
    db,
    `SELECT t.id, t.domain, t.name FROM question_tag qt JOIN tag t ON t.id = qt.tag_id
     WHERE qt.question_id = ? ORDER BY t.domain, t.name`,
    id,
  )

  return {
    id: r.id,
    blocks: parseDoc(r.blocks_json),
    answer: parseDoc(r.answer_blocks_json),
    analysis: parseDoc(r.analysis_blocks_json),
    qtype_code: r.qtype_code,
    qtype_label: r.qtype_code ? dict[r.qtype_code] || r.qtype_code : null,
    diff_code: r.diff_code,
    diff_label: r.diff_code ? dict[r.diff_code] || r.diff_code : null,
    pattern_id: r.pattern_id,
    source_kind: r.source_kind,
    source_label: r.source_kind ? dict[r.source_kind] || r.source_kind : null,
    source_raw: r.source_raw,
    prov: r.prov_json ? parseJson(r.prov_json) : null,
    variant_op: r.variant_op,
    match_key: r.match_key,
    status: r.status,
    created_at: r.created_at,
    updated_at: r.updated_at,
    kps,
    tags,
    lineage: { mother, variants },
    papers,
  }
}

function parseJson(raw) {
  try {
    return JSON.parse(raw)
  } catch (e) {
    return { parse_error: String(e.message), raw }
  }
}

function epArtifacts(db) {
  const rows = all(
    db,
    `SELECT a.id, a.name, a.kind, a.status, a.source_line, a.template_id,
            a.kp_ids_json, a.delivered_at, a.link, a.note, a.created_at,
            (SELECT COUNT(*) FROM paper p WHERE p.artifact_id = a.id) AS paper_count,
            (SELECT COUNT(*) FROM paper_item pi JOIN paper p2 ON p2.id = pi.paper_id
              WHERE p2.artifact_id = a.id) AS item_count
     FROM artifact a
     ORDER BY a.created_at DESC, a.id`,
  )
  return {
    total: rows.length,
    rows: rows.map((r) => ({
      ...r,
      kp_ids: r.kp_ids_json ? parseJson(r.kp_ids_json) : [],
      files: null,
    })),
  }
}

function epArtifactDetail(db, id) {
  const a = one(db, 'SELECT * FROM artifact WHERE id = ?', id)
  if (!a) return null
  const papers = all(
    db,
    `SELECT id, kind, title, ord, layout_json, status, created_at
     FROM paper WHERE artifact_id = ? ORDER BY ord, id`,
    id,
  )
  const out = papers.map((p) => ({
    id: p.id,
    kind: p.kind,
    title: p.title,
    ord: p.ord,
    status: p.status,
    layout: p.layout_json ? parseJson(p.layout_json) : null,
    created_at: p.created_at,
    items: all(
      db,
      `SELECT pi.ord, pi.section, pi.score, pi.question_id, q.blocks_json, q.status AS q_status
       FROM paper_item pi LEFT JOIN question q ON q.id = pi.question_id
       WHERE pi.paper_id = ? ORDER BY pi.ord`,
      p.id,
    ).map((it) => ({
      ord: it.ord,
      section: it.section,
      score: it.score,
      question_id: it.question_id,
      q_status: it.q_status,
      // 题面截断：册详情只做「看得出是哪道题」，全文进 /api/kb/papers/:id
      stem: it.blocks_json ? stemBrief(it.blocks_json, 80) : '🔴 题已不在库（断链）',
    })),
  }))
  return {
    ...a,
    kp_ids: a.kp_ids_json ? parseJson(a.kp_ids_json) : [],
    files: a.files_json ? parseJson(a.files_json) : null,
    papers: out,
  }
}

function epPaperDetail(db, id) {
  const p = one(db, 'SELECT * FROM paper WHERE id = ?', id)
  if (!p) return null
  const art = p.artifact_id ? one(db, 'SELECT id, name, kind, status FROM artifact WHERE id = ?', p.artifact_id) : null
  const dict = dictMap(db)
  const items = all(
    db,
    `SELECT pi.ord, pi.section, pi.score, pi.note, pi.question_id,
            q.blocks_json, q.answer_blocks_json, q.analysis_blocks_json,
            q.qtype_code, q.diff_code, q.status AS q_status
     FROM paper_item pi LEFT JOIN question q ON q.id = pi.question_id
     WHERE pi.paper_id = ? ORDER BY pi.ord`,
    id,
  ).map((it) => ({
    ord: it.ord,
    section: it.section,
    score: it.score,
    note: it.note,
    question_id: it.question_id,
    q_status: it.q_status,
    missing: !it.blocks_json, // 断链如实标
    qtype_label: it.qtype_code ? dict[it.qtype_code] || it.qtype_code : null,
    diff_label: it.diff_code ? dict[it.diff_code] || it.diff_code : null,
    blocks: parseDoc(it.blocks_json),
    answer: parseDoc(it.answer_blocks_json),
    analysis: parseDoc(it.analysis_blocks_json),
  }))
  return {
    id: p.id,
    title: p.title,
    kind: p.kind,
    ord: p.ord,
    status: p.status,
    created_at: p.created_at,
    layout: p.layout_json ? parseJson(p.layout_json) : null,
    artifact: art,
    items,
  }
}

// ── 路由 ────────────────────────────────────────────────────────────────
const ROUTES = [
  { re: /^\/api\/kb\/stats$/, run: (db) => epStats(db) },
  { re: /^\/api\/kb\/kg\/tree$/, run: (db) => buildTree(db) },
  { re: /^\/api\/kb\/questions$/, run: (db, _m, q) => epQuestions(db, q) },
  { re: /^\/api\/kb\/questions\/(.+)$/, run: (db, m) => epQuestionDetail(db, decodeURIComponent(m[1])) },
  { re: /^\/api\/kb\/artifacts$/, run: (db) => epArtifacts(db) },
  { re: /^\/api\/kb\/artifacts\/(.+)$/, run: (db, m) => epArtifactDetail(db, decodeURIComponent(m[1])) },
  { re: /^\/api\/kb\/papers\/(.+)$/, run: (db, m) => epPaperDetail(db, decodeURIComponent(m[1])) },
]

function send(res, code, obj) {
  const body = Buffer.from(JSON.stringify(obj, null, 2), 'utf8')
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': body.length,
    'Cache-Control': 'no-store',
  })
  res.end(body)
}

const server = createServer((req, res) => {
  let url
  try {
    url = new URL(req.url, `http://${HOST}:${PORT}`)
  } catch {
    return send(res, 400, { error: '请求路径非法' })
  }
  if (req.method !== 'GET') {
    // 🔴 只读 API：非 GET 一律拒（写动作归 agent/工具，页面无写口）
    return send(res, 405, { error: '本 API 只读，只接受 GET' })
  }
  const hit = ROUTES.map((r) => ({ r, m: r.re.exec(url.pathname) })).find((x) => x.m)
  if (!hit) {
    return send(res, 404, {
      error: '无此端点',
      endpoints: [
        'GET /api/kb/stats',
        'GET /api/kb/kg/tree',
        'GET /api/kb/questions?kp=&status=&source_kind=&qtype=&difficulty=&tag=&unused=&page=&size=' +
          '（qtype/difficulty/tag 可重复给：同名多值 qtype/difficulty=OR、tag=AND；' +
          'tag 写「域:名」或「名」；unused=1 未进过卷 / unused=0 进过卷）',
        'GET /api/kb/questions/:id',
        'GET /api/kb/artifacts',
        'GET /api/kb/artifacts/:id',
        'GET /api/kb/papers/:id',
      ],
    })
  }
  let db
  try {
    db = openRo()
    const data = hit.r.run(db, hit.m, url.searchParams)
    if (data === null) return send(res, 404, { error: '查无此条', path: url.pathname })
    return send(res, 200, data)
  } catch (e) {
    console.error(`[kb-read-api] ${url.pathname} 出错：${e.message}`)
    return send(res, 500, { error: String(e.message) })
  } finally {
    try {
      db?.close()
    } catch {
      /* 关不上就算了，进程退出会回收 */
    }
  }
})

if (!existsSync(DB_PATH)) {
  console.error(`🔴 库不存在：${DB_PATH}\n   （worktree 里先跑 python 工具箱/库/init_db.py --only kb 建沙盘库）`)
  process.exit(2)
}
server.listen(PORT, HOST, () => {
  console.log(`kb 读 API :${PORT} 库=${DB_PATH} 只读`)
})
