import { Alert, Card, Descriptions, Empty, Space, Spin, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { KbInline } from '@/kb/KbBlocks'
import type { KbKpDetail } from '@/kb/types'

/**
 * 右栏：选中节点的详情（真库版，数据全来自 GET /api/kb/kp/:id）。
 * 归属：真库组「知识图谱」自用。
 *
 * 三种态各有各的说法，别用一套模板糊过去（照搬 mock 页 LeafDetail 的分法）：
 * ① 没选中      → 说清这页回答哪三个维护问题
 * ② 选中的是枝  → 下辖规模 + 挂题 + 零挂载叶清单（缺口）
 * ③ 选中的是叶  → 考点档案（含对齐-003 后归到 kp 自己身上的 重难点/频率/难度/考法描述）
 *                 + 家当（题 / 考察模型 / 解题模型）+ 直挂题样例
 *
 * 🔴 与 mock 页最大的差别：**这里一个写按钮都没有**。加别名 / 改名 / 退役 / 建叶 / 改归属
 *   全部走 agent（KG维护 skill → 工具箱/kg/kg_tool.py，kp/kp_alias 的唯一写入通路）。
 *   mock 页那三个「原型演示态」按钮改的是本地 state，在真库页上留着只会骗人。
 */

const STATUS_COLOR: Record<string, string> = { 现行: 'green', 未铺: 'orange', 退役: 'default' }

export function KpDetail({ id, detail, loading }: { id: string; detail: KbKpDetail | null; loading: boolean }) {
  // ① 没选中
  if (!id) {
    return (
      <Card size="small" title="家底速览">
        <Typography.Paragraph style={{ marginBottom: 8 }}>
          左边点一个节点开始看。这页回答三个维护问题：
        </Typography.Paragraph>
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 2, color: 'rgba(0,0,0,0.65)' }}>
          <li>目录铺到哪儿了 —— 哪一枝还是空壳（kp.status=「未铺」的就是）</li>
          <li>哪片叶子是空的 —— 勾上「只看零挂载考点」，剩下的就是缺口</li>
          <li>词表乱不乱 —— 下面那张别名表：一词多挂、别名断链，两种坏账都摆出来</li>
        </ol>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '10px 0 0' }}>
          🔴 本页<b>只读</b>：建叶子、加别名、改名、改归属、退役，全部走 agent（KG维护 skill）。
        </Typography.Paragraph>
      </Card>
    )
  }
  if (loading || !detail) {
    return (
      <Card size="small">
        <Spin />
      </Card>
    )
  }

  const trail = (
    <span style={{ fontSize: 12, lineHeight: 1.9 }}>
      {detail.path.map((p, i) => (
        <span key={p.id}>
          {i > 0 ? <span style={{ color: 'rgba(0,0,0,0.25)', margin: '0 4px' }}>/</span> : null}
          <Typography.Text type={i === detail.path.length - 1 ? undefined : 'secondary'}>{p.name}</Typography.Text>
        </span>
      ))}
    </span>
  )

  // ② 选中的是枝
  if (!detail.is_leaf) {
    return (
      <Card
        size="small"
        title={
          <Space size={8}>
            <span>{detail.name}</span>
            <Tag style={{ marginInlineEnd: 0 }}>{detail.level}</Tag>
            <Tag color={STATUS_COLOR[detail.status] ?? 'default'} style={{ marginInlineEnd: 0 }}>
              {detail.status}
            </Tag>
          </Space>
        }
        extra={
          detail.q_total > 0 ? (
            <Link to={`/kb/questions?kp=${encodeURIComponent(detail.id)}`}>在题库里看这一枝（{detail.q_total} 题）</Link>
          ) : null
        }
      >
        {detail.status === '未铺' ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="这一枝还没铺"
            description="教材树上只有个名字，底下的单元 / 小节 / 考点一个都没建。铺目录是 agent 侧动作（KG维护 skill 从教材目录抽结构再灌树），本页只如实标出来——空目录假装铺好了是事故。"
          />
        ) : null}

        <Descriptions
          size="small"
          column={1}
          styles={{ label: { width: 84 } }}
          items={[
            { key: 'path', label: '路径', children: trail },
            {
              key: 'scale',
              label: '下辖',
              children: `${detail.children.length} 个直属子节点 · 子树共 ${detail.leaf_total} 片考点叶`,
            },
            {
              key: 'mount',
              label: '挂题',
              children: `${detail.q_total} 道题，落在 ${detail.leaf_total - detail.zero_mount_leaves.length} 片叶上`,
            },
            { key: 'id', label: 'kp id', children: <Typography.Text code>{detail.id}</Typography.Text> },
          ]}
        />

        {detail.children.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <Typography.Text strong style={{ fontSize: 13 }}>
              直属子节点
            </Typography.Text>
            <div style={{ marginTop: 6 }}>
              {detail.children.map((c) => (
                <Tag key={c.id} style={{ marginBottom: 4 }}>
                  {c.name}
                  <span style={{ color: 'rgba(0,0,0,0.45)', marginInlineStart: 6 }}>{c.q_count} 题</span>
                </Tag>
              ))}
            </div>
          </div>
        ) : null}

        {detail.zero_mount_leaves.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <Typography.Text strong style={{ fontSize: 13 }}>
              零挂载的叶子（{detail.zero_mount_leaves.length} / {detail.leaf_total}）
            </Typography.Text>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 6px' }}>
              目录有、题没有。这是维护时真正要盯的缺口，不是「数据没录完」。
            </Typography.Paragraph>
            <div>
              {detail.zero_mount_leaves.map((leaf) => (
                <Tag key={leaf.id} style={{ marginBottom: 4, color: 'rgba(0,0,0,0.55)' }}>
                  {leaf.name}
                </Tag>
              ))}
            </div>
          </div>
        ) : null}
      </Card>
    )
  }

  // ③ 选中的是考点叶
  return (
    <Card
      size="small"
      title={
        <Space size={8} wrap>
          <span>{detail.name}</span>
          <Tag style={{ marginInlineEnd: 0 }}>考点叶</Tag>
          <Tag color={STATUS_COLOR[detail.status] ?? 'default'} style={{ marginInlineEnd: 0 }}>
            {detail.status}
          </Tag>
        </Space>
      }
      extra={
        detail.q_count > 0 ? (
          <Link to={`/kb/questions?kp=${encodeURIComponent(detail.id)}`}>在题库里看（{detail.q_count} 题）</Link>
        ) : null
      }
    >
      <Descriptions
        size="small"
        column={1}
        styles={{ label: { width: 84 } }}
        items={[
          { key: 'path', label: '所属路径', children: trail },
          {
            key: 'alias',
            label: '别名',
            children: detail.aliases.length ? (
              <span>
                {detail.aliases.map((a) => (
                  <Tag key={a.alias} style={{ marginInlineEnd: 4, marginBottom: 4 }}>
                    {a.alias}
                    {a.alias_kind ? (
                      <span style={{ color: 'rgba(0,0,0,0.45)', marginInlineStart: 4 }}>{a.alias_kind}</span>
                    ) : null}
                  </Tag>
                ))}
              </span>
            ) : (
              <Typography.Text type="secondary">暂无别名</Typography.Text>
            ),
          },
          {
            // 🔴 对齐-001：考点叶自己携带教研属性（与题的属性同构，是另一个维度）。
            //   三列逐格摆——空就明写「未定标」，不整格省掉：省掉会让人以为这叶没有这个维度。
            key: 'exam',
            label: '教研属性',
            children: (
              <Space size={10} wrap style={{ fontSize: 12.5 }}>
                <span>
                  <Typography.Text type="secondary" style={{ marginInlineEnd: 4 }}>
                    重难点
                  </Typography.Text>
                  {detail.emphasis ? (
                    <Tag color="volcano" style={{ marginInlineEnd: 0 }}>
                      {detail.emphasis}
                    </Tag>
                  ) : (
                    <Typography.Text type="secondary">未定标</Typography.Text>
                  )}
                </span>
                <span>
                  <Typography.Text type="secondary" style={{ marginInlineEnd: 4 }}>
                    频率
                  </Typography.Text>
                  {detail.freq ? (
                    <Tag color="geekblue" style={{ marginInlineEnd: 0 }}>
                      {detail.freq}
                    </Tag>
                  ) : (
                    <Typography.Text type="secondary">未定标</Typography.Text>
                  )}
                </span>
                <span>
                  <Typography.Text type="secondary" style={{ marginInlineEnd: 4 }}>
                    难度
                  </Typography.Text>
                  {detail.diff_label ? (
                    <Tag style={{ marginInlineEnd: 0 }}>{detail.diff_label}</Tag>
                  ) : (
                    <Typography.Text type="secondary">未定标</Typography.Text>
                  )}
                </span>
              </Space>
            ),
          },
          {
            key: 'desc',
            label: '考法描述',
            children: detail.desc ? (
              <div>
                <Typography.Text style={{ fontSize: 13 }}>{detail.desc}</Typography.Text>
                <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '4px 0 0' }}>
                  🔴 这一格就是<b>讲义「题型N」的去处</b>：对齐-003 撤掉题型簇实体层后，
                  考法面并进本列（题型实体表 question_pattern 已清零）。全账见下方「题型下落」。
                </Typography.Paragraph>
              </div>
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                这片叶还没写考法描述（对齐-003 起「这类题长什么样」就归这一列；
                若它对应的讲义题型在「待归位」那 70 个里，归位后才会落到这儿）
              </Typography.Text>
            ),
          },
          {
            key: 'assets',
            label: '家当',
            children: (
              <Space size={6} wrap>
                <Typography.Text style={{ fontSize: 13 }}>
                  题 {detail.q_count} · 考察模型 {detail.exam_models.length} · 解题模型 {detail.solution_models.length}
                </Typography.Text>
                {detail.q_count === 0 ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    （零挂载：目录有、题没有）
                  </Typography.Text>
                ) : null}
              </Space>
            ),
          },
          { key: 'id', label: 'kp id', children: <Typography.Text code>{detail.id}</Typography.Text> },
        ]}
      />

      {detail.exam_models.length || detail.solution_models.length ? (
        <div style={{ marginTop: 12 }}>
          <Typography.Text strong style={{ fontSize: 13 }}>
            挂在这片叶上的模型
          </Typography.Text>
          <div style={{ marginTop: 6 }}>
            {detail.exam_models.map((m) => (
              <Tag key={m.id} color="blue" style={{ marginBottom: 4 }}>
                怎么造 · {m.name}
              </Tag>
            ))}
            {detail.solution_models.map((m) => (
              <Tag key={m.id} color="purple" style={{ marginBottom: 4 }}>
                怎么解 · {m.name}
                {m.tier != null ? (
                  <span style={{ marginInlineStart: 4, fontFamily: 'monospace' }}>
                    阶{m.tier}/频{m.freq}
                  </span>
                ) : null}
              </Tag>
            ))}
          </div>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '6px 0 0' }}>
            全表在 <Link to="/kb/models">维护 · 考察模型 · 真库</Link>。
          </Typography.Paragraph>
        </div>
      ) : null}

      <div style={{ marginTop: 12 }}>
        <Typography.Text strong style={{ fontSize: 13 }}>
          直挂的题（最多列 12 道）
        </Typography.Text>
        {detail.questions.length ? (
          <ul style={{ margin: '6px 0 0', paddingInlineStart: 18, lineHeight: 1.9 }}>
            {detail.questions.map((q) => (
              <li key={q.id}>
                {q.is_primary ? <Tag color="purple">主</Tag> : <Tag>副</Tag>}
                <span style={{ color: 'rgba(0,0,0,0.75)' }}>
                  <KbInline md={q.stem} />
                </span>
                <span style={{ color: 'rgba(0,0,0,0.45)', marginInlineStart: 6 }}>
                  {q.qtype_label ?? '—'} · {q.diff_label ?? '—'} · {q.status}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                零挂载：这片叶目前一道题都没挂
              </Typography.Text>
            }
          />
        )}
      </div>
    </Card>
  )
}

export default KpDetail
