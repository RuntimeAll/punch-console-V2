import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Card,
  Drawer,
  Empty,
  Image,
  Input,
  Segmented,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link, useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { DELIVERABLE_KINDS, kbApi, kbFileUrl } from '@/kb/api'
import type { KbDeliverableRow, KbDeliverables } from '@/kb/types'
import '@/kb/kb.css'

/**
 * 成品速览 · 真库页 —— 一件成品文件一行，点行**直接预览**。
 *
 * 🔴 口径三条：
 *   ① 成品 = 挂了账的件（`artifact.files_json` 拉平），全部住在顶层 `成品库/`；
 *      库里没挂账的散件本页看不见——看不见就是没挂账，不是"页面漏了"。
 *   ② **只读**：预览走 `/api/kb/file`（服务端直吐字节，五道路径闸夹着），
 *      页面一个写按钮都没有，也不提供下载/删除/重命名。
 *   ③ 指针没归一进 `成品库/` 的行**如实标灰**（`previewable:false`）并说明原因，
 *      绝不给一个点下去 403 的死链接让人去猜是不是权限坏了。
 *
 * 🔴 筛选/分页/预览态全挂 URL（与题库页同一套口径）：一屏 = 一个可直接贴给人的链接，
 *   走查截图也能复现。
 */

const ART_STATUS_COLOR: Record<string, string> = { 在产: 'blue', 已交付: 'green', 已上架: 'gold', 退役: 'default' }
const EXT_COLOR: Record<string, string> = { pdf: 'red', png: 'blue', jpg: 'blue', jpeg: 'blue', md: 'green' }

/** 扩展名 → 预览方式（三条路：PDF 内嵌 / 图放大 / 文本读全文） */
type Viewer = 'pdf' | 'image' | 'text' | 'none'
function viewerOf(ext: string): Viewer {
  if (ext === 'pdf') return 'pdf'
  if (ext === 'png' || ext === 'jpg' || ext === 'jpeg') return 'image'
  if (ext === 'md') return 'text'
  return 'none'
}

