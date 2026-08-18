import type { TreeNode } from './types'

/**
 * mock 教材树（题库多级目录 + 知识图谱页共用同一棵树）。
 *
 * 🔴 层级固定五段：版本 → 年级学期 → 单元 → 小节 → 考点。
 * 只有「人教版 / 四年级上册」这一枝是**铺满的**（8 个单元，每单元 2~4 个小节，
 * 小节下挂考点叶）；「四年级下册」「北师大版」故意留成空壳（label 带「未铺」、无 children），
 * 用来走查页面在「这一枝还没铺」的情况下长什么样——空目录假装铺好了是事故。
 *
 * 🔴 kpVocabulary 里那 9 个考点词**全部**能在本树上找到叶子（题库页的考点筛选与
 * 教材树筛选必须指向同一批题）：
 *   梯形的拼接问题 / 三角形的内角和问题 / 多边形的内角和问题 / 角度计算问题 /
 *   四则混合运算的运算顺序 / 乘法结合律的应用 / 三位数乘两位数的计算 /
 *   三位数除以两位数的计算 / 除法估算问题
 * 其中「内角和」「运算顺序与运算律」两组严格说是四下/衔接内容，教辅树上按惯例
 * 挂在四上对应单元里并在小节名上标（拓展）/（衔接），别当成录错了。
 */

/** 造考点叶的小工具（考点一律是叶子，不许有 children） */
function kp(key: string, label: string): TreeNode {
  return { key, label, kind: '考点' }
}

/** 造小节 */
function sec(key: string, label: string, children: TreeNode[]): TreeNode {
  return { key, label, kind: '小节', children }
}

/** 造单元 */
function unit(key: string, label: string, children: TreeNode[]): TreeNode {
  return { key, label, kind: '单元', children }
}

