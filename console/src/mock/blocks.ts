import type { Block, BlockRow, Cell, CellFigure, CellOption, CellTable, CellText, TableRow } from './types'

/**
 * 块流 v2 的**构造器 + 读取器**（数据结构.md §2.1②）。
 *
 * 🔴 为什么要这一层：块流是 `{ v, rows:[{ cells:[…] }] }` 三层嵌套，
 * mock 里手写 JSON 会淹掉题面本身，页面里手写遍历则各写各的。
 * 造题一律用构造器（`docOf(para('…'), row(figure(…)))`），
 * 读文字一律用读取器（`firstTextOf` / `plainTextOf` / `hasFigureIn`），
 * **页面不许自己递归 rows/cells 挑块** —— 真要渲题只有一个入口：<BlockFlow>。
 */

// ── 构造器（mock 造题用）────────────────────────────────────────

/** 一份块流文档（题面 / 答案 / 解析各一份） */
export function docOf(...rows: BlockRow[]): Block {
  return { v: 2, rows }
}

/** 一行（行内可以摆多个 cell，排布交渲染层） */
export function row(...cells: Cell[]): BlockRow {
  return { cells }
}

/** 文字 cell */
export function text(md: string): CellText {
  return { type: 'text', md }
}

/** 独占一行的文字段落（最常用，等价于 row(text(md))） */
export function para(md: string): BlockRow {
  return { cells: [{ type: 'text', md }] }
}

/** 图 cell：asset = 资产哈希，width = 百分比宽（🔴 不许省） */
export function figure(asset: string, width: string, caption?: string): CellFigure {
  return caption === undefined ? { type: 'figure', asset, width } : { type: 'figure', asset, width, caption }
}

/** 选项 cell：一项一 cell，内容可文可图；🔴 标号原样保留，不规整 */
export function option(label: string, ...blocks: Cell[]): CellOption {
  return { type: 'option', label, blocks }
}

/** 表格 cell */
export function table(rows: TableRow[]): CellTable {
  return { type: 'table', rows }
}

/** 空文档（答案/解析还没录时用它，别用 undefined —— 形状要恒定） */
export const EMPTY_DOC: Block = { v: 2, rows: [] }

// ── 读取器（页面扫读用；🔴 都不是「渲染」，渲染只走 <BlockFlow>）──────

/** 这份块流一个 cell 都没有 */
export function isEmptyDoc(d: Block): boolean {
  return d.rows.every((r) => r.cells.length === 0)
}

/** 一个 cell 的纯文本（option 连标号一起吐，table 按行拼） */
function cellText(c: Cell): string {
  if (c.type === 'text') return c.md
  if (c.type === 'figure') return c.caption ?? ''
  if (c.type === 'option') return `${c.label}. ${c.blocks.map(cellText).join(' ')}`
  return c.rows.map((r) => r.cells.map((cell) => cell.md).join(' ')).join(' ')
}

/**
 * 题面首行摘要（**纯文本**，只给表格单元格 / 清单当扫读用）。
 * 图开头的题没有文字首行 —— 如实说「以图为主」，别硬凑。
 */
export function firstTextOf(d: Block, fallback = '（本题题面以图为主）'): string {
  for (const r of d.rows) {
    for (const c of r.cells) {
      if (c.type === 'text' && c.md.trim()) return c.md.replace(/\s+/g, ' ').trim()
    }
  }
  return fallback
}

/** 全文检索用：把整份块流拍平成一串文字（含选项与表格里的字） */
export function plainTextOf(d: Block): string {
  return d.rows
    .flatMap((r) => r.cells.map(cellText))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** 递归判断某 cell（含选项内部）里有没有图 */
function cellHasFigure(c: Cell): boolean {
  if (c.type === 'figure') return true
  if (c.type === 'option') return c.blocks.some(cellHasFigure)
  return false
}

/** 这份块流里有没有配图（列表里打「含图」标记用；🔴 选项里的图也算） */
export function hasFigureIn(d: Block): boolean {
  return d.rows.some((r) => r.cells.some(cellHasFigure))
}

/** 这份块流里有没有选项块（题库列表标「选择题结构化」用） */
export function hasOptionIn(d: Block): boolean {
  return d.rows.some((r) => r.cells.some((c) => c.type === 'option'))
}

/**
 * 按行过滤出一份新文档（答案页要拆「答案主体 / 方法点拨」这类展示层派生用）。
 * 🔴 展示层派生，不回写 mock。
 */
export function filterRows(d: Block, keep: (r: BlockRow) => boolean): Block {
  return { v: 2, rows: d.rows.filter(keep) }
}

/** 这一行是不是纯文字且以某前缀开头（配合 filterRows 用） */
export function rowStartsWith(r: BlockRow, prefix: string): boolean {
  const first = r.cells[0]
  return first !== undefined && first.type === 'text' && first.md.startsWith(prefix)
}
