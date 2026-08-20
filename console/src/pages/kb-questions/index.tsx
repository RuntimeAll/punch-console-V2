import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Tree,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { DataNode } from 'antd/es/tree'
import { useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { KbDocView, KbInline } from '@/kb/KbBlocks'
import { QUESTION_STATUS, SOURCE_KINDS, kbApi } from '@/kb/api'
import type {
  KbKpNode,
  KbQuestionDetail,
  KbQuestionPage,
  KbSemanticHealth,
  KbStats,
  KbTree,
} from '@/kb/types'
import '@/kb/kb.css'

/**
 * 题库 · 真库页 —— 左 KG 树 / 右题表 / 行点开抽屉看题面答案解析。
 *
 * 🔴 本页**只读**：数据全部来自 `/api/kb`（node:sqlite 只读连接），
 *   页面上一个写按钮都没有。改题、挂考点、改状态一律走 skill / 工具箱脚本。
 * 🔴 树上「未铺」的枝如实标出来（老区把没铺的枝当空枝渲，看不出是"没有题"还是"没建过"）。
 *
 * ── PRD-007 线2 增强（四件，都在这一页上做，不另开页）──────────────────
 * ① **来源筛选**：教材版本 / 版本使用级 / 来源册三维（prov 现取，来源册是读 API 现推的，
 *    每行带 src_book_from 说明推法）——选题时「哪套教材的、能不能用、哪本册来的」是第一刀；
 * ② **审核工单标记**：review_ticket 里还挂着「待处理」的题**整行标红**（闸④ 等级审的未了结件），
 *    并给一个「只看挂单」开关。挂着单的题在页面上是隐形的，等于这条闸只活在库里；
 * ③ **草稿 / 上架状态可见**：状态下拉带上全库分布数（草稿 1 / 上架 1089 这种账要一眼看见）；
 * ④ **--like 语意搜索**：查询文本 → :4315 常驻 serve 算向量 → 与 question_vec 点积排序。
 *    🔴 serve 探活失败就**把搜索框收起来**（优雅降级），绝不留个点了没反应的框；
 *    也绝不在 serve 挂掉时静默退回「按时间排」冒充语意命中。
 */

const STATUS_COLOR: Record<string, string> = {
  草稿: 'default',
  已审: 'blue',
  上架: 'green',
  退役: 'red',
}

/** 版本使用级的颜色：一级能用（绿）/ 二级备用（蓝）/ 三级暂不用（灰）——组卷取题时的红绿灯 */
function USE_LEVEL_COLOR(v: string): string {
  if (v.startsWith('一级')) return 'green'
  if (v.startsWith('二级')) return 'blue'
  return 'default'
}

function treeTitle(n: KbKpNode) {
  return (
    <span>
      {n.name}
      {n.status === '未铺' ? (
        <Tag color="orange" style={{ marginInlineStart: 6 }}>
          未铺
        </Tag>
      ) : null}
      {n.q_total > 0 ? (
        <span style={{ color: 'rgba(0,0,0,0.45)', marginInlineStart: 6 }}>
          {n.level === '考点' ? n.q_count : n.q_total} 题
        </span>
      ) : null}
    </span>
  )
}

function toTreeData(nodes: KbKpNode[]): DataNode[] {
  return nodes.map((n) => ({
    key: n.id,
    title: treeTitle(n),
    children: n.children.length ? toTreeData(n.children) : undefined,
    // 未铺的枝没有下级，点它只是筛出 0 题——保留可选，让人一眼确认"确实没铺"
    selectable: true,
  }))
}

export function KbQuestions() {
  const [tree, setTree] = useState<KbTree | null>(null)
  const [stats, setStats] = useState<KbStats | null>(null)
  const [page, setPage] = useState<KbQuestionPage | null>(null)
  const [err, setErr] = useState<string>('')
  const [loading, setLoading] = useState(false)

  /**
   * 🔴 全部筛选态挂 URL，不放本地 state。三个理由，每个都真实：
   *   ① 知识图谱页的「在题库里看（N 题）」带 ?kp= 跳过来，必须能直接选中那一枝
   *      （放本地 state 就会出现「链接跳过来了、筛子没动」的假象）；
   *   ② 「三级·暂不用的题有哪些」「还挂着工单的是哪道」这种一屏要能直接发链接给人；
   *   ③ 走查/截图可复现——一个 URL 就是一个确定的画面。
   */
  const [searchParams, setSearchParams] = useSearchParams()
  const kp = searchParams.get('kp') ?? ''
  const status = searchParams.get('status') ?? ''
  const sourceKind = searchParams.get('source_kind') ?? ''
  /**
   * 🔴 多值维度必须 useMemo 按 URL 串缓存：`searchParams.getAll()` 每次渲染都返回**新数组**，
   * 直接进 useCallback 的依赖表 ⇒ reload 每渲染都换身份 ⇒ useEffect 每渲染都重跑 ⇒
   * **无限请求循环**（2026-08-20 实伤：页面显示「共 0 题」，无头 Chrome 直接 renderer 崩）。
   */
  const qs = searchParams.toString()
  const textbook = useMemo(() => searchParams.getAll('textbook'), [qs]) // eslint-disable-line react-hooks/exhaustive-deps
  const useLevel = useMemo(() => searchParams.getAll('use_level'), [qs]) // eslint-disable-line react-hooks/exhaustive-deps
  const srcBook = useMemo(() => searchParams.getAll('src_book'), [qs]) // eslint-disable-line react-hooks/exhaustive-deps
  const ticketOnly = searchParams.get('ticket') === '1'
  const like = (searchParams.get('like') ?? '').trim()
  const pageNo = Math.max(1, Number(searchParams.get('page') || 1))
  const pageSize = Math.max(1, Number(searchParams.get('size') || 20))

  /** 改筛选：默认把页码抹掉回第 1 页（不然会停在新结果集里不存在的页码上） */
  const patch = (fn: (p: URLSearchParams) => void, keepPage = false) => {
    const next = new URLSearchParams(searchParams)
    fn(next)
    if (!keepPage) next.delete('page')
    setSearchParams(next, { replace: true })
  }
  const setOne = (key: string, v: string) => patch((p) => (v ? p.set(key, v) : p.delete(key)))
  const setMany = (key: string, vs: string[]) =>
    patch((p) => {
      p.delete(key)
      for (const v of vs) p.append(key, v)
    })
  const setKp = (v: string) => setOne('kp', v)

  const [likeDraft, setLikeDraft] = useState(like)
  const [sem, setSem] = useState<KbSemanticHealth | null>(null)

  const [detail, setDetail] = useState<KbQuestionDetail | null>(null)
  const [detailId, setDetailId] = useState<string>('')

  // 树与库概况只取一次；语意 serve 也只探一次活（探不到就不显示 --like 框）
  useEffect(() => {
    kbApi
      .tree()
      .then(setTree)
      .catch((e) => setErr(String(e.message ?? e)))
    kbApi.stats().then(setStats).catch(() => undefined)
    kbApi.semanticHealth().then(setSem).catch(() => setSem({ ok: false, port: 4315 }))
  }, [])

  const reload = useCallback(() => {
    setLoading(true)
    kbApi
      .questions({
        kp,
        status,
        source_kind: sourceKind,
        textbook,
        use_level: useLevel,
        src_book: srcBook,
        ticket: ticketOnly,
        like,
        page: pageNo,
        size: pageSize,
      })
      .then((p) => {
        setPage(p)
        setErr('')
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [kp, status, sourceKind, textbook, useLevel, srcBook, ticketOnly, like, pageNo, pageSize])

  useEffect(reload, [reload])

  useEffect(() => {
    if (!detailId) {
      setDetail(null)
      return
    }
    kbApi
      .question(detailId)
      .then(setDetail)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [detailId])

  const treeData = useMemo(() => (tree ? toTreeData(tree.roots) : []), [tree])

  const columns: ColumnsType<NonNullable<KbQuestionPage['rows']>[number]> = [
    {
      title: '题面（首块，截断 120 字）',
      dataIndex: 'stem',
      // 🔴 必须给最小宽度：中文的 min-content 宽度 = 一个字，auto 布局会在别的列吃紧时
      //   把这一列压成「一行一个字」的竖条（2026-08-20 单行结果集实测撞到）。
      //   width 只是权重提示，真正兜底的是 render 里这层 minWidth。
      width: 300,
      render: (v: string) => (
        <div style={{ minWidth: 220 }}>
          {v ? <KbInline md={v} /> : <span style={{ color: '#cf1322' }}>🔴 题面为空</span>}
        </div>
      ),
    },
    {
      title: '题型 / 难度',
      width: 110,
      render: (_, r) => (
        <Space size={4} wrap>
          {r.qtype_label ? <Tag>{r.qtype_label}</Tag> : null}
          {r.diff_label ? <Tag color="geekblue">{r.diff_label}</Tag> : null}
        </Space>
      ),
    },
    {
      title: '考点',
      width: 170,
      render: (_, r) =>
        r.kps.length ? (
          <Space size={4} wrap>
            {r.kps.map((k) => (
              <Tag key={k.id} color={k.is_primary ? 'purple' : undefined}>
                {k.name}
              </Tag>
            ))}
          </Space>
        ) : (
          <span style={{ color: '#cf1322' }}>🔴 未挂考点</span>
        ),
    },
    {
      // 🔴 来源三维合一格：教材版本（哪套书）/ 版本使用级（能不能用）/ 来源册（哪本来的）
      //   —— 选题第一刀问的就是这三样，分三列太占地方，合一格上下三行
      title: '来源（版本 / 使用级 / 册）',
      key: 'src',
      width: 200,
      render: (_, r) => (
        <div style={{ fontSize: 12, lineHeight: 1.7 }}>
          <div>
            {r.textbook ? (
              <Tag style={{ marginInlineEnd: 4 }}>{r.textbook}</Tag>
            ) : (
              <Tag style={{ marginInlineEnd: 4, color: 'rgba(0,0,0,0.38)' }}>版本未标</Tag>
            )}
            {r.use_level ? (
              <Tag color={USE_LEVEL_COLOR(r.use_level)} style={{ marginInlineEnd: 0 }}>
                {r.use_level}
              </Tag>
            ) : null}
          </div>
          <div style={{ color: 'rgba(0,0,0,0.55)' }}>
            {r.src_book ? (
              <Tooltip title={`来源册是从 ${r.src_book_from} 推出来的（prov 里没有统一的册字段）`}>
                <span>{r.src_book}</span>
              </Tooltip>
            ) : (
              <span style={{ color: 'rgba(0,0,0,0.25)' }}>册未标</span>
            )}
          </div>
          <div style={{ color: 'rgba(0,0,0,0.45)' }}>{r.source_label ?? '—'}</div>
        </div>
      ),
    },
    {
      title: '状态 / 工单',
      width: 104,
      render: (_, r) => (
        <Space size={4} wrap>
          <Tag color={STATUS_COLOR[r.status] ?? 'default'} style={{ marginInlineEnd: 0 }}>
            {r.status}
          </Tag>
          {/* 🔴 闸④：还挂着待处理工单的题必须看得见（先审后上架，挂着单还上架就是违例） */}
          {r.ticket_open > 0 ? (
            <Tooltip title={r.tickets.filter((t) => t.status === '待处理').map((t) => `#${t.id} ${t.kind}：${t.note ?? ''}`).join('\n')}>
              <Tag color="red" style={{ marginInlineEnd: 0 }}>
                挂单 {r.ticket_open}
              </Tag>
            </Tooltip>
          ) : null}
        </Space>
      ),
    },
    {
      title: '血缘',
      width: 86,
      render: (_, r) =>
        r.has_lineage ? (
          <Space size={4} wrap>
            {r.has_mother ? <Tag color="volcano">有母题</Tag> : null}
            {r.variant_count > 0 ? <Tag color="cyan">变体 {r.variant_count}</Tag> : null}
          </Space>
        ) : (
          <span style={{ color: 'rgba(0,0,0,0.25)' }}>—</span>
        ),
    },
    { title: '建库时间', width: 104, dataIndex: 'created_at' },
  ]

  // 语意搜索时把相似度插到第一列：不摆出分数，「为什么这条排第一」就说不清
  if (page?.semantic) {
    columns.unshift({
      title: '相似度',
      key: 'score',
      width: 84,
      align: 'right',
      render: (_, r) =>
        r.score == null ? (
          <span style={{ color: 'rgba(0,0,0,0.25)' }}>—</span>
        ) : (
          <Typography.Text style={{ fontFamily: 'monospace', fontSize: 13 }}>{r.score.toFixed(3)}</Typography.Text>
        ),
    })
  }

  return (
    <PageFrame
      title="题库"
      desc={
        <>
          直连 kb.db 的只读视图（页面无任何写口，改题走 skill / 工具箱脚本）。左树点节点按整枝筛题，行点开看全文。
          {stats ? <span style={{ marginInlineStart: 8 }}>库：{stats.db_path}</span> : null}
        </>
      }
      extra={<Tag color="green">真库 · 只读</Tag>}
    >
      {err ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message="读 API 出错"
          description={
            <>
              {err}
              <br />
              起服务：<Typography.Text code>node console/server/kb-read-api.mjs</Typography.Text>（:4310）
            </>
          }
        />
      ) : null}

      <Row gutter={12}>
        <Col span={7}>
          <Card
            size="small"
            title="知识图谱（kp 五层树）"
            extra={
              tree ? (
                <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
                  {tree.kp_total} 节点 · 未铺 {tree.unbuilt_total}
                </span>
              ) : null
            }
          >
            <div className="kb-tree-panel">
              {tree ? (
                treeData.length ? (
                  <Tree
                    treeData={treeData}
                    defaultExpandedKeys={tree.roots.flatMap((r) => [r.id, ...r.children.map((c) => c.id)])}
                    selectedKeys={kp ? [kp] : []}
                    onSelect={(keys) => setKp(keys.length ? String(keys[0]) : '')}
                  />
                ) : (
                  <Empty description="树是空的：这个库还没铺过枝" />
                )
              ) : (
                <Spin />
              )}
            </div>
            {kp ? (
              <Button size="small" style={{ marginTop: 8 }} onClick={() => setKp('')}>
                清除考点筛选
              </Button>
            ) : null}
          </Card>
        </Col>

        <Col span={17}>
          <Card size="small">
            <Space wrap style={{ marginBottom: 8 }}>
              <Select
                allowClear
                placeholder="状态"
                style={{ width: 150 }}
                value={status || undefined}
                onChange={(v) => setOne('status', v ?? '')}
                // 🔴 状态下拉带全库分布：草稿多少、上架多少要一眼看见（账不摆出来就没人对）
                options={QUESTION_STATUS.map((s) => {
                  const f = page?.facets.status.find((x) => x.value === s)
                  return { value: s, label: f ? `${s}（${f.count}）` : `${s}（0）` }
                })}
              />
              <Select
                allowClear
                placeholder="来源类"
                style={{ width: 150 }}
                value={sourceKind || undefined}
                onChange={(v) => setOne('source_kind', v ?? '')}
                options={SOURCE_KINDS}
              />
              <Select
                allowClear
                mode="multiple"
                maxTagCount="responsive"
                placeholder="教材版本"
                style={{ minWidth: 170 }}
                value={textbook}
                onChange={(v) => setMany('textbook', v)}
                options={(page?.facets.textbook ?? []).map((f) => ({
                  value: f.value ?? '未标',
                  label: `${f.label}（${f.count}）`,
                }))}
              />
              <Select
                allowClear
                mode="multiple"
                maxTagCount="responsive"
                placeholder="版本使用级"
                style={{ minWidth: 190 }}
                value={useLevel}
                onChange={(v) => setMany('use_level', v)}
                options={(page?.facets.use_level ?? []).map((f) => ({
                  value: f.value ?? '未标',
                  label: `${f.label}（${f.count}）`,
                }))}
              />
              <Select
                allowClear
                mode="multiple"
                maxTagCount="responsive"
                placeholder="来源册"
                style={{ minWidth: 230 }}
                value={srcBook}
                onChange={(v) => setMany('src_book', v)}
                options={(page?.facets.src_book ?? []).map((f) => ({
                  value: f.value ?? '未标',
                  label: `${f.label}（${f.count}）`,
                }))}
              />
              <Checkbox
                checked={ticketOnly}
                onChange={(e) => setOne('ticket', e.target.checked ? '1' : '')}
              >
                <span style={{ fontSize: 13 }}>
                  只看挂着待处理工单的
                  {page ? (
                    <Tag color={page.facets.ticket_open_total > 0 ? 'red' : 'green'} style={{ marginInlineStart: 6 }}>
                      {page.facets.ticket_open_total}
                    </Tag>
                  ) : null}
                </span>
              </Checkbox>
            </Space>

            {/* --like 语意搜索：serve 探不到活就整条收起来（不留个点了没反应的框） */}
            {sem?.ok ? (
              <Space wrap style={{ marginBottom: 8 }}>
                <Input.Search
                  allowClear
                  placeholder="--like 语意搜索：描述你想找什么样的题"
                  style={{ width: 380 }}
                  value={likeDraft}
                  onChange={(e) => setLikeDraft(e.target.value)}
                  onSearch={(v) => setOne('like', v.trim())}
                  enterButton="语意找题"
                />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  先按上面的筛子过一遍，再在候选里按余弦排序（口径同 工具箱/检索/query_core）；
                  serve {sem.health?.model ?? ''} :{sem.port} 常驻
                </Typography.Text>
                {like ? (
                  <Tag
                    color="purple"
                    closable
                    onClose={() => {
                      setLikeDraft('')
                      setOne('like', '')
                    }}
                  >
                    语意：{like}
                  </Tag>
                ) : null}
              </Space>
            ) : (
              <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 8px' }}>
                语意搜索框已收起：:{sem?.port ?? 4315} 的常驻 serve 探不到活
                （起它：<Typography.Text code>python 工具箱\启动台.py</Typography.Text>）。
                其余筛选照常——serve 是加速器不是依赖。
              </Typography.Paragraph>
            )}

            <Space wrap style={{ marginBottom: 10 }}>
              {page?.kp_filter ? (
                <Tag color="purple">
                  考点：{page.kp_filter.name}（按 {page.kp_filter.matched_by} 命中，含下级）
                </Tag>
              ) : null}
              {page?.kp_unresolved ? (
                <Tag color="red">考点词「{page.kp_unresolved}」在库里 resolve 不到 ⇒ 0 条</Tag>
              ) : null}
              {page?.semantic ? (
                <Tag color="purple">
                  语意排序：SQL 先筛出 {page.semantic.sql_candidates} 条候选 → 算过向量的{' '}
                  {page.semantic.vectored} 条按余弦排
                  {page.semantic.missing > 0 ? `（还有 ${page.semantic.missing} 条没算向量，排不进来）` : ''}
                </Tag>
              ) : null}
              <span style={{ color: 'rgba(0,0,0,0.45)' }}>
                共 {page?.total ?? 0} 题
                {page ? ` / 全库 ${page.facets.question_total}` : ''}
              </span>
            </Space>

            <Table
              rowKey="id"
              size="small"
              loading={loading}
              dataSource={page?.rows ?? []}
              columns={columns}
              // 列多了会挤：横向留滚动条，别把题面列压成竖条
              // 列宽合计 ≈1074（300+110+170+200+104+86+104），给 1080 正好不横滚；
              // 窗口更窄时才出横滚条——总之绝不再把题面列压成竖条
              scroll={{ x: 1080 }}
              // 🔴 挂着待处理工单的题整行标红：这条闸不上脸就等于只活在库里
              onRow={(r) => ({
                onClick: () => setDetailId(r.id),
                style: { cursor: 'pointer', background: r.ticket_open > 0 ? '#fff1f0' : undefined },
              })}
              pagination={{
                current: page?.page ?? 1,
                pageSize: page?.size ?? pageSize,
                total: page?.total ?? 0,
                showSizeChanger: true,
                pageSizeOptions: [10, 20, 50, 100],
                onChange: (p, s) =>
                  patch(
                    (q) => {
                      q.set('page', String(p))
                      q.set('size', String(s))
                    },
                    true,
                  ),
                showTotal: (t) => `共 ${t} 题`,
              }}
              locale={{ emptyText: <Empty description="按当前筛选，库里没有题" /> }}
            />
          </Card>
        </Col>
      </Row>

      <Drawer
        width={780}
        open={!!detailId}
        onClose={() => setDetailId('')}
        title={detail ? `题 ${detail.id}` : '载入中…'}
      >
        {detail ? <QuestionDetailBody d={detail} /> : <Spin />}
      </Drawer>
    </PageFrame>
  )
}

function QuestionDetailBody({ d }: { d: KbQuestionDetail }) {
  return (
    <>
      <Descriptions size="small" column={2} bordered items={[
        { key: 'st', label: '状态', children: <Tag color={STATUS_COLOR[d.status] ?? 'default'}>{d.status}</Tag> },
        { key: 'qt', label: '题型 / 难度', children: `${d.qtype_label ?? '—'} / ${d.diff_label ?? '—'}` },
        { key: 'src', label: '来源类', children: d.source_label ?? '—' },
        { key: 'raw', label: '来源原文', children: d.source_raw ?? '—' },
        { key: 'ct', label: '建库', children: d.created_at ?? '—' },
        { key: 'ut', label: '更新', children: d.updated_at ?? '—' },
      ]} />

      <div className="kb-sec-title">考点全路径</div>
      {d.kps.length ? (
        d.kps.map((k) => (
          <div key={k.id} style={{ marginBottom: 4 }}>
            {k.is_primary ? <Tag color="purple">主</Tag> : <Tag>副</Tag>}
            {k.path.map((p) => p.name).join(' › ')}
            {k.anchor?.confidence !== undefined ? (
              <span style={{ color: 'rgba(0,0,0,0.45)', marginInlineStart: 8 }}>
                置信 {k.anchor.confidence}
                {k.anchor.stage ? ` · ${k.anchor.stage}` : ''}
              </span>
            ) : null}
          </div>
        ))
      ) : (
        <span style={{ color: '#cf1322' }}>🔴 这题没挂考点（叶子闸应拦住，出现即是坏账）</span>
      )}

      {d.tags.length ? (
        <>
          <div className="kb-sec-title">标签</div>
          <Space size={4} wrap>
            {d.tags.map((t) => (
              <Tag key={t.id}>
                {t.domain}·{t.name}
              </Tag>
            ))}
          </Space>
        </>
      ) : null}

      <div className="kb-sec-title">题面</div>
      <KbDocView doc={d.blocks} empty="题面块流为空（question.blocks_json 是 NOT NULL，为空即坏账）" />

      <div className="kb-sec-title">答案</div>
      <div className="kb-answer-box">
        <KbDocView doc={d.answer} empty="库里没有答案（老区 46% 无答案的坑，v2 由闸拦）" />
      </div>

      <div className="kb-sec-title">解析</div>
      <div className="kb-analysis-box">
        <KbDocView doc={d.analysis} empty="库里没有解析" />
      </div>

      <div className="kb-sec-title">血缘（SSOT = question.mother_qid 一列）</div>
      {d.lineage.mother ? (
        <div>
          母题：<Typography.Text code>{d.lineage.mother.id}</Typography.Text>{' '}
          {d.lineage.mother.missing ? (
            <Tag color="red">母题已不在库（断链）</Tag>
          ) : (
            <span style={{ color: 'rgba(0,0,0,0.65)' }}>
              <KbInline md={d.lineage.mother.stem ?? ''} />
            </span>
          )}
          {d.variant_op ? <Tag color="volcano" style={{ marginInlineStart: 6 }}>算子 {d.variant_op}</Tag> : null}
        </div>
      ) : (
        <div style={{ color: 'rgba(0,0,0,0.45)' }}>无母题（本题是母题或独立录入）</div>
      )}
      {d.lineage.variants.length ? (
        <ul style={{ margin: '6px 0 0', paddingInlineStart: 20 }}>
          {d.lineage.variants.map((v) => (
            <li key={v.id}>
              <Typography.Text code>{v.id}</Typography.Text> {v.variant_op ? <Tag>{v.variant_op}</Tag> : null}
              <span style={{ color: 'rgba(0,0,0,0.65)' }}>
                <KbInline md={v.stem} />
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="kb-sec-title">进过哪些卷（使用足迹 = join paper_item 现算）</div>
      {d.papers.length ? (
        <ul style={{ margin: 0, paddingInlineStart: 20 }}>
          {d.papers.map((p) => (
            <li key={`${p.paper_id}-${p.item_ord}`}>
              {p.artifact_name ?? '（无册）'} › {p.title}
              <span style={{ color: 'rgba(0,0,0,0.45)' }}>
                （第 {p.item_ord} 题{p.section ? ` · ${p.section}` : ''}
                {p.score != null ? ` · ${p.score} 分` : ''}）
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div style={{ color: 'rgba(0,0,0,0.45)' }}>还没进过任何卷（= 组卷时的"未用过的题"）</div>
      )}

      {d.prov ? (
        <>
          <div className="kb-sec-title">血缘原始载荷 prov_json</div>
          <Typography.Paragraph>
            <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(d.prov, null, 2)}</pre>
          </Typography.Paragraph>
        </>
      ) : null}
    </>
  )
}

export default KbQuestions
