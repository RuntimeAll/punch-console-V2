/**
 * kb 读 API · PRD-003 发布运营域端点自证（node 直跑：node console/server/kb-read-api-prd003.test.mjs）
 * ═══════════════════════════════════════════════════════════════════════
 * 覆盖四件事：
 *   ① GET /api/kb/materials（册/账号/启用/burned/在售态/关键词 六种过滤 + 启用版重复告警）
 *   ② GET /api/kb/artifacts/:id 补吐 sale_state / link / note 解析出的提取码（含冲突与查不到）
 *   ③ GET /api/kb/artifact-members 合刊关系（含断链如实标）
 *   ④ POST /api/kb/sale-state —— 🔴 全站唯一写端点
 *   ⑤ 审查三条实锤的反例闸（2026-08-19 补）：
 *      · LIKE 通配符注入：q=`_` / q=`%` 必须命中 0（转义前它俩等于"全表"）；
 *      · 端点账：自报必须是 9 读 + 1 写 = 10（曾自报 11）；
 *      · 缺 sale_state 列的库必须**拒启**（转义前是静默起来、4 个口齐 500）。
 *
 * 🔴 本测试的核心闸不是"接口能改状态"，而是**它只能改这一列**：
 *   每次 POST 前后整行快照逐列比对，除 sale_state 外任何一列变了就红；
 *   连全库各表行数也一起比对（防"顺手插一条 log"这种偷渡）。
 *
 * 🔴 库：临时目录里按 工具箱/库/schema_kb.sql（结构 SSOT）现建一个空库再插假数据。
 *   不拷、不连 知识库/kb.db，也不碰 资料库.db——测试永远不该有机会写到真库上。
 *   （用 SSOT 的 DDL 现建而不是拷副本，顺带把"DDL 改了 API 没跟上"也测掉。）
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
// 本机有代理：fetch 走环境代理会打不到 127.0.0.1（同 CLAUDE.md §5 curl --noproxy 那条坑）
for (const k of ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy']) delete process.env[k]
process.env.NO_PROXY = '*'

const HERE = dirname(fileURLToPath(import.meta.url))
const API = join(HERE, 'kb-read-api.mjs')
const SCHEMA = resolve(HERE, '..', '..', '工具箱', '库', 'schema_kb.sql')
const PORT = Number(process.env.KB_API_TEST_PORT || 4311)
const BASE = `http://127.0.0.1:${PORT}`

let tmp = ''
let dbPath = ''
let child = null
let banner = '' // 起服务横幅原文（端点账自报准不准，看它）

const get = async (p) => {
  const r = await fetch(`${BASE}${p}`)
  return { status: r.status, body: await r.json() }
}
const send = async (p, body, method = 'POST') => {
  const r = await fetch(`${BASE}${p}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  })
  return { status: r.status, body: await r.json() }
}

/** 全库快照：每表行数 + artifact 全表整行——写端点越界的照妖镜 */
function snapshot() {
  const db = new DatabaseSync(dbPath, { readOnly: true })
  try {
    const counts = {}
    for (const t of db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
      .all()) {
      counts[t.name] = db.prepare(`SELECT COUNT(*) AS c FROM "${t.name}"`).get().c
    }
    const artifacts = db.prepare('SELECT * FROM artifact ORDER BY id').all()
    return { counts, artifacts }
  } finally {
    db.close()
  }
}

/** 除 sale_state 外一列都不许动；表行数一行都不许变 */
function assertOnlySaleStateChanged(before_, after_, changedIds) {
  assert.deepEqual(after_.counts, before_.counts, '🔴 写端点改动了表行数（越界）')
  assert.equal(after_.artifacts.length, before_.artifacts.length, '🔴 artifact 行数变了')
  for (let i = 0; i < before_.artifacts.length; i++) {
    const b = before_.artifacts[i]
    const a = after_.artifacts[i]
    for (const k of Object.keys(b)) {
      if (k === 'sale_state') continue
      assert.deepEqual(a[k], b[k], `🔴 写端点越界改了 artifact.${k}（id=${b.id}）`)
    }
    if (!changedIds.includes(b.id)) {
      assert.deepEqual(a.sale_state, b.sale_state, `🔴 改了不该改的册 ${b.id} 的 sale_state`)
    }
  }
}

