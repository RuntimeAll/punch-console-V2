import type { Question, QuestionKp, QuestionTag, TagDomain } from './types'
import { docOf, figure, option, para, row, text } from './blocks'

/**
 * mock 题库（14 道）。
 *
 * 🔴🔴 第四轮全量迁到**定稿形态**（数据结构.md §2.1）：
 * - 块流 v2：`{ v:2, rows:[{ cells:[…] }] }`，图只留 asset 指针 + 百分比宽（真身在 assets.ts）；
 * - 分类走字典码（qtypeCode / diffCode，见 dict.ts），不写死中文；
 * - 考点存 **kpId**（= 教材树考点叶的 key）+ anchor（怎么挂上去的、多可信），不存名字；
 * - 标签是 { domain, name } 一等公民（tags.ts 的词池），不再是散字符串；
 * - 来源分「题源类 scan/manual」与「生成类 model/pipeline」，血缘走 motherQid + variantOp；
 * - 状态四态：草稿 / 已审 / 上架 / 退役（ingest 只入草稿，promote 才可见；退役只软删）。
 *
 * 🔴🔴 题面里**没有题号、没有分值**，且以后也不许加：
 * 分值属于载体位置（同一道题在不同卷里分值可以不同），题号只是切分锚点、由载体的 ord 承载。
 * 本轮迁移时已逐题清过一遍前缀 —— 谁再往 md 里写「1.」「（5 分）」就是把抽离出去的东西塞回来。
 *
 * 🔴 matchKey = 题面归一化后的指纹（去空白 / 统一符号 / 数字占位），认卷撞库与册内查重都吃它；
 * mock 里写成稳定假指纹，只要求全表唯一、变式与母题不同键。
 *
 * 走查看点（三道新题专为本轮的新能力打样，别删）：
 * - q-4012 四个纯文字短选项 → 一行流式并排；
 * - q-4013 四个**图选项** → 选项整体折行、图不脱离所属选项；
 * - q-4014 生成类（sourceKind='model'）→ 带母题血缘 q-4002 与变式算子。
 *
 * 页面组只读不改；要加题加在数组末尾（评审时按序号点名）。
 */

/** 主考点（恰一）：默认高置信、非兜底 */
function mainKp(kpId: string, confidence = 0.97, stage = '录入解析'): QuestionKp {
  return { kpId, isPrimary: true, anchor: { stage, fallback: false, confidence } }
}

/** 副考点：跨枝的能力标签，可多条 */
function subKp(kpId: string, confidence = 0.9, stage = '录入解析'): QuestionKp {
  return { kpId, isPrimary: false, anchor: { stage, fallback: false, confidence } }
}

/** 兜底挂靠：没命中叶子只好退一步挂，🔴 一律进审核台（低置信不许静默入库） */
function fallbackKp(kpId: string, confidence: number, stage: string): QuestionKp {
  return { kpId, isPrimary: true, anchor: { stage, fallback: true, confidence } }
}

/** 标签（名字必须来自 tags.ts 的词池，别现编） */
function tg(domain: TagDomain, name: string): QuestionTag {
  return { domain, name }
}

// 考点叶 id = 教材树上考点节点的 key（kg-tree.ts），这里给常用的几片起个短名，免得抄错
const KP_梯形拼接 = 'renjiao/g4a/u5/s4/k2'
const KP_角度计算 = 'renjiao/g4a/u3/s3/k2'
const KP_角的分类 = 'renjiao/g4a/u3/s3/k1'
const KP_三角形内角和 = 'renjiao/g4a/u3/s4/k1'
const KP_多边形内角和 = 'renjiao/g4a/u3/s4/k2'
const KP_三位数乘两位数 = 'renjiao/g4a/u4/s2/k1'
const KP_混合运算顺序 = 'renjiao/g4a/u4/s4/k1'
const KP_乘法结合律 = 'renjiao/g4a/u4/s4/k2'
const KP_平行与垂直 = 'renjiao/g4a/u5/s1/k1'
const KP_除法估算 = 'renjiao/g4a/u6/s1/k2'
const KP_三位数除以两位数 = 'renjiao/g4a/u6/s3/k1'

