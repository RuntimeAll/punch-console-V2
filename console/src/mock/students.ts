import type { Batch, BatchState, ItemVerdict, Student, Track } from './types'
import { HUMAN_STATES } from './types'

/**
 * mock 学员批改账本。
 *
 * 🔴 铁律③：学情按「轨」分账。轨 = 考点/专项（如「有理数混合运算」「绝对值化简求值」），
 * 层级是 学员 → 轨 → 天（Batch）。任何分数、趋势、考点覆盖都在**轨内**聚合，
 * 跨轨只能在学员档案层做汇总，绝不把两条轨的天数首尾相接画成一条曲线。
 *
 * 🔴 学员一律代号制（老区红线），mock 里也不许出现真名。
 *
 * 🔴 第三轮：状态从四态换成九态（见 types.ts 的 STATE_MACHINE）。本文件的样本
 * **把九态全铺满了**——队列页走查时九种格子都能看到真数据，不用靠想象。
 * 对应关系：旧「待批」→ 批改中；旧「已确认」除留一条现场样本外都推到已出件。
 */

/** 🔴 mock 基准时刻：停留时长按它算，不用 Date.now()，保证每次走查看到的数字一模一样 */
export const NOW = '2026-08-17T09:45:00'

/** 判定串 → items。字符按顺序对应第 1..N 题；'√' 对、'×' 错、'?' 存疑待人工 */
function mk(pattern: string, kpPool: string[], notes: Record<number, string> = {}): ItemVerdict[] {
  return Array.from(pattern).map((ch, i) => {
    const item: ItemVerdict = {
      qno: i + 1,
      verdict: ch as ItemVerdict['verdict'],
      kp: kpPool[i % kpPool.length],
    }
    if (notes[i + 1]) item.note = notes[i + 1]
    return item
  })
}

/** 由 items 反推 score / doubts，保证账面永远自洽（没有 items 的在飞批次不给分） */
function batch(id: string, dayInTrack: number, date: string, state: BatchState, items: ItemVerdict[]): Batch {
  const b: Batch = { id, dayInTrack, date, state, items }
  if (items.length > 0) {
    b.score = { right: items.filter((it) => it.verdict === '√').length, total: items.length }
    b.doubts = items.filter((it) => it.verdict === '?').length
  }
  return b
}

const KP_混合运算 = ['有理数加减混合运算', '有理数乘除混合运算', '乘方与混合运算', '运算顺序判断', '符号法则']
const KP_绝对值 = ['绝对值的化简', '含字母的绝对值化简', '数轴与绝对值', '绝对值的非负性']

/** 轨 1：七上混合运算 —— 已完结 6 天，全部已出件 */
const 轨_七上混合运算: Track = {
  id: 'tk-hunhe-01',
  name: '七上混合运算',
  bookRef: '七上混合运算一本通',
  status: '已完结',
  days: [
    batch('b-hh-1', 1, '2026-07-14', '已出件', mk('√√×√√√√×√√√√×√√√√×√√', KP_混合运算, { 3: '括号内先算，符号抄错', 18: '乘方与乘法顺序颠倒' })),
    batch('b-hh-2', 2, '2026-07-15', '已出件', mk('√√√√√×√√√√√√√√×√√√√√', KP_混合运算, { 6: '分配律展开漏乘一项' })),
    batch('b-hh-3', 3, '2026-07-16', '已出件', mk('√×√√×√√×√√×√√×√√×√√√', KP_混合运算, { 2: '负号丢失', 8: '除号改乘号后未取倒数', 14: '连续减法未变加' })),
    batch('b-hh-4', 4, '2026-07-17', '已出件', mk('√√√√√√√√×√√√√√√√√√×√', KP_混合运算, { 9: '(-2)³ 与 -2³ 混淆' })),
    batch('b-hh-5', 5, '2026-07-18', '已出件', mk('√√√×√√√√√√√√√√√√√√×√', KP_混合运算, { 4: '通分后分子未加括号' })),
    batch('b-hh-6', 6, '2026-07-19', '已出件', mk('√√√√√√√√√√√√√√√√√√√√', KP_混合运算)),
  ],
}

/**
 * 轨 2：绝对值化简求值 —— 进行中，是队列页最好的样本轨：
 * D3 卡在人手上（待终审，卡了快三天），D4 已经确认完在等收尾（待出件），D5 今早刚收在排队（待认卷）。
 * 🔴 D3 卡着不挡 D4/D5 往前走：终审是人的活，认卷/批改是编排器的活，两条线各跑各的。
 */
