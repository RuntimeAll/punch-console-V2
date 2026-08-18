import { Badge, Card, Col, Row, Space, Tag, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { PageFrame } from '@/components'
import { students } from '@/mock'
import {
  batchCountOf, isPending, pendingCountOf, stateTagColor, studentHref, studentStatusColor, trackRate,
} from './batch-view'

/**
 * 批改·学员 /grading
 * 归属：页面组「批改」。这一层只回答一句话：**谁在练、练着哪几条轨、哪儿有活要干**。
 *
 * 🔴 铁律③：学员 → 轨 → 天 三级。卡片上跨轨的数字**全是计数**（几条轨 / 几个批次 / 几条待办），
 * 正确率一律按轨分列，绝不合成一个「这个学生总分」。
 */
export default function Grading() {
  const navigate = useNavigate()
  const totalPending = students.reduce((n, s) => n + pendingCountOf(s), 0)
  /** 花名册按在读状态点数：只列非零的（全是 0 的档位不占地方）。跨学员同样只做**计数** */
  const roster = (['在读', '试听', '暂停', '结课'] as const)
    .map((st) => ({ st, n: students.filter((s) => s.status === st).length }))
    .filter((x) => x.n > 0)
    .map((x) => `${x.st} ${x.n}`)
    .join(' ｜ ')

  return (
    <PageFrame
      title="批改 · 学员"
      desc="按轨分账：一个学员可以同时挂多条轨（考点/专项），各算各的学情。点卡片进轨账。"
      extra={
        <Space size={6}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            共 {students.length} 名学员（{roster}）
          </Typography.Text>
          <Link to="/grading/queue?mine=1">
            <Tag color={totalPending > 0 ? 'orange' : undefined} style={{ marginInlineEnd: 0, cursor: 'pointer' }}>
              该我动手 {totalPending} 条
            </Tag>
          </Link>
        </Space>
      }
    >
      <Row gutter={[12, 12]}>
        {students.map((s) => {
          const pending = pendingCountOf(s)
          const running = s.tracks.filter((t) => t.status === '进行中')
          return (
            <Col key={s.code} xs={24} lg={12} xxl={8}>
              <Card
                size="small"
                hoverable
                onClick={() => navigate(studentHref(s.code))}
                title={
                  /* 🔴 档案三件（定稿 §一 student 扩表）：在读状态 Tag / 年级 + 教材版本。
                     教材版本不是装饰位——出题与认卷都吃它（人教 ≠ 浙教，章序与题面都不同）。 */
                  <Space size={8} align="center">
                    <span style={{ fontWeight: 600 }}>{s.code}</span>
                    <Tag color={studentStatusColor(s.status)} style={{ marginInlineEnd: 0 }}>
                      {s.status}
                    </Tag>
                    <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
                      {s.grade} · {s.textbookVer}
                    </Typography.Text>
                  </Space>
                }
                extra={
                  /* 待办红点：有活才亮，没活留白（宁缺勿滥） */
                  pending > 0 ? (
                    <Badge count={pending} size="small" offset={[0, 0]}>
                      <Typography.Text style={{ fontSize: 12, paddingRight: 10 }}>待办</Typography.Text>
                    </Badge>
                  ) : (
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      无待办
                    </Typography.Text>
                  )
                }
              >
                <Space direction="vertical" size={10} style={{ width: '100%' }}>
                  {/* 服务档位 + 入营时间：这人买的是哪一档、跑到第几周，一眼答完 */}
                  <Typography.Text style={{ fontSize: 12 }}>
                    {s.serviceTier}
                    <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineStart: 8 }}>
                      入营 {s.joinedAt}
                    </Typography.Text>
                  </Typography.Text>

                  {/* 跨轨只放计数，不放平均分 */}
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {s.tracks.length} 条轨（进行中 {running.length}） ｜ 累计 {batchCountOf(s)} 个批次
                  </Typography.Text>

                  {/* 一条轨一行：状态 + 轨名 + 天数 + 轨内正确率（🔴 正确率按轨分列） */}
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    {s.tracks.map((t) => {
                      const rate = trackRate(t)
                      // 🔴 待办口径统一走 isPending（= 三个人工态），别在页面里另列状态名
                      const pendingOfTrack = t.days.filter((d) => isPending(d.state)).length
                      return (
                        <div key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                          <Tag
                            color={t.status === '进行中' ? 'blue' : undefined}
                            style={{ marginInlineEnd: 0, width: 58, textAlign: 'center' }}
                          >
                            {t.status}
                          </Tag>
                          <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {t.name}
                          </span>
                          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                            {t.days.length} 天
                          </Typography.Text>
                          <Typography.Text style={{ fontSize: 12, width: 44, textAlign: 'right' }}>
                            {rate ? `${rate.percent}%` : '—'}
                          </Typography.Text>
                          {pendingOfTrack > 0 ? (
                            <Tag color={stateTagColor('待终审')} style={{ marginInlineEnd: 0 }}>
                              {pendingOfTrack}
                            </Tag>
                          ) : (
                            <span style={{ display: 'inline-block', width: 24 }} />
                          )}
                        </div>
                      )
                    })}
                  </Space>

                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    点卡片看轨账（趋势 / 逐天 / 终审）→
                  </Typography.Text>
                </Space>
              </Card>
            </Col>
          )
        })}
      </Row>
    </PageFrame>
  )
}
