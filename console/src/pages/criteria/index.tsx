import { useMemo, useState } from 'react'
import { Alert, Card, Empty, Input, Segmented, Space, Tabs, Tag, Typography } from 'antd'
import { PageFrame } from '@/components'
import type { Criterion, CriterionLine, CriterionStatus } from './criteria-mock'
import { CRITERIA, CRITERION_LINES } from './criteria-mock'

/**
 * 维护 · 判据沉淀 /criteria
 * 归属：页面组「维护」。只改本目录，别动 layout / mock / components（Shell/App 只挂了一个新项）。
 *
 * 🔴🔴 走查判词（R3-②）原话：**录题线也要有判断经验沉淀、原有流水线的判断依据要保存、
 *   都得有可查看的页面**。所以有了这一页。
 *
 * 🔴 和「错因管理」的分工，一句话就能分清 —— 两页都在沉淀经验，但沉淀的是**两拨人的错**：
 *   - 错因管理：沉淀**学生**的错，挂**考点**（这孩子在哪类题上反复栽跟头）
 *   - 判据沉淀：沉淀**产线自己**的判断经验，挂**产线**（录题怎么拆、批改怎么判、出题怎么防坑）
 *   写错地方就查不着：学生错了去 /cause，我们自己判错了来这里。
 *
 * 🔴 每条判据都来自一次真实事故或一次拍板 —— 这页**没有一条是编的**（编出来的「经验」
 *   注入给 agent 比没有更坏）。所以 mock 里查不到出处的 why 宁可留空。
 *
 * 🔴 本页**只读**：沉淀一条新判据、废止一条老判据，都是 agent 干完活之后的动作，
 *   不在这页开表单。这页是给人看「现在这条线按什么口径干活」的窗口。
 */

/** 产线 Tab 的可选值（'全部' 只是个筛子，不是第四条线） */
const TAB_KEYS = ['全部', ...CRITERION_LINES] as const
type TabKey = (typeof TAB_KEYS)[number]

/** Tabs / Segmented 回调给的是宽类型，用查表收窄，避免类型断言 */
function toTabKey(k: string): TabKey {
  return TAB_KEYS.find((t) => t === k) ?? '全部'
}
function toStatus(v: string | number): CriterionStatus {
  return v === '废止' ? '废止' : '现行'
}

/** 产线 → Tag 颜色（只用 antd 默认色板，不自定义主色、不铺大色块） */
const lineColor: Record<CriterionLine, string> = {
  录入: 'blue',
  批改: 'cyan',
  出题: 'purple',
}

/** 废止卡的底色：最浅一档，够看出「这条不算数了」，不至于变成大色块 */
const DEPRECATED_BG = '#fafafa'

/** 一条判据一张卡。废止的整卡压灰，并把替代链写出来 */
function CriterionCard({ c }: { c: Criterion }) {
  const dead = c.status === '废止'
  return (
    <Card
      size="small"
      style={{ background: dead ? DEPRECATED_BG : undefined }}
      styles={{ body: { padding: '12px 14px', opacity: dead ? 0.72 : 1 } }}
    >
      <Space size={8} align="center" wrap style={{ marginBottom: 6 }}>
        <Tag color={dead ? undefined : lineColor[c.line]} style={{ marginInlineEnd: 0 }}>
          {c.line}
        </Tag>
        {/* scene 加粗：走查时先看「什么时候会撞上这条」，再看怎么判 */}
        <Typography.Text strong={!dead} type={dead ? 'secondary' : undefined} style={{ fontSize: 14 }}>
          {c.scene}
        </Typography.Text>
        {dead ? (
          <Tag style={{ marginInlineEnd: 0 }}>已废止</Tag>
        ) : null}
      </Space>

      <Typography.Paragraph
        type={dead ? 'secondary' : undefined}
        style={{ fontSize: 13, lineHeight: 1.85, margin: 0 }}
      >
        {c.rule}
      </Typography.Paragraph>

      {c.why ? (
        <Typography.Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.8, margin: '6px 0 0' }}>
          为什么：{c.why}
        </Typography.Paragraph>
      ) : null}

      {/* 🔴 废止不是删除：替代链必须写在卡上，否则「这条为什么不算数了」就断在这儿 */}
      {dead && c.supersededBy ? (
        <Typography.Paragraph style={{ fontSize: 12.5, lineHeight: 1.8, margin: '6px 0 0' }}>
          <Typography.Text type="secondary">已被 </Typography.Text>
          <Typography.Text strong style={{ fontSize: 12.5 }}>
            {c.supersededBy}
          </Typography.Text>
          <Typography.Text type="secondary"> 替代 —— 本条不再注入，留档只为查「当年为什么那么干」。</Typography.Text>
        </Typography.Paragraph>
      ) : null}

      <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
        来源：{c.sourceRef} · {c.date}
      </Typography.Text>
    </Card>
  )
}

