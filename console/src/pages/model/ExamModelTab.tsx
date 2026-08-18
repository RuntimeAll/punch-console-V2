import { useMemo, useState } from 'react'
import { Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ExamModel } from '@/mock'
import { examModels, ticketsOfModel } from '@/mock'
// 🔴 溯源换算只有一份实现（kg 组的 trace.ts），本页单向依赖它，别在这儿再写一套考点名→树key
import { KpTraceLinks } from '@/pages/kg/KpTraceLink'
import { kpKeyOf } from '@/pages/kg/trace'
import { ModelDrawer } from './ModelDrawer'
import type { StatusMap } from './view'
import { initialStatus, statusHint, statusOf, statusTagColor, totalQuestions } from './view'

/**
 * 段②：考察模型 = 「这类题**怎么造**」的参数化配方，是举一反三 / 打卡册的产题底座。
 * 归属：维护组「考察模型」自用（原来是整页，第四轮起三段式里的一段）。
 *
 * 🔴 这段存在的理由（走查判词原话）：**低频但必须记账**——一个模型半年改不了一次，
 *   可它管着上百道题的出题口径，没这份记录换个人就只能凭印象重造，题退化成瞎换数字。
 * 🔴 这份记录不是编辑器：paramSummary 是人话摘要，完整参数在 dslRef 指的文件里。
 *   转正 / 停用给原型演示态（本地 state），改参数、跑出题一概不做——那是 agent 的活。
 * 🔴 draft 的 questionCount 是 0，别渲成「这个模型没用」：它是「参数写完了没接出题器」，两回事。
 *
 * 🔴🔴 判词⑤：模型必须能**向上溯源到知识图谱**。所以有「挂靠考点」一列，
 *   每个考点名点得动，落到 /kg?kp=&lt;树key&gt; 那片叶（换算走 kg 组的 trace.ts，唯一实现）。
 *   两种断法都要如实标出来，别糊成一种：
 *   - kpNames 空数组   → 「未挂考点」= 溯源彻底断了（em-004 就是，等审核台定名）
 *   - 名字有、树上没有 → 灰色虚线「未上树」（em-005 那两个绝对值考点，七上那一枝还没铺）
 *
 * 🔴 与另两段的分工别混：题型目录=长什么样（识别）、解题模型=怎么解（举一反三地基），
 *   本段=**怎么造**（出题 DSL 的配方）。三张表各挂各的考点，不是同一个东西的三个视图。
 */
