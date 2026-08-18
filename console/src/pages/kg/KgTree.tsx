import { useEffect, useMemo, useState } from 'react'
import type { CSSProperties, Key } from 'react'
import { Button, Card, Checkbox, Empty, Tree, Typography } from 'antd'
import type { TreeDataNode } from 'antd'
import type { TreeNode } from '@/mock'
import { flattenTree, isStub } from '@/mock'
import type { MaintMap } from './maint'
import { labelOf, patchOf } from './maint'
import { COUNT_BY_KEY, ROOT, ancestorKeysOf, pruneTree } from './tree-view'

/**
 * 左栏：教材树的**维护视图**。
 * 归属：维护组「知识图谱」自用。
 *
 * 🔴 与题库页那棵树的分工：题库页用树**筛题**（选中就过滤右表），
 *   本页用树**看家底**——每片叶挂了几道题、哪片一道都没有、哪一枝根本没铺、
 *   哪片改过名 / 退了役。同一棵 kgTree，两种读法，别各造一棵。
 * 🔴 未铺的枝（isStub）标灰、不给展开箭头，如实告诉走查的人「这里是空的」；
 *   空目录假装铺好了是事故（页面组约定 §3）。
 */

/** 默认展开到单元层：版本、年级学期两层撑开，单元露头但不再往下铺 */
const DEFAULT_EXPANDED: string[] = flattenTree()
  .filter((n) => (n.kind === '版本' || n.kind === '年级学期') && (n.children?.length ?? 0) > 0)
  .map((n) => n.key)

/** 小字后缀的统一样式（题数 / 别名 / 未铺 都用它，免得一行里三种字号） */
const SUFFIX: CSSProperties = { marginLeft: 6, fontSize: 12, color: 'rgba(0,0,0,0.45)', fontWeight: 400 }

function NodeTitle({ node, maint }: { node: TreeNode; maint: MaintMap }) {
  const stub = isStub(node)
  const leaf = node.kind === '考点'
  const count = COUNT_BY_KEY[node.key] ?? 0
  const patch = patchOf(maint, node.key)
  const name = labelOf(node, maint)
  // 零挂载叶与未铺枝都标灰：前者是「有名字没题」，后者是「有名字没目录」，都属于「这儿是空的」
  const dim = stub || (leaf && count === 0) || patch.retired === true

  return (
    <span
      title={
        stub
          ? '这一枝还没铺：教材树上只有个名字，底下的单元/小节/考点都没建'
          : leaf && count === 0
            ? '零挂载：这片考点叶目前一道题都没挂'
            : name
      }
      style={{ color: dim ? 'rgba(0,0,0,0.38)' : undefined, whiteSpace: 'nowrap' }}
    >
      {name}
      {count > 0 ? <span style={SUFFIX}>{count} 题</span> : null}
      {patch.aliases.length > 0 ? <span style={SUFFIX}>别名 {patch.aliases.length}</span> : null}
      {patch.renamedTo !== undefined ? <span style={SUFFIX}>已改名</span> : null}
      {patch.retired ? <span style={SUFFIX}>已退役</span> : null}
      {stub ? <span style={SUFFIX}>未铺</span> : null}
    </span>
  )
}

function toTreeData(nodes: TreeNode[], maint: MaintMap): TreeDataNode[] {
  return nodes.map((n) => ({
    key: n.key,
    title: <NodeTitle node={n} maint={maint} />,
    // children 缺省 = 考点叶或未铺的空壳，antd 自动不给展开箭头
    children: n.children ? toTreeData(n.children, maint) : undefined,
  }))
}

export function KgTree({
  selectedKey,
  onSelectKey,
  maint,
  zeroOnly,
  onZeroOnlyChange,
}: {
  /** 当前选中的树 key（'' = 没选） */
  selectedKey: string
  /** 选中变更（传 '' = 清除选中） */
  onSelectKey: (key: string) => void
  maint: MaintMap
  /** 只看零挂载考点（维护时最常用的一眼） */
  zeroOnly: boolean
  onZeroOnlyChange: (v: boolean) => void
}) {
  const [expanded, setExpanded] = useState<Key[]>(() =>
    Array.from(new Set([...DEFAULT_EXPANDED, ...(selectedKey ? ancestorKeysOf(selectedKey) : [])])),
  )

  /** 只看零挂载时把树裁一遍：只留走得到零挂载叶的枝（未铺的空壳枝自然被裁掉） */
  const shown = useMemo(
    () => (zeroOnly ? pruneTree(ROOT, (leaf) => (COUNT_BY_KEY[leaf.key] ?? 0) === 0) : ROOT),
    [zeroOnly],
  )

  const treeData = useMemo(() => toTreeData(shown, maint), [shown, maint])

  /**
   * 🔴 选中项是从**外面**来的（/model、/cause、/questions/:id 带 ?kp= 跳进来，见 kg/trace.ts），
   *   所以 selectedKey 变了必须把祖先撑开——否则叶子藏在收起的枝里，
   *   人跳过来只看到右边详情变了、左树没反应，会以为链接跳错了。
   */
  useEffect(() => {
    if (!selectedKey) return
    setExpanded((prev) => Array.from(new Set([...prev, ...ancestorKeysOf(selectedKey)])))
  }, [selectedKey])

  /** 裁过的树很窄，全展开才看得见叶子；关掉筛选回到默认展开 */
  useEffect(() => {
    setExpanded((prev) =>
      zeroOnly
        ? flattenTree(shown)
            .filter((n) => (n.children?.length ?? 0) > 0)
            .map((n) => n.key)
        : Array.from(new Set([...DEFAULT_EXPANDED, ...prev.map(String)])),
    )
  }, [zeroOnly, shown])

  return (
    <Card
      size="small"
      title="教材树"
      extra={
        selectedKey ? (
          <Button type="link" size="small" style={{ padding: 0, height: 'auto' }} onClick={() => onSelectKey('')}>
            清除选中
          </Button>
        ) : null
      }
      styles={{ body: { padding: 0 } }}
    >
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
        <Checkbox checked={zeroOnly} onChange={(e) => onZeroOnlyChange(e.target.checked)}>
          <span style={{ fontSize: 13 }}>只看零挂载考点</span>
        </Checkbox>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '4px 0 0' }}>
          {zeroOnly
            ? '只剩「有名字、没题」的叶子——维护时最该先看这一屏。'
            : '灰字 = 这儿是空的（未铺的枝 / 零挂载的叶 / 已退役的叶）。'}
        </Typography.Paragraph>
      </div>

      <div style={{ maxHeight: 560, overflow: 'auto', padding: '8px 8px 12px' }}>
        {treeData.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有零挂载的考点叶" />
        ) : (
          <Tree
            blockNode
            showLine={{ showLeafIcon: false }}
            treeData={treeData}
            selectedKeys={selectedKey ? [selectedKey] : []}
            expandedKeys={expanded}
            onExpand={(keys) => setExpanded(keys)}
            onSelect={(keys, info) => {
              // 再点一次已选中的节点 = 取消选中
              if (!info.selected) {
                onSelectKey('')
                return
              }
              const key = String(keys[0] ?? '')
              setExpanded((prev) => Array.from(new Set([...prev, key, ...ancestorKeysOf(key)])))
              onSelectKey(key)
            }}
          />
        )}
      </div>
    </Card>
  )
}

export default KgTree