before(async () => {
  tmp = mkdtempSync(join(tmpdir(), 'kbapi-prd003-'))
  dbPath = join(tmp, 'kb.db')
  // 🔴 建假数据这把句柄**关掉外键**：下面要故意插一条指向不存在册的合刊成员，
  //   用来验证读 API 会把断链标出来。这不是编造场景——桥脚本是 python（sqlite3 默认 FK OFF），
  //   坏账真能落进库，读侧必须认得出来。node:sqlite 默认是 FK ON，所以这里显式关。
  const db = new DatabaseSync(dbPath, { enableForeignKeyConstraints: false })
  db.exec(readFileSync(SCHEMA, 'utf8'))
  // schema_kb.sql 里 sale_state 那条 ALTER 是注释掉的（ALTER 非幂等，正式走 apply_ddl_263.py）——
  // 这里照它的 pragma 探测法补一次，口径与 apply_ddl_263.py 一致。
  const hasSale = db.prepare('PRAGMA table_info(artifact)').all().some((c) => c.name === 'sale_state')
  if (!hasSale) {
    db.exec("ALTER TABLE artifact ADD COLUMN sale_state TEXT CHECK(sale_state IN ('在售','待整理','停售'))")
  }

  const art = db.prepare(
    'INSERT INTO artifact (id,name,kind,status,link,note,created_at,sale_state) VALUES (?,?,?,?,?,?,?,?)',
  )
  // A1：note 是 JSON 宣发字段（吃库桥的正常形态），link 带 pwd，两者一致
  art.run('art-1', '七上代数式的值打卡', '打卡册', '已上架',
    'https://pan.baidu.com/s/126100-2_46dwPmB8z5whKA?pwd=ss7s',
    JSON.stringify({ 提取码: 'ss7s', 版本名: '正册', 组名: '七上代数式的值打卡' }), '2026-08-18 01:00:00', '在售')
  // A2：note 是纯文本（老账手写形态），link 不带 pwd ⇒ 只能从文本里解析
  art.run('art-2', '七上实数的运算打卡', '打卡册', '已交付',
    'https://pan.baidu.com/s/1WR028Bva17NDBfNt6_dEkw', '网盘已传，提取码：fu6a', '2026-08-18 01:01:00', null)
  // A3：合刊（parent）
  art.run('art-3', '七上计算合刊', '打卡册', '在产', null, null, '2026-08-18 01:02:00', '待整理')
  // A4：note 与 link 的提取码**打架** ⇒ 必须报 conflict，不许挑一个显示
  art.run('art-4', '五上同步小纸条', '打卡册', '已上架',
    'https://pan.baidu.com/s/1aaaaaaaaaaaaaaaaaaaa?pwd=aaaa', JSON.stringify({ 提取码: 'bbbb' }),
    '2026-08-18 01:03:00', '停售')
  // A5：无 link 无 note ⇒ 提取码必须是 null（不许瞎猜）
  art.run('art-5', '三上混合运算特训', '专项卷', '在产', null, null, '2026-08-18 01:04:00', null)

  const mem = db.prepare('INSERT INTO artifact_member (parent_id,member_id,ord) VALUES (?,?,?)')
  mem.run('art-3', 'art-1', 1)
  mem.run('art-3', 'art-2', 2)
  mem.run('art-3', 'art-不存在', 3) // 🔴 断链：必须被标出来而不是当"没有这个成员"

  const mat = db.prepare(
    `INSERT INTO material (id,artifact_id,account,is_active,title,body,topics_json,style_seed,
                           burned,product_desc,pan_share_text,created_at)
     VALUES (?,?,?,?,?,?,?,?,?,?,?,?)`,
  )
  mat.run('m-1', 'art-1', 'A', 1, '七年级上册 | 代数式的值五天打卡 ✅', '求值五法每天一页练透。',
    JSON.stringify(['初一数学', '七年级上册', '代数式']), null, 0, '5 天 25 题 PDF', '链接：…?pwd=ss7s', '2026-08-18 01:06:18')
  mat.run('m-2', 'art-1', 'B', 1, '初一代数式求值，五种套路一次讲清', '整体法、赋值法…', JSON.stringify(['初中数学']),
    'seed-b', 1, null, null, '2026-08-18 01:06:19') // burned=1：已发过
  mat.run('m-3', 'art-1', 'A', 0, '（旧版）代数式的值打卡', '旧文案', '[]', null, 0, null, null, '2026-08-17 09:00:00')
  mat.run('m-4', 'art-2', 'A', 1, '初一实数计算总错？问题都出在符号上', '最常见的五个坑…',
    JSON.stringify(['实数', '平方根']), null, 0, null, '通过百度网盘分享的文件…', '2026-08-18 01:07:00')
  // art-4 上故意放两条 A 号启用版 ⇒ 启用版唯一闸的读侧告警必须点亮
  mat.run('m-5', 'art-4', 'A', 1, '小纸条 A 号文案一', '正文一', '[]', null, 0, null, null, '2026-08-18 01:08:00')
  mat.run('m-6', 'art-4', 'A', 1, '小纸条 A 号文案二', '正文二', '[]', null, 0, null, null, '2026-08-18 01:09:00')

  db.prepare('INSERT INTO publish_log (id,material_id,published_on,result,note) VALUES (?,?,?,?,?)')
    .run(1, 'm-2', '2026-08-18', '已发', '人工发的')

  // 🔴 三个考点：给 resolveKp 的「考点名模糊」那一档（全文件唯一另一处吃用户输入的 LIKE）当靶子。
  //   考点名与物料 title/body/册名一样**刻意都不含 % 与 _**——这样 kp=% / kp=_ / q=% / q=_
  //   的正确答案恒为「一条都不该中」，通配符一旦生效就立刻红。
  const kp = db.prepare('INSERT INTO kp (id,name,parent_id,level,ord,status) VALUES (?,?,?,?,?,?)')
  kp.run('kp-root', '人教版', null, '版本', 1, '现行')
  kp.run('kp-1', '有理数的乘方', 'kp-root', '考点', 1, '现行')
  kp.run('kp-2', '整式的加减', 'kp-root', '考点', 2, '现行')
  db.close()

  child = spawn(process.execPath, [API], {
    env: { ...process.env, KB_DB: dbPath, KB_API_PORT: String(PORT) },
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
    child.on('exit', (c) => bad(new Error(`API 进程退出 code=${c}`)))
  })
})

