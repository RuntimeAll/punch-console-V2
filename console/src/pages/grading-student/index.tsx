import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Card, Divider, Empty, Space, Tabs, Tag, Typography } from 'antd'
import { useParams, useSearchParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import type { Batch, Track } from '@/mock'
import { findStudent } from '@/mock'
import {
  batchCountOf, depositsOf, locateBatch, pendingCountOf, reportCountOf, studentStatusColor,
} from '@/pages/grading/batch-view'
import { BatchDrawer, type Selection } from './BatchDrawer'
import { DayGrid, type DayCell } from './DayGrid'
import { TrackTrend, type TrendPoint } from './TrackTrend'
import './style.css'

/**
 * 批改·学员详情 /grading/:code —— 🔴 分轨模型的展示面，本次评审第二核心。
 *
 * 结构：档案头（代号+年级+教材版本+状态+服务档位+入营）→ 肖像条（备课出题依据）
 * → 360 汇总条（跨轨只做**计数**）→ 一条轨一个 Tab → 轨内趋势 + 天格 → 点格开右侧抽屉（详情/终审/报告）。
 * 🔴 定稿 §一：「学员 360 视图 = 现算不落表」——本页所有汇总数字都是从 mock 当场算出来的，没有汇总字段。
 * 🔴 铁律③：得分、趋势、错因全部**轨内**聚合。严禁把「绝对值化简求值」的第 1 天
 * 接在「七上混合运算」的第 6 天后面画一条线，也不给「这个学生的平均分」。
 *
 * 终审是本页的一个动作（抽屉里逐题三键 + 确认这批），改动只落本地 state（mock 原型，不落库）。
 */

/** 360 汇总条的一格：大数字 + 一行口径小字（数字不写口径就会被读成别的意思） */
function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 600, lineHeight: '26px' }}>{value}</div>
      {hint ? <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{hint}</div> : null}
    </div>
  )
}

