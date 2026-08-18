import { Tooltip } from 'antd'
import type { BatchState } from '@/mock'
import { HUMAN_STATES, STATE_MACHINE } from '@/mock'
import { stateHue } from '@/pages/grading/batch-view'

/**
 * 顶部状态计数条：九格横排 = 一条卷子从收件到出件的整条链。
 *
 * 🔴 判词①「状态外置明确」的第一现场：九格照 STATE_MACHINE 的顺序摆，
 *   摆的就是链路本身，不是「按数量排序的统计图」——格子空了也留着，
 *   空格本身是信息（这一段现在没堵）。
 * 🔴 三个人工态（待人工认卷 / 待终审 / 故障）带红点：红点 = 不点它永远不动。
 *   其余格子是机器在飞，看得见就够，别催。
 * 点格 = 过滤；再点一次取消。
 */
export function StateBar({
  counts,
  active,
  onPick,
}: {
  /** 状态 → 条数（页面按现态算好，含本地动作后的结果） */
  counts: Record<string, number>
  /** 当前筛住的状态；null = 不筛 */
  active: BatchState | null
  onPick: (state: BatchState) => void
}) {
  return (
    <div className="gq-statebar">
      {STATE_MACHINE.map((m) => {
        const n = counts[m.state] ?? 0
        const human = HUMAN_STATES.includes(m.state)
        const cls = [
          'gq-cell',
          human ? 'is-human' : '',
          active === m.state ? 'is-active' : '',
          n === 0 ? 'is-zero' : '',
        ]
          .filter(Boolean)
          .join(' ')

        return (
          <Tooltip key={m.state} title={`${m.actor === '终态' ? '终态' : `${m.actor}推进`} · ${m.reason}`}>
            <button
              type="button"
              className={cls}
              style={{ borderLeftColor: stateHue(m.state) }}
              aria-pressed={active === m.state}
              onClick={() => onPick(m.state)}
            >
              <span className="gq-cell-name">
                {human ? <span className="gq-dot" /> : null}
                {m.state}
              </span>
              <span className="gq-cell-num">{n}</span>
            </button>
          </Tooltip>
        )
      })}
    </div>
  )
}

export default StateBar
