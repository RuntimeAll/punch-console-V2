import { PAPER_SUBTITLE, PAPER_TITLE, paperTotal } from '@/pages/print-sample-paper/paper'

/**
 * 模版库的模版卡数据（mock）。
 *
 * 🔴 判词④：**渲染永远在 agent 本地跑（HTML → Chrome → PDF）**，系统这边只登记
 *    「有哪些模版、长什么样、参数是什么、样张在不在」。所以这份数据是**登记簿**，
 *    不是渲染配置——页面读它铺卡，不拿它去生成任何东西。
 *
 * 🔴 放在页面目录而不是 `@/mock`：模版库是本页自留数据，mock/types.ts 是地基工的正本，
 *    等模版库接真数据（agent 登记写入）时再由地基工提到 @/mock 去。
 */

/** 在用 = 现在出货就用它；停用 = 留档，需要时再启（不删，删了历史册子对不上版式） */
export type TemplateStatus = '在用' | '停用'

/** 样张状态：live = 页面里内嵌真组件能看；pending = 等 agent 渲染完登记回来 */
export type SampleState = 'live' | 'pending'

export interface TemplateParam {
  label: string
  value: string
}

export interface PaperTemplate {
  id: string
  name: string
  /** 用途一句话：什么场合掏这张模版出来 */
  purpose: string
  /** 适用册型 */
  fitFor: string
  /** 卡片上露的四项参数摘要（全表在抽屉里） */
  brief: { paper: string; margin: string; font: string; gap: string }
  version: string
  status: TemplateStatus
  sample: SampleState
  /** 参数全表：抽屉里逐行摆出来，走查时能对着纸核 */
  params: TemplateParam[]
  /** 登记信息：谁在什么时候把这张模版登记进来的 */
  registeredAt: string
  registeredBy: string
  /** 口径与坑：这张模版踩过什么、有什么铁律 */
  note: string
}

/** 内嵌样张的那张模版（?pick= 带题过来时也认它） */
export const STANDARD_TPL_ID = 'tpl-001'

/** 登记来源统一写法：模版都从 agent 本地渲染链登记进来 */
const BY_AGENT = 'agent · 本地渲染链（HTML → Chrome → PDF）'

