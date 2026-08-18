import { Drawer, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { StateMeta } from '@/mock'
import { STATE_MACHINE } from '@/mock'
import { stateHue } from '@/pages/grading/batch-view'

/**
 * 状态机说明抽屉 —— 🔴 判词①「状态外置明确」的落点：
 * 九格状态机**原样**摆出来（状态 / 谁推进 / 停留原因 / 出口），这就是自解释文档，
 * 不再靠口头解释「待批到底是什么意思」。
 *
 * 🔴 本抽屉一个字都不许自己写状态说明：全部渲 STATE_MACHINE 那九行。
 *   要改口径去 mock/types.ts 改正本，页面跟着变。
 */
export function StateMachineDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const columns: ColumnsType<StateMeta> = [
    {
      title: '状态',
      dataIndex: 'state',
      width: 108,
      render: (s: StateMeta['state']) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap' }}>
          <span className="gq-state-dot" style={{ background: stateHue(s) }} />
          {s}
        </span>
      ),
    },
    {
      title: '谁推进',
      dataIndex: 'actor',
      width: 76,
      render: (a: StateMeta['actor']) =>
        a === '人' ? (
          <Tag color="orange" style={{ marginInlineEnd: 0 }}>
            人
          </Tag>
        ) : a === '终态' ? (
          <Tag color="green" style={{ marginInlineEnd: 0 }}>
            终态
          </Tag>
        ) : (
          <Tag style={{ marginInlineEnd: 0 }}>系统</Tag>
        ),
    },
    { title: '停留原因', dataIndex: 'reason' },
    {
      title: '出口',
      dataIndex: 'exits',
      width: 190,
      render: (exits: string[]) =>
        exits.length === 0 ? (
          <Typography.Text type="secondary">到头了</Typography.Text>
        ) : (
          <Typography.Text style={{ fontSize: 12 }}>{exits.join('｜')}</Typography.Text>
        ),
    },
  ]

  return (
    <Drawer open={open} onClose={onClose} width={620} title="状态机说明 · 九格">
      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        一条卷子从收件到出件只走这九格，分格的唯一准绳是<b>这一格卡在谁手上</b>。
        队列页的状态列、计数条、筛子全渲这张表，没有第二份口径。
      </Typography.Paragraph>

      <Table<StateMeta>
        rowKey="state"
        size="small"
        columns={columns}
        dataSource={STATE_MACHINE}
        pagination={false}
        rowClassName={(m) => (m.actor === '人' ? 'gq-row-human' : '')}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 12, marginBottom: 0 }}>
        🔴 只有三格是<b>人的活</b>（待人工认卷 / 待终审 / 故障，表里左侧描橙的行）——
        「只看要我动手的」开关筛的就是这三格。其余六格是机器在飞，摆出来是让你看见链跑到哪了，不是让你点。
        <br />
        🔴 故障<b>就地挂起不自动重试</b>：机器不敢自己重来（怕把半张卷判两遍），
        非要人看一眼原话再点 retry，retry 后回原状态。
      </Typography.Paragraph>
    </Drawer>
  )
}

export default StateMachineDrawer
