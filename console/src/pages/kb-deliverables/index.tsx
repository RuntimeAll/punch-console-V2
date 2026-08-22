import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Card,
  Descriptions,
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
import { DELIVERABLE_KINDS, FILE_ROLE_COLOR, humanBytes, kbApi, kbFileUrl } from '@/kb/api'
import type { KbDeliverableRow, KbDeliverables } from '@/kb/types'
import '@/kb/kb.css'

/**
 * 成品速览 · 真库页 —— 一件成品文件一行，点行**直接预览**。
 *
 * 🔴 口径四条：
 *   ① 成品 = 挂了账的件，数据源＝ `artifact_file` 表（权威明细：一行一件带
 *      角色/字节/指纹/所属卷血缘），全部住在顶层 `成品库/`；库里没挂账的散件本页
 *      看不见——看不见就是没挂账，不是"页面漏了"。
 *   ② **只读**：预览走 `/api/kb/file`（服务端直吐字节，五道路径闸夹着），
 *      页面一个写按钮都没有，也不提供下载/删除/重命名。
 *   ③ 指针没归一进 `成品库/` 的行**如实标灰**（`previewable:false`）并说明原因，
 *      绝不给一个点下去 403 的死链接让人去猜是不是权限坏了。
 *   ④ 🔴 库里还没建 `artifact_file` 表时后端回落 `files_json` 兼容视图
 *      （`source==='files_json(兼容)'`）：本页顶部**明说**角色/血缘列不可用，
 *      角色筛子收起来——不静默摆一列空白让人以为"这批件都没标角色"。
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

// 组件名带 Page 后缀：`KbDeliverables` 这个名字已经是响应类型（types.ts），同名会撞
export function KbDeliverablesPage() {
  const [data, setData] = useState<KbDeliverables | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  // 🔴 筛选/分页/选中件全挂 URL（理由同题库页：直链可分享、走查可复现、跳转能选中）
  const [searchParams, setSearchParams] = useSearchParams()
  const type = searchParams.get('type') ?? ''
  const kind = searchParams.get('kind') ?? ''
  /** 角色多选：URL 上是逗号串（`?role=答案卷,题目卷`），与后端同一个写法 */
  const roleParam = searchParams.get('role') ?? ''
  const roles = useMemo(() => roleParam.split(',').map((s) => s.trim()).filter(Boolean), [roleParam])
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
      .deliverables({ ext: exts, role: roles, kind, q, page: pageNo, size: pageSize })
      .then((d) => {
        setData(d)
        setErr('')
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setLoading(false))
  }, [exts, roles, kind, q, pageNo, pageSize])

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

  /** 🔴 兼容视图＝这个库还没建 artifact_file 表：角色/大小/血缘三列没有真值可显示 */
  const compat = data?.source === 'files_json(兼容)'

  /** 角色筛子的选项：全量分组计数（来自后端 role_stat，不写死也不受当前筛选影响） */
  const roleOptions = useMemo(
    () => (data?.role_stat ?? []).map((s) => ({ value: s.value, label: `${s.value}（${s.count}）` })),
    [data],
  )

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
      // 🔴 角色列摆在类型前面：人先问的是「这是题目卷还是答案卷」，扩展名是次要信息
      title: '角色',
      dataIndex: 'role',
      width: 92,
      render: (v: string | null) =>
        v ? (
          <Tag color={FILE_ROLE_COLOR[v] ?? 'default'}>{v}</Tag>
        ) : (
          // 兼容视图下整列没值：写「待建表」而不是空白，空白会被读成"这件没标角色"
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {compat ? '待建表' : '未标'}
          </Typography.Text>
        ),
    },
    {
      title: '类型',
      dataIndex: 'ext',
      width: 78,
      render: (v: string) => <Tag color={EXT_COLOR[v] ?? 'default'}>{v.toUpperCase()}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'bytes',
      width: 88,
      align: 'right',
      render: (v: number | null) => (
        <Typography.Text style={{ fontSize: 12 }} type={v === null ? 'secondary' : undefined}>
          {humanBytes(v)}
        </Typography.Text>
      ),
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
          成品 = 挂了账的件（
          <Typography.Text code>{compat ? 'artifact.files_json' : 'artifact_file'}</Typography.Text>
          ），全部住在 <Typography.Text code>{data?.root ?? '成品库'}/</Typography.Text>——点任意一行直接预览
          （PDF 内嵌、图放大、md 读全文）。本页只读，不提供任何写动作。
        </>
      }
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {data ? <Tag color={compat ? 'orange' : 'blue'}>源 {data.source}</Tag> : null}
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

      {compat ? (
        // 🔴 如实告知不静默：这个库还没跑 artifact_file 的 DDL，角色/血缘列没有真值可显示
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="artifact_file 表尚未在本库建成，当前为兼容视图，角色/血缘列不可用"
          description={
            <>
              成品件明细正在从 <Typography.Text code>artifact.files_json</Typography.Text> 拉平（只有路径），
              角色（题目卷/答案卷/页图…）、文件大小、内容指纹、所属卷血缘四项要等主位执行
              <Typography.Text code>工具箱/库/apply_ddl_窗V成品件.py</Typography.Text> 建表回填之后才有。
              件数与预览不受影响。
            </>
          }
        />
      ) : null}

      {data && data.filters.role_invalid.length ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`角色筛子里有值域外的值：${data.filters.role_invalid.join('、')}`}
          description={`成品件角色的值域只有 ${data.role_domain.join(' / ')}，本次按 0 件返回（不当"没筛"把全量端出来）。`}
        />
      ) : null}

      {data && data.orphan_total > 0 ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${data.orphan_total} 件的所属册在库里查无此条（断链坏账）`}
          description="artifact_file 里有行、artifact 表里没有那本册。这些行标了「册已不在库」，请走 artifact_tool 清账。"
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
          {/* 🔴 角色筛子的选项来自后端 role_stat（不写死）；兼容视图下 role_stat 为空
              ⇒ 整个筛子收起来，不摆一个选了也筛不动的空下拉 */}
          {roleOptions.length ? (
            <Select
              allowClear
              mode="multiple"
              placeholder="角色（可多选）"
              style={{ minWidth: 220 }}
              maxTagCount="responsive"
              value={roles}
              onChange={(v: string[]) => setOne('role', (v ?? []).join(','))}
              options={roleOptions}
            />
          ) : null}
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
          scroll={{ x: 1234 }}
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
              {current.role ? (
                <Tag color={FILE_ROLE_COLOR[current.role] ?? 'default'}>{current.role}</Tag>
              ) : null}
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

      {/* 🔴 件级事实（角色/大小/血缘/指纹）——只有 artifact_file 表才有；缺的一项就不摆，
          不拿路径或册级字段凑一个假的顶上 */}
      <Descriptions
        size="small"
        column={2}
        style={{ marginBottom: 12 }}
        items={[
          {
            key: 'role',
            label: '角色',
            children: row.role ? (
              <Tag color={FILE_ROLE_COLOR[row.role] ?? 'default'}>{row.role}</Tag>
            ) : (
              <Typography.Text type="secondary">未建 artifact_file 表，取不到</Typography.Text>
            ),
          },
          { key: 'bytes', label: '大小', children: humanBytes(row.bytes) },
          {
            key: 'paper',
            label: '所属卷',
            children: row.paper_id ? (
              // 🔴 血缘：这件是哪张卷渲出来的——点进去直接展开那张卷的逐题明细
              // （卷库页的选中态挂在 ?paper=，别写成 ?id= 会打不开）
              <Link to={`/papers?paper=${encodeURIComponent(row.paper_id)}`}>{row.paper_id}</Link>
            ) : (
              <Typography.Text type="secondary">未记（不是每件都从卷渲出来）</Typography.Text>
            ),
          },
          {
            key: 'sha',
            label: '内容指纹',
            children: row.sha256 ? (
              <Tooltip title={row.sha256}>
                {/* 只摆前 12 位：够认「换没换过内容」，全串 64 位摆出来没人读 */}
                <Typography.Text code style={{ fontSize: 12 }}>
                  {row.sha256.slice(0, 12)}
                </Typography.Text>
              </Tooltip>
            ) : (
              <Typography.Text type="secondary">—</Typography.Text>
            ),
          },
        ]}
      />

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

export default KbDeliverablesPage
