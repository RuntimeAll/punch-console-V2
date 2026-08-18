import type { Batch } from '@/mock'
import { stateHue } from '@/pages/grading/batch-view'

/**
 * 轨内「天格」：一天一格（D1…DN），格里放得分 + 状态，点格开右侧抽屉。
 * 状态只用左边 3px 描边 + 小字色表示，不铺底色（禁大色块）。
 */
export type DayCell = {
  batchId: string
  day: number
  state: Batch['state']
  /** 现判分（终审改过就是改后的），没出分给 null */
  score: { right: number; total: number } | null
}

export function DayGrid({
  cells,
  activeId,
  onOpen,
}: {
  cells: DayCell[]
  activeId: string | null
  onOpen: (batchId: string) => void
}) {
  return (
    <div className="gs-daygrid">
      {cells.map((c) => (
        <button
          key={c.batchId}
          type="button"
          className={`gs-daycell${activeId === c.batchId ? ' is-active' : ''}`}
          style={{ borderLeftColor: stateHue(c.state) }}
          onClick={() => onOpen(c.batchId)}
        >
          <div className="gs-day-no">D{c.day}</div>
          <div className="gs-day-score">{c.score ? `${c.score.right}/${c.score.total}` : '—'}</div>
          <div className="gs-day-state" style={{ color: stateHue(c.state) }}>
            {c.state}
          </div>
        </button>
      ))}
    </div>
  )
}

export default DayGrid
