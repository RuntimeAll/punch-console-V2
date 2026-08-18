import type { ReactNode } from 'react'
import { List, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { KpTrace } from './trace'
import { traceStemSummary } from './trace'

/**
 * 🔴 考点详情 = **聚合落点**（第三轮判词⑤ 原话）。
 * 一片考点叶挂着四样家当，四小节固定顺序、**一个都不许隐藏**：
 *   ① 关联题目（归属挂在这片叶下的题）
 *   ② 关联考察模型（模型认领的 kpNames + 母题落在这片叶下的，两路并集）
 *   ③ 关联错因（错因词表 kpNames 里写了这片叶名的）
 *   ④ 最近批改沉淀（经 ③ 的错因**间接**挂上来的，带轨名）
 *
 * 🔴 空了写「暂无」，不是把小节藏掉：
 *   用户点开一片叶要的答案就是「这个考点挂着什么家当」——
 *   藏掉空小节，页面就从「回答问题」退化成「有什么显示什么」，四小节各写各的空态说法，
 *   因为「没题」「没模型」「没错因」「没沉淀」在维护上根本不是一回事。
 *
 * 🔴 铁律③：④ 只**列**不算率、不画趋势线，每条必须带轨名（跨轨拉平就是造假）。
 * 🔴 本件不渲题面：题目内容一律走 <BlockFlow>，这里只出题号 + 首行摘要当扫读。
 */

/** 小节外壳：标题 + 计数 + 一句口径说明，空了走 empty */
function Section({
  title,
  count,
  hint,
  empty,
  children,
}: {
  title: string
  count: number
  /** 这一小节的口径说明（为什么这里会有东西 / 为什么可能是空的） */
  hint: string
  /** 🔴 空态说法各小节自己写：四种「空」含义不同，不许共用一句 */
  empty: ReactNode
  children?: ReactNode
}) {
  return (
    <div style={{ marginTop: 14 }}>
      <Space size={6} align="baseline" wrap>
        <Typography.Text strong style={{ fontSize: 13 }}>
          {title}
        </Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {count} 项
        </Typography.Text>
      </Space>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 6px' }}>
        {hint}
      </Typography.Paragraph>
      {count === 0 ? (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          暂无 —— {empty}
        </Typography.Text>
      ) : (
        children
      )}
    </div>
  )
}

export function KpTraceSections({ trace }: { trace: KpTrace }) {
  const navigate = useNavigate()

  return (
    <div>
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
        <Typography.Text strong style={{ fontSize: 13 }}>
          这片叶挂着什么家当
        </Typography.Text>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 0' }}>
          🔴 维护区三样东西（题目 / 考察模型 / 错因）内容各不相同，但都要能向上溯源到知识图谱——
          考点详情就是它们的聚合落点。四小节空了也照写「暂无」，缺口本身就是要看的东西。
        </Typography.Paragraph>
      </div>

      {/* ① 关联题目 */}
      <Section
        title="① 关联题目"
        count={trace.questions.length}
        hint="按归属（treePath 前缀）算：这些题在教材树上就长在这片叶下面。点题号进详情。"
        empty="零挂载：目录有、题没有。要么这块还没出题，要么题挂到别的叶子上去了。"
      >
        <List
          size="small"
          dataSource={trace.questions}
          renderItem={(q) => (
            <List.Item style={{ paddingInline: 0 }}>
              <Typography.Link onClick={() => navigate(`/questions/${q.id}`)} style={{ display: 'block', width: '100%' }}>
                <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{q.id}</span>
                <Typography.Text style={{ fontSize: 13 }}>{traceStemSummary(q)}</Typography.Text>
              </Typography.Link>
            </List.Item>
          )}
        />
      </Section>

      {/* ② 关联考察模型 */}
      <Section
        title="② 关联考察模型"
        count={trace.models.length}
        hint="两路并集：模型自己把这片叶写进了 kpNames，或者它的母题正好归属在这片叶下。点名字去 /model 那张表。"
        empty="这个考点还没有参数化的出题配方 —— 要出题只能一道一道现编，正是该立模型的地方。"
      >
        <List
          size="small"
          dataSource={trace.models}
          renderItem={(m) => (
            <List.Item style={{ paddingInline: 0 }}>
              <div style={{ width: '100%' }}>
                <Space size={6} wrap>
                  <Typography.Link onClick={() => navigate('/model')}>{m.name}</Typography.Link>
                  <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
                    {m.id}
                  </Typography.Text>
                  {m.status === 'draft' ? (
                    <Tag color="orange" style={{ marginInlineEnd: 0 }}>
                      草稿
                    </Tag>
                  ) : null}
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    管着 {m.questionCount} 道题
                  </Typography.Text>
                </Space>
              </div>
            </List.Item>
          )}
        />
      </Section>

      {/* ③ 关联错因 */}
      <Section
        title="③ 关联错因"
        count={trace.causes.length}
        hint="错因词表里把这片叶名写进 kpNames 的那几条。点名字去 /cause 的错因库。"
        empty="没有专门挂在这个考点上的错因（跨考点通用错因如「誊写笔误」不算挂在任何一片叶上）。"
      >
        <List
          size="small"
          dataSource={trace.causes}
          renderItem={(c) => (
            <List.Item style={{ paddingInline: 0 }}>
              <div style={{ width: '100%' }}>
                <Typography.Link onClick={() => navigate('/cause')}>{c.name}</Typography.Link>
                <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 6, fontFamily: 'monospace' }}>
                  {c.id}
                </Typography.Text>
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: 12, lineHeight: 1.7 }}>
                    {c.definition}
                  </Typography.Text>
                </div>
              </div>
            </List.Item>
          )}
        />
      </Section>

      {/* ④ 最近批改沉淀 */}
      <Section
        title="④ 最近批改沉淀"
        count={trace.deposits.length}
        hint={
          trace.depositTotal > trace.deposits.length
            ? `经 ③ 的错因间接挂上来的（考点 → 错因 → 沉淀）。这里只列最近 ${trace.deposits.length} 条，共 ${trace.depositTotal} 条，全量去 /cause 的批改沉淀页签。`
            : '经 ③ 的错因间接挂上来的（考点 → 错因 → 沉淀）。🔴 只列不算率：每条自带轨名，跨轨拉平算正确率是禁区。'
        }
        empty="这个考点上还没栽过跟头 —— 要么没考过，要么考了没错（③ 没错因时这里必然也是空的）。"
      >
        <List
          size="small"
          dataSource={trace.deposits}
          renderItem={(d) => (
            <List.Item style={{ paddingInline: 0 }}>
              <div style={{ width: '100%' }}>
                <Space size={6} wrap>
                  <Typography.Text style={{ fontSize: 13 }}>{d.student}</Typography.Text>
                  {/* 🔴 轨名是命根子：没有它，两条轨的沉淀就被拉平成一堆 */}
                  <Tag style={{ marginInlineEnd: 0 }}>{d.track}</Tag>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {d.date} · 第 {d.dayInTrack} 天 · 第 {d.qno} 题
                  </Typography.Text>
                </Space>
                <div>
                  {/* 批改原话不截断：那句话本身就是精华 */}
                  <Typography.Text type="secondary" style={{ fontSize: 12, lineHeight: 1.7 }}>
                    {d.note}
                  </Typography.Text>
                </div>
              </div>
            </List.Item>
          )}
        />
      </Section>
    </div>
  )
}

export default KpTraceSections
