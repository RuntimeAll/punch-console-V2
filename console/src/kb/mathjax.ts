/**
 * 真库页的数学渲染：MathJax 本地加载 + md/LaTeX → 安全 HTML。
 *
 * 🔴 三条纪律：
 *   ① **本地字体本地脚本**：`/mathjax/tex-mml-chtml.js` 是从 `工具箱/渲染/mathjax/es5/` 原样拷进
 *      `console/public/mathjax/` 的（连 output/ 字体子树一起，保持相对结构 ⇒ MathJax 自己按
 *      脚本位置找字体，不联网、不打 CDN）。
 *   ② **先转义再放定界**：`md` 是库里的文本，直接 dangerouslySetInnerHTML 就是注入口。
 *      本文件的做法是——把 md 切成「文本段 / 数学段」，两种段都先做 HTML 转义，
 *      转义完再补 `\(` `\)` 定界符（定界符是我们自己拼的常量，不来自数据）。
 *      MathJax 从 DOM 的 textContent 读公式，`&lt;` 到它眼里就是 `<`，转义不影响出数。
 *   ③ 只在真库页加载一次（模块级 Promise 缓存），mock 页零负担。
 */

// MathJax 的全局对象没有官方类型；这里只用到三个成员，按最小面声明。
type MathJaxGlobal = {
  typesetPromise?: (els?: Element[]) => Promise<void>
  typesetClear?: (els?: Element[]) => void
  startup?: { promise?: Promise<unknown> }
}
declare global {
  interface Window {
    MathJax?: MathJaxGlobal | Record<string, unknown>
  }
}

let booting: Promise<void> | null = null

/** 注入 MathJax（幂等）。失败**抛出**，页面照实标"公式未渲"，不静默留原文。 */
export function ensureMathJax(): Promise<void> {
  if (booting) return booting
  booting = new Promise<void>((resolve, reject) => {
    const mj = window.MathJax as MathJaxGlobal | undefined
    if (mj?.typesetPromise) {
      resolve()
      return
    }
    // 🔴 配置必须在脚本加载**之前**挂到 window 上
    window.MathJax = {
      tex: {
        // 我们只喂 \(…\) / \[…\]（$ 已在 mdToHtml 里换掉），避免正文里的美元号被当公式
        inlineMath: [['\\(', '\\)']],
        displayMath: [['\\[', '\\]']],
        processEscapes: false,
      },
      options: {
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
        enableMenu: false,
      },
      startup: { typeset: false },
    }
    const s = document.createElement('script')
    s.src = '/mathjax/tex-mml-chtml.js'
    s.async = true
    s.onload = () => {
      const g = window.MathJax as MathJaxGlobal
      const p = g?.startup?.promise
      if (p) p.then(() => resolve()).catch(reject)
      else resolve()
    }
    s.onerror = () => reject(new Error('MathJax 加载失败：/mathjax/tex-mml-chtml.js 取不到'))
    document.head.appendChild(s)
  })
  return booting
}

// ── 排版调度 ────────────────────────────────────────────────────────────
// 🔴 为什么要攒批：MathJax 的 `typesetPromise(els)` 每调一次都会把内部 math 清单重扫一遍，
//   一页二十行各调一次 ⇒ O(n²) 且旧条目会被反复 updateDocument。攒到一个 tick 里一次排完。
const pending = new Set<HTMLElement>()
let timer: number | null = null

/** 把一块 DOM 排进下一批（同一 tick 内的所有块合并成一次 typesetPromise） */
export function scheduleTypeset(el: HTMLElement | null | undefined): void {
  if (!el) return
  pending.add(el)
  if (timer !== null) return
  timer = window.setTimeout(() => {
    timer = null
    const els = [...pending].filter((e) => e.isConnected) // 已被 React 卸掉的节点别排
    pending.clear()
    if (!els.length) return
    void ensureMathJax()
      .then(() => {
        const mj = window.MathJax as MathJaxGlobal
        if (!mj?.typesetPromise) return undefined
        // 清空 MathJax 的旧条目清单（DOM 不受影响）：我们每次都自己重写 innerHTML，
        // 让它记着上一批的条目只会让它去更新已经不存在的节点。
        mj.typesetClear?.()
        return mj.typesetPromise(els)
      })
      .catch((e) => {
        // 单条公式坏了不该整页白屏：控制台留证，页面保留 \(…\) 原文（一眼看得出没排上）
        console.warn('[kb] MathJax 排版出错：', e)
      })
  }, 0)
}

// ── md → HTML ───────────────────────────────────────────────────────────

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 已转义文本上的极简 md：只认 **粗体** 和换行，别的一律原样（不引 md 解析器） */
function lightMd(escaped: string): string {
  return escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br/>')
}

/** 从 from 开始找**未被反斜杠转义**的定界符位置；找不到返回 -1 */
function findClose(md: string, from: number, delim: string): number {
  let i = from
  while (i < md.length) {
    if (md[i] === '\\') {
      i += 2
      continue
    }
    if (md.startsWith(delim, i)) return i
    i += 1
  }
  return -1
}

/**
 * `md`（Markdown + 内联 `$LaTeX$`）→ 可交给 dangerouslySetInnerHTML 的字符串。
 * 🔴 顺序死规矩：**先 escape，后拼定界符**。数据里的每个字符都被转义过，
 *   出现在结果里的所有标签与 `\( \)` 都是本函数写死的常量。
 */
export function mdToHtml(md: string): string {
  if (!md) return ''
  const out: string[] = []
  let buf = ''
  let i = 0
  const flush = () => {
    if (buf) {
      out.push(lightMd(escapeHtml(buf)))
      buf = ''
    }
  }
  while (i < md.length) {
    const ch = md[i]
    if (ch === '\\' && md[i + 1] === '$') {
      // 正文里被转义的美元号：当普通字符，不开数学段
      buf += '$'
      i += 2
      continue
    }
    if (ch === '$') {
      const display = md[i + 1] === '$'
      const delim = display ? '$$' : '$'
      const start = i + delim.length
      const close = findClose(md, start, delim)
      if (close < 0) {
        // 单边美元号 = 数据本来就这样，当普通字符渲，不猜不补
        buf += ch
        i += 1
        continue
      }
      flush()
      const tex = escapeHtml(md.slice(start, close))
      out.push(display ? `\\[${tex}\\]` : `\\(${tex}\\)`)
      i = close + delim.length
      continue
    }
    buf += ch
    i += 1
  }
  flush()
  return out.join('')
}
