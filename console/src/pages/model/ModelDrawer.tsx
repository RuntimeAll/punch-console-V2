import { Alert, Button, Descriptions, Drawer, List, Popconfirm, Space, Tag, Tooltip, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { ExamModel } from '@/mock'
import { ticketsOfModel } from '@/mock'
// 🔴 溯源换算的唯一实现在 kg 组，本抽屉单向依赖（见 kg/trace.ts 顶部的依赖方向说明）
import { KpTraceLinks } from '@/pages/kg/KpTraceLink'
import { kpKeyOf } from '@/pages/kg/trace'
import type { LiveStatus } from './view'
import { motherQuestions, statusHint, statusTagColor, stemSummary } from './view'

/**
 * 模型详情抽屉 —— 一个模型的完整记录。
 * 归属：维护组「考察模型」自用。
 *
 * 抽屉里回答四件事，顺序别调（走查按这个顺序讲）：
 * ① 它现在什么状态、管着多少题、DSL 在哪
 * ② 参数域**全文**（表格里那列是摘要，这里是原文，不许 ellipsis）
 * ③ 它是从哪几道母题蒸馏来的（每道可点进题库详情）
 * ④ 维护告诫（note）—— 常写着「改参数前先看它挂着多少题」这类话，必须显眼
 *
 * 🔴 转正 / 停用是**原型演示态**：只改本页临时状态，不落库、不动出题器。
 *   真出题、改参数都在 agent 侧（页面组约定 §8）。
 */
export function ModelDrawer({
  open,
  onClose,
  model,
  status,
  onPromote,
  onSuspend,
  onResume,
}: {
  open: boolean
  onClose: () => void
  model: ExamModel | null
  /** 现态（本页转正/停用后的态，不是 mock 里的原状态） */
  status: LiveStatus
  onPromote: () => void
  onSuspend: () => void
  onResume: () => void
}) {
  const navigate = useNavigate()
  if (!model) return null

  // 🔴 被审核台卡着的模型不许转正：rv-006 等的就是 em-004 先定名，名字没定就转正 = 拿着没名字的配方产题
  const blockers = ticketsOfModel(model.id)
  const mothers = motherQuestions(model)
  /** 判词⑤：挂了名字但树上找不到同名叶的那几个考点词（灰色虚线「未上树」的就是它们） */
  const offTree = model.kpNames.filter((k) => kpKeyOf(k) === undefined)

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={720}
      title={
        <Space size={8} wrap>
          <span>{model.name}</span>
          <Tag color={statusTagColor(status)} style={{ marginInlineEnd: 0 }}>
            {status}
          </Tag>
          <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
            {model.id}
          </Typography.Text>
        </Space>
      }
      footer={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            🔴 转正 / 停用只改本页临时状态，不落库、不动出题器。
          </Typography.Text>
          <Space size={8}>
            {status === '草稿' ? (
              <Tooltip title={blockers.length > 0 ? '审核台还有工单卡着这个模型的定名，先去处理' : ''}>
                <Button type="primary" disabled={blockers.length > 0} onClick={onPromote}>
                  转正（接出题器）
                </Button>
              </Tooltip>
            ) : null}
            {status === '在用' ? (
              <Popconfirm
                title="停用这个模型？"
                description={
                  <span style={{ display: 'inline-block', maxWidth: 300 }}>
                    停用后不再用它产新题，已出的 {model.questionCount} 道题原地不动。
                  </span>
                }
                okText="停用"
                cancelText="取消"
                onConfirm={onSuspend}
              >
                <Button danger>停用</Button>
              </Popconfirm>
            ) : null}
            {status === '已停用' ? <Button onClick={onResume}>恢复在用</Button> : null}
          </Space>
        </div>
      }
    >
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {/* ① 基本账 */}
        <Descriptions
          size="small"
          column={2}
          styles={{ label: { width: 76 } }}
          items={[
            {
              key: 'status',
              label: '状态',
              children: (
                <Space size={6} wrap>
                  <Tag color={statusTagColor(status)} style={{ marginInlineEnd: 0 }}>
                    {status}
                  </Tag>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {statusHint(status)}
                  </Typography.Text>
                </Space>
              ),
              span: 2,
            },
            { key: 'count', label: '已出题数', children: `${model.questionCount} 道` },
            {
              key: 'origin',
              label: '母题',
              children: mothers.length === 0 ? '手写立的模型（无母题来源）' : `${mothers.length} 道`,
            },
            {
              // 🔴 判词⑤：模型 → 知识图谱的溯源链。点考点名落到 /kg?kp=<树key> 那片叶
              key: 'kp',
              label: '挂靠考点',
              children: (
                <div>
                  <KpTraceLinks
                    names={model.kpNames}
                    // 关掉抽屉再跳：抽屉盖在页面上，不关就跳会留一层没人管的遮罩
                    onNavigated={onClose}
                    empty={
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        未挂考点（溯源断点）—— 这个模型说不出自己考的是哪片叶
                      </Typography.Text>
                    }
                  />
                  {offTree.length > 0 ? (
                    <div>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        灰色虚线的 {offTree.length} 个词教材树上还没有同名叶（{offTree.join('、')}），
                        点不动是如实显示，不是坏了。
                      </Typography.Text>
                    </div>
                  ) : null}
                </div>
              ),
              span: 2,
            },
            {
              key: 'dsl',
              label: 'DSL 指针',
              children: <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{model.dslRef}</span>,
              span: 2,
            },
          ]}
        />

        {/* 被审核台卡着定名 */}
        {blockers.length > 0 ? (
          <Alert
            type="warning"
            showIcon
            message={`审核台有 ${blockers.length} 条工单卡着这个模型`}
            description={
              <div>
                {blockers.map((t) => (
                  <div key={t.id} style={{ marginBottom: 4 }}>
                    <Tag style={{ marginInlineEnd: 6 }}>{t.kind}</Tag>
                    <Typography.Text style={{ fontSize: 13 }}>{t.title}</Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                      {t.id} · {t.priority}优先 · {t.state}
                    </Typography.Text>
                  </div>
                ))}
                <Typography.Paragraph style={{ fontSize: 12, margin: '6px 0 8px' }}>
                  考点低置信等的就是模型先定名 —— 名字定了，考点叶才好跟着定。定名前不给转正。
                </Typography.Paragraph>
                <Button size="small" onClick={() => navigate('/review')}>
                  去审核台处理
                </Button>
              </div>
            }
          />
        ) : null}

        {/* ② 参数域全文 */}
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            参数域（全文）
          </Typography.Text>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 6px' }}>
            这是人话摘要；完整参数表在 <span style={{ fontFamily: 'monospace' }}>{model.dslRef}</span> 里，改它归 agent。
          </Typography.Paragraph>
          <div
            style={{
              padding: '8px 12px',
              background: '#fafafa',
              border: '1px solid #f0f0f0',
              borderRadius: 4,
              fontSize: 13,
              lineHeight: 1.9,
              whiteSpace: 'pre-wrap',
            }}
          >
            {model.paramSummary}
          </div>
        </div>

        {/* ③ 母题 */}
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            母题（这个配方是从哪几道题蒸馏出来的）
          </Typography.Text>
          {mothers.length === 0 ? (
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '4px 0 0' }}>
              手写立的模型，没有母题来源 —— 参数是直接照出题口径写的，不是从某道题反推的。
            </Typography.Paragraph>
          ) : (
            <List
              size="small"
              dataSource={mothers}
              style={{ marginTop: 4 }}
              renderItem={({ id, q }) => (
                <List.Item style={{ paddingInline: 0 }}>
                  {q ? (
                    <Typography.Link onClick={() => navigate(`/questions/${id}`)} style={{ display: 'block', width: '100%' }}>
                      <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{id}</span>
                      <Typography.Text style={{ fontSize: 13 }}>{stemSummary(q)}</Typography.Text>
                    </Typography.Link>
                  ) : (
                    <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                      <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{id}</span>
                      题库里已经找不到这道母题（被删或没录）
                    </Typography.Text>
                  )}
                </List.Item>
              )}
            />
          )}
        </div>

        {/* ④ 维护告诫 */}
        <Alert type="info" showIcon message="维护备注" description={model.note} />
      </Space>
    </Drawer>
  )
}

export default ModelDrawer
