import { Alert, Button, Descriptions, Drawer, Empty, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Batch, ItemVerdict } from '@/mock'
import { stateTagColor, verdictHue } from '@/pages/grading/batch-view'
import { SheetPane } from './SheetPane'
import { photosOfBatch } from './sheet-photos'

/**
 * 批次详情抽屉 —— 一天的账本。
 *
 * 🔴 v2.1 语义：**终审就是这里的一个动作**（state=待终审 时表上方出「终审模式」，
 * 逐题三键 √/×/去掉，底部「确认这批」），不再有独立的「终审台」页面。
 * 🔴 报告属于批次：已确认/已出件的批次在抽屉底部挂报告块，不再有独立的「报告架」。
 *
 * 🔴 左右分栏（用户走查判词「终审下面的原图呢？」+ 二判「把原图丢上来对比就行」）：
 * **左 = 当天卷面照片直显**（sticky，自己滚，点图放大），**右 = 逐题拍板表**（原样不动）。
 * 存疑原因写的是「看不清写的是 2a 还是 －2a」「纸张折角」，不对着原图没法拍板。
 * 不做题位框/联动定位——照片摆上来人眼对题号就够。窄屏（<900px）改上下堆叠。
 */

/** 终审选择：'drop' = 本题作废（不计分）；undefined = 存疑还没拍板 */
export type Selection = '√' | '×' | 'drop' | undefined

