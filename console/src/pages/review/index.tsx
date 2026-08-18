import { useState } from 'react'
import { App as AntApp, Badge, Input, Modal, Result, Space, Tabs, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import type { ReviewKind, ReviewTicket } from '@/mock'
import { ticketsOfKind } from '@/mock'
import type { DoneMark } from './actions'
import { CLEARED_WORD, KINDS, nowText, tabFromParam } from './actions'
import { DoneList, FigureReviewCard, LowConfCard, PromoteCard, QuarantineCard } from './cards'
import './style.css'

/**
 * 录入 · 审核台 /review
 * 归属：页面组「录入」。只改本目录，别动 layout / mock / components。
 *
 * 这页管**题库的入口**：录进来的题谁来放行。
 * 🔴 与 /grading/queue 分工死死钉住：那边管**学生的卷子**（批完了谁拍板），
 *   这边管**题库的题**（录完了谁放行）。两条队列绝不合并成「全站待办」——
 *   归属不同、处理人不同、处理动作也不同。
 * 🔴 四类工单各有各的卡（图审并排看图 / 题审转正看整题 / 考点低置信摆候选 / 隔离行看原始记录），
 *   长得不一样是故意的：动作不同，卡就不该长一个样。
 * 🔴 处理动作是 **mock 本地状态**：点完卡进「已处理」折叠区，刷新页面回到初始。
 *   真放行、真改树、真重录全在 agent 侧，本页只出结论。
 *
 * 落地：支持 ?tab=图审|题审转正|考点低置信|隔离行（录入记录的红灯行就是这么链过来的）。
 */

/** 页签标题：类名 + 待处理角标（清零时压成灰 0，一眼看出哪类已经清了） */
function TabLabel({ kind, pending }: { kind: ReviewKind; pending: number }) {
  return (
    <Space size={6}>
      <span>{kind}</span>
      {pending > 0 ? (
        <Badge count={pending} size="small" />
      ) : (
        <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.35)' }}>0</span>
      )}
    </Space>
  )
}

/** 四类各配各的卡：这一层只做分发，卡本身在 cards.tsx */
function cardOf(
  t: ReviewTicket,
  onDone: (t: ReviewTicket, action: string, note?: string) => void,
  onAsk: (t: ReviewTicket, action: string, prompt: string) => void,
) {
  // 🔴 key 必须作为 JSX 属性单独写，不能塞进 props 对象里 spread 进去：
  // React 19 会告警「A props object containing a "key" prop is being spread into JSX」——
  // spread 进来的 key 无法被静态识别成列表 key，将来会彻底不认，列表 diff 会退化。
  const props = { t, onDone, onAsk }
  switch (t.kind) {
    case '图审':
      return <FigureReviewCard key={t.id} {...props} />
    case '题审转正':
      return <PromoteCard key={t.id} {...props} />
    case '考点低置信':
      return <LowConfCard key={t.id} {...props} />
    case '隔离行':
      return <QuarantineCard key={t.id} {...props} />
    default:
      return null
  }
}

function ReviewInner() {
  const { message } = AntApp.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = tabFromParam(searchParams.get('tab'))

  /** 本轮处理过的工单（mock 本地状态，刷新即失） */
  const [marks, setMarks] = useState<Record<string, DoneMark>>({})
  /** 需要写一句话才能落判的动作（驳回 / 废弃 / 定稿口径 / 改判重投）走这个弹窗 */
  const [ask, setAsk] = useState<{ t: ReviewTicket; action: string; prompt: string } | null>(null)
  const [note, setNote] = useState('')
  const [missing, setMissing] = useState(false)

  const onDone = (t: ReviewTicket, action: string, text?: string) => {
    setMarks((prev) => ({ ...prev, [t.id]: { action, note: text, at: nowText() } }))
    message.success(`${t.id} 已${action}（mock：只改本地状态，真动作在 agent 侧）`)
  }

  const onAsk = (t: ReviewTicket, action: string, prompt: string) => {
    setAsk({ t, action, prompt })
    setNote('')
    setMissing(false)
  }

  const submitAsk = () => {
    if (!ask) return
    if (note.trim() === '') {
      setMissing(true)
      return
    }
    onDone(ask.t, ask.action, note.trim())
    setAsk(null)
  }

  /** 每类页签的现况：待处理 / 已处理 */
  const groups = KINDS.map((kind) => {
    const all = ticketsOfKind(kind)
    return {
      kind,
      pending: all.filter((t) => !marks[t.id]),
      done: all.filter((t) => marks[t.id]),
    }
  })
  const pendingTotal = groups.reduce((n, g) => n + g.pending.length, 0)

  return (
    <PageFrame
      title="录入 · 审核台"
      desc="录进来的题在这里放行：配图核过没、草稿转不转正、考点低置信定哪个、隔离行怎么归位。四类工单各走各的处理动作，本页只出结论。"
      extra={
        <Space size={6} wrap>
          {groups.map((g) => (
            <Tag key={g.kind} color={g.pending.length === 0 ? 'green' : undefined} style={{ marginInlineEnd: 0 }}>
              {g.kind} {g.pending.length}
            </Tag>
          ))}
        </Space>
      }
    >
      <Tabs
        activeKey={tab}
        onChange={(k) => setSearchParams({ tab: k }, { replace: true })}
        items={groups.map((g) => ({
          key: g.kind,
          label: <TabLabel kind={g.kind} pending={g.pending.length} />,
          children: (
            <div>
              {g.pending.length === 0 ? (
                // 🔴 空态给贺词，不给「暂无数据」——清空了是件事，得说清是什么被清空了
                <Result
                  status="success"
                  title={`${g.kind} 清空了`}
                  subTitle={CLEARED_WORD[g.kind]}
                  style={{ paddingBlock: 24 }}
                />
              ) : (
                g.pending.map((t) => cardOf(t, onDone, onAsk))
              )}
              <DoneList tickets={g.done} marks={marks} />
            </div>
          ),
        }))}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}>
        待处理合计 {pendingTotal} 条。🔴 这条队列只管**题库的入口**（录完了谁放行）；学生卷子批完谁拍板在
        「批改 · 待办」，两条队列不合并。处理动作全是 mock 本地状态，刷新页面回到初始。
      </Typography.Paragraph>

      <Modal
        open={ask !== null}
        title={ask ? `${ask.action} · ${ask.t.id}` : ''}
        okText="确认"
        cancelText="取消"
        onOk={submitAsk}
        onCancel={() => setAsk(null)}
        destroyOnHidden
      >
        {ask ? (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Typography.Text style={{ fontSize: 13 }}>{ask.t.title}</Typography.Text>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {ask.prompt}
            </Typography.Text>
            <Input.TextArea
              rows={4}
              value={note}
              status={missing ? 'error' : undefined}
              onChange={(e) => {
                setNote(e.target.value)
                if (missing) setMissing(false)
              }}
              placeholder="写给下一个人看的：他要照着这句话动手"
            />
            {missing ? (
              <Typography.Text type="danger" style={{ fontSize: 12 }}>
                这一栏必填——不写清楚，工单等于没处理。
              </Typography.Text>
            ) : null}
          </Space>
        ) : null}
      </Modal>
    </PageFrame>
  )
}

/**
 * 外壳只做一件事：套 antd 的 <App>，让页内能用 useApp() 拿到带主题上下文的 message，
 * 不用静态 message.xxx（静态调用吃不到 ConfigProvider 的主题，控制台会告警）。
 */
export default function Review() {
  return (
    <AntApp component={false}>
      <ReviewInner />
    </AntApp>
  )
}