const 轨_绝对值化简: Track = {
  id: 'tk-juedui-01',
  name: '绝对值化简求值',
  bookRef: '绝对值压轴打卡',
  status: '进行中',
  days: [
    batch('b-jd-1', 1, '2026-08-12', '已出件', mk('√√×√√√×√√√', KP_绝对值, { 3: '未讨论 a 的正负直接去绝对值', 7: '数轴上点的位置判断错误' })),
    batch('b-jd-2', 2, '2026-08-13', '已出件', mk('√√√√×√√√√×', KP_绝对值, { 5: '分类讨论只写了一种情况', 10: '化简后未合并同类项' })),
    // 🔴 待终审样本：2 题存疑（字迹不清 / 纸张折角），等人工拍板；停了 2 天多，队列上要显眼
    {
      id: 'b-jd-3',
      dayInTrack: 3,
      date: '2026-08-14',
      state: '待终审',
      stuckSince: '2026-08-14T20:10:00',
      score: { right: 6, total: 10 },
      doubts: 2,
      items: [
        { qno: 1, verdict: '√', kp: '绝对值的化简' },
        { qno: 2, verdict: '√', kp: '含字母的绝对值化简' },
        { qno: 3, verdict: '×', kp: '数轴与绝对值', note: '把 |a－b| 直接写成 a－b，未判断大小' },
        { qno: 4, verdict: '?', kp: '含字母的绝对值化简', note: '过程写对，末行答案被涂改，看不清最终写的是 2a 还是 －2a' },
        { qno: 5, verdict: '√', kp: '绝对值的非负性' },
        { qno: 6, verdict: '√', kp: '绝对值的化简' },
        { qno: 7, verdict: '×', kp: '含字母的绝对值化简', note: '分类讨论缺 a＝0 的情况' },
        { qno: 8, verdict: '?', kp: '数轴与绝对值', note: '卷面此处纸张折角，题号 8 的作答区被遮住一半' },
        { qno: 9, verdict: '√', kp: '绝对值的非负性' },
        { qno: 10, verdict: '√', kp: '绝对值的化简' },
      ],
    },
    // 待出件样本：昨天终审确认完，报告还没渲（agent 写总结 → 渲报告 → 推送 这一段还没跑完）
    {
      ...batch('b-jd-4', 4, '2026-08-16', '待出件', mk('√√√√×√√√√√', KP_绝对值, { 5: '去绝对值后忘了变号' })),
      stuckSince: '2026-08-16T21:05:00',
      note: '昨晚 21:05 终审确认，出件任务排在夜间队列，今早还没落报告',
    },
    // 待认卷样本：今早刚收，编排器串行 WIP=1，前面还有一张在批改中，所以排着
    {
      id: 'b-jd-5',
      dayInTrack: 5,
      date: '2026-08-17',
      state: '待认卷',
      stuckSince: '2026-08-17T09:36:10',
      items: [],
      note: '编排器串行 WIP=1，前面「洛天熙 · 有理数混合运算 D3」正在批改中',
    },
  ],
}

/**
 * 洛天熙 · 有理数混合运算 —— 队列页的「系统在飞」样本轨：
 * D2 刚静默判完（已确认），D3 正在无头 session 里跑（批改中），D4 撞库双命中踢给人（待人工认卷）。
 */
const 轨_有理数混合运算: Track = {
  id: 'tk-youli-01',
  name: '有理数混合运算',
  bookRef: '七上混合运算一本通',
  status: '进行中',
  days: [
    batch('b-yl-1', 1, '2026-08-13', '已出件', mk('√√√×√√√√×√', KP_混合运算, { 4: '去括号变号只改了第一项', 9: '乘方底数取错' })),
    // 已确认样本：机器复核全绿，静默定稿，出件任务还没起（已确认 → 待出件 之间的那一瞬）
    {
      ...batch('b-yl-2', 2, '2026-08-15', '已确认', mk('√√√√√×√√√√', KP_混合运算, { 6: '除法未取倒数' })),
      stuckSince: '2026-08-17T09:41:30',
      note: '机器复核全绿，静默确认，等出件任务领走',
    },
    // 批改中样本：无头 session 正在整页直读，没结果所以不给分
    {
      id: 'b-yl-3',
      dayInTrack: 3,
      date: '2026-08-17',
      state: '批改中',
      stuckSince: '2026-08-17T09:31:00',
      items: [],
      note: '无头 session 第 1 轮：整页直读已完成 7/12 题，机器复核未开始',
    },
    // 🔴 待人工认卷样本：两本册子题面重合，编排器双命中，认不出是哪张卷 → 卡在人手上
    {
      id: 'b-yl-4',
      dayInTrack: 4,
      date: '2026-08-17',
      state: '待人工认卷',
      stuckSince: '2026-08-17T08:52:00',
      items: [],
      candidates: ['七上混合运算一本通 · 第 4 天（2026-07 版）', '有理数混合运算 20 天 · 第 4 天（2026-08 改版）'],
      note: '题面与两本册子同时命中（相似度 0.94 / 0.91），编排器不敢自己定，等人指定哪一张',
    },
  ],
}

