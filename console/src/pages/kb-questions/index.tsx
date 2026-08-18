import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tree,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { DataNode } from 'antd/es/tree'
import PageFrame from '@/components/PageFrame'
import { KbDocView, KbInline } from '@/kb/KbBlocks'
import { QUESTION_STATUS, SOURCE_KINDS, kbApi } from '@/kb/api'
import type { KbKpNode, KbQuestionDetail, KbQuestionPage, KbStats, KbTree } from '@/kb/types'
import '@/kb/kb.css'

/**
 * 题库 · 真库页 —— 左 KG 树 / 右题表 / 行点开抽屉看题面答案解析。
 *
 * 🔴 本页**只读**：数据全部来自 `/api/kb`（node:sqlite 只读连接），
 *   页面上一个写按钮都没有。改题、挂考点、改状态一律走 skill / 工具箱脚本。
 * 🔴 树上「未铺」的枝如实标出来（老区把没铺的枝当空枝渲，看不出是"没有题"还是"没建过"）。
 */

const STATUS_COLOR: Record<string, string> = {
  草稿: 'default',
  已审: 'blue',
  上架: 'green',
  退役: 'red',
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

  const [kp, setKp] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [sourceKind, setSourceKind] = useState<string>('')
  const [pageNo, setPageNo] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const [detail, setDetail] = useState<KbQuestionDetail | null>(null)
  const [detailId, setDetailId] = useState<string>('')

  // 树与库概况只取一次
  useEffect(() => {
    kbApi
      .tree()
      .then(setTree)
      .catch((e) => setErr(String(e.message ?? e)))
    kbApi.stats().then(setStats).catch(() => undefined)
  }, [])

  const reload = useCallback(() => {
    setLoading(true)
    kbApi
      .questions({ kp, status, source_kind: sourceKind, page: pageNo, size: pageSize })
      .then((p) => {
        setPage(p)
        setErr('')
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [kp, status, sourceKind, pageNo, pageSize])

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
      render: (v: string) => (v ? <KbInline md={v} /> : <span style={{ color: '#cf1322' }}>🔴 题面为空</span>),
    },
    {
      title: '题型 / 难度',
      width: 130,
      render: (_, r) => (
        <Space size={4} wrap>
          {r.qtype_label ? <Tag>{r.qtype_label}</Tag> : null}
          {r.diff_label ? <Tag color="geekblue">{r.diff_label}</Tag> : null}
        </Space>
      ),
    },
    {
      title: '考点',
      width: 190,
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
      title: '来源类',
      width: 110,
      dataIndex: 'source_label',
      render: (v: string | null) => v ?? <span style={{ color: 'rgba(0,0,0,0.25)' }}>—</span>,
    },
    {
      title: '状态',
      width: 76,
      dataIndex: 'status',
      render: (v: string) => <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '血缘',
      width: 96,
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
    { title: '建库时间', width: 152, dataIndex: 'created_at' },
  ]

  return (
    <PageFrame
      title="题库 · 真库"
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
                    onSelect={(keys) => {
                      setKp(keys.length ? String(keys[0]) : '')
                      setPageNo(1)
                    }}
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
            <Space wrap style={{ marginBottom: 10 }}>
              <Select
                allowClear
                placeholder="状态"
                style={{ width: 120 }}
                value={status || undefined}
                onChange={(v) => {
                  setStatus(v ?? '')
                  setPageNo(1)
                }}
                options={QUESTION_STATUS.map((s) => ({ value: s, label: s }))}
              />
              <Select
                allowClear
                placeholder="来源类"
                style={{ width: 170 }}
                value={sourceKind || undefined}
                onChange={(v) => {
                  setSourceKind(v ?? '')
                  setPageNo(1)
                }}
                options={SOURCE_KINDS}
              />
              {page?.kp_filter ? (
                <Tag color="purple">
                  考点：{page.kp_filter.name}（按 {page.kp_filter.matched_by} 命中，含下级）
                </Tag>
              ) : null}
              {page?.kp_unresolved ? (
                <Tag color="red">考点词「{page.kp_unresolved}」在库里 resolve 不到 ⇒ 0 条</Tag>
              ) : null}
              <span style={{ color: 'rgba(0,0,0,0.45)' }}>共 {page?.total ?? 0} 题</span>
            </Space>

            <Table
              rowKey="id"
              size="small"
              loading={loading}
              dataSource={page?.rows ?? []}
              columns={columns}
              onRow={(r) => ({ onClick: () => setDetailId(r.id), style: { cursor: 'pointer' } })}
              pagination={{
                current: page?.page ?? 1,
                pageSize: page?.size ?? pageSize,
                total: page?.total ?? 0,
                showSizeChanger: true,
                pageSizeOptions: [10, 20, 50, 100],
                onChange: (p, s) => {
                  setPageNo(p)
                  setPageSize(s)
                },
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
