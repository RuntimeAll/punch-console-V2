import { useEffect, useMemo, useState } from 'react'
import { Alert, Empty, Space, Spin, Table, Tabs, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link, useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { kbApi } from '@/kb/api'
import type { KbExamModel, KbKpRef, KbModels, KbPatternRow, KbSolutionModel } from '@/kb/types'

/**
 * 维护 · 考察模型 · 真库 /kb/models（PRD-007 线2 去 mock 第 2 页）
 *
 * 版面照搬 mock 页 /model 的三段式设计（三张名片 + 三个页签），数据换成真库：GET /api/kb/models。
 *
 * 三段各回答一句话，别混（数据结构 §2.1④）：
 * | 段 | 表 | 它是干嘛的 |
 * |---|---|---|
 * | 考察模型 | exam_model       | 这类题**怎么造**（出题 DSL 配方） |
 * | 题型目录 | question_pattern | 这类题**长什么样** —— 🔴 **对齐-003 起停用**，零行零写入 |
 * | 解题模型 | solution_model   | 这类题**怎么解**（举一反三地基，tier/freq 双旋钮） |
 *
 * 🔴 题型目录那张脸**如实显示「停用」**，不许拿别的东西把空表装满——
 *   停用后「这类题长什么样」归 kp.desc（考点自己的考法面），页面把去处指清楚，
 *   否则走查的人会以为「数据丢了」而不是「口径变了」。
 * 🔴 挂靠考点全部点得动 → /kb/kg?kp=<kp_id>（真库版溯源链）；断链（kp_ids_json 指了个不存在的 id）
 *   渲成灰色不可点，两种断法不糊成一种。
 */

const STATUS_COLOR: Record<string, string> = { 在用: 'green', 停用: 'default' }

/** 挂靠考点：点得动 = 树上有这片叶；灰字 = 断链（指了个库里没有的 kp id） */
function KpLinks({ kps }: { kps: KbKpRef[] }) {
  if (!kps.length) {
    return (
      <Typography.Text
        type="secondary"
        style={{ fontSize: 12 }}
        title="kp_ids_json 是空数组：这个模型说不出自己考的是哪片叶，溯源到这儿就断了"
      >
        未挂考点（溯源断点）
      </Typography.Text>
    )
  }
  return (
    <Space size={4} wrap>
      {kps.map((k) =>
        k.missing ? (
          <Tooltip key={k.id} title={`kp_ids_json 指向 ${k.id}，但 kp 表里没有这条——断链`}>
            <Tag style={{ marginInlineEnd: 0, color: 'rgba(0,0,0,0.38)', borderStyle: 'dashed' }}>
              {k.id} 已不在树上
            </Tag>
          </Tooltip>
        ) : (
          <Link key={k.id} to={`/kb/kg?kp=${encodeURIComponent(k.id)}`}>
            <Tag color="blue" style={{ marginInlineEnd: 0, cursor: 'pointer' }}>
              {k.name}
            </Tag>
          </Link>
        ),
      )}
    </Space>
  )
}

/** params_json 展开成「键：值」若干行（模型的正主是参数，不许被「…」吃掉） */
function ParamLines({ params, raw }: { params: Record<string, unknown> | null; raw: string | null }) {
  if (!params) {
    return raw ? (
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        params_json 解不开：{raw.slice(0, 60)}
      </Typography.Text>
    ) : (
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        没记参数
      </Typography.Text>
    )
  }
  if ('parse_error' in params) {
    return <span style={{ color: '#cf1322' }}>🔴 params_json 坏了：{String(params.parse_error)}</span>
  }
  return (
    <div style={{ fontSize: 13, lineHeight: 1.8 }}>
      {Object.entries(params).map(([k, v]) => (
        <div key={k}>
          <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineEnd: 6 }}>
            {k}
          </Typography.Text>
          <Typography.Text style={{ fontFamily: Array.isArray(v) ? 'monospace' : undefined, fontSize: 12.5 }}>
            {Array.isArray(v) ? v.join(' / ') : typeof v === 'object' ? JSON.stringify(v) : String(v)}
          </Typography.Text>
        </div>
      ))}
    </div>
  )
}

