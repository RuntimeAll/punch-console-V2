import { useMemo, useState } from 'react'
import { Badge, Card, Collapse, Empty, Space, Table, Tabs, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link, useSearchParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import type { IngestBatch, IngestItem, IngestLight, IngestSrcKind, IngestTemplate, ReviewLevel } from '@/mock'
import {
  autoPassRate, findIngestBatch, findIngestTemplate, ingestBatches, ingestTemplates,
  levelTotals, lightTotals, questions, ticketsOfBatch,
} from '@/mock'
import './style.css'

/**
 * 录入记录 /ingest
 * 归属：页面组「录入」。只改本目录，别动 layout / mock / components。
 *
 * 这页只回答一句话：**上一批录进来的到底是什么，拦下了什么**。
 * 🔴 录入记录不做生产：没有「重跑这批」「重新 OCR」「上传」这类按钮——跑管线是 agent 的事（kb:ingest），
 *   本页只把账摆出来，让人一眼看出哪批干净、哪批带病。
 * 🔴 灯色口径（正本在 mock/ingest.ts 顶部）：绿=直接进库可用 / 黄=进库但待转正 / 红=拦下隔离。
 *   页面不许自造第四种灯，也不许把黄灯说成「已完成」。
 * 🔴 counts 是题级且自洽（直收+排队人审+拒收=总数）；行级隔离（根本不成题的行）不计入 counts，
 *   只出现在闸报告里，它的去处是审核台的「隔离行」工单——本页给链接就够，不在这里做处理动作。
 *
 * 🔴🔴 第四轮按定稿补三样（正本 = 数据结构.md D-18 / D-21）：
 * ① 批次行挂 **srcKind 徽标**：文字层有守恒基准（图数/公式数/字符多重集可对账，人审只看报警）；
 *    图片源**没有守恒基准** ⇒ 置信度 + 双跑对照 + 人审必过，所以图片源一律配「等级+1」提示。
 * ② 展开的逐题清单挂 **reviewLevel 色阶徽标**（L0 直入 → 人工，绿蓝黄橙红五阶）：
 *    同一批里复杂度不同、等级也不同——等级是**逐题**的事，不是整批一刀切。
 * ③ 页头挂 **审核等级矩阵**（复杂度 × 源，D-21 原表 5 行）与 **入库执行阀五条**，
 *    都是折叠卡：平时不挡路，判等级判不准时点开对表。
 *
 * 交互：Tab 一分为二——「录入批次」（一行一批，点行展开看逐题灯 + 等级）与「录入模板」（版式方言库）。
 * 带 ?batch=<批次id> 进来自动展开那一批（审核台的工单卡就是这么链回来的）；?tab=templates 直落模板页。
 */

/** 灯色 → antd Badge 的状态点（小圆点，不铺色块） */
const LIGHT_STATUS: Record<IngestLight, 'success' | 'warning' | 'error'> = {
  绿: 'success',
  黄: 'warning',
  红: 'error',
}

/** 灯色 → 逐题清单里的人话（黄灯一律「待转正」，不许写成「已完成」） */
const LIGHT_WORD: Record<IngestLight, string> = {
  绿: '绿 · 进库可用',
  黄: '黄 · 待转正',
  红: '红 · 拦下隔离',
}

/**
 * 审核等级的色阶与人话（口径正本 = 数据结构.md D-21；审核台 /review 有一份同口径的副本，
 * 两页各在各自目录里放一份，不下沉公共件——纪律：页面组只改自己目录）。
 * 绿 → 蓝 → 黄 → 橙 → 红：看一眼颜色就知道这题要花多少人眼时间。
 */
const LEVEL_COLOR: Record<ReviewLevel, string> = {
  L0: 'green',
  L1: 'blue',
  L2: 'gold',
  L3: 'orange',
  人工: 'red',
}

const LEVEL_WORD: Record<ReviewLevel, string> = {
  L0: '直入',
  L1: '抽检',
  L2: '逐题速审',
  L3: '逐题细审',
  人工: '全程人来',
}

/** 等级徽标：色阶 + 人话一起出现才有信息量（光写 L2 没人记得住是什么） */
function LevelTag({ level }: { level: ReviewLevel }) {
  return (
    <Tag color={LEVEL_COLOR[level]} style={{ marginInlineEnd: 0 }}>
      {level === '人工' ? '人工' : level + ' · ' + LEVEL_WORD[level]}
    </Tag>
  )
}

/** 源类型说明（鼠标移上去看的那句）：两类源的闸口径完全不是一回事 */
const SRC_WHY: Record<IngestSrcKind, string> = {
  文字层:
    'docx / 文字型 PDF 确定性直读：有守恒基准（图数、公式数、字符多重集都能对上原件），闸能对账，人审只看报警。',
  图片OCR:
    '无文字层，走 MinerU 本地 OCR：🔴 没有守恒基准（不知道原件本该有几图几式），闸改成「置信度 + 双跑对照 + 人审必过」，批次默认不许直接过。',
}

/** 源徽标：图片源必须跟一句「等级+1」——这是 D-21 里最容易被忘掉的一条 */
function SrcKindTag({ kind }: { kind: IngestSrcKind }) {
  const isOcr = kind === '图片OCR'
  return (
    <Tooltip title={SRC_WHY[kind]}>
      <Space size={4}>
        <Tag color={isOcr ? 'orange' : undefined} style={{ marginInlineEnd: 0 }}>
          {kind}
        </Tag>
        {isOcr ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            等级+1
          </Typography.Text>
        ) : null}
      </Space>
    </Tooltip>
  )
}

