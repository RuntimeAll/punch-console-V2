import { useEffect, useRef } from 'react'
import { Alert, Empty } from 'antd'
import type { KbCell, KbDoc } from './types'
import { mdToHtml, scheduleTypeset } from './mathjax'
import './kb.css'

/**
 * 🔴 真库页唯一的块流渲染入口（四型闭集：text / figure / option / table）。
 *
 * 与 mock 的 `components/BlockFlow` 的分工：那个渲 mock 形状、按纯文本出题面；
 * 本组件渲**库里的真形状**，并把 `$…$` 交给 MathJax 真渲出来。两者不合并——
 * mock 页是设计稿、真库页是数据，混一起改一个必崩另一个。
 *
 * 安全口径：一切 md 都过 `mdToHtml`（先 HTML 转义、后补 `\(\)` 定界符）才进 DOM，
 * 数据里带标签也只会原样显示成文字。
 */
export function KbDocView({ doc, empty = '（无内容）' }: { doc: KbDoc | null | undefined; empty?: string }) {
  if (!doc) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} />
  if (doc.parse_error) {
    // 🔴 坏数据如实报，绝不静默渲成空白（空白会被当成"这题本来就没内容"）
    return <Alert type="error" showIcon message="块流 JSON 损坏" description={doc.parse_error} />
  }
  if (!doc.rows?.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={empty} />

  return (
    <div className="kbdoc">
      {doc.rows.map((row, ri) => (
        <div key={ri} className={(row.cells?.length ?? 0) > 1 ? 'kb-row kb-row-flow' : 'kb-row'}>
          {(row.cells ?? []).map((c, ci) => (
            <CellView key={ci} cell={c} />
          ))}
        </div>
      ))}
    </div>
  )
}

/**
 * 🔴 带公式的一段文字 —— 全站真库页只有这一个地方往 DOM 里塞 HTML。
 *
 * 为什么用 ref 手写 innerHTML 而不是 `dangerouslySetInnerHTML`：
 *   MathJax 排完会把 `\(…\)` 换成 `<mjx-container>` 子树，这是 **React 不知道的 DOM 变更**。
 *   一旦 React 把这个节点重建（实测：antd Table 每次 columns 换新引用就重建单元格），
 *   排好的公式会被打回 `\(…\)` 原文，而 `dangerouslySetInnerHTML` 因为字符串没变**不会重排**
 *   ——页面就这么留在半渲染状态。改成"节点上盖戳 data-kb-md"：
 *   节点是新建的就没戳 ⇒ 重写内容 + 重排；戳还在且内容没换 ⇒ 什么都不做。自愈且不空转。
 */
export function KbInline({ md }: { md: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  // 🔴 故意不给依赖数组：每次渲染都自检一遍，这正是"节点被重建"能被发现的唯一时机
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (el.dataset.kbMd === md) return
    el.innerHTML = mdToHtml(md ?? '')
    el.dataset.kbMd = md
    scheduleTypeset(el)
  })
  return <span ref={ref} />
}

function CellView({ cell, inOption = false }: { cell: KbCell; inOption?: boolean }) {
  if (!cell || typeof cell !== 'object') {
    return <span style={{ color: '#cf1322' }}>🔴 非法块（不是对象）</span>
  }

  if (cell.type === 'text') {
    return (
      <p className="kb-text">
        {cell.role && cell.role !== '题面' ? <span className="kb-role">{cell.role}</span> : null}
        <KbInline md={cell.md ?? ''} />
      </p>
    )
  }

  if (cell.type === 'figure') {
    // 展示台不做图床：图只出占位框并**写明 asset id**，要看真身去 知识库/资产/
    return (
      <span className="kb-figure" style={{ width: inOption ? '100%' : cell.width }}>
        🖼 图占位 · asset=<b>{cell.asset}</b>
        {cell.width ? <> · 宽 {cell.width}</> : null}
        {cell.caption ? (
          <>
            <br />
            {cell.caption}
          </>
        ) : null}
      </span>
    )
  }

  if (cell.type === 'option') {
    return (
      <span className="kb-option">
        <span className="kb-option-label">{cell.label}.</span>
        <span>
          {(cell.blocks ?? []).map((b, i) => (
            <CellView key={i} cell={b} inOption />
          ))}
        </span>
      </span>
    )
  }

  if (cell.type === 'table') return <TableView cell={cell} />

  return <span style={{ color: '#cf1322' }}>🔴 未知块型：{String((cell as { type?: string }).type)}</span>
}

/**
 * 表格块两种载荷都认（口径来自 `工具箱/库/gates.py` 的 table 分支）：
 *   ① `md` = GFM 整表；② `rows` = [行][格][块列表]（闸认的结构化形状）。
 * 另兼容读原型期 `{cells:[{md,isHeader}]}` 形状——遇到就照渲，不静默出空表。
 */
function TableView({ cell }: { cell: Extract<KbCell, { type: 'table' }> }) {
  if (typeof cell.md === 'string' && cell.md.trim()) return <GfmTable md={cell.md} />
  const rows = cell.rows
  if (!Array.isArray(rows) || rows.length === 0) {
    return <span style={{ color: '#cf1322' }}>🔴 表格块无载荷（既无 md 也无 rows）</span>
  }

  // 形状嗅探：闸形状 = 行本身是数组；原型形状 = 行是 {cells:[…]}
  const gateShape = Array.isArray(rows[0])
  return (
    <div className="kb-table">
      <table>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri}>
              {gateShape
                ? (r as KbCell[][]).map((tc, ci) => {
                    // 闸形状不带表头位；按老规矩首行当表头（打卡/教辅表格一律首行是表头）
                    const Tag = ri === 0 ? 'th' : 'td'
                    return (
                      <Tag key={ci}>
                        {(tc ?? []).map((b, bi) => (
                          <CellView key={bi} cell={b} />
                        ))}
                      </Tag>
                    )
                  })
                : ((r as { cells?: { md?: string; isHeader?: boolean; colspan?: number; rowspan?: number }[] })
                    .cells ?? []
                  ).map((tc, ci) => {
                    const Tag = tc.isHeader ? 'th' : 'td'
                    return (
                      <Tag key={ci} colSpan={tc.colspan} rowSpan={tc.rowspan}>
                        <KbInline md={tc.md ?? ''} />
                      </Tag>
                    )
                  })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** GFM 整表：按 | 切列，第二行是 |---| 分隔行则首行当表头 */
function GfmTable({ md }: { md: string }) {
  const lines = md
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
  const split = (l: string) =>
    l
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((s) => s.trim())
  const isSep = (l: string) => /^\|?\s*:?-{2,}/.test(l)
  const head = lines.length > 1 && isSep(lines[1]) ? split(lines[0]) : null
  const body = (head ? lines.slice(2) : lines).map(split)
  return (
    <div className="kb-table">
      <table>
        {head ? (
          <thead>
            <tr>
              {head.map((h, i) => (
                <th key={i}>
                  <KbInline md={h} />
                </th>
              ))}
            </tr>
          </thead>
        ) : null}
        <tbody>
          {body.map((r, ri) => (
            <tr key={ri}>
              {r.map((c, ci) => (
                <td key={ci}>
                  <KbInline md={c} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default KbDocView
