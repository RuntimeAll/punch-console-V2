import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Descriptions, Drawer, Empty, Segmented, Space, Spin, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { kbApi } from '@/kb/api'
import type { KbTemplate, KbTemplateLayer, KbTemplates } from '@/kb/types'

/**
 * 模版库 /templates（PRD-007 线2 去 mock 第 4 页；2026-08-21 真库转正为正式页，老 /export-preview 重定向到这）
 *
 * 版面照搬 mock 页 /export-preview（模版卡片货架 + 抽屉看参数全表），数据换成真库：GET /api/kb/templates。
 *
 * 🔴 这页**不是导出器、不是渲染器**，是模版的货架：渲染永远在 agent 本地跑（HTML → Chrome → PDF），
 *   系统只登记模版与样张。页面只读：不新建、不改参数、不生成 PDF。
 * 🔴 与 mock 页的硬差别：mock 那 6 张是**编的**（含一张内嵌 <SamplePaper> 假样张）；
 *   真库里现在是 {total} 张真模版，**样张一张都没登记**（template.sample_asset 全空）——
 *   页面必须如实说「样张待登记」，不许拿内嵌组件冒充样张（预览好看、打出来两样，正是这页要防的）。
 * 🔴 停用的模版不删：已经发出去的册子还是老版式，删了对不上账。
 *
 * ── 二轮改造：分层 + 引用链 ──────────────────────────────────────────────
 * 模版不是一堆平级的卡，是**三层叠起来**的：组件（一个槽怎么排）› 版式（一整页什么骨架）
 * › 配方（出哪套卷：选题规则 + 用哪张版式）。平铺成一列看不出「谁用谁」。
 * 🔴 层来自 `params.层`；没回填才按 id 约定倒推，并在卡上标「层待回填」——**推的就说是推的**。
 * 🔴 引用链**只画 params 里读得到的**：配方卡标「使用版式 X」（来自 params.layout），
 *   版式卡标「含组件 Y」（params 文本里点了名）。读不到就显示「引用未登记」，
 *   **绝不按常识写死一条关系**——出货时照着假引用核参数会真出错卷。
 */

const STATUS_COLOR: Record<string, string> = { 在用: 'green', 停用: 'default' }
type StatusFilter = '全部' | '在用' | '停用'

/** 三层的顺序与说明（自下而上：组件 → 版式 → 配方） */
const LAYERS: { key: KbTemplateLayer; desc: string }[] = [
  { key: '组件', desc: '一个槽位怎么排——选项列位、公式块这类。被版式引用，自己不单独出卷。' },
  { key: '版式', desc: '一整页什么骨架——纸张、边距、字号、节样式、题号规则。渲染骨架落在 punchkit layouts。' },
  { key: '配方', desc: '出哪套卷——选题规则（题量/难度配比/题源）+ 用哪张版式。出卷流水线照它取题。' },
]
const LAYER_COLOR: Record<string, string> = { 组件: 'cyan', 版式: 'blue', 配方: 'purple' }

/** params_json 展开成 Descriptions 行；嵌套对象/数组转成人读得懂的一行，不吐生 JSON 给人看 */
function paramItems(params: Record<string, unknown> | null) {
  if (!params) return []
  return Object.entries(params).map(([k, v]) => ({
    key: k,
    label: k,
    children: <ParamValue v={v} />,
  }))
}

function ParamValue({ v }: { v: unknown }) {
  if (v === null || v === undefined) return <Typography.Text type="secondary">—</Typography.Text>
  if (Array.isArray(v)) {
    return (
      <Space size={4} wrap>
        {v.map((x, i) => (
          <Tag key={i} style={{ marginInlineEnd: 0 }}>
            {typeof x === 'object' ? JSON.stringify(x) : String(x)}
          </Tag>
        ))}
      </Space>
    )
  }
  if (typeof v === 'object') {
    // 嵌套对象（如 exam_paper 的 边距mm / 字号pt / 坑位）：拆成「子键：值」若干行，比一坨 JSON 好读
    return (
      <div style={{ fontSize: 12.5, lineHeight: 1.85 }}>
        {Object.entries(v as Record<string, unknown>).map(([k2, v2]) => (
          <div key={k2}>
            <Typography.Text type="secondary" style={{ marginInlineEnd: 6 }}>
              {k2}
            </Typography.Text>
            {Array.isArray(v2) ? v2.join('；') : typeof v2 === 'object' ? JSON.stringify(v2) : String(v2)}
          </div>
        ))}
      </div>
    )
  }
  return <Typography.Text style={{ fontSize: 13 }}>{String(v)}</Typography.Text>
}

