/**
 * kb 读 API · PRD-007 二轮页面线自证（node --test console/server/kb-read-api-prd007b.test.mjs）
 * ═══════════════════════════════════════════════════════════════════════
 * 覆盖二轮新开的 2 个只读口 + 3 处端点增强：
 *   ① GET /api/kb/kg/patterns   讲义题型的下落：已锚/待归位两分 + 两份正本文件的一致闸
 *   ② GET /api/kb/papers        卷库列表：题数/满分/时长/所属册，断链如实标
 *   ③ GET /api/kb/papers/:id    逐题预览：stem 截断 + 考点挂靠
 *   ④ /api/kb/artifacts 增强：细类分流 + 人话名（三条来源）+ 退役标记
 *   ⑤ /api/kb/templates 增强：层（登记 vs id 回退）+ 引用链（**只画 params 里读得到的**）
 *
 * 🔴 本测试的四条核心闸：
 *   · **优雅回退真的能跑**：artifact 缺「细类」列时不 500，回 细类_available:false + 整列 null
 *     （回退分支写了不测 = 等于没写）；kg/patterns 的正本文件不在时同理。
 *   · **不许编关系**：两张共享同一 layout key 的**配方**之间**不得**互相画成「使用版式」——
 *     这是二轮实测抓到的真 bug，专门留一条闸钉死。
 *   · **不许拿 0 冒充"未记"**：满分没登记就回 null，绝不用逐题分值求和顶上。
 *   · **坏账要看得见**：卷指向已删的题 / 册、题型锚到不存在的叶、两份正本对不上，四种各插一条断言。
 *
 * 🔴 库：临时目录里按 工具箱/库/schema_kb.sql（结构 SSOT）现建空库再插假数据，
 *   不拷、不连 知识库/kb.db。端口 4316（避开主位 4310 与 prd003/prd007 测试的 4311/4313/4314）。
 */
import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve, relative } from 'node:path'
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
const V2_ROOT = resolve(HERE, '..', '..')
const SCHEMA = resolve(V2_ROOT, '工具箱', '库', 'schema_kb.sql')
const PORT = Number(process.env.KB_API_TEST_PORT || 4316)
const BASE = `http://127.0.0.1:${PORT}`

let tmp = ''
let dbPath = ''
let child = null
/** 题型锚定的两个假正本（相对 V2_ROOT，用 env 顶给服务） */
let mapRel = ''
let listRel = ''

const get = async (p) => {
  const r = await fetch(`${BASE}${p}`)
  return { status: r.status, body: await r.json() }
}

