import { useMemo, useState } from 'react'
import { Alert, Button, Card, Empty, Input, Select, Space, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { Link } from 'react-router-dom'
import { PageFrame } from '@/components'
import type { Todo } from '@/mock'
import {
  NOW,
  allBatches,
  artifacts,
  findExamModel,
  findIngestBatch,
  findIngestTemplate,
  findQuestion,
  firstTextOf,
  openTodos,
  todoCountByLine,
  todos,
} from '@/mock'
import './style.css'

/**
 * 待办列表 /todo —— 归属：页面组 E。只改本目录。
 *
 * 🔴 这是一张**自由事项表**（定稿 D-14 todo 表）：想起什么记一笔，agent 也会往里写。
 *    与工作台的「待办视图」（从业务数据现算出来的该干的活：卡在人手上的批次）**不是一回事，两者并列不合并**。
 *
 * 🔴 本页**只读**：增删改走 agent/MCP 直接写库 —— 页面只有查看，永远不长「新建 / 编辑 / 删除」按钮。
 *
 * 🔴 时间一律取 mock 基准 NOW（2026-08-17），不用 Date.now()：走查两次看到的「已过期」必须一模一样。
 */

const LINES: Todo['line'][] = ['录入', '批改', '出题', '资料', '其他']
const STATUSES: Todo['status'][] = ['待办', '进行中', '已完成', '已取消']
const PRIORITIES: Todo['priority'][] = ['高', '中', '低']

/** 收起态（默认）不显示的两个状态 —— 干完的和不干的别占版面 */
const CLOSED_STATUSES: Todo['status'][] = ['已完成', '已取消']
const isClosed = (t: Todo) => CLOSED_STATUSES.includes(t.status)

/** mock 基准日：2026-08-17。过期判定按它算，不取系统时间 */
const TODAY = NOW.slice(0, 10)

/** 产线 → Tag 色（沿用判据沉淀那页的口径：录入蓝 / 批改青 / 出题紫，只用 antd 默认色板） */
const lineColor: Record<Todo['line'], string> = {
  录入: 'blue',
  批改: 'cyan',
  出题: 'purple',
  资料: 'gold',
  其他: 'default',
}

/** 状态 → Tag 色。已取消不给色，压成灰字 */
const statusColor: Record<Todo['status'], string | undefined> = {
  待办: 'default',
  进行中: 'blue',
  已完成: 'green',
  已取消: undefined,
}

/** 优先级 → Tag 色。低优先级不给色，免得三个标签一起抢眼 */
const priorityColor: Record<Todo['priority'], string | undefined> = {
  高: 'red',
  中: 'orange',
  低: undefined,
}

/** 默认排序：没做完的在前 → 优先级高的在前 → 截止早的在前 → 新记的在前 */
const STATUS_ORD: Record<Todo['status'], number> = { 进行中: 0, 待办: 1, 已完成: 2, 已取消: 3 }
const PRIORITY_ORD: Record<Todo['priority'], number> = { 高: 0, 中: 1, 低: 2 }

function byDefaultOrder(a: Todo, b: Todo): number {
  if (STATUS_ORD[a.status] !== STATUS_ORD[b.status]) return STATUS_ORD[a.status] - STATUS_ORD[b.status]
  if (PRIORITY_ORD[a.priority] !== PRIORITY_ORD[b.priority]) return PRIORITY_ORD[a.priority] - PRIORITY_ORD[b.priority]
  // 没定截止的排在有截止的后面（不是"最不急"，只是没定，所以放末尾而不是当今天算）
  const da = a.due ?? '9999-12-31'
  const db = b.due ?? '9999-12-31'
  if (da !== db) return da < db ? -1 : 1
  return b.createdAt.localeCompare(a.createdAt)
}

/** 到期状态。已完成 / 已取消的不再算过期 —— 事都结了，红字没有意义 */
type DueState = '无' | '已过期' | '今天到期' | '正常'

function dueStateOf(t: Todo): DueState {
  if (!t.due) return '无'
  if (isClosed(t)) return '正常'
  if (t.due < TODAY) return '已过期'
  if (t.due === TODAY) return '今天到期'
  return '正常'
}

/**
 * 关联指针解析。
 * 🔴 **能在库里查到对应记录才给跳**：假链接（点过去是空页 / 找不到）比不给链接更坏，
 *    查不到的一律留灰字 + 悬浮说明为什么点不动。
 */
type RefTarget = {
  /** 指针本身（原样显示，人对着它跟 agent 说话） */
  id: string
  /** 指向哪类东西，落在指针下面一行小字 */
  kind: string
  /** 能跳才给路由，不能跳就没有 */
  to?: string
  /** 悬浮说明：跳过去看到的是什么 / 为什么点不动 */
  hint: string
}

function resolveRef(pointer: string): RefTarget {
  // 题目 q-4003 → 题目详情
  if (pointer.startsWith('q-')) {
    const q = findQuestion(pointer)
    return q
      ? {
          id: pointer,
          kind: '题目',
          to: `/questions/${encodeURIComponent(pointer)}`,
          hint: `题目详情 · ${firstTextOf(q.blocks).slice(0, 40)}`,
        }
      : { id: pointer, kind: '题目', hint: '题库里查不到这道题（可能已退役），不给跳' }
  }
  // 录入批次 ib-002 → 录入记录页并定位到该批
  if (pointer.startsWith('ib-')) {
    const b = findIngestBatch(pointer)
    return b
      ? {
          id: pointer,
          kind: '录入批次',
          to: `/ingest?batch=${encodeURIComponent(pointer)}`,
          hint: `录入记录 · ${b.source}`,
        }
      : { id: pointer, kind: '录入批次', hint: '录入记录里查不到这一批，不给跳' }
  }
  // 录入模板 it-hekan → 录入线（模板库挂在录入记录页下）
  if (pointer.startsWith('it-')) {
    const t = findIngestTemplate(pointer)
    return t
      ? { id: pointer, kind: '录入模板', to: '/ingest', hint: `录入模板 · ${t.name}（模板库归录入线）` }
      : { id: pointer, kind: '录入模板', hint: '模板库里查不到这张模板，不给跳' }
  }
  // 批改批次 b-jd-3 → 学员页并定位到该批（只跳学员页会落在默认轨，等于断链）
  if (pointer.startsWith('b-')) {
    const row = allBatches().find((r) => r.batch.id === pointer)
    return row
      ? {
          id: pointer,
          kind: '批改批次',
          to: `/grading/${encodeURIComponent(row.student.code)}?batch=${encodeURIComponent(pointer)}`,
          hint: `批改批次 · ${row.student.code} ${row.track.name} 第 ${row.batch.dayInTrack} 天`,
        }
      : { id: pointer, kind: '批改批次', hint: '批改账本里查不到这一批，不给跳' }
  }
  // 成品 af-002 → 资料清单
  if (pointer.startsWith('af-')) {
    const a = artifacts.find((x) => x.id === pointer)
    return a
      ? { id: pointer, kind: '成品', to: '/artifacts', hint: `资料清单 · ${a.name}` }
      : { id: pointer, kind: '成品', hint: '资料清单里查不到这本，不给跳' }
  }
  // 考察模型 em-004 → 维护 · 考察模型
  if (pointer.startsWith('em-')) {
    const m = findExamModel(pointer)
    return m
      ? { id: pointer, kind: '考察模型', to: '/model', hint: `考察模型 · ${m.name}` }
      : { id: pointer, kind: '考察模型', hint: '模型库里查不到它，不给跳' }
  }
  // 判据 cr-012 → 真库里指向 criterion 表；本轮 mock 未收录这一条，故点不动
  if (pointer.startsWith('cr-')) {
    return {
      id: pointer,
      kind: '判据',
      hint: '真库里它指向判据表（criterion）；本轮 mock 没有这条记录，宁可点不动也不给假链接',
    }
  }
  return {
    id: pointer,
    kind: '未知类型',
    hint: '认不出这是什么指针（前缀不在 q- / ib- / it- / b- / af- / em- / cr- 之内），不给跳',
  }
}

/** 关联指针单元格：能跳的给链接，不能跳的虚线灰字 */
function RefCell({ pointer }: { pointer?: string }) {
  if (!pointer) return <Typography.Text type="secondary">—</Typography.Text>
  const target = resolveRef(pointer)
  return (
    <Tooltip title={target.hint}>
      <div>
        {target.to ? (
          <Link to={target.to}>{target.id}</Link>
        ) : (
          <Typography.Text type="secondary" style={{ textDecoration: 'underline dotted' }}>
            {target.id}
          </Typography.Text>
        )}
        <div className="td-sub">{target.kind}</div>
      </div>
    </Tooltip>
  )
}

export default function TodoPage() {
  // ── 筛选段（线 / 状态 / 优先级 / 关键词 + 收起开关）───────────────
  const [line, setLine] = useState<Todo['line'] | undefined>()
  const [status, setStatus] = useState<Todo['status'] | undefined>()
  const [priority, setPriority] = useState<Todo['priority'] | undefined>()
  const [keyword, setKeyword] = useState('')
  /** 🔴 默认隐藏已完成 / 已取消：这页是给人看「还欠什么」的 */
  const [showClosed, setShowClosed] = useState(false)

  /** 收起时把状态筛子里的已完成 / 已取消一并撤掉，避免留下必然筛空的组合 */
  const toggleClosed = (on: boolean) => {
    setShowClosed(on)
    if (!on && status && CLOSED_STATUSES.includes(status)) setStatus(undefined)
  }

  const resetAll = () => {
    setLine(undefined)
    setStatus(undefined)
    setPriority(undefined)
    setKeyword('')
    setShowClosed(false)
  }

  // 概览口径：未完成 = 待办 + 进行中（与菜单角标、工作台提示同一个 openTodos()）
  const open = openTodos()
  const byLine = todoCountByLine()
  const 高优先 = open.filter((t) => t.priority === '高').length
  const 已过期 = open.filter((t) => dueStateOf(t) === '已过期').length
  const 今天到期 = open.filter((t) => dueStateOf(t) === '今天到期').length
  const 已完成数 = todos.filter((t) => t.status === '已完成').length
  const 已取消数 = todos.filter((t) => t.status === '已取消').length

  const filtered = useMemo(() => {
    const kw = keyword.trim()
    return todos
      .filter((t) => {
        if (!showClosed && isClosed(t)) return false
        if (line && t.line !== line) return false
        if (status && t.status !== status) return false
        if (priority && t.priority !== priority) return false
        // 关键词同时搜标题 / 详情 / 指针：人记得住的往往是详情里那句人话，或者那个批次号
        if (kw && !`${t.title}${t.detail}${t.ref ?? ''}`.includes(kw)) return false
        return true
      })
      .sort(byDefaultOrder)
  }, [line, status, priority, keyword, showClosed])

  const 有筛子 = Boolean(line || status || priority || keyword.trim())

  const columns: ColumnsType<Todo> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, t) => (
        <div>
          <Typography.Text
            strong={!isClosed(t)}
            delete={t.status === '已取消'}
            type={isClosed(t) ? 'secondary' : undefined}
          >
            {title}
          </Typography.Text>
          <div className="td-sub">{t.id}</div>
        </div>
      ),
    },
    {
      title: '线',
      dataIndex: 'line',
      key: 'line',
      width: 78,
      render: (l: Todo['line']) => <Tag color={lineColor[l]}>{l}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 86,
      render: (s: Todo['status']) => (statusColor[s] ? <Tag color={statusColor[s]}>{s}</Tag> : <Tag>{s}</Tag>),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 84,
      render: (p: Todo['priority']) => (priorityColor[p] ? <Tag color={priorityColor[p]}>{p}</Tag> : <Tag>{p}</Tag>),
    },
    {
      title: '截止',
      dataIndex: 'due',
      key: 'due',
      width: 116,
      render: (due: string | undefined, t) => {
        const st = dueStateOf(t)
        if (!due) return <Typography.Text type="secondary">未定</Typography.Text>
        return (
          <div>
            <span style={{ color: st === '已过期' ? '#cf1322' : st === '今天到期' ? '#d46b08' : undefined }}>
              {due}
            </span>
            {st === '已过期' ? <div className="td-sub td-sub-over">已过期</div> : null}
            {st === '今天到期' ? <div className="td-sub td-sub-soon">今天到期</div> : null}
          </div>
        )
      },
    },
    {
      title: '关联指针',
      dataIndex: 'ref',
      key: 'ref',
      width: 148,
      render: (ref: string | undefined) => <RefCell pointer={ref} />,
    },
    {
      title: '谁记的',
      dataIndex: 'createdBy',
      key: 'createdBy',
      width: 92,
      render: (by: Todo['createdBy']) => (by === 'agent' ? <Tag color="geekblue">agent</Tag> : <Tag>人</Tag>),
    },
    {
      title: '时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 132,
      render: (createdAt: string, t) => (
        <div>
          <span>记于 {createdAt}</span>
          {t.doneAt ? (
            <div className="td-sub">
              {t.status === '已取消' ? '取消' : '完成'} {t.doneAt}
            </div>
          ) : null}
        </div>
      ),
    },
  ]

  return (
    <PageFrame
      title="待办列表"
      desc={
        <>
          一张<b>自由事项表</b>：想起什么记一笔，agent 也会往里写。与工作台那份「待办视图」
          （从业务数据现算出来的该干的活：卡在人手上的批次）<b>不是一回事，两者并列不合并</b>。
          🔴 本页只读：增删改走 agent/MCP 直接写库，页面只有查看。
        </>
      }
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          未完成 {open.length} / 共 {todos.length} 条（mock）
        </Typography.Text>
      }
    >
      {/* 只读说明：这页不长按钮，所以必须把「那我怎么加一条」写在最显眼处 */}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="要加待办：跟 agent 说一声就行"
        description={
          <ol style={{ margin: '4px 0 0', paddingInlineStart: 18, fontSize: 13, lineHeight: 1.9 }}>
            <li>
              <b>记一笔</b>：跟 agent 说「记个待办：……」，它直接写库；线 / 优先级 / 截止 / 关联指针由它填，
              你不用点表单。
            </li>
            <li>
              <b>干完了或者不做了</b>：同样说一声，它把状态改成「已完成」或「已取消」（都不删，留着可查）。
              所以本页从头到尾<b>没有新建 / 编辑 / 删除按钮</b>，这是定稿 D-14 的口径。
            </li>
            <li>
              <b>别跟工作台混</b>：工作台那份待办是机器现算的（哪个批次卡在人手上），没有表、也记不进去东西；
              本页是人和 agent 随手记的活儿与欠账，两边各看各的。
            </li>
          </ol>
        }
      />

      {/* 概览条：未完成的分布 + 已收起的条数（让人知道下面还藏着什么） */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Typography.Text style={{ fontSize: 12 }}>
          未完成 <b>{open.length}</b> 条 ｜ 按线：录入 {byLine.录入} · 批改 {byLine.批改} · 出题 {byLine.出题} · 资料{' '}
          {byLine.资料} · 其他 {byLine.其他} ｜ 高优先级 <b>{高优先}</b> ｜ 今天到期 {今天到期} · 已过期 {已过期}
        </Typography.Text>
        <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginTop: 4 }}>
          另有已完成 {已完成数} 条、已取消 {已取消数} 条，默认收起 —— 下面那个开关打开就能看。
        </div>
      </Card>

      {/* 筛选：线 / 状态 / 优先级 / 关键词 + 收起开关 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap size={8}>
          <Select
            placeholder="全部线"
            allowClear
            style={{ width: 120 }}
            value={line}
            onChange={setLine}
            options={LINES.map((l) => ({ value: l, label: l }))}
          />
          <Select
            placeholder="全部状态"
            allowClear
            style={{ width: 130 }}
            value={status}
            onChange={setStatus}
            // 收起态下只给「待办 / 进行中」：选了也必然筛空的选项不该出现在菜单里
            options={(showClosed ? STATUSES : STATUSES.filter((s) => !CLOSED_STATUSES.includes(s))).map((s) => ({
              value: s,
              label: s,
            }))}
          />
          <Select
            placeholder="全部优先级"
            allowClear
            style={{ width: 130 }}
            value={priority}
            onChange={setPriority}
            options={PRIORITIES.map((p) => ({ value: p, label: p }))}
          />
          <Input.Search
            placeholder="搜标题 / 详情 / 指针"
            allowClear
            style={{ width: 260 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={setKeyword}
          />
          <Space size={6}>
            <Switch size="small" checked={showClosed} onChange={toggleClosed} />
            <Typography.Text style={{ fontSize: 13 }}>显示已完成 / 已取消</Typography.Text>
          </Space>
          <Button onClick={resetAll} disabled={!有筛子 && !showClosed}>
            重置
          </Button>
        </Space>
      </Card>

      <Table<Todo>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={filtered}
        pagination={false}
        scroll={{ x: 1060 }}
        rowClassName={(t) => (isClosed(t) ? 'td-row-done' : dueStateOf(t) === '已过期' ? 'td-row-over' : '')}
        expandable={{
          // detail 是人话原文，逐条展开原样显示，不改写成术语
          expandedRowRender: (t) => {
            const target = t.ref ? resolveRef(t.ref) : null
            return (
              <div className="td-expand">
                <Typography.Paragraph className="td-detail">{t.detail}</Typography.Paragraph>
                <div className="td-meta">
                  {t.createdBy === 'agent' ? 'agent 记的' : '你记的'} · {t.createdAt}
                  {t.due ? ` ｜ 截止 ${t.due}` : ' ｜ 没定截止'}
                  {t.doneAt ? ` ｜ ${t.status === '已取消' ? '取消于' : '完成于'} ${t.doneAt}` : ''}
                  {target ? ` ｜ 关联 ${target.id}：${target.hint}` : ' ｜ 没挂关联指针'}
                </div>
              </div>
            )
          },
        }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                  {有筛子
                    ? '没有匹配的事项 —— 清掉筛子，或打开「显示已完成 / 已取消」再看看。'
                    : showClosed
                      ? '这张表还是空的。想起什么要干的，跟 agent 说一声就行，它直接写库。'
                      : '没有未完成的事项了 —— 欠的都清干净了。想起什么要干的，跟 agent 说一声就行，它直接写库。'}
                </Typography.Text>
              }
            />
          ),
        }}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}>
        排序口径：没做完的在前 → 优先级高的在前 → 截止早的在前 → 新记的在前（没定截止的排在有截止的后面）。
        <br />
        时间基准 = mock 写死的 {TODAY}，「已过期 / 今天到期」按它算、不取系统时间，所以每次走查看到的数字一样。
        <br />
        关联指针<b>能在库里查到对应记录才给跳</b>（题目→题目详情、录入批次→录入记录、批改批次→学员页对应批次、
        录入模板→录入线、成品→资料清单、考察模型→考察模型页）；查不到的保持虚线灰字点不动、鼠标停上去说明原因
        —— 假链接点过去是空页，比不给链接更坏。
      </Typography.Paragraph>
    </PageFrame>
  )
}