/** 引用链一行：「使用版式 X」/「含组件 Y」——文案随 ref.kind 变，来源随行标注 */
function RefLine({ t }: { t: KbTemplate }) {
  if (!t.refs.length) {
    return (
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        引用未登记（params 里没写它用哪张版式 / 含哪些组件）
      </Typography.Text>
    )
  }
  return (
    <Space size={4} wrap>
      {t.refs.map((r) => (
        <Tag
          key={`${r.kind}|${r.id}`}
          color={LAYER_COLOR[r.kind] ?? 'default'}
          style={{ marginInlineEnd: 0 }}
          title={`引用来源：${r.via}`}
        >
          {r.kind === '版式' ? '使用版式' : r.kind === '组件' ? '含组件' : '引用'} {r.name}
        </Tag>
      ))}
    </Space>
  )
}

/** 一张模版卡：名字 / 版本 / 状态 / 层 / 用途 / 适用册型 / 参数摘要 / 引用链 / 样张登记与否 */
function TemplateCard({ t, onOpen }: { t: KbTemplate; onOpen: () => void }) {
  const p = (t.params ?? {}) as Record<string, unknown>
  const brief: [string, string][] = [
    ['版式 key', String(p.layout ?? p.slot ?? '—')],
    ['纸张', String(p.纸张 ?? p['纸张'] ?? '—')],
    ['满分/题量', p.满分 != null || p.题量 != null ? `${p.满分 ?? '—'} 分 / ${p.题量 ?? '—'} 题` : '—'],
    ['结构', String(p.结构 ?? p.布局 ?? '—')],
  ]
  return (
    <Card
      size="small"
      hoverable
      onClick={onOpen}
      style={{ flex: '1 1 340px', minWidth: 320, cursor: 'pointer' }}
      title={
        <Space size={6} wrap>
          <span>{t.name ?? t.id}</span>
          <Tag style={{ marginInlineEnd: 0 }}>{t.version ?? '未标版本'}</Tag>
          {/* 🔴 推来的层必须自报是推的，别让人以为库里登记了 */}
          {t.层_待回填 ? (
            <Tag color="orange" style={{ marginInlineEnd: 0 }} title={`层来自：${t.层_from ?? '推不出来'}`}>
              层待回填
            </Tag>
          ) : null}
        </Space>
      }
      extra={
        <Tag color={STATUS_COLOR[t.status] ?? 'default'} style={{ marginInlineEnd: 0 }}>
          {t.status}
        </Tag>
      }
    >
      <Typography.Paragraph
        type="secondary"
        style={{ fontSize: 12.5, lineHeight: 1.8, margin: '0 0 8px' }}
        ellipsis={{ rows: 3 }}
      >
        {t.purpose ?? '没写用途'}
      </Typography.Paragraph>

      <div style={{ fontSize: 12.5, lineHeight: 1.9 }}>
        <div>
          <Typography.Text type="secondary" style={{ marginInlineEnd: 6 }}>
            适用
          </Typography.Text>
          {t.book_kinds ?? '—'}
        </div>
        {brief
          .filter(([, v]) => v !== '—')
          .map(([k, v]) => (
            <div key={k}>
              <Typography.Text type="secondary" style={{ marginInlineEnd: 6 }}>
                {k}
              </Typography.Text>
              <span style={{ wordBreak: 'break-all' }}>{v}</span>
            </div>
          ))}
      </div>

      <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #f0f0f0' }}>
        <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineEnd: 6 }}>
          引用
        </Typography.Text>
        <RefLine t={t} />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 10,
          paddingTop: 8,
          borderTop: '1px solid #f0f0f0',
        }}
      >
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t.sample_rel_path ? '样张已登记' : '样张待登记'} · 用它的册 {t.artifact_count} 本
        </Typography.Text>
        <Typography.Link style={{ fontSize: 12 }}>看参数与坑</Typography.Link>
      </div>
    </Card>
  )
}