after(() => {
  child?.kill()
  try {
    rmSync(tmp, { recursive: true, force: true })
  } catch {
    /* Windows 上偶尔占用，删不掉就留给系统清 */
  }
})

// ── ① 物料清单 ─────────────────────────────────────────────────────────
test('materials 全量：条数/账号分布/burned 计数/正文全出', async () => {
  const { status, body } = await get('/api/kb/materials')
  assert.equal(status, 200)
  assert.equal(body.total, 6)
  assert.deepEqual(body.account_total, { A: 5, B: 1 })
  assert.equal(body.burned_total, 1)
  const m1 = body.rows.find((r) => r.id === 'm-1')
  assert.equal(m1.artifact_name, '七上代数式的值打卡')
  assert.equal(m1.artifact_sale_state, '在售')
  assert.equal(m1.is_active, true)
  assert.equal(m1.burned, false)
  assert.deepEqual(m1.topics, ['初一数学', '七年级上册', '代数式'])
  assert.equal(m1.body, '求值五法每天一页练透。') // 一键复制要全文，不许截断
  assert.equal(m1.pan_code.code, 'ss7s')
  const m2 = body.rows.find((r) => r.id === 'm-2')
  assert.equal(m2.burned, true)
  assert.equal(m2.publish_count, 1)
  assert.equal(m2.last_published_on, '2026-08-18')
})

test('materials 启用版重复=读侧告警点亮（art-4 的 A 号有两条 is_active=1）', async () => {
  const { body } = await get('/api/kb/materials')
  assert.equal(body.active_dup.length, 1)
  assert.equal(body.active_dup[0].artifact_id, 'art-4')
  assert.equal(body.active_dup[0].account, 'A')
  assert.equal(body.active_dup[0].active_count, 2)
})

test('materials 按册过滤 + 册头带提取码', async () => {
  const { body } = await get('/api/kb/materials?artifact_id=art-1')
  assert.equal(body.total, 3)
  assert.equal(body.artifact.name, '七上代数式的值打卡')
  assert.equal(body.artifact.sale_state, '在售')
  assert.equal(body.artifact.pan_code.code, 'ss7s')
  assert.equal(body.artifact_unresolved, null)
  assert.ok(body.rows.every((r) => r.artifact_id === 'art-1'))
})