/** 数字格：0 一律压成灰杠，让非 0 的数字自己跳出来 */
function Count({ value, color }: { value: number; color?: string }) {
  if (value === 0) return <Typography.Text type="secondary">—</Typography.Text>
  return <span style={{ color, fontWeight: 500 }}>{value}</span>
}

// ── 审核等级矩阵（数据结构.md D-21 原表，5 行照渲）─────────────────
type MatrixRow = { key: string; complexity: string; textLayer: ReviewLevel; photo: ReviewLevel }

const LEVEL_MATRIX: MatrixRow[] = [
  { key: 'm1', complexity: '纯文本', textLayer: 'L0', photo: 'L1' },
  { key: 'm2', complexity: '单张配图', textLayer: 'L1', photo: 'L2' },
  { key: 'm3', complexity: '两张以上图 或 表格', textLayer: 'L2', photo: 'L3' },
  { key: 'm4', complexity: '超长题+多图+跳页隔断', textLayer: 'L3', photo: '人工' },
  { key: 'm5', complexity: '手写稿', textLayer: '人工', photo: '人工' },
]

function LevelMatrix() {
  const columns: ColumnsType<MatrixRow> = [
    { title: '复杂度（Word/文字层源）', dataIndex: 'complexity', width: 260 },
    { title: '等级', key: 'textLayer', width: 150, render: (_, r) => <LevelTag level={r.textLayer} /> },
    { title: '拍照/扫描源', key: 'photo', width: 150, render: (_, r) => <LevelTag level={r.photo} /> },
  ]
  return (
    <div>
      <Table<MatrixRow>
        rowKey="key"
        size="small"
        columns={columns}
        dataSource={LEVEL_MATRIX}
        pagination={false}
        className="ig-matrix"
      />
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
        读法：左列是题的复杂度，中列是同复杂度在<b>文字层源</b>下的等级，右列是<b>拍照 / 扫描源</b>下的等级。
        🔴 拍照源整体<b>比文字层源高一级</b>（OCR 无守恒基准，天然多一分不确定）；<b>手写稿一律人工</b>。
        等级含义：L0＝闸全绿直入 ｜ L1＝抽检 ｜ L2＝逐题速审 ｜ L3＝逐题细审 ｜ 人工＝全程人来。
      </Typography.Paragraph>
    </div>
  )
}

// ── 入库执行阀（五条硬闸，全过才入）───────────────────────────────
type Valve = { no: string; name: string; quote: string; state: string; ok: boolean; now: string }