export function ExamModelTab() {
  const [statusMap, setStatusMap] = useState<StatusMap>(initialStatus)
  const [openId, setOpenId] = useState<string>('')

  const counts = useMemo(() => {
    const acc = { 在用: 0, 草稿: 0, 已停用: 0 }
    for (const m of examModels) acc[statusOf(statusMap, m)] += 1
    return acc
  }, [statusMap])

  /** 溯源欠账盘点：几个模型一片叶都没挂、几个模型挂的名字树上找不到 */
  const traceGap = useMemo(() => {
    const noKp = examModels.filter((m) => m.kpNames.length === 0).length
    const offTree = examModels.filter(
      (m) => m.kpNames.length > 0 && m.kpNames.some((k) => kpKeyOf(k) === undefined),
    ).length
    return { noKp, offTree }
  }, [])

  const current = examModels.find((m) => m.id === openId) ?? null
  const setStatus = (id: string, s: StatusMap[string]) => setStatusMap((prev) => ({ ...prev, [id]: s }))

  const columns: ColumnsType<ExamModel> = [
    {
      title: '模型名',
      key: 'name',
      width: 250,
      render: (_, m) => {
        const blockers = ticketsOfModel(m.id)
        return (
          <div>
            <Typography.Text strong style={{ fontSize: 13 }}>
              {m.name}
            </Typography.Text>
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
                {m.id}
              </Typography.Text>
              {blockers.length > 0 ? (
                <Tooltip title={blockers.map((t) => `${t.id} ${t.title}`).join('；')}>
                  <Tag color="orange" style={{ marginInlineStart: 6, marginInlineEnd: 0 }}>
                    等审核台定名
                  </Tag>
                </Tooltip>
              ) : null}
            </div>
          </div>
        )
      },
    },
    {
      title: '参数域摘要',
      dataIndex: 'paramSummary',
      key: 'paramSummary',
      // 🔴 不给 ellipsis：参数是这段的正主，宁可折行也不许被「…」吃掉
      render: (s: string) => (
        <Typography.Text style={{ fontSize: 13, lineHeight: 1.8 }}>{s}</Typography.Text>
      ),
    },
    {
      // 🔴 判词⑤：模型 → 知识图谱的溯源链就在这一列，每个考点名点得动
      title: '挂靠考点',
      key: 'kpNames',
      width: 210,
      render: (_, m) => (
        <KpTraceLinks
          names={m.kpNames}
          empty={
            // 🔴 空数组 ≠ 「跨考点通用」（那是错因的说法）：模型没挂考点就是溯源断了，是活儿
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12 }}
              title="ExamModel.kpNames 是空数组：这个模型说不出自己考的是哪片叶，溯源到这儿就断了"
            >
              未挂考点（溯源断点）
            </Typography.Text>
          }
        />
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 92,
      render: (_, m) => {
        const s = statusOf(statusMap, m)
        return (
          <Tooltip title={statusHint(s)}>
            <Tag color={statusTagColor(s)} style={{ marginInlineEnd: 0 }}>
              {s}
            </Tag>
          </Tooltip>
        )
      },
    },
    {
      title: '已出题数',
      key: 'questionCount',
      width: 112,
      align: 'right',
      render: (_, m) => {
        const s = statusOf(statusMap, m)
        return (
          <div>
            <Typography.Text style={{ fontSize: 13 }}>{m.questionCount} 道</Typography.Text>
            {m.questionCount === 0 && s === '草稿' ? (
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  未接出题器
                </Typography.Text>
              </div>
            ) : null}
          </div>
        )
      },
    },
    {
      title: 'DSL 指针',
      dataIndex: 'dslRef',
      key: 'dslRef',
      width: 250,
      render: (s: string) => (
        <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace', wordBreak: 'break-all' }}>
          {s}
        </Typography.Text>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} size={6} wrap>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          它是干嘛的：<b>怎么造</b>这类题 —— 参数化出题配方，出题动作归 agent，本段只记账。
        </Typography.Text>
        <Tag style={{ marginInlineEnd: 0 }}>在用 {counts.在用}</Tag>
        <Tag color="orange" style={{ marginInlineEnd: 0 }}>
          草稿 {counts.草稿}
        </Tag>
        {counts.已停用 > 0 ? <Tag style={{ marginInlineEnd: 0 }}>已停用 {counts.已停用}</Tag> : null}
        <Tag style={{ marginInlineEnd: 0 }}>共管 {totalQuestions()} 道题</Tag>
        {/* 🔴 溯源欠账明摆在段头：不摆出来就没人记得这是活儿 */}
        {traceGap.noKp + traceGap.offTree > 0 ? (
          <Tooltip title="「未挂考点」= kpNames 空数组，溯源彻底断了；「考点未上树」= 名字有、教材树上找不到同名叶">
            <Tag color="orange" style={{ marginInlineEnd: 0 }}>
              溯源断点 {traceGap.noKp} 未挂考点
              {traceGap.offTree > 0 ? ` · ${traceGap.offTree} 考点未上树` : ''}
            </Tag>
          </Tooltip>
        ) : null}
      </Space>

      <Table<ExamModel>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={examModels}
        pagination={false}
        onRow={(m) => ({
          style: { cursor: 'pointer' },
          onClick: () => setOpenId(m.id),
        })}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：点任意一行开详情抽屉（参数域全文 + 挂靠考点 + 母题 + 维护备注）。
        em-004「20以内退位减·破十法型」是草稿且被审核台 rv-006 卡着定名——抽屉里的「转正」按钮是禁用的，
        鼠标悬上去有原因；转正 / 停用只改本页临时状态，不落库。
        <b> 溯源看这三行</b>：em-001 的两个考点都点得动（蓝字），点「三位数乘两位数的计算」落到 /kg 那片叶——
        那片叶一道题都没挂，却能在「② 关联考察模型」里反过来看见 em-001，一来一回对得上；
        em-005 两个考点是灰色虚线「未上树」（七上那一枝教材树还没铺，点不动是如实显示）；
        em-004 写的是「未挂考点（溯源断点）」。三种状态长得都不一样，别糊成一种。
      </Typography.Paragraph>

      <ModelDrawer
        open={openId !== ''}
        onClose={() => setOpenId('')}
        model={current}
        status={current ? statusOf(statusMap, current) : '在用'}
        onPromote={() => current && setStatus(current.id, '在用')}
        onSuspend={() => current && setStatus(current.id, '已停用')}
        onResume={() => current && setStatus(current.id, '在用')}
      />
    </div>
  )
}

export default ExamModelTab
