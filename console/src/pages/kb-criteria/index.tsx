import { useEffect, useMemo, useState } from 'react'
import { Alert, Card, Empty, Input, Segmented, Space, Spin, Tabs, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { kbApi } from '@/kb/api'
import type { KbCriteria, KbCriterion } from '@/kb/types'

/**
 * 维护 · 判据沉淀 · 真库 /kb/criteria（PRD-007 线2 去 mock 第 3 页）
 *
 * 版面照搬 mock 页 /criteria（注入机制说明 + 产线页签 + 现行/废止分段 + 一条一张卡），
 * 数据换成真库：GET /api/kb/criteria（criterion 表）。
 *
 * 🔴 和「错因管理」的分工一句话分清：错因沉淀**学生**的错（挂考点）；本页沉淀**产线自己**的
 *   判断经验（挂产线）。写错地方就查不着。
 * 🔴 **废止不混现行**：默认只看现行（日常来这页是问「现在按什么口径干活」），
 *   废止的整卡压灰 + 写出**替代链**（被谁替代了）。agent 开工注入永远只取现行——
 *   把废止的混进现行 = 把已经被推翻的口径又注回 agent，是最坏的一种错。
 * 🔴 产线页签**按库里真有的线出**（criterion.line 的 CHECK 有四条线：录入/批改/出题/渲染，
 *   但库里现在只有几条线有货）——不给没有的线渲成「0 条」的空页签装门面。
 * 🔴 本页只读：沉淀一条新判据、废止一条老判据，都是 agent 干完活之后的动作，不在这页开表单。
 */

const LINE_COLOR: Record<string, string> = { 录入: 'blue', 批改: 'cyan', 出题: 'purple', 渲染: 'gold' }
/** 废止卡的底色：最浅一档，够看出「这条不算数了」，不至于变成大色块 */
const DEPRECATED_BG = '#fafafa'

function CriterionCard({ c }: { c: KbCriterion }) {
  const dead = c.status === '废止'
  return (
    <Card
      size="small"
      style={{ background: dead ? DEPRECATED_BG : undefined }}
      styles={{ body: { padding: '12px 14px', opacity: dead ? 0.72 : 1 } }}
    >
      <Space size={8} align="center" wrap style={{ marginBottom: 6 }}>
        <Tag color={dead ? undefined : LINE_COLOR[c.line]} style={{ marginInlineEnd: 0 }}>
          {c.line}
        </Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
          {c.id}
        </Typography.Text>
        {/* scene 加粗：走查时先看「什么时候会撞上这条」，再看怎么判 */}
        <Typography.Text strong={!dead} type={dead ? 'secondary' : undefined} style={{ fontSize: 14 }}>
          {c.scene}
        </Typography.Text>
        {dead ? <Tag style={{ marginInlineEnd: 0 }}>已废止</Tag> : null}
      </Space>

      <Typography.Paragraph
        type={dead ? 'secondary' : undefined}
        style={{ fontSize: 13, lineHeight: 1.85, margin: 0, whiteSpace: 'pre-wrap' }}
      >
        {c.rule}
      </Typography.Paragraph>

      {c.why ? (
        <Typography.Paragraph type="secondary" style={{ fontSize: 12.5, lineHeight: 1.8, margin: '6px 0 0' }}>
          为什么：{c.why}
        </Typography.Paragraph>
      ) : null}

      {/* 🔴 废止不是删除：替代链必须写在卡上，否则「这条为什么不算数了」就断在这儿 */}
      {dead && c.superseded_by ? (
        <Typography.Paragraph style={{ fontSize: 12.5, lineHeight: 1.8, margin: '6px 0 0' }}>
          <Typography.Text type="secondary">已被 </Typography.Text>
          <Typography.Text strong style={{ fontSize: 12.5, fontFamily: 'monospace' }}>
            {c.superseded_by}
          </Typography.Text>
          {c.superseded_by_info?.missing ? (
            <Typography.Text type="danger" style={{ fontSize: 12.5 }}>
              （🔴 替代链断了：库里没有这条 id）
            </Typography.Text>
          ) : (
            <Typography.Text type="secondary">
              「{c.superseded_by_info?.scene}」（{c.superseded_by_info?.status}）替代 ——
              本条不再注入，留档只为查「当年为什么那么干」。
            </Typography.Text>
          )}
        </Typography.Paragraph>
      ) : null}

      <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
        来源：{c.source_ref ?? '—'}
        {c.created_at ? ` · ${c.created_at}` : ''}
      </Typography.Text>
    </Card>
  )
}

export function KbCriteriaPage() {
  const [d, setD] = useState<KbCriteria | null>(null)
  const [err, setErr] = useState('')
  const [keyword, setKeyword] = useState('')
  /** 🔴 线与状态挂在 URL 上：「某条线的现行判据」这一屏要能直链（agent 注入口径的人肉对照面） */
  const [searchParams, setSearchParams] = useSearchParams()
  const line = searchParams.get('line') || '全部'
  const status: '现行' | '废止' = searchParams.get('status') === '废止' ? '废止' : '现行'
  const setParam = (k: string, v: string, dflt: string) => {
    const next = new URLSearchParams(searchParams)
    if (v === dflt) next.delete(k)
    else next.set(k, v)
    setSearchParams(next, { replace: true })
  }
  const setLine = (v: string) => setParam('line', v, '全部')
  const setStatus = (v: '现行' | '废止') => setParam('status', v, '现行')

  useEffect(() => {
    kbApi
      .criteria()
      .then(setD)
      .catch((e) => setErr(String(e.message ?? e)))
  }, [])

  /** 当前产线范围内的全部判据（统计条按这个范围算——注入本来就是按线取的） */
  const scope = useMemo(() => {
    if (!d) return []
    return line === '全部' ? d.rows : d.rows.filter((c) => c.line === line)
  }, [d, line])

  const stat = useMemo(() => {
    const live = scope.filter((c) => c.status === '现行').length
    return { total: scope.length, live, dead: scope.length - live }
  }, [scope])

  const filtered = useMemo(() => {
    const kw = keyword.trim()
    return scope.filter((c) => {
      if (c.status !== status) return false
      // 搜索面覆盖编号/场景/规则/理由/来源：找一条判据时，人记得住的常常是「哪次事故」而不是规则原文
      if (kw && !`${c.id}${c.scene}${c.rule}${c.why ?? ''}${c.source_ref ?? ''}`.includes(kw)) return false
      return true
    })
  }, [scope, status, keyword])

  return (
    <PageFrame
      title="维护 · 判据沉淀 · 真库"
      desc={
        <>
          错因管理沉淀的是<b>学生</b>的错（挂考点）；本页沉淀的是<b>产线自己</b>的判断经验（挂产线）——
          录题怎么拆、批改怎么判、出题怎么防坑。每条判据来自一次真实事故或一次拍板，是 agent 干活时的注入依据：
          agent 领某条线的任务，开工时<b>按线全量注入「现行」判据</b>；废止的不注入，但留档可查。
          数据直连 kb.db 的 criterion 表，沉淀与废止都是 agent 的动作，本页只读。
        </>
      }
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {d ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              全库 {d.total} 条 · 现行 {d.live_total} · 废止 {d.dead_total}
            </Typography.Text>
          ) : null}
        </Space>
      }
    >
      {err ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message="读 API 出错"
          description={
            <>
              {err}
              <br />
              起服务：<Typography.Text code>python 工具箱\启动台.py</Typography.Text>（:4310 读 API）
            </>
          }
        />
      ) : null}

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

      {!d ? (
        err ? null : (
          <Spin />
        )
      ) : (
        <>
          {/* 产线页签只按库里真有的线出：CHECK 允许四条线，没货的线不渲空页签装门面 */}
          <Tabs
            activeKey={line}
            onChange={setLine}
            items={[
              { key: '全部', label: `全部（${d.total}）` },
              ...d.line_stat.map((l) => ({ key: l.line, label: `${l.line}（${l.total}）` })),
            ]}
            style={{ marginBottom: 4 }}
          />

          <Space size={10} wrap style={{ marginBottom: 10 }}>
            {/* 默认落「现行」：日常来这页是想知道「现在按什么口径干活」，废止的是查档才看 */}
            <Segmented
              value={status}
              onChange={(v) => setStatus(v === '废止' ? '废止' : '现行')}
              options={[
                { label: `现行（${stat.live}）`, value: '现行' },
                { label: `废止（${stat.dead}）`, value: '废止' },
              ]}
            />
            <Input.Search
              allowClear
              placeholder="搜编号 / 场景 / 规则 / 来源事故"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ width: 280 }}
            />
          </Space>

          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 12px' }}>
            {line === '全部' ? '共' : `${line}线共`} {stat.total} 条 · 现行 {stat.live} · 废止 {stat.dead}
            {' ｜ '}
            agent 开工注入口径：按线取全部现行
            {keyword.trim() ? ` ｜ 当前搜索命中 ${filtered.length} 条` : ''}
            {' ｜ '}
            库里现有产线：{d.line_stat.map((l) => `${l.line} ${l.total}`).join(' / ')}
            （criterion.line 的值域是 录入/批改/出题/渲染 四条，其余三条现在<b>一条都没有</b>——是欠账不是筛没了）
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
            走查提示：点「废止（{d.dead_total}）」看被推翻的判据长什么样 —— 卡还在、整卡压灰、
            替代链写着「已被 XXX 替代」，但 agent 开工时一条都不会拿到。
          </Typography.Paragraph>
        </>
      )}
    </PageFrame>
  )
}

export default KbCriteriaPage