test('materials 册 id 库里没有 ⇒ 0 条 + 原样回 artifact_unresolved（不静默当全部）', async () => {
  const { body } = await get('/api/kb/materials?artifact_id=art-查无此册')
  assert.equal(body.total, 0)
  assert.equal(body.artifact, null)
  assert.equal(body.artifact_unresolved, 'art-查无此册')
})

test('materials 账号过滤：B 号只出 B；账号写错 ⇒ 0 条 + account_unknown', async () => {
  const b = await get('/api/kb/materials?account=B')
  assert.equal(b.body.total, 1)
  assert.equal(b.body.rows[0].account, 'B')
  const both = await get('/api/kb/materials?account=A&account=B')
  assert.equal(both.body.total, 6)
  const bad = await get('/api/kb/materials?account=C')
  assert.equal(bad.body.total, 0)
  assert.deepEqual(bad.body.account_unknown, ['C'])
})

test('materials burned / active 过滤', async () => {
  const burned = await get('/api/kb/materials?burned=1')
  assert.equal(burned.body.total, 1)
  assert.equal(burned.body.rows[0].id, 'm-2')
  const off = await get('/api/kb/materials?active=0')
  assert.equal(off.body.total, 1)
  assert.equal(off.body.rows[0].id, 'm-3')
})

test('materials 在售态筛选：按册的人工列过滤，「未标」查得到 sale_state 为空的册', async () => {
  const on = await get('/api/kb/materials?sale_state=在售')
  assert.equal(on.body.total, 3) // art-1 的三条
  assert.ok(on.body.rows.every((r) => r.artifact_sale_state === '在售'))
  const none = await get('/api/kb/materials?sale_state=未标')
  assert.equal(none.body.total, 1) // art-2 的 m-4
  assert.equal(none.body.rows[0].id, 'm-4')
  const mix = await get('/api/kb/materials?sale_state=在售&sale_state=停售')
  assert.equal(mix.body.total, 5)
  const bad = await get('/api/kb/materials?sale_state=卖光了')
  assert.equal(bad.body.total, 0)
  assert.deepEqual(bad.body.sale_state_unknown, ['卖光了'])
})

test('materials 关键词命中标题/正文/册名', async () => {
  const { body } = await get(`/api/kb/materials?q=${encodeURIComponent('符号')}`)
  assert.equal(body.total, 1)
  assert.equal(body.rows[0].id, 'm-4')
})