/** 起一个服务实例，跑完 fn 再收——回退分支的测试要换 env / 换库重起 */
async function withApi(env, port, fn) {
  const c = spawn(process.execPath, [API], {
    env: { ...process.env, KB_API_PORT: String(port), ...env },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  let out = ''
  c.stdout.on('data', (b) => (out += b))
  c.stderr.on('data', (b) => (out += b))
  try {
    for (let i = 0; i < 100; i++) {
      if (/端点 \d+ 读/.test(out) || /🔴/.test(out)) break
      await new Promise((r) => setTimeout(r, 60))
    }
    await fn(async (p) => {
      const r = await fetch(`http://127.0.0.1:${port}${p}`)
      return { status: r.status, body: await r.json() }
    }, out)
  } finally {
    c.kill()
    await new Promise((r) => setTimeout(r, 120))
  }
}

before(async () => {
  tmp = mkdtempSync(join(tmpdir(), 'kbapi-prd007b-'))
  dbPath = join(tmp, 'kb.db')
  // 🔴 关外键：下面要故意插「指向不存在的题 / 册 / 叶」的坏账，读侧必须认得出来
  const db = new DatabaseSync(dbPath, { enableForeignKeyConstraints: false })
  db.exec(readFileSync(SCHEMA, 'utf8'))
  // schema SSOT 已含 细类 与 status 的「退役」值域；旧库缺列那条路单独在下面用另一个库测
  const cols = db.prepare('PRAGMA table_info(artifact)').all().map((c) => c.name)
  assert.ok(cols.includes('细类'), '🔴 schema_kb.sql 里没有 artifact.细类——结构 SSOT 与本测试脱节了')

  // ── kp：两片叶（一片给题挂，一片给题型锚）────────────────────────────
  const kp = db.prepare('INSERT INTO kp (id,name,parent_id,level,ord,status,desc) VALUES (?,?,?,?,?,?,?)')
  kp.run('K0', '浙教版数学', null, '版本', 1, '现行', null)
  kp.run('K1', '有理数', 'K0', '单元', 1, '现行', null)
  kp.run('KA', '相反数', 'K1', '考点', 1, '现行', '考法：相反数的定义')
  kp.run('KB', '绝对值', 'K1', '考点', 2, '现行', null)

  // ── 题 ────────────────────────────────────────────────────────────────
  const blocks = (t) => JSON.stringify({ v: 2, rows: [{ cells: [{ type: 'text', md: t }] }] })
  const q = db.prepare(
    'INSERT INTO question (id,blocks_json,qtype_code,diff_code,source_kind,status,created_at) VALUES (?,?,?,?,?,?,?)',
  )
  q.run('q1', blocks('求 -2 的相反数是多少'), 'choice', 'D1', 'manual', '上架', '2026-08-20 01:00:00')
  q.run('q2', blocks('化简 |-3|'), 'fill', 'D2', 'manual', '上架', '2026-08-20 01:01:00')
  const qk = db.prepare('INSERT INTO question_kp (question_id,kp_id,is_primary) VALUES (?,?,?)')
  qk.run('q1', 'KA', 1)
  qk.run('q2', 'KB', 1)
  qk.run('q2', 'KA', 0) // 一题挂两叶

  // ── artifact：三种细类各一本 + 一本退役 + 一本 note 不是 JSON ───────────
  const art = db.prepare(
    'INSERT INTO artifact (id,name,kind,status,source_line,link,note,created_at,细类) VALUES (?,?,?,?,?,?,?,?,?)',
  )
  art.run('A_ZJ', '浙教出卷·U1·2', '专项卷', '已交付', '浙教出卷', null, null, '2026-08-20 02:00:00', '组卷册')
  art.run(
    'A_PUB',
    '浙教七上第1章3套单元卷（发布包）',
    '专项卷',
    '已交付',
    '发布',
    'https://pan.example/s/abc?pwd=1234',
    JSON.stringify({ 标题候选: ['1. 浙教版七上数学第1章有理数单元测试卷', '2. 备选标题'], 商品描述: 'x' }),
    '2026-08-20 02:01:00',
    '发布包',
  )
  art.run('A_OLD', '三升四每日一练', '打卡册', '已交付', 'punch', null, '纯文本备注', '2026-08-20 02:02:00', '历史册')
  art.run('A_DEAD', '平行卷·第一单元测试', '专项卷', '退役', '平行出卷', null,
    JSON.stringify({ 退役: '2026-08-20', 缘由: '被浙教出卷取代' }), '2026-08-20 02:03:00', '组卷册')
  // 🔴 发布包但 标题候选 是空数组 ⇒ 人话名必须老实退回 name，不去 note 里翻别的键凑
  art.run('A_PUB2', '空候选的发布包', '专项卷', '已交付', '发布', null, JSON.stringify({ 标题候选: [] }),
    '2026-08-20 02:04:00', '发布包')

  // ── paper：满分/时长两种登记态 + 一张挂到不存在的册 ─────────────────────
  const paper = db.prepare(
    'INSERT INTO paper (id,artifact_id,kind,title,ord,layout_json,status,created_at) VALUES (?,?,?,?,?,?,?,?)',
  )
  paper.run('P1', 'A_ZJ', '专项卷', '第1章 有理数 单元测试（二）', 1,
    JSON.stringify({ layout: 'exam_paper', full_score: 100, duration_min: 60, subtitle: '库内复刻', sections: [{ name: '一、选择题' }, { name: '二、填空题' }] }),
    '草稿', '2026-08-20 03:00:00')
  // 🔴 卷头没记满分/时长：必须回 null（不是 0），页面显示「未记」
  paper.run('P2', 'A_DEAD', '专项卷', '第一单元测试（旧）', 1, JSON.stringify({ layout: 'exam_paper' }),
    '草稿', '2026-08-20 03:01:00')
  // 🔴 所属册断链：artifact_id 指了一本不存在的册
  paper.run('P3', 'A_NOPE', '打卡天', '孤儿卷', 1, null, '定稿', '2026-08-20 03:02:00')

  const pi = db.prepare('INSERT INTO paper_item (paper_id,ord,question_id,section,score) VALUES (?,?,?,?,?)')
  pi.run('P1', 1, 'q1', '一、选择题', null) // score 全 NULL：与主位现状同构
  pi.run('P1', 2, 'q2', '二、填空题', null)
  // 🔴 题断链：卷里指着一道已不在库的题
  pi.run('P1', 3, 'q_gone', '二、填空题', null)
  pi.run('P2', 1, 'q1', null, 5) // 这张记了逐题分值 ⇒ score_sum=5

  // ── template：三层俱全 + 一张层没回填（走 id 约定）─────────────────────
  const tpl = db.prepare(
    'INSERT INTO template (id,name,purpose,book_kinds,params_json,pitfalls,version,status) VALUES (?,?,?,?,?,?,?,?)',
  )
  tpl.run('tpl-choice-v1', '选择题·标准列位', '选项列位', '试卷',
    JSON.stringify({ 层: '组件', slot: 'choice', opt_cols: '4|2|1' }), null, 'v1', '在用')
  tpl.run('tpl-exam-v1', 'A4真卷', '单元测试卷骨架', '专项卷',
    // 版式点名了组件（引用②的靶子）
    JSON.stringify({ 层: '版式', layout: 'exam_paper', 纸张: 'A4', 槽位: ['choice(沿用 tpl-choice-v1 的列位口径)', 'fill'] }),
    '坑：题号连号', 'v1', '在用')
  tpl.run('zj_u1_v1', '浙教U1配方', '第1章单元卷', '专项卷',
    JSON.stringify({ 层: '配方', layout: 'exam_paper', 满分: 100, 题量: 20 }), null, 'v1', '在用')
  // 🔴 同样 layout=exam_paper 的**第二张配方**：它与 zj_u1_v1 之间**不得**互相画成「使用版式」
  tpl.run('zj_u2_v1', '浙教U2配方', '第2章单元卷', '专项卷',
    JSON.stringify({ 层: '配方', layout: 'exam_paper', 满分: 120, 题量: 23 }), null, 'v1', '在用')
  // 🔴 层没回填：走 id 约定倒推成「配方」，且必须自报 层_待回填
  tpl.run('zj_mix_v1', '综合卷配方', '全章综合', '专项卷',
    JSON.stringify({ layout: 'exam_paper', 满分: 120 }), null, 'v1', '停用')
  // 🔴 层推不出来的：既不归层也不硬塞
  tpl.run('mystery-1', '来路不明', null, null, JSON.stringify({ 随便: 1 }), null, null, '在用')

  db.close()

  // ── 题型锚定的两个假正本：写进临时目录，用 env 顶给服务 ─────────────────
  const kgDir = join(tmp, 'fakekg')
  mkdirSync(kgDir, { recursive: true })
  const mapAbs = join(kgDir, 'map.json')
  const listAbs = join(kgDir, 'list.md')
  writeFileSync(
    mapAbs,
    JSON.stringify({
      讲1题型1: { 题型名: '正数和负数', kp_id: 'KA' },
      讲1题型2: { 题型名: '相反数的定义', kp_id: 'KA' },
      讲2题型1: { 题型名: '求绝对值', kp_id: 'KB' },
      // 🔴 锚到一片不存在的叶 = 断链坏账
      讲2题型9: { 题型名: '锚错了的题型', kp_id: 'K不存在' },
      // 待归位两条
      讲3题型3: { 题型名: '相反意义的量', kp_id: null },
      讲3题型4: { 题型名: '数轴上的分类讨论', kp_id: null },
    }),
    'utf8',
  )
  writeFileSync(
    listAbs,
    '# 待挂题型清单\n\n- [ ] 讲3题型3：相反意义的量\n- [x] 讲3题型4：数轴上的分类讨论\n',
    'utf8',
  )
  mapRel = relative(V2_ROOT, mapAbs)
  listRel = relative(V2_ROOT, listAbs)

  child = spawn(process.execPath, [API], {
    env: { ...process.env, KB_DB: dbPath, KB_API_PORT: String(PORT), KG_PATTERN_MAP: mapRel, KG_PATTERN_LIST: listRel },
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  let banner = ''
  child.stdout.on('data', (b) => (banner += b))
  child.stderr.on('data', (b) => (banner += b))
  for (let i = 0; i < 100; i++) {
    try {
      const r = await fetch(`${BASE}/api/kb/stats`)
      if (r.ok) break
    } catch {
      /* 还没起来 */
    }
    await new Promise((r) => setTimeout(r, 60))
  }
})

after(() => {
  child?.kill()
  try {
    rmSync(tmp, { recursive: true, force: true })
  } catch {
    /* 临时目录删不掉不影响判定 */
  }
})

// ── ① 题型下落 ──────────────────────────────────────────────────────────
test('kg/patterns：173 那笔账两分（已锚进 kp.desc / 待人工归位），锚到不存在的叶标断链', async () => {
  const { status, body } = await get('/api/kb/kg/patterns')
  assert.equal(status, 200)
  assert.equal(body.available, true)
  assert.equal(body.total, 6)
  assert.equal(body.anchored_total, 4)
  assert.equal(body.pending_total, 2)
  // 已锚的按叶归拢：KA 吃了两个题型
  const ka = body.anchored_by_leaf.find((g) => g.kp_id === 'KA')
  assert.equal(ka.题型.length, 2)
  assert.equal(ka.kp_name, '相反数')
  assert.equal(ka.kp_missing, false)
  // 🔴 锚到不存在的叶：如实标 missing，不静默丢
  const bad = body.anchored_by_leaf.find((g) => g.kp_id === 'K不存在')
  assert.equal(bad.kp_missing, true)
  assert.equal(bad.kp_name, null)
  // 库侧自证口径：对齐-003 后 question_pattern 应为 0 行
  assert.equal(body.pattern_rows, 0)
  assert.equal(body.leaf_total, 2)
  assert.equal(body.leaf_with_desc, 1)
})

test('kg/patterns：人工归位清单的勾选状态读得出，且与映射对得上（一致闸）', async () => {
  const { body } = await get('/api/kb/kg/patterns')
  assert.equal(body.checklist_total, 2)
  assert.equal(body.checklist_done, 1, '清单里勾了一条 [x]')
  assert.equal(body.一致, true)
  assert.deepEqual(body.只在json, [])
  assert.deepEqual(body.只在清单, [])
  const p3 = body.pending_rows.find((r) => r.key === '讲3题型4')
  assert.equal(p3.done, true)
  assert.equal(p3.讲, 3)
  assert.equal(body.pending_rows.find((r) => r.key === '讲3题型3').done, false)
})

test('🔴 kg/patterns：两份正本对不上 ⇒ 一致=false 且把差集端出去（不许挑一个显示）', async () => {
  const badList = join(tmp, 'fakekg', 'bad.md')
  // 清单少收一条、又多出一条映射里没有的
  writeFileSync(badList, '- [ ] 讲3题型3：相反意义的量\n- [ ] 讲9题型9：映射里根本没有的\n', 'utf8')
  await withApi(
    { KB_DB: dbPath, KG_PATTERN_MAP: mapRel, KG_PATTERN_LIST: relative(V2_ROOT, badList) },
    4317,
    async (g) => {
      const { body } = await g('/api/kb/kg/patterns')
      assert.equal(body.一致, false)
      assert.deepEqual(body.只在json, ['讲3题型4'], '映射里待归位、清单没收的')
      assert.deepEqual(body.只在清单, ['讲9题型9'], '清单里有、映射里没有的')
    },
  )
})

test('🔴 kg/patterns 优雅回退：正本文件不在 ⇒ available=false + 说清哪个文件，绝不编计数', async () => {
  await withApi(
    { KB_DB: dbPath, KG_PATTERN_MAP: '不存在的目录/没有这个文件.json', KG_PATTERN_LIST: listRel },
    4317,
    async (g) => {
      const { status, body } = await g('/api/kb/kg/patterns')
      assert.equal(status, 200, '回退不是错误，不该 500')
      assert.equal(body.available, false)
      assert.match(body.reason, /没有这个文件\.json/)
      assert.equal(body.total, undefined, '🔴 文件没读到就不许有 total')
      assert.equal(body.pending_total, undefined)
      // 库侧那几个数仍然给（它们不依赖文件）
      assert.equal(body.leaf_total, 2)
      assert.equal(body.pattern_rows, 0)
    },
  )
})

// ── ② 卷库列表 ──────────────────────────────────────────────────────────
test('papers：卷名/题数/满分/时长/所属册一屏；满分只认 layout.full_score', async () => {
  const { status, body } = await get('/api/kb/papers')
  assert.equal(status, 200)
  assert.equal(body.total, 3)
  assert.equal(body.item_total, 4)
  const p1 = body.rows.find((r) => r.id === 'P1')
  assert.equal(p1.item_count, 3)
  assert.equal(p1.full_score, 100)
  assert.equal(p1.duration_min, 60)
  assert.equal(p1.layout_key, 'exam_paper')
  assert.equal(p1.section_count, 2)
  assert.equal(p1.subtitle, '库内复刻')
  assert.equal(p1.artifact_name, '浙教出卷·U1·2')
  assert.equal(p1.artifact_细类, '组卷册')
  // 🔴 逐题分值全 NULL ⇒ score_sum 为 null，绝不变成 0
  assert.equal(p1.score_sum, null)
  // 🔴 卷头没记满分 ⇒ null（不是 0）
  const p2 = body.rows.find((r) => r.id === 'P2')
  assert.equal(p2.full_score, null)
  assert.equal(p2.duration_min, null)
  assert.equal(p2.score_sum, 5, '这张记了逐题分值，如实求和')
  // 登记率如实报
  assert.equal(body.with_full_score, 1)
  assert.equal(body.with_duration, 1)
})

test('🔴 papers：题断链与册断链两种坏账分别标出来，不静默按存活数报', async () => {
  const { body } = await get('/api/kb/papers')
  const p1 = body.rows.find((r) => r.id === 'P1')
  assert.equal(p1.missing_count, 1, '卷里有一道题已不在库')
  assert.equal(p1.item_count, 3, '题位数照实是 3，不缩水成 2')
  const p3 = body.rows.find((r) => r.id === 'P3')
  assert.equal(p3.artifact_missing, true, '所属册指了不存在的册')
  assert.equal(p3.artifact_name, null)
  assert.equal(p3.artifact_id, 'A_NOPE')
})

test('papers：按 kind / artifact_id 筛，筛不中就是 0 条不当「不过滤」', async () => {
  assert.equal((await get('/api/kb/papers?kind=%E6%89%93%E5%8D%A1%E5%A4%A9')).body.total, 1)
  assert.equal((await get('/api/kb/papers?artifact_id=A_ZJ')).body.total, 1)
  assert.equal((await get('/api/kb/papers?artifact_id=A_NOT_EXIST')).body.total, 0)
  assert.equal((await get('/api/kb/papers?status=%E5%AE%9A%E7%A8%BF')).body.total, 1)
  const stat = await get('/api/kb/papers?artifact_id=A_ZJ')
  // 分组统计走全表，不随筛选缩水
  assert.equal(stat.body.kind_stat.reduce((s, k) => s + k.count, 0), 3)
})

test('papers/:id：逐题预览带 stem 截断 + 考点挂靠 + 题型难度，断链行如实标', async () => {
  const { status, body } = await get('/api/kb/papers/P1')
  assert.equal(status, 200)
  assert.equal(body.item_count, 3)
  assert.equal(body.full_score, 100)
  assert.equal(body.artifact.细类, '组卷册')
  const it1 = body.items.find((i) => i.ord === 1)
  assert.match(it1.stem, /相反数/)
  assert.equal(it1.missing, false)
  assert.deepEqual(it1.kps.map((k) => k.name), ['相反数'])
  assert.equal(it1.kps[0].is_primary, true)
  // 一题挂两叶：主叶排前
  const it2 = body.items.find((i) => i.ord === 2)
  assert.equal(it2.kps.length, 2)
  assert.equal(it2.kps[0].name, '绝对值')
  assert.equal(it2.kps[0].is_primary, true)
  // 🔴 断链题：stem 说明白，不留空白行冒充正常题
  const it3 = body.items.find((i) => i.ord === 3)
  assert.equal(it3.missing, true)
  assert.match(it3.stem, /不在库/)
  assert.deepEqual(it3.kps, [])
})

test('papers/:id 查无此卷 ⇒ 404（不许回个空壳假装有）', async () => {
  assert.equal((await get('/api/kb/papers/P_NOPE')).status, 404)
})

test('🔴 stem 截断不留落单的 $：宁可少显示半句，也不摆一段渲不出来的生 LaTeX', async () => {
  // 靶子：第 120 字正好落在 $…$ 中间（截图实测抓到的真现象：列表里印出 `$174\leqslant x\leqs…`）
  const prefix = '仔细阅读下面题目后作答并把过程写清楚'.repeat(7).slice(0, 110) // 110 字，第 120 字必落进公式里
  const long = `${prefix}$\\frac{1}{2}+\\frac{3}{4}-\\frac{5}{6}$ 的值是多少`
  assert.ok(prefix.length === 110 && long.length > 130, '靶子构造得不对，这条测试就没在测截断')
  const d = new DatabaseSync(dbPath, { enableForeignKeyConstraints: false })
  d.prepare('INSERT INTO question (id,blocks_json,status,created_at) VALUES (?,?,?,?)').run(
    'q_math',
    JSON.stringify({ v: 2, rows: [{ cells: [{ type: 'text', md: long }] }] }),
    '上架',
    '2026-08-20 05:00:00',
  )
  d.prepare('INSERT INTO paper (id,artifact_id,kind,title,ord,status,created_at) VALUES (?,?,?,?,?,?,?)').run(
    'P_MATH', 'A_ZJ', '专项卷', '公式截断靶卷', 9, '草稿', '2026-08-20 05:00:00',
  )
  d.prepare('INSERT INTO paper_item (paper_id,ord,question_id) VALUES (?,?,?)').run('P_MATH', 1, 'q_math')
  d.close()

  const { body } = await get('/api/kb/papers/P_MATH')
  const stem = body.items[0].stem
  const dollars = (stem.match(/(?<!\\)\$/g) || []).length
  assert.equal(dollars % 2, 0, `🔴 截出了落单的 $，MathJax 会把生 LaTeX 原样印出来：${stem}`)
  assert.ok(!/\\frac\{1\}\{2\}$/.test(stem.replace('…', '')), '半截公式应当被退掉而不是留在尾巴上')
  assert.match(stem, /…$/, '截断标记仍要在，让人知道这里被截了')
})

// ── ③ 资料册细类 + 人话名 ────────────────────────────────────────────────
test('artifacts：三细类分流计数 + 退役标记', async () => {
  const { body } = await get('/api/kb/artifacts')
  assert.equal(body.细类_available, true)
  assert.deepEqual(body.细类_stat, { 组卷册: 2, 发布包: 2, 历史册: 1 })
  assert.equal(body.retired_total, 1)
  assert.equal(body.rows.find((r) => r.id === 'A_DEAD').retired, true)
  assert.equal(body.rows.find((r) => r.id === 'A_ZJ').retired, false)
})

test('artifacts 人话名：组卷册取卷面标题 / 发布包取标题候选[0] / 其余退回 name，来源随行', async () => {
  const { body } = await get('/api/kb/artifacts')
  const zj = body.rows.find((r) => r.id === 'A_ZJ')
  assert.equal(zj.display_name, '第1章 有理数 单元测试（二）')
  assert.equal(zj.display_from, 'paper.title（所属卷的卷面标题）')
  assert.equal(zj.code_name, '浙教出卷·U1·2', '内部代号留着当灰色副行')

  const pub = body.rows.find((r) => r.id === 'A_PUB')
  // 🔴 候选串前面的「1. 」是清单序号不是标题的一部分，剥掉
  assert.equal(pub.display_name, '浙教版七上数学第1章有理数单元测试卷')
  assert.equal(pub.display_from, 'note.标题候选[0]')

  const old = body.rows.find((r) => r.id === 'A_OLD')
  assert.equal(old.display_name, '三升四每日一练')
  assert.equal(old.display_from, 'artifact.name')
  assert.equal(old.code_name, null, '人话名就是 name 时不重复摆两行')

  // 🔴 发布包但候选是空数组 ⇒ 老实退回 name，不去 note 里翻别的键凑一个
  const pub2 = body.rows.find((r) => r.id === 'A_PUB2')
  assert.equal(pub2.display_name, '空候选的发布包')
  assert.equal(pub2.display_from, 'artifact.name')
})

test('artifacts/:id：详情同样带细类与人话名', async () => {
  const { body } = await get('/api/kb/artifacts/A_ZJ')
  assert.equal(body.细类, '组卷册')
  assert.equal(body.细类_available, true)
  assert.equal(body.display_name, '第1章 有理数 单元测试（二）')
  assert.equal(body.code_name, '浙教出卷·U1·2')
  assert.equal(body.retired, false)
  assert.equal((await get('/api/kb/artifacts/A_DEAD')).body.retired, true)
})

test('🔴 优雅回退：artifact 没有「细类」列时不 500，回 细类_available=false + 整列 null', async () => {
  // 另建一个库，把 细类 列拿掉（模拟没跑过那道 ALTER 的旧库 / worktree 沙盘）
  const oldDb = join(tmp, 'kb-nosub.db')
  const d = new DatabaseSync(oldDb, { enableForeignKeyConstraints: false })
  d.exec(readFileSync(SCHEMA, 'utf8'))
  d.exec('ALTER TABLE artifact DROP COLUMN 细类')
  d.prepare('INSERT INTO artifact (id,name,kind,status,created_at) VALUES (?,?,?,?,?)').run(
    'A1', '某册', '打卡册', '已交付', '2026-08-20 00:00:00',
  )
  assert.ok(
    !d.prepare('PRAGMA table_info(artifact)').all().some((c) => c.name === '细类'),
    '细类列没删掉，这条测试就没在测回退',
  )
  d.close()

  await withApi({ KB_DB: oldDb }, 4317, async (g) => {
    const list = await g('/api/kb/artifacts')
    assert.equal(list.status, 200, '🔴 缺列不许 500——整页白屏比少一列信息坏得多')
    assert.equal(list.body.细类_available, false)
    assert.equal(list.body.细类_stat, null, '缺列时不许给出一份编的分类计数')
    assert.equal(list.body.rows[0].细类, null)
    // 人话名退回 name（推不出细类就不去猜怎么起名）
    assert.equal(list.body.rows[0].display_name, '某册')
    assert.equal(list.body.rows[0].display_from, 'artifact.name')

    const det = await g('/api/kb/artifacts/A1')
    assert.equal(det.status, 200)
    assert.equal(det.body.细类, null)
    assert.equal(det.body.细类_available, false)
    // 卷库口也得活着（它同样 join artifact）
    assert.equal((await g('/api/kb/papers')).status, 200)
  })
})

// ── ④ 模版分层与引用链 ──────────────────────────────────────────────────
test('templates：层优先取 params.层；没回填才按 id 约定倒推并自报「层待回填」', async () => {
  const { body } = await get('/api/kb/templates')
  const by = Object.fromEntries(body.rows.map((t) => [t.id, t]))
  assert.equal(by['tpl-choice-v1'].层, '组件')
  assert.equal(by['tpl-choice-v1'].层_from, 'params.层')
  assert.equal(by['tpl-choice-v1'].层_待回填, false)
  assert.equal(by['tpl-exam-v1'].层, '版式')
  assert.equal(by['zj_u1_v1'].层, '配方')
  // 🔴 层没回填的：推成配方，但必须自报是推的
  assert.equal(by['zj_mix_v1'].层, '配方')
  assert.equal(by['zj_mix_v1'].层_from, 'id 约定回退')
  assert.equal(by['zj_mix_v1'].层_待回填, true)
  // 🔴 推不出来的不硬塞进某一层
  assert.equal(by['mystery-1'].层, null)
  assert.equal(by['mystery-1'].层_from, null)
  assert.deepEqual(body.层_stat, { 组件: 1, 版式: 1, 配方: 3 })
  assert.equal(body.层_未归, 1)
  assert.equal(body.层_待回填, 1)
})

test('🔴 templates 引用链：配方→版式、版式→组件；两张配方共享同一 layout key 也不得互相引用', async () => {
  const { body } = await get('/api/kb/templates')
  const by = Object.fromEntries(body.rows.map((t) => [t.id, t]))

  // 配方 → 它用的那张版式（且只有那一张）
  const u1 = by['zj_u1_v1'].refs
  assert.equal(u1.length, 1)
  assert.equal(u1[0].kind, '版式')
  assert.equal(u1[0].id, 'tpl-exam-v1')
  assert.match(u1[0].via, /params\.layout/)
  // 🔴 这是本次实测抓到的真 bug 的钉子：zj_u1 与 zj_u2 都写着 layout=exam_paper，
  //   不认层就会互相画成「使用版式」——两张都是配方，这关系是编的。
  assert.ok(!u1.some((r) => r.id === 'zj_u2_v1'), '🔴 配方之间不许互相画成「使用版式」')
  assert.ok(!by['zj_u2_v1'].refs.some((r) => r.id === 'zj_u1_v1'))
  assert.ok(!by['zj_mix_v1'].refs.some((r) => r.层 === '配方' || r.id.startsWith('zj_')))

  // 版式 → 它含的组件；且版式自己声明的 layout key 不算「引用别人」
  const exam = by['tpl-exam-v1'].refs
  assert.deepEqual(exam.map((r) => `${r.kind}:${r.id}`), ['组件:tpl-choice-v1'])
  assert.ok(!exam.some((r) => r.kind === '版式'), '🔴 版式自己的 layout key 是身份不是引用')

  // 组件是最底层：params 里没点名别人 ⇒ 引用未登记（空数组，页面照实说）
  assert.deepEqual(by['tpl-choice-v1'].refs, [])
  assert.deepEqual(by['mystery-1'].refs, [])
})

test('templates：按 status 筛时引用链不缩水（指向停用模版的引用不许凭空消失）', async () => {
  const { body } = await get('/api/kb/templates?status=%E5%9C%A8%E7%94%A8')
  assert.equal(body.shown, 5, '停用的 zj_mix_v1 被筛掉')
  assert.ok(!body.rows.some((t) => t.id === 'zj_mix_v1'))
  // 全表统计不随筛选缩水
  assert.equal(body.total, 6)
  // 在用的配方仍能指到版式
  assert.equal(body.rows.find((t) => t.id === 'zj_u1_v1').refs[0].id, 'tpl-exam-v1')
})

// ── ⑤ 页面只读没被破 ────────────────────────────────────────────────────
test('🔴 二轮 +2 读口一个写口都没加：写端点恒 =1，新口只认 GET', async () => {
  const nf = await get('/api/kb/不存在的口')
  assert.equal(nf.status, 404)
  assert.equal(nf.body.端点合计, '17 读 + 1 写 = 18')
  assert.equal(nf.body.endpoints.filter((e) => e.startsWith('GET ')).length, 17)
  const writes = nf.body.endpoints.filter((e) => e.includes('POST '))
  assert.equal(writes.length, 1)
  assert.match(writes[0], /\/api\/kb\/sale-state/)
  for (const p of ['/api/kb/papers', '/api/kb/kg/patterns']) {
    const r = await fetch(`${BASE}${p}`, { method: 'POST', body: '{}' })
    assert.equal(r.status, 405, `🔴 ${p} 居然接受了 POST`)
  }
})

test('路由顺序：/papers 列表口没被 /papers/:id 吃掉', async () => {
  const list = await get('/api/kb/papers')
  // 🔴 只验形状不写死条数：前面几条测试往库里插过卷，写死数字会让本条变成"谁先跑"的运气题
  assert.ok(Array.isArray(list.body.rows), '🔴 /api/kb/papers 回的必须是列表不是详情')
  assert.equal(list.body.rows.length, list.body.total)
  assert.ok(list.body.rows.some((r) => r.id === 'P1'))
  assert.equal(list.body.id, undefined, '列表口不该带详情的 id 字段')
  const detail = await get('/api/kb/papers/P1')
  assert.equal(detail.body.id, 'P1')
  assert.ok(Array.isArray(detail.body.items))
})
