import { Button, Card, Col, Collapse, Descriptions, Empty, Row, Space, Tag, Typography } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import {
  diffLabel, findPattern, findQuestion, hasOptionIn, kpNameOf, qtypeLabel,
  questions, questionsOfPattern, variantsOf,
} from '@/mock'
// 🔴 溯源链渲法只有一份实现（kg 组），本页单向依赖（见 kg/trace.ts 顶部的依赖方向说明）
import { KpTraceLink } from '@/pages/kg/KpTraceLink'
import { anchorTitle, CONF_GATE, isGenerated, isLowConf, sourceKindText, sourceText } from '@/pages/questions/helpers'
import { DifficultyStars, StatusTag, TagChipsGrouped, TreePathTrail } from '@/pages/questions/parts'
import { QuestionBlocks } from './QuestionBlocks'

/**
 * 题目详情 /questions/:id —— 🔴 本次评审的核心页，替掉老版被否定的页面结构。
 * 归属：页面组「题库」。
 *
 * 页面结构（主区三段 + 右侧一栏，别再加第五段，页面宁缺勿滥）：
 * ① 顶部动作条：上一题 / 下一题 / 在模版库中查看 / 返回题库
 * ② 🔴 **元信息卡**（主区最上、最显眼）：来源 / 状态 / 题型 / 难度 / 题型目录 / 血缘 +
 *    考点（主考点 ★ + 置信度，低置信标黄）+ 标签（按域分组 chips）。
 *    为什么摆在题面**上面**：走查时第一个问题永远是「这题哪来的、什么档次、归谁管」，
 *    塞进右侧窄栏就得靠人去找；题面本身是纯题面，元信息一律外挂在这张卡里。
 * ③ 主区「学生视角」题目卡：题面块流原位混排（图在中间就在中间、选项流式并排），
 *    答案 / 解析各是一条独立块流，收进折叠面板、**默认收起**（先当题看，再看答案）
 * ④ 右侧窄栏「归属与关联」：树位置面包屑 / 血缘兄弟 / 同题型目录的题 / 题号 / 排重键
 *
 * 🔴🔴 铁律（定稿 §2.1①）：题面是**纯题面** —— 题号与分值根本不在 question 上
 *   （分值属于载体位置，题号只是切分锚点由载体 ord 承载）。
 *   页面上出现的「题号 q-40xx」是**库内 id**，不是卷面题号，两者别混。
 * 🔴 只读页：不做编辑表单。改题、补解析、重打标一律归 agent，页面不承担 CRUD。
 */
