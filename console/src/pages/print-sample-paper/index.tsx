import { useState } from 'react'
import { Button, Space, Switch } from 'antd'
import { SamplePaper } from '@/pages/print-sample-paper/paper'
import { STANDARD_TPL_ID, findTemplate } from '@/pages/export-preview/templates'

/**
 * 打印样卷 /print/sample-paper
 * 🔴 裸路由：不套 Shell（没有侧栏顶栏），整页就是纸，Ctrl+P 直接出 PDF。
 * 归属：页面组 I「模版库」。屏幕上才出现的东西一律加 className="no-print"。
 *
 * 版式本体在 ./paper.tsx —— 和模版库「专项卷 · 标准版」抽屉里的样张是同一份组件。
 * 🔴 这张纸是哪个模版、第几版，从模版库登记簿里取，不在这儿手写版本号（写两处必漂）。
 */

/** 本页出的纸对应哪张模版（模版库登记簿是唯一出处） */
const TPL = findTemplate(STANDARD_TPL_ID)

export default function PrintSamplePaper() {
  // 学生卷默认不带答案页；这里默认开，是为了走查时直接看到两页纸
  const [withAnswerSheet, setWithAnswerSheet] = useState(true)

  return (
    <div className="pp-root">
      <div className="no-print pp-toolbar">
        <Space size={16} wrap>
          <Button type="primary" onClick={() => window.print()}>
            打印 / 另存为 PDF
          </Button>
          <Space size={6}>
            <Switch size="small" checked={withAnswerSheet} onChange={setWithAnswerSheet} />
            <span className="pp-toolbar-note">附答案速查页（学生卷正式导出时关掉）</span>
          </Space>
          <Button href="/export-preview">返回模版库</Button>
          <span className="pp-toolbar-note">
            {TPL ? `模版：${TPL.name} ${TPL.version} · ` : ''}V2.1 原型 · mock 数据 · 设计稿评审版
          </span>
        </Space>
      </div>

      <SamplePaper withAnswerSheet={withAnswerSheet} />
    </div>
  )
}