export function BatchDrawer({
  open,
  onClose,
  studentCode,
  trackName,
  batch,
  state,
  score,
  selectionOf,
  onJudge,
  onConfirm,
}: {
  open: boolean
  onClose: () => void
  studentCode: string
  trackName: string
  batch: Batch | null
  /** 现态（本地终审确认过就是「已确认」，不是 mock 里的原状态） */
  state: Batch['state']
  /** 现判分（终审改判/作废后实时重算） */
  score: { right: number; total: number } | null
  selectionOf: (qno: number) => Selection
  onJudge: (qno: number, sel: Exclude<Selection, undefined>) => void
  onConfirm: () => void
}) {
  const reviewing = state === '待终审'
  const items = batch?.items ?? []
  const unresolved = items.filter((it) => selectionOf(it.qno) === undefined).length
  const dropped = items.filter((it) => selectionOf(it.qno) === 'drop').length

  const columns: ColumnsType<ItemVerdict> = [
    { title: '题号', dataIndex: 'qno', key: 'qno', width: 72, render: (n: number) => `第 ${n} 题` },
    {
      title: reviewing ? '机器判' : '判定',
      key: 'verdict',
      width: 64,
      align: 'center',
      render: (_, it) => (
        <span style={{ color: verdictHue(it.verdict), fontWeight: 600 }}>{it.verdict}</span>
      ),
    },
    ...(reviewing
      ? ([
          {
            title: '终审',
            key: 'judge',
            width: 148,
            render: (_, it) => {
              const sel = selectionOf(it.qno)
              return (
                <Space.Compact size="small">
                  <Tooltip title="判对">
                    <Button type={sel === '√' ? 'primary' : 'default'} onClick={() => onJudge(it.qno, '√')}>
                      √
                    </Button>
                  </Tooltip>
                  <Tooltip title="判错">
                    <Button type={sel === '×' ? 'primary' : 'default'} onClick={() => onJudge(it.qno, '×')}>
                      ×
                    </Button>
                  </Tooltip>
                  <Tooltip title="本题作废，不计入分母">
                    <Button type={sel === 'drop' ? 'primary' : 'default'} onClick={() => onJudge(it.qno, 'drop')}>
                      去掉
                    </Button>
                  </Tooltip>
                </Space.Compact>
              )
            },
          },
        ] as ColumnsType<ItemVerdict>)
      : []),
    { title: '考点', dataIndex: 'kp', key: 'kp', width: 150, render: (k?: string) => k ?? '—' },
    {
      title: reviewing ? '存疑原因 / 错因' : '错因备注',
      dataIndex: 'note',
      key: 'note',
      render: (n?: string) => (n ? n : <Typography.Text type="secondary">—</Typography.Text>),
    },
  ]

  return (
    <Drawer
      open={open}
      onClose={onClose}
      /* 🔴 加宽到两栏放得下：左原图（A4 竖版，太窄看不清）+ 右逐题表 */
      width="min(1280px, 96vw)"
      title={
        batch ? (
          <Space size={8} wrap>
            <span>{studentCode}</span>
            <Typography.Text type="secondary" style={{ fontSize: 13, fontWeight: 400 }}>
              {trackName} · 第 {batch.dayInTrack} 天
            </Typography.Text>
            <Tag color={stateTagColor(state)} style={{ marginInlineEnd: 0 }}>
              {state}
            </Tag>
          </Space>
        ) : null
      }
      footer={
        reviewing ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              现判 {score ? `${score.right}/${score.total}` : '—'}
              {dropped > 0 ? ` ｜ 作废 ${dropped} 题` : ''}
              {unresolved > 0 ? ` ｜ 还有 ${unresolved} 题存疑没拍板` : ' ｜ 存疑已清'}
            </Typography.Text>
            <Tooltip title={unresolved > 0 ? `还有 ${unresolved} 题存疑没拍板` : ''}>
              <Button type="primary" disabled={unresolved > 0} onClick={onConfirm}>
                确认这批
              </Button>
            </Tooltip>
          </div>
        ) : null
      }
    >
      {!batch ? null : batch.items.length === 0 ? (
        <Empty
          description={
            <Space direction="vertical" size={2}>
              {/* 九态里没出分的格子（收件中/待认卷/待人工认卷/批改中/故障）都落这儿，
                  所以第一句直接报状态，第二句用批次自带的 note（机器原话） */}
              <span>这一天还没有判定结果：{state}</span>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {batch.note ?? '收卷 → 认卷 → 整页直读 → 落库都是 agent 侧动作，这里只看结果。'}
              </Typography.Text>
            </Space>
          }
        />
      ) : (
        /* ── 两栏：左卷面原图（sticky 独立滚）｜ 右逐题拍板表（原样）── */
        <div className="gs-split">
          <div className="gs-split-left">
            <SheetPane photos={photosOfBatch(batch.dayInTrack)} dateLabel={batch.date} />
          </div>

          <div className="gs-split-right">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Descriptions
                size="small"
                column={3}
                colon={false}
                items={[
                  { key: 'date', label: '日期', children: batch.date },
                  { key: 'score', label: '现判', children: score ? `${score.right}/${score.total}` : '—' },
                  {
                    key: 'doubt',
                    label: '存疑',
                    children: unresolved > 0 ? <Tag color="red">{unresolved} 题</Tag> : '—',
                  },
                ]}
              />

              {reviewing ? (
                <Alert
                  type="warning"
                  showIcon
                  message="终审模式"
                  description="逐题拍板：√ 判对 / × 判错 / 去掉（本题作废，不计入分母）。存疑（?）全部拍完才能确认这批。对着左边的卷面原图拍。"
                />
              ) : null}

              <Table<ItemVerdict>
                rowKey="qno"
                size="small"
                columns={columns}
                dataSource={batch.items}
                pagination={false}
                rowClassName={(it) => (selectionOf(it.qno) === 'drop' ? 'gs-row-dropped' : '')}
              />

              {/* 🔴 报告属于批次：出件后挂在这天底下，没有独立「报告架」 */}
              {state === '已出件' || state === '已确认' || state === '待出件' ? (
                <div className="gs-report">
                  <Space size={8}>
                    <Typography.Text strong style={{ fontSize: 13 }}>
                      学情报告 · 本批次
                    </Typography.Text>
                    <Tag style={{ marginInlineEnd: 0 }}>{state === '已出件' ? '已生成' : '待出件生成'}</Tag>
                  </Space>
                  <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '4px 0 0' }}>
                    {state === '已出件'
                      ? '报告挂在这一天的批次下（考得怎么样 + 错在哪），由 agent 出件时生成。'
                      : '这批已确认，出件后报告会挂在这里。'}
                  </Typography.Paragraph>
                  <div className="gs-skeleton-line" style={{ width: '78%' }} />
                  <div className="gs-skeleton-line" style={{ width: '92%' }} />
                  <div className="gs-skeleton-line" style={{ width: '54%' }} />
                  <Button size="small" disabled style={{ marginTop: 10 }}>
                    打开报告（原型占位）
                  </Button>
                </div>
              ) : null}
            </Space>
          </div>
        </div>
      )}
    </Drawer>
  )
}

export default BatchDrawer
