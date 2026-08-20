import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Breadcrumb, Button, Card, Collapse, Descriptions, Empty, Space, Spin, Table, Tabs, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link, useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { KbDocView, KbInline } from '@/kb/KbBlocks'
import { ARTIFACT_SUBKINDS, kbApi } from '@/kb/api'
import type { KbArtifactDetail, KbArtifactList, KbArtifactRow, KbArtifactSubkind, KbPaperDetail } from '@/kb/types'
import '@/kb/kb.css'

/**
 * 资料册 · 真库页 —— 一本账列表 → 册详情（papers 天列表）→ 单卷（一天一屏）。
 *
 * 🔴 只读：artifact / paper / paper_item 的写入通路是 工具箱/挂账/artifact_tool.py 与组卷工具，
 *   页面这里连一个"改状态"按钮都不放（老区页面能改状态，改完没人记账，最后对不上）。
 * 🔴 单卷视图按"一天一屏"渲：题序 + 节名 + 题面 + 答案，公式真渲（MathJax 本地）。
 *
 * ── 二轮改造（用户走查：「一本账里全是内部代号，看不出这是啥」）──────────────
 * ① **三页签分流**，吃 `artifact.细类`：组卷册 / 发布包 / 历史册。三种东西的看法完全不同
 *    （组卷册要看卷、发布包要看宣发与链接、历史册只有账），混在一张表里每一列都对不齐。
 *    🔴 细类列没上线的库（worktree 沙盘 / 旧库）⇒ 退回**全量一张表** + 顶栏「细类列待上线」提示，
 *    不显示三个空页签装样子。
 * ② **人话名**：列表主行显示 `display_name`（组卷册取所属卷的卷面标题、发布包取 note.标题候选[0]），
 *    内部代号（`浙教出卷·U1·2` 这类）缩成灰色副行。名字怎么来的随行带 `display_from`，鼠标悬停可见。
 * ③ **退役不混现役**：`status=退役` 的册默认收进「已退役」折叠区。退役是账面下线不是删除
 *    （题已归池、PDF 已挪走），混在现役里排会让人把退役册当在售册发出去。
 */

const ART_STATUS_COLOR: Record<string, string> = { 在产: 'blue', 已交付: 'green', 已上架: 'gold', 退役: 'default' }
const SUBKIND_COLOR: Record<string, string> = { 组卷册: 'blue', 发布包: 'purple', 历史册: 'default' }