export default function QuestionDetail() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const q = findQuestion(id)

  // 上一题 / 下一题按 mock 数组顺序走（将来接后端换成列表页当前筛选结果的游标）
  const index = questions.findIndex((item) => item.id === id)
  const prev = index > 0 ? questions[index - 1] : undefined
  const next = index >= 0 && index < questions.length - 1 ? questions[index + 1] : undefined

  if (!q) {
    return (
      <PageFrame title="题目详情">
        <Card size="small">
          <Empty description={`题库里没有这道题：${id}`}>
            <Button onClick={() => navigate('/questions')}>返回题库</Button>
          </Empty>
        </Card>
      </PageFrame>
    )
  }

  const pattern = q.patternId ? findPattern(q.patternId) : undefined
  /** 本题派生出去的变式（本题当母题时） */
  const derived = variantsOf(q.id)
  /** 同一个母题下的其它变式（本题是变式时）——血缘的横向一支 */
  const siblings = q.motherQid ? variantsOf(q.motherQid).filter((v) => v.id !== q.id) : []
  /** 同一个题型目录下的题（「这类题长什么样」的其它样本） */
  const mates = q.patternId ? questionsOfPattern(q.patternId).filter((x) => x !== q.id) : []

  /** 题号链接的统一渲法（血缘那几处都用它，别各写各的 Link） */
  const qidLink = (qid: string) => (
    <Typography.Link key={qid} onClick={() => navigate(`/questions/${qid}`)} style={{ marginInlineEnd: 8 }}>
      {qid}
    </Typography.Link>
  )

  return (
    <PageFrame
      title={`题目 ${q.id}`}
      desc={sourceText(q)}
      extra={
        <Space size={8} wrap>
          <Button disabled={!prev} onClick={() => prev && navigate(`/questions/${prev.id}`)}>
            ← 上一题
          </Button>
          <Button disabled={!next} onClick={() => next && navigate(`/questions/${next.id}`)}>
            下一题 →
          </Button>
          {/* 约定：带 ?pick=<题号> 过去，模版库页可据此预选这道题（读不读由导出组定） */}
          <Button onClick={() => navigate(`/export-preview?pick=${q.id}`)}>在模版库中查看</Button>
          <Button type="text" onClick={() => navigate('/questions')}>
            返回题库
          </Button>
        </Space>
      }
    >
      <Row gutter={[12, 12]} wrap>
        {/* 主区 */}
        <Col flex="1 1 560px" style={{ minWidth: 0 }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {/*
              🔴 生成类横幅（定稿 D-9）：这题不是录进来的，是**机器产的**。
              摆在最上面是因为它会改变读者对下面一切的判断（该不该当作库存题、该不该二次校验）。
              淡底 + 细边，不做大色块（全站审美口径）。
            */}
            {isGenerated(q) ? (
              <div style={{ border: '1px solid #efdbff', background: '#fcfaff', borderRadius: 6, padding: '8px 12px' }}>
                <Space size={8} wrap>
                  <Tag color="purple" style={{ marginInlineEnd: 0 }}>
                    生成类
                  </Tag>
                  <Typography.Text strong style={{ fontSize: 13 }}>
                    来自考察模型 · {sourceKindText(q.sourceKind)}
                  </Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {q.sourceRaw}
                  </Typography.Text>
                </Space>
                <div style={{ marginTop: 4, fontSize: 12 }}>
                  {q.motherQid ? (
                    <span>
                      血缘：母题 {qidLink(q.motherQid)}
                      {q.variantOp ? `· 变式算子「${q.variantOp}」` : null}
                    </span>
                  ) : (
                    <Typography.Text type="secondary">血缘：出题器直出，无母题</Typography.Text>
                  )}
                  <Typography.Text type="secondary">
                    　—— 血缘就在题上（母题字段即 SSOT，不另建 trace 表）；题库页默认不看生成类。
                  </Typography.Text>
                </div>
              </div>
            ) : null}

            {/* ② 元信息卡 */}
            <Card
              size="small"
              title="元信息"
              extra={
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  定稿 §2.1 的题目字段，一屏看全（题面里不含题号与分值）
                </Typography.Text>
              }
            >
              <Descriptions
                size="small"
                column={{ xs: 1, sm: 2 }}
                bordered
                /* label 定宽 96 + 禁折行：84 时「题型目录」会断成「题型目/录」（集成工目检点名） */
                styles={{ label: { width: 96, whiteSpace: 'nowrap' } }}
                items={[
                  {
                    key: 'source',
                    label: '来源',
                    children: (
                      <span>
                        {q.sourceRaw}
                        <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineStart: 6 }}>
                          （{sourceKindText(q.sourceKind)}）
                        </Typography.Text>
                      </span>
                    ),
                  },
                  { key: 'status', label: '状态', children: <StatusTag status={q.status} /> },
                  { key: 'qtype', label: '题型', children: qtypeLabel(q.qtypeCode) },
                  {
                    key: 'difficulty',
                    label: '难度',
                    children: (
                      <Space size={6}>
                        <DifficultyStars code={q.diffCode} />
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {diffLabel(q.diffCode)}
                        </Typography.Text>
                      </Space>
                    ),
                  },
                  {
                    key: 'pattern',
                    label: '题型目录',
                    children: pattern ? (
                      <span>
                        {/* 点进去 = 回列表按这个题型目录筛（?pattern=<id> 是两页之间的传话口径） */}
                        <Typography.Link
                          title={pattern.desc}
                          onClick={() => navigate(`/questions?pattern=${encodeURIComponent(pattern.id)}`)}
                        >
                          {pattern.name}
                        </Typography.Link>
                        <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineStart: 6 }}>
                          同类另有 {mates.length} 道
                        </Typography.Text>
                      </span>
                    ) : (
                      <Typography.Text type="secondary">未归目录</Typography.Text>
                    ),
                  },
                  {
                    key: 'lineage',
                    label: '血缘',
                    children: q.motherQid ? (
                      <span>
                        母题 {qidLink(q.motherQid)}
                        {q.variantOp ? (
                          <Typography.Text type="secondary">{`算子「${q.variantOp}」`}</Typography.Text>
                        ) : null}
                      </span>
                    ) : derived.length ? (
                      <span>
                        <Typography.Text type="secondary" style={{ marginInlineEnd: 6 }}>
                          本题是母题，已派生 {derived.length} 道：
                        </Typography.Text>
                        {derived.map((v) => qidLink(v.id))}
                      </span>
                    ) : (
                      <Typography.Text type="secondary">无母题、未派生变式</Typography.Text>
                    ),
                  },
                ]}
              />

              {/*
                考点行单独摆在 Descriptions 外面：它不是一句话，是**一条条带来历的挂靠**——
                每条都要显示「主/副 + 置信度 + 是不是兜底」，塞进两列格子里挤不下也读不清。
                🔴 低置信 / 兜底一律标黄（口径 = helpers 的 isLowConf，与列表页同一条线）：
                  那是欠账（该进审核台），不是正常态，页面必须让它看得见。
              */}
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px dashed #f0f0f0' }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  考点（能力标签轴 · 主考点恰一）—— 点考点名去知识图谱，看这片叶挂着什么家当
                </Typography.Text>
                <div style={{ marginTop: 6 }}>
                  {q.kps.map((k) => {
                    const low = isLowConf(k.anchor)
                    const belowGate = k.anchor.confidence < CONF_GATE
                    return (
                      <div
                        key={k.kpId}
                        style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}
                      >
                        {/* 🔴 题上存 kpId，名字现查：改叶子名不用回写每道题 */}
                        <KpTraceLink name={kpNameOf(k.kpId)} primary={k.isPrimary} />
                        <Typography.Text
                          title={anchorTitle(k.anchor)}
                          style={{ fontSize: 12, color: low ? '#d46b08' : 'rgba(0,0,0,0.45)' }}
                        >
                          {k.isPrimary ? '主考点' : '副考点'} · 置信度{' '}
                          {Math.round(k.anchor.confidence * 100)}% · 来历「{k.anchor.stage}」
                          {k.anchor.fallback ? ' · 兜底挂靠' : ''}
                          {belowGate ? ` · 低于入库闸 ${Math.round(CONF_GATE * 100)}%，该进审核台` : ''}
                        </Typography.Text>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/*
                标签行：🔴 **按域分组**（场景 / 方法 / 思想 / 图形特征）。
                分组不是排版癖好——标签有四个方向这件事，糊成一排灰 Tag 就看不见了；
                而且开新域时页面零改（域来自 TAG_DOMAINS 正本）。
              */}
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed #f0f0f0' }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  标签（不成树、不定量的归类维度；与考点是两条轴，别混）
                </Typography.Text>
                <div style={{ marginTop: 6 }}>
                  <TagChipsGrouped tags={q.tags} />
                </div>
              </div>
            </Card>

            {/* ③ 题目（学生视角） */}
            <Card
              size="small"
              title="题目（学生视角）"
              extra={
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {hasOptionIn(q.blocks)
                    ? '选项结构化：短选项并排、放不下整体折行，一个选项绝不被拆散'
                    : '题面与配图按块流顺序原位渲染'}
                </Typography.Text>
              }
            >
              {/* 🔴 一条块流一次渲染，图夹在哪两段文字之间就渲在那儿；题面里没有题号、没有分值 */}
              <QuestionBlocks blocks={q.blocks} />
            </Card>

            {/* 答案 / 解析：默认收起，先当题看 */}
            <Collapse
              size="small"
              defaultActiveKey={[]}
              items={[
                {
                  key: 'answer',
                  label: '答案',
                  children: <QuestionBlocks blocks={q.answerBlocks} empty="（答案待录）" />,
                },
                {
                  key: 'analysis',
                  label: '解析',
                  children: <QuestionBlocks blocks={q.analysisBlocks} empty="（解析待补）" />,
                },
              ]}
            />
          </Space>
        </Col>

        {/* ④ 右侧窄栏：归属与关联（元信息在左卡，这里只放「从这题还能去哪」） */}
        <Col flex="0 1 300px" style={{ minWidth: 260 }}>
          <Card size="small" title="归属与关联">
            <Descriptions
              size="small"
              column={1}
              styles={{ label: { width: 56 } }}
              items={[
                {
                  /**
                   * 🔴 归属轴，与元信息卡里的「考点」是两回事、别合并：
                   * - 这里「树位置」= 这题长在教材哪根枝上，点回 /questions?tree=… 带筛选；
                   * - 那里「考点」= 这题考什么（可跨枝、可副考点），点去 /kg 看那片叶。
                   * 两者末段常同名，但回答的是不同的问题。
                   */
                  key: 'treePath',
                  label: '树位置',
                  children: <TreePathTrail path={q.treePath} />,
                },
                {
                  key: 'siblings',
                  label: '变式兄弟',
                  children: siblings.length ? (
                    <span>{siblings.map((v) => qidLink(v.id))}</span>
                  ) : derived.length ? (
                    <span>{derived.map((v) => qidLink(v.id))}</span>
                  ) : (
                    <Typography.Text type="secondary">—</Typography.Text>
                  ),
                },
                {
                  key: 'mates',
                  label: '同类题',
                  children: mates.length ? (
                    <span>
                      {mates.slice(0, 4).map((x) => qidLink(x))}
                      {mates.length > 4 ? (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          等 {mates.length} 道
                        </Typography.Text>
                      ) : null}
                    </span>
                  ) : (
                    <Typography.Text type="secondary">—</Typography.Text>
                  ),
                },
                {
                  key: 'id',
                  label: '题号',
                  children: (
                    <span
                      style={{ fontFamily: 'monospace' }}
                      title="库内 id —— 🔴 不是卷面题号：题号与分值属于载体（卷/册）位置，不进 question"
                    >
                      {q.id}
                    </span>
                  ),
                },
                {
                  key: 'matchKey',
                  label: '排重键',
                  children: (
                    <Typography.Text
                      type="secondary"
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                      title="题面归一化后的指纹：认卷撞库与册内查重都吃它"
                    >
                      {q.matchKey}
                    </Typography.Text>
                  ),
                },
                {
                  key: 'createdAt',
                  label: '入库',
                  children: <Typography.Text type="secondary">{q.createdAt}</Typography.Text>,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </PageFrame>
  )
}