/** 五条阀的现况里带一个现算数字：库里主考点恰一的题数（阀⑤就是靠这个数字说话） */
function valves(): Valve[] {
  const total = questions.length
  const primaryOk = questions.filter((q) => q.kps.filter((k) => k.isPrimary).length === 1).length
  return [
    {
      no: '①',
      name: '置信度 ≥ 85%',
      quote: '低于即滞留待审，不许静默入。',
      state: '口径已定 · 字段待建',
      ok: false,
      now: 'demo 的批次账还没有 confidence 字段，图片源把「置信度 + 双跑对照」写进闸报告原话里（见 ib-004）——判法已经按这条走，数字化留给下一轮。',
    },
    {
      no: '②',
      name: '格式清晰（块流过校验器）',
      quote: '块型白名单 / 选项连续 / asset 存在 / GFM 表前后空行。',
      state: '已生效',
      ok: true,
      now: '全站渲题只有 BlockFlow 一个口径；图资产取不到时渲红框「图资产缺失」不静默留白——校验器的 asset 那一条在页面上看得见。',
    },
    {
      no: '③',
      name: '存取同构',
      quote: '存进库的格式＝直接使用的格式，同一份 blocks_json 展示 / 导出 / 交换直接吃，没有第二种存储形态、没有出库转换层。',
      state: '已生效',
      ok: true,
      now: '题面 / 答案 / 解析三份块流：录入记录、审核台、题目详情、打印样卷读的是同一份文档，页面一步转换都不做（所见＝所存＝所印）。',
    },
    {
      no: '④',
      name: '纯图片题面可入，但必须过审',
      quote: '——或用户明确说跳过审核才免。',
      state: '已生效',
      ok: true,
      now: 'ib-004 的图选项题 q-4013（四个选项各带一张图）就是这条闸的样子：进得来，但落黄灯 + L3 逐题细审，挂着图审工单等人核。',
    },
    {
      no: '⑤',
      name: '每题必挂考点（KG 叶子闸）',
      quote: '挂不上就不入库，绝不裸题入库。',
      state: '已生效',
      ok: true,
      now: '现算：库内 ' + total + ' 题，主考点恰一的 ' + primaryOk + '/' + total + '——没有裸题，也没有两个主考点打架的题。',
    },
  ]
}

function ValveList() {
  return (
    <div>
      {valves().map((v) => (
        <div className="ig-valve" key={v.no}>
          <div className="ig-valve-head">
            <span className="ig-valve-no">{v.no}</span>
            <span className="ig-valve-name">{v.name}</span>
            <Tag color={v.ok ? 'green' : 'gold'} style={{ marginInlineEnd: 0 }}>
              {v.state}
            </Tag>
          </div>
          <div className="ig-valve-quote">判据原话：{v.quote}</div>
          <div className="ig-valve-now">本页现况：{v.now}</div>
        </div>
      ))}
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
        五条是<b>与</b>的关系：全过才入库，任一条不过就滞留待审。🔴 阀不是页面上的按钮——阀在 agent 的管线里跑，
        本页只把「这一批到底过没过」摆出来。
      </Typography.Paragraph>
    </div>
  )
}