/** 人教版 · 四年级上册 —— 唯一铺满的一枝 */
const 人教四上: TreeNode = {
  key: 'renjiao/g4a',
  label: '四年级上册',
  kind: '年级学期',
  children: [
    unit('renjiao/g4a/u1', '第一单元 大数的认识', [
      sec('renjiao/g4a/u1/s1', '亿以内数的认识', [
        kp('renjiao/g4a/u1/s1/k1', '数位顺序表与计数单位'),
        kp('renjiao/g4a/u1/s1/k2', '亿以内数的读法'),
        kp('renjiao/g4a/u1/s1/k3', '亿以内数的写法'),
      ]),
      sec('renjiao/g4a/u1/s2', '数的大小比较与改写', [
        kp('renjiao/g4a/u1/s2/k1', '亿以内数的大小比较'),
        kp('renjiao/g4a/u1/s2/k2', '用「万」作单位改写'),
        kp('renjiao/g4a/u1/s2/k3', '求近似数（四舍五入）'),
      ]),
      sec('renjiao/g4a/u1/s3', '亿以上数的认识', [
        kp('renjiao/g4a/u1/s3/k1', '亿以上数的读写'),
        kp('renjiao/g4a/u1/s3/k2', '用「亿」作单位改写'),
      ]),
      sec('renjiao/g4a/u1/s4', '计算工具的认识', [
        kp('renjiao/g4a/u1/s4/k1', '用计算器计算'),
        kp('renjiao/g4a/u1/s4/k2', '用计算器探索规律'),
      ]),
    ]),

    unit('renjiao/g4a/u2', '第二单元 公顷和平方千米', [
      sec('renjiao/g4a/u2/s1', '公顷的认识', [
        kp('renjiao/g4a/u2/s1/k1', '公顷与平方米的换算'),
        kp('renjiao/g4a/u2/s1/k2', '公顷的实际应用'),
      ]),
      sec('renjiao/g4a/u2/s2', '平方千米的认识', [
        kp('renjiao/g4a/u2/s2/k1', '平方千米与公顷的换算'),
        kp('renjiao/g4a/u2/s2/k2', '土地面积单位的选择'),
      ]),
    ]),

    unit('renjiao/g4a/u3', '第三单元 角的度量', [
      sec('renjiao/g4a/u3/s1', '线段·直线·射线', [
        kp('renjiao/g4a/u3/s1/k1', '线段直线射线的区别'),
        kp('renjiao/g4a/u3/s1/k2', '过点画直线的条数'),
      ]),
      sec('renjiao/g4a/u3/s2', '角的度量与画角', [
        kp('renjiao/g4a/u3/s2/k1', '用量角器量角'),
        kp('renjiao/g4a/u3/s2/k2', '画指定度数的角'),
      ]),
      sec('renjiao/g4a/u3/s3', '角的分类与计算', [
        kp('renjiao/g4a/u3/s3/k1', '角的分类（锐角直角钝角平角周角）'),
        kp('renjiao/g4a/u3/s3/k2', '角度计算问题'),
        kp('renjiao/g4a/u3/s3/k3', '用三角尺拼角'),
      ]),
      // （拓展）= 严格说属四下/思维拓展，教辅树按惯例挂在本单元
      sec('renjiao/g4a/u3/s4', '内角和（拓展）', [
        kp('renjiao/g4a/u3/s4/k1', '三角形的内角和问题'),
        kp('renjiao/g4a/u3/s4/k2', '多边形的内角和问题'),
      ]),
    ]),

    unit('renjiao/g4a/u4', '第四单元 三位数乘两位数', [
      sec('renjiao/g4a/u4/s1', '口算乘法', [
        kp('renjiao/g4a/u4/s1/k1', '整十数乘整十数的口算'),
        kp('renjiao/g4a/u4/s1/k2', '因数末尾有 0 的口算'),
      ]),
      sec('renjiao/g4a/u4/s2', '笔算乘法', [
        kp('renjiao/g4a/u4/s2/k1', '三位数乘两位数的计算'),
        kp('renjiao/g4a/u4/s2/k2', '因数中间或末尾有 0 的笔算'),
      ]),
      sec('renjiao/g4a/u4/s3', '积的变化规律', [
        kp('renjiao/g4a/u4/s3/k1', '积的变化规律'),
        kp('renjiao/g4a/u4/s3/k2', '单价数量总价'),
        kp('renjiao/g4a/u4/s3/k3', '速度时间路程'),
      ]),
      // （衔接）= 运算律与混合运算，四上教辅普遍提前铺
      sec('renjiao/g4a/u4/s4', '运算顺序与运算律（衔接）', [
        kp('renjiao/g4a/u4/s4/k1', '四则混合运算的运算顺序'),
        kp('renjiao/g4a/u4/s4/k2', '乘法结合律的应用'),
        kp('renjiao/g4a/u4/s4/k3', '乘法分配律的应用'),
      ]),
    ]),

    unit('renjiao/g4a/u5', '第五单元 平行四边形和梯形', [
      sec('renjiao/g4a/u5/s1', '平行与垂直', [
        kp('renjiao/g4a/u5/s1/k1', '平行与垂直的判断'),
        kp('renjiao/g4a/u5/s1/k2', '点到直线的距离'),
      ]),
      sec('renjiao/g4a/u5/s2', '画垂线与平行线', [
        kp('renjiao/g4a/u5/s2/k1', '过一点画垂线'),
        kp('renjiao/g4a/u5/s2/k2', '用直尺三角尺画平行线'),
      ]),
      sec('renjiao/g4a/u5/s3', '平行四边形', [
        kp('renjiao/g4a/u5/s3/k1', '平行四边形的特征与底高'),
        kp('renjiao/g4a/u5/s3/k2', '平行四边形的不稳定性'),
      ]),
      sec('renjiao/g4a/u5/s4', '梯形', [
        kp('renjiao/g4a/u5/s4/k1', '梯形的特征与分类'),
        kp('renjiao/g4a/u5/s4/k2', '梯形的拼接问题'),
        kp('renjiao/g4a/u5/s4/k3', '四边形之间的关系'),
      ]),
    ]),

    unit('renjiao/g4a/u6', '第六单元 除数是两位数的除法', [
      sec('renjiao/g4a/u6/s1', '口算除法与估算', [
        kp('renjiao/g4a/u6/s1/k1', '整十数除整十数的口算'),
        kp('renjiao/g4a/u6/s1/k2', '除法估算问题'),
      ]),
      sec('renjiao/g4a/u6/s2', '笔算除法（除数是整十数）', [
        kp('renjiao/g4a/u6/s2/k1', '除数是整十数的笔算'),
        kp('renjiao/g4a/u6/s2/k2', '商是一位数的试商'),
      ]),
      sec('renjiao/g4a/u6/s3', '笔算除法（三位数除以两位数）', [
        kp('renjiao/g4a/u6/s3/k1', '三位数除以两位数的计算'),
        kp('renjiao/g4a/u6/s3/k2', '四舍五入试商'),
        kp('renjiao/g4a/u6/s3/k3', '商是两位数的除法'),
      ]),
      sec('renjiao/g4a/u6/s4', '商的变化规律', [
        kp('renjiao/g4a/u6/s4/k1', '商的变化规律'),
        kp('renjiao/g4a/u6/s4/k2', '被除数与除数同时扩大缩小'),
      ]),
    ]),

    unit('renjiao/g4a/u7', '第七单元 条形统计图', [
      sec('renjiao/g4a/u7/s1', '认识条形统计图', [
        kp('renjiao/g4a/u7/s1/k1', '1 格表示 1 个单位的条形统计图'),
        kp('renjiao/g4a/u7/s1/k2', '从统计图中读取信息'),
      ]),
      sec('renjiao/g4a/u7/s2', '一格表示多个单位', [
        kp('renjiao/g4a/u7/s2/k1', '1 格表示 2 / 5 个单位的条形统计图'),
        kp('renjiao/g4a/u7/s2/k2', '根据数据绘制条形统计图'),
      ]),
    ]),

    unit('renjiao/g4a/u8', '第八单元 数学广角·优化', [
      sec('renjiao/g4a/u8/s1', '沏茶问题（合理安排时间）', [
        kp('renjiao/g4a/u8/s1/k1', '工序优化与最短时间'),
      ]),
      sec('renjiao/g4a/u8/s2', '烙饼问题', [
        kp('renjiao/g4a/u8/s2/k1', '烙饼问题的最优方案'),
      ]),
      sec('renjiao/g4a/u8/s3', '田忌赛马（对策问题）', [
        kp('renjiao/g4a/u8/s3/k1', '对策问题的最优策略'),
      ]),
    ]),
  ],
}