// 教材树路径（归属轴）：五段全写，且每条都在 kg-tree.ts 上走得通
const P_梯形 = ['人教版', '四年级上册', '第五单元 平行四边形和梯形', '梯形', '梯形的拼接问题']
const P_内角和_三角形 = ['人教版', '四年级上册', '第三单元 角的度量', '内角和（拓展）', '三角形的内角和问题']
const P_内角和_多边形 = ['人教版', '四年级上册', '第三单元 角的度量', '内角和（拓展）', '多边形的内角和问题']
const P_运算律 = ['人教版', '四年级上册', '第四单元 三位数乘两位数', '运算顺序与运算律（衔接）']
const P_角分类 = ['人教版', '四年级上册', '第三单元 角的度量', '角的分类与计算', '角的分类（锐角直角钝角平角周角）']
const P_平行垂直 = ['人教版', '四年级上册', '第五单元 平行四边形和梯形', '平行与垂直', '平行与垂直的判断']

export const questions: Question[] = [
  {
    id: 'q-4001',
    // 🔴 打样题：figure 夹在两段题面文字之间，页面必须原位渲染
    blocks: docOf(
      para('把两个完全一样的直角梯形拼成一个长方形（如图），'),
      row(figure('cceea0b6', '62%', '两个完全一样的直角梯形拼成一个长方形')),
      para('这个直角梯形的周长是(　　)。'),
    ),
    answerBlocks: docOf(
      para('25＋10＋13＝48（cm）'),
      para(
        '【方法点拨】拼成的长方形，长就是梯形上底与下底的和，宽就是梯形的高。所以梯形的周长 = 长方形的长 + 长方形的宽 + 梯形的斜腰，不必先分别求出上底和下底。',
      ),
    ),
    analysisBlocks: docOf(
      para('梯形的周长 = 上底 + 下底 + 高 + 斜腰。其中「上底 + 下底」已经被拼成了长方形的长。'),
      row(figure('7b41d2e0', '46%', '蓝线为原直角梯形的四条边')),
      para('上底 + 下底 = 25cm，高 = 10cm，斜腰 = 13cm，合起来 25＋10＋13＝48（cm）。'),
    ),
    qtypeCode: 'qt-fill',
    diffCode: 'df-3',
    patternId: 'qp-tixing-pinjie',
    sourceKind: 'scan',
    sourceRaw: '四上·空间与图形单元卷 P2',
    matchKey: 'mk-3a7f21c9',
    status: '上架',
    createdAt: '2026-08-14',
    kps: [mainKp(KP_梯形拼接), subKp(KP_角度计算, 0.72)],
    tags: [tg('图形特征', '拼接'), tg('场景', '拼图操作'), tg('思想', '转化思想')],
    treePath: P_梯形,
  },
  {
    id: 'q-4002',
    blocks: docOf(para('用简便方法计算：125×88')),
    answerBlocks: docOf(para('125×88＝125×8×11＝1000×11＝11000')),
    analysisBlocks: docOf(para('把 88 拆成 8×11，先凑出 125×8＝1000，再乘 11。拆数时要保证乘积不变。')),
    qtypeCode: 'qt-calc',
    diffCode: 'df-2',
    patternId: 'qp-jianbian-chaishu',
    sourceKind: 'manual',
    sourceRaw: '四上·运算律专项练 P5',
    matchKey: 'mk-88b1e004',
    status: '上架',
    createdAt: '2026-08-08',
    kps: [mainKp(KP_乘法结合律), subKp(KP_三位数乘两位数, 0.88)],
    tags: [tg('方法', '凑整拆数')],
    treePath: [...P_运算律, '乘法结合律的应用'],
  },
  {
    id: 'q-4003',
    blocks: docOf(para('脱式计算：(280＋120)÷25×4')),
    answerBlocks: docOf(para('(280＋120)÷25×4＝400÷25×4＝16×4＝64')),
    analysisBlocks: docOf(
      para('有括号先算括号里的；÷ 和 × 同级，从左往右依次算。'),
      para('典型错解：把 25×4 先凑成 100 再去除，得 4。同级运算不能随意交换先后。'),
    ),
    qtypeCode: 'qt-calc',
    diffCode: 'df-2',
    sourceKind: 'manual',
    sourceRaw: '四上·运算律专项练 P6',
    matchKey: 'mk-c04d7712',
    status: '上架',
    createdAt: '2026-08-08',
    // 🔴 撞名叶子二选一，机器只有 0.52 的把握 —— 审核台挂着「考点低置信」工单等人拍板
    kps: [fallbackKp(KP_混合运算顺序, 0.52, '录入解析·撞名二选一')],
    tags: [tg('方法', '凑整拆数')],
    treePath: [...P_运算律, '四则混合运算的运算顺序'],
  },
  {
    id: 'q-4004',
    blocks: docOf(para('笔算：728÷26＝(　　)')),
    answerBlocks: docOf(para('728÷26＝28')),
    analysisBlocks: docOf(
      para('把 26 看作 30 试商：72÷30 商 2，余数够继续除；商的个位再试 8，26×8＝208，正好除尽。'),
    ),
    qtypeCode: 'qt-calc',
    diffCode: 'df-2',
    sourceKind: 'manual',
    sourceRaw: '四上·除数是两位数的除法单元卷 P3',
    matchKey: 'mk-72826a1f',
    status: '上架',
    createdAt: '2026-08-08',
    kps: [mainKp(KP_三位数除以两位数), subKp(KP_除法估算, 0.85)],
    tags: [tg('方法', '凑整拆数')],
    treePath: [
      '人教版',
      '四年级上册',
      '第六单元 除数是两位数的除法',
      '笔算除法（三位数除以两位数）',
      '三位数除以两位数的计算',
    ],
  },
  {
    id: 'q-4005',
    blocks: docOf(
      para('如图，三角形中已知两个角的度数，'),
      row(figure('3f9c14aa', '40%', '三角形中已知 55° 与 75°')),
      para('求图中标「?」的角是多少度。'),
    ),
    answerBlocks: docOf(para('180°－55°－75°＝50°')),
    analysisBlocks: docOf(para('三角形的内角和是 180°，用 180° 依次减去已知的两个角即可。')),
    qtypeCode: 'qt-answer',
    diffCode: 'df-1',
    patternId: 'qp-neijiaohe-qiujiao',
    sourceKind: 'scan',
    sourceRaw: '四上·空间与图形单元卷 P4',
    matchKey: 'mk-5575a0c2',
    status: '上架',
    createdAt: '2026-08-14',
    kps: [mainKp(KP_三角形内角和), subKp(KP_角度计算)],
    tags: [tg('思想', '数形结合')],
    treePath: P_内角和_三角形,
  },
  {
    id: 'q-4006',
    blocks: docOf(
      para('如图，一个正五边形和一个正方形有一条公共边，'),
      row(figure('91d0b7c3', '34%', '正五边形与正方形共边')),
      para('求 ∠1 的度数。'),
    ),
    answerBlocks: docOf(para('正五边形每个内角：(5－2)×180°÷5＝108°'), para('∠1＝360°－108°－90°＝162°')),
    analysisBlocks: docOf(
      para('先用多边形内角和公式求出正五边形的一个内角 108°，正方形的内角是 90°。'),
      para('公共顶点处三个角围成一个周角，所以 ∠1 = 360° 减去这两个内角。'),
    ),
    qtypeCode: 'qt-answer',
    diffCode: 'df-3',
    patternId: 'qp-neijiaohe-qiujiao',
    sourceKind: 'manual',
    sourceRaw: '四上·思维拓展讲义 P11',
    matchKey: 'mk-108-90-162',
    status: '上架',
    createdAt: '2026-08-11',
    kps: [mainKp(KP_多边形内角和), subKp(KP_角度计算)],
    tags: [tg('图形特征', '共顶点'), tg('思想', '数形结合')],
    treePath: P_内角和_多边形,
  },
  {
    id: 'q-4007',
    blocks: docOf(
      para('下图是一个五角星，'),
      row(figure('6a2e8f57', '38%', '五角星的五个角')),
      para('求 ∠1＋∠2＋∠3＋∠4＋∠5 的度数。'),
    ),
    answerBlocks: docOf(para('∠1＋∠2＋∠3＋∠4＋∠5＝180°')),
    analysisBlocks: docOf(
      para('把五角星看成一个三角形加两个「角的搬家」：利用三角形的外角，把五个尖角依次移到同一个三角形里。'),
      para('五个角最后正好拼成一个三角形的内角和，所以是 180°。'),
    ),
    qtypeCode: 'qt-answer',
    diffCode: 'df-4',
    patternId: 'qp-neijiaohe-qiujiao',
    sourceKind: 'manual',
    sourceRaw: '四上·思维拓展讲义 P14',
    matchKey: 'mk-wujiaoxing180',
    status: '上架',
    createdAt: '2026-08-11',
    kps: [mainKp(KP_三角形内角和), subKp(KP_角度计算)],
    tags: [tg('图形特征', '共顶点'), tg('方法', '整体代入'), tg('思想', '转化思想')],
    treePath: P_内角和_三角形,
  },
  {
    id: 'q-4008',
    blocks: docOf(para('三角形的内角和是(　　)度，四边形的内角和是(　　)度。')),
    answerBlocks: docOf(para('180；360')),
    analysisBlocks: docOf(para('四边形沿对角线可以分成 2 个三角形，内角和是 180°×2＝360°。')),
    qtypeCode: 'qt-fill',
    diffCode: 'df-1',
    sourceKind: 'scan',
    sourceRaw: '四上·空间与图形单元卷 P1',
    matchKey: 'mk-180-360-fill',
    status: '上架',
    createdAt: '2026-08-14',
    kps: [mainKp(KP_三角形内角和), subKp(KP_多边形内角和)],
    tags: [tg('思想', '转化思想')],
    treePath: P_内角和_三角形,
  },
  {
    id: 'q-4009',
    blocks: docOf(para('一个直角三角形中，有一个锐角是 35°，另一个锐角是(　　)°。')),
    answerBlocks: docOf(para('55')),
    analysisBlocks: docOf(para('直角三角形两个锐角的和是 180°－90°＝90°，所以另一个锐角是 90°－35°＝55°。')),
    qtypeCode: 'qt-fill',
    diffCode: 'df-2',
    sourceKind: 'scan',
    sourceRaw: '四上·空间与图形单元卷 P1',
    matchKey: 'mk-35-55-rt',
    status: '上架',
    createdAt: '2026-08-14',
    kps: [mainKp(KP_三角形内角和), subKp(KP_角度计算)],
    tags: [tg('方法', '逆推还原')],
    treePath: P_内角和_三角形,
  },
  {
    id: 'q-4010',
    blocks: docOf(para('一个六边形从同一个顶点出发，可以分成(　　)个三角形，它的内角和是(　　)°。')),
    answerBlocks: docOf(para('4；720')),
    analysisBlocks: docOf(
      para('n 边形从一个顶点出发能分成 (n－2) 个三角形，内角和 = (n－2)×180°。'),
      para('六边形：(6－2)×180°＝720°。'),
    ),
    qtypeCode: 'qt-fill',
    diffCode: 'df-3',
    sourceKind: 'manual',
    sourceRaw: '四上·思维拓展讲义 P12',
    matchKey: 'mk-6bian-720',
    status: '上架',
    createdAt: '2026-08-11',
    kps: [mainKp(KP_多边形内角和)],
    tags: [tg('思想', '转化思想'), tg('方法', '画图辅助')],
    treePath: P_内角和_多边形,
  },
  {
    id: 'q-4011',
    // 草稿态样本：ingest 只入草稿、promote 才可见的活证据（审核台挂着「题审转正」工单）
    blocks: docOf(
      para(
        '把两个完全一样的直角三角形拼成一个长方形，长方形的周长是 36cm，其中一条直角边是 5cm，这个直角三角形的周长是(　　)cm。',
      ),
    ),
    answerBlocks: docOf(para('（待复核）')),
    analysisBlocks: docOf(para('（解析待补：原卷该题条件疑似不足，录入时挂起。）')),
    qtypeCode: 'qt-fill',
    diffCode: 'df-3',
    sourceKind: 'scan',
    sourceRaw: '四上·空间与图形单元卷 P2',
    matchKey: 'mk-36-5-rt-tri',
    status: '草稿',
    createdAt: '2026-08-14',
    // 兜底挂靠 + 低置信：没有「直角三角形拼接」这片叶，只好退挂到梯形拼接
    kps: [fallbackKp(KP_梯形拼接, 0.61, '录入解析·无对应叶兜底')],
    tags: [tg('图形特征', '拼接'), tg('场景', '拼图操作')],
    treePath: P_梯形,
  },
  {
    id: 'q-4012',
    /**
     * 🔴 新能力打样①：四个**纯文字短选项**。
     * 数据层一项一 cell（结构化，选项从来不是一坨文字），排布交渲染层：
     * 短的并排在一行、长的整体折到下一行，**一个选项绝不被拆散**。
     */
    blocks: docOf(
      para('下面各角中，是钝角的是(　　)。'),
      row(
        option('A', text('45°')),
        option('B', text('90°')),
        option('C', text('120°')),
        option('D', text('180°')),
      ),
    ),
    answerBlocks: docOf(para('C')),
    analysisBlocks: docOf(
      para('钝角 = 比直角大、比平角小，即大于 90° 且小于 180°。'),
      para('45° 是锐角，90° 是直角，180° 是平角，只有 120° 落在钝角范围里。'),
    ),
    qtypeCode: 'qt-choice',
    diffCode: 'df-1',
    patternId: 'qp-jiao-fenlei',
    sourceKind: 'scan',
    sourceRaw: '四上·角的度量随堂练（手机拍照）P1',
    matchKey: 'mk-dunjiao-abcd',
    status: '上架',
    createdAt: '2026-08-16',
    kps: [mainKp(KP_角的分类, 0.94, '录入解析·OCR')],
    tags: [tg('思想', '分类讨论')],
    treePath: P_角分类,
  },
  {
    id: 'q-4013',
    /**
     * 🔴 新能力打样②：**图选项**（老区实测 313 个选项含图）。
     * 每个选项里裹着一张 figure，图跟着自己的选项走 —— 选项换行时图一起走，
     * 绝不允许把四张图抽出来集中成「配图区」再让人对标号。
     */
    blocks: docOf(
      para('下面各组直线中，两条直线互相垂直的是(　　)。'),
      row(
        option('A', figure('d41a9e02', '22%')),
        option('B', figure('d52b8f13', '22%')),
        option('C', figure('d63ca024', '22%')),
        option('D', figure('d74db135', '22%')),
      ),
    ),
    answerBlocks: docOf(para('B')),
    analysisBlocks: docOf(
      para('两条直线相交成直角才叫互相垂直，图上有直角标记的那一组就是。'),
      para('A 组相交但不成直角；C 组是平行（永不相交）；D 组现在没相交，延长后会相交但不成直角。'),
    ),
    qtypeCode: 'qt-choice',
    diffCode: 'df-2',
    patternId: 'qp-pingxing-chuizhi',
    sourceKind: 'scan',
    sourceRaw: '四上·平行与垂直随堂练（手机拍照）P2',
    matchKey: 'mk-chuizhi-4fig',
    status: '上架',
    createdAt: '2026-08-16',
    kps: [mainKp(KP_平行与垂直, 0.91, '录入解析·OCR')],
    tags: [tg('思想', '数形结合'), tg('方法', '画图辅助')],
    treePath: P_平行垂直,
  },
  {
    id: 'q-4014',
    /**
     * 🔴 新能力打样③：**生成类**题（sourceKind='model'）。
     * 血缘就在题上：母题 q-4002 + 变式算子「换数保结构」，🔴 不另建 trace 表
     *（老区那张平行表只有 6 行，注释却说它是 SSOT —— 是谎言，v2 以本列为准）。
     * 题库页默认只看题源类（scan/manual），生成类要专门筛出来看，
     * 别让它混进「我录了多少题」的账。
     */
    blocks: docOf(para('用简便方法计算：25×44')),
    answerBlocks: docOf(para('25×44＝25×4×11＝100×11＝1100')),
    analysisBlocks: docOf(
      para('与母题同一条路子：把 44 拆成 4×11，先凑出 25×4＝100，再乘 11。'),
      para('拆数只换数字不换结构 —— 母题凑的是 125×8＝1000，这里凑的是 25×4＝100。'),
    ),
    qtypeCode: 'qt-calc',
    diffCode: 'df-2',
    patternId: 'qp-jianbian-chaishu',
    sourceKind: 'model',
    sourceRaw: '举一反三·乘法结合律拆数凑整（em-002 出题器）',
    motherQid: 'q-4002',
    variantOp: '换数保结构',
    matchKey: 'mk-25x44-var',
    // 生成出来过了闸但还没上架：四态里「已审」这一格的活样本
    status: '已审',
    createdAt: '2026-08-17',
    kps: [mainKp(KP_乘法结合律, 0.99, '母题继承')],
    tags: [tg('方法', '凑整拆数')],
    treePath: [...P_运算律, '乘法结合律的应用'],
  },
]