export default function Criteria() {
  const [line, setLine] = useState<TabKey>('全部')
  const [status, setStatus] = useState<CriterionStatus>('现行')
  const [keyword, setKeyword] = useState('')

  /** 当前产线范围内的全部判据（统计条按这个范围算 —— 注入本来就是按线取的） */
  const scope = useMemo(() => (line === '全部' ? CRITERIA : CRITERIA.filter((c) => c.line === line)), [line])

  const stat = useMemo(() => {
    const live = scope.filter((c) => c.status === '现行').length
    return { total: scope.length, live, dead: scope.length - live }
  }, [scope])

  const filtered = useMemo(() => {
    const kw = keyword.trim()
    return scope.filter((c) => {
      if (c.status !== status) return false
      // 搜索面覆盖场景/规则/理由/来源：找一条判据时，人记得住的常常是「哪次事故」而不是规则原文
      if (kw && !`${c.scene}${c.rule}${c.why ?? ''}${c.sourceRef}`.includes(kw)) return false
      return true
    })
  }, [scope, status, keyword])

  return (
    <PageFrame
      title="维护 · 判据沉淀"
      desc={
        <>
          错因管理沉淀的是<b>学生</b>的错（挂考点）；本页沉淀的是<b>产线自己</b>的判断经验（挂产线）——
          录题怎么拆、批改怎么判、出题怎么防坑。每条判据来自一次真实事故或一次拍板，是 agent 干活时的注入依据：
          agent 领某条线的任务，开工时<b>按线全量注入「现行」判据</b>；废止的不注入，但留档可查。
          沉淀与废止都是 agent 的动作，本页只读。
        </>
      }
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          全库 {CRITERIA.length} 条 · 现行 {CRITERIA.filter((c) => c.status === '现行').length} 条
        </Typography.Text>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="注入机制：agent 开工时怎么拿到这些判据"
        description={
          <ol style={{ margin: '4px 0 0', paddingInlineStart: 18, fontSize: 13, lineHeight: 1.9 }}>
            <li>
              <b>开工注入 = 按线全量取现行</b>。agent 领的是「录入」的活就把录入线全部现行判据灌进去，
              百条量级全量比检索稳 —— 检索会漏，而漏掉的那条往往正是这次要踩的坑。
            </li>
            <li>
              <b>量大之后再走语意检索补充</b>，复用资料 RAG 那套基建；但检索是补充，不是替代全量。
            </li>
            <li>
              <b>判据可被推翻</b>。废止不删除、留档并带替代链（见下面压灰的卡），
              注入永远只取现行 —— 留档是给人查「当年为什么那么干」的，不进 agent 的上下文。
            </li>
          </ol>
        }
      />

      {/* 产线 Tabs 只当筛子用：内容统一在下面渲染一次，不给每个页签各铺一份 */}
      <Tabs
        activeKey={line}
        onChange={(k) => setLine(toTabKey(k))}
        items={TAB_KEYS.map((k) => ({
          key: k,
          label: k === '全部' ? `全部（${CRITERIA.length}）` : `${k}（${CRITERIA.filter((c) => c.line === k).length}）`,
        }))}
        style={{ marginBottom: 4 }}
      />

      <Space size={10} wrap style={{ marginBottom: 10 }}>
        {/* 默认落「现行」：日常来这页是想知道「现在按什么口径干活」，废止的是查档才看 */}
        <Segmented
          value={status}
          onChange={(v) => setStatus(toStatus(v))}
          options={[
            { label: `现行（${stat.live}）`, value: '现行' },
            { label: `废止（${stat.dead}）`, value: '废止' },
          ]}
        />
        <Input.Search
          allowClear
          placeholder="搜场景 / 规则 / 来源事故"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          style={{ width: 260 }}
        />
      </Space>

      {/* 统计条：注入口径直接写在这里，走查时不用问「那 agent 到底吃哪些」 */}
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 12px' }}>
        {line === '全部' ? '共' : `${line}线共`} {stat.total} 条 · 现行 {stat.live} · 废止 {stat.dead}
        {' ｜ '}
        agent 开工注入口径：按线取全部现行
        {keyword.trim() ? ` ｜ 当前搜索命中 ${filtered.length} 条` : ''}
      </Typography.Paragraph>

      {filtered.length > 0 ? (
        <Space direction="vertical" size={10} style={{ display: 'flex' }}>
          {filtered.map((c) => (
            <CriterionCard key={c.id} c={c} />
          ))}
        </Space>
      ) : (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Typography.Text type="secondary" style={{ fontSize: 13 }}>
              {status === '废止' && !keyword.trim()
                ? // 空在这里是好消息，不是缺数据，得说清楚
                  `${line === '全部' ? '' : `${line}线`}还没有被推翻过的判据 —— 现有口径至今站得住。`
                : '没有匹配的判据，换个词试试。'}
            </Typography.Text>
          }
        />
      )}

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 14, marginBottom: 0 }}>
        走查提示：切到「录入」线再点「废止」，能看见两条压灰的卡（TextIn 云 OCR 自动回落、乱序闸拦截式报错）——
        那就是「判据被推翻」长什么样：卡还在、替代链写着，但 agent 开工时一条都不会拿到。
      </Typography.Paragraph>
    </PageFrame>
  )
}