function ExamTable({ d }: { d: KbModels }) {
  const columns: ColumnsType<KbExamModel> = [
    {
      title: '模型名',
      key: 'name',
      width: 210,
      render: (_, m) => (
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            {m.name}
          </Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
              {m.id}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: '参数域（params_json 全展开）',
      key: 'params',
      render: (_, m) => (
        <div>
          <ParamLines params={m.params} raw={m.params_raw} />
          {m.note ? (
            <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
              备注：{m.note}
            </Typography.Text>
          ) : null}
        </div>
      ),
    },
    { title: '挂靠考点', key: 'kps', width: 220, render: (_, m) => <KpLinks kps={m.kps} /> },
    {
      title: '状态',
      dataIndex: 'status',
      width: 76,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'} style={{ marginInlineEnd: 0 }}>
          {s}
        </Tag>
      ),
    },
    {
      title: '已出题数',
      key: 'qc',
      width: 100,
      align: 'right',
      render: (_, m) => (
        <Tooltip title="现算于题的血缘：prov_json.model_id = 本模型 id 的题数（模型表不落冗余计数列）">
          <Typography.Text style={{ fontSize: 13 }}>{m.question_count} 道</Typography.Text>
        </Tooltip>
      ),
    },
    {
      title: 'DSL 指针',
      dataIndex: 'dsl_ref',
      width: 230,
      render: (s: string | null) =>
        s ? (
          <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace', wordBreak: 'break-all' }}>
            {s}
          </Typography.Text>
        ) : (
          <Tooltip title="没记 DSL 指针 = 这个模型说不出自己怎么造题，出题时只能凭印象重造">
            <span style={{ color: '#cf1322' }}>🔴 未记指针</span>
          </Tooltip>
        ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} size={6} wrap>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          它是干嘛的：<b>怎么造</b>这类题 —— 参数化出题配方，出题动作归 agent，本段只记账。
        </Typography.Text>
        <Tag style={{ marginInlineEnd: 0 }}>在用 {d.exam.in_use}</Tag>
        <Tag style={{ marginInlineEnd: 0 }}>共管 {d.exam.question_total} 道题</Tag>
        {d.trace_gap.exam_no_kp + d.trace_gap.exam_broken_kp > 0 ? (
          <Tag color="orange" style={{ marginInlineEnd: 0 }}>
            溯源断点 {d.trace_gap.exam_no_kp} 未挂考点 · {d.trace_gap.exam_broken_kp} 挂了不存在的叶
          </Tag>
        ) : (
          <Tag color="green" style={{ marginInlineEnd: 0 }}>
            溯源闸绿：每条都挂着树上找得到的叶
          </Tag>
        )}
      </Space>
      <Table<KbExamModel> rowKey="id" size="small" columns={columns} dataSource={d.exam.rows} pagination={false} />
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：DSL 指针指的是 agent 本地那份出题器源码（
        <Typography.Text code>工具箱/dsl/…_qbank.py</Typography.Text>）——系统只记指针不存代码，
        「怎么造」的真身永远在产线那边。挂靠考点点得动，落到知识图谱真库页那片叶。
      </Typography.Paragraph>
    </div>
  )
}

function SolutionTable({ d }: { d: KbModels }) {
  const columns: ColumnsType<KbSolutionModel> = [
    {
      title: '模型名',
      key: 'name',
      width: 190,
      render: (_, m) => (
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            {m.name}
          </Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
              {m.id}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      // 🔴 二元组同格渲：两半分列会让人以为是两个独立字段，实际是一句话的上下半句
      title: '怎么解（触发特征 → 动作结论）',
      key: 'pair',
      render: (_, m) => (
        <div style={{ fontSize: 13, lineHeight: 1.8 }}>
          <div>
            <Tag style={{ marginInlineEnd: 6 }}>触发</Tag>
            <Typography.Text>{m.trigger_feature}</Typography.Text>
          </div>
          <div style={{ color: 'rgba(0,0,0,0.35)', fontSize: 12, margin: '2px 0 2px 6px' }}>↓ 就这么做</div>
          <div>
            <Tag style={{ marginInlineEnd: 6 }}>结论</Tag>
            <Typography.Text>{m.action_conclusion}</Typography.Text>
          </div>
        </div>
      ),
    },
    { title: '挂靠考点（多值）', key: 'kps', width: 220, render: (_, m) => <KpLinks kps={m.kps} /> },
    {
      title: '双旋钮',
      key: 'knobs',
      width: 104,
      render: (_, m) => (
        <Space size={4} wrap>
          <Tooltip title="阶 = 模型复杂度（越高越难）">
            <Tag style={{ marginInlineEnd: 0, fontFamily: 'monospace' }}>阶 {m.tier ?? '—'}</Tag>
          </Tooltip>
          <Tooltip title="频 = 考频（越低越稀有，稀有 + 高阶 = 压轴）">
            <Tag style={{ marginInlineEnd: 0, fontFamily: 'monospace' }}>频 {m.freq ?? '—'}</Tag>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 76,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'} style={{ marginInlineEnd: 0 }}>
          {s}
        </Tag>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} size={6} wrap>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          它是干嘛的：这类题<b>怎么解</b> —— 举一反三的地基，没有它变式就退化成瞎换数字。
        </Typography.Text>
        <Tag style={{ marginInlineEnd: 0 }}>解题模型 {d.solution.total} 条</Tag>
        <Tooltip title="难度 = 阶（模型复杂度）+ 频（考频）由表算出来，LLM 只负责匹配到哪个模型，不自评难度">
          <Tag style={{ marginInlineEnd: 0 }}>难度=模型表驱动</Tag>
        </Tooltip>
      </Space>
      <Table<KbSolutionModel>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={d.solution.rows}
        pagination={false}
      />
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：库里现有 {d.solution.total} 条 —— 老区那 43 条金标模型的平移归 PRD-004（举一反三数据施工），
        本页只如实显示现在有几条，<b>不拿老区的数字充库存</b>。
      </Typography.Paragraph>
    </div>
  )
}

function PatternTable({ d }: { d: KbModels }) {
  const columns: ColumnsType<KbPatternRow> = [
    { title: '题型名', dataIndex: 'name', width: 220 },
    { title: '长什么样（desc）', dataIndex: 'desc' },
    { title: '锚考点', key: 'kps', width: 220, render: (_, m) => <KpLinks kps={m.kps} /> },
    { title: '状态', dataIndex: 'status', width: 76 },
  ]
  return (
    <div>
      {/* 🔴 停用的表就说停用：不拿 kp.desc 或别的什么把这张空表装满，那是页面在编事实 */}
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 12 }}
        message="题型目录（question_pattern）已停用 —— 对齐-003，2026-08-19 用户拍板"
        description={
          <div style={{ fontSize: 13, lineHeight: 1.9 }}>
            <div>{d.pattern.disabled_note}</div>
            <div style={{ marginTop: 6 }}>
              <Tag color={d.pattern.total === 0 ? 'green' : 'red'}>question_pattern 表 {d.pattern.total} 行</Tag>
              <Tag color={d.pattern.question_with_pattern_id === 0 ? 'green' : 'red'}>
                写了 pattern_id 的题 {d.pattern.question_with_pattern_id} 道
              </Tag>
              <Tag color="blue">接手它的 kp.desc 已写 {d.pattern.kp_desc_total} 片叶</Tag>
            </div>
            <div style={{ marginTop: 6 }}>
              去处：「这类题长什么样」现在看 <Link to="/kb/kg">知识图谱 · 真库</Link> 里每片叶的
              <b>考法描述</b>；「怎么造」仍看本页第一段考察模型。
            </div>
          </div>
        }
      />
      {d.pattern.total === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              零行 —— 这是<b>停用后的正常态</b>，不是数据没录（误立的 173 行 2026-08-19 已清空）。
            </Typography.Text>
          }
        />
      ) : (
        <Table<KbPatternRow> rowKey="id" size="small" columns={columns} dataSource={d.pattern.rows} pagination={false} />
      )}
    </div>
  )
}

