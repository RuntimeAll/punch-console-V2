/**
 * kb 读 API · PRD-007 维护域端点自证（node 直跑：node --test console/server/kb-read-api-prd007.test.mjs）
 * ═══════════════════════════════════════════════════════════════════════
 * 覆盖线2「展示台去 mock」新开的 6 个只读口 + 题库页三项增强：
 *   ① GET /api/kb/kg/aliases      别名层：分组统计 / 一词多挂 / 别名断链
 *   ② GET /api/kb/kp/:id          考点节点详情：叶（档案+家当）与枝（下辖+零挂载缺口）两种形态
 *   ③ GET /api/kb/models          三张脸：exam_model 出题数现算 / solution_model / pattern 停用零行
 *   ④ GET /api/kb/criteria        判据：线分组 / 现行废止分开数 / 替代链（含断链）
 *   ⑤ GET /api/kb/templates       模版：params 展开 / 样张登记与否 / 用它的册数
 *   ⑥ GET /api/kb/semantic/health 语意 serve 探活：探不到活也必须 200 + ok:false（页面据此降级）
 *   ⑦ /api/kb/questions 增强：来源三维筛选（含「未标」）/ 工单标记 / facets 全库口径 /
 *      --like 在 serve 挂掉时**明确报错**不静默降级
 *
 * 🔴 本测试的两条核心闸：
 *   · **页面只读没被破**：新开 6 个口一个写口都没加，写端点数恒 =1（下面直接对 404 自报数断言）；
 *   · **坏账要看得见**：一词多挂 / 别名断链 / 模型挂了不存在的叶 / 判据替代链指空，
 *     四种坏账各插一条假数据，断言 API 如实标出来而不是静默吞掉。
 *
 * 🔴 库：临时目录里按 工具箱/库/schema_kb.sql（结构 SSOT）现建空库再插假数据，
 *   不拷、不连 知识库/kb.db。端口 4314（避开主位 4310 与 prd003 测试的 4311/4313）。
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

process.removeAllListeners('warning')
process.on('warning', (w) => {
  if (w.name === 'ExperimentalWarning' && /SQLite/i.test(String(w.message))) return
  console.warn(w)
})
for (const k of ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy']) delete process.env[k]
process.env.NO_PROXY = '*'

const HERE = dirname(fileURLToPath(import.meta.url))
const API = join(HERE, 'kb-read-api.mjs')
const SCHEMA = resolve(HERE, '..', '..', '工具箱', '库', 'schema_kb.sql')
const PORT = Number(process.env.KB_API_TEST_PORT || 4314)
/** 🔴 故意指一个没人监听的端口：语意 serve「挂掉」这条路必须能测（页面降级就靠它） */
const DEAD_EMBED_PORT = Number(process.env.EMBED_TEST_PORT || 4399)
const BASE = `http://127.0.0.1:${PORT}`

let tmp = ''
let dbPath = ''
let child = null
let banner = ''

const get = async (p) => {
  const r = await fetch(`${BASE}${p}`)
  return { status: r.status, body: await r.json() }
}

