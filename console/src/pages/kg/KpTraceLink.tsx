import type { MouseEvent, ReactNode } from 'react'
import { Tag } from 'antd'
import { useNavigate } from 'react-router-dom'
import { kpKeyOf } from './trace'

/**
 * 🔴 溯源链的**唯一渲法**（判词⑤）：任何地方出现一个「考点名」，都用这个件渲，
 * 点一下落到 /kg?kp=<树key> 并选中那片叶。
 * 现在的用处：/model 的挂靠考点列与抽屉、/cause 错因库的挂靠考点列、/questions/:id 的考点行。
 *
 * 🔴 两态必须长得不一样，不许糊成一种：
 * - **通**：树上有这片叶 → 蓝字 + 手型，点得动；
 * - **断**：树上没有这片叶 → 灰字、不给点，title 说清为什么。
 *   断点不是 bug，是**欠账**（叶子还没铺进教材树），页面如实显示才看得见活儿。
 *   em-005 那两个绝对值考点就是这种：模型认领了，七上那一枝树还没铺。
 *
 * 🔴 一个组件包住这件事，是为了三处不各写各的判空——
 *   否则总有一处会把断点渲成能点，点过去落一个空页。
 */
export function KpTraceLink({
  name,
  primary = false,
  onNavigated,
}: {
  name: string
  /** 主考点：沿用题库页 KpTags 的样子（★ + 蓝底 Tag），走查时两页看着是同一个东西 */
  primary?: boolean
  /** 跳走之前捎带做点事（比如关掉抽屉），可不传 */
  onNavigated?: () => void
}) {
  const navigate = useNavigate()
  const key = kpKeyOf(name)

  // 断：树上没有这片叶
  if (key === undefined) {
    return (
      <Tag
        title={`「${name}」在教材树上还没有对应的考点叶 —— 溯源断点，等这一枝铺进树才连得上`}
        style={{ marginInlineEnd: 4, marginBottom: 4, color: 'rgba(0,0,0,0.45)', borderStyle: 'dashed' }}
      >
        {primary ? `★ ${name}` : name}
        <span style={{ marginLeft: 4, fontSize: 12, color: 'rgba(0,0,0,0.35)' }}>未上树</span>
      </Tag>
    )
  }

  // 通：点过去落到那片叶
  // 🔴 必须掐住冒泡：这些 Tag 常长在**整行可点**的表格里（/model 点行开抽屉、
  //   /cause 点行开沉淀抽屉），不掐就成了「开抽屉的同时跳走」，两件事一起发生。
  const go = (e: MouseEvent<HTMLElement>) => {
    e.stopPropagation()
    onNavigated?.()
    navigate(`/kg?kp=${encodeURIComponent(key)}`)
  }

  return (
    <Tag
      color={primary ? 'blue' : undefined}
      title={`去知识图谱看「${name}」这片叶挂着什么家当`}
      onClick={go}
      style={{ marginInlineEnd: 4, marginBottom: 4, cursor: 'pointer' }}
    >
      {primary ? (
        `★ ${name}`
      ) : (
        // 不给底色只给链接色：风格口径「禁大色块」，但点得动这件事必须看得出来
        <span style={{ color: '#1677ff' }}>{name}</span>
      )}
    </Tag>
  )
}

/**
 * 一串考点名的溯源链。空数组的说法由调用方给（跨考点通用 / 溯源断点 / 未挂考点，
 * 三处含义完全不同，塞一句默认文案必然有一处是错的）。
 */
export function KpTraceLinks({
  names,
  empty,
  onNavigated,
}: {
  names: string[]
  empty: ReactNode
  onNavigated?: () => void
}) {
  if (names.length === 0) return <>{empty}</>
  return (
    <span>
      {names.map((n) => (
        <KpTraceLink key={n} name={n} onNavigated={onNavigated} />
      ))}
    </span>
  )
}

export default KpTraceLink
