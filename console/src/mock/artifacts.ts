import type { Artifact } from './types'

/**
 * mock 资料清单。
 *
 * 🔴 清单只管**记录 + 展示**：这本册子是什么、做到哪一步、交付没有、链接在哪。
 * 生产过程（出题 / 排版 / 出 PDF / 传网盘）全在 agent 那边跑，展示台不做生产管理页。
 */
export const artifacts: Artifact[] = [
  {
    id: 'af-001',
    name: '七上混合运算一本通',
    kind: '打卡册',
    status: '已交付',
    deliveredAt: '2026-07-13',
    link: 'https://pan.example.com/s/1hunhe',
    note: '浙教版口径；教辅版 1037 题，快速训练版砍半。合刊册型，双号共用一条链接。',
  },
  {
    id: 'af-002',
    name: '三上混合运算特训30天',
    kind: '打卡册',
    status: '已交付',
    deliveredAt: '2026-08-01',
    link: 'https://pan.example.com/s/9szs',
    note: '30 天 × 14 题共 420 题；题目由本地表达式树 DSL 生成，逐题实算过闸。',
  },
  {
    id: 'af-003',
    name: '角度问题专练',
    kind: '专项卷',
    status: '已交付',
    deliveredAt: '2026-07-26',
    link: 'https://pan.example.com/s/4jdzl',
    note: '四上口径；覆盖三角形内角和 / 多边形内角和 / 角度计算三个考点。',
  },
  {
    id: 'af-004',
    name: '绝对值压轴打卡',
    kind: '打卡册',
    status: '在产',
    note: '10 天 × 12 题；本地五路径重算已全绿，网盘未传，等第 3 天终审完一起收口。',
  },
  {
    id: 'af-005',
    name: '五上认识懂变举一反三',
    kind: '举一反三',
    status: '已上架',
    deliveredAt: '2026-07-27',
    link: 'https://pan.example.com/s/5rsdb',
    note: '三个专项，五级递进「1 认 2 识 3 懂 4 变 5 再变」，母题挂图已随题走。',
  },
  {
    id: 'af-006',
    name: '四上同步讲义题库批',
    kind: '讲义',
    status: '在产',
    note: '空间与图形单元；已录 11 题，1 题草稿挂起（条件疑似不足，待复核）。',
  },
  {
    id: 'af-007',
    name: '三角形内角和专项卷',
    kind: '专项卷',
    status: '已上架',
    deliveredAt: '2026-08-05',
    link: 'https://pan.example.com/s/3sjx',
    note: '题目卷与解析卷分成两个独立 PDF；题目卷无提示，可直接打印。',
  },
]
