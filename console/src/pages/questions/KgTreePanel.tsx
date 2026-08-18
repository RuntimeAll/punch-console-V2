import { useMemo, useState } from 'react'
import type { Key } from 'react'
import { Button, Card, Tree, Typography } from 'antd'
import type { TreeDataNode } from 'antd'
import type { TreeNode } from '@/mock'
import { flattenTree, isStub, kgTree, labelPathMap, questionsUnderPath } from '@/mock'
import { crossAxisKp, keyOfLabelPath } from './helpers'

/**
 * 题库页左栏：教材树目录（版本 → 年级学期 → 单元 → 小节 → 考点）。
 * 归属：页面组「题库」自用。**只读**——建叶子 / 改归属这类写动作在 agent 侧。
 *
 * 口径（页面组约定 §1、§3）：
 * - 点任意层级 = 按 treePath **前缀**过滤右表；点已选中的节点再点一次 = 取消选中。
 * - 🔴 树控件回调只给 key，label 路径一律走 labelPathMap()[key] 换算，
 *   绝不按 key 切字符串反推（单元名带空格，切出来必错）。
 * - 🔴 未铺的枝（isStub）标灰 + 不给展开箭头，如实告诉走查的人「这里是空的」，
 *   空目录假装铺好了是事故。
 */

/** 默认展开到**单元层**：把版本、年级学期两层撑开，单元露头但不再往下铺 */
const DEFAULT_EXPANDED: string[] = flattenTree()
  .filter((n) => (n.kind === '版本' || n.kind === '年级学期') && (n.children?.length ?? 0) > 0)
  .map((n) => n.key)

/** 每个节点底下挂了多少道题（前缀口径，建一次） */
const COUNT_BY_KEY: Record<string, number> = Object.fromEntries(
  Object.entries(labelPathMap()).map(([key, path]) => [key, questionsUnderPath(path).length]),
)

/** 某个 key 的全部祖先 key（选中时要把上级撑开，否则选中项藏在收起的枝里看不见） */
function ancestorKeysOf(key: string): string[] {
  const path = labelPathMap()[key]
  if (!path) return []
  return path.slice(0, -1).map((_, i) => keyOfLabelPath(path.slice(0, i + 1)))
    .filter((k): k is string => Boolean(k))
}

/** 节点标题：未铺标灰，挂了题的在名字后面缀一个题数（0 不显示，免得满屏都是 0） */
function NodeTitle({ node }: { node: TreeNode }) {
  const stub = isStub(node)
  const count = COUNT_BY_KEY[node.key] ?? 0
  return (
    <span
      title={stub ? '这一枝还没铺：教材树上只有个名字，底下的单元/小节/考点都没建' : node.label}
      style={{ color: stub ? 'rgba(0,0,0,0.35)' : undefined, whiteSpace: 'nowrap' }}
    >
      {node.label}
      {count > 0 ? (
        <span style={{ marginLeft: 6, fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{count}</span>
      ) : null}
    </span>
  )
}

function toTreeData(nodes: TreeNode[]): TreeDataNode[] {
  return nodes.map((n) => ({
    key: n.key,
    title: <NodeTitle node={n} />,
    // children 缺省 = 叶子（考点）或未铺的空壳，antd 自动不给展开箭头
    children: n.children ? toTreeData(n.children) : undefined,
  }))
}

const TREE_DATA = toTreeData(kgTree)

export function KgTreePanel({
  selectedKey,
  onSelectKey,
  onSwitchToKpTag,
}: {
  /** 当前选中的树 key（'' = 没选，右表不按树筛） */
  selectedKey: string
  /** 选中变更（传 '' = 清除选中） */
  onSelectKey: (key: string) => void
  /** 「改按考点标签筛」：清掉树选中、改用考点下拉（口径切换，见下方说明） */
  onSwitchToKpTag: (kpName: string) => void
}) {
  // 初始展开 = 默认到单元层 + 当前选中项的祖先（从详情页带 ?tree= 进来时要能看见选中的那片叶子）
  const [expanded, setExpanded] = useState<Key[]>(() =>
    Array.from(new Set([...DEFAULT_EXPANDED, ...(selectedKey ? ancestorKeysOf(selectedKey) : [])])),
  )

  const path = useMemo(() => (selectedKey ? (labelPathMap()[selectedKey] ?? []) : []), [selectedKey])

  /**
   * 「同一个考点，两条轴对不上」的提示（口径正本在 helpers.crossAxisKp）。
   * 🔴 treePath 管归属、kps 管能力标签（页面组约定 §1），两者不是一回事：
   * 「角度计算问题」这片叶子归属下一道题都没有，却有 5 道题把它当**副考点**——
   * 树筛不到它们，考点下拉能筛到。差额出现时才提示，相等时不啰嗦
   *（mock 里有 4 片叶子会触发这条提示，走查随便点一片就能看到）。
   */
  const crossAxis = useMemo(() => (selectedKey ? crossAxisKp(selectedKey) : undefined), [selectedKey])

  return (
    <Card size="small" title="教材树" styles={{ body: { padding: 0 } }}>
      {/* ① 面包屑：当前选中的整条路径 + 清除 */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12, flex: '1 1 auto', minWidth: 0 }}>
            {path.length > 0 ? path.join(' / ') : '未选中：右表显示全部题目'}
          </Typography.Text>
          {selectedKey ? (
            <Button type="link" size="small" style={{ padding: 0, height: 'auto' }} onClick={() => onSelectKey('')}>
              清除
            </Button>
          ) : null}
        </div>

        {crossAxis ? (
          <div style={{ marginTop: 6 }}>
            <Button
              type="link"
              size="small"
              style={{ padding: 0, height: 'auto', fontSize: 12, whiteSpace: 'normal', textAlign: 'left' }}
              onClick={() => onSwitchToKpTag(crossAxis.name)}
            >
              改按考点标签筛（跨枝 {crossAxis.byTag} 道）
            </Button>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 0' }}>
              树按<b>归属</b>筛（题长在哪根枝上），考点下拉按<b>能力标签</b>筛（这题考什么，可跨枝）。
            </Typography.Paragraph>
          </div>
        ) : null}
      </div>

      {/* ② 树本体：窄栏放不下长单元名，容器自己横向滚，别让整页跟着横滚 */}
      <div style={{ maxHeight: 520, overflow: 'auto', padding: '8px 8px 12px' }}>
        {/*
          不用 blockNode：单元名比 270px 宽，节点标题一律 nowrap 让容器横向滚，
          此时 blockNode 的整行底色只铺到可视宽度，选中态会被截得像渲染坏了。
        */}
        <Tree
          showLine={{ showLeafIcon: false }}
          treeData={TREE_DATA}
          selectedKeys={selectedKey ? [selectedKey] : []}
          expandedKeys={expanded}
          onExpand={(keys) => setExpanded(keys)}
          onSelect={(keys, info) => {
            // 再点一次已选中的节点 = 取消选中（等价于「清除」）
            if (!info.selected) {
              onSelectKey('')
              return
            }
            const key = String(keys[0] ?? '')
            // 选中即把这一枝连同上级撑开；只加不减，用户手动收起的枝不会被抢回去
            setExpanded((prev) => Array.from(new Set([...prev, key, ...ancestorKeysOf(key)])))
            onSelectKey(key)
          }}
        />
      </div>
    </Card>
  )
}

export default KgTreePanel
