/**
 * kb 薄读 API —— 展示台接真库的唯一数据口（批次⑤前置件）
 * ═══════════════════════════════════════════════════════════════════════
 * 🔴 三条铁律（违反其一这个文件就该被删掉重写）：
 *   ① **只读**：连接一律 SQLITE_OPEN_READONLY（node:sqlite 的 readOnly:true），
 *      写语句在驱动层就被拒（实测报 "attempt to write a readonly database"）。
 *      页面一个写按钮都不许有，写动作全走 工具箱/ 脚本与 skill。
 *      🔴 **唯一豁免**（PRD-003，2026-08-19 用户拍板）：`POST /api/kb/sale-state`——
 *      全站唯一写端点，只许写 `artifact.sale_state` 一列（人工售卖态）。
 *      豁免由 `WRITE_ROUTES` 白名单持有，长度硬断言=1；为什么必须留这一个口，
 *      见 epSetSaleState 头上原样搬来的 punch-console 血案注释。
 *   ② **薄**：只做「取数 + 拼形状 + 贴中文标签」，不做业务判断、不落任何缓存表。
 *      口径正本在 认知/数据结构.md，本文件是它的只读投影。
 *   ③ **全参数化**：一切外部输入进 SQL 一律走 ? 占位；唯一的字符串拼接是
 *      /api/kb/stats 的表名——它来自 sqlite_master（库自己的名字，不是用户输入），
 *      且做了双引号转义。
 *      🔴 **占位符挡得住引号，挡不住通配符**：凡把用户输入拼进 LIKE 模式串的地方
 *      （epMaterials 的 q= 关键词、resolveKp 的考点名模糊），一律 `likeEsc()` 转义
 *      `% _ \` 再配 `ESCAPE '\'`——否则 q=`%` 等于"全表匹配"、q=`_` 等于"任意一字符"，
 *      页面就会把「查不到」显示成「全都有」（与本文件到处在防的那件事同源）。
 *
 * 端点账（🔴 改口子必须同步改这三处：ROUTES/WRITE_ROUTES、下面的 EP_READ/EP_WRITE 常量、
 *   404 的 endpoints 清单——数量对不上服务直接起不来，见文件末尾自检闸）：
 *   **10 条 = 9 读 + 1 写**。其中 PRD-003 在原有 7 读的底子上 **+2 读**
 *   （GET /api/kb/materials、GET /api/kb/artifact-members）**+1 写**（POST /api/kb/sale-state）。
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

/** 🔴 全站唯一的可写句柄。只有 epSetSaleState 调它，别的地方多调一次都算破了「页面只读」。 */
function openRw() {
  return new DatabaseSync(DB_PATH)
}

// ── 小工具 ──────────────────────────────────────────────────────────────
const all = (db, sql, ...p) => db.prepare(sql).all(...p)
const one = (db, sql, ...p) => db.prepare(sql).get(...p)
/** IN (?,?,?) 占位串 */
const marks = (n) => Array.from({ length: n }, () => '?').join(',')

/**
 * 🔴 LIKE 模式转义：把用户输入里的 `%` `_` `\` 变成字面量。
 * 必须与 SQL 里的 `LIKE ? ESCAPE '\'`（= 常量 LIKE_ESC）成对出现，少一半就等于没转。
 * 反例（转义前的真实行为）：q=`%` 命中全表、q=`_` 命中任意单字符——把"查不到"演成"全都有"。
 */
const likeEsc = (s) => String(s).replace(/[\\%_]/g, '\\$&')
/** 拼进 SQL 的 ESCAPE 子句（JS 里 '\\' 落到 SQL 就是一个反斜杠） */
const LIKE_ESC = "ESCAPE '\\'"

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
  // 🔴 模糊这一档才是 LIKE：用户输入里的 % _ 必须转义（否则 kp=`_` 会"模糊"到随便哪个考点上）
  hit = one(
    db,
    `SELECT id, name, level, status FROM kp WHERE name LIKE ? ${LIKE_ESC} ORDER BY LENGTH(name) LIMIT 1`,
    `%${likeEsc(w)}%`,
  )
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
    // 全文件仅此一处 LIKE 不转义：模式串是写死的字面量 'sqlite_%'（要的就是它的通配语义），
    // 没有任何用户输入拼进来。其余 LIKE 一律 likeEsc + LIKE_ESC。
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