const SEGS = ['exam', 'pattern', 'solution']

export function KbModelsPage() {
  const [d, setD] = useState<KbModels | null>(null)
  const [err, setErr] = useState('')
  // 🔴 段挂在 URL 的 ?seg= 上：三张脸各自可直链（走查/截图/从别的页指过来都要能直接落在那一段）
  const [searchParams, setSearchParams] = useSearchParams()
  const raw = searchParams.get('seg') ?? ''
  const tab = SEGS.includes(raw) ? raw : 'exam'
  const setTab = (k: string) => {
    const next = new URLSearchParams(searchParams)
    if (k === 'exam') next.delete('seg')
    else next.set('seg', k)
    setSearchParams(next, { replace: true })
  }

  useEffect(() => {
    kbApi
      .models()
      .then(setD)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [])

  const segments = useMemo(
    () => [
      {
        key: 'exam',
        name: '考察模型',
        one: '这类题怎么造',
        hint: '参数化出题配方（DSL）；出题动作归 agent，本页只记账',
        count: d ? `${d.exam.total} 条` : '—',
        off: false,
      },
      {
        key: 'pattern',
        name: '题型目录',
        one: '这类题长什么样',
        hint: '🔴 对齐-003 起停用：归 kp.desc，表零行零写入',
        count: d ? `${d.pattern.total} 条` : '—',
        off: true,
      },
      {
        key: 'solution',
        name: '解题模型',
        one: '这类题怎么解',
        hint: '举一反三的地基；难度=阶+频表驱动，LLM 只匹配不自评',
        count: d ? `${d.solution.total} 条` : '—',
        off: false,
      },
    ],
    [d],
  )

  return (
    <PageFrame
      title="维护 · 考察模型 · 真库"
      desc="低频维护区——日常不来，来了就是治理。这里放着「一类题」的三张脸：长什么样（题型目录·已停用）/ 怎么造（考察模型）/ 怎么解（解题模型）。数据直连 kb.db（exam_model / solution_model / question_pattern），页面只读。"
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {d ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              考察模型 {d.exam.total} · 解题模型 {d.solution.total} · 题型目录 {d.pattern.total}（停用）
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

      {/* 三张名片：一眼看清分工。🔴 禁大色块——只用最浅的边与底，选中那张靠加深边框区分 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        {segments.map((s) => {
          const on = s.key === tab
          return (
            <div
              key={s.key}
              onClick={() => setTab(s.key)}
              style={{
                flex: '1 1 240px',
                minWidth: 240,
                cursor: 'pointer',
                padding: '8px 12px',
                borderRadius: 4,
                background: on ? '#fafafa' : '#fff',
                border: `1px solid ${on ? '#bfbfbf' : '#f0f0f0'}`,
              }}
            >
              <div>
                <Typography.Text strong style={{ fontSize: 13 }} type={s.off ? 'secondary' : undefined}>
                  {s.name}
                </Typography.Text>
                <Tag style={{ marginInlineStart: 8, marginInlineEnd: 0 }}>{s.one}</Tag>
                <Tag style={{ marginInlineEnd: 0 }} color={s.off ? 'default' : 'blue'}>
                  {s.count}
                </Tag>
              </div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {s.hint}
              </Typography.Text>
            </div>
          )
        })}
      </div>

      {d ? (
        <Tabs
          activeKey={tab}
          onChange={setTab}
          items={[
            { key: 'exam', label: `考察模型（${d.exam.total}）`, children: <ExamTable d={d} /> },
            { key: 'pattern', label: `题型目录（停用 · ${d.pattern.total}）`, children: <PatternTable d={d} /> },
            { key: 'solution', label: `解题模型（${d.solution.total}）`, children: <SolutionTable d={d} /> },
          ]}
        />
      ) : err ? null : (
        <Spin />
      )}
    </PageFrame>
  )
}

export default KbModelsPage
