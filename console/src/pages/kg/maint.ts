import type { TreeNode } from '@/mock'

/**
 * 考点叶的**维护态**（别名 / 改名 / 退役）—— 页面本地 state，刷新即还原。
 * 归属：维护组「知识图谱」自用。
 *
 * 🔴 为什么别名不在 mock/types.ts 里：TreeNode 是**目录结构**的形状，
 *   别名是**词表运维**的东西（同一片叶子在不同教辅里叫什么），两层生命周期不同。
 *   等这套维护动作在评审里定下来了，再由地基工提到 types.ts 立正本，
 *   现在先在页面里长着——原型阶段不给数据层挖坑。
 *
 * 🔴 更要紧的边界：这里的「加别名 / 改名 / 退役」是**原型演示态**，只改本页临时 state、
 *   不落库、不回填题目。真改一片叶子的名字要连带回写挂在它下面的每道题的 treePath，
 *   那是 agent 侧的事务动作，页面不承担（页面组约定 §8）。
 */

/** 一片考点叶的本地维护补丁 */
export type LeafPatch = {
  /** 别名（这片叶子在别的教辅/口头里的叫法） */
  aliases: string[]
  /** 改过名就有值；渲染时以它为准，原 label 作为「原名」留痕 */
  renamedTo?: string
  /** 退役 = 不再往这片叶子上挂新题（已挂的题不动，等 agent 迁走） */
  retired?: boolean
}

export type MaintMap = Record<string, LeafPatch>

/**
 * 别名种子：给几片有代表性的叶子先铺上别名，走查时能看到「有别名 / 没别名」两种态。
 * 🔴 键必须是 kg-tree.ts 上真实存在的考点叶 key（编一个树上没有的 key = 这张表白写）。
 */
export const ALIAS_SEED: Record<string, string[]> = {
  // 第五单元 · 梯形
  'renjiao/g4a/u5/s4/k2': ['梯形拼图', '两个梯形拼平行四边形'],
  // 第四单元 · 笔算乘法
  'renjiao/g4a/u4/s2/k1': ['三位数×两位数笔算', '多位数乘法竖式'],
  // 第四单元 · 运算顺序与运算律（衔接）
  'renjiao/g4a/u4/s4/k1': ['四则运算顺序', '先乘除后加减'],
  // 第三单元 · 内角和（拓展）
  'renjiao/g4a/u3/s4/k1': ['三角形内角和 180°'],
  // 第三单元 · 角的分类与计算
  'renjiao/g4a/u3/s3/k2': ['求角的度数', '钟面夹角'],
  // 第一单元 · 数的大小比较与改写
  'renjiao/g4a/u1/s2/k3': ['四舍五入取近似数', '省略尾数求近似数'],
  // 第六单元 · 口算除法与估算
  'renjiao/g4a/u6/s1/k2': ['除法估算'],
  // 第六单元 · 笔算除法（三位数除以两位数）
  'renjiao/g4a/u6/s3/k1': ['三位数÷两位数笔算'],
}

/** 初始维护态 = 只有种子别名，没人改名、没人退役 */
export function initialMaint(): MaintMap {
  const acc: MaintMap = {}
  for (const [key, aliases] of Object.entries(ALIAS_SEED)) acc[key] = { aliases: [...aliases] }
  return acc
}

/** 取某片叶子的补丁（没动过就返回空补丁，调用方不用到处判空） */
export function patchOf(maint: MaintMap, key: string): LeafPatch {
  return maint[key] ?? { aliases: [] }
}

/** 叶子的**现名**：改过名就用改后的，否则用树上的原名 */
export function labelOf(node: TreeNode, maint: MaintMap): string {
  return patchOf(maint, node.key).renamedTo ?? node.label
}

/** 别名总账：多少条别名、覆盖了多少片叶子（统计卡用） */
export function aliasTotals(maint: MaintMap): { 条数: number; 覆盖叶子: number } {
  const rows = Object.values(maint).filter((p) => p.aliases.length > 0)
  return {
    条数: rows.reduce((n, p) => n + p.aliases.length, 0),
    覆盖叶子: rows.length,
  }
}

/** 本页动过手的叶子（改过名 / 退役 / 别名与种子不一致），用来提示「本页临时改动 N 处」 */
export function dirtyKeys(maint: MaintMap): string[] {
  return Object.entries(maint)
    .filter(([key, p]) => {
      if (p.renamedTo !== undefined || p.retired === true) return true
      const seed = ALIAS_SEED[key] ?? []
      return p.aliases.length !== seed.length || p.aliases.some((a, i) => a !== seed[i])
    })
    .map(([key]) => key)
}
