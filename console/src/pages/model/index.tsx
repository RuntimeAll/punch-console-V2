import { useState } from 'react'
import { Tabs, Tag, Typography } from 'antd'
import { PageFrame } from '@/components'
import { examModels, questionPatterns, solutionModels } from '@/mock'
import { ExamModelTab } from './ExamModelTab'
import { PatternTab } from './PatternTab'
import { SolutionModelTab } from './SolutionModelTab'

/**
 * 维护 · 考察模型 /model
 * 归属：页面组「维护」。只改本目录，别动 layout / mock / components。
 *
 * 🔴🔴 第四轮起本页是**三段式**（数据结构.md §2.1④ 定稿：pattern / exam_model / solution_model
 * 是三张独立的表，不是一张表的三个字段）。三段各回答一句话，别混：
 *
 * | 段 | 表 | 它是干嘛的 | 落点 |
 * |---|---|---|---|
 * | 题型目录 | question_pattern | 这类题**长什么样** | 题挂 patternId，识别与归类 |
 * | 考察模型 | exam_model       | 这类题**怎么造** | 出题 DSL 配方（本页原有那张表） |
 * | 解题模型 | solution_model   | 这类题**怎么解** | 举一反三地基，难度靠 tier/freq 表驱动 |
 *
 * 🔴 为什么摆在一页：三者都挂**考点**、都低频、都属于「不记账就只能凭印象重造」的东西。
 *   摆成三段是为了让人一眼看出它们的分工，摆成一张表就又糊回去了（老区就是糊的）。
 * 🔴 三段的挂靠考点全部可点 → /kg?kp=&lt;树key&gt;（判词⑤：维护区三样都要能向上溯源到知识图谱）；
 *   换算只有一份实现（kg 组 trace.ts / KpTraceLink），本页单向依赖，不自己再写一套。
 * 🔴 页头菜单名仍叫「考察模型」（Shell 的 NAV 归地基工管），本页标题跟着它，别各叫各的。
 */

/** 三段的一句话名片：段 key ↔ 一句「它是干嘛的」，页头对照条与页签共用一份，别两处各写各的 */
const SEGMENTS: { key: string; name: string; one: string; hint: string }[] = [
  {
    key: 'exam',
    name: '考察模型',
    one: '这类题怎么造',
    hint: '参数化出题配方（DSL）；出题动作归 agent，本页只记账',
  },
  {
    key: 'pattern',
    name: '题型目录',
    one: '这类题长什么样',
    hint: '识别与归类；题上挂 patternId，题库详情页那行就是它',
  },
  {
    key: 'solution',
    name: '解题模型',
    one: '这类题怎么解',
    hint: '举一反三的地基；难度=阶+稀有度表驱动，LLM 只匹配不自评',
  },
]

export default function Model() {
  /** 🔴 页签受控：页头的三张名片点得动（点哪张切哪段），不受控就切不过去 */
  const [tab, setTab] = useState('exam')

  return (
    <PageFrame
      title="维护 · 考察模型"
      desc="低频维护区——日常不来，来了就是治理。这里放着「一类题」的三张脸：长什么样（题型目录）/ 怎么造（考察模型）/ 怎么解（解题模型）。三张表各挂各的考点，都能点回知识图谱。"
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          考察模型 {examModels.length} 条 · 题型目录 {questionPatterns.length} 条 · 解题模型 {solutionModels.length} 条
        </Typography.Text>
      }
    >
      {/* 三张名片：一眼看清分工。🔴 「禁大色块」——只用最浅的边与底，选中那张靠加深边框区分 */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        {SEGMENTS.map((s) => {
          const on = s.key === tab
          return (
            <div
              key={s.key}
              onClick={() => setTab(s.key)}
              style={{
                flex: '1 1 240px',
                minWidth: 240,
                cursor: 'pointer',
                padding: '8px 12px',
                borderRadius: 4,
                background: on ? '#fafafa' : '#fff',
                border: `1px solid ${on ? '#bfbfbf' : '#f0f0f0'}`,
              }}
            >
              <div>
                <Typography.Text strong style={{ fontSize: 13 }}>
                  {s.name}
                </Typography.Text>
                <Tag style={{ marginInlineStart: 8, marginInlineEnd: 0 }}>{s.one}</Tag>
              </div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {s.hint}
              </Typography.Text>
            </div>
          )
        })}
      </div>

      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'exam', label: `考察模型（${examModels.length}）`, children: <ExamModelTab /> },
          { key: 'pattern', label: `题型目录（${questionPatterns.length}）`, children: <PatternTab /> },
          { key: 'solution', label: `解题模型（${solutionModels.length}）`, children: <SolutionModelTab /> },
        ]}
      />
    </PageFrame>
  )
}
