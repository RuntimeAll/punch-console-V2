import { Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { Question, QuestionTag } from '@/mock'
import { DIFF_MAX, diffLabel, diffOrd, kpNameOf, tagText } from '@/mock'
import { anchorTitle, isLowConf, tagsByDomain, treePathKeys } from './helpers'

/**
 * 题库组内共用**展示组件**（列表页 /questions 与详情页 /questions/:id 共用一份口径）。
 * 纯函数小件在同目录 helpers.ts（拆开是为了 Fast Refresh）。
 *
 * 🔴 边界：这里只放「元信息怎么显示」（难度星、状态、考点 Tag），
 * **绝不放块流渲染逻辑** —— 题目内容一律走公共件 <BlockFlow>（见 @/components）。
 * 🔴 归属：题库组自用，其它页面组别 import 本文件（要共用请让地基工提到 @/components）。
 */

/**
 * 难度星：用文字 ★☆ 而不是 antd Rate —— Rate 默认是大面积金色，
 * 与「朴素学术、禁大色块」的风格口径冲突；文字星在表格行里也更紧凑。
 *
 * 🔴 第四轮改吃**难度码**（diffCode）：档位与中文都从字典查（@/mock 的 diffOrd / diffLabel），
 * 页面不再私存一份 1~4 的对照表（老区「注释说 3 档、字典其实 4 档」就是这么错的）。
 */
export function DifficultyStars({ code }: { code?: string }) {
  const value = code ? diffOrd(code) : 0
  if (!value) return <Typography.Text type="secondary">—</Typography.Text>
  const title = `${value} 档 / 共 ${DIFF_MAX} 档（${diffLabel(code ?? '')}）`
  return (
    <span title={title} style={{ letterSpacing: 1, whiteSpace: 'nowrap' }}>
      {'★'.repeat(value)}
      <span style={{ color: 'rgba(0,0,0,0.25)' }}>{'☆'.repeat(Math.max(0, DIFF_MAX - value))}</span>
    </span>
  )
}

/**
 * 状态标签（🔴 四态：草稿 / 已审 / 上架 / 退役）。
 * 上架 = 默认态，无色不抢眼；草稿橙（还没 promote，前台看不见）；
 * 已审蓝（过了闸等上架）；退役灰删除线（🔴 只软删，题还在库里）。
 */
export function StatusTag({ status }: { status: Question['status'] }) {
  if (status === '草稿') return <Tag color="orange">草稿</Tag>
  if (status === '已审') return <Tag color="blue">已审</Tag>
  if (status === '退役') {
    return (
      <Tag style={{ textDecoration: 'line-through', color: 'rgba(0,0,0,0.45)' }} title="软删：题还在库里，只是不再出卷">
        退役
      </Tag>
    )
  }
  return <Tag>上架</Tag>
}

/**
 * 考点 Tag 组：主考点（isPrimary）前面带 ★ 并用蓝色，副考点默认灰。
 * 一道题只有一个主考点，评审时用户要一眼看出「这题归哪个考点」。
 *
 * 🔴 题上存的是 kpId，名字现查（kpNameOf）：名字不冗余进题里，改名不用回写题。
 * 🔴 兜底挂靠（anchor.fallback）额外标一枚「兜底」——那是欠账不是正常态，得看得见。
 */
export function KpTags({ kps }: { kps: Question['kps'] }) {
  return (
    <>
      {kps.map((k) => {
        // 🔴 低置信 / 兜底 = 欠账，一律标黄（口径与详情页同一条线：helpers 的 isLowConf）
        const low = isLowConf(k.anchor)
        return (
          <Tag
            key={k.kpId}
            color={low ? 'orange' : k.isPrimary ? 'blue' : undefined}
            style={{ marginInlineEnd: 4 }}
            title={anchorTitle(k.anchor)}
          >
            {k.isPrimary ? `★ ${kpNameOf(k.kpId)}` : kpNameOf(k.kpId)}
            {low ? '（待核）' : ''}
          </Tag>
        )
      })}
    </>
  )
}

/**
 * 标签 chips（列表列用）：🔴 一律渲**域·名**（tagText）。
 * 同名不同域是两条标签（方法·分类讨论 ≠ 思想·分类讨论），只写名字就分不清了。
 */
export function TagChips({ tags }: { tags: QuestionTag[] }) {
  if (tags.length === 0) return <Typography.Text type="secondary">—</Typography.Text>
  return (
    <span>
      {tags.map((t) => (
        <Tag key={tagText(t)} style={{ marginInlineEnd: 4, fontSize: 12 }} title={`标签域：${t.domain}`}>
          {tagText(t)}
        </Tag>
      ))}
    </span>
  )
}

/**
 * 标签 chips **按域分组**（详情页用）：一行一个域，域名在左、chips 在右。
 * 🔴 域的顺序与集合走正本（helpers.tagsByDomain → TAG_DOMAINS）：开新域这里零改。
 * 分组渲染是为了让「标签有 4 个方向」这件事在页面上看得见，而不是糊成一排灰 Tag。
 */
export function TagChipsGrouped({ tags }: { tags: QuestionTag[] }) {
  const groups = tagsByDomain(tags)
  if (groups.length === 0) return <Typography.Text type="secondary">这题还没打标签</Typography.Text>
  return (
    <div>
      {groups.map((g) => (
        <div key={g.domain} style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 4 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12, flex: '0 0 60px' }}>
            {g.domain}
          </Typography.Text>
          <span>
            {g.tags.map((t) => (
              <Tag key={tagText(t)} style={{ marginInlineEnd: 4 }}>
                {t.name}
              </Tag>
            ))}
          </span>
        </div>
      ))}
    </div>
  )
}

/**
 * 树位置面包屑：把 Question.treePath 整条渲出来，**每一段都能点回题库列表并带上筛选**
 *（点「第五单元」= 回列表看这个单元下的全部题；点末段 = 只看这片考点叶）。
 *
 * 🔴 段 → 树 key 走 treePathKeys()（labelPathMap 的逆查表），
 *   不按 key 切字符串反推——单元名里带空格，切出来必错（页面组约定 §1）。
 * 🔴 这里显示的是**归属**（题长在教材哪根枝上），与右边「考点」那行的能力标签不是一回事，
 *   两者末段常同名但不强制，别把两行合并。
 */
export function TreePathTrail({ path }: { path?: string[] }) {
  const navigate = useNavigate()
  if (!path || path.length === 0) {
    return <Typography.Text type="secondary">未挂树（这题还没归到教材树上）</Typography.Text>
  }
  const keys = treePathKeys(path)
  return (
    <span style={{ fontSize: 12, lineHeight: 1.9 }}>
      {path.map((label, i) => {
        const key = keys[i]
        return (
          <span key={label}>
            {i > 0 ? <span style={{ color: 'rgba(0,0,0,0.25)', margin: '0 4px' }}>/</span> : null}
            {key ? (
              // 带 ?tree= 回列表：列表页的树选中以 URL 为事实源
              <Typography.Link onClick={() => navigate(`/questions?tree=${encodeURIComponent(key)}`)}>
                {label}
              </Typography.Link>
            ) : (
              // 树上查不到这一段 = 这题的 treePath 编错了，如实显示成不可点
              <Typography.Text type="secondary" title="教材树上找不到这一段，可能是 treePath 录错了">
                {label}
              </Typography.Text>
            )}
          </span>
        )
      })}
    </span>
  )
}
