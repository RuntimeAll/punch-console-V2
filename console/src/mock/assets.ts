/**
 * 资产表（数据结构.md §2.1⑤ asset）。
 *
 * 🔴 块流里的 figure **只存指针**（asset 哈希），图的真身在本表。
 * 真库里 rel_path 指到 `知识库/资产/<hash前2>/<hash>.<ext>`（🔴 一律相对 v2 根：
 * 老货架 717 行绝对路径全断的教训）；原型阶段没有文件系统，svg 字段就是「取到的那份图」。
 *
 * SVG 约定：手写内联线条图，stroke #333，无填充色块，随容器宽度自适应，
 * 由 <BlockFlow> 按 figure.width 给的百分比装进版面。
 */
export interface Asset {
  /** 内容哈希（真库里由字节算出；mock 里是稳定假哈希，只要求全表唯一） */
  hash: string
  kind: 'figure' | 'photo' | 'sample'
  /** 🔴 相对 v2 根的路径，绝不写绝对路径 */
  relPath: string
  /** 宽高等提示信息（🔴 版面宽度以块流的 width 百分比为准，像素只作提示） */
  meta: { w: number; h: number }
  /** 原型阶段的图真身（内联 SVG，本仓可信内容） */
  svg: string
}

/** 直角梯形 →（拼）→ 长方形，标 13cm / 25cm / 10cm */
const SVG_梯形拼长方形 = `
<svg viewBox="0 0 470 190" width="100%" xmlns="http://www.w3.org/2000/svg">
  <g fill="none" stroke="#333" stroke-width="1.5" stroke-linejoin="round">
    <polygon points="40,50 120,50 160,130 40,130" fill="#fafafa"/>
    <path d="M40,118 h12 v12"/>
    <path d="M185,90 h34"/>
    <rect x="245" y="50" width="180" height="80" fill="#fafafa"/>
    <path d="M365,130 L325,50" stroke-dasharray="5 4"/>
  </g>
  <polygon points="219,84 233,90 219,96" fill="#333"/>
  <g font-family="system-ui, sans-serif" font-size="13" fill="#333">
    <text x="147" y="86">13cm</text>
    <text x="335" y="152" text-anchor="middle">25cm</text>
    <text x="431" y="94">10cm</text>
  </g>
</svg>`.trim()

/** 解析图：在长方形上标出梯形的四条边 */
const SVG_梯形拼长方形_解析 = `
<svg viewBox="0 0 300 160" width="100%" xmlns="http://www.w3.org/2000/svg">
  <rect x="40" y="30" width="200" height="90" fill="#fafafa" stroke="#333" stroke-width="1.5"/>
  <path d="M170,120 L130,30" stroke="#333" stroke-width="1.5" stroke-dasharray="5 4" fill="none"/>
  <polygon points="40,30 130,30 170,120 40,120" fill="none" stroke="#1677ff" stroke-width="2.5" stroke-linejoin="round"/>
  <g font-family="system-ui, sans-serif" font-size="13" fill="#333">
    <text x="140" y="142" text-anchor="middle">25cm</text>
    <text x="246" y="80">10cm</text>
    <text x="156" y="80">13cm</text>
  </g>
</svg>`.trim()

/** 三角形内角和：已知两角求第三角 */
const SVG_三角形求角 = `
<svg viewBox="0 0 240 170" width="100%" xmlns="http://www.w3.org/2000/svg">
  <polygon points="40,140 200,140 110,40" fill="#fafafa" stroke="#333" stroke-width="1.5" stroke-linejoin="round"/>
  <g font-family="system-ui, sans-serif" font-size="13" fill="#333">
    <text x="56" y="132">55°</text>
    <text x="164" y="132">75°</text>
    <text x="103" y="66">?</text>
  </g>
</svg>`.trim()

/** 正方形与正五边形共边，求夹角 ∠1 */
const SVG_正方形五边形 = `
<svg viewBox="0 0 240 300" width="100%" xmlns="http://www.w3.org/2000/svg">
  <g fill="#fafafa" stroke="#333" stroke-width="1.5" stroke-linejoin="round">
    <polygon points="70,180 160,180 187.8,94.4 115,41.5 42.2,94.4"/>
    <rect x="70" y="180" width="90" height="90"/>
  </g>
  <path d="M63.2,159.1 A22,22 0 0 0 70,202" fill="none" stroke="#1677ff" stroke-width="1.5"/>
  <g font-family="system-ui, sans-serif" font-size="13" fill="#333">
    <text x="34" y="184" text-anchor="end">∠1</text>
    <text x="115" y="118" text-anchor="middle">正五边形</text>
    <text x="115" y="230" text-anchor="middle">正方形</text>
  </g>
</svg>`.trim()

