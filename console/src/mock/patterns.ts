import type { QuestionPattern, SolutionModel } from './types'
import { questions } from './questions'

/**
 * 题型目录 + 金标解题模型（数据结构.md §2.1④，老区 326 条 pattern / 43 条 model 的精华位）。
 *
 * 🔴 三样东西分工别混（页面上也别把它们摆成一个列表）：
 * - **QuestionPattern（题型目录）**：这类题**长什么样** —— 识别与归类用，题挂 patternId；
 * - **SolutionModel（解题模型）**：这类题**怎么解** —— 举一反三的地基，难度靠它的 tier/freq 算；
 * - **ExamModel（考察模型，exam-models.ts）**：这类题**怎么造** —— 出题 DSL 的配方。
 *
 * 🔴 两张表的 kpIds 都是**多值**（2026-08-17 用户拍板：「模型是可能考多个考点的，不能说是一个」）。
 */
export const questionPatterns: QuestionPattern[] = [
  {
    id: 'qp-tixing-pinjie',
    name: '拼接还原型（梯形/三角形拼长方形）',
    kpIds: ['renjiao/g4a/u5/s4/k2', 'renjiao/g4a/u5/s4/k1'],
    desc: '给两个全等图形拼成的规则图形，反过来求原图形的边或周长。特征是「拼后的边 = 拼前若干条边的和」。',
    status: '在用',
  },
  {
    id: 'qp-neijiaohe-qiujiao',
    name: '内角和求角型',
    kpIds: ['renjiao/g4a/u3/s4/k1', 'renjiao/g4a/u3/s4/k2', 'renjiao/g4a/u3/s3/k2'],
    desc: '已知多边形若干内角求剩下那个角；含共顶点周角、外角搬家等变形。',
    status: '在用',
  },
  {
    id: 'qp-jianbian-chaishu',
    name: '简便计算·拆数凑整型',
    kpIds: ['renjiao/g4a/u4/s4/k2', 'renjiao/g4a/u4/s2/k1'],
    desc: '把一个因数拆成两个数的积，先凑出整十整百再算。识别特征：式子里出现 25 / 125 / 8 / 4 这类互补数。',
    status: '在用',
  },
  {
    id: 'qp-shishang-tiaoshang',
    name: '试商调商型（三位数除以两位数）',
    kpIds: ['renjiao/g4a/u6/s3/k1', 'renjiao/g4a/u6/s1/k2'],
    desc: '把除数看成整十数试商，再按余数调商。识别特征：除数个位是 6~9（试大）或 1~4（试小）。',
    status: '在用',
  },
  {
    id: 'qp-jiao-fenlei',
    name: '角的分类判断型',
    kpIds: ['renjiao/g4a/u3/s3/k1'],
    desc: '给若干角的度数或图形，判断它属于锐角/直角/钝角/平角/周角。四选一是最常见的载体。',
    status: '在用',
  },
  {
    id: 'qp-pingxing-chuizhi',
    name: '平行与垂直识图型',
    kpIds: ['renjiao/g4a/u5/s1/k1'],
    desc: '给几组直线的图，判断哪一组平行、哪一组垂直。🔴 选项本身是图，是「图选项」的典型题型。',
    status: '在用',
  },
]

/**
 * 金标解题模型。
 * - triggerFeature   看到什么就用它（这句必须能让人一眼对上题面）
 * - actionConclusion 怎么做、得到什么
 * - tier / freq      🔴 双旋钮：tier=模型的阶（越高越难），freq=出现频次（越低越稀有）。
 *                    难度由「阶 + 稀有度」算出来，**LLM 只匹配模型、不自评难度**。
 */
export const solutionModels: SolutionModel[] = [
  {
    id: 'sm-pinjie-bianyi',
    name: '拼接边转移',
    kpIds: ['renjiao/g4a/u5/s4/k2', 'renjiao/g4a/u5/s4/k1'],
    triggerFeature: '题面出现「两个完全一样的…拼成…」，且问的是原图形的周长或某条边',
    actionConclusion: '把拼后图形的边按拼接关系翻译成原图形的边（拼后长 = 上底+下底），周长直接凑，不必先分别求出上下底',
    tier: 2,
    freq: 3,
    status: '在用',
  },
  {
    id: 'sm-neijiaohe-jianfa',
    name: '内角和减法',
    kpIds: ['renjiao/g4a/u3/s4/k1', 'renjiao/g4a/u3/s3/k2'],
    triggerFeature: '给出三角形（或 n 边形）里的若干个角，求剩下一个角',
    actionConclusion: '用 (n−2)×180° 求出内角和，减去已知角即得所求角',
    tier: 1,
    freq: 5,
    status: '在用',
  },
  {
    id: 'sm-waijiao-banjia',
    name: '外角搬家（角的转移）',
    kpIds: ['renjiao/g4a/u3/s4/k1', 'renjiao/g4a/u3/s4/k2'],
    triggerFeature: '几个角散在不同三角形里，直接加不起来（五角星、镖形、共顶点图）',
    actionConclusion: '用「三角形的外角 = 不相邻两内角之和」把散角搬到同一个三角形里，再一次性用内角和收口',
    tier: 3,
    freq: 2,
    status: '在用',
  },
  {
    id: 'sm-chaishu-couzheng',
    name: '拆数凑整',
    kpIds: ['renjiao/g4a/u4/s4/k2', 'renjiao/g4a/u4/s2/k1'],
    triggerFeature: '连乘式里出现 25/125/8/4 这类互补数，或某个因数拆开后能凑整十整百',
    actionConclusion: '把因数拆成两个数的积后重新结合，先算出 100/1000 再乘剩下那个数；🔴 拆数必须保证乘积不变',
    tier: 1,
    freq: 5,
    status: '在用',
  },
  {
    id: 'sm-shishang-tiaoshang',
    name: '试商调商',
    kpIds: ['renjiao/g4a/u6/s3/k1', 'renjiao/g4a/u6/s1/k2'],
    triggerFeature: '三位数除以两位数的笔算，除数不是整十数',
    actionConclusion: '把除数四舍五入成整十数试商：试大了往小调、余数比除数大就往大调，直到余数小于除数',
    tier: 2,
    freq: 4,
    status: '在用',
  },
]

/** 按 id 取题型；找不到返回 undefined */
export function findPattern(id: string): QuestionPattern | undefined {
  return questionPatterns.find((p) => p.id === id)
}

/** 按 id 取解题模型；找不到返回 undefined */
export function findSolutionModel(id: string): SolutionModel | undefined {
  return solutionModels.find((m) => m.id === id)
}

/** 挂在这个题型下的题（现算，不落计数字段 —— 老区计数 143 个里 74 个是错的） */
export function questionsOfPattern(patternId: string): string[] {
  return questions.filter((q) => q.patternId === patternId).map((q) => q.id)
}

/** 这片考点叶上挂着的解题模型（kpIds 多值，所以一片叶可能对上多个模型） */
export function modelsOfKpId(kpId: string): SolutionModel[] {
  return solutionModels.filter((m) => m.kpIds.includes(kpId))
}
