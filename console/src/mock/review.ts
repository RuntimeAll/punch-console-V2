import type { ReviewKind, ReviewTicket } from './types'

/**
 * mock 审核工单队列（审核台 /review 的数据源）。
 *
 * 🔴 与「批改·待办」的分工别搞混：
 * - /grading/queue 管**学生的卷子**（收到出件整条队列，谁该动手一目了然）
 * - /review       管**题库的入口**（录进来的题谁来放行）
 * 两条队列各走各的，不许合成一个「全站待办」——归属不同，处理人也不同。
 *
 * 四类工单：
 * - 图审       题进库了但配图没跟原稿核过（黄灯的主要去处）
 * - 题审转正   草稿题 / 口径打架的题申请转成在用
 * - 考点低置信 打标器给的考点置信度低于阈值，等人工从候选里定一个（或建新叶子）
 * - 隔离行     解析出来但根本不成题的行，preflight 拦下等人工归位
 *
 * 🔴 detail 一律写**工单原话**（机器拦下时到底说了什么），不许改写成客气话——
 * 人审要的就是原话，改写过的话没法判。
 */
export const reviewQueue: ReviewTicket[] = [
  {
    id: 'rv-001',
    kind: '图审',
    title: 'q-4001 梯形拼长方形 · 配图标注位置待核',
    detail:
      '图审器原话：「本题配图经 crop_grp 整块重裁，重裁前后标注文本的相对位置有位移。当前图上 13cm 标在斜腰、25cm 标在长方形的长、10cm 标在右侧高。请对照原卷第 2 页确认三处标注是否都落在同一条边上。」',
    batchId: 'ib-001',
    questionId: 'q-4001',
    priority: '高',
    createdAt: '2026-08-14',
    state: '待处理',
  },
  {
    id: 'rv-002',
    kind: '图审',
    title: 'q-4005 三角形求角 · 「?」的位置与原卷不一致',
    detail:
      '图审器原话：「重建图中未知角「?」标在顶角，OCR 原文的坐标显示原卷该标注在左下角附近（x 偏差 62px）。两处都不影响解法（内角和 180° 减两角），但卷面还原度不达标，需人工确认按哪一版定稿。」',
    batchId: 'ib-001',
    questionId: 'q-4005',
    priority: '中',
    createdAt: '2026-08-14',
    state: '待处理',
  },
  {
    id: 'rv-003',
    kind: '图审',
    title: 'q-4007 五角星 · 五个角的编号方向待定',
    detail:
      '图审器原话：「当前图按顺时针给五个角编号 1→5，讲义原图无法判定编号方向（扫描页有折痕）。解析文本按顺时针讲『角的搬家』，若原图为逆时针则解析需同步改。」',
    batchId: 'ib-002',
    questionId: 'q-4007',
    priority: '中',
    createdAt: '2026-08-11',
    state: '处理中',
  },
  {
    id: 'rv-004',
    kind: '题审转正',
    title: 'q-4011 草稿题转正申请 · 条件疑似不足',
    detail:
      'preflight 原话：「题面给出长方形周长 36cm 与直角三角形的一条直角边 5cm，求三角形周长。由 36cm 可得长+宽=18cm，但两条直角边与斜边三者未定，斜边不可解。判定：答案不可解，落草稿区。」处理选项：① 回原卷补条件后转正 ② 按原卷确实缺条件，退回不录。',
    batchId: 'ib-001',
    questionId: 'q-4011',
    priority: '高',
    createdAt: '2026-08-14',
    state: '待处理',
  },
  {
    id: 'rv-005',
    kind: '题审转正',
    title: 'ib-002 第 12 题「4:00 时针分针夹角」· 答案与解析口径打架',
    detail:
      '一致性闸原话：「答案区写 150°，解析区按『分针每分钟 6°、时针每分钟 0.5°』推出 165°，两值不等且都不是笔误可解释的范围。判定：口径冲突，禁止转正。」需人工定稿一个口径（4:00 整点标准答案应为 120°，两处疑似都错），定稿后整题重录。',
    batchId: 'ib-002',
    priority: '高',
    createdAt: '2026-08-11',
    state: '待处理',
  },
  {
    id: 'rv-006',
    kind: '考点低置信',
    title: '「破十法」未命中已有考点叶 · 置信度 0.41',
    detail:
      '打标器原话：「题面『13-7，先把 13 分成 10 和 3，10-7=3，3+3=6』的解法特征指向『破十法』，但候选叶子里没有同名节点。最高分候选『20 以内退位减法』置信度 0.41，低于阈值 0.60，已挂起等人工定名。备注：本题所属的考察模型 em-004（20以内退位减·破十法型）也还是 draft，建议先定模型名再定叶子名。」',
    // 🔴 这题还没入库（一年级线预研），所以没有 questionId / batchId，
    //    着落点挂在考察模型上：em-004 定了名，这个叶子才好定名。
    modelId: 'em-004',
    candidates: ['20 以内退位减法（一上·第 6 单元）', '退位减法的算理', '平十法与破十法（拟新建叶子）', '减法的计算方法'],
    priority: '中',
    createdAt: '2026-08-12',
    state: '待处理',
  },
  {
    id: 'rv-007',
    kind: '考点低置信',
    title: 'q-4003 撞名叶子二选一 · 置信度 0.52',
    detail:
      '打标器原话：「题面『(280＋120)÷25×4』同时命中『四则混合运算的运算顺序』(0.52) 与『运算顺序判断』(0.48)，两者语义高度重叠且分属不同枝，无法自动裁决。已按最高分暂挂，等人工确认是否要合并这两个叶子。」',
    questionId: 'q-4003',
    batchId: 'ib-003',
    candidates: ['四则混合运算的运算顺序', '运算顺序判断', '同级运算从左往右'],
    priority: '低',
    createdAt: '2026-08-08',
    state: '待处理',
  },
  {
    id: 'rv-008',
    kind: '隔离行',
    title: 'ib-001 行 L-042 · 答案串行，没挂到任何题上',
    detail:
      'preflight 原话：「第 4 页解析出一行『答案：48cm』，该行无题干、无题号、无选项，且上一题（第 1 题）已自带答案块。判定：疑似答案区串行到题面区，隔离不入库。」需人工回原卷确认这个 48cm 是第 1 题答案的重复，还是某道漏抽的题的答案。',
    batchId: 'ib-001',
    priority: '中',
    createdAt: '2026-08-14',
    state: '待处理',
  },
  {
    id: 'rv-009',
    kind: '隔离行',
    title: 'ib-002 行 L-207 ·「（图 3-2）」图注被当成题面行',
    detail:
      'preflight 原话：「解析出一行『（图 3-2）』，长度 6 字符，无题干无答案，判定为图注而非题面，隔离不入库。对应的手绘图已单独裁出并落 img_hd/fig-3-2.png，未挂到任何题上。」批内第 7 题（平行线截同位角）缺一张图，疑似就是这张，需人工挂回。',
    batchId: 'ib-002',
    priority: '中',
    createdAt: '2026-08-11',
    state: '处理中',
  },
]

/** 按类型过滤（审核台的四个页签就吃这个） */
export function ticketsOfKind(kind: ReviewKind): ReviewTicket[] {
  return reviewQueue.filter((t) => t.kind === kind)
}

/** 四类各多少条（页签角标 / 工作台卡片用） */
export function ticketCountByKind(): Record<ReviewKind, number> {
  const acc: Record<ReviewKind, number> = { 图审: 0, 题审转正: 0, 考点低置信: 0, 隔离行: 0 }
  for (const t of reviewQueue) acc[t.kind] += 1
  return acc
}

/** 某道题身上挂着的全部工单（题目详情页显示「这题还没放行」用） */
export function ticketsOfQuestion(questionId: string): ReviewTicket[] {
  return reviewQueue.filter((t) => t.questionId === questionId)
}

/** 某个批次名下的全部工单（录入记录页给「去审核台」入口用） */
export function ticketsOfBatch(batchId: string): ReviewTicket[] {
  return reviewQueue.filter((t) => t.batchId === batchId)
}

/** 某个考察模型被哪些工单卡着（考察模型页显示「等定名」用） */
export function ticketsOfModel(modelId: string): ReviewTicket[] {
  return reviewQueue.filter((t) => t.modelId === modelId)
}
