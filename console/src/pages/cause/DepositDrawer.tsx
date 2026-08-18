import { Alert, Button, Descriptions, Drawer, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { CauseDeposit, ErrorCause } from '@/mock'
// 🔴 溯源渲法的唯一实现在 kg 组，本抽屉单向依赖（见 kg/trace.ts 顶部的依赖方向说明）
import { KpTraceLink, KpTraceLinks } from '@/pages/kg/KpTraceLink'
import { contextOf, verdictHue } from './context'

/**
 * 单条沉淀的判定上下文抽屉。
 * 归属：维护组「错因管理」自用。
 *
 * 一条沉淀 = 某学员某轨某天某题命中了某条错因。抽屉把这条沉淀**还原回批改现场**：
 * ① 坐标：哪个学员、哪条轨、第几天、第几题、哪一批
 * ② 机器怎么判的（√ / × / ?）、判在哪个考点上、机器自己写的备注
 * ③ 批改原话（沉淀的 note）—— 这是精华本身，原样展示不截断
 * ④ 命中的错因是什么口径（定义 + 收编的机器错因码）
 *
 * 🔴 铁律③：这里出现的分数只有「本批次当天」一个数，且明写是轨内口径。
 *   绝不跨轨算率、不画趋势——要看走势去 /grading/<代号> 的轨内看。
 */
export function DepositDrawer({
  open,
  onClose,
  deposit,
  cause,
}: {
  open: boolean
  onClose: () => void
  deposit: CauseDeposit | null
  cause?: ErrorCause
}) {
  const navigate = useNavigate()
  if (!deposit) return null

  const { batch, item } = contextOf(deposit)
  // 🔴 誊写笔误的招牌场景：机器判**对**，但仍要记一条提醒（按学生自己抄下来的题面核算）
  const judgedRight = item?.verdict === '√'

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={640}
      title={
        <Space size={8} wrap>
          <span>{deposit.student}</span>
          <Typography.Text type="secondary" style={{ fontSize: 13, fontWeight: 400 }}>
            {deposit.track} · 第 {deposit.dayInTrack} 天 · 第 {deposit.qno} 题
          </Typography.Text>
          {cause ? (
            <Tag style={{ marginInlineEnd: 0 }}>{cause.name}</Tag>
          ) : (
            <Tag color="orange" style={{ marginInlineEnd: 0 }}>
              错因已从词表删除
            </Tag>
          )}
        </Space>
      }
      footer={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            要看这条轨的走势，去学员页的轨内看——本页只计数。
          </Typography.Text>
          <Button onClick={() => navigate(`/grading/${encodeURIComponent(deposit.student)}`)}>
            去看 {deposit.student} 的这条轨
          </Button>
        </div>
      }
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {/* ① 坐标 + ② 机器判定 */}
        <Descriptions
          size="small"
          column={2}
          styles={{ label: { width: 76 } }}
          items={[
            { key: 'date', label: '日期', children: deposit.date },
            {
              key: 'batch',
              label: '批次',
              children: batch ? (
                <Space size={6}>
                  <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{batch.id}</span>
                  <Tag style={{ marginInlineEnd: 0 }}>{batch.state}</Tag>
                </Space>
              ) : (
                <Typography.Text type="secondary">批改账本上找不到这一批</Typography.Text>
              ),
            },
            {
              key: 'verdict',
              label: '机器判定',
              children: item ? (
                <span style={{ color: verdictHue(item.verdict), fontWeight: 600, fontSize: 15 }}>{item.verdict}</span>
              ) : (
                <Typography.Text type="secondary">—</Typography.Text>
              ),
            },
            {
              key: 'score',
              label: '当天得分',
              children: batch?.score ? (
                <Space size={6}>
                  <span>
                    {batch.score.right}/{batch.score.total}
                  </span>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    （本批次当天，轨内口径）
                  </Typography.Text>
                </Space>
              ) : (
                '—'
              ),
            },
            {
              // 🔴 判词⑤：机器判在哪个考点上，也要能溯源到知识图谱。
              //   这几个考点现在全是「未上树」（七上那一枝教材树还没铺），点不动是如实显示——
              //   批改判得出考点、树上却没这片叶，正是溯源断点最典型的样子。
              key: 'kp',
              label: '判在考点',
              children: item?.kp ? (
                <KpTraceLink name={item.kp} onNavigated={onClose} />
              ) : (
                <Typography.Text type="secondary">—</Typography.Text>
              ),
              span: 2,
            },
            {
              key: 'itemNote',
              label: '机器备注',
              children: item?.note ?? <Typography.Text type="secondary">机器没写备注</Typography.Text>,
              span: 2,
            },
          ]}
        />

        {judgedRight ? (
          <Alert
            type="info"
            showIcon
            message="这题判的是「对」，但仍记了一条沉淀"
            description="判定口径：按学生自己抄下来的题面核算——抄错了但按抄错的题算对了，判对，只记一条誊写提醒，不算错题。所以「沉淀条数」不等于「错题数」，别拿它当错题率的分子。"
          />
        ) : null}

        {/* ③ 批改原话 —— 精华本身，原样不截断 */}
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            批改原话
          </Typography.Text>
          <div
            style={{
              marginTop: 4,
              padding: '8px 12px',
              background: '#fafafa',
              border: '1px solid #f0f0f0',
              borderRadius: 4,
              fontSize: 13,
              lineHeight: 1.9,
              whiteSpace: 'pre-wrap',
            }}
          >
            {deposit.note}
          </div>
        </div>

        {/* ④ 错因口径 */}
        {cause ? (
          <div>
            <Typography.Text strong style={{ fontSize: 13 }}>
              命中的错因 · {cause.name}
            </Typography.Text>
            <Typography.Paragraph style={{ fontSize: 13, lineHeight: 1.9, margin: '4px 0 6px' }}>
              {cause.definition}
            </Typography.Paragraph>
            <Space size={6} wrap>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                收编的机器错因码：
              </Typography.Text>
              {cause.mappedCodes.map((c) => (
                <Tag key={c} style={{ marginInlineEnd: 0, fontFamily: 'monospace', fontSize: 12 }}>
                  {c}
                </Tag>
              ))}
            </Space>
            {/* 🔴 溯源收口：这条沉淀命中的错因挂在哪几片叶上，点过去看那个考点的全部家当 */}
            <div style={{ marginTop: 8 }}>
              <Typography.Text type="secondary" style={{ fontSize: 12, marginRight: 6 }}>
                这条错因挂靠的考点：
              </Typography.Text>
              <KpTraceLinks
                names={cause.kpNames}
                onNavigated={onClose}
                empty={
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    不限考点（跨考点通用）—— 这是它的正常态，不是溯源断了
                  </Typography.Text>
                }
              />
            </div>
          </div>
        ) : null}
      </Space>
    </Drawer>
  )
}

export default DepositDrawer
