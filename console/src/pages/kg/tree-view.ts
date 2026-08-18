import type { TreeNode } from '@/mock'
import { flattenTree, isStub, kgTree, labelPathMap, questionsUnderPath } from '@/mock'

/**
 * 知识图谱组内的纯函数 / 静态派生表（不含 JSX —— 与组件分文件是为了 Vite Fast Refresh）。
 * 归属：维护组「知识图谱」**自用**，其它页面组别 import。
 *
 * 🔴 树是静态 mock，本文件的派生表**建一次就够**（模块顶层算完缓存），
 *   别在 render 里反复 flattenTree()——58 片叶 × 每次重渲是白烧。
 * 🔴 与同目录 trace.ts 的分工：本文件管**树自己的形状**（谁是谁的儿子、哪枝空、挂几道题），
 *   trace.ts 管**跨域溯源**（考点名 ↔ 树 key、一片叶挂着的题/模型/错因/沉淀），
 *   而且 trace.ts 是允许被 /model /cause /questions/:id 单向 import 的那一份。别把两边的活揉一起。
 */

/** key → 节点（选中后查 kind / children 用） */
export const NODE_BY_KEY: Record<string, TreeNode> = Object.fromEntries(flattenTree().map((n) => [n.key, n]))

/**
 * key → 从根到该节点的 label 路径。
 * 🔴 页面组约定 §1：树控件回调只给 key，label 路径一律查这张表，
 *   绝不按 key 切字符串反推（单元名里带空格，切出来必错）。
 */
export const PATH_BY_KEY: Record<string, string[]> = labelPathMap()

/** JSON(label 路径) → key，PATH_BY_KEY 的逆表（用 JSON 串当键：label 自带空格括号，拿分隔符拼键早晚撞车） */
const KEY_BY_PATH: Record<string, string> = Object.fromEntries(
  Object.entries(PATH_BY_KEY).map(([key, path]) => [JSON.stringify(path), key]),
)

/** label 路径 → 树 key；树上没有这条路径返回 undefined */
export function keyOfPath(path: string[]): string | undefined {
  return KEY_BY_PATH[JSON.stringify(path)]
}

/** 某个 key 的全部祖先 key（选中时要把上级撑开，否则选中项藏在收起的枝里看不见） */
export function ancestorKeysOf(key: string): string[] {
  const path = PATH_BY_KEY[key]
  if (!path) return []
  return path
    .slice(0, -1)
    .map((_, i) => keyOfPath(path.slice(0, i + 1)))
    .filter((k): k is string => Boolean(k))
}

/** key → 这一枝下挂了多少道题（前缀口径：选单元就是整个单元的题数） */
export const COUNT_BY_KEY: Record<string, number> = Object.fromEntries(
  Object.entries(PATH_BY_KEY).map(([key, path]) => [key, questionsUnderPath(path).length]),
)

/** 家底盘点：各层级各有多少个、有几枝是空壳 */
export const TREE_STATS = (() => {
  const all = flattenTree()
  const by = (kind: TreeNode['kind']) => all.filter((n) => n.kind === kind).length
  return {
    版本: by('版本'),
    年级学期: by('年级学期'),
    单元: by('单元'),
    小节: by('小节'),
    考点: by('考点'),
    /** 未铺 = isStub 为真的枝（有名字、底下什么都没建） */
    未铺: all.filter((n) => isStub(n)).length,
  }
})()

/** 全部考点叶 */
export const LEAVES: TreeNode[] = flattenTree().filter((n) => n.kind === '考点')

/**
 * 🔴 零挂载叶 = 树上有、但一道题都没挂的考点。
 * 这是维护视图里最该看的东西：目录铺了 58 片叶，真有题的只有几片，
 * 缺口在哪一眼就该看见（不是「数据没录完」，是「这些地方还没题」）。
 */
export const ZERO_MOUNT_KEYS: string[] = LEAVES.filter((n) => (COUNT_BY_KEY[n.key] ?? 0) === 0).map((n) => n.key)

/** 已挂题的叶子数（挂载卡的分子） */
export const MOUNTED_LEAF_COUNT = LEAVES.length - ZERO_MOUNT_KEYS.length

/**
 * 按「留哪些叶子」裁剪树：只保留能走到留存叶的枝。
 * 🔴 未铺的空壳枝一律裁掉（它底下没有叶子，留着只会让人以为那儿有货）。
 */
export function pruneTree(nodes: TreeNode[], keepLeaf: (leaf: TreeNode) => boolean): TreeNode[] {
  const out: TreeNode[] = []
  for (const n of nodes) {
    if (n.kind === '考点') {
      if (keepLeaf(n)) out.push(n)
      continue
    }
    const kids = pruneTree(n.children ?? [], keepLeaf)
    if (kids.length > 0) out.push({ ...n, children: kids })
  }
  return out
}

/** 某个枝底下的全部后代（枝概览用；传考点叶返回空数组） */
export function descendantsOf(node: TreeNode): TreeNode[] {
  return flattenTree(node.children ?? [])
}

/** 树的根（组件里直接用，省得各处 import kgTree） */
export const ROOT: TreeNode[] = kgTree