/** 🔴 教材树正本。页面只读，不许在页面里就地拼树。 */
export const kgTree: TreeNode[] = [
  {
    key: 'renjiao',
    label: '人教版',
    kind: '版本',
    children: [
      人教四上,
      // 空壳：这一枝还没铺，页面要如实标出来
      { key: 'renjiao/g4b', label: '四年级下册（未铺）', kind: '年级学期' },
    ],
  },
  { key: 'beishida', label: '北师大版（未铺）', kind: '版本' },
]

/** 深度优先拉平整棵树（页面做搜索 / 统计用） */
export function flattenTree(nodes: TreeNode[] = kgTree): TreeNode[] {
  return nodes.flatMap((n) => [n, ...flattenTree(n.children ?? [])])
}

/** 全部考点叶的名字（顺序 = 树上的先后顺序） */
export function kpLeaves(): string[] {
  return flattenTree().filter((n) => n.kind === '考点').map((n) => n.label)
}

/** 按 label 路径找节点，如 ['人教版','四年级上册','第五单元 平行四边形和梯形']；找不到返回 undefined */
export function findTreeNode(path: string[]): TreeNode | undefined {
  let level = kgTree
  let hit: TreeNode | undefined
  for (const label of path) {
    hit = level.find((n) => n.label === label)
    if (!hit) return undefined
    level = hit.children ?? []
  }
  return hit
}