/** 展开区：闸报告全文 + 本批用的模板 + 逐题灯/等级清单 + 本批挂着的工单入口 */
function BatchDetail({ batch }: { batch: IngestBatch }) {
  const tickets = ticketsOfBatch(batch.id)
  const ticketByKind = tickets.reduce<Record<string, number>>((acc, t) => {
    acc[t.kind] = (acc[t.kind] ?? 0) + 1
    return acc
  }, {})
  const tpl = batch.templateId ? findIngestTemplate(batch.templateId) : undefined

  const columns: ColumnsType<IngestItem> = [
    {
      title: '序',
      dataIndex: 'seq',
      width: 52,
      render: (n: number) => <Typography.Text type="secondary">{n}</Typography.Text>,
    },
    {
      title: '灯',
      key: 'light',
      width: 118,
      render: (_, it) => <Badge status={LIGHT_STATUS[it.light]} text={LIGHT_WORD[it.light]} />,
    },
    {
      // 🔴 等级是逐题的：同一批里纯文本 L0、两图一表 L2，不许按批次一刀切
      title: '审核等级',
      key: 'level',
      width: 128,
      render: (_, it) => <LevelTag level={it.reviewLevel} />,
    },
    {
      title: '题面',
      dataIndex: 'title',
      ellipsis: { showTitle: true },
    },
    {
      title: '原因（非绿灯必写）',
      dataIndex: 'reason',
      width: 300,
      render: (r?: string) => (r ? r : <Typography.Text type="secondary">—</Typography.Text>),
    },
    {
      title: '去处',
      key: 'go',
      width: 168,
      render: (_, it) => (
        <Space size={8} wrap>
          {it.questionId ? (
            <Link to={`/questions/${it.questionId}`}>看题 {it.questionId}</Link>
          ) : (
            <Typography.Text type="secondary">未成题</Typography.Text>
          )}
          {/* 🔴 红灯的归宿是审核台的隔离行，不是在记录页上就地处理 */}
          {it.light === '红' ? <Link to="/review?tab=%E9%9A%94%E7%A6%BB%E8%A1%8C">去隔离行处置</Link> : null}
        </Space>
      ),
    },
  ]

  return (
    <div className="ig-expand">
      <div className="ig-gate">
        <div className="ig-gate-title">闸报告（原样，不截断）</div>
        <p className="ig-gate-text">{batch.gateSummary}</p>
      </div>

      {/* 这批按哪张录入模板切的：D-21 流程里「有相似 ⇒ 沿用既有切法」的落点 */}
      <div className="ig-tpl-line">
        {tpl ? (
          <>
            本批按录入模板切：<b>{tpl.name}</b>（{tpl.id}）—— {tpl.layoutTraits}
          </>
        ) : (
          <>
            本批<b>没有对得上的录入模板</b>，现切；同版式再来第二份，就该评估建一张模板（见「录入模板」页）。
          </>
        )}
      </div>

      <Table<IngestItem>
        rowKey="seq"
        size="small"
        columns={columns}
        dataSource={batch.items}
        pagination={false}
        rowClassName={(it) => (it.light === '红' ? 'ig-item-red' : it.light === '绿' ? 'ig-item-green' : '')}
      />

      {tickets.length > 0 ? (
        <div className="ig-tickets">
          本批还挂着 {tickets.length} 条审核工单：
          <Space size={10} style={{ marginInlineStart: 6 }}>
            {Object.entries(ticketByKind).map(([kind, n]) => (
              <Link key={kind} to={`/review?tab=${encodeURIComponent(kind)}`}>
                {kind} {n}
              </Link>
            ))}
          </Space>
        </div>
      ) : null}
    </div>
  )
}

// ── 录入模板库（D-21 ingest_template）─────────────────────────────
function TemplateCard({ tpl }: { tpl: IngestTemplate }) {
  // 这张模板切过哪几批：用过才知道它真认得出版式，没上过真卷子的模板不算验过
  const used = ingestBatches.filter((b) => b.templateId === tpl.id)
  return (
    <Card
      size="small"
      className="ig-tpl-card"
      title={
        <Space size={8} wrap>
          <span style={{ fontWeight: 500 }}>{tpl.name}</span>
          <Tag color={tpl.status === '在用' ? 'green' : undefined} style={{ marginInlineEnd: 0 }}>
            {tpl.status}
          </Tag>
          <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 400 }}>
            {tpl.id}
          </Typography.Text>
        </Space>
      }
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          建于 {tpl.createdAt}
        </Typography.Text>
      }
    >
      <div className="ig-tpl-field">
        <div className="ig-tpl-k">适用版式特征（怎么认出「这版式归我管」）</div>
        <div className="ig-tpl-v">{tpl.layoutTraits}</div>
      </div>
      <div className="ig-tpl-field">
        <div className="ig-tpl-k">规则指针（切割规则 / 脚本）</div>
        <div className="ig-tpl-v ig-mono">{tpl.rulesRef}</div>
      </div>
      {tpl.sampleRef ? (
        <div className="ig-tpl-field">
          <div className="ig-tpl-k">样张</div>
          <div className="ig-tpl-v ig-mono">{tpl.sampleRef}</div>
        </div>
      ) : null}
      <div className="ig-tpl-field">
        <div className="ig-tpl-k">切过的批次</div>
        <div className="ig-tpl-v">
          {used.length > 0 ? (
            <Space size={12} wrap>
              {used.map((b) => (
                <Link key={b.id} to={`/ingest?batch=${b.id}`}>
                  {b.id} · {b.time.slice(0, 10)}
                </Link>
              ))}
            </Space>
          ) : (
            <Typography.Text type="secondary">还没切过批次——没上过真卷子的模板，不算验过。</Typography.Text>
          )}
        </div>
      </div>
    </Card>
  )
}

