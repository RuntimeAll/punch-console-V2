import { useMemo, useState } from 'react'
import { Alert, Button, Card, Form, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { CauseDeposit, ErrorCause } from '@/mock'
import { causeDeposits } from '@/mock'
import { depositKey, sortDeposits, studentOptions } from './context'
import { DepositDrawer } from './DepositDrawer'

/**
 * 页签①（默认）：批改沉淀。
 * 归属：维护组「错因管理」自用。
 *
 * 🔴 走查判词原话：**学生批改后的沉淀 = 精华**。分数是一次性的，
 *   留得下来的是「这孩子在哪类错误上反复栽跟头」。所以这张表是本页的主角，
 *   错因库那张表只是它的口径来源。
 * 🔴 铁律③：每行自带轨名，汇总只做**计数**。不许出现「该错因正确率」这类
 *   跨轨算出来的数——两条轨的题量、难度、天数都不一样，拉平算就是造假。
 * 🔴 批改原话（note）不截断：那句话本身就是价值，被「…」吃掉这张表就白做了。
 */

const ALL = ''

export function DepositTab({
  causes,
  onJumpToCause,
}: {
  causes: ErrorCause[]
  /**
   * 🔴 判词⑤ 溯源链第一跳：沉淀 → 错因。点错因 Tag 切到错因库页签并高亮那条，
   * 从那儿再点「挂靠考点」就上到知识图谱。三跳连起来才是完整的「向上溯源」。
   */
  onJumpToCause: (causeId: string) => void
}) {
  const [causeId, setCauseId] = useState(ALL)
  const [student, setStudent] = useState(ALL)
  const [openKey, setOpenKey] = useState('')

  const nameOf = useMemo(() => Object.fromEntries(causes.map((c) => [c.id, c.name])), [causes])

  const rows = useMemo(() => {
    const hit = causeDeposits.filter((d) => {
      if (causeId && d.causeId !== causeId) return false
      if (student && d.student !== student) return false
      return true
    })
    return sortDeposits(hit)
  }, [causeId, student])

  /** 🔴 只计数：命中集合里每条错因各几条，没有率、没有趋势 */
  const tally = useMemo(() => {
    const acc: Record<string, number> = {}
    for (const d of rows) acc[d.causeId] = (acc[d.causeId] ?? 0) + 1
    return Object.entries(acc).sort((a, b) => b[1] - a[1])
  }, [rows])

  const current = rows.find((d) => depositKey(d) === openKey) ?? null

  const columns: ColumnsType<CauseDeposit> = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 104 },
    { title: '学员', dataIndex: 'student', key: 'student', width: 78 },
    {
      // 🔴 轨名是这张表的命根子：没有它，两条轨的沉淀就被拉平成一堆
      title: '轨',
      dataIndex: 'track',
      key: 'track',
      width: 148,
      render: (t: string) => (
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {t}
        </Typography.Text>
      ),
    },
    {
      title: '天',
      dataIndex: 'dayInTrack',
      key: 'dayInTrack',
      width: 66,
      render: (n: number) => `第 ${n} 天`,
    },
    { title: '题号', dataIndex: 'qno', key: 'qno', width: 66, render: (n: number) => `第 ${n} 题` },
    {
      // 🔴 Tag 点击 = 切到错因库并高亮这条（溯源第一跳）；点行的其它地方仍是开判定上下文抽屉。
      //   两个动作长在同一行里，所以 Tag 的 onClick 必须 stopPropagation，不然一点两开。
      title: '错因',
      dataIndex: 'causeId',
      key: 'causeId',
      width: 106,
      render: (id: string) => (
        <Tag
          title={`去错因库看「${nameOf[id] ?? id}」的判定口径与挂靠考点（再往上就是知识图谱）`}
          onClick={(e) => {
            e.stopPropagation()
            onJumpToCause(id)
          }}
          style={{ marginInlineEnd: 0, cursor: 'pointer' }}
        >
          <span style={{ color: '#1677ff' }}>{nameOf[id] ?? id}</span>
        </Tag>
      ),
    },
    {
      title: '批改原话',
      dataIndex: 'note',
      key: 'note',
      // 🔴 不给 ellipsis：这一列就是精华，宁可折行
      render: (s: string) => <Typography.Text style={{ fontSize: 13, lineHeight: 1.8 }}>{s}</Typography.Text>,
    },
  ]

  return (
    <div>
      {/* 筛选：错因 + 学员两个口子，够用 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Form layout="inline" style={{ rowGap: 8 }}>
          <Form.Item label="错因">
            <Select
              value={causeId}
              onChange={setCauseId}
              style={{ width: 190 }}
              options={[{ value: ALL, label: '全部错因' }, ...causes.map((c) => ({ value: c.id, label: c.name }))]}
            />
          </Form.Item>
          <Form.Item label="学员">
            <Select
              value={student}
              onChange={setStudent}
              style={{ width: 150 }}
              options={[
                { value: ALL, label: '全部学员' },
                ...studentOptions().map((s) => ({ value: s, label: s })),
              ]}
            />
          </Form.Item>
          <Form.Item>
            <Button
              onClick={() => {
                setCauseId(ALL)
                setStudent(ALL)
              }}
            >
              重置
            </Button>
          </Form.Item>
        </Form>

        <Space size={6} wrap style={{ marginTop: 10 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            命中 {rows.length} / 共 {causeDeposits.length} 条 —— 按错因计数：
          </Typography.Text>
          {tally.length === 0 ? (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              无
            </Typography.Text>
          ) : (
            tally.map(([id, n]) => (
              <Tag key={id} style={{ marginInlineEnd: 0 }}>
                {nameOf[id] ?? id} {n}
              </Tag>
            ))
          )}
        </Space>
      </Card>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="这里只计数，不算率"
        description="学情按轨分账：两条轨的题量、难度、天数都不一样，把沉淀拉平算「该错因正确率」或画一条跨轨趋势线就是造假。要看某个学员的走势，点行进抽屉再去学员页的轨内看。"
      />

      <Table<CauseDeposit>
        rowKey={depositKey}
        size="small"
        columns={columns}
        dataSource={rows}
        pagination={{ pageSize: 10, showSizeChanger: false, showTotal: (t) => `共 ${t} 条`, hideOnSinglePage: false }}
        onRow={(d) => ({
          style: { cursor: 'pointer' },
          onClick: () => setOpenKey(depositKey(d)),
        })}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：点任意一行开判定上下文抽屉（还原回批改现场：哪一批、机器判了什么、当天几分）。
        筛「誊写笔误」那一条（洛天熙 第 1 天 第 6 题）——机器判的是<b>对</b>，照样记了一条沉淀，
        抽屉里写着为什么：按学生自己抄下来的题面核算。
        <b> 溯源三跳</b>：点「错因」列那个蓝色 Tag（不是点整行）→ 切到错因库并高亮那条 →
        再点它的「挂靠考点」→ 落到 /kg 的那片叶。沉淀 → 错因 → 考点，一条链走到底。
      </Typography.Paragraph>

      <DepositDrawer
        open={openKey !== ''}
        onClose={() => setOpenKey('')}
        deposit={current}
        cause={current ? causes.find((c) => c.id === current.causeId) : undefined}
      />
    </div>
  )
}

export default DepositTab
