import type { IngestTemplate } from './types'

/**
 * 录入模板库（数据结构.md D-21 ingest_template）= 老区「版式方言」的正规化容器。
 *
 * 🔴 录题流程里它站在这个位置：
 *   格式确认 → **先查相似题记录**（match_key + 近似检索）
 *   → 有相似 ⇒ 沿用既有切割方式直接分割录入
 *   → 无相似 ⇒ **对照本表**，评估要不要新建一张模板 → 按审核等级决定是否入库。
 *
 * 🔴 layoutTraits 写的是「怎么认出这版式归我管」（给人也给机器看的识别特征），
 * 不是版式的美学描述 —— 认不出来的模板等于没有。
 */
export const ingestTemplates: IngestTemplate[] = [
  {
    id: 'it-jingyou-paper',
    name: '试卷·菁优网导出版式',
    layoutTraits:
      '题号顶格「1．」全角点；每题末尾带【答案】【解答】【点评】三段标记；配图单独成段居中；卷末集中附答案区。',
    rulesRef: '录入管线/切割规则/jingyou_paper.py（按【答案】标记切段，图按段内顺序回填）',
    sampleRef: '知识库/资产/样张/jingyou-p1.png',
    status: '在用',
    createdAt: '2026-08-08',
  },
  {
    id: 'it-jiangyi-series',
    name: '同步讲义系列（例题→变式→作业三段式）',
    layoutTraits:
      '每节以「例 N」起头，紧跟「变式 N-1 / N-2」，节末是「课后作业」；例题与变式之间靠缩进区分，没有横线分隔。',
    rulesRef: '录入管线/切割规则/jiangyi_series.py（例题与变式建母子血缘，作业段独立成题）',
    sampleRef: '知识库/资产/样张/jiangyi-u3.png',
    status: '在用',
    createdAt: '2026-08-11',
  },
  {
    id: 'it-hekan',
    name: '合刊册（多册合一）',
    layoutTraits:
      '同一页混排两个来源册的题，页眉标来源册名，两册题号各自独立从 1 开始 —— 🔴 认不出来源就会把两册题号串成一串。',
    rulesRef: '（待落）现在靠现切：先按页眉分流来源册，再各自按册内规则切',
    status: '在用',
    createdAt: '2026-08-15',
  },
]

/** 按 id 取模板；找不到返回 undefined */
export function findIngestTemplate(id: string): IngestTemplate | undefined {
  return ingestTemplates.find((t) => t.id === id)
}
