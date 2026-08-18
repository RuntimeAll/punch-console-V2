import { useEffect, useState } from 'react'
import { Alert, Breadcrumb, Button, Card, Descriptions, Empty, Space, Spin, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import PageFrame from '@/components/PageFrame'
import { KbDocView, KbInline } from '@/kb/KbBlocks'
import { kbApi } from '@/kb/api'
import type { KbArtifactDetail, KbArtifactRow, KbPaperDetail } from '@/kb/types'
import '@/kb/kb.css'

/**
 * 资料册 · 真库页 —— 一本账列表 → 册详情（papers 天列表）→ 单卷（一天一屏）。
 *
 * 🔴 只读：artifact / paper / paper_item 的写入通路是 工具箱/挂账/artifact_tool.py 与组卷工具，
 *   页面这里连一个"改状态"按钮都不放（老区页面能改状态，改完没人记账，最后对不上）。
 * 🔴 单卷视图按"一天一屏"渲：题序 + 节名 + 题面 + 答案，公式真渲（MathJax 本地）。
 */

const ART_STATUS_COLOR: Record<string, string> = { 在产: 'blue', 已交付: 'green', 已上架: 'gold' }

export function KbArtifacts() {
  const [rows, setRows] = useState<KbArtifactRow[] | null>(null)
  const [err, setErr] = useState('')
  const [artifactId, setArtifactId] = useState('')
  const [artifact, setArtifact] = useState<KbArtifactDetail | null>(null)
  const [paperId, setPaperId] = useState('')
  const [paper, setPaper] = useState<KbPaperDetail | null>(null)

  useEffect(() => {
    kbApi
      .artifacts()
      .then((r) => setRows(r.rows))
      .catch((e) => setErr(String(e.message ?? e)))
  }, [])

  useEffect(() => {
    if (!artifactId) {
      setArtifact(null)
      return
    }
    setArtifact(null)
    kbApi
      .artifact(artifactId)
      .then(setArtifact)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [artifactId])

  useEffect(() => {
    if (!paperId) {
      setPaper(null)
      return
    }
    setPaper(null)
    kbApi
      .paper(paperId)
      .then(setPaper)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [paperId])

  const columns: ColumnsType<KbArtifactRow> = [
    { title: '册名', dataIndex: 'name' },
    { title: '类别', dataIndex: 'kind', width: 96, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => <Tag color={ART_STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '出自产线', dataIndex: 'source_line', width: 110, render: (v: string | null) => v ?? '—' },
    { title: '卷数', dataIndex: 'paper_count', width: 70 },
    { title: '题数', dataIndex: 'item_count', width: 70 },
    { title: '覆盖考点', width: 96, render: (_, r) => `${r.kp_ids.length} 个` },
    { title: '建账时间', dataIndex: 'created_at', width: 152 },
  ]

  return (
    <PageFrame
      title="资料册 · 真库"
      desc="直连 kb.db 的 artifact / paper / paper_item 三表（只读）。册 → 天 → 单卷逐层下钻，单卷按一天一屏渲。"
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

      {artifactId ? (
        <Breadcrumb
          style={{ marginBottom: 10 }}
          items={[
            {
              title: (
                <a
                  onClick={() => {
                    setArtifactId('')
                    setPaperId('')
                  }}
                >
                  资料一本账
                </a>
              ),
            },
            {
              title: paperId ? <a onClick={() => setPaperId('')}>{artifact?.name ?? artifactId}</a> : (artifact?.name ?? artifactId),
            },
            ...(paperId ? [{ title: paper?.title ?? paperId }] : []),
          ]}
        />
      ) : null}

      {!artifactId ? (
        <Card size="small">
          <Table
            rowKey="id"
            size="small"
            loading={rows === null && !err}
            dataSource={rows ?? []}
            columns={columns}
            onRow={(r) => ({ onClick: () => setArtifactId(r.id), style: { cursor: 'pointer' } })}
            pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 册` }}
            locale={{ emptyText: <Empty description="一本账是空的：这个库还没挂过账" /> }}
          />
        </Card>
      ) : paperId ? (
        <PaperSheet paper={paper} onBack={() => setPaperId('')} />
      ) : (
        <ArtifactBody a={artifact} onOpenPaper={setPaperId} onBack={() => setArtifactId('')} />
      )}
    </PageFrame>
  )
}

function ArtifactBody({
  a,
  onOpenPaper,
  onBack,
}: {
  a: KbArtifactDetail | null
  onOpenPaper: (id: string) => void
  onBack: () => void
}) {
  if (!a) return <Spin />
  return (
    <>
      <Card size="small" style={{ marginBottom: 12 }} title={a.name} extra={<Button size="small" onClick={onBack}>返回一本账</Button>}>
        <Descriptions
          size="small"
          column={3}
          items={[
            { key: 'id', label: '册 id', children: <Typography.Text code>{a.id}</Typography.Text> },
            { key: 'kind', label: '类别', children: <Tag>{a.kind}</Tag> },
            { key: 'st', label: '状态', children: <Tag color={ART_STATUS_COLOR[a.status] ?? 'default'}>{a.status}</Tag> },
            { key: 'line', label: '出自产线', children: a.source_line ?? '—' },
            { key: 'tpl', label: '模版', children: a.template_id ?? '—' },
            { key: 'kp', label: '覆盖考点', children: `${a.kp_ids.length} 个` },
            { key: 'del', label: '交付时间', children: a.delivered_at ?? '—' },
            { key: 'link', label: '分享链接', children: a.link ?? '—' },
            { key: 'note', label: '备注', children: a.note ?? '—' },
          ]}
        />
        {a.files ? (
          <div style={{ marginTop: 8 }}>
            成品件：
            <Space size={4} wrap>
              {Object.entries(a.files).map(([k, v]) => (
                <Tag key={k}>
                  {k}：{String(v)}
                </Tag>
              ))}
            </Space>
          </div>
        ) : null}
      </Card>

      <div className="kb-sec-title">卷/天列表（按册内序 ord）</div>
      {a.papers.length ? (
        a.papers.map((p) => (
          <Card
            key={p.id}
            size="small"
            style={{ marginBottom: 10, cursor: 'pointer' }}
            onClick={() => onOpenPaper(p.id)}
            title={
              <span>
                {/* ord = 册内序（打卡册就是天号），标在类别里，不往标题上再拼一遍 */}
                <Tag color="blue">
                  {p.kind}
                  {p.ord != null ? ` · 序 ${p.ord}` : ''}
                </Tag>
                {p.title}
              </span>
            }
            extra={
              <Space size={6}>
                <Tag color={p.status === '定稿' ? 'green' : 'default'}>{p.status}</Tag>
                <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{p.items.length} 题 · 点开看全卷</span>
              </Space>
            }
          >
            <ol style={{ margin: 0, paddingInlineStart: 22 }}>
              {p.items.map((it) => (
                <li key={it.ord} style={{ marginBottom: 2 }}>
                  {it.section ? <Tag>{it.section}</Tag> : null}
                  <KbInline md={it.stem} />
                  <Typography.Text type="secondary" style={{ marginInlineStart: 6, fontSize: 12 }}>
                    {it.question_id}
                  </Typography.Text>
                </li>
              ))}
            </ol>
          </Card>
        ))
      ) : (
        <Empty description="这册还没挂任何卷（paper 表里没有 artifact_id 指向它的行）" />
      )}
    </>
  )
}

/** 一天一屏：题序 + 节名 + 题面 + 答案（解析折在后面一并出，走查时看得全） */
function PaperSheet({ paper, onBack }: { paper: KbPaperDetail | null; onBack: () => void }) {
  if (!paper) return <Spin />
  return (
    <Card
      size="small"
      title={
        <span>
          <Tag color="blue">
            {paper.kind}
            {paper.ord != null ? ` · 序 ${paper.ord}` : ''}
          </Tag>
          {paper.title}
          <Tag color={paper.status === '定稿' ? 'green' : 'default'} style={{ marginInlineStart: 8 }}>
            {paper.status}
          </Tag>
        </span>
      }
      extra={<Button size="small" onClick={onBack}>返回册</Button>}
    >
      <div className="kb-sheet">
        {paper.items.length ? (
          paper.items.map((it) => (
            <div className="kb-sheet-item" key={it.ord}>
              <div>
                <span className="kb-sheet-no">{it.ord}.</span>
                {it.section ? <Tag>{it.section}</Tag> : null}
                {it.qtype_label ? <Tag>{it.qtype_label}</Tag> : null}
                {it.diff_label ? <Tag color="geekblue">{it.diff_label}</Tag> : null}
                {it.score != null ? <Tag color="gold">{it.score} 分</Tag> : null}
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {it.question_id}
                </Typography.Text>
                {it.missing ? <Tag color="red">🔴 题已不在库（断链）</Tag> : null}
              </div>
              <KbDocView doc={it.blocks} empty="题面为空" />
              <div className="kb-answer-box">
                <b>答案：</b>
                <KbDocView doc={it.answer} empty="（库里无答案）" />
              </div>
              {it.analysis ? (
                <div className="kb-analysis-box">
                  <b>解析：</b>
                  <KbDocView doc={it.analysis} empty="（库里无解析）" />
                </div>
              ) : null}
            </div>
          ))
        ) : (
          <Empty description="这卷没有题（paper_item 为空）" />
        )}
      </div>
    </Card>
  )
}

export default KbArtifacts