/**
 * 网盘提取码：从 note（JSON 或纯文本）与 link（`?pwd=`）里**解析**，不猜。
 * 🔴 三条口径：
 *   ① 三个来源都取，取到几个就列几个（candidates），**互相不一致时 conflict=true 原样端出去**——
 *      页面必须显示"这册的提取码对不上"，而不是挑一个显示（老区"静默择一"就是这么把错码发给客户的）。
 *   ② 一个都没有 ⇒ code=null / source=null，页面显示"—"；绝不从链接里瞎猜四位。
 *   ③ 优先序 note.提取码 > link 的 pwd > note 纯文本正则——note 是宣发字段定稿位（数据结构 §2.6c）。
 */
function panCode(note, link) {
  const cands = []
  const push = (code, source) => {
    const c = String(code ?? '').trim()
    if (c) cands.push({ code: c, source })
  }
  // ① note 是 JSON 对象时取 提取码 / pan_code 键
  if (note) {
    const raw = String(note).trim()
    if (raw.startsWith('{')) {
      try {
        const o = JSON.parse(raw)
        if (o && typeof o === 'object') push(o['提取码'] ?? o.pan_code, 'note.提取码')
      } catch {
        /* note 不是合法 JSON：正常（纯文本备注），交给 ③ */
      }
    }
  }
  // ② 链接自带 pwd 参数（百度网盘 `?pwd=xxxx` 是现行主流形态）
  if (link) {
    const m = /[?&]pwd=([0-9A-Za-z]{3,8})/.exec(String(link))
    if (m) push(m[1], 'link.pwd')
  }
  // ③ note 纯文本里写着「提取码：xxxx」
  if (note) {
    const m = /提取码\s*[:：]?\s*([0-9A-Za-z]{3,8})/.exec(String(note))
    if (m) push(m[1], 'note 文本')
  }
  if (!cands.length) return { code: null, source: null, candidates: [], conflict: false }
  const distinct = [...new Set(cands.map((c) => c.code))]
  return {
    code: cands[0].code,
    source: cands[0].source,
    candidates: cands,
    conflict: distinct.length > 1, // 🔴 冲突如实报，页面必须显眼标出来
  }
}

/** note 解析成对象（不是 JSON 就原样当文本回，绝不吞） */
function noteObj(note) {
  if (note === null || note === undefined || note === '') return null
  const raw = String(note).trim()
  if (!raw.startsWith('{')) return { _text: raw }
  try {
    const o = JSON.parse(raw)
    return o && typeof o === 'object' ? o : { _text: raw }
  } catch {
    return { _text: raw, parse_error: 'note 以 { 开头但不是合法 JSON' }
  }
}

