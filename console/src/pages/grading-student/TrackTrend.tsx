import { Typography } from 'antd'
import type { Batch } from '@/mock'
import { stateHue } from '@/pages/grading/batch-view'

/**
 * 轨内趋势折线（纯 SVG，不引图表库）。
 * 🔴 铁律③：喂进来的点**必须来自同一条轨**，横轴是「轨内第几天」（D1…DN）。
 * 绝不允许把两条轨的天首尾相接画成一条线——那是把两本册子的成绩混算。
 */
export type TrendPoint = {
  /** 轨内第几天 */
  day: number
  right: number
  total: number
  state: Batch['state']
}

const PAD_L = 42
const PAD_R = 18
const PAD_T = 22
const PAD_B = 26
const PLOT_H = 112
const STEP = 66

export function TrackTrend({ points }: { points: TrendPoint[] }) {
  const usable = points.filter((p) => p.total > 0)

  if (usable.length === 0) {
    return (
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        本轨还没有出分的天，趋势图等第一批批完出现。
      </Typography.Text>
    )
  }

  const width = PAD_L + Math.max(usable.length - 1, 1) * STEP + PAD_R
  const height = PAD_T + PLOT_H + PAD_B
  const x = (i: number) => PAD_L + i * STEP
  const y = (percent: number) => PAD_T + (1 - percent / 100) * PLOT_H

  const rows = usable.map((p, i) => {
    const percent = Math.round((p.right / p.total) * 100)
    return { ...p, percent, cx: x(i), cy: y(percent) }
  })

  const polyline = rows.map((r) => `${r.cx},${r.cy}`).join(' ')

  return (
    <div className="gs-trend">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="轨内正确率趋势">
        {/* 网格线：100% / 50% / 0%，浅灰细线，不铺底色 */}
        {[100, 50, 0].map((v) => (
          <g key={v}>
            <line x1={PAD_L} y1={y(v)} x2={width - PAD_R} y2={y(v)} stroke="#f0f0f0" strokeWidth={1} />
            <text x={PAD_L - 8} y={y(v) + 4} textAnchor="end" fontSize={11} fill="rgba(0,0,0,0.45)">
              {v}%
            </text>
          </g>
        ))}

        {/* 折线本体：只有 2 个点以上才画线 */}
        {rows.length > 1 ? (
          <polyline points={polyline} fill="none" stroke="#1677ff" strokeWidth={1.6} strokeLinejoin="round" />
        ) : null}

        {rows.map((r) => (
          <g key={r.day}>
            {/* 点：待终审用状态色描边提示「这天还没定版」 */}
            <circle cx={r.cx} cy={r.cy} r={3.5} fill="#fff" stroke={stateHue(r.state)} strokeWidth={1.8} />
            {/* 点上标注得分（原始题数口径，不写百分比，免得和纵轴重复） */}
            <text x={r.cx} y={r.cy - 9} textAnchor="middle" fontSize={11} fill="rgba(0,0,0,0.65)">
              {r.right}/{r.total}
            </text>
            {/* 横轴：轨内第几天 */}
            <text x={r.cx} y={PAD_T + PLOT_H + 16} textAnchor="middle" fontSize={11} fill="rgba(0,0,0,0.45)">
              D{r.day}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

export default TrackTrend
