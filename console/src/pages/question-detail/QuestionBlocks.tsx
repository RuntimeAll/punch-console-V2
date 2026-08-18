import { Typography } from 'antd'
import { BlockFlow } from '@/components'
import type { Block } from '@/mock'
import { isEmptyDoc } from '@/mock'

/**
 * 🔴🔴 QuestionBlocks —— 题目内容渲染的**唯一姿势**（本页内组件，导出预览组照抄这个思路）。
 *
 * ── 为什么长这样（给要抄的人看）──────────────────────────────
 * 1. 真正干活的是公共件 <BlockFlow>（@/components/BlockFlow.tsx）：它按块流 v2 的
 *    `rows → cells` **顺序渲染**，figure 排在第几个 cell 就渲在第几个。本组件只是套一层语义外壳
 *    （空态兜底 + 段落留白），**不重新解析块流**。
 *    👉 抄的时候连"套一层"都可以省，直接调 <BlockFlow>；千万别另写第二个块解析器。
 * 2. 🔴 绝对禁止的写法（老版被用户否定的头号交互）：
 *      rows.flatMap(r => r.cells).filter(c => c.type === 'text')   // 先把文字铺完
 *      rows.flatMap(r => r.cells).filter(c => c.type === 'figure') // 再在末尾集中挂图 =「配图区」
 *    题面与配图必须**一起混排**：图夹在哪两段文字之间，页面上就得夹在那两段之间。
 *    验收样本 = q-4001（题面 text→figure→text）与它的解析（同样 text→figure→text）。
 * 3. 题面 / 答案 / 解析是三条**独立**块流，各调一次本组件，三条流各自内部都能混排配图。
 *    不要把三条流拼成一个数组渲染，那样答案里的图会串到题面去。
 * 4. 打印/导出场景：外层容器请自己加 className="print-item"（每题一块，禁跨页切断），
 *    本组件不管纸张排版，只管块流顺序。
 */
export function QuestionBlocks({
  blocks,
  /** 空块流时的占位文案（草稿题的答案/解析可能是空的） */
  empty = '（暂无内容）',
}: {
  /** 一份块流文档（v2 起是 { v, rows } 而不是数组） */
  blocks: Block
  empty?: string
}) {
  if (isEmptyDoc(blocks)) {
    return <Typography.Text type="secondary">{empty}</Typography.Text>
  }
  return <BlockFlow blocks={blocks} />
}

export default QuestionBlocks