function epArtifacts(db) {
  const rows = all(
    db,
    `SELECT a.id, a.name, a.kind, a.status, a.sale_state, a.source_line, a.template_id,
            a.kp_ids_json, a.delivered_at, a.link, a.note, a.created_at,
            (SELECT COUNT(*) FROM paper p WHERE p.artifact_id = a.id) AS paper_count,
            (SELECT COUNT(*) FROM paper_item pi JOIN paper p2 ON p2.id = pi.paper_id
              WHERE p2.artifact_id = a.id) AS item_count,
            (SELECT COUNT(*) FROM material m WHERE m.artifact_id = a.id) AS material_count,
            (SELECT COUNT(*) FROM artifact_member am WHERE am.parent_id = a.id) AS member_count
     FROM artifact a
     ORDER BY a.created_at DESC, a.id`,
  )
  return {
    total: rows.length,
    rows: rows.map((r) => ({
      ...r,
      kp_ids: r.kp_ids_json ? parseJson(r.kp_ids_json) : [],
      pan_code: panCode(r.note, r.link),
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
  // ── PRD-003 补吐：售卖态 / 网盘链接+提取码 / 合刊关系 / 物料概览 ──
  const members = all(
    db,
    `SELECT am.member_id, am.ord, a2.name, a2.kind, a2.status, a2.sale_state
     FROM artifact_member am LEFT JOIN artifact a2 ON a2.id = am.member_id
     WHERE am.parent_id = ? ORDER BY am.ord, am.member_id`,
    id,
  ).map((m) => ({
    id: m.member_id,
    ord: m.ord,
    name: m.name ?? null,
    kind: m.kind ?? null,
    status: m.status ?? null,
    sale_state: m.sale_state ?? null,
    missing: m.name === null || m.name === undefined, // 🔴 断链如实标，不当成"没有成员"
  }))
  const memberOf = all(
    db,
    `SELECT am.parent_id, am.ord, a2.name FROM artifact_member am
     LEFT JOIN artifact a2 ON a2.id = am.parent_id
     WHERE am.member_id = ? ORDER BY am.parent_id`,
    id,
  ).map((p) => ({ id: p.parent_id, ord: p.ord, name: p.name ?? null, missing: p.name == null }))

  const mstat = all(
    db,
    `SELECT account, COUNT(*) AS c, SUM(is_active) AS act, SUM(burned) AS burned
     FROM material WHERE artifact_id = ? GROUP BY account ORDER BY account`,
    id,
  )

  return {
    ...a,
    kp_ids: a.kp_ids_json ? parseJson(a.kp_ids_json) : [],
    files: a.files_json ? parseJson(a.files_json) : null,
    // sale_state 由 `...a` 原样带出（人工列，本 API 只读它；改它走 POST /api/kb/sale-state）
    note_obj: noteObj(a.note),
    pan_code: panCode(a.note, a.link),
    members, // 本册作为合刊时的成员（doc_member 吃进来的）
    member_of: memberOf, // 本册被哪些合刊收编
    material_stat: mstat.map((m) => ({
      account: m.account,
      total: m.c,
      active: m.act ?? 0,
      burned: m.burned ?? 0,
    })),
    papers: out,
  }
}

// ── PRD-003 发布运营域端点 ────────────────────────────────────────────────

/**
 * 物料清单（小红书文案等）。artifact_id 不给=全库；给了但库里没这册 ⇒
 * artifact_unresolved 原样回 + 0 条，🔴 不静默当"全部"。
 */
function epMaterials(db, q) {
  const where = []
  const args = []
  let art = null
  let artMiss = null

  const aid = q.get('artifact_id')
  if (aid) {
    art = one(db, 'SELECT id, name, kind, status, sale_state, link, note FROM artifact WHERE id = ?', aid)
    if (art) {
      where.push('m.artifact_id = ?')
      args.push(aid)
    } else {
      artMiss = aid
      where.push('1 = 0')
    }
  }
  const acc = q.getAll('account').filter(Boolean) // A / B，多值=OR
  const badAcc = acc.filter((v) => v !== 'A' && v !== 'B')
  if (acc.length) {
    if (badAcc.length) where.push('1 = 0') // 🔴 值域外的账号名不当"不过滤"
    else {
      where.push(`m.account IN (${marks(acc.length)})`)
      args.push(...acc)
    }
  }
  const flag = (name, col) => {
    const raw = q.get(name)
    if (raw === null || raw === '') return null
    const on = !/^(0|false|no|否)$/i.test(raw)
    where.push(`${col} = ?`)
    args.push(on ? 1 : 0)
    return on
  }
  const active = flag('active', 'm.is_active')
  const burned = flag('burned', 'm.burned')

  // 顶部「在售态」筛选：过滤的是**册的人工列**，不是物料自己的属性
  const sale = q.getAll('sale_state').filter(Boolean)
  const NULL_WORDS = ['未标', 'null', '空']
  const badSale = sale.filter((s) => !SALE_STATES.has(s) && !NULL_WORDS.includes(s))
  if (sale.length) {
    if (badSale.length) {
      where.push('1 = 0') // 🔴 值域外的态名不当"不过滤"
    } else {
      const real = sale.filter((s) => !NULL_WORDS.includes(s))
      const seg = []
      if (real.length) {
        seg.push(`a.sale_state IN (${marks(real.length)})`)
        args.push(...real)
      }
      if (sale.length > real.length) seg.push('a.sale_state IS NULL')
      where.push(`(${seg.join(' OR ')})`)
    }
  }
  const kw = (q.get('q') || '').trim()
  if (kw) {
    // 🔴 关键词是纯用户输入：转义 % _ \ 并带 ESCAPE，q=`%` 只该匹配含百分号的文案，不是整库
    where.push(`(m.title LIKE ? ${LIKE_ESC} OR m.body LIKE ? ${LIKE_ESC} OR a.name LIKE ? ${LIKE_ESC})`)
    const pat = `%${likeEsc(kw)}%`
    args.push(pat, pat, pat)
  }

  const sql = where.length ? ` WHERE ${where.join(' AND ')}` : ''
  const rows = all(
    db,
    `SELECT m.id, m.artifact_id, m.account, m.is_active, m.title, m.body, m.topics_json,
            m.style_seed, m.burned, m.product_desc, m.pan_share_text, m.created_at,
            a.name AS artifact_name, a.kind AS artifact_kind, a.status AS artifact_status,
            a.sale_state AS artifact_sale_state, a.link AS artifact_link, a.note AS artifact_note,
            (SELECT COUNT(*) FROM publish_log pl WHERE pl.material_id = m.id) AS publish_count,
            (SELECT MAX(published_on) FROM publish_log pl2 WHERE pl2.material_id = m.id) AS last_published_on
     FROM material m LEFT JOIN artifact a ON a.id = m.artifact_id${sql}
     ORDER BY a.name, m.account, m.is_active DESC, m.created_at DESC, m.id`,
    ...args,
  )

  // ⚙️ 启用版唯一闸的**读侧告警**：同 册+账号 出现两条 is_active=1 就是坏账，页面必须看得见
  const dup = all(
    db,
    `SELECT m.artifact_id, a.name AS artifact_name, m.account, COUNT(*) AS active_count
     FROM material m LEFT JOIN artifact a ON a.id = m.artifact_id
     WHERE m.is_active = 1 GROUP BY m.artifact_id, m.account HAVING COUNT(*) > 1`,
  )

  const acct = { A: 0, B: 0 }
  for (const r of rows) if (r.account in acct) acct[r.account] += 1

  return {
    total: rows.length,
    artifact: art
      ? { id: art.id, name: art.name, kind: art.kind, status: art.status, sale_state: art.sale_state,
          link: art.link, pan_code: panCode(art.note, art.link) }
      : null,
    artifact_unresolved: artMiss, // 🔴 这个册 id 库里没有，页面照实说
    account_unknown: badAcc.length ? badAcc : null, // account 只有 A/B 两个值，别的词照实回
    sale_state_unknown: badSale.length ? badSale : null, // 同上：售卖态值域外的词照实回
    account_total: acct,
    burned_total: rows.filter((r) => r.burned).length,
    active_dup: dup, // 空数组=闸绿
    filters: {
      artifact_id: aid || null,
      account: acc,
      active,
      burned,
      sale_state: sale,
      q: kw || null,
    },
    rows: rows.map((r) => ({
      id: r.id,
      artifact_id: r.artifact_id,
      artifact_name: r.artifact_name ?? null,
      artifact_kind: r.artifact_kind ?? null,
      artifact_status: r.artifact_status ?? null,
      artifact_sale_state: r.artifact_sale_state ?? null,
      artifact_missing: r.artifact_name == null, // 物料挂了个不存在的册=断链，如实标
      account: r.account,
      is_active: !!r.is_active,
      burned: !!r.burned, // 已发过=烧掉，页面灰显
      title: r.title,
      body: r.body, // 全文出（一键复制要的就是全文，不截断）
      topics: r.topics_json ? parseJson(r.topics_json) : [],
      style_seed: r.style_seed,
      product_desc: r.product_desc,
      pan_share_text: r.pan_share_text,
      pan_code: panCode(r.artifact_note, r.artifact_link),
      publish_count: r.publish_count,
      last_published_on: r.last_published_on,
      created_at: r.created_at,
    })),
  }
}

/** 合刊关系（吃自 doc_member）。?parent_id= 只看某合刊；?member_id= 反查某册被谁收编。 */
function epArtifactMembers(db, q) {
  const where = []
  const args = []
  const pid = q.get('parent_id')
  const mid = q.get('member_id')
  if (pid) {
    where.push('am.parent_id = ?')
    args.push(pid)
  }
  if (mid) {
    where.push('am.member_id = ?')
    args.push(mid)
  }
  const sql = where.length ? ` WHERE ${where.join(' AND ')}` : ''
  const rows = all(
    db,
    `SELECT am.parent_id, am.member_id, am.ord,
            p.name AS parent_name, p.kind AS parent_kind, p.status AS parent_status,
            p.sale_state AS parent_sale_state,
            c.name AS member_name, c.kind AS member_kind, c.status AS member_status,
            c.sale_state AS member_sale_state
     FROM artifact_member am
     LEFT JOIN artifact p ON p.id = am.parent_id
     LEFT JOIN artifact c ON c.id = am.member_id${sql}
     ORDER BY p.name, am.ord, am.member_id`,
    ...args,
  )
  const byParent = new Map()
  for (const r of rows) {
    if (!byParent.has(r.parent_id)) {
      byParent.set(r.parent_id, {
        parent_id: r.parent_id,
        parent_name: r.parent_name ?? null,
        parent_kind: r.parent_kind ?? null,
        parent_status: r.parent_status ?? null,
        parent_sale_state: r.parent_sale_state ?? null,
        parent_missing: r.parent_name == null,
        members: [],
      })
    }
    byParent.get(r.parent_id).members.push({
      id: r.member_id,
      ord: r.ord,
      name: r.member_name ?? null,
      kind: r.member_kind ?? null,
      status: r.member_status ?? null,
      sale_state: r.member_sale_state ?? null,
      missing: r.member_name == null, // 🔴 指向不存在的册=断链
    })
  }
  const groups = [...byParent.values()]
  return {
    pair_total: rows.length,
    parent_total: groups.length,
    broken_total: rows.filter((r) => r.parent_name == null || r.member_name == null).length,
    filters: { parent_id: pid || null, member_id: mid || null },
    rows: groups,
  }
}

// ── 🔴 全站唯一写端点 ────────────────────────────────────────────────────
/**
 * 改一本资料的**售卖态 sale_state**（`在售` / `待整理` / `停售` / 清空）。
 *
 * ┌─ 以下血案注释原样搬自 punch-console `web/src/app/api/doc-state/route.ts`
 * │  （PRD-003 吃库并入 v2，注释随口径一起搬——这条闸的理由不能在搬家路上丢了）
 * │
 * │ 🔴🔴 为什么必须是"人点一下"而不是产线自动置：
 * │    2026-08-10 实伤 —— 11 条管线四盏灯刚转绿，就被顺手 `UPDATE 人工态='在售'`。
 * │    可用户**根本还没发布过**。「能发」不等于「已发」，中间隔着一次人工动作
 * │    （去小红书发帖、挂商品），那件事机器做不了也不该替人宣布做完了。
 * │    用户原话：「我还没发布呢？你不要自己联想状态」。
 * │    ⇒ 这个接口存在的意义就是把那次动作**留给人**，产线侧任何代码都不许调它。
 * │
 * │ 🔴 只允许写 `人工态` 这一列。其余列各有各的事实源：
 * │    题/物料/图由产线重跑覆盖，网盘链接由物料 md 带进来 —— 从界面改会被下次 import 抹掉。
 * │
 * │ 🔴 人工态是**产线不碰的人工列**（`import-all.ts` 的 `upsertDoc(..., 保留人工列=true)`
 * │    set 白名单里没有 manualState），所以这里写进去的值重跑导入不会被冲掉。
 * └─────────────────────────────────────────────────────────────────────
 *
 * v2 落点差异（口径不变，只是搬了家）：
 *   · 列名 `人工态` → `artifact.sale_state`（数据结构 §2.6c；🔴 与产线机器列 status 两物两名不合并）；
 *   · id 是 **字符串**不是整数（v2 铁律：id 全链路字符串，绝不 Number() 一下再进 SQL）；
 *   · 「产线不碰」在 v2 由 工具箱/挂账/artifact_tool.py 的 set 白名单守（它不写 sale_state）。
 */
const SALE_STATES = new Set(['在售', '待整理', '停售'])

function epSetSaleState(body) {
  let payload
  try {
    payload = JSON.parse(body || '')
  } catch {
    return { code: 400, data: { ok: false, error: '请求体不是 JSON' } }
  }
  const id = payload?.id
  if (typeof id !== 'string' || !id.trim()) {
    // 🔴 不接受数字 id：给了数字就是调用方还带着老区/punch-console 的整数 id 习惯，宁可报错
    return { code: 400, data: { ok: false, error: 'id 必须是非空字符串（v2 铁律：id 全链路字符串）' } }
  }
  const raw = Object.prototype.hasOwnProperty.call(payload, 'sale_state') ? payload.sale_state : undefined
  if (raw === undefined) {
    return { code: 400, data: { ok: false, error: '缺 sale_state 字段（清空请显式给 null）' } }
  }
  // null / "" / "清空" 都表示清空这一列
  const next = raw === null || raw === '' || raw === '清空' ? null : String(raw)
  if (next !== null && !SALE_STATES.has(next)) {
    return {
      code: 400,
      data: { ok: false, error: `sale_state 只能是 ${[...SALE_STATES].join(' / ')} 或空`, got: next },
    }
  }

  const db = openRw()
  try {
    const prev = one(db, 'SELECT id, name, sale_state FROM artifact WHERE id = ?', id.trim())
    if (!prev) return { code: 404, data: { ok: false, error: '没有这本资料', id } }
    // 🔴 这是本文件唯一一条写语句，且列名写死在字面量里——多写一列都要过 code review
    db.prepare('UPDATE artifact SET sale_state = ? WHERE id = ?').run(next, id.trim())
    return { code: 200, data: { ok: true, id: prev.id, name: prev.name, from: prev.sale_state, to: next } }
  } finally {
    try {
      db.close()
    } catch {
      /* 关不上就算了，进程退出会回收 */
    }
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
  { re: /^\/api\/kb\/artifact-members$/, run: (db, _m, q) => epArtifactMembers(db, q) },
  { re: /^\/api\/kb\/artifacts\/(.+)$/, run: (db, m) => epArtifactDetail(db, decodeURIComponent(m[1])) },
  { re: /^\/api\/kb\/materials$/, run: (db, _m, q) => epMaterials(db, q) },
  { re: /^\/api\/kb\/papers\/(.+)$/, run: (db, m) => epPaperDetail(db, decodeURIComponent(m[1])) },
]

/**
 * 🔴 写端点白名单——全站就这一条，长度硬断言在文件末尾。
 * 想再加一条写口 = 先回 认知/数据结构.md 改「页面只读」正本，改完再回来动这个数组。
 */
const WRITE_ROUTES = [{ method: 'POST', path: '/api/kb/sale-state', run: epSetSaleState }]

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
    // 🔴 只读 API：非 GET 一律拒，唯一豁免=白名单里那一条写端点（改 artifact.sale_state 一列）
    const w = WRITE_ROUTES.find((x) => x.method === req.method && x.path === url.pathname)
    if (!w) {
      return send(res, 405, {
        error: '本 API 只读，只接受 GET',
        写端点: WRITE_ROUTES.map((x) => `${x.method} ${x.path}`),
      })
    }
    const chunks = []
    let size = 0
    let tooBig = false
    req.on('error', () => {
      /* 连接被掐断（多半是下面这条 destroy 自己干的），不算服务出错 */
    })
    req.on('data', (c) => {
      if (tooBig) return
      size += c.length
      if (size > 64 * 1024) {
        // 写端点只吃一个 {id, sale_state}，超 64KB 必是打错门了——先回话再断，别让对方干等
        tooBig = true
        send(res, 413, { ok: false, error: '请求体过大（本端点只接受一个小 JSON）' })
        req.destroy()
        return
      }
      chunks.push(c)
    })
    req.on('end', () => {
      if (tooBig) return
      try {
        const out = w.run(Buffer.concat(chunks).toString('utf8'))
        send(res, out.code, out.data)
      } catch (e) {
        console.error(`[kb-read-api] ${url.pathname} 写出错：${e.message}`)
        send(res, 500, { ok: false, error: String(e.message) })
      }
    })
    return
  }
  const hit = ROUTES.map((r) => ({ r, m: r.re.exec(url.pathname) })).find((x) => x.m)
  if (!hit) {
    return send(res, 404, {
      error: '无此端点',
      // 🔴 数字现算不手写（自报端点数曾经报错过：说 11 实为 10）
      端点合计: `${ROUTES.length} 读 + ${WRITE_ROUTES.length} 写 = ${ROUTES.length + WRITE_ROUTES.length}`,
      endpoints: [
        'GET /api/kb/stats',
        'GET /api/kb/kg/tree',
        'GET /api/kb/questions?kp=&status=&source_kind=&qtype=&difficulty=&tag=&unused=&page=&size=' +
          '（qtype/difficulty/tag 可重复给：同名多值 qtype/difficulty=OR、tag=AND；' +
          'tag 写「域:名」或「名」；unused=1 未进过卷 / unused=0 进过卷）',
        'GET /api/kb/questions/:id',
        'GET /api/kb/artifacts',
        'GET /api/kb/artifacts/:id（含 sale_state / link / 解析出的 pan_code / 合刊 members）',
        'GET /api/kb/artifact-members?parent_id=&member_id=（合刊关系）',
        'GET /api/kb/materials?artifact_id=&account=A|B&active=&burned=&sale_state=&q=' +
          '（sale_state 可写「未标」查未标册；account 可重复给=OR）',
        'GET /api/kb/papers/:id',
        '🔴 POST /api/kb/sale-state {id, sale_state}（全站唯一写端点，只写 artifact.sale_state 一列）',
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
// 🔴 起服务前的自检闸①：全站写端点必须恰好 1 条，且只能是 sale-state；读端点数必须与
// 文件头「端点账」对得上。靠闸不靠注释——有人偷偷 push 第二条写口 / 加个口不改账，服务直接起不来。
const EP_READ = 9 // 原 7 读 + PRD-003 的 materials、artifact-members
const EP_WRITE = 1 // 全站唯一写口 sale-state
if (WRITE_ROUTES.length !== EP_WRITE || WRITE_ROUTES[0].path !== '/api/kb/sale-state') {
  console.error(`🔴 写端点白名单被改了（现有 ${WRITE_ROUTES.length} 条）：页面只读原则=全站唯一写端点 sale-state`)
  process.exit(3)
}
if (ROUTES.length !== EP_READ) {
  console.error(
    `🔴 端点账对不上：ROUTES 实有 ${ROUTES.length} 读，文件头「端点账」写的是 ${EP_READ} 读。\n` +
      `   加口/删口请同步改：文件头端点账、EP_READ、404 的 endpoints 清单、console/README.md`,
  )
  process.exit(3)
}
// 🔴 起服务前的自检闸②：artifact 必须有 sale_state 列（PRD-003 的售卖态人工列）。
// 缺列 = 这个库没跑过 263 号 DDL，artifacts / artifacts/:id / materials / sale-state
// 四个口会在运行期齐刷刷 500（no such column: a.sale_state）。
// 宁可起不来也不许"静默起来等着 500"——报错要直接给出修法。
{
  let cols
  try {
    const probe = openRo()
    try {
      cols = probe.prepare('PRAGMA table_info(artifact)').all().map((c) => c.name)
    } finally {
      probe.close()
    }
  } catch (e) {
    console.error(`🔴 库打不开：${DB_PATH}（${e.message}）`)
    process.exit(4)
  }
  if (!cols.length) {
    console.error(`🔴 库里没有 artifact 表：${DB_PATH}\n   跑 python 工具箱/库/init_db.py --only kb 建库`)
    process.exit(4)
  }
  if (!cols.includes('sale_state')) {
    console.error(
      `🔴 artifact 表缺 sale_state 列（PRD-003 售卖态人工列），` +
        `/api/kb/artifacts、/api/kb/artifacts/:id、/api/kb/materials、POST /api/kb/sale-state 四个口会 500。\n` +
        `   跑 python 工具箱/库/apply_ddl_263.py ${DB_PATH}`,
    )
    process.exit(4)
  }
}
server.listen(PORT, HOST, () => {
  console.log(
    `kb 读 API :${PORT} 库=${DB_PATH} 只读` +
      `（端点 ${ROUTES.length} 读 + ${WRITE_ROUTES.length} 写 = ${ROUTES.length + WRITE_ROUTES.length}，` +
      `唯一写口 POST /api/kb/sale-state）`,
  )
})
