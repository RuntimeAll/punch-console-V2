import { Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { SolutionModel } from '@/mock'
import { solutionModels } from '@/mock'
// 🔴 溯源换算只有一份实现（kg 组的 trace.ts / KpTraceLink），本页单向依赖
import { KpTraceLinks } from '@/pages/kg/KpTraceLink'
import { freqHint, kpNamesOfIds, tierHint } from './view'

/**
 * 段③：解题模型（solution_model，数据结构.md §2.1④，老区 43 条金标模型的位置）。
 * 归属：维护组「考察模型」自用。
 *
 * 🔴 它是干嘛的：「这类题**怎么解**」—— 举一反三的地基。没有它，变式必然退化成瞎换数字。
 * 🔴 正文是一个**二元组**，两半缺一不可，所以渲成一格里的上下两行、中间一个箭头：
 *   触发特征（看到什么就用它）→ 动作结论（怎么做、得到什么）。
 *   只写触发不写动作 = 认得出用不上；只写动作不写触发 = 不知道什么时候该拿它出来。
 * 🔴 tier / freq 是**双旋钮**：难度 = 模型表驱动（阶 + 稀有度算出来），
 *   **LLM 只匹配模型、不自评难度**。所以页面只如实显示这两个数字，不在这儿另算一个难度。
 * 🔴 kpIds 多值，全部点得动 → /kg?kp=&lt;树key&gt;（判词⑤ 的溯源链）。
 */
export function SolutionModelTab() {
  const columns: ColumnsType<SolutionModel> = [
    {
      title: '模型名',
      key: 'name',
      width: 168,
      render: (_, m) => (
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            {m.name}
          </Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
              {m.id}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      // 🔴 二元组同格渲：两半分列会让人以为它们是两个独立字段，实际是一句话的上下半句
      title: '怎么解（触发特征 → 动作结论）',
      key: 'pair',
      render: (_, m) => (
        <div style={{ fontSize: 13, lineHeight: 1.8 }}>
          <div>
            <Tag style={{ marginInlineEnd: 6 }}>触发</Tag>
            <Typography.Text>{m.triggerFeature}</Typography.Text>
          </div>
          <div style={{ color: 'rgba(0,0,0,0.35)', fontSize: 12, margin: '2px 0 2px 6px' }}>↓ 就这么做</div>
          <div>
            <Tag style={{ marginInlineEnd: 6 }}>结论</Tag>
            <Typography.Text>{m.actionConclusion}</Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: '挂靠考点（多值）',
      key: 'kpIds',
      width: 230,
      render: (_, m) => (
        <KpTraceLinks
          names={kpNamesOfIds(m.kpIds)}
          empty={
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12 }}
              title="kpIds 是空数组：这个解题模型说不出自己解的是哪片叶上的题，溯源到这儿就断了"
            >
              未挂考点（溯源断点）
            </Typography.Text>
          }
        />
      ),
    },
    {
      // 🔴 双旋钮做成徽标：两个数字并排，一眼比得出哪个模型更难更稀有
      title: '双旋钮',
      key: 'knobs',
      width: 104,
      render: (_, m) => (
        <Space size={4} wrap>
          <Tooltip title={tierHint(m.tier)}>
            <Tag style={{ marginInlineEnd: 0, fontFamily: 'monospace' }}>阶 {m.tier}</Tag>
          </Tooltip>
          <Tooltip title={freqHint(m.freq)}>
            <Tag style={{ marginInlineEnd: 0, fontFamily: 'monospace' }}>频 {m.freq}</Tag>
          </Tooltip>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: SolutionModel['status']) => (
        <Tag color={s === '停用' ? 'orange' : undefined} style={{ marginInlineEnd: 0 }}>
          {s}
        </Tag>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} size={6} wrap>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          它是干嘛的：这类题<b>怎么解</b> —— 举一反三的地基，没有它变式就退化成瞎换数字。
        </Typography.Text>
        <Tag style={{ marginInlineEnd: 0 }}>解题模型 {solutionModels.length} 条</Tag>
        <Tooltip title="难度 = 阶（模型复杂度）+ 稀有度（频次越低越稀有）由表算出来，LLM 只负责匹配到哪个模型，不自评难度">
          <Tag style={{ marginInlineEnd: 0 }}>难度=模型表驱动</Tag>
        </Tooltip>
      </Space>

      <Table<SolutionModel>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={solutionModels}
        pagination={false}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：比一比「内角和减法」（阶 1 · 频 5：人人都会、天天出现 = 送分）与「外角搬家」（阶 3 · 频 2：会的人少、出得也少 = 压轴）——
        两个旋钮一摆，难度不用谁去拍脑袋。鼠标悬在徽标上有各自的口径。
        挂靠考点点得动，落 /kg 那片叶。「梯形的拼接问题」这片叶同时被题型目录的「拼接还原型」和本段的「拼接边转移」认领 ——
        切回「题型目录」段展开那条，「解法参考」里出现的正是本段这条模型，<b>长什么样 → 怎么解</b>在同一片叶上对得起来。
      </Typography.Paragraph>
    </div>
  )
}

export default SolutionModelTab