export function KbDeliverables() {
  const [data, setData] = useState<KbDeliverables | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  // 🔴 筛选/分页/选中件全挂 URL（理由同题库页：直链可分享、走查可复现、跳转能选中）
  const [searchParams, setSearchParams] = useSearchParams()
  const type = searchParams.get('type') ?? ''
  const kind = searchParams.get('kind') ?? ''
  const q = searchParams.get('q') ?? ''
  const openFile = searchParams.get('file') ?? ''
  const pageNo = Math.max(1, Number(searchParams.get('page') || 1))
  const pageSize = Math.max(1, Number(searchParams.get('size') || 50))

  const patch = (fn: (p: URLSearchParams) => void, keepPage = false) => {
    const next = new URLSearchParams(searchParams)
    fn(next)
    if (!keepPage) next.delete('page')
    setSearchParams(next, { replace: true })
  }
  const setOne = (key: string, v: string) => patch((p) => (v ? p.set(key, v) : p.delete(key)))

  const [kwDraft, setKwDraft] = useState(q)
  useEffect(() => setKwDraft(q), [q])

  /** 「类型」档 → 后端要的扩展名多值（图 = png+jpg+jpeg 一次传三个） */
  const exts = useMemo(
    () => (DELIVERABLE_KINDS.find((k) => k.value === type)?.exts ?? []) as string[],
    [type],
  )

  const reload = useCallback(() => {
    setLoading(true)
    kbApi
      .deliverables({ ext: exts, kind, q, page: pageNo, size: pageSize })
      .then((d) => {
        setData(d)
        setErr('')
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [exts, kind, q, pageNo, pageSize])

  useEffect(reload, [reload])

  /** 打开的那一件（从当前页里找；翻页/换筛选后找不到就自动关抽屉） */
  const current = useMemo(
    () => (openFile ? (data?.rows.find((r) => r.file === openFile) ?? null) : null),
    [openFile, data],
  )

  /** 「类型」档的选项带全量计数（计数来自后端 ext_stat，不受当前筛选影响） */
  const typeOptions = useMemo(() => {
    const stat = new Map((data?.ext_stat ?? []).map((s) => [s.value, s.count]))
    const all = (data?.file_total ?? 0)
    return DELIVERABLE_KINDS
      // 库里一件都没有的类型不摆出来（摆个「图 0」会让人以为筛坏了）
      .filter((k) => !k.value || k.exts.some((e) => (stat.get(e) ?? 0) > 0))
      .map((k) => {
        const n = k.value ? k.exts.reduce((s, e) => s + (stat.get(e) ?? 0), 0) : all
        return { value: k.value, label: `${k.label} ${n}` }
      })
  }, [data])

  const columns: ColumnsType<KbDeliverableRow> = [
    {
      title: '文件',
      dataIndex: 'basename',
      width: 380,
      render: (_: string, r) => (
        <div style={{ minWidth: 300 }}>
          <div style={{ fontWeight: 600 }}>{r.basename}</div>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {r.file}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: '所属册',
      width: 260,
      render: (_, r) => (
        <div style={{ minWidth: 200 }}>
          {/* 🔴 点册名进资料册页并直接打开那本册（?id=），不是只跳到列表让人再找一遍 */}
          <Link to={`/artifacts?id=${encodeURIComponent(r.artifact_id)}`} onClick={(e) => e.stopPropagation()}>
            {r.artifact_name}
          </Link>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {r.artifact_code_name ?? r.artifact_id}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'ext',
      width: 78,
      render: (v: string) => <Tag color={EXT_COLOR[v] ?? 'default'}>{v.toUpperCase()}</Tag>,
    },
    { title: '册类别', dataIndex: 'kind', width: 92, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '册状态',
      dataIndex: 'status',
      width: 88,
      render: (v: string) => <Tag color={ART_STATUS_COLOR[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: '交付时间',
      dataIndex: 'delivered_at',
      width: 156,
      // 🔴 没记交付时间就写「未记」，不拿建账时间冒充（历史册普遍没记，冒充会把账做假）
      render: (v: string | null) =>
        v ?? <Typography.Text type="secondary" style={{ fontSize: 12 }}>未记</Typography.Text>,
    },
  ]

  return (
    <PageFrame
      title="成品速览"
      desc={
        <>
          成品 = 挂了账的件（<Typography.Text code>artifact.files_json</Typography.Text>），全部住在{' '}
          <Typography.Text code>{data?.root ?? '成品库'}/</Typography.Text>——点任意一行直接预览
          （PDF 内嵌、图放大、md 读全文）。本页只读，不提供任何写动作。
        </>
      }
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {data ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              共 {data.file_total} 件 · 分属 {data.artifact_total} 册
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
              起服务：<Typography.Text code>python 工具箱\启动台.py</Typography.Text>（kb 读 API :4310）
            </>
          }
        />
      ) : null}

      {data && data.outside_root_total > 0 ? (
        // 🔴 归一没做完的期间照实说：这些件点了会 403，不是页面坏了
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message={`还有 ${data.outside_root_total} 件的指针没归一进 ${data.root}/`}
          description={`成品件的读取白名单只认 ${data.root}/ 前缀（放宽一层等于把整个仓挂上 HTTP）。这些行会标灰、点不开，等成品库归一把 files_json 指过来即可预览。`}
        />
      ) : null}

      {data && data.bad_json.length ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${data.bad_json.length} 册的 files_json 解析不了（坏账，如实报）`}
          description={data.bad_json.map((b) => `${b.artifact_id} ${b.name}：${b.error}`).join('；')}
        />
      ) : null}

      <Card size="small">
        <Space wrap style={{ marginBottom: 10 }}>
          <Segmented
            value={type}
            onChange={(v) => setOne('type', String(v))}
            options={typeOptions}
          />
          <Select
            allowClear
            placeholder="册类别"
            style={{ width: 180 }}
            value={kind || undefined}
            onChange={(v) => setOne('kind', v ?? '')}
            options={(data?.kind_stat ?? []).map((k) => ({
              value: k.value,
              label: `${k.value}（${k.count}）`,
            }))}
          />
          <Input.Search
            allowClear
            placeholder="搜文件名 / 路径 / 册名"
            style={{ width: 320 }}
            value={kwDraft}
            onChange={(e) => setKwDraft(e.target.value)}
            onSearch={(v) => setOne('q', v.trim())}
            enterButton="找件"
          />
          <span style={{ color: 'rgba(0,0,0,0.45)' }}>
            当前筛出 {data?.total ?? 0} 件{data ? ` / 全库 ${data.file_total}` : ''}
          </span>
        </Space>

        <Table
          rowKey="file"
          size="small"
          loading={loading}
          dataSource={data?.rows ?? []}
          columns={columns}
          scroll={{ x: 1054 }}
          onRow={(r) => ({
            onClick: () => (r.previewable ? setOne('file', r.file) : undefined),
            style: {
              cursor: r.previewable ? 'pointer' : 'not-allowed',
              // 指针没归一的行标灰：一眼看出「这件现在点不开」
              background: r.previewable ? undefined : '#fafafa',
              color: r.previewable ? undefined : 'rgba(0,0,0,0.45)',
            },
          })}
          pagination={{
            current: data?.page ?? 1,
            pageSize: data?.size ?? pageSize,
            total: data?.total ?? 0,
            showSizeChanger: true,
            pageSizeOptions: [20, 50, 100, 200],
            onChange: (p, s) =>
              patch(
                (u) => {
                  u.set('page', String(p))
                  u.set('size', String(s))
                },
                true,
              ),
            showTotal: (t) => `共 ${t} 件`,
          }}
          locale={{ emptyText: <Empty description="按当前筛选，库里没有成品件" /> }}
        />
      </Card>

      <Drawer
        width="72%"
        open={!!openFile}
        onClose={() => setOne('file', '')}
        title={
          current ? (
            <Space size={8} wrap>
              <span>{current.basename}</span>
              <Tag color={EXT_COLOR[current.ext] ?? 'default'}>{current.ext.toUpperCase()}</Tag>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                所属册{' '}
                <Link to={`/artifacts?id=${encodeURIComponent(current.artifact_id)}`}>
                  {current.artifact_name}
                </Link>
              </Typography.Text>
            </Space>
          ) : (
            '预览'
          )
        }
      >
        {current ? (
          <FilePreview row={current} />
        ) : openFile ? (
          // 翻页/换筛选之后这一件不在当前结果里了——说清楚，不空着让人以为卡住
          <Empty description="这一件不在当前筛选结果里（换过筛子或翻过页），关掉抽屉重新点一行" />
        ) : null}
      </Drawer>
    </PageFrame>
  )
}

/** 三条预览路：PDF 内嵌 iframe / 图走 antd Image（可放大）/ md 拉文本按原样排 */
function FilePreview({ row }: { row: KbDeliverableRow }) {
  const url = kbFileUrl(row.file)
  const v = viewerOf(row.ext)
  const [text, setText] = useState<string | null>(null)
  const [textErr, setTextErr] = useState('')

  useEffect(() => {
    if (v !== 'text') return
    setText(null)
    setTextErr('')
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}：${(await r.text()).slice(0, 160)}`)
        return r.text()
      })
      .then(setText)
      .catch((e) => setTextErr(String(e.message ?? e)))
  }, [url, v])

  return (
    <>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 10 }}>
        <Tooltip title="服务端只放 成品库/ 下的 pdf/png/jpg/jpeg/md，越界一律 403">
          <Typography.Text code>{row.file}</Typography.Text>
        </Tooltip>
        {row.delivered_at ? <span style={{ marginInlineStart: 8 }}>交付于 {row.delivered_at}</span> : null}
        {row.source_line ? <span style={{ marginInlineStart: 8 }}>出自产线 {row.source_line}</span> : null}
      </Typography.Paragraph>

      {v === 'pdf' ? (
        <iframe src={url} style={{ width: '100%', height: '72vh', border: 0 }} title={row.basename} />
      ) : v === 'image' ? (
        <Image src={url} width="100%" alt={row.basename} />
      ) : v === 'text' ? (
        textErr ? (
          <Alert type="error" showIcon message="读不到这个文件" description={textErr} />
        ) : text === null ? (
          <Spin />
        ) : (
          // md 按原样排（本页是"看成品"不是"渲成品"，渲染归渲染出件那条线）
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, fontSize: 13 }}>{text}</pre>
        )
      ) : (
        <Alert
          type="warning"
          showIcon
          message="这个扩展名不在预览白名单里"
          description={`.${row.ext} 不在 pdf/png/jpg/jpeg/md 之内，服务端不放行。`}
        />
      )}
    </>
  )
}

export default KbDeliverables
