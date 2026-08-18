import { useMemo, useState } from 'react'
import { Card, Col, Row, Statistic, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import { kpVocabulary, questions } from '@/mock'
import { KgTree } from './KgTree'
import { LeafDetail } from './LeafDetail'
import type { LeafPatch, MaintMap } from './maint'
import { aliasTotals, dirtyKeys, initialMaint, patchOf } from './maint'
import { resolveKpParam, traceGaps } from './trace'
import { LEAVES, MOUNTED_LEAF_COUNT, TREE_STATS, ZERO_MOUNT_KEYS } from './tree-view'

/** 断点词太多时走查提示只报前几个（全量看 /model 与 /cause 那两张表，那儿一条不落） */
function gapPreview(names: string[], head = 4): string {
  return names.length <= head ? names.join('、') : `${names.slice(0, head).join('、')} 等 ${names.length} 个`
}

/**
 * 维护 · 知识图谱 /kg
 * 归属：页面组「维护」。只改本目录，别动 layout / mock / components。
 *
 * 这页是教材树的**维护视图**：树长什么样、每片叶挂了几道题、哪一枝还没铺、词表乱不乱。
 * 🔴 与题库页的分工：题库页用树**筛题**（左树右表），本页用树**看家底**
 *   （哪里空、哪里挤、哪片改过名），两页共用同一棵 kgTree，别各造一棵。
 * 🔴 「未铺」的枝（isStub 为真）必须如实标出来——空目录假装铺好了是事故。
 * 🔴 写动作的边界：别名 / 改名 / 退役是**词表**级的轻量动作，本页给原型演示态
 *   （只改本地 state、不落库）；建叶子 / 改归属 / 删节点这类**结构**动作一概不做，走 agent。
 *
 * 🔴🔴 第三轮判词⑤：**维护区三样（错因 / 考察模型 / 题目）都要能溯源到知识图谱，
 *   考点详情 = 聚合落点**。所以本页多了一个入口身份：/model、/cause、/questions/:id
 *   点考点名一律带 `?kp=<树key>` 落到这里并选中那片叶（换算与聚合的唯一实现 = trace.ts）。
 * 🔴 选中挂在 URL 上、不做本地 state：外面点进来要能直接选中，这是四个页面之间唯一的传话口径
 *   （与 /questions 的 ?tree= 同一套做法）。
 */
export default function Kg() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [zeroOnly, setZeroOnly] = useState(false)
  const [maint, setMaint] = useState<MaintMap>(initialMaint)

  /**
   * 选中的树 key = URL 的 ?kp=。
   * 🔴 一律过 resolveKpParam 洗一遍：URL 里塞了树上没有的值（手敲错、树改过、
   *   或者外面传的是考点名而不是 key）一律回落成「没选中」，不许让页面显示一条假路径。
   */
  const selectedKey = resolveKpParam(searchParams.get('kp') ?? '')
  const setSelectedKey = (key: string) => {
    const next = new URLSearchParams(searchParams)
    if (key) next.set('kp', key)
    else next.delete('kp')
    // replace：树上点来点去不该在浏览器后退栈里堆一串记录
    setSearchParams(next, { replace: true })
  }

  /** 🔴 溯源欠账：考点词在树上找不到同名叶 / 模型一片叶都没挂——都是活儿，不是正常态 */
  const gaps = useMemo(() => traceGaps(), [])

  const alias = useMemo(() => aliasTotals(maint), [maint])
  const dirty = useMemo(() => dirtyKeys(maint), [maint])
  const retiredCount = useMemo(() => Object.values(maint).filter((p) => p.retired).length, [maint])

  /**
   * kpVocabulary（题库页考点下拉的词表）与树叶的对账。
   * 🔴 两处各管一头：树管**归属**、词表管**能力标签**。但词表里的词必须在树上找得到同名叶，
   *   否则筛出来的题和树里的对不上——维护页要能一眼看出这个账平没平。
   */
  const vocabMiss = useMemo(() => {
    const names = new Set(LEAVES.map((n) => n.label))
    return kpVocabulary.filter((w) => !names.has(w))
  }, [])

  /** 别名 / 改名 / 退役：都是本地 state 上的合并写，不落库 */
  const patchLeaf = (key: string, fn: (prev: LeafPatch) => LeafPatch) =>
    setMaint((prev) => ({ ...prev, [key]: fn(patchOf(prev, key)) }))

  return (
    <PageFrame
      title="维护 · 知识图谱"
      desc="低频维护区——日常不来，来了就是治理。教材树的家底：版本 → 年级学期 → 单元 → 小节 → 考点五层，哪片叶挂了题、哪一枝还没铺、词表乱没乱。"
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          考点叶 {TREE_STATS.考点} 片 · 已挂树的题 {questions.filter((q) => q.treePath !== undefined).length}/
          {questions.length} 道（mock）
          {dirty.length > 0 ? (
            <Tag color="orange" style={{ marginInlineStart: 8, marginInlineEnd: 0 }}>
              本页临时改动 {dirty.length} 处
            </Tag>
          ) : null}
        </Typography.Text>
      }
    >
      {/* ① 五张统计卡：各回答一个维护问题，数字全部由 kgTree + questions + 本地维护态现算 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic title="考点总数" value={TREE_STATS.考点} suffix="片叶" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              分布在 {TREE_STATS.单元} 个单元 / {TREE_STATS.小节} 个小节
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic title="教材树 · 未铺的枝" value={TREE_STATS.未铺} suffix="枝" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              共 {TREE_STATS.版本} 个版本 / {TREE_STATS.年级学期} 个学期，只有人教·四上铺满
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic title="别名" value={alias.条数} suffix="条" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              覆盖 {alias.覆盖叶子} 片叶{retiredCount > 0 ? ` · 已退役 ${retiredCount} 片` : ''}
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic
              title="挂载"
              value={MOUNTED_LEAF_COUNT}
              suffix={`/ ${TREE_STATS.考点} 片有题`}
              valueStyle={{ fontSize: 22 }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              零挂载 {ZERO_MOUNT_KEYS.length} 片 —— 维护时最该看的一屏
            </Typography.Text>
          </Card>
        </Col>
        {/* 🔴 判词⑤ 的欠账卡：模型 / 错因说的考点，树上到底认不认得 */}
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic
              title="溯源断点"
              value={gaps.offTreeKpNames.length}
              suffix="个考点词没上树"
              valueStyle={{ fontSize: 22 }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              另有 {gaps.modelsWithoutKp.length} 个模型一片叶都没挂 —— 溯源到这儿就断了
            </Typography.Text>
          </Card>
        </Col>
      </Row>

      {/* ② 左树右详情 */}
      <Row gutter={[12, 12]} wrap>
        <Col flex="0 1 340px" style={{ minWidth: 280 }}>
          <KgTree
            selectedKey={selectedKey}
            onSelectKey={setSelectedKey}
            maint={maint}
            zeroOnly={zeroOnly}
            onZeroOnlyChange={setZeroOnly}
          />
        </Col>
        <Col flex="1 1 520px" style={{ minWidth: 0 }}>
          <LeafDetail
            selectedKey={selectedKey}
            maint={maint}
            onAddAlias={(key, a) =>
              patchLeaf(key, (p) => (p.aliases.includes(a) ? p : { ...p, aliases: [...p.aliases, a] }))
            }
            onRemoveAlias={(key, a) => patchLeaf(key, (p) => ({ ...p, aliases: p.aliases.filter((x) => x !== a) }))}
            onRename={(key, n) => patchLeaf(key, (p) => ({ ...p, renamedTo: n }))}
            onRetire={(key, retired) => patchLeaf(key, (p) => ({ ...p, retired }))}
          />
        </Col>
      </Row>

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：勾「只看零挂载考点」= 缺口清单（{ZERO_MOUNT_KEYS.length} 片叶还没题）；点「四年级下册（未铺）」
        看空壳枝怎么标。
        <b> 聚合落点看这两片</b>：「四则混合运算的运算顺序」（第四单元 · 运算顺序与运算律）四小节全满——
        题、考察模型、错因、最近沉淀一次看齐；「三位数乘两位数的计算」（第四单元 · 笔算乘法）
        一道题都没挂，却挂着 1 个考察模型 + 1 条错因 + 1 条沉淀——
        <b>零挂载不等于没家当</b>，这正是聚合落点要回答的问题（光看「挂载」那张卡是看不出来的）。
        从 /model、/cause、/questions/:id 点考点名进来会带 ?kp=&lt;树key&gt; 直接选中对应的叶。
        {vocabMiss.length === 0
          ? ` 题库页考点词表 ${kpVocabulary.length} 个词已全部在树上找到同名叶，两条轴对得上。`
          : ` ⚠️ 有 ${vocabMiss.length} 个考点词在树上找不到同名叶：${vocabMiss.join('、')}。`}
        {gaps.offTreeKpNames.length > 0
          ? ` 🔴 另有 ${gaps.offTreeKpNames.length} 个考点词只在模型 / 错因里出现、树上没有同名叶（${gapPreview(gaps.offTreeKpNames)}），在 /model 与 /cause 里渲成灰色虚线「未上树」的就是它们。`
          : ''}
      </Typography.Paragraph>
    </PageFrame>
  )
}
