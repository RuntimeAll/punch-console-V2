import { useMemo, useState } from 'react'
import { Alert, Card, Col, Empty, Input, Row, Segmented, Space, Spin, Statistic, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { KbKgPatterns, KbPatternPending } from '@/kb/types'

/**
 * 「那批考点哪里去了」——讲义题型的下落（用户走查第一问的答案，PRD-007 二轮第 1 件）
 * ═══════════════════════════════════════════════════════════════════════
 * 用户看到 KG 上只有 71 片考点叶，问讲义里那 173 个「题型N」跑哪去了。答案不是"丢了"，
 * 是 **对齐-003 把题型簇这一层撤掉了**：题型标题 = 考点的考法面，并进 `kp.desc`，
 * 不再单独建表（`question_pattern` 173 行已清空，本页会把它的现行行数摆出来自证）。
 *
 * 于是 173 分两路：
 *   · **103 已锚** → 已并进对应叶的 desc（现库 55 片叶带 desc）
 *   · **70 待归位** → 方法/场景/跨叶词，机器锚不到唯一叶，等人点名归哪片叶
 *
 * 🔴 本块的数据来自两个**磁盘正本文件**（不是库）：
 *   工具箱/kg/题型锚定映射.json + 记录/考点定标/待挂题型-浙教七上.md。
 *   两者必须对得上（清单条目集 ≡ 映射里 kp_id 为 null 的键集）——对不上就整块标红报差集。
 *   文件不在（worktree 沙盘）⇒ 如实说哪个文件找不到，**不编计数**。
 */

const pendCols: ColumnsType<KbPatternPending> = [
  { title: '出处', dataIndex: 'key', width: 118, render: (v: string) => <Typography.Text code>{v}</Typography.Text> },
  {
    title: '题型名（讲义原词）',
    dataIndex: '题型名',
    // 🔴 中文列给最小宽度：中文 min-content 宽 = 一个字，auto 布局会把它压成竖条
    render: (v: string) => <span style={{ minWidth: 240, display: 'inline-block' }}>{v}</span>,
  },
  {
    title: '归位',
    dataIndex: 'done',
    width: 96,
    render: (v: boolean | undefined) =>
      v ? <Tag color="green">已归位</Tag> : <Typography.Text type="secondary">待人工</Typography.Text>,
  },
]

export function PatternFate({ data, err }: { data: KbKgPatterns | null; err?: string }) {
  const [seg, setSeg] = useState<'待归位' | '已锚'>('待归位')
  const [kw, setKw] = useState('')

  const pending = useMemo(() => {
    const rows = data?.pending_rows ?? []
    const k = kw.trim()
    return k ? rows.filter((r) => `${r.key}${r.题型名}`.includes(k)) : rows
  }, [data, kw])

  const anchored = useMemo(() => {
    const rows = data?.anchored_by_leaf ?? []
    const k = kw.trim()
    if (!k) return rows
    return rows
      .map((g) => ({ ...g, 题型: g.题型.filter((t) => `${t.key}${t.题型名}`.includes(k) || (g.kp_name ?? '').includes(k)) }))
      .filter((g) => g.题型.length > 0)
  }, [data, kw])

  if (err) {
    return (
      <Card size="small" style={{ marginTop: 12 }} title="题型下落">
        <Alert type="error" showIcon message="题型下落读不出来" description={err} />
      </Card>
    )
  }
  if (!data) {
    return (
      <Card size="small" style={{ marginTop: 12 }} title="题型下落">
        <Spin />
      </Card>
    )
  }

  // 正本文件不在：如实说，不编计数
  if (!data.available) {
    return (
      <Card size="small" style={{ marginTop: 12 }} title="题型下落 · 清单待结构化">
        <Alert
          type="warning"
          showIcon
          message="题型锚定的正本文件读不到，本块只能给库侧口径"
          description={
            <span style={{ fontSize: 13, lineHeight: 1.9 }}>
              {data.reason}
              <br />
              正本位置：<Typography.Text code>{data.source.map}</Typography.Text> 与{' '}
              <Typography.Text code>{data.source.list}</Typography.Text>。
              <br />
              库侧现状（这几个数是实查的）：现行考点叶 <b>{data.leaf_total}</b> 片、带考法描述{' '}
              <b>{data.leaf_with_desc}</b> 片、question_pattern 表 <b>{data.pattern_rows}</b> 行
              （对齐-003 后应为 0）。
            </span>
          }
        />
      </Card>
    )
  }

  const 不一致 = data.一致 === false

  return (
    <Card
      size="small"
      style={{ marginTop: 12 }}
      title="题型下落 —— 讲义那 173 个「题型N」去哪了"
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          口径正本：{data.对齐}
        </Typography.Text>
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="不是丢了，是并进考点了"
        description={
          <span style={{ fontSize: 13, lineHeight: 1.9 }}>
            对齐-003 撤掉了「题型簇」这一实体层：讲义里的「题型N」本质是<b>考点的考法面</b>，
            处理方式 = <b>并进对应考点叶的考法描述（kp.desc）</b>，不再单独建表。
            自证：<Typography.Text code>question_pattern</Typography.Text> 表现有{' '}
            <b style={{ color: data.pattern_rows === 0 ? undefined : '#cf1322' }}>{data.pattern_rows}</b> 行
            （对齐-003 后应为 0），而 <b>{data.leaf_with_desc}</b> 片叶带上了考法描述。
            剩下 <b>{data.pending_total}</b> 个是方法词 / 场景词 / 跨叶词，机器锚不到唯一叶——
            按 <b>对齐-002</b>（别名层只做正向产线词、不为历史数据铸兼容名），这批<b>不铸别名硬凑</b>，
            等人点名「这条归哪片叶」。
          </span>
        }
      />

      {不一致 ? (
        // 🔴 两个正本文件对不上 = 坏账，摆差集不挑一个显示
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message="两个正本文件对不上（映射 JSON 与人工归位清单）"
          description={
            <span style={{ fontSize: 13, lineHeight: 1.9 }}>
              只在映射里、清单没收：{data.只在json?.join('、') || '（无）'}
              <br />
              只在清单里、映射没有：{data.只在清单?.join('、') || '（无）'}
              <br />
              两边同步了这条告警才会消失（映射 = <Typography.Text code>{data.source.map}</Typography.Text>，
              清单 = <Typography.Text code>{data.source.list}</Typography.Text>）。
            </span>
          }
        />
      ) : null}

      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col flex="1 1 200px">
          <Card size="small">
            <Statistic title="讲义题型总数" value={data.total ?? 0} suffix="个" valueStyle={{ fontSize: 22 }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              浙教七上预习讲义实抽（映射正本 {data.source.map.split('/').pop()}）
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 200px">
          <Card size="small">
            <Statistic
              title="已锚进考点"
              value={data.anchored_total ?? 0}
              suffix={`/ 落在 ${data.leaf_covered ?? 0} 片叶`}
              valueStyle={{ fontSize: 22 }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              考法已并进这些叶的 desc（{data.leaf_with_desc}/{data.leaf_total} 片叶带描述）
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 200px">
          <Card size="small">
            <Statistic
              title="待人工归位"
              value={data.pending_total ?? 0}
              suffix="个"
              valueStyle={{ fontSize: 22, color: (data.pending_total ?? 0) > 0 ? '#d46b08' : undefined }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              已勾办 {data.checklist_done ?? 0} / {data.checklist_total ?? 0} —— 用户闸，agent 不自作主张
            </Typography.Text>
          </Card>
        </Col>
        <Col flex="1 1 200px">
          <Card size="small">
            <Statistic
              title="两份正本一致"
              value={data.一致 === null ? '清单缺失' : 不一致 ? '不一致' : '一致'}
              valueStyle={{ fontSize: 22, color: 不一致 ? '#cf1322' : undefined }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              清单条目集 ≡ 映射里没锚到叶的键集
            </Typography.Text>
          </Card>
        </Col>
      </Row>

      <Space size={10} wrap style={{ marginBottom: 10 }}>
        <Segmented
          size="small"
          value={seg}
          onChange={(v) => setSeg(v as '待归位' | '已锚')}
          options={[
            { label: `待归位 ${data.pending_total ?? 0}`, value: '待归位' },
            { label: `已锚 ${data.anchored_total ?? 0}`, value: '已锚' },
          ]}
        />
        <Input.Search
          allowClear
          size="small"
          placeholder="搜题型名 / 出处 / 考点名"
          value={kw}
          onChange={(e) => setKw(e.target.value)}
          style={{ width: 220 }}
        />
        {seg === '待归位' && data.pending_by_lecture?.length ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            按讲次：{data.pending_by_lecture.map((l) => `讲${l.讲}×${l.count}`).join(' ')}
          </Typography.Text>
        ) : null}
      </Space>

      {seg === '待归位' ? (
        <>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 8px' }}>
            归位方式 = 人点名「这条归哪片叶」，agent 把它并进该叶的 desc（走 KG维护 skill）。
            清单正本 <Typography.Text code>{data.source.list}</Typography.Text>，勾一条办一条；本页只读不改。
          </Typography.Paragraph>
          <Table<KbPatternPending>
            rowKey="key"
            size="small"
            columns={pendCols}
            dataSource={pending}
            pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
            locale={{ emptyText: <Empty description="按当前搜索没有待归位题型" /> }}
          />
        </>
      ) : (
        <>
          <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '0 0 8px' }}>
            这些题型已经并进对应叶的考法描述——点左边的树选中那片叶，右栏「考法描述」一栏就是它们的去处。
          </Typography.Paragraph>
          <div style={{ maxHeight: 420, overflow: 'auto' }}>
            {anchored.length ? (
              anchored.map((g) => (
                <div key={g.kp_id} style={{ marginBottom: 8, lineHeight: 1.9 }}>
                  {g.kp_missing ? (
                    <Tag color="red">🔴 叶 {g.kp_id} 不在库</Tag>
                  ) : (
                    <Tag color="green">{g.kp_name}</Tag>
                  )}
                  <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineEnd: 6 }}>
                    吃下 {g.题型.length} 个题型：
                  </Typography.Text>
                  {g.题型.map((t) => (
                    <Tag key={t.key} style={{ marginBottom: 3 }} title={t.key}>
                      {t.题型名}
                    </Tag>
                  ))}
                </div>
              ))
            ) : (
              <Empty description="按当前搜索没有已锚题型" />
            )}
          </div>
        </>
      )}
    </Card>
  )
}

export default PatternFate