// ── ② 册详情补吐 ───────────────────────────────────────────────────────
test('artifact 详情：sale_state / link / note JSON 解析出提取码', async () => {
  const { body } = await get('/api/kb/artifacts/art-1')
  assert.equal(body.sale_state, '在售')
  assert.match(body.link, /^https:\/\/pan\.baidu\.com\//)
  assert.equal(body.pan_code.code, 'ss7s')
  assert.equal(body.pan_code.source, 'note.提取码')
  assert.equal(body.pan_code.conflict, false)
  assert.equal(body.note_obj.版本名, '正册')
  assert.deepEqual(body.member_of.map((p) => p.id), ['art-3'])
  assert.deepEqual(
    body.material_stat,
    [{ account: 'A', total: 2, active: 1, burned: 0 }, { account: 'B', total: 1, active: 1, burned: 1 }],
  )
})

test('artifact 详情：note 是纯文本时也解析得出提取码，来源如实标', async () => {
  const { body } = await get('/api/kb/artifacts/art-2')
  assert.equal(body.sale_state, null)
  assert.equal(body.pan_code.code, 'fu6a')
  assert.equal(body.pan_code.source, 'note 文本')
  assert.equal(body.note_obj._text, '网盘已传，提取码：fu6a')
})

test('artifact 详情：note 与 link 提取码打架 ⇒ conflict=true 且两个都端出去', async () => {
  const { body } = await get('/api/kb/artifacts/art-4')
  assert.equal(body.pan_code.conflict, true)
  assert.deepEqual(body.pan_code.candidates.map((c) => c.code).sort(), ['aaaa', 'bbbb'])
})

test('artifact 详情：没链接没备注 ⇒ 提取码 null（绝不瞎猜四位）', async () => {
  const { body } = await get('/api/kb/artifacts/art-5')
  assert.equal(body.pan_code.code, null)
  assert.equal(body.pan_code.source, null)
  assert.deepEqual(body.pan_code.candidates, [])
  assert.equal(body.note_obj, null)
})

test('artifact 详情：合刊册列出成员，断链成员标 missing', async () => {
  const { body } = await get('/api/kb/artifacts/art-3')
  assert.equal(body.members.length, 3)
  assert.deepEqual(body.members.map((m) => m.id), ['art-1', 'art-2', 'art-不存在'])
  assert.equal(body.members[2].missing, true)
  assert.equal(body.members[0].missing, false)
  assert.equal(body.members[0].sale_state, '在售')
})

test('artifact 列表：带 sale_state / 提取码 / 物料数 / 成员数', async () => {
  const { body } = await get('/api/kb/artifacts')
  assert.equal(body.total, 5)
  const a1 = body.rows.find((r) => r.id === 'art-1')
  assert.equal(a1.sale_state, '在售')
  assert.equal(a1.material_count, 3)
  assert.equal(a1.pan_code.code, 'ss7s')
  const a3 = body.rows.find((r) => r.id === 'art-3')
  assert.equal(a3.member_count, 3)
})

// ── ③ 合刊关系 ─────────────────────────────────────────────────────────
test('artifact-members 全量：按合刊归组，断链计数如实', async () => {
  const { status, body } = await get('/api/kb/artifact-members')
  assert.equal(status, 200)
  assert.equal(body.pair_total, 3)
  assert.equal(body.parent_total, 1)
  assert.equal(body.broken_total, 1)
  assert.equal(body.rows[0].parent_id, 'art-3')
  assert.equal(body.rows[0].parent_sale_state, '待整理')
  assert.deepEqual(body.rows[0].members.map((m) => m.ord), [1, 2, 3])
})

test('artifact-members 按 parent_id / member_id 过滤', async () => {
  const p = await get('/api/kb/artifact-members?parent_id=art-3')
  assert.equal(p.body.pair_total, 3)
  const m = await get('/api/kb/artifact-members?member_id=art-1')
  assert.equal(m.body.pair_total, 1)
  assert.equal(m.body.rows[0].parent_id, 'art-3')
  const none = await get('/api/kb/artifact-members?parent_id=art-5')
  assert.equal(none.body.pair_total, 0)
  assert.deepEqual(none.body.rows, [])
})

// ── ④ 唯一写端点 ───────────────────────────────────────────────────────
test('sale-state 置值：只改 sale_state 一列，别的列与全库行数纹丝不动', async () => {
  const b0 = snapshot()
  const { status, body } = await send('/api/kb/sale-state', { id: 'art-2', sale_state: '在售' })
  assert.equal(status, 200)
  assert.deepEqual(body, { ok: true, id: 'art-2', name: '七上实数的运算打卡', from: null, to: '在售' })
  const b1 = snapshot()
  assertOnlySaleStateChanged(b0, b1, ['art-2'])
  assert.equal(b1.artifacts.find((a) => a.id === 'art-2').sale_state, '在售')
  const back = await get('/api/kb/artifacts/art-2')
  assert.equal(back.body.sale_state, '在售')
})

test('sale-state 清空：null 回到未标', async () => {
  const b0 = snapshot()
  const { status, body } = await send('/api/kb/sale-state', { id: 'art-2', sale_state: null })
  assert.equal(status, 200)
  assert.equal(body.to, null)
  assert.equal(body.from, '在售')
  assertOnlySaleStateChanged(b0, snapshot(), ['art-2'])
})

test('sale-state 夹带别的字段 ⇒ 一个字都写不进去', async () => {
  const b0 = snapshot()
  const { status } = await send('/api/kb/sale-state', {
    id: 'art-1',
    sale_state: '停售',
    status: '在产', // 生产态：产线的列，页面碰不得
    name: '被改掉的名字',
    link: 'https://坏人.example/x',
    note: '{"提取码":"9999"}',
  })
  assert.equal(status, 200)
  assertOnlySaleStateChanged(b0, snapshot(), ['art-1'])
  // 复位，免得影响后面的用例
  await send('/api/kb/sale-state', { id: 'art-1', sale_state: '在售' })
})

test('sale-state 值域外 / 缺字段 / 数字 id / 查无此册 ⇒ 全部拒收且零改动', async () => {
  const b0 = snapshot()
  const bad = await send('/api/kb/sale-state', { id: 'art-1', sale_state: '已卖光' })
  assert.equal(bad.status, 400)
  assert.equal(bad.body.ok, false)
  const miss = await send('/api/kb/sale-state', { id: 'art-1' })
  assert.equal(miss.status, 400)
  // 🔴 id 全链路字符串：数字 id 是老区/punch-console 的习惯，这里必须报错而不是 Number 一下
  const numId = await send('/api/kb/sale-state', { id: 1, sale_state: '在售' })
  assert.equal(numId.status, 400)
  assert.match(numId.body.error, /字符串/)
  const nf = await send('/api/kb/sale-state', { id: 'art-查无此册', sale_state: '在售' })
  assert.equal(nf.status, 404)
  const junk = await send('/api/kb/sale-state', '这不是 JSON')
  assert.equal(junk.status, 400)
  // 超大体：先回 413 再断连，绝不让调用方干等
  const huge = await send('/api/kb/sale-state', { id: 'art-1', sale_state: '在售', 垃圾: 'x'.repeat(70 * 1024) })
  assert.equal(huge.status, 413)
  assertOnlySaleStateChanged(b0, snapshot(), [])
})

test('页面只读复查：除 sale-state 外任何写法一律 405', async () => {
  const b0 = snapshot()
  const p1 = await send('/api/kb/artifacts', { id: 'art-1' })
  assert.equal(p1.status, 405)
  assert.deepEqual(p1.body.写端点, ['POST /api/kb/sale-state'])
  const p2 = await send('/api/kb/questions/q-1', { status: '上架' })
  assert.equal(p2.status, 405)
  const p3 = await send('/api/kb/sale-state', { id: 'art-1', sale_state: '停售' }, 'PUT')
  assert.equal(p3.status, 405)
  const p4 = await send('/api/kb/materials', { id: 'm-1', burned: 1 })
  assert.equal(p4.status, 405)
  assertOnlySaleStateChanged(b0, snapshot(), [])
})

// ── ⑤-1 LIKE 通配符注入反例闸 ───────────────────────────────────────────
test('materials 关键词：% 与 _ 只当字面量，命中 0（转义前它俩=全表）', async () => {
  // 沙盘六条物料的 title/body 与五本册的 name 都不含 % 和 _，正确答案恒为 0 条。
  // 🔴 未转义时：q=% ⇒ LIKE '%%%' 命中 6 条；q=_ ⇒ LIKE '%_%' 命中所有非空文案 6 条。
  const pct = await get('/api/kb/materials?q=%25')
  assert.equal(pct.status, 200)
  assert.equal(pct.body.total, 0, '🔴 q=% 被当成通配符了（LIKE 注入）')
  assert.deepEqual(pct.body.rows, [])
  assert.equal(pct.body.filters.q, '%')

  const und = await get(`/api/kb/materials?q=${encodeURIComponent('_')}`)
  assert.equal(und.body.total, 0, '🔴 q=_ 被当成"任意一个字符"了（LIKE 注入）')

  // 转义符自己也要被转义，否则 q=\ 会把后面的字符吃掉
  const bs = await get(`/api/kb/materials?q=${encodeURIComponent('\\')}`)
  assert.equal(bs.body.total, 0)
  const bsPct = await get(`/api/kb/materials?q=${encodeURIComponent('\\%')}`)
  assert.equal(bsPct.body.total, 0)

  // 转义没把正常关键词一起废掉（正向不回归）
  const ok = await get(`/api/kb/materials?q=${encodeURIComponent('符号')}`)
  assert.equal(ok.body.total, 1)
  assert.equal(ok.body.rows[0].id, 'm-4')
  const byName = await get(`/api/kb/materials?q=${encodeURIComponent('实数')}`)
  assert.equal(byName.body.total, 1) // 命中册名「七上实数的运算打卡」
})

test('考点模糊 resolve：% 与 _ 只当字面量，一律 unresolved（转义前会"模糊"到随便哪个考点）', async () => {
  for (const w of ['%', '_']) {
    const { body } = await get(`/api/kb/questions?kp=${encodeURIComponent(w)}`)
    assert.equal(body.kp_filter, null, `🔴 kp=${w} 被当成通配符，模糊到了考点上`)
    assert.equal(body.kp_unresolved, w) // 查不到就照实说，不许当"全部"
    assert.equal(body.total, 0)
  }
  // 半截通配也不许生效：库里没有哪个考点名字面上带「乘方%」，所以必须 unresolved
  // （未转义时 `%乘方%%` 会命中「有理数的乘方」）
  const half = await get(`/api/kb/questions?kp=${encodeURIComponent('乘方%')}`)
  assert.equal(half.body.kp_filter, null, '🔴 半截通配 `乘方%` 仍被当成通配符')
  assert.equal(half.body.kp_unresolved, '乘方%')

  // 正向不回归（防"转过头"把整档模糊废掉）：普通词仍走得通「考点名模糊」这一档
  const hit = await get(`/api/kb/questions?kp=${encodeURIComponent('乘方')}`)
  assert.equal(hit.body.kp_filter.id, 'kp-1')
  assert.equal(hit.body.kp_filter.matched_by, '考点名模糊')
  assert.equal(hit.body.kp_unresolved, null)
  const root = await get(`/api/kb/questions?kp=${encodeURIComponent('人教')}`)
  assert.equal(root.body.kp_filter.id, 'kp-root')
})

// ── ⑤-2 端点账反例闸 ────────────────────────────────────────────────────
test('端点账自报准数：9 读 + 1 写 = 10（曾自报 11 的反例闸）', async () => {
  const nf = await get('/api/kb/不存在的口')
  assert.equal(nf.status, 404)
  assert.equal(nf.body.端点合计, '9 读 + 1 写 = 10')
  assert.equal(nf.body.endpoints.length, 10, '🔴 清单条数与自报数对不上')
  assert.equal(nf.body.endpoints.filter((e) => e.startsWith('GET ')).length, 9)
  assert.equal(nf.body.endpoints.filter((e) => e.includes('POST ')).length, 1)
  // 启动横幅也得报同一个数（横幅是人眼唯一看得见的自报口）
  assert.match(banner, /端点 9 读 \+ 1 写 = 10/)
})

// ── ⑤-3 缺 sale_state 列 ⇒ 拒启 ────────────────────────────────────────
test('缺 sale_state 列的库 ⇒ 服务拒启并给出修法（不许静默起来等 4 个口 500）', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'kbapi-nosale-'))
  const badDb = join(dir, 'kb.db')
  const d = new DatabaseSync(badDb)
  // 模拟「没跑过 263 号 DDL 的老库」：artifact 表在，就是没有 sale_state 这一列
  d.exec("CREATE TABLE artifact (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT, status TEXT)")
  d.close()

  const r = await new Promise((ok) => {
    const c = spawn(process.execPath, [API], {
      env: { ...process.env, KB_DB: badDb, KB_API_PORT: String(PORT + 1) },
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let out = ''
    let err = ''
    let done = false
    const t = setTimeout(() => {
      if (done) return
      done = true
      c.kill()
      ok({ code: '起来了没退出', out, err })
    }, 8000)
    c.stdout.on('data', (x) => (out += x))
    c.stderr.on('data', (x) => (err += x))
    c.on('exit', (code) => {
      if (done) return
      done = true
      clearTimeout(t)
      ok({ code, out, err })
    })
  })

  assert.equal(r.code, 4, `🔴 缺列的库该以 4 号码拒启，实际 code=${r.code}；stderr=${r.err}`)
  assert.match(r.err, /sale_state/)
  assert.match(r.err, /apply_ddl_263\.py/) // 报错必须带修法，不能只说"错了"
  assert.ok(r.err.includes(badDb), '🔴 修法要点名是哪个库')
  assert.equal(r.out.trim(), '', '🔴 拒启就不该打出「服务已起」横幅')
  rmSync(dir, { recursive: true, force: true })
})

// ── 存量端点不回归 ──────────────────────────────────────────────────────
test('存量端点仍绿：stats / kg 树 / 题列表 / 404 端点清单已登记新口', async () => {
  const s = await get('/api/kb/stats')
  assert.equal(s.status, 200)
  assert.equal(s.body.readonly, true)
  assert.ok(s.body.rows.some((r) => r.table === 'material'))
  const t = await get('/api/kb/kg/tree')
  assert.equal(t.status, 200)
  const q = await get('/api/kb/questions')
  assert.equal(q.status, 200)
  assert.equal(q.body.total, 0)
  const nf = await get('/api/kb/不存在的口')
  assert.equal(nf.status, 404)
  const list = nf.body.endpoints.join('\n')
  assert.match(list, /\/api\/kb\/materials/)
  assert.match(list, /\/api\/kb\/artifact-members/)
  assert.match(list, /POST \/api\/kb\/sale-state/)
})