export function KbTemplatesPage() {
  const [d, setD] = useState<KbTemplates | null>(null)
  const [err, setErr] = useState('')
  const [filter, setFilter] = useState<StatusFilter>('全部')
  // 🔴 打开哪张卡挂在 URL 的 ?tpl= 上：一张模版的参数全表要能直链（出货时对着链接核参数）
  const [searchParams, setSearchParams] = useSearchParams()
  const openId = searchParams.get('tpl') ?? ''
  const setOpenId = (id: string) => {
    const next = new URLSearchParams(searchParams)
    if (id) next.set('tpl', id)
    else next.delete('tpl')
    setSearchParams(next, { replace: true })
  }
  const current: KbTemplate | null = d?.rows.find((t) => t.id === openId) ?? null

  useEffect(() => {
    kbApi
      .templates()
      .then(setD)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [])

  const shown = useMemo(() => {
    if (!d) return []
    return filter === '全部' ? d.rows : d.rows.filter((t) => t.status === filter)
  }, [d, filter])

  return (
    <PageFrame
      title="模版库"
      desc="渲染永远在 agent 本地跑（HTML → Chrome → PDF），系统只登记模版与样张——本页不是渲染器，是模版的货架。数据直连 kb.db 的 template 表，页面只读：不新建、不改参数、不生成 PDF。"
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          <Segmented
            size="small"
            value={filter}
            onChange={(v) => setFilter(v as StatusFilter)}
            options={(['全部', '在用', '停用'] as StatusFilter[]).map((s) => ({ label: s, value: s }))}
          />
          {d ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              共 {d.total} 张 · 在用 {d.in_use} · 已登记样张 {d.with_sample} · 分层 组件{' '}
              {d.层_stat.组件} / 版式 {d.层_stat.版式} / 配方 {d.层_stat.配方}
              {d.层_未归 > 0 ? ` · 未归层 ${d.层_未归}` : ''}
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

      {d && d.with_sample === 0 ? (
        // 🔴 如实说：样张一张都没登记。不拿内嵌样张组件冒充（预览好看、打出来两样正是这页要防的事）
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${d.total} 张模版里样张登记数 = 0（template.sample_asset 全空）`}
          description="参数表和坑都登记齐了，样张图还没回来——agent 本地渲完一次把首页样张登记进 asset 表，这里才有图可看。在那之前照参数表核，别指望页面上能预览。"
        />
      ) : null}

      {d && d.层_待回填 > 0 ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`${d.层_待回填} 张模版的「层」是按 id 约定推出来的，不是登记的`}
          description="层的正本是 params.层。没回填的那几张卡上标着「层待回填」——主线回填后本页自动改用登记值，不需要改代码。"
        />
      ) : null}

      {!d ? (
        err ? null : (
          <Spin />
        )
      ) : shown.length === 0 ? (
        <Empty description={`没有「${filter}」的模版`} />
      ) : (
        <>
          {/* 三层分区：自下而上 组件 → 版式 → 配方。同层的卡并排，跨层靠分区分开 */}
          {LAYERS.map(({ key, desc }) => {
            const group = shown.filter((t) => t.层 === key)
            if (!group.length) return null
            return (
              <div key={key} style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
                  <Tag color={LAYER_COLOR[key]} style={{ marginInlineEnd: 0 }}>
                    {key}
                  </Tag>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {group.length} 张 —— {desc}
                  </Typography.Text>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                  {group.map((t) => (
                    <TemplateCard key={t.id} t={t} onOpen={() => setOpenId(t.id)} />
                  ))}
                </div>
              </div>
            )
          })}
          {/* 🔴 推不出层的不硬塞进某一层，单独一区如实摆 */}
          {shown.some((t) => t.层 === null) ? (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
                <Tag style={{ marginInlineEnd: 0 }}>未归层</Tag>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  params.层 没登记，id 也认不出来 —— 等人工归层，不猜
                </Typography.Text>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                {shown
                  .filter((t) => t.层 === null)
                  .map((t) => (
                    <TemplateCard key={t.id} t={t} onOpen={() => setOpenId(t.id)} />
                  ))}
              </div>
            </div>
          ) : null}
        </>
      )}

      <Card size="small" style={{ marginTop: 12 }} title="新模版怎么来">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', fontSize: 12.5 }}>
          <span>① agent 本地把版式调好（HTML → Chrome → PDF，反复出纸看效果）</span>
          <span style={{ color: 'rgba(0,0,0,0.25)' }}>→</span>
          <span>② 调稳了登记进 template 表（参数 + 坑 + 一页样张）</span>
          <span style={{ color: 'rgba(0,0,0,0.25)' }}>→</span>
          <span>③ 这里可见，出货时照着挑</span>
        </div>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
          登记动作归 agent（渲染出件 skill / 工具箱脚本），本页只读。模版停用了也不删——
          已经发出去的册子还是老版式，删了对不上账。
        </Typography.Paragraph>
      </Card>

      <Drawer
        title={current ? `${current.name ?? current.id} · ${current.version ?? ''}` : ''}
        width="min(940px, 94vw)"
        open={Boolean(current)}
        onClose={() => setOpenId('')}
        destroyOnHidden
      >
        {current ? (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="模版编号">
                <Typography.Text code>{current.id}</Typography.Text>
              </Descriptions.Item>
              <Descriptions.Item label="层">
                <Space size={6} wrap>
                  {current.层 ? (
                    <Tag color={LAYER_COLOR[current.层] ?? 'default'} style={{ marginInlineEnd: 0 }}>
                      {current.层}
                    </Tag>
                  ) : (
                    <Typography.Text type="secondary">未归层</Typography.Text>
                  )}
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    来自 {current.层_from ?? '推不出来'}
                    {current.层_待回填 ? '（待回填 params.层）' : ''}
                  </Typography.Text>
                </Space>
              </Descriptions.Item>
              <Descriptions.Item label="引用链">
                <RefLine t={current} />
              </Descriptions.Item>
              <Descriptions.Item label="用途">{current.purpose ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="适用册型">{current.book_kinds ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={STATUS_COLOR[current.status] ?? 'default'}>{current.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="登记来源">{current.registered_by ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="最近更新">{current.updated_at ?? '—'}</Descriptions.Item>
              <Descriptions.Item label="用它的资料册">{current.artifact_count} 本</Descriptions.Item>
            </Descriptions>

            <div className="kb-sec-title" style={{ margin: '14px 0 6px', fontSize: 13, fontWeight: 600 }}>
              版式参数全表（params_json 逐键展开）
            </div>
            {current.params && Object.keys(current.params).length ? (
              <Descriptions size="small" column={1} bordered items={paramItems(current.params)} />
            ) : (
              <Typography.Text type="secondary">这张模版没记参数（params_json 为空）</Typography.Text>
            )}

            <div style={{ margin: '14px 0 6px', fontSize: 13, fontWeight: 600 }}>口径与坑（pitfalls）</div>
            {current.pitfalls ? (
              <Typography.Paragraph style={{ fontSize: 13, lineHeight: 1.9, whiteSpace: 'pre-wrap' }}>
                {current.pitfalls}
              </Typography.Paragraph>
            ) : (
              <Typography.Text type="secondary">还没记坑 —— 踩过一次就该回来补一条。</Typography.Text>
            )}

            <div style={{ margin: '14px 0 6px', fontSize: 13, fontWeight: 600 }}>样张</div>
            {current.sample_rel_path ? (
              <Typography.Paragraph style={{ fontSize: 13 }}>
                已登记：<Typography.Text code>{current.sample_rel_path}</Typography.Text>
                <br />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  真身在 知识库/资产/ 下（相对路径指针）；展示台不做图床，看图去本地文件。
                </Typography.Text>
              </Typography.Paragraph>
            ) : (
              <div
                style={{
                  border: '1px dashed #d9d9d9',
                  borderRadius: 4,
                  background: '#fafafa',
                  padding: '18px 16px',
                  color: 'rgba(0,0,0,0.45)',
                  fontSize: 12.5,
                  lineHeight: 1.9,
                }}
              >
                <b style={{ color: 'rgba(0,0,0,0.65)' }}>样张待 agent 渲染登记</b>
                <br />
                这张模版的 HTML 在 agent 本地调好后跑一次 Chrome 出 PDF，再把首页样张登记回 asset 表
                （template.sample_asset），这里才有图可看。页面自己不渲染、不出 PDF —— 参数表已经登记了，先照表核。
              </div>
            )}
          </>
        ) : null}
      </Drawer>
    </PageFrame>
  )
}

export default KbTemplatesPage
