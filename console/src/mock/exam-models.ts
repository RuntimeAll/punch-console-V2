import type { ExamModel } from './types'

/**
 * mock 考察模型清单。
 *
 * 🔴 这是走查判词点名的「低频但必须记账」的第一类东西：
 * 一个模型可能半年不改一次，但它管着上百道题的出题口径——没有一份记录，
 * 换个人（或换个 session）就只能凭印象重造，出出来的题退化成瞎换数字。
 *
 * 展示台只做**记录**：看得见、查得到、知道它管着几道题、从哪几道母题蒸馏来的、
 * DSL 文件在哪。参数编辑与真出题都在 agent 侧，本页不做「新建模型」表单。
 */
export const examModels: ExamModel[] = [
  {
    id: 'em-001',
    name: '三位数乘两位数·进位控制型',
    paramSummary:
      '因数A ∈ [100,999]（百位 2~9）；因数B ∈ [11,99]；进位次数 2~3 次；因数末尾 0 的个数 0~1；积不超过 6 位',
    status: 'active',
    questionCount: 148,
    originQuestionIds: ['q-4002'],
    kpNames: ['三位数乘两位数的计算', '因数中间或末尾有 0 的笔算'],
    dslRef: 'dsl/mul-3x2/carry-v3.json',
    note: '进位次数是难度主旋钮：0~1 次＝送分，2 次＝巩固，3 次且中间位连续进位＝中档。四上打卡册 30 天版的主力产题模型，改参数前先看它挂着 148 道题。',
  },
  {
    id: 'em-002',
    name: '混合运算·括号嵌套型',
    paramSummary:
      '运算元 3~5 个；括号 1~2 层；至少含一处同级运算（÷ 与 × 连算）；中间结果与最终结果都必须是整数',
    status: 'active',
    questionCount: 96,
    originQuestionIds: ['q-4003'],
    kpNames: ['四则混合运算的运算顺序', '乘法分配律的应用'],
    dslRef: 'dsl/mixed-ops/bracket-v2.json',
    note: '专治「同级运算随意交换先后」这条错因（(280＋120)÷25×4 被算成 4）。出题时强制留一个「必须从左往右才对」的陷阱位，否则这批题测不出东西。',
  },
  {
    id: 'em-003',
    name: '梯形拼接·周长型',
    paramSummary:
      '上底＋下底 ∈ [20,40]cm；高 ∈ [6,15]cm；斜腰 ∈ [10,20]cm（优先取勾股整数）；拼接方式＝旋转拼成长方形 / 平行四边形',
    status: 'active',
    questionCount: 34,
    originQuestionIds: ['q-4001', 'q-4011'],
    kpNames: ['梯形的特征与分类', '梯形的拼接问题'],
    dslRef: 'dsl/geo-trapezoid/joint-perimeter-v1.json',
    note: '🔴 配图必须随参数重画（上下底与高的比例要跟数值对得上，否则学生按图估就露馅）。q-4011 是同模型的直角三角形变体，原卷条件疑似不足已挂草稿，转正前不进产。',
  },
  {
    id: 'em-004',
    name: '20以内退位减·破十法型',
    paramSummary:
      '被减数 11~18；减数个位 > 被减数个位（强制退位）；每题标注解法＝破十法 / 平十法，同一天内两种解法不混排',
    status: 'draft',
    questionCount: 0,
    originQuestionIds: [],
    // 🔴 空数组 = 溯源断点：「破十法」这片叶子还没铺进教材树，等模型定名后补
    kpNames: [],
    dslRef: 'dsl/sub-within-20/break-ten-v0.draft.json',
    note: '一年级线预研：参数表写完了但还没接出题器，所以挂 0 道题。审核台那条「破十法」考点低置信工单等的就是这个模型定名——名字定了才好把考点叶补进教材树。',
  },
  {
    id: 'em-005',
    name: '绝对值化简·分类讨论型',
    paramSummary:
      '字母个数 1~2；取值区间由数轴给定（含端点 / 不含端点二选一）；讨论分支数 2~3；末行必须能合并同类项',
    status: 'active',
    questionCount: 62,
    originQuestionIds: [],
    // 七上这一枝教材树还没铺，所以这两片叶名在树上暂时找不到（维护区要显式标出来）
    kpNames: ['绝对值的化简', '含字母的绝对值化简'],
    dslRef: 'dsl/abs-value/case-split-v2.json',
    note: '手写立的模型（没有母题来源）。分支数就是难度：2 分支＝巩固，3 分支＝压轴。绝对值压轴打卡册 10 天 × 12 题全部出自这里。',
  },
]

/** 按 id 取模型；找不到返回 undefined */
export function findExamModel(id: string): ExamModel | undefined {
  return examModels.find((m) => m.id === id)
}

/** 某道题被哪些模型认作母题（题目详情页挂「它是谁的母题」用） */
export function modelsOfQuestion(questionId: string): ExamModel[] {
  return examModels.filter((m) => m.originQuestionIds.includes(questionId))
}
