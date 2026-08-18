import type { DictItem } from './types'

/**
 * 字典表（数据结构.md §2.1⑤ dict_item）。
 *
 * 🔴 为什么值域一定走字典而不是写死中文枚举：老区并存过**四套题型编码**、两套 source 字典，
 * 而 Java 侧 javadoc 还写着「6 类题型 / 3 档难度」这种**过期注释**（现行是 8 类 / 4 档），
 * 照注释写代码必错。v2 把值域收在这一张表里：加一类改一行，页面只认 code。
 *
 * 🔴 题目上存的是 **code**（qtypeCode / diffCode），中文只在渲染那一刻查出来。
 */
export const dictItems: DictItem[] = [
  // 题型 8 类
  { domain: 'qtype', code: 'qt-choice', label: '选择题', ord: 1, status: '在用' },
  { domain: 'qtype', code: 'qt-fill', label: '填空题', ord: 2, status: '在用' },
  { domain: 'qtype', code: 'qt-judge', label: '判断题', ord: 3, status: '在用' },
  { domain: 'qtype', code: 'qt-calc', label: '计算题', ord: 4, status: '在用' },
  { domain: 'qtype', code: 'qt-answer', label: '解答题', ord: 5, status: '在用' },
  { domain: 'qtype', code: 'qt-apply', label: '应用题', ord: 6, status: '在用' },
  { domain: 'qtype', code: 'qt-draw', label: '作图题', ord: 7, status: '在用' },
  { domain: 'qtype', code: 'qt-explore', label: '探究题', ord: 8, status: '在用' },

  // 难度 4 档（口径同「难度评级」rubric：难度=模型阶+稀有度算出来的，不是 LLM 自评）
  { domain: 'difficulty', code: 'df-1', label: '送分', ord: 1, status: '在用' },
  { domain: 'difficulty', code: 'df-2', label: '巩固', ord: 2, status: '在用' },
  { domain: 'difficulty', code: 'df-3', label: '中档', ord: 3, status: '在用' },
  { domain: 'difficulty', code: 'df-4', label: '压轴', ord: 4, status: '在用' },
]

/** 某一域的全部在用字典项（顺序 = ord，页面下拉直接吃） */
export function dictOf(domain: DictItem['domain']): DictItem[] {
  return dictItems.filter((d) => d.domain === domain && d.status === '在用').sort((a, b) => a.ord - b.ord)
}

/** code → 中文标签；查不到如实返回 code 本身（别静默显示成空，那样看不出是脏码） */
export function dictLabel(domain: DictItem['domain'], code: string): string {
  return dictItems.find((d) => d.domain === domain && d.code === code)?.label ?? code
}

/** 题型码 → 中文 */
export function qtypeLabel(code: string): string {
  return dictLabel('qtype', code)
}

/** 难度码 → 中文（送分 / 巩固 / 中档 / 压轴） */
export function diffLabel(code: string): string {
  return dictLabel('difficulty', code)
}

/** 难度码 → 档位序号 1~4（难度星那类展示件要的是序号，不是中文） */
export function diffOrd(code: string): number {
  return dictItems.find((d) => d.domain === 'difficulty' && d.code === code)?.ord ?? 0
}

/** 难度总档数（星星底数，别在页面里写死 4） */
export const DIFF_MAX: number = dictOf('difficulty').length
