import type { ReactNode } from 'react'

/**
 * 页面统一外壳：标题 + 一句话说明 + 右上操作位 + 正文。
 * 六个页面组都用它，保证走查时页头长得一样；只改 children，别各自搓页头。
 */
export function PageFrame({
  title,
  desc,
  extra,
  children,
}: {
  title: string
  /** 一句话说明这页是干嘛的（走查时用户就看这句判断页面该不该存在） */
  desc?: ReactNode
  /** 右上角操作位（按钮/筛选器） */
  extra?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="page-title">{title}</h1>
          {desc ? <p className="page-desc">{desc}</p> : null}
        </div>
        {extra ? <div>{extra}</div> : null}
      </div>
      <div className="page-body">{children}</div>
    </div>
  )
}

export default PageFrame