/** 一条 treePath 转面包屑文本（详情页 / 表格里显示归属用） */
export function treePathText(path?: string[], sep = ' / '): string {
  return path && path.length > 0 ? path.join(sep) : '—'
}

/** 这枝铺了没：没有 children = 未铺（页面据此标灰、不给点开） */
export function isStub(node: TreeNode): boolean {
  return node.kind !== '考点' && (node.children === undefined || node.children.length === 0)
}

/**
 * key → 从根到该节点的 **label 路径**。
 * 🔴 树控件的选中回调只给 key，而 Question.treePath 存的是 label；
 * 点树筛题的标准姿势 = `questionsUnderPath(labelPathMap()[selectedKey])`，
 * 页面别自己按 key 切字符串反推路径（单元名里带空格，切出来必错）。
 */
export function labelPathMap(nodes: TreeNode[] = kgTree, prefix: string[] = []): Record<string, string[]> {
  const acc: Record<string, string[]> = {}
  for (const n of nodes) {
    const path = [...prefix, n.label]
    acc[n.key] = path
    Object.assign(acc, labelPathMap(n.children ?? [], path))
  }
  return acc
}

// ═══════════════════════════════════════════════════════════════
// 🔴 考点 id ↔ 名字（第四轮加：题目的 kps 存 kpId 不存名字）
// ═══════════════════════════════════════════════════════════════

/**
 * 🔴 表外考点（本原型的临时口径，不是设计缺口）。
 *
 * 教材树目前只**铺满了人教四上**一枝，而批改线跑的是七上（有理数混合运算 / 绝对值 / 整式），
 * 那几片叶子还没铺进树。为了让「错因码翻译（err_code_map）」「解题模型」这些
 * **按考点作用域**的东西有真 id 可挂，先在这里登记为表外叶。
 *
 * 纪律：
 * - id 的写法与树上一致（`版本/年级学期/单元/小节/考点`），将来铺树时**原地转正**、id 不变；
 * - 只能登记**叶子**（叶子闸不因为它在表外就放松）；
 * - 页面把它们当普通考点显示即可，别做特判。
 */
export const OFF_TREE_KPS: Record<string, string> = {
  'renjiao/g7a/u1/s4/k1': '有理数混合运算的运算顺序',
  'renjiao/g7a/u1/s2/k2': '含字母的绝对值化简',
  'renjiao/g7a/u2/s2/k1': '整式的加减·去括号合并同类项',
  'renjiao/g7a/u1/s3/k1': '有理数的乘方与底数判断',
}

/** 树上全部考点叶：id → 名（懒建一次，树是静态 mock） */
let kpNameCache: Record<string, string> | undefined

function kpNameTable(): Record<string, string> {
  if (!kpNameCache) {
    const acc: Record<string, string> = { ...OFF_TREE_KPS }
    for (const n of flattenTree()) if (n.kind === '考点') acc[n.key] = n.label
    kpNameCache = acc
  }
  return kpNameCache
}

/**
 * 考点 id → 名字。
 * 🔴 查不到不返回空串：如实吐 `未知考点(<id>)`，让脏 id 在页面上看得见（静默吞掉最难查）。
 */
export function kpNameOf(kpId: string): string {
  return kpNameTable()[kpId] ?? `未知考点(${kpId})`
}

/** 考点名 → id（同名叶取先出现的那片；找不到返回 undefined） */
export function kpIdOf(name: string): string | undefined {
  return Object.keys(kpNameTable()).find((id) => kpNameTable()[id] === name)
}

/** 这个 id 在教材树上真有对应叶子吗（表外考点返回 false —— 它还没铺进树） */
export function isOnTreeKp(kpId: string): boolean {
  return flattenTree().some((n) => n.kind === '考点' && n.key === kpId)
}
