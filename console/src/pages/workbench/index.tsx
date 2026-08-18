import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { Card, Col, List, Row, Space, Statistic, Tag, Timeline, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { PageFrame } from '@/components'
import type { BatchState } from '@/mock'
import { allBatches, artifacts, hasFigureIn, kpNameOf, pendingBatches, questions } from '@/mock'

/**
 * 工作台 /
 * 归属：页面组「工作台」。只改本文件与本目录，别动 layout / mock / components。
 *
 * 这页只回答一句话：**今天有什么要我处理的**。
 * 上面四张卡是当前存量（点一下就跳到对应页），下面左边是待办、右边是最近发生了什么。
 * 🔴 不做生产管理 / 任务队列 / 系统监控——那些归 agent，不上展示台。
 * 🔴 铁律③：跨轨只做计数（几条轨、几批待办），绝不跨轨算平均分；每条待办行必须带轨名。
 */

/** 待办行的视图模型（页面自用，不是数据契约） */
type TodoRow = {
  key: string
  /** 待办类别：批改的三个人工态（认卷/终审/故障）+ 图审 = 题目录入后要人眼核对 */
  cat: '认卷' | '终审' | '故障' | '图审'
  catColor: string
  title: ReactNode
  desc: string
  action: string
  to: string
}

/** 🔴 批改人工态 → 待办类别 / 动作词（九态里只有这三态该我动手，其余机器在跑不上待办） */
const 人工态视图: Record<string, { cat: TodoRow['cat']; color: string; action: string }> = {
  待终审: { cat: '终审', color: 'orange', action: '去终审' },
  待人工认卷: { cat: '认卷', color: 'gold', action: '去认卷' },
  故障: { cat: '故障', color: 'red', action: '去处理' },
}

/** 九态 → 动态流里的一句人话（照 STATE_MACHINE 的语义写，别自造说法） */
const 状态动作: Record<BatchState, string> = {
  收件中: '照片已收，判稳中',
  待认卷: '排队等认卷',
  待人工认卷: '撞库多命中，等人工认卷',
  批改中: '批改进行中',
  待终审: '批改完成，待终审',
  已确认: '判定定稿',
  待出件: '已确认，等出件',
  已出件: '已出件',
  故障: '异常挂起，等 retry',
}

/** 动态流的一条 */
type Event = {
  date: string
  cat: '批改' | '资料' | '录入'
  color: string
  text: string
  to: string
}

const 日期倒序 = (a: { date: string }, b: { date: string }) => b.date.localeCompare(a.date)

export default function Workbench() {
  const navigate = useNavigate()

  // ── 四张统计卡的口径 ────────────────────────────────────
  // 🔴 pendingBatches() = 卡在人手上的三态（待人工认卷 / 待终审 / 故障），机器在飞的不上待办
  const pending = pendingBatches()
  const 待终审数 = pending.filter((r) => r.batch.state === '待终审').length
  const 其他人工数 = pending.length - 待终审数

  const 在产数 = artifacts.filter((a) => a.status === '在产').length
  const 已交付数 = artifacts.filter((a) => a.status === '已交付').length
  const 已上架数 = artifacts.filter((a) => a.status === '已上架').length

  // 🔴 状态四态：上架 = 前台看得见的；草稿 = ingest 入了但没 promote，看不见
  const 在用题数 = questions.filter((q) => q.status === '上架').length
  const 草稿题数 = questions.filter((q) => q.status === '草稿').length

  /** 最近一次出件（按天取最新的「已出件」批次；只取一条，不跨轨算任何分数） */
  const 最近出件 = useMemo(
    () =>
      allBatches()
        .filter((r) => r.batch.state === '已出件')
        .sort((a, b) => 日期倒序({ date: a.batch.date }, { date: b.batch.date }))[0],
    [],
  )

  // ── 左列：待你处理 ──────────────────────────────────────
  const todoRows = useMemo<TodoRow[]>(() => {
    // ① 批改待办：待终审排前，其余人工态在后；🔴 每行都带轨名，不允许只写学员
    const 批改行 = [...pending]
      .sort((a, b) => {
        if (a.batch.state !== b.batch.state) return a.batch.state === '待终审' ? -1 : 1
        return 日期倒序({ date: a.batch.date }, { date: b.batch.date })
      })
      .map<TodoRow>(({ student, track, batch }) => {
        const 视图 = 人工态视图[batch.state] ?? { cat: '终审' as const, color: 'orange', action: '去处理' }
        return {
          key: batch.id,
          cat: 视图.cat,
          catColor: 视图.color,
          title: `${student.code} · ${track.name} 第 ${batch.dayInTrack} 天`,
          desc:
            batch.state === '待终审'
              ? `${batch.date} · 机批 ${batch.score?.right ?? 0}/${batch.score?.total ?? 0} · ${batch.doubts ?? 0} 题存疑，等人工拍板`
              : `${batch.date} · ${batch.note ?? 状态动作[batch.state]}`,
          action: 视图.action,
          // 🔴 必须带 ?batch=：学员页据此自动切到对应轨并弹开该批次抽屉，
          //    与 /grading/queue 的跳法保持同一条链路（只跳学员页会落在默认轨，等于断链）
          to: `/grading/${encodeURIComponent(student.code)}?batch=${encodeURIComponent(batch.id)}`,
        }
      })

    // ② 图审待办（样例）：mock 题目没有独立的「审核状态」字段，
    //    这里用 status=草稿（还没 promote）+ 含配图的题（图文要与原卷核对）推导出几条，
    //    走查通过后再决定要不要给 Question 补 reviewState 字段。
    const 草稿行 = questions
      .filter((q) => q.status === '草稿')
      .map<TodoRow>((q) => ({
        key: q.id,
        cat: '图审',
        catColor: 'default',
        title: `题目 ${q.id} · ${q.kps[0] ? kpNameOf(q.kps[0].kpId) : '未挂考点'}`,
        desc: `${q.sourceRaw} · 录入时挂起：条件疑似不足，答案与解析待补`,
        action: '去复核',
        to: `/questions/${q.id}`,
      }))

    const 配图行 = questions
      .filter((q) => q.status === '上架' && hasFigureIn(q.blocks))
      .slice(0, 2)
      .map<TodoRow>((q) => ({
        key: `fig-${q.id}`,
        cat: '图审',
        catColor: 'default',
        title: `题目 ${q.id} 配图待核对`,
        desc: `${q.sourceRaw} · 题面含配图，需核对是否与原卷同一位置混排`,
        action: '看题面',
        to: `/questions/${q.id}`,
      }))

    return [...批改行, ...草稿行, ...配图行]
  }, [pending])

  // ── 右列：最近动态 ──────────────────────────────────────
  const events = useMemo<Event[]>(() => {
    const 批改事件 = allBatches().map<Event>(({ student, track, batch }) => {
      const 动作 = 状态动作[batch.state]
      const 分数 = batch.score ? `（${batch.score.right}/${batch.score.total}）` : ''
      return {
        date: batch.date,
        cat: '批改',
        color: 'blue',
        text: `${student.code} · ${track.name} 第 ${batch.dayInTrack} 天 ${动作}${分数}`,
        // 同上：动态流点进去要落到**那一天**，不是学员页首屏
        to: `/grading/${encodeURIComponent(student.code)}?batch=${encodeURIComponent(batch.id)}`,
      }
    })

    const 资料事件 = artifacts
      .filter((a) => a.deliveredAt)
      .map<Event>((a) => ({
        date: a.deliveredAt as string,
        cat: '资料',
        color: 'green',
        text: `《${a.name}》${a.status}`,
        to: '/artifacts',
      }))

    // 🔴 录入事件是**页面级 mock**：Question 上没有录入时间字段，
    //    动态流要按天排序就得有日期，先在这里造两条占位，走查后再决定给类型补 createdAt。
    const 录入事件: Event[] = [
      {
        date: '2026-08-14',
        cat: '录入',
        color: 'gray',
        text: '四上·空间与图形单元卷 录入 5 题（1 题挂草稿待复核）',
        to: '/questions',
      },
      {
        date: '2026-08-11',
        cat: '录入',
        color: 'gray',
        text: '四上·思维拓展讲义 录入 3 题，配图随题面原位混排',
        to: '/questions',
      },
    ]

    return [...批改事件, ...资料事件, ...录入事件].sort(日期倒序).slice(0, 9)
  }, [])

  /** 统计卡：整张卡可点，落到对应页面 */
  const statCard = (title: string, value: ReactNode, foot: string, to: string) => (
    <Card size="small" hoverable onClick={() => navigate(to)} style={{ cursor: 'pointer' }}>
      <Statistic title={title} value={value as string | number} valueStyle={{ fontSize: 24 }} />
      <div style={{ marginTop: 6, fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{foot}</div>
    </Card>
  )

  return (
    <PageFrame
      title="工作台"
      desc="今天有什么要我处理：待终审的批次、在产的资料、题库存量、最近一次出件。"
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          数据为 mock；四张卡与每条待办都可点，用来走查跳转路径
        </Typography.Text>
      }
    >
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={6}>
          {statCard(
            '待终审',
            `${待终审数} 批`,
            其他人工数 > 0 ? `另有 ${其他人工数} 批要人工处理 · 点击进队列` : '点击进队列',
            '/grading/queue?mine=1',
          )}
        </Col>
        <Col span={6}>
          {statCard('在产资料', `${在产数} 条`, `已交付 ${已交付数} · 已上架 ${已上架数}`, '/artifacts')}
        </Col>
        <Col span={6}>
          {statCard('题库总量', `${questions.length} 道`, `在用 ${在用题数} · 草稿 ${草稿题数}`, '/questions')}
        </Col>
        <Col span={6}>
          {statCard(
            '最近出件',
            最近出件 ? 最近出件.batch.date : '—',
            最近出件
              ? `${最近出件.student.code} · ${最近出件.track.name} 第 ${最近出件.batch.dayInTrack} 天`
              : '暂无出件记录',
            最近出件
              ? `/grading/${encodeURIComponent(最近出件.student.code)}?batch=${encodeURIComponent(最近出件.batch.id)}`
              : '/grading',
          )}
        </Col>
      </Row>

      <Row gutter={12}>
        {/* 左：待你处理 —— 批改终审 + 题目图审混在一个清单里，按「该我动手」排 */}
        <Col span={15}>
          <Card
            size="small"
            title="待你处理"
            extra={<Link to="/grading/queue?mine=1">去队列</Link>}
            styles={{ body: { paddingTop: 0, paddingBottom: 0 } }}
          >
            <List
              size="small"
              dataSource={todoRows}
              locale={{ emptyText: '没有待办' }}
              renderItem={(r) => (
                <List.Item style={{ cursor: 'pointer' }} onClick={() => navigate(r.to)}>
                  <List.Item.Meta
                    title={
                      <Space size={8}>
                        <Tag color={r.catColor} style={{ marginInlineEnd: 0 }}>
                          {r.cat}
                        </Tag>
                        <span style={{ fontWeight: 500 }}>{r.title}</span>
                      </Space>
                    }
                    description={<span style={{ fontSize: 12 }}>{r.desc}</span>}
                  />
                  <Typography.Link>{r.action}</Typography.Link>
                </List.Item>
              )}
            />
          </Card>
        </Col>

        {/* 右：最近动态 —— 出件 / 交付 / 录入 按天倒序 */}
        <Col span={9}>
          <Card
            size="small"
            title="最近动态"
            extra={
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                近 {events.length} 条
              </Typography.Text>
            }
          >
            <Timeline
              style={{ paddingTop: 4 }}
              items={events.map((e, i) => ({
                key: i,
                color: e.color,
                children: (
                  <div>
                    <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
                      {e.date} · {e.cat}
                    </div>
                    <Typography.Link onClick={() => navigate(e.to)} style={{ fontSize: 13 }}>
                      {e.text}
                    </Typography.Link>
                  </div>
                ),
              }))}
            />
          </Card>
        </Col>
      </Row>
    </PageFrame>
  )
}
