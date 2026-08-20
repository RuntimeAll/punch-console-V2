import { useCallback, useEffect, useMemo, useState } from 'react'
import type { Key } from 'react'
import {
  Alert,
  Card,
  Checkbox,
  Col,
  Empty,
  Input,
  Row,
  Segmented,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Tree,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { DataNode } from 'antd/es/tree'
import { useSearchParams } from 'react-router-dom'
import PageFrame from '@/components/PageFrame'
import { kbApi } from '@/kb/api'
import type { KbAliasRow, KbAliases, KbKgPatterns, KbKpDetail, KbKpNode, KbTree } from '@/kb/types'
import '@/kb/kb.css'
import { KpDetail } from './KpDetail'
import { PatternFate } from './PatternFate'

/**
 * 维护 · 知识图谱 /kg（PRD-007 线2 去 mock 第 1 页；2026-08-21 真库转正为正式页）
 *
 * 版面照搬 mock 页 /kg 的设计（五张统计卡 + 左树右详情 + 走查提示），数据全换成真库：
 *   GET /api/kb/kg/tree（kp 102 节点五层树）· GET /api/kb/kp/:id（节点详情）· GET /api/kb/kg/aliases（别名层）
 *
 * 🔴 与 mock 页的两处硬差别，都是「不许骗人」：
 *   ① mock 页的加别名 / 改名 / 退役是**原型演示态**（只改本地 state）——真库页一个写按钮都没有，
 *      建叶改树类动作一律「走 agent」的提示文案（唯一写入通路 = KG维护 skill / 工具箱/kg/kg_tool.py）；
 *   ② 数字一律现算于库，不留 mock 常量：零挂载、别名覆盖、一词多挂、别名断链全是 API 现算的。
 * 🔴 选中挂在 URL 的 ?kp= 上（与 mock 页同一套传话口径）：外面点进来要能直接选中那片叶。
 */

const STATUS_COLOR: Record<string, string> = { 现行: 'green', 未铺: 'orange', 退役: 'default' }

/** 树节点标题：灰字 = 这儿是空的（未铺的枝 / 零挂载的叶 / 已退役的叶），与 mock 页同一套读法 */
function nodeTitle(n: KbKpNode) {
  const leaf = n.children.length === 0
  const zero = leaf && n.q_count === 0
  const dim = n.status === '未铺' || n.status === '退役' || zero
  const suffix = { marginLeft: 6, fontSize: 12, color: 'rgba(0,0,0,0.45)', fontWeight: 400 } as const
  return (
    <span
      title={
        n.status === '未铺'
          ? '这一枝还没铺：教材树上只有个名字，底下的单元/小节/考点都没建'
          : zero
            ? '零挂载：这片考点叶目前一道题都没挂'
            : n.name
      }
      style={{ color: dim ? 'rgba(0,0,0,0.38)' : undefined, whiteSpace: 'nowrap' }}
    >
      {n.name}
      {n.q_total > 0 ? <span style={suffix}>{leaf ? n.q_count : n.q_total} 题</span> : null}
      {n.alias_count > 0 ? <span style={suffix}>别名 {n.alias_count}</span> : null}
      {n.status === '未铺' ? <span style={suffix}>未铺</span> : null}
      {n.status === '退役' ? <span style={suffix}>已退役</span> : null}
    </span>
  )
}

/** 只看零挂载：裁掉走不到零挂载叶的枝（未铺的空壳枝自然被裁掉） */
function prune(nodes: KbKpNode[]): KbKpNode[] {
  const out: KbKpNode[] = []
  for (const n of nodes) {
    if (n.children.length === 0) {
      if (n.q_count === 0) out.push(n)
      continue
    }
    const kids = prune(n.children)
    if (kids.length) out.push({ ...n, children: kids })
  }
  return out
}

function toTreeData(nodes: KbKpNode[]): DataNode[] {
  return nodes.map((n) => ({
    key: n.id,
    title: nodeTitle(n),
    children: n.children.length ? toTreeData(n.children) : undefined,
  }))
}

/** 树上全部节点（拍平，用来算展开键与统计） */
function flatten(nodes: KbKpNode[]): KbKpNode[] {
  return nodes.flatMap((n) => [n, ...flatten(n.children)])
}

/** 某节点的祖先键（外面带 ?kp= 进来要把枝撑开，否则叶子藏在收起的枝里） */
function ancestorsOf(nodes: KbKpNode[], id: string): string[] {
  const path: string[] = []
  const walk = (list: KbKpNode[], trail: string[]): boolean => {
    for (const n of list) {
      if (n.id === id) {
        path.push(...trail)
        return true
      }
      if (walk(n.children, [...trail, n.id])) return true
    }
    return false
  }
  walk(nodes, [])
  return path
}

export function KbKg() {
  const [tree, setTree] = useState<KbTree | null>(null)
  const [alias, setAlias] = useState<KbAliases | null>(null)
  const [patterns, setPatterns] = useState<KbKgPatterns | null>(null)
  const [patternErr, setPatternErr] = useState('')
  const [detail, setDetail] = useState<KbKpDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [err, setErr] = useState('')

  const [zeroOnly, setZeroOnly] = useState(false)
  const [expanded, setExpanded] = useState<Key[]>([])
  const [aliasKind, setAliasKind] = useState<string>('全部')
  const [aliasKw, setAliasKw] = useState('')

  const [searchParams, setSearchParams] = useSearchParams()
  const selected = searchParams.get('kp') ?? ''
  const setSelected = useCallback(
    (key: string) => {
      const next = new URLSearchParams(searchParams)
      if (key) next.set('kp', key)
      else next.delete('kp')
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  useEffect(() => {
    kbApi
      .tree()
      .then((t) => {
        setTree(t)
        // 默认展开到单元层：版本 / 年级学期两层撑开，单元露头但不再往下铺
        setExpanded(
          flatten(t.roots)
            .filter((n) => (n.level === '版本' || n.level === '年级学期') && n.children.length > 0)
            .map((n) => n.id),
        )
      })
      .catch((e) => setErr(String(e.message ?? e)))
    kbApi
      .aliases()
      .then(setAlias)
      .catch((e) => setErr(String(e.message ?? e)))
    // 🔴 题型下落读的是磁盘正本文件，挂了不该把整页拖红——单独收错，本块自己显示原因
    kbApi
      .kgPatterns()
      .then(setPatterns)
      .catch((e) => setPatternErr(String(e.message ?? e)))
  }, [])

  useEffect(() => {
    if (!selected) {
      setDetail(null)
      return
    }
    setDetailLoading(true)
    kbApi
      .kp(selected)
      .then((d) => {
        setDetail(d)
        setErr('')
      })
      .catch((e) => setErr(String(e.message ?? e)))
      .finally(() => setDetailLoading(false))
  }, [selected])

  // 外面带 ?kp= 进来：把祖先撑开，不然人跳过来只看到右边详情变了、左树没反应
  useEffect(() => {
    if (!selected || !tree) return
    setExpanded((prev) => Array.from(new Set([...prev, ...ancestorsOf(tree.roots, selected), selected])))
  }, [selected, tree])

  const shown = useMemo(() => (tree ? (zeroOnly ? prune(tree.roots) : tree.roots) : []), [tree, zeroOnly])
  const treeData = useMemo(() => toTreeData(shown), [shown])

  useEffect(() => {
    if (!zeroOnly) return
    // 裁过的树很窄，全展开才看得见叶子
    setExpanded(
      flatten(shown)
        .filter((n) => n.children.length > 0)
        .map((n) => n.id),
    )
  }, [zeroOnly, shown])

  /** 统计一律现算于树，不写死 */
  const stat = useMemo(() => {
    if (!tree) return null
    const all = flatten(tree.roots)
    const leaves = all.filter((n) => n.children.length === 0)
    const byLevel = (lv: string) => all.filter((n) => n.level === lv).length
    return {
      node_total: tree.kp_total,
      leaf_total: leaves.length,
      unit: byLevel('单元'),
      section: byLevel('小节'),
      unbuilt: tree.unbuilt_total,
      retired: all.filter((n) => n.status === '退役').length,
      mounted: leaves.filter((n) => n.q_count > 0).length,
      zero: leaves.filter((n) => n.q_count === 0).length,
      q_total: tree.roots.reduce((s, r) => s + r.q_total, 0),
    }
  }, [tree])

  const aliasRows = useMemo(() => {
    if (!alias) return []
    const kw = aliasKw.trim()
    return alias.rows.filter((r) => {
      if (aliasKind !== '全部' && (r.alias_kind ?? '未标来源') !== aliasKind) return false
      if (kw && !`${r.alias}${r.kp_name ?? ''}`.includes(kw)) return false
      return true
    })
  }, [alias, aliasKind, aliasKw])

  const aliasCols: ColumnsType<KbAliasRow> = [
    {
      title: '别名（产线/讲义/老区的叫法）',
      dataIndex: 'alias',
      width: 260,
      render: (v: string) => <Typography.Text style={{ fontSize: 13 }}>{v}</Typography.Text>,
    },
    {
      title: '来源',
      dataIndex: 'alias_kind',
      width: 120,
      render: (v: string | null) => <Tag style={{ marginInlineEnd: 0 }}>{v ?? '未标来源'}</Tag>,
    },
    {
      title: '翻到哪片叶',
      key: 'kp',
      render: (_, r) =>
        r.missing ? (
          <span style={{ color: '#cf1322' }}>🔴 断链：kp {r.kp_id} 不在库里</span>
        ) : (
          <Typography.Link onClick={() => setSelected(r.kp_id)}>{r.kp_name}</Typography.Link>
        ),
    },
    {
      title: '叶状态',
      dataIndex: 'kp_status',
      width: 90,
      render: (v: string | null) =>
        v ? <Tag color={STATUS_COLOR[v] ?? 'default'}>{v}</Tag> : <span style={{ color: 'rgba(0,0,0,0.25)' }}>—</span>,
    },
  ]

  return (
    <PageFrame
      title="维护 · 知识图谱"
      desc="低频维护区——日常不来，来了就是治理。教材树的家底：版本 → 年级学期 → 单元 → 小节 → 考点五层，哪片叶挂了题、哪一枝还没铺、别名词表乱没乱。数据直连 kb.db（kp / kp_alias / question_kp），页面只读。"
      extra={
        <Space size={8} wrap>
          <Tag color="green">真库 · 只读</Tag>
          {stat ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {/* 🔴 说「挂靠处数」不说「题数」：一题挂两片叶就是两处，按树求和必然大于题总数，
                  写成「已挂题 N 道」就是把 1118 处说成 1118 道题（库里只有 1090 道） */}
              kp {stat.node_total} 节点 · 考点叶 {stat.leaf_total} 片 · 考点挂靠 {stat.q_total} 处
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

      {/* 🔴 门禁上脸：这页能干什么、不能干什么，先说清楚 */}
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="建叶 / 改树类操作不在页面上——走 agent"
        description={
          <span style={{ fontSize: 13, lineHeight: 1.9 }}>
            铺枝、建考点叶、改归属、加别名、改名、退役，全部是 <b>KG维护 skill</b> 的活
            （唯一写入通路 = <Typography.Text code>工具箱/kg/kg_tool.py</Typography.Text>，每次执行自动落 skill_log）。
            本页只负责把家底如实摆出来：<b>零挂载 = 目录有、题没有</b>（是缺口不是坏账），
            <b>未铺 = 有名字、没目录</b>，<b>别名断链 / 一词多挂</b> = 词表坏账（下面那张表会标红）。
          </span>
        }
      />

      {/* ① 五张统计卡：各回答一个维护问题，数字全部现算于库 */}
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic title="考点总数" value={stat?.leaf_total ?? 0} suffix="片叶" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              分布在 {stat?.unit ?? 0} 个单元 / {stat?.section ?? 0} 个小节（kp 共 {stat?.node_total ?? 0} 节点）
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic title="教材树 · 未铺的枝" value={stat?.unbuilt ?? 0} suffix="枝" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {stat && stat.unbuilt === 0
                ? '当前树上每一枝都铺过了（未铺=只有名字没目录）'
                : '空目录假装铺好了是事故，这里如实标'}
              {stat && stat.retired > 0 ? ` · 已退役 ${stat.retired} 片` : ''}
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic title="别名" value={alias?.total ?? 0} suffix="条" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              覆盖 {alias?.covered_kp ?? 0} 片叶 · {alias?.kind_stat.map((k) => `${k.kind}${k.count}`).join(' / ') ?? '—'}
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic
              title="挂载"
              value={stat?.mounted ?? 0}
              suffix={`/ ${stat?.leaf_total ?? 0} 片有题`}
              valueStyle={{ fontSize: 22 }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              零挂载 {stat?.zero ?? 0} 片 —— 维护时最该看的一屏
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 220px">
          <Card size="small">
            <Statistic
              title="词表坏账"
              value={(alias?.ambiguous.length ?? 0) + (alias?.broken_total ?? 0)}
              suffix="处"
              valueStyle={{ fontSize: 22, color: (alias?.ambiguous.length ?? 0) + (alias?.broken_total ?? 0) > 0 ? '#cf1322' : undefined }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              一词多挂 {alias?.ambiguous.length ?? 0}（resolve 会二义）· 别名断链 {alias?.broken_total ?? 0}
            </Typography.Text>
          </Card>
        </Col>
      </Row>

      {/* ② 左树右详情 */}
      <Row gutter={[12, 12]} wrap>
        <Col flex="0 1 360px" style={{ minWidth: 280 }}>
          <Card
            size="small"
            title="教材树"
            extra={
              selected ? (
                <Typography.Link onClick={() => setSelected('')} style={{ fontSize: 12 }}>
                  清除选中
                </Typography.Link>
              ) : null
            }
            styles={{ body: { padding: 0 } }}
          >
            <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
              <Checkbox checked={zeroOnly} onChange={(e) => setZeroOnly(e.target.checked)}>
                <span style={{ fontSize: 13 }}>只看零挂载考点</span>
              </Checkbox>
              <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '4px 0 0' }}>
                {zeroOnly
                  ? '只剩「有名字、没题」的叶子——维护时最该先看这一屏。'
                  : '灰字 = 这儿是空的（未铺的枝 / 零挂载的叶 / 已退役的叶）。'}
              </Typography.Paragraph>
            </div>
            <div style={{ maxHeight: 560, overflow: 'auto', padding: '8px 8px 12px' }}>
              {!tree ? (
                <Spin />
              ) : treeData.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有零挂载的考点叶" />
              ) : (
                <Tree
                  blockNode
                  showLine={{ showLeafIcon: false }}
                  treeData={treeData}
                  selectedKeys={selected ? [selected] : []}
                  expandedKeys={expanded}
                  onExpand={(keys) => setExpanded(keys)}
                  onSelect={(keys, info) => {
                    if (!info.selected) {
                      setSelected('')
                      return
                    }
                    const key = String(keys[0] ?? '')
                    setExpanded((prev) => Array.from(new Set([...prev, key])))
                    setSelected(key)
                  }}
                />
              )}
            </div>
          </Card>
        </Col>
        <Col flex="1 1 520px" style={{ minWidth: 0 }}>
          <KpDetail id={selected} detail={detail} loading={detailLoading} />
        </Col>
      </Row>

      {/* ③ 题型下落：讲义 173 个「题型N」并进考点的账（对齐-003），含 70 个待人工归位 */}
      <PatternFate data={patterns} err={patternErr} />

      {/* ④ 别名表：产线词 → 叶子的翻译层（老区 resolve 命中率 2%~29% 的解药） */}
      <Card
        size="small"
        style={{ marginTop: 12 }}
        title={`别名表 · kp_alias（${alias?.total ?? 0} 条，覆盖 ${alias?.covered_kp ?? 0} 片叶）`}
        extra={
          <Space size={8} wrap>
            <Segmented
              size="small"
              value={aliasKind}
              onChange={(v) => setAliasKind(String(v))}
              options={['全部', ...(alias?.kind_stat.map((k) => k.kind) ?? [])].map((k) => ({ label: k, value: k }))}
            />
            <Input.Search
              allowClear
              size="small"
              placeholder="搜别名 / 考点名"
              value={aliasKw}
              onChange={(e) => setAliasKw(e.target.value)}
              style={{ width: 200 }}
            />
          </Space>
        }
      >
        {/* 🔴 用户走查第二问「别名干啥的」——三句话定位，摆在表头上方，别让人对着一张词表猜用途 */}
        <div
          style={{
            background: '#fafafa',
            border: '1px solid #f0f0f0',
            borderRadius: 4,
            padding: '10px 12px',
            marginBottom: 10,
            fontSize: 13,
            lineHeight: 2,
          }}
        >
          <div>
            <Tag color="green" style={{ marginInlineEnd: 6 }}>
              正本
            </Tag>
            <b>KG 叶是唯一正本</b>——题、册、模型挂考点时<b>只存叶 id</b>，别名一个都不存。
            别名层塌了，挂载关系一条都不受影响。
          </div>
          <div>
            <Tag color="blue" style={{ marginInlineEnd: 6 }}>
              干什么用
            </Tag>
            <b>别名 = 外部叫法 → 唯一叶的「进门翻译」</b>：录入 resolve 与检索输入端把讲义原词、
            产线词翻成叶 id。按 <b>对齐-002</b> 口径只收<b>正向产线词</b>——
            <b>不为历史数据铸兼容名</b>（对不上现行叶的历史数据是弃或人工重标，不做特别兼容）。
          </div>
          <div>
            <Tag style={{ marginInlineEnd: 6 }}>本页用途</Tag>
            <b>查坏翻译</b>：一词两叶 = 坏账（resolve 必二义），现{' '}
            <b style={{ color: (alias?.ambiguous.length ?? 0) > 0 ? '#cf1322' : '#389e0d' }}>
              {alias?.ambiguous.length ?? 0}
            </b>
            {' '}处；别名断链（指向不存在的叶）现{' '}
            <b style={{ color: (alias?.broken_total ?? 0) > 0 ? '#cf1322' : '#389e0d' }}>
              {alias?.broken_total ?? 0}
            </b>
            {' '}处。加别名 / 并叶走 KG维护 skill，本页只读。
          </div>
        </div>

        {alias && alias.ambiguous.length > 0 ? (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 10 }}
            message={`一词多挂 ${alias.ambiguous.length} 处：${alias.ambiguous.map((a) => `${a.alias}（${a.kp_count} 片叶）`).join('、')}`}
            description="同一个别名指向两片以上叶子，resolve 时会二义——产线词翻到哪片全看运气。修法走 KG维护 skill 的并叶 / 改别名。"
          />
        ) : null}
        <Table<KbAliasRow>
          rowKey={(r) => `${r.kp_id}|${r.alias}`}
          size="small"
          columns={aliasCols}
          dataSource={aliasRows}
          pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          locale={{ emptyText: <Empty description="按当前筛选，没有别名" /> }}
        />
      </Card>

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：勾「只看零挂载考点」= 缺口清单（{stat?.zero ?? 0} 片叶还没题）；点任一片叶看
        <b>聚合落点</b>——别名、教研属性（重难点 / 频率 / 难度）、考法描述（对齐-003 后「这类题长什么样」就归这一列）、
        挂在它上面的考察模型与解题模型、直挂题样例，一屏看齐。点「在题库里看」带 ?kp= 落到题库真库页那一枝。
      </Typography.Paragraph>
    </PageFrame>
  )
}

export default KbKg
