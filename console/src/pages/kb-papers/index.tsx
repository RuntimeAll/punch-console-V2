import { useCallback, useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Segmented, Space, Spin, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link, useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { KbInline } from '@/kb/KbBlocks'
import { kbApi } from '@/kb/api'
import type { KbPaperDetail, KbPaperRow, KbPapers } from '@/kb/types'
import '@/kb/kb.css'

/**
 * 卷库 /papers（PRD-007 二轮页面线 第 3 件；2026-08-21 真库转正为正式页）
 * ═══════════════════════════════════════════════════════════════════════
 * 为什么单开一页：资料册页是**册**的视角（一本账 → 册 → 卷），可产线真正的作业单位是**卷**。
 * 「库里现在有哪些卷、每张多少题多少分、哪张还没记满分」这类问题，在册视角下要一本本点开才看得到。
 * 本页把 paper 拉平成一屏：列表（卷名 / 题数 / 满分 / 时长 / 所属册 / 建卷时间）+ 点开逐题预览。
 *
 * 数据：GET /api/kb/papers（列表）· GET /api/kb/papers/:id（逐题）。页面只读。
 *
 * 🔴 三条口径：
 *   ① **满分只认 `paper.layout_json.full_score`**。`paper_item.score` 实查全库为 NULL，
 *      拿逐题分值求和会得到 0——显示「满分 0 分」比显示「未记」坏得多。没记就写「未记」。
 *   ② **卷组卷进度不在这页判**：草稿/定稿是 paper.status 的原值，页面不替它推断"完没完"。
 *   ③ **断链如实标**：卷里指向已不在库的题（missing_count）标红，不静默按存活题数报数。
 */

const P_STATUS_COLOR: Record<string, string> = { 草稿: 'default', 定稿: 'green' }
const SUBKIND_COLOR: Record<string, string> = { 组卷册: 'blue', 发布包: 'purple', 历史册: 'default' }

export function KbPapersPage() {
  const [d, setD] = useState<KbPapers | null>(null)
  const [err, setErr] = useState('')
  const [detail, setDetail] = useState<KbPaperDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 🔴 筛选与选中全挂 URL：外面（资料册页的「在卷库里看」）要能直链进来
  const [searchParams, setSearchParams] = useSearchParams()
  const openId = searchParams.get('paper') ?? ''
  const artifactId = searchParams.get('artifact_id') ?? ''
  const kind = searchParams.get('kind') ?? ''

  const patch = useCallback(
    (k: string, v: string) => {
      const next = new URLSearchParams(searchParams)
      if (v) next.set(k, v)
      else next.delete(k)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  useEffect(() => {
    setD(null)
    kbApi
      .papers({ artifact_id: artifactId || undefined, kind: kind || undefined })
      .then(setD)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [artifactId, kind])

  useEffect(() => {
    if (!openId) {
      setDetail(null)
      return
    }
    setDetailLoading(true)
    setDetail(null)
    kbApi
      .paper(openId)
      .then((p) => {
        setDetail(p)
        setErr('')
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setDetailLoading(false))
  }, [openId])

  const kindOptions = useMemo(
    () => ['全部', ...(d?.kind_stat.map((k) => k.kind) ?? [])].map((k) => ({ label: k, value: k })),
    [d],
  )

  const columns: ColumnsType<KbPaperRow> = [
    {
      title: '卷名',
      dataIndex: 'title',
      width: 330,
      // 🔴 中文列给最小宽度：中文 min-content 宽 = 一个字，auto 布局会把它压成一行一个字
      render: (v: string, r) => (
        <div style={{ minWidth: 250 }}>
          <div>{v}</div>
          {r.subtitle ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {r.subtitle}
            </Typography.Text>
          ) : null}
        </div>
      ),
    },
    { title: '类别', dataIndex: 'kind', width: 88, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '题数',
      dataIndex: 'item_count',
      width: 92,
      render: (v: number, r) => (
        <span>
          {v}
          {r.missing_count > 0 ? (
            <Tag color="red" style={{ marginInlineStart: 4 }}>
              断链 {r.missing_count}
            </Tag>
          ) : null}
        </span>
      ),
    },
    {
      title: '满分',
      dataIndex: 'full_score',
      width: 82,
      // 没记就说没记（卷头 layout.full_score 为空），不拿 0 顶上
      render: (v: number | null) =>
        v == null ? <Typography.Text type="secondary">未记</Typography.Text> : `${v} 分`,
    },
    {
      title: '时长',
      dataIndex: 'duration_min',
      width: 82,
      render: (v: number | null) =>
        v == null ? <Typography.Text type="secondary">未记</Typography.Text> : `${v} 分钟`,
    },
    {
      title: '所属册',
      dataIndex: 'artifact_name',
      width: 190,
      render: (v: string | null, r) =>
        r.artifact_missing ? (
          <span style={{ color: '#cf1322' }}>🔴 断链：册 {r.artifact_id} 不在库</span>
        ) : v ? (
          <div style={{ minWidth: 140 }}>
            <Link to={`/artifacts`}>{v}</Link>
            {r.artifact_细类 ? (
              <Tag color={SUBKIND_COLOR[r.artifact_细类] ?? 'default'} style={{ marginInlineStart: 4 }}>
                {r.artifact_细类}
              </Tag>
            ) : null}
          </div>
        ) : (
          <Typography.Text type="secondary">未挂册</Typography.Text>
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 76,
      render: (v: string) => <Tag color={P_STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '建卷时间', dataIndex: 'created_at', width: 152 },
  ]

  return (
    <PageFrame
      title="卷库"
      desc="产线的作业单位是「卷」不是「册」——本页把 kb.db 的 paper 拉平成一屏：每张卷多少题、多少分、多长时间、归哪本册。点开看逐题（题面 / 题型难度 / 考点 / 状态）。页面只读，组卷走 工具箱/组卷/paper_tool.py。"
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {d ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {d.total} 卷 · 共 {d.item_total} 道题位
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
              起服务：<Typography.Text code>python 工具箱\启动台.py</Typography.Text>（:4310 读 API）
            </>
          }
        />
      ) : null}

      {openId ? (
        <PaperDetail detail={detail} loading={detailLoading} onBack={() => patch('paper', '')} />
      ) : (
        <>
          {/* 卷头账：记了满分/时长的有几张——如实摆出缺口，不填 0 冒充 */}
          {d && (d.with_full_score < d.total || d.with_duration < d.total) ? (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`卷头参数登记：满分 ${d.with_full_score}/${d.total} 张 · 时长 ${d.with_duration}/${d.total} 张`}
              description="满分与时长的落点是 paper.layout_json（渲染从库读的依据）。没登记的那几张在表里显示「未记」——这是真账不是页面 bug；逐题分值 paper_item.score 全库为空，所以满分不能靠求和补出来。"
            />
          ) : null}

          {artifactId ? (
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`只看册 ${artifactId} 的卷`}
              action={
                <Button size="small" onClick={() => patch('artifact_id', '')}>
                  看全部卷
                </Button>
              }
            />
          ) : null}

          <Card size="small">
            <Space size={10} wrap style={{ marginBottom: 10 }}>
              <span style={{ fontSize: 13 }}>卷类别</span>
              <Segmented
                size="small"
                value={kind || '全部'}
                onChange={(v) => patch('kind', String(v) === '全部' ? '' : String(v))}
                options={kindOptions}
              />
              {d ? (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {d.status_stat.map((s) => `${s.status} ${s.count}`).join(' · ')}
                </Typography.Text>
              ) : null}
            </Space>
            <Table
              rowKey="id"
              size="small"
              loading={d === null && !err}
              dataSource={d?.rows ?? []}
              columns={columns}
              scroll={{ x: 1092 }}
              onRow={(r) => ({ onClick: () => patch('paper', r.id), style: { cursor: 'pointer' } })}
              pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 卷` }}
              locale={{ emptyText: <Empty description="按当前筛选没有卷" /> }}
            />
          </Card>
        </>
      )}
    </PageFrame>
  )
}

/** 逐题预览：按 paper_item 序，题号 / 题面首块 / 题型难度 / 考点 / 状态 */
function PaperDetail({
  detail,
  loading,
  onBack,
}: {
  detail: KbPaperDetail | null
  loading: boolean
  onBack: () => void
}) {
  if (loading || !detail) {
    return (
      <Card size="small">
        <Spin />
      </Card>
    )
  }
  const cols: ColumnsType<KbPaperDetail['items'][number]> = [
    { title: '题号', dataIndex: 'ord', width: 62 },
    { title: '大题', dataIndex: 'section', width: 130, render: (v: string | null) => v ?? '—' },
    {
      title: '题面（首块截 120 字）',
      dataIndex: 'stem',
      width: 430,
      render: (v: string, r) => (
        <div style={{ minWidth: 320 }}>
          <KbInline md={v} />
          {r.missing ? <Tag color="red">🔴 题已不在库</Tag> : null}
        </div>
      ),
    },
    {
      title: '题型 / 难度',
      width: 130,
      render: (_, r) => (
        <Space size={4} wrap>
          {r.qtype_label ? <Tag style={{ marginInlineEnd: 0 }}>{r.qtype_label}</Tag> : null}
          {r.diff_label ? (
            <Tag color="geekblue" style={{ marginInlineEnd: 0 }}>
              {r.diff_label}
            </Tag>
          ) : null}
          {!r.qtype_label && !r.diff_label ? <Typography.Text type="secondary">—</Typography.Text> : null}
        </Space>
      ),
    },
    {
      title: '考点',
      width: 190,
      render: (_, r) =>
        r.kps.length ? (
          <div style={{ minWidth: 140 }}>
            {r.kps.map((k) =>
              k.missing ? (
                <Tag key={k.id ?? 'x'} color="red" style={{ marginBottom: 2 }}>
                  🔴 叶不在库
                </Tag>
              ) : (
                <Tag key={k.id ?? k.name ?? 'x'} color={k.is_primary ? 'purple' : 'default'} style={{ marginBottom: 2 }}>
                  {k.name}
                </Tag>
              ),
            )}
          </div>
        ) : (
          // 组卷闸要求题必须挂叶子，所以这里空 = 缺口，如实标
          <Typography.Text type="secondary">未挂考点</Typography.Text>
        ),
    },
    {
      title: '题状态',
      dataIndex: 'q_status',
      width: 82,
      render: (v: string | null) => (v ? <Tag>{v}</Tag> : '—'),
    },
    {
      title: '分值',
      dataIndex: 'score',
      width: 72,
      render: (v: number | null) => (v == null ? <Typography.Text type="secondary">未记</Typography.Text> : v),
    },
  ]

  return (
    <>
      <Card
        size="small"
        style={{ marginBottom: 12 }}
        title={
          <Space size={8} wrap>
            <span>{detail.title}</span>
            <Tag color={P_STATUS_COLOR[detail.status] ?? 'default'} style={{ marginInlineEnd: 0 }}>
              {detail.status}
            </Tag>
          </Space>
        }
        extra={
          <Button size="small" onClick={onBack}>
            返回卷库
          </Button>
        }
      >
        <Descriptions
          size="small"
          column={3}
          items={[
            { key: 'id', label: '卷 id', children: <Typography.Text code>{detail.id}</Typography.Text> },
            { key: 'kind', label: '类别', children: <Tag>{detail.kind}</Tag> },
            { key: 'n', label: '题数', children: `${detail.item_count} 道` },
            {
              key: 'fs',
              label: '满分',
              children: detail.full_score == null ? <Typography.Text type="secondary">卷头未记</Typography.Text> : `${detail.full_score} 分`,
            },
            {
              key: 'du',
              label: '时长',
              children: detail.duration_min == null ? <Typography.Text type="secondary">卷头未记</Typography.Text> : `${detail.duration_min} 分钟`,
            },
            { key: 'lay', label: '版式 key', children: detail.layout_key ?? '—' },
            {
              key: 'sec',
              label: '节数',
              children: detail.section_count == null ? '—' : `${detail.section_count} 节`,
            },
            {
              key: 'art',
              label: '所属册',
              children: detail.artifact ? (
                <Space size={4}>
                  <span>{detail.artifact.name}</span>
                  {detail.artifact.细类 ? (
                    <Tag color={SUBKIND_COLOR[detail.artifact.细类] ?? 'default'} style={{ marginInlineEnd: 0 }}>
                      {detail.artifact.细类}
                    </Tag>
                  ) : null}
                </Space>
              ) : (
                <Typography.Text type="secondary">未挂册</Typography.Text>
              ),
            },
            { key: 'ct', label: '建卷时间', children: detail.created_at ?? '—' },
          ]}
        />
        {detail.subtitle ? (
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '8px 0 0' }}>
            副标题：{detail.subtitle}
          </Typography.Paragraph>
        ) : null}
      </Card>

      <Card size="small" title={`逐题预览（按 paper_item 序，共 ${detail.items.length} 道）`}>
        <Table
          rowKey="ord"
          size="small"
          dataSource={detail.items}
          columns={cols}
          scroll={{ x: 1096 }}
          pagination={false}
          locale={{ emptyText: <Empty description="这卷没有题（paper_item 为空）" /> }}
        />
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
          要看整卷题面 + 答案 + 解析的「一天一屏」渲法，去
          <Link to="/artifacts"> 资料册 </Link>
          从册里点开这张卷。本页是卷级速览：一屏看清题号 / 题面 / 题型难度 / 考点 / 状态的配比。
        </Typography.Paragraph>
      </Card>
    </>
  )
}

export default KbPapersPage