/**
 * 小铁蛋 · 有理数混合运算 —— 收件段与故障段样本轨：
 * D2 故障挂着等 retry（🔴 就地挂起不自动重试），D3 照片刚落收件箱还在判稳。
 */
const 轨_小铁蛋混合运算: Track = {
  id: 'tk-tiedan-01',
  name: '有理数混合运算',
  bookRef: '七上混合运算一本通',
  status: '进行中',
  days: [
    batch('b-td-1', 1, '2026-08-15', '已出件', mk('√√×√√√√√×√√√', KP_混合运算, { 3: '先乘除后加减的顺序做反了', 9: '乘方写成了乘法' })),
    // 🔴 故障样本：无头会话超时被杀，就地挂起，不自动重试，等人点 retry
    {
      id: 'b-td-2',
      dayInTrack: 2,
      date: '2026-08-16',
      state: '故障',
      stuckSince: '2026-08-16T22:41:00',
      items: [],
      note: '无头 session 超时 20 分钟被杀（整页直读到第 5 题无响应），已就地挂起等 retry；retry 后回到「批改中」',
    },
    // 收件中样本：照片刚落收件箱，90 秒判稳窗口内（防拍一半就开跑）
    {
      id: 'b-td-3',
      dayInTrack: 3,
      date: '2026-08-17',
      state: '收件中',
      stuckSince: '2026-08-17T09:44:10',
      items: [],
      note: '收到 2 张照片，90 秒判稳窗口内（防拍一半）；判稳后转「待认卷」',
    },
  ],
}

/**
 * 学员档案（第四轮按定稿 §一 student 扩表补全：
 * 教材版本 / 在读状态 / 服务档位 / 入营时间 / **肖像** / 备注）。
 *
 * 🔴 红线不变：代号制，真名与联系方式永不入库；触达家长在你手机侧按代号对应。
 * 🔴 profile（肖像）不是花絮：备课选题、出题难度、批改时看哪几处，都吃这几句。
 *    写法要能直接指导动作（「先看后算防硬算」），别写「比较聪明」这种没法照做的话。
 */
export const students: Student[] = [
  {
    code: '小崽子',
    grade: '七年级',
    textbookVer: '浙教版',
    status: '在读',
    serviceTier: '订阅特训 21 天',
    joinedAt: '2026-07-12',
    profile: ['计算准思维欠，套路题稳、变形题一改条件就卡', '绝对值必先判正负再去号，不判就硬去是老毛病', '题量给足反而稳，一次少于 8 题会飘'],
    note: '七上混合运算已完结（6 天全绿收尾），现在跑绝对值化简求值第 5 天。',
    tracks: [轨_七上混合运算, 轨_绝对值化简],
  },
  {
    code: '洛天熙',
    grade: '七年级',
    textbookVer: '人教版',
    status: '在读',
    serviceTier: '订阅特训 7 天（内测）',
    joinedAt: '2026-08-11',
    profile: ['先看后算防硬算：拿到题不看结构直接开算，一路算到底才发现绕远', '去括号变号只改第一项是高频错', '字迹偏淡，拍照容易糊，收卷前提醒补光'],
    note: '内测名额，7 天版跑完再决定要不要转 21 天。',
    tracks: [轨_有理数混合运算],
  },
  {
    code: '小铁蛋',
    grade: '七年级',
    textbookVer: '人教版',
    status: '试听',
    serviceTier: '打卡客户（未订阅）',
    joinedAt: '2026-08-15',
    profile: ['运算顺序常做反：先乘除后加减这条要每天点一次', '乘方写成乘法（3² 写成 3×2）', '交卷时间不稳，常在夜里 22 点后'],
    note: '试听中：D2 那批因无头 session 超时挂了故障，retry 前先确认照片清晰度。',
    tracks: [轨_小铁蛋混合运算],
  },
]

/** 按代号取学员；找不到返回 undefined（学员页需自行处理 404 态） */
export function findStudent(code: string): Student | undefined {
  return students.find((s) => s.code === code)
}

/** 扁平行：一条 = 一个学员的一条轨的某一天 */
export type PendingRow = { student: Student; track: Track; batch: Batch }

/** 全部批次拉平（不排序，页面自己排） */
export function allBatches(): PendingRow[] {
  return students.flatMap((student) =>
    student.tracks.flatMap((track) => track.days.map((batch) => ({ student, track, batch }))),
  )
}

/**
 * 🔴 待办 = **卡在人手上的三态**（待人工认卷 / 待终审 / 故障），与 HUMAN_STATES 同一口径。
 * 系统态（收件中 / 待认卷 / 批改中 / 已确认 / 待出件）不进待办——机器在跑，催人没用。
 */
export function pendingBatches(): PendingRow[] {
  return allBatches().filter((r) => HUMAN_STATES.includes(r.batch.state))
}