/** 五角星，求五个角的和 */
const SVG_五角星 = `
<svg viewBox="0 0 220 200" width="100%" xmlns="http://www.w3.org/2000/svg">
  <polygon points="110,30 127.6,80.7 181.3,81.8 138.5,114.3 154.1,165.7 110,135 65.9,165.7 81.5,114.3 38.7,81.8 92.4,80.7"
           fill="#fafafa" stroke="#333" stroke-width="1.5" stroke-linejoin="round"/>
  <g font-family="system-ui, sans-serif" font-size="13" fill="#333">
    <text x="110" y="60" text-anchor="middle">1</text>
    <text x="164" y="94" text-anchor="middle">2</text>
    <text x="146" y="148" text-anchor="middle">3</text>
    <text x="74" y="148" text-anchor="middle">4</text>
    <text x="56" y="94" text-anchor="middle">5</text>
  </g>
</svg>`.trim()

/** 选项图 A：两条直线斜着相交（不垂直） */
const SVG_选项_斜交 = `
<svg viewBox="0 0 120 90" width="100%" xmlns="http://www.w3.org/2000/svg">
  <g stroke="#333" stroke-width="1.5" fill="none">
    <path d="M12,74 L108,20"/>
    <path d="M18,20 L104,70"/>
  </g>
</svg>`.trim()

/** 选项图 B：两条直线互相垂直（带直角标记） */
const SVG_选项_垂直 = `
<svg viewBox="0 0 120 90" width="100%" xmlns="http://www.w3.org/2000/svg">
  <g stroke="#333" stroke-width="1.5" fill="none">
    <path d="M12,58 L108,58"/>
    <path d="M60,10 L60,82"/>
    <path d="M60,48 h10 v10"/>
  </g>
</svg>`.trim()

/** 选项图 C：两条直线平行 */
const SVG_选项_平行 = `
<svg viewBox="0 0 120 90" width="100%" xmlns="http://www.w3.org/2000/svg">
  <g stroke="#333" stroke-width="1.5" fill="none">
    <path d="M12,32 L108,32"/>
    <path d="M12,64 L108,64"/>
  </g>
</svg>`.trim()

/** 选项图 D：两条线段没相交，但延长后会相交（不平行） */
const SVG_选项_延长相交 = `
<svg viewBox="0 0 120 90" width="100%" xmlns="http://www.w3.org/2000/svg">
  <g stroke="#333" stroke-width="1.5" fill="none">
    <path d="M14,26 L92,26"/>
    <path d="M14,72 L92,58"/>
    <path d="M92,26 L112,26" stroke-dasharray="4 4"/>
    <path d="M92,58 L112,54" stroke-dasharray="4 4"/>
  </g>
</svg>`.trim()

/**
 * 🔴 资产正本。块流里的 figure.asset 一律引本表的 hash；
 * 引了表里没有的 hash = 断链，渲染层要如实标红（不许静默渲成空白）。
 */
export const assets: Asset[] = [
  { hash: 'cceea0b6', kind: 'figure', relPath: '知识库/资产/cc/cceea0b6.svg', meta: { w: 470, h: 190 }, svg: SVG_梯形拼长方形 },
  { hash: '7b41d2e0', kind: 'figure', relPath: '知识库/资产/7b/7b41d2e0.svg', meta: { w: 300, h: 160 }, svg: SVG_梯形拼长方形_解析 },
  { hash: '3f9c14aa', kind: 'figure', relPath: '知识库/资产/3f/3f9c14aa.svg', meta: { w: 240, h: 170 }, svg: SVG_三角形求角 },
  { hash: '91d0b7c3', kind: 'figure', relPath: '知识库/资产/91/91d0b7c3.svg', meta: { w: 240, h: 300 }, svg: SVG_正方形五边形 },
  { hash: '6a2e8f57', kind: 'figure', relPath: '知识库/资产/6a/6a2e8f57.svg', meta: { w: 220, h: 200 }, svg: SVG_五角星 },
  { hash: 'd41a9e02', kind: 'figure', relPath: '知识库/资产/d4/d41a9e02.svg', meta: { w: 120, h: 90 }, svg: SVG_选项_斜交 },
  { hash: 'd52b8f13', kind: 'figure', relPath: '知识库/资产/d5/d52b8f13.svg', meta: { w: 120, h: 90 }, svg: SVG_选项_垂直 },
  { hash: 'd63ca024', kind: 'figure', relPath: '知识库/资产/d6/d63ca024.svg', meta: { w: 120, h: 90 }, svg: SVG_选项_平行 },
  { hash: 'd74db135', kind: 'figure', relPath: '知识库/资产/d7/d74db135.svg', meta: { w: 120, h: 90 }, svg: SVG_选项_延长相交 },
]

/** 按哈希取资产；查不到返回 undefined（渲染层据此显示断链，别静默吞掉） */
export function findAsset(hash: string): Asset | undefined {
  return assets.find((a) => a.hash === hash)
}
