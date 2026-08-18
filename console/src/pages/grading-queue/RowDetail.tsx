import { Button, Radio, Space, Typography } from 'antd'
import type { QueueRow } from '@/mock'

/** 本地动作留下的一行时间线（mock：刷新即还原） */
export interface TimelineEntry {
  /** 只盖 mock 基准钟点，走查时数字恒定 */
  at: string
  text: string
}

/**
 * 展开区 = 这一行「为什么停在这儿、下一步往哪走、机器原话是什么」。
 *
 * 🔴 判词①「状态外置明确」：停留原因与出口不是注释，是数据（STATE_MACHINE 那一行），
 *   队列里每一行都能就地展开自解释，不用回头翻文档。
 * 🔴 待人工认卷的行把候选卷摆在这里二选一：编排器双命中不敢定，人一点就定。
 * 🔴 note 一律**机器原话**，不改写成客气话。
 */
export function RowDetail({
  row,
  pick,
  onPick,
  onAssign,
  timeline,
}: {
  row: QueueRow
  /** 当前选中的候选卷名 */
  pick?: string
  onPick: (name: string) => void
  onAssign: () => void
  timeline?: TimelineEntry[]
}) {
  const assignable = row.state === '待人工认卷' && (row.candidates?.length ?? 0) > 0

  return (
    <div className="gq-detail">
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        {/* 停留原因 + 出口：照状态机原话渲，页面不改写 */}
        <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.65)' }}>
          <b>为什么停在这儿：</b>
          {row.reason || '—'}
          <span style={{ marginInlineStart: 16 }}>
            <b>出口：</b>
            {row.exits.length > 0 ? row.exits.join('　｜　') : '到头了，没有下一步'}
          </span>
        </div>

        {/* 机器原话 */}
        {row.note ? (
          <div className="gq-note">
            <div className="gq-note-title">机器原话（不改写）</div>
            <p className="gq-note-text">{row.note}</p>
          </div>
        ) : null}

        {/* 🔴 候选卷二选一：认卷是人的活，选完这条就回「批改中」交还给机器 */}
        {assignable ? (
          <div className="gq-pick">
            <div className="gq-note-title" style={{ marginBottom: 6 }}>
              编排器多命中，认不出是哪一张 —— 请指定（选完回「批改中」，机器接着跑）
            </div>
            <Radio.Group value={pick} onChange={(e) => onPick(e.target.value)}>
              <Space direction="vertical" size={4}>
                {row.candidates?.map((c) => (
                  <Radio key={c} value={c} style={{ fontSize: 13 }}>
                    {c}
                  </Radio>
                ))}
              </Space>
            </Radio.Group>
            <div style={{ marginTop: 8 }}>
              <Button size="small" type="primary" disabled={!pick} onClick={onAssign}>
                就是这张
              </Button>
              <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineStart: 8 }}>
                mock：只改本地状态，真认卷在 agent 侧
              </Typography.Text>
            </div>
          </div>
        ) : null}

        {/* 本地动作留痕 */}
        {timeline && timeline.length > 0 ? (
          <ul className="gq-timeline">
            {timeline.map((t, i) => (
              <li key={`${t.at}-${i}`}>
                {t.at}　{t.text}
              </li>
            ))}
          </ul>
        ) : null}
      </Space>
    </div>
  )
}

export default RowDetail
