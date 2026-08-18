import type { ErrCodeMapEntry } from './types'

/**
 * 产线错因码 → 错因 的翻译层（数据结构.md §2.3 err_code_map）。
 *
 * 🔴🔴 主键是**复合键 (kpId, code)**，不是 code 一个字段。理由是实锤不是洁癖：
 * 产线码 `dist` 在「混合运算」线指的是**运算律简算用错**，
 * 在「整式」线指的是**去括号/合并同类项出错** —— **同码两义**，
 * 而这个歧义已经印进过学员交付报告。无作用域的 (code→cause) 映射必然串义。
 *
 * 🔴 写入纪律（照抄老区）：同键**不静默覆盖**；改判走「先摘后挂」两条审计记录，可回溯。
 *
 * 🔴 kpId 为空串 = **通用兜底**（跨考点都成立的码，如誊写笔误）：
 * 只有在带作用域的键都没命中时才允许落到它，绝不能反过来拿它去盖住有作用域的映射。
 */
export const errCodeMap: ErrCodeMapEntry[] = [
  // ── 🔴 同码两义的活样本：同一个 dist，两个考点两种含义 ──────────────
  {
    kpId: 'renjiao/g4a/u4/s4/k1',
    code: 'dist',
    causeId: 'ec-order',
    note: '混合运算线：把同级运算里的 25×4 先凑成 100 再去除，运算律用在了不该用的地方（顺序被改了）',
  },
  {
    kpId: 'renjiao/g7a/u2/s2/k1',
    code: 'dist',
    causeId: 'ec-sign',
    note: '整式线：去括号漏乘系数或没变号，合并同类项时把符号带错 —— 与混合运算线的 dist 完全不是一回事',
  },

  // ── 其余映射（每条都带考点作用域）──────────────────────────────
  {
    kpId: 'renjiao/g4a/u4/s4/k1',
    code: 'order',
    causeId: 'ec-order',
    note: '先乘除后加减、有括号先算括号 —— 这三条里错了任意一条',
  },
  {
    kpId: 'renjiao/g7a/u1/s4/k1',
    code: 'sign',
    causeId: 'ec-sign',
    note: '有理数混合运算：负号丢失、减法未变加、除法未取倒数',
  },
  {
    kpId: 'renjiao/g7a/u1/s2/k2',
    code: 'miss',
    causeId: 'ec-miss',
    note: '含字母绝对值：分类讨论只写了一支（最常漏 a＝0）',
  },
  {
    kpId: 'renjiao/g7a/u1/s3/k1',
    code: 'concept',
    causeId: 'ec-concept',
    note: '(−2)³ 与 −2³ 混为一谈：底数到底带不带负号',
  },
  {
    kpId: 'renjiao/g4a/u4/s2/k1',
    code: 'carry',
    causeId: 'ec-carry',
    note: '笔算乘法进位没加上去，或进位加到了错的一位',
  },
  {
    kpId: 'renjiao/g4a/u6/s3/k1',
    code: 'carry',
    causeId: 'ec-carry',
    note: '笔算除法退位错：借位后忘了减 1（同一个 carry 码，除法线说的是退位）',
  },
  {
    kpId: 'renjiao/g4a/u3/s4/k1',
    code: 'concept',
    causeId: 'ec-concept',
    note: '内角和公式记成 n×180° 或直接套 360°',
  },
  {
    kpId: '',
    code: 'copy',
    causeId: 'ec-copy',
    note: '通用兜底：把题面数字抄错、上下行誊写串位 —— 跨考点都成立，没有作用域',
  },
]

/**
 * 翻译一个产线码：**先按 (kpId, code) 精确查，查不到才落通用兜底**。
 * 🔴 顺序不许颠倒：颠倒了就是拿通用义盖住考点义，同码两义又串回去了。
 */
export function resolveErrCode(kpId: string, code: string): ErrCodeMapEntry | undefined {
  return (
    errCodeMap.find((e) => e.kpId === kpId && e.code === code) ??
    errCodeMap.find((e) => e.kpId === '' && e.code === code)
  )
}

/** 这片考点叶下登记了哪些码（错因页按考点看翻译表用） */
export function codesOfKp(kpId: string): ErrCodeMapEntry[] {
  return errCodeMap.filter((e) => e.kpId === kpId)
}

/**
 * 🔴 一码多义清单：同一个 code 在不同考点下翻译成**不同**错因的那些码。
 * 页面要把它显式标出来 —— 这是「为什么主键必须带 kpId」的现场证据，不是异常。
 */
export function ambiguousCodes(): { code: string; entries: ErrCodeMapEntry[] }[] {
  const byCode = new Map<string, ErrCodeMapEntry[]>()
  for (const e of errCodeMap) {
    const hit = byCode.get(e.code)
    if (hit) hit.push(e)
    else byCode.set(e.code, [e])
  }
  return Array.from(byCode.entries())
    .filter(([, list]) => new Set(list.map((e) => e.causeId)).size > 1)
    .map(([code, entries]) => ({ code, entries }))
}