before(async () => {
  tmp = mkdtempSync(join(tmpdir(), 'kbapi-prd007-'))
  dbPath = join(tmp, 'kb.db')
  // 🔴 关外键：下面要故意插「指向不存在的 kp / criterion」的坏账，读侧必须认得出来。
  //   这不是编造场景——写入通路是 python sqlite3（默认 FK OFF），坏账真能落进库。
  const db = new DatabaseSync(dbPath, { enableForeignKeyConstraints: false })
  db.exec(readFileSync(SCHEMA, 'utf8'))
  const hasSale = db.prepare('PRAGMA table_info(artifact)').all().some((c) => c.name === 'sale_state')
  if (!hasSale) {
    db.exec("ALTER TABLE artifact ADD COLUMN sale_state TEXT CHECK(sale_state IN ('在售','待整理','停售'))")
  }

  // ── kp 树：版本 › 单元 › 三片叶（一片零挂载）──────────────────────────
  const kp = db.prepare(
    'INSERT INTO kp (id,name,parent_id,level,ord,status,note,emphasis,freq,diff_code,desc) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
  )
  kp.run('K0', '浙教版数学', null, '版本', 1, '现行', null, null, null, null, null)
  kp.run('K1', '有理数', 'K0', '单元', 1, '现行', null, null, null, null, null)
  kp.run('K1A', '绝对值的概念', 'K1', '考点', 1, '现行', null, '重难点', '高频', 'D2', '考法：求一个数的绝对值')
  kp.run('K1B', '相反数', 'K1', '考点', 2, '现行', null, null, null, null, null)
  kp.run('K1C', '零挂载的叶', 'K1', '考点', 3, '现行', null, null, null, null, null) // 一道题都不挂

  const alias = db.prepare('INSERT INTO kp_alias (kp_id,alias,alias_kind) VALUES (?,?,?)')
  alias.run('K1A', '绝对值', '讲义名')
  alias.run('K1A', '绝对值化简', '产线词')
  alias.run('K1B', '相反数与倒数', '老区名')
  // 🔴 坏账①：一词多挂 —— 同一别名指向两片叶，resolve 必然二义
  alias.run('K1A', '两头挂的词', '产线词')
  alias.run('K1B', '两头挂的词', '产线词')
  // 🔴 坏账②：别名断链 —— 指向库里没有的 kp
  alias.run('K不存在', '孤儿别名', '老区名')

  // ── 题：给 kp 详情的「直挂题」与题库页增强的来源三维当靶子 ────────────
  const q = db.prepare(
    `INSERT INTO question (id,blocks_json,qtype_code,diff_code,source_kind,source_raw,prov_json,status,created_at)
     VALUES (?,?,?,?,?,?,?,?,?)`,
  )
  const blocks = (t) => JSON.stringify({ v: 2, rows: [{ cells: [{ type: 'text', md: t }] }] })
  q.run('q1', blocks('化简 |-3| 的值'), null, null, 'manual', '浙教七上预习讲义·讲1·p07',
    JSON.stringify({ 教材版本: '浙教', 版本使用级: '一级·浙教', 讲: 1 }), '上架', '2026-08-20 01:00:00')
  q.run('q2', blocks('求 -2 的相反数'), null, null, 'scan', '卷3',
    JSON.stringify({ 教材版本: '人教2024', 版本使用级: '二级·人教互通', 卷: '卷3', 卷名: '第一章 有理数单元测试' }),
    '上架', '2026-08-20 01:01:00')
  // 🔴 prov 全空的题：来源三维的「未标」那一档（facets 里必须占一格，不许被吞）
  q.run('q3', blocks('没有任何 prov 的题'), null, null, 'manual', null, null, '草稿', '2026-08-20 01:02:00')
  const qk = db.prepare('INSERT INTO question_kp (question_id,kp_id,is_primary) VALUES (?,?,?)')
  qk.run('q1', 'K1A', 1)
  qk.run('q2', 'K1B', 1)
  qk.run('q3', 'K1A', 1)

  // 🔴 工单：q3 挂一条待处理（页面必须标红）、q1 挂一条已处理（不该算进「还挂着」）
  const rt = db.prepare('INSERT INTO review_ticket (id,kind,ref,status,note,created_at) VALUES (?,?,?,?,?,?)')
  rt.run(1, '图审', 'q3', '待处理', 'L3·细审', '2026-08-20 01:03:00')
  rt.run(2, '图审', 'q1', '已处理', '已放行', '2026-08-20 01:04:00')

  // ── 三张脸 ────────────────────────────────────────────────────────────
  const em = db.prepare(
    'INSERT INTO exam_model (id,name,kp_ids_json,dsl_ref,params_json,note,status) VALUES (?,?,?,?,?,?,?)',
  )
  em.run('EM1', '绝对值链', JSON.stringify(['K1A']), '工具箱/dsl/x_qbank.py', '{"gens":["g1"],"lv":[1,3]}', '备注', '在用')
  // 🔴 坏账③：模型挂了一片不存在的叶（溯源断链）+ 一条一片叶都没挂（溯源断点）
  em.run('EM2', '挂了不存在的叶', JSON.stringify(['K不存在']), null, null, null, '在用')
  em.run('EM3', '一片叶都没挂', '[]', null, null, null, '停用')
  db.prepare(
    'INSERT INTO solution_model (id,name,kp_ids_json,trigger_feature,action_conclusion,tier,freq,status) VALUES (?,?,?,?,?,?,?,?)',
  ).run('SM1', '先定号再定序', JSON.stringify(['K1A', 'K1B']), '看到混合算式', '先定号再定序', 1, 3, '在用')
  // question_pattern 一行都不插：对齐-003 停用后的正常态就是零行

  // ── 判据：两条现行 + 一条废止（替代链有效）+ 一条废止（替代链指空=断链）──
  const cr = db.prepare(
    'INSERT INTO criterion (id,line,scene,rule,why,source_ref,status,superseded_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
  )
  cr.run('R01', '录入', '读 docx 段落', '必须读 XML run 级', '只读 w:t 会静默丢公式', '坑清单 R01', '现行', null, '2026-08-18T19:49:39')
  cr.run('R02', '录入', '读 docx 表格', '表格必须作为结构进块流', null, '坑清单 R02', '现行', null, '2026-08-18T19:49:39')
  cr.run('G01', '批改', '判卷面涂改', '涂改处按最终笔迹判', null, '批改线拍板', '现行', null, '2026-08-19T10:00:00')
  cr.run('DEP1', '录入', '公式重的 docx（老规则）', '【已废止】oMath>=8 送 OCR', '老区补偿动作', '数据结构 §2.7', '废止', 'R01', '2026-08-18T19:49:39')
  // 🔴 坏账④：替代链指向一条根本不存在的判据
  cr.run('DEP2', '录入', '指了个不存在的替代条', '【已废止】老规则二', null, '存档', '废止', 'C不存在', '2026-08-18T19:49:39')

  // ── 模版：一张登记了样张 + 一张没登记；一本册用了前者 ──────────────────
  db.prepare('INSERT INTO asset (hash,kind,rel_path,meta_json,created_at) VALUES (?,?,?,?,?)')
    .run('h-sample', 'sample', '知识库/资产/sample/exam-v1.png', null, '2026-08-20 01:00:00')
  const tpl = db.prepare(
    `INSERT INTO template (id,name,purpose,book_kinds,params_json,pitfalls,version,status,sample_asset,registered_by,updated_at)
     VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
  )
  tpl.run('tpl-a', 'A4真卷', '单元测试卷', '专项卷',
    '{"layout":"exam_paper","纸张":"A4","边距mm":{"上":13,"左右":12}}', '一卷多页要走 @page margin',
    'v1', '在用', 'h-sample', 'agent', '2026-08-20 01:32:22')
  tpl.run('tpl-b', '停用的老版式', '老打卡册', '打卡册', '{"layout":"old"}', null, 'v0', '停用', null, 'agent', '2026-08-19 01:00:00')
  db.prepare('INSERT INTO artifact (id,name,kind,status,template_id,created_at) VALUES (?,?,?,?,?,?)')
    .run('A1', '某单元卷', '专项卷', '在产', 'tpl-a', '2026-08-20 01:00:00')
  db.close()

  child = spawn(process.execPath, [API], {
    // 🔴 EMBED_PORT 指到没人监听的口：语意那条路的「挂了怎么办」才测得到
    env: { ...process.env, KB_DB: dbPath, KB_API_PORT: String(PORT), EMBED_PORT: String(DEAD_EMBED_PORT) },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  child.stderr.on('data', (d) => process.stderr.write(`[api] ${d}`))
  await new Promise((ok, bad) => {
    const t = setTimeout(() => bad(new Error('API 起不来（10s 超时）')), 10000)
    child.stdout.on('data', (d) => {
      banner += String(d)
      if (String(d).includes(`:${PORT}`)) {
        clearTimeout(t)
        ok()
      }
    })
  })
})

after(() => {
  child?.kill()
  try {
    rmSync(tmp, { recursive: true, force: true })
  } catch {
    /* 临时目录删不掉不影响结论 */
  }
})

// ── ① 别名层 ────────────────────────────────────────────────────────────
test('kg/aliases：分组统计 + 一词多挂 + 别名断链，三样都摆出来', async () => {
  const r = await get('/api/kb/kg/aliases')
  assert.equal(r.status, 200)
  assert.equal(r.body.total, 6)
  assert.equal(r.body.covered_kp, 3) // K1A / K1B / K不存在
  // 🔴 一词多挂必须点名，不许只给个数
  assert.deepEqual(r.body.ambiguous, [{ alias: '两头挂的词', kp_count: 2 }])
  assert.equal(r.body.broken_total, 1)
  const orphan = r.body.rows.find((x) => x.alias === '孤儿别名')
  assert.equal(orphan.missing, true)
  assert.equal(orphan.kp_name, null)
  const kinds = Object.fromEntries(r.body.kind_stat.map((k) => [k.kind, k.count]))
  assert.equal(kinds['产线词'], 3)
  assert.equal(kinds['讲义名'], 1)
})

test('kg/aliases：按叶 / 按来源 / 关键词筛，且 % _ 只当字面量', async () => {
  assert.equal((await get('/api/kb/kg/aliases?kp_id=K1A')).body.shown, 3)
  assert.equal((await get('/api/kb/kg/aliases?kind=%E8%AE%B2%E4%B9%89%E5%90%8D')).body.shown, 1)
  // 🔴 转义闸：q=% 转义前等于「全表」，转义后只该匹配含百分号的别名 ⇒ 0 条
  assert.equal((await get('/api/kb/kg/aliases?q=%25')).body.shown, 0)
  assert.equal((await get('/api/kb/kg/aliases?q=_')).body.shown, 0)
  // 🔴 但**总数不随筛选缩水**：统计是全表口径，筛出 0 条时页面仍要知道库里一共 6 条
  assert.equal((await get('/api/kb/kg/aliases?q=%25')).body.total, 6)
})

// ── ② 考点节点详情 ──────────────────────────────────────────────────────
test('kp/:id 叶：档案（教研属性+考法描述）/ 家当（题+模型）/ 直挂题', async () => {
  const r = await get('/api/kb/kp/K1A')
  assert.equal(r.status, 200)
  assert.equal(r.body.is_leaf, true)
  assert.equal(r.body.q_count, 2) // q1 + q3
  assert.equal(r.body.emphasis, '重难点')
  assert.equal(r.body.freq, '高频')
  assert.match(r.body.desc, /考法/)
  assert.deepEqual(r.body.path.map((p) => p.name), ['浙教版数学', '有理数', '绝对值的概念'])
  assert.equal(r.body.aliases.length, 3)
  assert.equal(r.body.exam_models.length, 1)
  assert.equal(r.body.exam_models[0].id, 'EM1')
  assert.equal(r.body.solution_models.length, 1)
  assert.equal(r.body.patterns.length, 0) // 停用表，永远零
  assert.equal(r.body.questions.length, 2)
})

test('kp/:id 枝：下辖规模 + 零挂载缺口清单（不是「数据没录完」，是缺口）', async () => {
  const r = await get('/api/kb/kp/K1')
  assert.equal(r.body.is_leaf, false)
  assert.equal(r.body.leaf_total, 3)
  assert.equal(r.body.q_total, 3) // 子树去重题数
  assert.deepEqual(r.body.zero_mount_leaves.map((l) => l.id), ['K1C'])
  assert.equal(r.body.children.length, 3)
})

test('kp/:id 查无此节点 ⇒ 404（不许回个空壳假装有）', async () => {
  assert.equal((await get('/api/kb/kp/K不存在')).status, 404)
})

// ── ③ 三张脸 ────────────────────────────────────────────────────────────
test('models：出题数现算 / 溯源两种断法分开标 / pattern 停用零行有证据', async () => {
  const r = await get('/api/kb/models')
  assert.equal(r.status, 200)
  assert.equal(r.body.exam.total, 3)
  assert.equal(r.body.exam.in_use, 2)
  // 🔴 两种断法不许糊成一种：EM2 是「挂了不存在的叶」，EM3 是「一片叶都没挂」
  assert.equal(r.body.trace_gap.exam_broken_kp, 1)
  assert.equal(r.body.trace_gap.exam_no_kp, 1)
  const em2 = r.body.exam.rows.find((m) => m.id === 'EM2')
  assert.equal(em2.kps[0].missing, true)
  assert.equal(em2.kps[0].name, null)
  const em1 = r.body.exam.rows.find((m) => m.id === 'EM1')
  assert.deepEqual(em1.params, { gens: ['g1'], lv: [1, 3] })
  assert.equal(em1.kps[0].name, '绝对值的概念')
  // 解题模型双旋钮原样端出
  assert.equal(r.body.solution.rows[0].tier, 1)
  assert.equal(r.body.solution.rows[0].freq, 3)
  // 🔴 停用那张脸：零行 + disabled + 「写了 pattern_id 的题」现算为 0（非 0 就是违例）
  assert.equal(r.body.pattern.total, 0)
  assert.equal(r.body.pattern.disabled, true)
  assert.match(r.body.pattern.disabled_note, /对齐-003/)
  assert.equal(r.body.pattern.question_with_pattern_id, 0)
  assert.equal(r.body.pattern.kp_desc_total, 1) // 只有 K1A 写了 desc
})

test('models：exam_model 的已出题数来自题的血缘（prov.model_id），不是表上的冗余列', async () => {
  const before_ = (await get('/api/kb/models')).body.exam.rows.find((m) => m.id === 'EM1')
  assert.equal(before_.question_count, 0) // 还没有题记它的血缘
  const db = new DatabaseSync(dbPath)
  db.prepare(
    `INSERT INTO question (id,blocks_json,source_kind,prov_json,status,created_at) VALUES (?,?,?,?,?,?)`,
  ).run('q4', JSON.stringify({ v: 2, rows: [] }), 'model', JSON.stringify({ model_id: 'EM1' }), '上架', '2026-08-20 02:00:00')
  db.close()
  const after_ = (await get('/api/kb/models')).body.exam.rows.find((m) => m.id === 'EM1')
  assert.equal(after_.question_count, 1, '🔴 出题数没跟着题的血缘走 = 落了冗余计数列')
})

// ── ④ 判据 ──────────────────────────────────────────────────────────────
test('criteria：线分组 / 现行废止分开数 / 替代链（含指空的断链）', async () => {
  const r = await get('/api/kb/criteria')
  assert.equal(r.status, 200)
  assert.equal(r.body.total, 5)
  assert.equal(r.body.live_total, 3)
  assert.equal(r.body.dead_total, 2)
  const stat = Object.fromEntries(r.body.line_stat.map((l) => [l.line, l]))
  assert.equal(stat['录入'].total, 4)
  assert.equal(stat['录入'].live, 2)
  assert.equal(stat['录入'].dead, 2)
  assert.equal(stat['批改'].total, 1)
  // 🔴 CHECK 里有四条线，库里只有两条有货 ⇒ 只报有货的，不给没有的线渲空页签
  assert.equal(r.body.line_stat.length, 2)
  const dep1 = r.body.rows.find((c) => c.id === 'DEP1')
  assert.equal(dep1.superseded_by_info.missing, false)
  assert.equal(dep1.superseded_by_info.scene, '读 docx 段落')
  const dep2 = r.body.rows.find((c) => c.id === 'DEP2')
  assert.equal(dep2.superseded_by_info.missing, true, '🔴 替代链指空必须标出来，不许显示成正常替代')
})

test('criteria：按线 / 按状态 / 关键词筛，且分组统计不随筛选缩水', async () => {
  const live = await get('/api/kb/criteria?status=%E7%8E%B0%E8%A1%8C')
  assert.equal(live.body.shown, 3)
  assert.equal(live.body.rows.every((c) => c.status === '现行'), true)
  assert.equal(live.body.total, 5, '🔴 全库数被筛小了 = 页签上的账会跟着漂')
  const dead = await get('/api/kb/criteria?status=%E5%BA%9F%E6%AD%A2&line=%E5%BD%95%E5%85%A5')
  assert.equal(dead.body.shown, 2)
  assert.equal((await get('/api/kb/criteria?q=%25')).body.shown, 0) // 通配符转义闸
})

// ── ⑤ 模版 ──────────────────────────────────────────────────────────────
test('templates：params 展开 / 样张登记与否 / 用它的册数现算', async () => {
  const r = await get('/api/kb/templates')
  assert.equal(r.status, 200)
  assert.equal(r.body.total, 2)
  assert.equal(r.body.in_use, 1)
  assert.equal(r.body.with_sample, 1)
  const a = r.body.rows.find((t) => t.id === 'tpl-a')
  assert.equal(a.params.layout, 'exam_paper')
  assert.deepEqual(a.params['边距mm'], { 上: 13, 左右: 12 })
  assert.equal(a.sample_rel_path, '知识库/资产/sample/exam-v1.png')
  assert.equal(a.artifact_count, 1)
  assert.match(a.pitfalls, /@page margin/)
  const b = r.body.rows.find((t) => t.id === 'tpl-b')
  // 🔴 没登记样张就是没登记：回 null，页面写「待登记」，不许拿占位图冒充
  assert.equal(b.sample_rel_path, null)
  assert.equal(b.artifact_count, 0)
  // 停用的模版不删（发出去的册子还是老版式）
  assert.equal((await get('/api/kb/templates?status=%E5%81%9C%E7%94%A8')).body.shown, 1)
})

// ── ⑥ 语意 serve 探活与降级 ─────────────────────────────────────────────
test('semantic/health：serve 挂了也回 200 + ok:false（页面据此收起搜索框，不报红）', async () => {
  const r = await get('/api/kb/semantic/health')
  assert.equal(r.status, 200, '🔴 探活口自己不许 5xx——它就是用来问「活着吗」的')
  assert.equal(r.body.ok, false)
  assert.equal(r.body.port, DEAD_EMBED_PORT)
  assert.match(r.body.hint, /启动台/)
})

test('--like：serve 挂了必须明确报错，绝不静默退回「按时间排」冒充语意命中', async () => {
  const r = await get('/api/kb/questions?like=%E7%BB%9D%E5%AF%B9%E5%80%BC')
  assert.equal(r.status, 500)
  assert.match(r.body.error, new RegExp(`语意 serve :${DEAD_EMBED_PORT} 连不上`))
})

// ── ⑦ 题库页三项增强 ────────────────────────────────────────────────────
test('questions：来源三维 facets 是全库口径，「未标」自成一档不被吞', async () => {
  const r = await get('/api/kb/questions?size=50')
  assert.equal(r.status, 200)
  const tb = Object.fromEntries(r.body.facets.textbook.map((f) => [f.label, f.count]))
  assert.equal(tb['浙教'], 1)
  assert.equal(tb['人教2024'], 1)
  assert.equal(tb['未标'], 2, '🔴 prov 没记版本的题必须占一档（q3 与 q4），不许被吞')
  const sb = Object.fromEntries(r.body.facets.src_book.map((f) => [f.label, f.count]))
  assert.equal(sb['第一章 有理数单元测试'], 1) // 卷名那一档
  assert.equal(sb['浙教七上预习讲义'], 1) // 讲义 → source_raw 首段
  assert.equal(r.body.facets.ticket_open_total, 1)
  assert.equal(r.body.facets.question_total, 4)
})

test('questions：来源三维筛选（含「未标」），筛不中就是 0 条不当「不过滤」', async () => {
  assert.equal((await get('/api/kb/questions?textbook=%E6%B5%99%E6%95%99')).body.total, 1)
  assert.equal((await get('/api/kb/questions?use_level=%E4%B8%80%E7%BA%A7%C2%B7%E6%B5%99%E6%95%99')).body.total, 1)
  // 「未标」= prov 里没这一维的题
  assert.equal((await get('/api/kb/questions?textbook=%E6%9C%AA%E6%A0%87')).body.total, 2)
  // 多值 = OR
  assert.equal((await get('/api/kb/questions?textbook=%E6%B5%99%E6%95%99&textbook=%E4%BA%BA%E6%95%992024')).body.total, 2)
  // 🔴 库里根本没有的值 ⇒ 0 条（不是「不过滤」= 全都有）
  assert.equal((await get('/api/kb/questions?textbook=%E5%8C%97%E5%B8%88%E5%A4%A7')).body.total, 0)
})

test('questions：行上带来源三维与推法说明；工单只算「待处理」的', async () => {
  const r = await get('/api/kb/questions?size=50')
  const q1 = r.body.rows.find((x) => x.id === 'q1')
  assert.equal(q1.textbook, '浙教')
  assert.equal(q1.src_book, '浙教七上预习讲义')
  assert.equal(q1.src_book_from, 'prov.讲→source_raw 首段', '🔴 来源册是现推的，推法必须随行带出来')
  // q1 挂的是「已处理」的单 ⇒ 不算还挂着
  assert.equal(q1.ticket_open, 0)
  assert.equal(q1.tickets.length, 1)
  const q2 = r.body.rows.find((x) => x.id === 'q2')
  assert.equal(q2.src_book, '第一章 有理数单元测试')
  assert.equal(q2.src_book_from, 'prov.卷名')
  const q3 = r.body.rows.find((x) => x.id === 'q3')
  assert.equal(q3.ticket_open, 1)
  assert.equal(q3.status, '草稿')
  assert.equal(q3.src_book, null) // prov 全空 ⇒ 推不出册，如实为 null
})

test('questions：ticket=1 只出还挂着待处理工单的题（闸④ 上脸）', async () => {
  const r = await get('/api/kb/questions?ticket=1')
  assert.equal(r.body.total, 1)
  assert.equal(r.body.rows[0].id, 'q3')
  const off = await get('/api/kb/questions?ticket=0')
  assert.equal(off.body.total, 3) // 其余三道
})

// ── 页面只读没被破 ──────────────────────────────────────────────────────
test('🔴 新开 6 个口一个写口都没加：写端点恒 =1，且只能是 sale-state', async () => {
  const nf = await get('/api/kb/不存在的口')
  assert.equal(nf.status, 404)
  assert.equal(nf.body.端点合计, '17 读 + 1 写 = 18')
  const writes = nf.body.endpoints.filter((e) => e.includes('POST '))
  assert.equal(writes.length, 1)
  assert.match(writes[0], /\/api\/kb\/sale-state/)
  // 新口一律只认 GET
  for (const p of ['/api/kb/models', '/api/kb/criteria', '/api/kb/templates', '/api/kb/kg/aliases']) {
    const r = await fetch(`${BASE}${p}`, { method: 'POST', body: '{}' })
    assert.equal(r.status, 405, `🔴 ${p} 居然接受了 POST`)
  }
})
