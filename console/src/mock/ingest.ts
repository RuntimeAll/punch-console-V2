import type { IngestBatch, ReviewLevel } from './types'

/**
 * mock 录入记录。
 *
 * 🔴 走查判词点名的第二类东西：录入管线跑完到底进来了什么、拦下了什么，
 * 现在只在 agent 的终端里滚过去，人事后查不到。录入记录这一层就是把它落下来：
 * 一次录入 = 一条批次，逐题一盏灯，灯色 + 原因写死在账上。
 *
 * 灯色口径（IngestLight）：
 * - 绿 = 三件套齐、考点命中已有叶子、preflight 全过 → 直接进库可用
 * - 黄 = 进库了但挂着工单（多半是配图要人眼核对），**核过才算转正**
 * - 红 = preflight 拦下，落隔离区不进主表（题库里最多以草稿挂着）
 *
 * 🔴 counts 是**题级**口径且必须自洽：accepted + queued + rejected = total。
 * 行级隔离（解析出来但根本不成题的行，如答案串行、图注被当题面）不计入 counts，
 * 只写在 gateSummary 里并挂到审核台的「隔离行」工单上。
 *
 * 🔴🔴 第四轮按定稿 D-18 / D-21 补两样：
 * ① 批次带 **srcKind**（文字层 / 图片OCR）—— 闸口径完全不同：
 *    文字层有**守恒基准**（图数/公式数/字符多重集可对账，人审只看报警）；
 *    图片源**没有守恒基准**（不知道原件本该有几图几式）⇒ 置信度 + 双跑对照 + 人审必过，
 *    所以图片源批次默认不许直接过。
 * ② 逐条带 **reviewLevel**（L0~L3/人工）—— 复杂度 × 源 决定看多细：
 *    纯文本 L0 ｜ 单图 L1 ｜ 两图以上或表格 L2 ｜ 超长多图跳页 L3 ｜ 手写稿 人工，
 *    且 🔴 **拍照源整体比文字层源高一级**（同样是纯文本，docx 是 L0、拍照就是 L1）。
 */
