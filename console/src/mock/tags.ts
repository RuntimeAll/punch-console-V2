import type { QuestionTag, TagDomain } from './types'
import { TAG_DOMAINS } from './types'

/**
 * 标签词池（数据结构.md D-19：tag / question_tag 两表的 mock 面）。
 *
 * 🔴 标签 = **不成树、不定量**的维度：场景与特殊方法这类东西，硬塞进考点树只会把树搞脏。
 * 四个首发域（TAG_DOMAINS）已拍板；**开新域零改表** —— 往下面加一条别的 domain 就行，
 * 页面按 domain 分组渲染，不需要改任何结构。
 *
 * 🔴 不存 use_count 这类计数（老区 143 个里 74 个是错的）：要「这个标签挂了几道题」就现算。
 */
export const tagPool: QuestionTag[] = [
  // 场景：题目讲的是哪种真实情境
  { domain: '场景', name: '生活情境' },
  { domain: '场景', name: '行程问题' },
  { domain: '场景', name: '购物付款' },
  { domain: '场景', name: '拼图操作' },

  // 方法：这道题吃哪种特殊招法
  { domain: '方法', name: '凑整拆数' },
  { domain: '方法', name: '整体代入' },
  { domain: '方法', name: '逆推还原' },
  { domain: '方法', name: '画图辅助' },

  // 思想：更上位的数学思想（老区 math_thoughts 有存量对位）
  { domain: '思想', name: '分类讨论' },
  { domain: '思想', name: '数形结合' },
  { domain: '思想', name: '转化思想' },
  { domain: '思想', name: '方程思想' },

  // 图形特征：几何题的形状特征
  { domain: '图形特征', name: '拼接' },
  { domain: '图形特征', name: '折叠' },
  { domain: '图形特征', name: '网格' },
  { domain: '图形特征', name: '共顶点' },
]

/** 某个域下的全部标签（页面按域分组时用；域的顺序走 TAG_DOMAINS） */
export function tagsOfDomain(domain: TagDomain): QuestionTag[] {
  return tagPool.filter((t) => t.domain === domain)
}

/** 全部域（按正本顺序），页面别自己写死四个中文 */
export function tagDomains(): TagDomain[] {
  return TAG_DOMAINS
}

/** 标签的展示写法：域·名（同名不同域是两条标签，展示时必须带域，否则分不清） */
export function tagText(t: QuestionTag): string {
  return `${t.domain}·${t.name}`
}
