import { useMemo } from 'react'
import { Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import type { QuestionPattern } from '@/mock'
import { questionPatterns } from '@/mock'
// 🔴 溯源换算只有一份实现（kg 组的 trace.ts / KpTraceLink），本页单向依赖
import { KpTraceLinks } from '@/pages/kg/KpTraceLink'
import { kpNamesOfIds, questionsOfPatternRows, solutionsForPattern } from './view'

/**
 * 段①：题型目录（question_pattern，数据结构.md §2.1④，老区 326 条精华位）。
 * 归属：维护组「考察模型」自用。
 *
 * 🔴 它是干嘛的：「这类题**长什么样**」—— 识别与归类用。题上挂 patternId，
 *   题库详情页那行「题型目录」显示的就是这里的 name。
 * 🔴 与另两段的分工：考察模型=怎么造（DSL 配方）、解题模型=怎么解（举一反三地基）。
 *   长什么样 ≠ 怎么造 ≠ 怎么解，三张表各挂各的考点，别当成一个东西的三个视图。
 * 🔴 kpIds **多值**（2026-08-17 用户拍板原话：「模型是可能考多个考点的，不能说是一个」），
 *   所以这一列一行可能好几个考点，全部点得动 → /kg?kp=&lt;树key&gt;。
 * 🔴 挂题数**现算**（questionsOfPattern），不落计数字段——老区计数 143 个里 74 个是错的。
 *   0 道要写成「目录里有、库里还没题」，别渲成空白让人以为数据缺了。
 */
export function PatternTab() {
  const navigate = useNavigate()

  /** 段头盘点：一共挂了多少道题、几条题型库里一道题都没有 */
  const tally = useMemo(() => {
    let hung = 0
    let empty = 0
    for (const p of questionPatterns) {
      const n = questionsOfPatternRows(p.id).length
      hung += n
      if (n === 0) empty += 1
    }
    return { hung, empty }
  }, [])

  const columns: ColumnsType<QuestionPattern> = [
    {
      title: '题型名',
      key: 'name',
      width: 230,
      render: (_, p) => (
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            {p.name}
          </Typography.Text>
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
              {p.id}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      // 🔴 不给 ellipsis：识别特征就是这条题型的全部价值，折叠起来等于没写
      title: '长什么样（识别特征）',
      dataIndex: 'desc',
      key: 'desc',
      render: (s: string) => <Typography.Text style={{ fontSize: 13, lineHeight: 1.8 }}>{s}</Typography.Text>,
    },
    {
      // 🔴 判词⑤：题型 → 知识图谱的溯源链就在这一列（kpIds 多值，逐个点得动）
      title: '挂靠考点（多值）',
      key: 'kpIds',
      width: 230,
      render: (_, p) => (
        <KpTraceLinks
          names={kpNamesOfIds(p.kpIds)}
          empty={
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12 }}
              title="kpIds 是空数组：这条题型说不出自己归到哪片叶，溯源到这儿就断了"
            >
              未挂考点（溯源断点）
            </Typography.Text>
          }
        />
      ),
    },
    {
      title: '挂题数',
      key: 'count',
      width: 116,
      align: 'right',
      render: (_, p) => {
        const n = questionsOfPatternRows(p.id).length
        return (
          <div>
            <Typography.Text style={{ fontSize: 13 }}>{n} 道</Typography.Text>
            {n === 0 ? (
              <div>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  目录里有、库里还没题
                </Typography.Text>
              </div>
            ) : null}
          </div>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (s: QuestionPattern['status']) => (
        <Tag color={s === '停用' ? 'orange' : undefined} style={{ marginInlineEnd: 0 }}>
          {s}
        </Tag>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} size={6} wrap>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          它是干嘛的：这类题<b>长什么样</b> —— 识别与归类用，题上挂 patternId。
        </Typography.Text>
        <Tag style={{ marginInlineEnd: 0 }}>题型 {questionPatterns.length} 条</Tag>
        <Tag style={{ marginInlineEnd: 0 }}>共挂 {tally.hung} 道题</Tag>
        {tally.empty > 0 ? (
          <Tooltip title="题型立了但库里一道题都没挂上——不是坏数据，是「目录先行、题后补」的正常中间态，摆出来才知道要补">
            <Tag color="orange" style={{ marginInlineEnd: 0 }}>
              {tally.empty} 条还没题
            </Tag>
          </Tooltip>
        ) : null}
      </Space>

      <Table<QuestionPattern>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={questionPatterns}
        pagination={false}
        expandable={{
          // 展开 = 这条题型挂着哪几道题 + 共考点的解法参考（「长什么样」→「怎么解」一跳）
          expandedRowRender: (p) => {
            const rows = questionsOfPatternRows(p.id)
            const solutions = solutionsForPattern(p.kpIds)
            return (
              <div style={{ paddingInlineStart: 8 }}>
                <Typography.Text strong style={{ fontSize: 13 }}>
                  挂在这条题型下的题（{rows.length} 道）
                </Typography.Text>
                {rows.length === 0 ? (
                  <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '4px 0 8px' }}>
                    一道都没有 —— 题型目录先立着，等录入线把这类题收进来再挂。
                  </Typography.Paragraph>
                ) : (
                  <div style={{ margin: '4px 0 10px' }}>
                    {rows.map(({ id, summary }) => (
                      <div key={id} style={{ marginBottom: 2 }}>
                        {summary === undefined ? (
                          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                            <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{id}</span>
                            题库里已经找不到这道题（被删或没录）
                          </Typography.Text>
                        ) : (
                          <Typography.Link onClick={() => navigate(`/questions/${id}`)}>
                            <span style={{ fontFamily: 'monospace', marginRight: 8 }}>{id}</span>
                            <Typography.Text style={{ fontSize: 13 }}>{summary}</Typography.Text>
                          </Typography.Link>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <Typography.Text strong style={{ fontSize: 13 }}>
                  解法参考（与它共考点的解题模型）
                </Typography.Text>
                <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 4px' }}>
                  🔴 这是<b>现算的弱关联</b>：题型与解题模型各自挂考点，共了考点才推得出「这类题大概用哪个模型解」，
                  不是数据结构里的外键。要看模型正文去「解题模型」那一段。
                </Typography.Paragraph>
                {solutions.length === 0 ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    暂无 —— 这几片考点叶上还没立解题模型。
                  </Typography.Text>
                ) : (
                  <span>
                    {solutions.map((m) => (
                      <Tag key={m.id} style={{ marginInlineEnd: 6 }}>
                        {m.name}
                        <Typography.Text type="secondary" style={{ fontSize: 12, marginLeft: 6 }}>
                          阶 {m.tier} · 频 {m.freq}
                        </Typography.Text>
                      </Tag>
                    ))}
                  </span>
                )}
              </div>
            )
          },
        }}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：点行首箭头展开，看这条题型挂着哪几道题（题号点得动，落到题库详情页，那页的「题型目录」行写的就是这条题型，一来一回对得上）。
        三处值得看：「简便计算·拆数凑整型」下面挂着 q-4002 与它的变式 q-4014（同题型 + 母子血缘，一眼看出这类题在怎么繁衍）；
        「平行与垂直识图型」挂的是 q-4013 那道<b>图选项</b>题；「试商调商型」写着「目录里有、库里还没题」——
        题型先立着等题补进来，是正常中间态不是坏数据。挂靠考点是多值，一行里点哪个都能落到 /kg 那片叶。
      </Typography.Paragraph>
    </div>
  )
}

export default PatternTab