function TemplatePanel() {
  // 没套模板的批次＝「现切」的那些；它们正是下一张模板的候选来源
  const adhoc = ingestBatches.filter((b) => !b.templateId)
  return (
    <div>
      <div className="ig-flow">
        <div className="ig-flow-main">有相似题记录 → 照既有方式切；没有 → 评估建新模板。</div>
        <div className="ig-flow-sub">
          完整流程（D-21）：格式确认 → <b>先查相似题记录</b>（match_key + 近似检索）→ 有相似 ⇒
          沿用既有切割方式直接分割录入（题干元信息抽离 + 判据经验吸收）；无相似 ⇒ 对照本页模板库，评估是否
          <b>新建录入模板</b> → 再按审核等级决定是否入库。
        </div>
      </div>

      {ingestTemplates.map((t) => (
        <TemplateCard key={t.id} tpl={t} />
      ))}

      <div className="ig-adhoc">
        {adhoc.length > 0 ? (
          <>
            <div>
              现切（没有对得上的模板）的批次：
              <Space size={12} wrap style={{ marginInlineStart: 6 }}>
                {adhoc.map((b) => (
                  <Link key={b.id} to={`/ingest?batch=${b.id}`}>
                    {b.id} · {b.source}
                  </Link>
                ))}
              </Space>
            </div>
            <div style={{ marginTop: 4 }}>
              🔴 现切不是错，是模板的来源：同一种版式现切到第二次，就该在这儿立一张模板，
              把这次的切法与判据经验落成规则指针——别让经验只留在那一次对话里。
            </div>
          </>
        ) : (
          <>每一批都套上了模板——没有现切的批次。</>
        )}
      </div>
    </div>
  )
}