export default function GradingStudent() {
  const { code = '' } = useParams()
  const student = findStudent(code)
  const [searchParams, setSearchParams] = useSearchParams()
  const batchParam = searchParams.get('batch')

  /** 终审草稿：batchId → { 题号: 选择 }。'drop' = 该题作废不计分 */
  const [drafts, setDrafts] = useState<Record<string, Record<number, Exclude<Selection, undefined>>>>({})
  /** 本地已确认的批次（mock 原型：不落库，刷新即还原） */
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({})
  /** 首屏就定好激活的轨/抽屉（惰性初始化，避免 Tab 空一帧） */
  const landing = student && batchParam ? locateBatch(student, batchParam) : null
  const [activeTrack, setActiveTrack] = useState<string>(() => landing?.track.id ?? student?.tracks[0]?.id ?? '')
  const [openId, setOpenId] = useState<string | null>(() => landing?.batch.id ?? null)

  /** 从待办页带 ?batch=xxx 进来：自动切到对应轨 + 弹开该批次抽屉 */
  useEffect(() => {
    if (!student) return
    if (batchParam) {
      const hit = locateBatch(student, batchParam)
      if (hit) {
        setActiveTrack(hit.track.id)
        setOpenId(hit.batch.id)
        return
      }
    }
    setActiveTrack((k) => k || student.tracks[0]?.id || '')
  }, [student, batchParam])

  if (!student) {
    return (
      <PageFrame title="学员">
        <Empty description={`没有这个学员代号：${code}`} />
      </PageFrame>
    )
  }

  // ── 现态推导（终审改判后所有视图跟着变）────────────────────
  /** 某题的终审选择：草稿优先；没草稿时沿用机器判，'?' 视为「还没拍板」 */
  const selectionOf = (batch: Batch, qno: number): Selection => {
    const drafted = drafts[batch.id]?.[qno]
    if (drafted) return drafted
    const item = batch.items.find((it) => it.qno === qno)
    if (!item) return undefined
    return item.verdict === '?' ? undefined : item.verdict
  }

  /** 批次现态：本地确认过就是「已确认」 */
  const stateOf = (batch: Batch): Batch['state'] => (confirmed[batch.id] ? '已确认' : batch.state)

  /** 批次现判分：作废的题不进分母；未拍板的存疑题算在分母、不算对 */
  const scoreOf = (batch: Batch): { right: number; total: number } | null => {
    if (batch.items.length === 0) return batch.score ?? null
    const kept = batch.items.filter((it) => selectionOf(batch, it.qno) !== 'drop')
    if (kept.length === 0) return null
    return { right: kept.filter((it) => selectionOf(batch, it.qno) === '√').length, total: kept.length }
  }

  /** 🔴 轨内正确率：只累计本轨的天 */
  const rateOfTrack = (track: Track) => {
    let right = 0
    let total = 0
    for (const d of track.days) {
      const s = scoreOf(d)
      if (!s) continue
      right += s.right
      total += s.total
    }
    return total > 0 ? { right, total, percent: Math.round((right / total) * 100) } : null
  }

  /** 🔴 轨内高频错因考点 top3（同样只吃本轨的天） */
  const weakKpsOfTrack = (track: Track) => {
    const bag: Record<string, number> = {}
    for (const d of track.days) {
      for (const it of d.items) {
        if (!it.kp || selectionOf(d, it.qno) !== '×') continue
        bag[it.kp] = (bag[it.kp] ?? 0) + 1
      }
    }
    return Object.entries(bag)
      .map(([kp, wrong]) => ({ kp, wrong }))
      .sort((a, b) => b.wrong - a.wrong)
      .slice(0, 3)
  }

  // ── 终审动作 ──────────────────────────────────────────────
  const judge = (batchId: string, qno: number, sel: Exclude<Selection, undefined>) =>
    setDrafts((prev) => ({ ...prev, [batchId]: { ...(prev[batchId] ?? {}), [qno]: sel } }))

  const confirmBatch = (batchId: string) => setConfirmed((prev) => ({ ...prev, [batchId]: true }))

  const closeDrawer = () => {
    setOpenId(null)
    // 关抽屉顺手把 ?batch= 抹掉，免得刷新又弹开
    if (batchParam) setSearchParams({}, { replace: true })
  }

  const opened = openId ? locateBatch(student, openId) : null
  const running = student.tracks.filter((t) => t.status === '进行中')
  /** 🔴 360 三个数全部**现算**（定稿 §一：学员 360 视图不落表），且跨轨只做计数 */
  const reports = reportCountOf(student)
  const deposits = depositsOf(student.code)
  const depositKinds = new Set(deposits.map((d) => d.causeId)).size

  return (
    <PageFrame
      title={student.code}
      desc="学员 360：上面是档案 + 肖像 + 汇总，下面按轨分账（一条轨一个 Tab，跨轨只计数不平均）。"
    >
      {/* ══ 档案头 ══ 定稿 §一 student 扩表：代号 + 年级 + 教材版本 + 状态 + 服务档位 + 入营时间，一行读完。
          🔴 红线不变：一律代号制，真名 / 联系方式永不入库，页面上更不许出现。 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space size={10} align="center" wrap>
          <span className="gs-code">{student.code}</span>
          <Tag color={studentStatusColor(student.status)} style={{ marginInlineEnd: 0 }}>
            {student.status}
          </Tag>
          <Typography.Text style={{ fontSize: 13 }}>{student.grade}</Typography.Text>
          {/* 教材版本不是装饰位：出题与认卷都吃它（人教 ≠ 浙教，章序与题面都不同） */}
          <Typography.Text style={{ fontSize: 13 }}>{student.textbookVer}</Typography.Text>
          <Divider type="vertical" style={{ margin: 0 }} />
          <Typography.Text style={{ fontSize: 13 }}>{student.serviceTier}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            入营 {student.joinedAt}
          </Typography.Text>
        </Space>
        {student.note ? <div className="gs-note">备注：{student.note}</div> : null}

        <Divider style={{ margin: '10px 0' }} />

        {/* ══ 肖像条 ══ 🔴 profile 不是花絮：备课选题、出题难度、批改时先看哪几处，都吃这几句。
            渲成描边 chips（不铺色块），一句一枚。 */}
        <div className="gs-portrait">
          <span className="gs-portrait-label">肖像</span>
          <div className="gs-chips">
            {student.profile.length > 0 ? (
              student.profile.map((p) => (
                <span key={p} className="gs-chip">
                  {p}
                </span>
              ))
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                还没写肖像 —— 先跑两天卷子再补，别凭印象编
              </Typography.Text>
            )}
          </div>
        </div>
        <div className="gs-portrait-hint">
          这几句是备课选题 / 出题难度 / 批改时重点看哪几处的个性化依据，写法要能直接照做（如「先看后算防硬算」），
          「比较聪明」这种没法照做的话不配进来。
        </div>

        <Divider style={{ margin: '10px 0' }} />

        {/* ══ 360 汇总条 ══ 🔴 全部从 mock 现算（定稿 §一：学员 360 视图现算不落表）。
            🔴 铁律③：这一条**全是计数**；正确率按轨分列摆在最右，绝不合成一个「这个学生的总分」。 */}
        <Space size={30} wrap align="start">
          <Stat label="在练轨" value={running.length} hint={`共 ${student.tracks.length} 条轨`} />
          <Stat label="累计批次" value={batchCountOf(student)} hint="含在飞的" />
          <Stat label="报告" value={reports} hint="已出件的批次各挂一份" />
          <Stat
            label="沉淀错因"
            value={deposits.length}
            hint={deposits.length > 0 ? `涉 ${depositKinds} 类错因` : '还没沉淀'}
          />
          <Stat label="待处理" value={pendingCountOf(student)} hint="卡在人手上的批次" />
          <div>
            <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>各轨正确率（🔴 分列，不平均）</div>
            <Space size={6} wrap style={{ marginTop: 4 }}>
              {student.tracks.map((t) => {
                const r = rateOfTrack(t)
                return (
                  <Tag key={t.id} style={{ marginInlineEnd: 0 }}>
                    {t.name} {r ? `${r.percent}%` : '—'}
                  </Tag>
                )
              })}
            </Space>
          </div>
        </Space>
      </Card>

      {/* ── 主体：一条轨一个 Tab ────────────────────────────── */}
      <Card size="small">
        <Tabs
          activeKey={activeTrack}
          onChange={setActiveTrack}
          items={student.tracks.map((t) => {
            const rate = rateOfTrack(t)
            const weak = weakKpsOfTrack(t)
            const points: TrendPoint[] = t.days
              .map((d) => {
                const s = scoreOf(d)
                return s ? { day: d.dayInTrack, right: s.right, total: s.total, state: stateOf(d) } : null
              })
              .filter((p): p is TrendPoint => p !== null)
            const cells: DayCell[] = t.days.map((d) => ({
              batchId: d.id,
              day: d.dayInTrack,
              state: stateOf(d),
              score: scoreOf(d),
            }))

            return {
              key: t.id,
              label: (
                <Space size={6}>
                  <span>{t.name}</span>
                  <Tag color={t.status === '进行中' ? 'blue' : undefined} style={{ marginInlineEnd: 0 }}>
                    {t.status}
                  </Tag>
                </Space>
              ),
              children: (
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  {/* 轨内小结（全部本轨口径） */}
                  <Space size={18} wrap>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      册子：{t.bookRef ?? '—'}
                    </Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      已练 {t.days.length} 天
                    </Typography.Text>
                    <Typography.Text style={{ fontSize: 12 }}>
                      轨内正确率 <b>{rate ? `${rate.percent}%` : '—'}</b>
                      {rate ? `（${rate.right}/${rate.total} 题）` : ''}
                    </Typography.Text>
                    {weak.length > 0 ? (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        本轨高频错因：{weak.map((w) => `${w.kp} ×${w.wrong}`).join(' ｜ ')}
                      </Typography.Text>
                    ) : null}
                  </Space>

                  <Divider style={{ margin: '10px 0' }} />

                  <Typography.Text strong style={{ fontSize: 13 }}>
                    轨内趋势
                    <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
                      　纵轴 = 正确率，横轴 = 轨内第几天，点上标得分
                    </Typography.Text>
                  </Typography.Text>
                  <TrackTrend points={points} />

                  <Divider style={{ margin: '10px 0' }} />

                  <Typography.Text strong style={{ fontSize: 13 }}>
                    逐天
                    <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
                      　点一格看这天的账；待终审的天在抽屉里直接拍板
                    </Typography.Text>
                  </Typography.Text>
                  <DayGrid cells={cells} activeId={openId} onOpen={setOpenId} />
                </Space>
              ),
            }
          })}
        />
      </Card>

      {/* ── 批次抽屉：详情 / 终审 / 报告占位 ─────────────────── */}
      <BatchDrawer
        open={opened !== null}
        onClose={closeDrawer}
        studentCode={student.code}
        trackName={opened?.track.name ?? ''}
        batch={opened?.batch ?? null}
        state={opened ? stateOf(opened.batch) : '批改中'}
        score={opened ? scoreOf(opened.batch) : null}
        selectionOf={(qno) => (opened ? selectionOf(opened.batch, qno) : undefined)}
        onJudge={(qno, sel) => opened && judge(opened.batch.id, qno, sel)}
        onConfirm={() => opened && confirmBatch(opened.batch.id)}
      />
    </PageFrame>
  )
}