export function KbArtifacts() {
  const [list, setList] = useState<KbArtifactList | null>(null)
  const [err, setErr] = useState('')
  const [artifactId, setArtifactId] = useState('')
  const [artifact, setArtifact] = useState<KbArtifactDetail | null>(null)
  const [paperId, setPaperId] = useState('')
  const [paper, setPaper] = useState<KbPaperDetail | null>(null)

  // 🔴 页签挂在 URL 的 ?sub= 上（与全站「选中挂 URL」同一套口径）：
  //   外面要能直链到「发布包」那一页，走查时也能把某一页签的链接直接贴给人。
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('sub') ?? ''
  // 细类列没上线时页签退化：只有「全部」一张表可看
  const tab: KbArtifactSubkind | '全部' =
    list && !list.细类_available
      ? '全部'
      : (['组卷册', '发布包', '历史册', '全部'] as const).includes(rawTab as KbArtifactSubkind | '全部')
        ? (rawTab as KbArtifactSubkind | '全部')
        : '组卷册'
  const setTab = useCallback(
    (k: string) => {
      const next = new URLSearchParams(searchParams)
      if (k && k !== '组卷册') next.set('sub', k)
      else next.delete('sub')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  useEffect(() => {
    kbApi
      .artifacts()
      .then(setList)
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

  /** 当前页签下的行（不含退役——退役单独折叠区） */
  const { live, retired } = useMemo(() => {
    const rows = list?.rows ?? []
    const inTab = tab === '全部' ? rows : rows.filter((r) => r.细类 === tab)
    return { live: inTab.filter((r) => !r.retired), retired: inTab.filter((r) => r.retired) }
  }, [list, tab])

  const columns: ColumnsType<KbArtifactRow> = [
    {
      title: '册名',
      dataIndex: 'display_name',
      // 🔴 中文列必须给最小宽度：中文 min-content 宽 = 一个字，auto 布局会把它压成竖条
      width: 320,
      render: (_: string, r) => (
        <div style={{ minWidth: 240 }}>
          <div title={`名字来自：${r.display_from}`}>{r.display_name}</div>
          {r.code_name ? (
            // 内部代号缩成灰色副行：产线排班认它，人不认它
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {r.code_name}
            </Typography.Text>
          ) : null}
        </div>
      ),
    },
    { title: '类别', dataIndex: 'kind', width: 92, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '状态',
      dataIndex: 'status',
      width: 84,
      render: (v: string) => <Tag color={ART_STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '出自产线', dataIndex: 'source_line', width: 118, render: (v: string | null) => v ?? '—' },
    { title: '卷数', dataIndex: 'paper_count', width: 66 },
    { title: '题数', dataIndex: 'item_count', width: 66 },
    { title: '覆盖考点', width: 92, render: (_, r) => `${r.kp_ids.length} 个` },
    { title: '建账时间', dataIndex: 'created_at', width: 150 },
  ]

  const st = list?.细类_stat
  const tabItems = [
    ...ARTIFACT_SUBKINDS.map((k) => ({
      key: k.value,
      label: `${k.label}${st ? ` ${st[k.value]}` : ''}`,
    })),
    { key: '全部', label: `全部${list ? ` ${list.total}` : ''}` },
  ]

  return (
    <PageFrame
      title="资料册"
      desc="直连 kb.db 的 artifact / paper / paper_item 三表（只读）。册 → 天 → 单卷逐层下钻，单卷按一天一屏渲。"
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {list ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              共 {list.total} 册{list.retired_total > 0 ? ` · 其中已退役 ${list.retired_total}` : ''}
            </Typography.Text>
          ) : null}
        </Space>
      }
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
              title: paperId ? (
                <a onClick={() => setPaperId('')}>{artifact?.display_name ?? artifactId}</a>
              ) : (
                (artifact?.display_name ?? artifactId)
              ),
            },
            ...(paperId ? [{ title: paper?.title ?? paperId }] : []),
          ]}
        />
      ) : null}

      {!artifactId ? (
        <>
          {list && !list.细类_available ? (
            // 🔴 缺列不假装分好了类：退回全量一张表，并把原因说清楚
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 12 }}
              message="细类列待上线 —— 本页暂按全量显示"
              description="artifact 表还没有「细类」列（组卷册 / 发布包 / 历史册），三页签分流暂时退化成一张全量表。DDL 落库后本页自动分流，不需要改代码。"
            />
          ) : null}

          <Card size="small" styles={{ body: { paddingTop: 8 } }}>
            {list?.细类_available ? (
              <>
                <Tabs size="small" activeKey={tab} onChange={setTab} items={tabItems} style={{ marginBottom: 4 }} />
                <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 10px' }}>
                  {ARTIFACT_SUBKINDS.find((k) => k.value === tab)?.desc ??
                    '三种细类合在一张表里看——列的含义各不相同，对不齐属正常。'}
                </Typography.Paragraph>
              </>
            ) : null}

            <Table
              rowKey="id"
              size="small"
              loading={list === null && !err}
              dataSource={live}
              columns={columns}
              scroll={{ x: 1090 }}
              onRow={(r) => ({ onClick: () => setArtifactId(r.id), style: { cursor: 'pointer' } })}
              pagination={{ pageSize: 20, showTotal: (t) => `现役 ${t} 册` }}
              locale={{ emptyText: <Empty description={`「${tab}」这一类现在没有现役的册`} /> }}
            />

            {retired.length ? (
              // 🔴 退役折叠区：默认收起，与现役分开排。退役=账面下线不物理删（题已归池、PDF 已挪走）
              <Collapse
                size="small"
                style={{ marginTop: 12 }}
                items={[
                  {
                    key: 'retired',
                    label: (
                      <span>
                        已退役 {retired.length} 册
                        <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineStart: 8 }}>
                          账面下线不删档——题已归池，卷面留档备查
                        </Typography.Text>
                      </span>
                    ),
                    children: (
                      <Table
                        rowKey="id"
                        size="small"
                        dataSource={retired}
                        columns={columns}
                        scroll={{ x: 1090 }}
                        onRow={(r) => ({ onClick: () => setArtifactId(r.id), style: { cursor: 'pointer' } })}
                        pagination={false}
                      />
                    ),
                  },
                ]}
              />
            ) : null}
          </Card>
        </>
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
      <Card
        size="small"
        style={{ marginBottom: 12 }}
        title={
          <Space size={8} wrap>
            <span>{a.display_name}</span>
            {a.细类 ? (
              <Tag color={SUBKIND_COLOR[a.细类] ?? 'default'} style={{ marginInlineEnd: 0 }}>
                {a.细类}
              </Tag>
            ) : null}
            {a.retired ? (
              <Tag color="default" style={{ marginInlineEnd: 0 }}>
                已退役
              </Tag>
            ) : null}
          </Space>
        }
        extra={
          <Button size="small" onClick={onBack}>
            返回一本账
          </Button>
        }
      >
        {a.code_name ? (
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 8px' }}>
            内部代号 <Typography.Text code>{a.code_name}</Typography.Text>
            <span style={{ marginInlineStart: 8 }}>册名显示取自 {a.display_from}</span>
          </Typography.Paragraph>
        ) : null}
        <Descriptions
          size="small"
          column={3}
          items={[
            { key: 'id', label: '册 id', children: <Typography.Text code>{a.id}</Typography.Text> },
            { key: 'kind', label: '类别', children: <Tag>{a.kind}</Tag> },
            {
              key: 'sub',
              label: '细类',
              children: a.细类 ? (
                <Tag color={SUBKIND_COLOR[a.细类] ?? 'default'}>{a.细类}</Tag>
              ) : (
                <Typography.Text type="secondary">细类列待上线</Typography.Text>
              ),
            },
            { key: 'st', label: '状态', children: <Tag color={ART_STATUS_COLOR[a.status] ?? 'default'}>{a.status}</Tag> },
            { key: 'line', label: '出自产线', children: a.source_line ?? '—' },
            { key: 'tpl', label: '模版', children: a.template_id ? <Link to={`/templates?tpl=${encodeURIComponent(a.template_id)}`}>{a.template_id}</Link> : '—' },
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

      <div className="kb-sec-title">
        卷/天列表（按册内序 ord）
        {a.papers.length ? (
          <Link
            to={`/papers?artifact_id=${encodeURIComponent(a.id)}`}
            style={{ fontSize: 12, marginInlineStart: 10, fontWeight: 400 }}
          >
            在卷库里看这本册的卷 →
          </Link>
        ) : null}
      </div>
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