export const TEMPLATES: PaperTemplate[] = [
  {
    id: STANDARD_TPL_ID,
    name: '专项卷 · 标准版',
    purpose: '一个专项一张卷，题目卷与解析卷分成两个 PDF，题目卷直接打印发给学生。',
    fitFor: '专项卷 / 同步练 / 课后作业',
    brief: { paper: 'A4 纵向', margin: '14mm', font: '10.5pt', gap: '6mm' },
    version: 'v2.3',
    status: '在用',
    sample: 'live',
    registeredAt: '2026-07-26',
    registeredBy: BY_AGENT,
    note: '两条铁律：配图在题面里排第几块就渲在第几块，绝不甩到题尾「配图区」；题目整块不跨页。题目卷不带任何提示与内部词。',
    params: [
      { label: '纸张', value: 'A4 纵向 210 × 297mm' },
      { label: '页边距', value: '14mm（@page，四边等宽）' },
      { label: '分栏', value: '单栏（几何题带图，双栏排不下）' },
      { label: '页眉', value: '品牌小字一行压细线 · 8.5pt / 灰 45% / 居中 / 下线 0.5pt' },
      { label: '卷名', value: `主 17pt 600 居中 · 副 10pt 灰（现「${PAPER_TITLE}」）` },
      { label: '身份行', value: '姓名 28mm / 日期 24mm / 用时 16mm 下划线，段间距 12mm' },
      { label: '分组条', value: '11.5pt 600 · 左竖线 3px · 上 7mm 下 3mm，右侧灰字写要求与题量' },
      { label: '正文', value: '10.5pt / 行距 1.75' },
      { label: '题号', value: '定宽悬挂，题号栏 7mm；全卷连续编号，跨组不重编' },
      { label: '题间距', value: '6mm，题目整块不跨页' },
      { label: '配图', value: '原位混排，限高 30mm，居中' },
      { label: '页脚', value: '「品牌 · 卷名 · 第 N 页 / 共 M 页」8.5pt / 灰 45% / 距正文 6mm' },
      { label: '答案页', value: '题号 + 答案 + 一句方法点拨，另起一页；默认不随学生卷下发' },
      { label: '本样张选题', value: `${PAPER_SUBTITLE} · 共 ${paperTotal} 题（mock 题库）` },
    ],
  },
  {
    id: 'tpl-002',
    name: '打卡册 · 平摊开版',
    purpose: '整页 5 题大留白，孩子直接写在册子上，家长拍一张照就能回传批改。',
    fitFor: '每日打卡册（21 天 / 30 天）',
    brief: { paper: 'A4 纵向', margin: '18mm', font: '12pt', gap: '14mm' },
    version: 'v1.4',
    status: '在用',
    sample: 'pending',
    registeredAt: '2026-08-04',
    registeredBy: BY_AGENT,
    note: '两个坑：stepwise 排法不吃长题面，超长题必须切 rotating；数学高亮要用 \\color，直接写颜色 MathJax 不认。',
    params: [
      { label: '纸张', value: 'A4 纵向 210 × 297mm' },
      { label: '页边距', value: '18mm；装订侧 22mm（平摊装订留位）' },
      { label: '分栏', value: '单栏' },
      { label: '每页题量', value: '5 题（一天一页，整页大留白）' },
      { label: '正文', value: '12pt / 行距 2.0' },
      { label: '题间距', value: '14mm，每题下方留 3 行手写位' },
      { label: '题号', value: '行首悬挂 8mm，按天从 1 重编' },
      { label: '页眉', value: '左「第 N 天」右「日期 ______」，品牌小字居中' },
      { label: '配图', value: '原位混排，限高 34mm' },
      { label: '长题面', value: '超长题自动转 rotating 排法（stepwise 排不下）' },
      { label: '页脚', value: '「第 N 天 / 共 M 天」+ 品牌小字' },
      { label: '答案卷', value: '独立 PDF，绝不与题目卷合并' },
      { label: '水印', value: '网盘 PDF 无水印；小红书配图才带水印' },
    ],
  },
  {
    id: 'tpl-003',
    name: '打卡册 · 紧凑版',
    purpose: '一页排 12～14 题，纯计算刷量用，省纸省打印钱。',
    fitFor: '计算特训 / 口算 / 混合运算',
    brief: { paper: 'A4 纵向', margin: '12mm', font: '10pt', gap: '4mm' },
    version: 'v1.1',
    status: '停用',
    sample: 'pending',
    registeredAt: '2026-07-13',
    registeredBy: BY_AGENT,
    note: '停用原因：家长实测更认大留白版（孩子写得开、拍照也清楚）。本版留档不删——已发出去的册子还是这个版式，对不上会说不清。',
    params: [
      { label: '纸张', value: 'A4 纵向 210 × 297mm' },
      { label: '页边距', value: '12mm' },
      { label: '分栏', value: '双栏（纯计算题、无配图才能双栏）' },
      { label: '每页题量', value: '12 ～ 14 题' },
      { label: '正文', value: '10pt / 行距 1.6' },
      { label: '题间距', value: '4mm' },
      { label: '题号', value: '行内编号，不占独立题号栏' },
      { label: '竖式区', value: '每题右侧留 22 × 18mm 空白格' },
      { label: '配图', value: '不支持（有配图的题请改用平摊开版）' },
      { label: '页脚', value: '「第 N 天 / 共 M 天」' },
    ],
  },
  {
    id: 'tpl-004',
    name: '合刊 · 分页跟随版',
    purpose: '多册合一：只重排版式，不重造题；分页跟随原册，目录与页码统一重编。',
    fitFor: '一本通 / 多册合刊',
    brief: { paper: 'A4 纵向', margin: '14mm', font: '10.5pt', gap: '5mm' },
    version: 'v0.9',
    status: '在用',
    sample: 'pending',
    registeredAt: '2026-07-13',
    registeredBy: BY_AGENT,
    note: '关键是各册吐统一 JSON 契约，改一册跑一次 rebuild 就能重出全册；教材归属要标清楚（同一章在不同教材版本里章号不一样）。',
    params: [
      { label: '纸张', value: 'A4 纵向 210 × 297mm' },
      { label: '页边距', value: '14mm' },
      { label: '分栏', value: '单栏' },
      { label: '分页规则', value: '跟随原册：合刊不重新分页，只换版式' },
      { label: '目录', value: '合刊首部统一重编，原册页码保留在括号里' },
      { label: '章节页', value: '每册起页另起一页，册名居中，下标教材版本' },
      { label: '正文', value: '10.5pt / 行距 1.7' },
      { label: '题间距', value: '5mm' },
      { label: '数据契约', value: '各册吐统一 JSON，一键重出全册' },
      { label: '题量口径', value: '教辅版全量；快速训练版按型砍半，两版共用同一份题源' },
    ],
  },
  {
    id: 'tpl-005',
    name: '学情报告 · 玉米款',
    purpose: '一次测评出一份报告：考得怎么样、错在哪，学术风排面，家长能一口气读完。',
    fitFor: '摸底报告 / 阶段测评报告',
    brief: { paper: 'A4 纵向', margin: '16mm', font: '11pt', gap: '段距 8mm' },
    version: 'v2.0',
    status: '在用',
    sample: 'pending',
    registeredAt: '2026-08-13',
    registeredBy: BY_AGENT,
    note: '三条硬口径：报告头绝不带学生代号；分数一律题数口径（16/19 这种），不写考点题次；结论必须是肯定判断，禁「疑似 / 可能 / 应该」。',
    params: [
      { label: '纸张', value: 'A4 纵向 210 × 297mm' },
      { label: '页边距', value: '16mm' },
      { label: '分栏', value: '单栏 + 右侧 34mm 批注留白' },
      { label: '视觉调性', value: '学术风 · 精准简约：页眉只留品牌小字，禁卡通与大色块' },
      { label: '正文', value: '11pt / 行距 1.8' },
      { label: '段间距', value: '8mm' },
      { label: '图表', value: '逐考点条形图，灰阶 + 单一强调色' },
      { label: '分数口径', value: '题数口径（例 16/19），不按考点题次算' },
      { label: '隐私', value: '报告头不出现学生代号' },
      { label: '交付面', value: '免费阶段只给「考得怎么样 + 错在哪」；走势与明日安排属增值项，不进本模版' },
    ],
  },
  {
    id: 'tpl-006',
    name: '摸底卷 · 获客版',
    purpose: '公开发放的摸底卷：题面干净、不带答案，末页留一句服务说明。',
    fitFor: '摸底卷 / 试听课前测',
    brief: { paper: 'A4 纵向', margin: '14mm', font: '10.5pt', gap: '7mm' },
    version: 'v1.2',
    status: '在用',
    sample: 'pending',
    registeredAt: '2026-08-05',
    registeredBy: BY_AGENT,
    note: '卷面禁内部词（层 / ★ / 素材 / 薄弱这些不许上纸），节标题只写干净知识点名。答案不随卷公开——答案与报告才是转化钩子。',
    params: [
      { label: '纸张', value: 'A4 纵向 210 × 297mm' },
      { label: '页边距', value: '14mm' },
      { label: '分栏', value: '单栏' },
      { label: '题量', value: '12 题 / 60 分钟' },
      { label: '正文', value: '10.5pt / 行距 1.75' },
      { label: '题间距', value: '7mm（留手写位）' },
      { label: '首页', value: '顶部一段说明：这卷做什么用、怎么交回来' },
      { label: '末页', value: '一句服务说明 + 联系方式位；禁二维码大色块' },
      { label: '卷面用词', value: '禁内部词（层 / ★ / 素材 / 薄弱），节标题只写知识点名' },
      { label: '答案', value: '不随卷下发' },
    ],
  },
]

/** 按 id 找模版（?pick= 与抽屉复用） */
export function findTemplate(id: string): PaperTemplate | undefined {
  return TEMPLATES.find((t) => t.id === id)
}