export default function Ingest() {
  const [searchParams, setSearchParams] = useSearchParams()
  const lights = lightTotals()
  const levels = levelTotals()
  const auto = autoPassRate()

  // 时间倒序：最近一批永远在第一行（本页第一眼要看的就是「刚跑完那批怎么样」）
  const rows = useMemo(() => [...ingestBatches].sort((a, b) => b.time.localeCompare(a.time)), [])
  const latest = rows[0]

  // ?batch=ib-001 进来自动展开那一批（审核台工单卡链回来时用）
  const focus = searchParams.get('batch')
  const [expanded, setExpanded] = useState<string[]>(focus && findIngestBatch(focus) ? [focus] : [])

  // ?tab=templates 直落模板页；认不得的参数不报错，静默回落批次页
  const tab = searchParams.get('tab') === 'templates' ? 'templates' : 'batches'
  const onTab = (k: string) => {
    const next: Record<string, string> = {}
    if (k === 'templates') next.tab = 'templates'
    else if (focus) next.batch = focus
    setSearchParams(next, { replace: true })
  }

  const columns: ColumnsType<IngestBatch> = [
    {
      title: '时间',
      dataIndex: 'time',
      width: 132,
      render: (t: string) => <span style={{ whiteSpace: 'nowrap' }}>{t}</span>,
    },
    {
      // 🔴 源类型就摆在来源旁边：它决定这一批的闸怎么走、等级要不要整体 +1
      title: '源',
      key: 'srcKind',
      width: 138,
      render: (_, b) => <SrcKindTag kind={b.srcKind} />,
    },
    {
      title: '来源',
      dataIndex: 'source',
      ellipsis: { showTitle: true },
    },
    {
      title: '总数',
      key: 'total',
      width: 68,
      align: 'right',
      render: (_, b) => (
        <Tooltip title="直收 + 排队人审 + 拒收 = 总数（题级口径，行级隔离不计入）">
          <span style={{ fontWeight: 500 }}>{b.counts.total}</span>
        </Tooltip>
      ),
    },
    {
      title: '直收',
      key: 'accepted',
      width: 68,
      align: 'right',
      render: (_, b) => <Count value={b.counts.accepted} color="#389e0d" />,
    },
    {
      title: '排队人审',
      key: 'queued',
      width: 88,
      align: 'right',
      render: (_, b) => <Count value={b.counts.queued} color="#d48806" />,
    },
    {
      title: '拒收',
      key: 'rejected',
      width: 68,
      align: 'right',
      render: (_, b) => <Count value={b.counts.rejected} color="#cf1322" />,
    },
    {
      title: '闸灯摘要',
      dataIndex: 'gateSummary',
      width: 280,
      ellipsis: { showTitle: true },
      render: (s: string) => (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {s}
        </Typography.Text>
      ),
    },
  ]

  const batchPanel = (
    <>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
        口径：<b>直收</b>＝绿灯（三件套齐、考点命中已有叶子，直接可用）｜<b>排队人审</b>＝黄灯（
        <b>进库但待转正</b>，多半等图审核过）｜<b>拒收</b>＝红灯（preflight 拦下，落隔离区不进主表）。
        闸报告里提到的「行级隔离」是<b>行</b>不是<b>题</b>，不计入上面的数，去审核台的「隔离行」处置。
        免人审的只有 L0：全库 {auto.total} 条里 {auto.auto} 条直入，其余都得人看一眼。
      </Typography.Paragraph>

      <Table<IngestBatch>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={rows}
        pagination={false}
        scroll={{ x: 1160 }}
        locale={{ emptyText: <Empty description="还没有录入批次" /> }}
        expandable={{
          expandedRowKeys: expanded,
          onExpandedRowsChange: (keys) => setExpanded(keys as string[]),
          expandedRowRender: (b) => <BatchDetail batch={b} />,
          expandRowByClick: true,
          columnWidth: 40,
        }}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：点行展开看逐题灯 + 审核等级——ib-001 是扫描件（图片源，等级整体 +1），1 题红灯被拦、2 题黄灯待图审；
        ib-002 是 docx 文字层直转（守恒闸对得上账），10 题黄灯卡在图没核；ib-003 三题纯文本 + 文字层，全绿 L0 直入，
        是轻路径跑通的样子；ib-004 是手机拍照，q-4013 四个图选项 ⇒「两图以上」叠加拍照源 = L3 逐题细审。
      </Typography.Paragraph>
    </>
  )

  return (
    <PageFrame
      title="录入记录"
      desc="每次录入跑完落一条批次账：来源是什么、几题进库、几题挂起、几题被拦，逐题一盏灯、逐题一个审核等级。录入动作归 agent（kb:ingest），本页只看记录、闸报告与模板库。"
      extra={
        <Space size={6} wrap>
          <Tag color="green" style={{ marginInlineEnd: 0 }}>
            绿 {lights.绿}
          </Tag>
          <Tag color="gold" style={{ marginInlineEnd: 0 }}>
            黄 {lights.黄}
          </Tag>
          <Tag color="red" style={{ marginInlineEnd: 0 }}>
            红 {lights.红}
          </Tag>
          {latest ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              最近一次录入 {latest.time}
            </Typography.Text>
          ) : null}
        </Space>
      }
    >
      {/* 页头两张折叠卡：判等级、对执行阀，都在这儿；默认收起不挡路 */}
      <Collapse
        size="small"
        className="ig-ref"
        defaultActiveKey={[]}
        items={[
          {
            key: 'matrix',
            label: (
              <Space size={10} wrap>
                <span>审核等级矩阵（复杂度 × 源）</span>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  本页 {auto.total} 条：L0 {levels.L0} / L1 {levels.L1} / L2 {levels.L2} / L3 {levels.L3} / 人工{' '}
                  {levels.人工}
                </Typography.Text>
              </Space>
            ),
            children: <LevelMatrix />,
          },
          {
            key: 'valves',
            label: (
              <Space size={10} wrap>
                <span>入库执行阀 · 五条硬闸（全过才入）</span>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  置信度 / 格式清晰 / 存取同构 / 图片题必过审 / 每题必挂考点
                </Typography.Text>
              </Space>
            ),
            children: <ValveList />,
          },
        ]}
      />

      <Tabs
        activeKey={tab}
        onChange={onTab}
        items={[
          { key: 'batches', label: `录入批次（${ingestBatches.length}）`, children: batchPanel },
          { key: 'templates', label: `录入模板（${ingestTemplates.length}）`, children: <TemplatePanel /> },
        ]}
      />
    </PageFrame>
  )
}