/** 按 id 取题；找不到返回 undefined（详情页需自行处理 404 态） */
export function findQuestion(id: string): Question | undefined {
  return questions.find((q) => q.id === id)
}

/**
 * 教材树按节点筛题：给一条 label 路径（可以只到单元、只到小节），
 * 返回 treePath 以它开头的全部题。
 * 🔴 前缀匹配，所以点「第三单元 角的度量」能一次拿到该单元下所有小节的题；
 *    传空数组 = 不筛（返回全部），页面别为此另写一套 if。
 */
export function questionsUnderPath(path: string[]): Question[] {
  if (path.length === 0) return questions
  return questions.filter((q) => q.treePath !== undefined && path.every((seg, i) => q.treePath?.[i] === seg))
}

/**
 * 词表口径的全部考点名（题库页的**考点**下拉筛选用，顺序即展示顺序）。
 * 🔴 这 11 个词全部能在 kg-tree.ts 上找到同名叶子；教材树的考点叶远多于这 11 个
 *   （树是全量目录，本词表只是「当前 mock 题库真用到的」）。两处别互相覆盖：
 *   树管归属筛选（treePath），本词表管能力标签筛选（kps）。
 */
export const kpVocabulary: string[] = [
  '梯形的拼接问题',
  '三角形的内角和问题',
  '多边形的内角和问题',
  '角度计算问题',
  '角的分类（锐角直角钝角平角周角）',
  '平行与垂直的判断',
  '四则混合运算的运算顺序',
  '乘法结合律的应用',
  '三位数乘两位数的计算',
  '三位数除以两位数的计算',
  '除法估算问题',
]

/** 🔴 题源类（scan/manual）= 题库页默认口径；生成类（model/pipeline）要专门筛（定稿 D-9） */
export function sourceQuestions(): Question[] {
  return questions.filter((q) => q.sourceKind === 'scan' || q.sourceKind === 'manual')
}

/** 这道题的变式兄弟（同一个母题下的题；母题自己不算） */
export function variantsOf(motherQid: string): Question[] {
  return questions.filter((q) => q.motherQid === motherQid)
}
