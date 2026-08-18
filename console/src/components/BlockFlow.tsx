import type { Block, BlockRow, Cell } from '@/mock'
import { findAsset } from '@/mock'
import './BlockFlow.css'

/**
 * 🔴🔴 块流混排渲染器 —— 全站唯一的题目内容渲染入口（块流 v2）。
 *
 * 数据形状（数据结构.md §2.1②）：`{ v:2, rows:[{ cells:[Cell] }] }`，
 * Cell 四型：text / figure / option / table。
 *
 * 渲染规则（三条，页面别自己另发明一套）：
 * ① **行是竖着来的，行内是横着流的**：一行多个 cell 时按 flex-wrap 流式排布 ——
 *    短的并排、放不下的整体折到下一行；
 * ② 🔴 **option 整体不可折散**（用户判词）：一个选项 = 标号 + 内容一个盒子，
 *    换行时整块走，绝不出现「标号在上一行、图掉到下一行」；
 * ③ 🔴 **figure 按 width 百分比占位**：宽度是数据带来的（老区 5467 个图块个个带宽度），
 *    渲染层不许自己拍脑袋定大小；图**原位**渲染，绝不允许抽出来集中成页尾「配图区」
 *    （老版被否定的头号交互）。
 *
 * 题面 / 答案 / 解析是三份独立块流，各调一次本组件即可。
 * 旧格式（v1 的 Block[] 数组）不兼容也不做降级：mock 已全量换新，出现旧数据就是脏数据。
 */
export function BlockFlow({
  blocks,
  size = 'normal',
}: {
  /** 一份块流文档（不是数组）：题面 / 答案 / 解析各传一份 */
  blocks: Block
  /** normal = 详情/打印；compact = 列表里的缩略预览（图会限高） */
  size?: 'normal' | 'compact'
}) {
  return (
    <div className={`bf bf-${size}`}>
      {blocks.rows.map((r, i) => (
        // key 用下标：块流是定序静态内容，不做增删排序
        <Row key={i} row={r} />
      ))}
    </div>
  )
}

/** 一行：单 cell 就是普通段落；多 cell 走流式排布（选项行的换行全靠它） */
function Row({ row }: { row: BlockRow }) {
  const multi = row.cells.length > 1
  return (
    <div className={multi ? 'bf-row bf-row-flow' : 'bf-row'}>
      {row.cells.map((c, i) => (
        <CellView key={i} cell={c} />
      ))}
    </div>
  )
}

/**
 * 一个 cell 按块型分派（四型闭集；将来加块型先改 types.ts，再回这里加分支）。
 * @param inOption 这个 cell 是不是长在某个选项**里面**（图选项要把宽度让给外层选项盒子）
 */
function CellView({ cell, inOption = false }: { cell: Cell; inOption?: boolean }) {
  if (cell.type === 'text') {
    // md 里的 Markdown / $LaTeX$ 原型阶段按纯文本渲（够走查用），不引 md 解析器
    return <p className="bf-text">{cell.md}</p>
  }

  if (cell.type === 'figure') {
    // 🔴 选项里的图：宽度由外层选项盒子按同一个百分比占位，图自己铺满盒子，
    //    这样四个图选项才会等宽并排，而且换行时图跟着自己的选项一起走
    return (
      <figure className="bf-figure" style={{ width: inOption ? '100%' : cell.width }}>
        <FigureBody asset={cell.asset} />
        {cell.caption ? <figcaption className="bf-caption">{cell.caption}</figcaption> : null}
      </figure>
    )
  }

  if (cell.type === 'option') {
    // 选项里裹着图时，把图的百分比宽提到选项盒子上（见上一段注释）
    const inner = cell.blocks.find((b) => b.type === 'figure')
    const basis = inner !== undefined && inner.type === 'figure' ? inner.width : undefined
    return (
      <div className="bf-option" style={basis === undefined ? undefined : { flexBasis: basis }}>
        {/* 🔴 标号与内容在同一个盒子里：这就是「option 整体不可折散」的实现 */}
        <span className="bf-option-label">{cell.label}.</span>
        <span className="bf-option-body">
          {cell.blocks.map((c, i) => (
            <CellView key={i} cell={c} inOption />
          ))}
        </span>
      </div>
    )
  }

  return (
    <div className="bf-table">
      <table>
        <tbody>
          {cell.rows.map((r, ri) => (
            <tr key={ri}>
              {r.cells.map((c, ci) =>
                c.isHeader ? (
                  <th key={ci} colSpan={c.colspan} rowSpan={c.rowspan}>
                    {c.md}
                  </th>
                ) : (
                  <td key={ci} colSpan={c.colspan} rowSpan={c.rowspan}>
                    {c.md}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * 图真身：块流里只有 asset 指针，到这一步才去资产表取。
 * 🔴 取不到**如实标断链**，不许静默渲成空白 —— 空白会被当成「这题本来就没图」。
 */
function FigureBody({ asset }: { asset: string }) {
  const hit = findAsset(asset)
  if (!hit) {
    return <span className="bf-broken">图资产缺失：{asset}</span>
  }
  // mock 的 svg 是本仓内联可信字符串；将来接后端必须先过白名单清洗
  return <span className="bf-svg" dangerouslySetInnerHTML={{ __html: hit.svg }} />
}

export default BlockFlow
