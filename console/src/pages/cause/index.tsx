import { useMemo, useState } from 'react'
import { Tabs, Tag, Typography } from 'antd'
import { PageFrame } from '@/components'
import type { ErrorCause } from '@/mock'
import { ambiguousCodes, causeDeposits, errCodeMap, errorCauses } from '@/mock'
import { CauseLibTab } from './CauseLibTab'
import { DepositTab } from './DepositTab'
import { ErrCodeMapTab } from './ErrCodeMapTab'

/**
 * 维护 · 错因管理 /cause
 * 归属：页面组「维护」。只改本目录，别动 layout / mock / components。
 *
 * 🔴 走查判词原话：**学生批改后的沉淀 = 精华**。分数是一次性的，
 * 留得下来的是「这孩子在哪类错误上反复栽跟头」。所以本页分三层、三个页签：
 * - 批改沉淀（**默认页签**，主角）：事实层，一条 = 某学员某轨某天某题命中了某条错因，只增不改
 * - 错因库：词表层，全局唯一一份，低频维护，改一次影响全部历史沉淀的归类
 * - 错因码翻译表（第四轮新增，数据结构.md §2.3 err_code_map）：接线层，
 *   把批改脚本吐的**局部码**翻成错因。🔴 主键是**复合键 (考点, 码)**——
 *   同一个 `dist` 在混合运算线是「运算顺序错」、在整式线是「符号处理错」，
 *   **同码两义**已经印进过交付报告，所以那对必须并排摆出来给人看见。
 *
 * 🔴 铁律③管着整页：每条沉淀自带 track，汇总**只做计数**，
 *   绝不把不同轨的沉淀拉平算正确率、更不画成一条跨轨趋势线。
 *   要看某个学员的走势，去 /grading/<代号> 的轨内看。
 * 🔴 kpNames 为空数组 = 跨考点通用错因，渲成「不限考点（跨考点通用）」，不许留白。
 *
 * 🔴🔴 第三轮判词⑤：错因也要能**向上溯源到知识图谱**。两条链：
 * - 错因库的「挂靠考点」每个词点得动 → /kg?kp=&lt;树key&gt; 那片叶（换算走 kg 组 trace.ts）
 * - 沉淀行的错因 Tag 点得动 → 切到错因库页签并高亮那一条（沉淀 → 错因 → 考点，一跳一跳往上走）
 *   所以页签从 defaultActiveKey 改成**受控**：跨页签的跳转要有人管，不受控就跳不过去。
 */
export default function Cause() {
  /** 本页新增的错因（原型演示态，刷新即还原；真正的收编走 agent） */
  const [extra, setExtra] = useState<ErrorCause[]>([])
  const causes = useMemo(() => [...errorCauses, ...extra], [extra])
  const 跨考点条数 = causes.filter((c) => c.kpNames.length === 0).length
  /** 🔴 一码两义的组数：现算，不写死数字（将来翻译表加行，页头跟着变） */
  const 一码两义组数 = ambiguousCodes().length

  /** 🔴 页签受控：默认仍落「批改沉淀」（用户点名的精华），沉淀行点错因 Tag 时由代码切到错因库 */
  const [tab, setTab] = useState('deposits')
  /** 从沉淀跳过来时要高亮的那条错因（'' = 没有）；用户手动切页签就清掉，别留个洗不掉的高亮 */
  const [highlightId, setHighlightId] = useState('')

  /** 沉淀行 → 错因库：切页签 + 高亮。溯源链的第一跳（沉淀 → 错因） */
  const jumpToCause = (causeId: string) => {
    setHighlightId(causeId)
    setTab('lib')
  }

  return (
    <PageFrame
      title="维护 · 错因管理"
      desc="低频维护区——日常不来，来了就是治理。批改沉淀是精华：错因词表管口径（低频改一次影响全库归类），沉淀行管事实（只增不改，一条一次真实的栽跟头），错因码翻译表管接线（产线码怎么翻成错因，键必须带考点）。"
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          沉淀 {causeDeposits.length} 条 · 错因 {causes.length} 条（其中跨考点 {跨考点条数} 条） · 翻译 {errCodeMap.length}{' '}
          条（其中一码两义 {一码两义组数} 组）
          {extra.length > 0 ? (
            <Tag color="orange" style={{ marginInlineStart: 8, marginInlineEnd: 0 }}>
              本页新增 {extra.length} 条
            </Tag>
          ) : null}
        </Typography.Text>
      }
    >
      <Tabs
        // 🔴 默认落在「批改沉淀」：这是用户点名的精华，词表是它的配套
        activeKey={tab}
        onChange={(k) => {
          setTab(k)
          // 手动切页签 = 不是从沉淀跳来的，高亮该退场
          setHighlightId('')
        }}
        items={[
          {
            key: 'deposits',
            label: `批改沉淀（${causeDeposits.length}）`,
            children: <DepositTab causes={causes} onJumpToCause={jumpToCause} />,
          },
          {
            key: 'lib',
            label: `错因库（${causes.length}）`,
            children: (
              <CauseLibTab
                causes={causes}
                onAdd={(c) => setExtra((prev) => [...prev, c])}
                highlightId={highlightId}
                onClearHighlight={() => setHighlightId('')}
              />
            ),
          },
          {
            // 接线层：产线码 → 错因。与错因库共用 jumpToCause（翻译表点错因也跳回词表并高亮）
            key: 'codemap',
            label: `错因码翻译表（${errCodeMap.length}）`,
            children: <ErrCodeMapTab causes={causes} onJumpToCause={jumpToCause} />,
          },
        ]}
      />
    </PageFrame>
  )
}