export const ingestBatches: IngestBatch[] = [
  {
    id: 'ib-001',
    time: '2026-08-14 09:42',
    source: '四上·空间与图形单元卷（扫描件 12 页 · MinerU 本地 OCR）',
    srcKind: '图片OCR',
    templateId: 'it-jingyou-paper',
    counts: { total: 5, accepted: 2, queued: 2, rejected: 1 },
    gateSummary:
      '题面纯净闸 / 三件套闸 / 考点归属闸全过；含图 2 题落待图审队列。另有 1 条行级隔离（第 4 页「答案：48cm」被切成独立行，没挂到任何题上），已进隔离区待人工归位，不计入题级 counts。🔴 图片源无守恒基准，全批按「置信度 + 人审必过」走，等级整体比文字层高一级。',
    items: [
      { seq: 1, title: '把两个完全一样的直角梯形拼成一个长方形，求梯形周长', light: '黄', reviewLevel: 'L2',
        reason: '题面含配图，图的标注位置需与原卷第 2 页逐一核对后才转正', questionId: 'q-4001' },
      { seq: 2, title: '已知三角形两角 55°、75°，求第三个角', light: '黄', reviewLevel: 'L2',
        reason: '题面含配图，「?」的标注位置与原卷疑似不一致', questionId: 'q-4005' },
      { seq: 3, title: '三角形的内角和是(　　)度，四边形的内角和是(　　)度', light: '绿', reviewLevel: 'L1', questionId: 'q-4008' },
      { seq: 4, title: '直角三角形一个锐角 35°，另一个锐角是(　　)°', light: '绿', reviewLevel: 'L1', questionId: 'q-4009' },
      { seq: 5, title: '两个完全一样的直角三角形拼成长方形，周长 36cm、直角边 5cm，求三角形周长', light: '红', reviewLevel: 'L1',
        reason: '条件不足：由长方形周长 36cm 与一条直角边 5cm 推不出斜边，preflight 判「答案不可解」拦下，已落草稿隔离区', questionId: 'q-4011' },
    ],
  },
  {
    id: 'ib-002',
    time: '2026-08-11 20:15',
    source: '四上·思维拓展讲义（docx 文字层直转，无 OCR）',
    srcKind: '文字层',
    templateId: 'it-jiangyi-series',
    counts: { total: 12, accepted: 2, queued: 10, rejected: 0 },
    gateSummary:
      '文字层直转，守恒闸对账通过（图 11 / 公式 34 / 字符多重集全对得上），题面零损；三件套齐全，考点全部命中已有叶子。但 10 题带手绘几何图，图与讲义原稿没做过逐一核对 → 整批落待图审队列，核过才转正。另有 1 条行级隔离（「（图 3-2）」图注被当成题面行）挂在审核台。',
    items: [
      { seq: 1, title: '一个正五边形和一个正方形有一条公共边，求 ∠1', light: '黄', reviewLevel: 'L1',
        reason: '含手绘图：公共边的位置关系要与讲义第 11 页原图核对', questionId: 'q-4006' },
      { seq: 2, title: '五角星求五个角的和', light: '黄', reviewLevel: 'L1',
        reason: '含手绘图：五个角的编号方向（顺/逆时针）要与原图一致，解析按顺时针讲', questionId: 'q-4007' },
      { seq: 3, title: '六边形从同一顶点分成几个三角形，内角和是多少', light: '绿', reviewLevel: 'L0', questionId: 'q-4010' },
      { seq: 4, title: '四边形沿对角线分割，说明内角和为 360°', light: '绿', reviewLevel: 'L0' },
      { seq: 5, title: '七边形的内角和与外角和', light: '黄', reviewLevel: 'L1', reason: '含手绘图，未核对' },
      { seq: 6, title: '风筝形中已知三角，求第四个角', light: '黄', reviewLevel: 'L1', reason: '含手绘图，未核对' },
      { seq: 7, title: '两条平行线被第三条直线所截，求同位角', light: '黄', reviewLevel: 'L1',
        reason: '含手绘图，未核对；本题对应的图疑似就是那条被隔离的「（图 3-2）」，需人工挂回' },
      { seq: 8, title: '正六边形拼地板，求拼接处角度和', light: '黄', reviewLevel: 'L1', reason: '含手绘图，未核对' },
      { seq: 9, title: '三角形纸片折叠后求折痕两侧的角', light: '黄', reviewLevel: 'L2',
        reason: '折前折后两张图，属「两张以上图」⇒ 逐题速审；未核对' },
      { seq: 10, title: '五边形剪去一个角后还剩几个角，内角和怎么变', light: '黄', reviewLevel: 'L1', reason: '含手绘图，未核对' },
      { seq: 11, title: '用三角尺拼出 75°、105°，画出拼法', light: '黄', reviewLevel: 'L2',
        reason: '两种拼法两张图 ⇒ 逐题速审；未核对' },
      { seq: 12, title: '时针与分针在 4:00 的夹角是多少度', light: '黄', reviewLevel: 'L1',
        reason: '含手绘钟面图，未核对；且答案给 150°、解析按每分钟分针 6°/时针 0.5° 算出 165°，两处口径打架，已另挂题审转正工单' },
    ],
  },
  {
    id: 'ib-003',
    time: '2026-08-08 15:20',
    source: '手工零录（备课临时补题 · 四上运算律专项练 + 除法单元卷）',
    srcKind: '文字层',
    counts: { total: 3, accepted: 3, queued: 0, rejected: 0 },
    gateSummary:
      '手工逐题录入，三题全绿：题面纯净（无「计算：」「变式」这类指令词残留）、三件套齐、考点全部命中已有叶子、无配图不需图审。纯文本 + 文字层 ⇒ 全批 L0 直入。这批就是「录题管线轻路径」跑通的样子；没套模板，逐题现录。',
    items: [
      { seq: 1, title: '用简便方法计算：125×88', light: '绿', reviewLevel: 'L0', questionId: 'q-4002' },
      { seq: 2, title: '脱式计算：(280＋120)÷25×4', light: '绿', reviewLevel: 'L0', questionId: 'q-4003' },
      { seq: 3, title: '笔算：728÷26', light: '绿', reviewLevel: 'L0', questionId: 'q-4004' },
    ],
  },
  {
    id: 'ib-004',
    time: '2026-08-16 11:05',
    source: '四上·随堂练两页（手机拍照 · MinerU 本地 OCR）',
    srcKind: '图片OCR',
    counts: { total: 2, accepted: 1, queued: 1, rejected: 0 },
    gateSummary:
      '🔴 拍照源：没有守恒基准（不知道原件本该有几图几式），改走「置信度 + 双跑对照 + 人审必过」。两跑选项标号一致（A/B/C/D 未自动规整，如实保留）；四张选项图整块裁切成功，没有子图错位。图选项题四图 ⇒ 属「两张以上图」，叠加拍照源升一级 = L3 逐题细审。没有对得上的录入模板，按随堂练现切。',
    items: [
      { seq: 1, title: '下面各角中，是钝角的是', light: '绿', reviewLevel: 'L1', questionId: 'q-4012' },
      { seq: 2, title: '下面各组直线中，两条直线互相垂直的是', light: '黄', reviewLevel: 'L3',
        reason: '四个选项各带一张图：要逐图核对是不是原卷那一组（A 斜交 / B 垂直 / C 平行 / D 延长相交），核过才转正',
        questionId: 'q-4013' },
    ],
  },
]

/** 按 id 取批次；找不到返回 undefined */
export function findIngestBatch(id: string): IngestBatch | undefined {
  return ingestBatches.find((b) => b.id === id)
}

/** 三色灯的合计（录入记录页顶部的概览条用） */
export function lightTotals(): { 绿: number; 黄: number; 红: number } {
  const acc = { 绿: 0, 黄: 0, 红: 0 }
  for (const b of ingestBatches) for (const it of b.items) acc[it.light] += 1
  return acc
}

/** 审核等级的合计（哪一级的量最大，就知道人的时间花在哪儿） */
export function levelTotals(): Record<ReviewLevel, number> {
  const acc: Record<ReviewLevel, number> = { L0: 0, L1: 0, L2: 0, L3: 0, 人工: 0 }
  for (const b of ingestBatches) for (const it of b.items) acc[it.reviewLevel] += 1
  return acc
}

/** 🔴 免人审的量（只有 L0 是闸全绿直入，其余都要人看一眼） */
export function autoPassRate(): { auto: number; total: number } {
  const total = ingestBatches.reduce((n, b) => n + b.items.length, 0)
  const auto = ingestBatches.reduce((n, b) => n + b.items.filter((it) => it.reviewLevel === 'L0').length, 0)
  return { auto, total }
}
