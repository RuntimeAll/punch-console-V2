import { useMemo, useState } from 'react'
import { App as AntApp, Button, Empty, Result, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { InboxOutlined, PartitionOutlined } from '@ant-design/icons'
import { Link, useSearchParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import type { BatchState, QueueRow } from '@/mock'
import { HUMAN_STATES, STATE_MACHINE, queueRows } from '@/mock'
import { stateHue, studentHref } from '@/pages/grading/batch-view'
import { IntakeModal, type IntakePayload } from './IntakeModal'
import { RowDetail, type TimelineEntry } from './RowDetail'
import { StateBar } from './StateBar'
import { StateMachineDrawer } from './StateMachineDrawer'
import { MOCK_CLOCK, RETRY_BACK_TO, STUCK_ALERT_MINUTES, bookRefOf, intakeRow, patchRow } from './queue-view'
import './style.css'

/**
 * 批改 · 队列 /grading/queue
 * 归属：页面组「批改」。只改本目录，别动 layout / mock / components。
 *
 * 🔴 判词①：**整条队列展示，状态外置明确**。
 *   队列不是「待办清单」——机器在飞的五格（收件中/待认卷/批改中/已确认/待出件）也全摆出来，
 *   让人一眼看见这条链跑到哪了；「该我动手」只是队列的一个筛子（?mine=1 → 三个人工态），
 *   所以旧的「待办」页删了，老链接 /grading/todo 重定向到这里。
 * 🔴 判词②：**收卷录入不配单开一页**，降格成右上角一个按钮 + 弹窗（IntakeModal）。
 *
 * 🔴 追加①：停留时长吃 row.stuckMinutes / row.stuckText（mock 按固定基准 NOW 算好），
 *   本页一个 Date.now() 都没有——走查时每次看到的数字一模一样。
 * 🔴 追加②：「该我动手」只认 HUMAN_STATES（= mock 的 pendingMine() 口径），
 *   本页不另列状态名；本地动作改过状态的行也照同一口径重算，所以直接过滤现态。
 *
 * 本地态（重试 / 指定卷子 / 收卷）全是 mock：只改本地 state + 留一行时间线，刷新回到初始。
 */

/** 队列表格一行的现态：mock 行 + 本页本地动作的覆盖 */
type Patch = { state: BatchState; note: string }

function QueueInner() {
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()

  // ── URL 参数（筛子要能分享）──────────────────────────────
  const mineOnly = searchParams.get('mine') === '1'
  const stateParam = searchParams.get('state')
  /** 脏值直接当没筛（不 cast，照状态机查一遍） */
  const stateFilter = STATE_MACHINE.find((m) => m.state === stateParam)?.state ?? null

  // ── 本地态 ───────────────────────────────────────────────
  const base = useMemo(() => queueRows(), [])
  const [patches, setPatches] = useState<Record<string, Patch>>({})
  const [intake, setIntake] = useState<QueueRow[]>([])
  const [timeline, setTimeline] = useState<Record<string, TimelineEntry[]>>({})
  const [picks, setPicks] = useState<Record<string, string>>({})
  const [expanded, setExpanded] = useState<string[]>([])
  const [intakeOpen, setIntakeOpen] = useState(false)
  const [docOpen, setDocOpen] = useState(false)

  /**
   * 现态行 = 新收的（置顶）+ mock 行（被本地动作改过的就换状态）。
   * 🔴 故意**不重排**：mock 已经排好（人的活 → 系统在飞 → 终态），
   *   本地动作后行留在原位、加一条蓝色左描边，比整表跳动好读；排序口径归 mock，不在页面里重写一份。
   */
  const rows: QueueRow[] = [
    ...intake,
    ...base.map((r) => {
      const p = patches[r.batchId]
      return p ? patchRow(r, p.state, p.note) : r
    }),
  ]

  const localIds = new Set<string>([...intake.map((r) => r.batchId), ...Object.keys(patches)])

  const counts: Record<string, number> = {}
  for (const m of STATE_MACHINE) counts[m.state] = 0
  for (const r of rows) counts[r.state] = (counts[r.state] ?? 0) + 1

  const mineCount = rows.filter((r) => HUMAN_STATES.includes(r.state)).length
  const flyingCount = rows.filter((r) => !HUMAN_STATES.includes(r.state) && r.state !== '已出件').length

  const visible = rows.filter(
    (r) => (!mineOnly || HUMAN_STATES.includes(r.state)) && (!stateFilter || r.state === stateFilter),
  )

  // ── 筛子 ────────────────────────────────────────────────
  const applyParams = (next: { mine?: boolean; state?: BatchState | null }) => {
    const mine = next.mine === undefined ? mineOnly : next.mine
    let st = next.state === undefined ? stateFilter : next.state
    // 「只看我的」+ 系统态筛子 = 必空表，没有意义：开开关时顺手把系统态筛子摘掉
    if (mine && st && !HUMAN_STATES.includes(st)) st = null
    const p: Record<string, string> = {}
    if (mine) p.mine = '1'
    if (st) p.state = st
    setSearchParams(p, { replace: true })
  }

  const pickState = (s: BatchState) => {
    if (stateFilter === s) {
      applyParams({ state: null })
      return
    }
    // 点系统态的格子时自动关掉「只看我的」，不然点了像没反应
    applyParams({ state: s, mine: HUMAN_STATES.includes(s) ? mineOnly : false })
  }

  // ── 本地动作 ────────────────────────────────────────────
  const addTimeline = (id: string, text: string) =>
    setTimeline((prev) => ({ ...prev, [id]: [...(prev[id] ?? []), { at: MOCK_CLOCK, text }] }))

  const openRow = (id: string) =>
    setExpanded((prev) => (prev.includes(id) ? prev.filter((k) => k !== id) : [...prev, id]))

  /** 🔴 故障重试：状态机出口写着「retry → 回原状态」，不是回到队首重跑 */
  const retry = (row: QueueRow) => {
    setPatches((prev) => ({
      ...prev,
      [row.batchId]: {
        state: RETRY_BACK_TO,
        note: `${MOCK_CLOCK} 人工点了重试：无头 session 重新领走，回到「${RETRY_BACK_TO}」（轮次不变）`,
      },
    }))
    addTimeline(row.batchId, `重试 → 回原状态「${RETRY_BACK_TO}」（mock：只改本地态）`)
    if (!expanded.includes(row.batchId)) openRow(row.batchId)
    message.success(`${row.batchId} 已重试：回原状态「${RETRY_BACK_TO}」`)
  }

  /** 待人工认卷：人指定是哪一张 → 交还给编排器（批改中） */
  const assign = (row: QueueRow) => {
    const pick = picks[row.batchId]
    if (!pick) {
      message.warning('先选一张：编排器多命中不敢自己定，得由人指定')
      return
    }
    setPatches((prev) => ({
      ...prev,
      [row.batchId]: { state: '批改中', note: `${MOCK_CLOCK} 人工认卷：指定为「${pick}」，已交回编排器` },
    }))
    addTimeline(row.batchId, `人工认卷 → ${pick}`)
    message.success('已指定卷子：这批进入「批改中」')
  }

  const submitIntake = (p: IntakePayload) => {
    const row = intakeRow(intake.length + 1, p.student, p.files, p.kind)
    setIntake((prev) => [row, ...prev])
    addTimeline(row.batchId, `人工收卷：${p.files.length} 张照片｜卷型 ${p.kind}`)
    setIntakeOpen(false)
    message.success(`已收 ${p.files.length} 张照片 · 90 秒判稳后进入「待认卷」`)
    // 新行是「收件中」（系统态）：正卡在别的筛子上就看不见它，顺手把筛子清了
    if (mineOnly || (stateFilter && stateFilter !== '收件中')) {
      applyParams({ mine: false, state: null })
      message.info('已切回整条队列，好让新收的这行看得见')
    }
  }

  // ── 表 ──────────────────────────────────────────────────
  const columns: ColumnsType<QueueRow> = [
    {
      title: '学员',
      dataIndex: 'student',
      width: 84,
      render: (code: string) => <Link to={studentHref(code)}>{code}</Link>,
    },
    {
      title: '轨（册子）',
      key: 'track',
      ellipsis: { showTitle: true },
      render: (_, r) => {
        const book = bookRefOf(r.trackId)
        return (
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13 }}>{r.track}</div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {book ?? '认卷后确定是哪本'}
            </Typography.Text>
          </div>
        )
      },
    },
    {
      title: '轨内天',
      key: 'day',
      width: 96,
      render: (_, r) => (
        <div>
          <div style={{ fontSize: 13 }}>{r.dayInTrack > 0 ? `第 ${r.dayInTrack} 天` : '待认卷后定'}</div>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {r.date}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: '状态',
      key: 'state',
      width: 158,
      render: (_, r) => (
        <Tooltip title={`${r.actor === '终态' ? '终态' : `${r.actor}推进`} · ${r.reason}`}>
          <div>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span className="gq-state-dot" style={{ background: stateHue(r.state) }} />
              <span style={{ fontSize: 13 }}>{r.state}</span>
              {localIds.has(r.batchId) ? (
                <Tag color="blue" style={{ marginInlineEnd: 0, fontSize: 11, lineHeight: '16px' }}>
                  本地
                </Tag>
              ) : null}
            </span>
            <div style={{ fontSize: 12, color: r.actor === '人' ? '#d46b08' : 'rgba(0,0,0,0.45)' }}>
              {r.actor === '人' ? '要你动手' : r.actor === '终态' ? '到头了' : '系统在飞'}
            </div>
          </div>
        </Tooltip>
      ),
    },
    {
      title: '停留',
      key: 'stuck',
      width: 108,
      render: (_, r) => {
        // 🔴 只渲 mock 算好的数，本页不碰时间
        const long = r.stuckMinutes !== null && r.stuckMinutes > STUCK_ALERT_MINUTES
        if (!long) {
          return <span style={{ fontSize: 13 }}>{r.stuckText}</span>
        }
        return (
          <Tooltip title={`已经超过 ${STUCK_ALERT_MINUTES / 60} 小时没往前走`}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#cf1322' }}>{r.stuckText}</span>
          </Tooltip>
        )
      },
    },
    {
      title: '存疑',
      dataIndex: 'doubts',
      width: 64,
      align: 'right',
      render: (n: number) =>
        n > 0 ? (
          <span style={{ color: '#d46b08', fontWeight: 500 }}>{n}</span>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: '机器初判',
      key: 'score',
      width: 82,
      align: 'right',
      render: (_, r) =>
        r.score ? (
          <span style={{ fontSize: 13 }}>
            {r.score.right}/{r.score.total}
          </span>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: '操作',
      key: 'op',
      width: 176,
      render: (_, r) => (
        // 整行点击 = 展开详情（expandRowByClick），所以操作区必须掐断冒泡，
        // 否则「指定卷子」会被行点击再 toggle 一次，两下抵消看着像按钮坏了
        <Space size={10} onClick={(e) => e.stopPropagation()}>
          {r.state === '待终审' ? (
            // 终审是学员页抽屉里的动作：带 ?batch= 过去自动开抽屉，不在队列上做二套终审
            <Link to={studentHref(r.student, r.batchId)}>去终审</Link>
          ) : null}
          {r.state === '待人工认卷' ? (
            <Button size="small" type="link" style={{ padding: 0 }} onClick={() => openRow(r.batchId)}>
              指定卷子
            </Button>
          ) : null}
          {r.state === '故障' ? (
            <Button size="small" type="link" danger style={{ padding: 0 }} onClick={() => retry(r)}>
              重试
            </Button>
          ) : null}
          <Link to={studentHref(r.student, r.batchId)}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              看这天
            </Typography.Text>
          </Link>
        </Space>
      ),
    },
  ]

  const rowClass = (r: QueueRow) => {
    if (r.state === '故障') return 'gq-row-fault'
    if (HUMAN_STATES.includes(r.state)) return 'gq-row-human'
    if (r.state === '已出件') return 'gq-row-done'
    if (localIds.has(r.batchId)) return 'gq-row-local'
    return ''
  }

  /** 空态分三种，各说各的话：全清了 / 这一格空 / 队列真空 */
  const emptyNode =
    mineOnly && rows.length > 0 ? (
      <Result
        status="success"
        title="没有要你动手的了"
        subTitle={`系统还在飞 ${flyingCount} 条（收件 / 认卷 / 批改 / 出件），机器自己会往前推。要看整条链，关掉上面的开关。`}
        style={{ paddingBlock: 20 }}
      />
    ) : stateFilter ? (
      <Empty
        description={
          <span>
            「{stateFilter}」这一格现在没有批次
            <br />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              空格子是好事：这一段没堵。再点一次那个格子取消筛选。
            </Typography.Text>
          </span>
        }
      />
    ) : (
      <Empty
        description={
          <span>
            队列是空的：还没收到任何卷子
            <br />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              右上角「收卷」放照片进来，链就从「收件中」跑起来了。
            </Typography.Text>
          </span>
        }
      />
    )

  return (
    <PageFrame
      title="批改 · 队列"
      desc="一条卷子从收件到出件整条链摆出来：机器在飞的也看得见，但只有三格该你动手（待人工认卷 / 待终审 / 故障）。"
      extra={
        <Space size={10} wrap>
          <Space size={6}>
            <Switch size="small" checked={mineOnly} onChange={(v) => applyParams({ mine: v })} />
            <Typography.Text style={{ fontSize: 13 }}>只看要我动手的</Typography.Text>
            <Tag color={mineCount > 0 ? 'orange' : undefined} style={{ marginInlineEnd: 0 }}>
              {mineCount}
            </Tag>
          </Space>
          <Button size="small" icon={<PartitionOutlined />} onClick={() => setDocOpen(true)}>
            状态机说明
          </Button>
          <Button size="small" type="primary" icon={<InboxOutlined />} onClick={() => setIntakeOpen(true)}>
            收卷
          </Button>
        </Space>
      }
    >
      <StateBar counts={counts} active={stateFilter} onPick={pickState} />

      <div style={{ margin: '10px 0 8px', fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
        点格子筛这一格（再点一次取消）；带红点的三格是人的活。
        当前看的是
        <b>
          {' '}
          {mineOnly ? '只要我动手的' : '整条队列'}
          {stateFilter ? ` · ${stateFilter}` : ''}{' '}
        </b>
        共 {visible.length} 行
        {stateFilter || mineOnly ? (
          <Button size="small" type="link" style={{ padding: '0 4px' }} onClick={() => applyParams({ mine: false, state: null })}>
            看全部
          </Button>
        ) : null}
      </div>

      <Table<QueueRow>
        rowKey="batchId"
        size="small"
        columns={columns}
        dataSource={visible}
        pagination={false}
        rowClassName={rowClass}
        locale={{ emptyText: emptyNode }}
        expandable={{
          expandedRowKeys: expanded,
          onExpandedRowsChange: (keys) => setExpanded(keys as string[]),
          expandRowByClick: true,
          columnWidth: 40,
          expandedRowRender: (r) => (
            <RowDetail
              row={r}
              pick={picks[r.batchId]}
              onPick={(name) => setPicks((prev) => ({ ...prev, [r.batchId]: name }))}
              onAssign={() => assign(r)}
              timeline={timeline[r.batchId]}
            />
          ),
        }}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        {/* 🔴 「近期已出件」与数字必须写在同一行：JSX 会把「文本 ↔ {表达式}」之间的换行+缩进整段吞掉，
            拆行就渲成「近期已出件5 条」，跟前面「在飞 5 条」的空格对不齐（走查已实测）。 */}
        整条队列 {rows.length} 行 = 在飞 {flyingCount} 条 + 该我动手 {mineCount} 条 + 近期已出件{' '}
        {rows.filter((r) => r.state === '已出件').length} 条（终态只留最近几条当尾巴，历史去学员页看）。
        每行都能展开：停留原因、出口、机器原话都在里面 —— 状态说明的正本是右上角「状态机说明」那九行。
        <br />
        走查提示：重试 / 指定卷子 / 收卷都是 <b>mock 本地态</b>（改本地状态 + 留一行时间线，行上打「本地」标），
        刷新页面回到初始；真动作全在 agent 侧。停留时长按 mock 固定基准时刻算好，本页不碰时钟，每次走查数字都一样。
      </Typography.Paragraph>

      <IntakeModal
        open={intakeOpen}
        onCancel={() => setIntakeOpen(false)}
        onSubmit={submitIntake}
        onWarn={(text) => message.warning(text)}
      />
      <StateMachineDrawer open={docOpen} onClose={() => setDocOpen(false)} />
    </PageFrame>
  )
}

/**
 * 外壳只做一件事：套 antd 的 <App>，让页内能用 useApp() 拿到带主题上下文的 message，
 * 不用静态 message.xxx（静态调用吃不到 ConfigProvider 的主题，控制台会告警）。
 */
export default function GradingQueue() {
  return (
    <AntApp component={false}>
      <QueueInner />
    </AntApp>
  )
}
