import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Shell from '@/layout/Shell'
import Workbench from '@/pages/workbench'
import Todo from '@/pages/todo'
import Questions from '@/pages/questions'
import QuestionDetail from '@/pages/question-detail'
import Artifacts from '@/pages/artifacts'
import Grading from '@/pages/grading'
import GradingQueue from '@/pages/grading-queue'
import GradingStudent from '@/pages/grading-student'
import ExportPreview from '@/pages/export-preview'
import PrintSamplePaper from '@/pages/print-sample-paper'
import Ingest from '@/pages/ingest'
import Review from '@/pages/review'
import Kg from '@/pages/kg'
import Model from '@/pages/model'
import Cause from '@/pages/cause'
import Criteria from '@/pages/criteria'
// 🔴 真库组：直连 kb.db 的只读页（与上面所有 mock 页并列不合并，改一边不影响另一边）
import KbQuestions from '@/pages/kb-questions'
import KbArtifacts from '@/pages/kb-artifacts'
import NotFound from '@/pages/not-found'

/**
 * 全站路由表（唯一一份）。页面组只改自己 pages/<目录>/index.tsx，**不要动本文件**；
 * 需要新路由先找地基工在这里挂，避免六个组各挂各的。
 */
export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 🔴 裸路由：不套 Shell（无侧栏无顶栏），专供打印/导出截图 */}
        <Route path="/print/sample-paper" element={<PrintSamplePaper />} />

        {/* 带壳的正常页面 */}
        <Route element={<Shell />}>
          <Route path="/" element={<Workbench />} />
          {/* 待办列表 = 自由事项表（定稿 D-14），与工作台那份「现算待办视图」并列不合并 */}
          <Route path="/todo" element={<Todo />} />
          <Route path="/questions" element={<Questions />} />
          <Route path="/questions/:id" element={<QuestionDetail />} />
          <Route path="/artifacts" element={<Artifacts />} />
          <Route path="/grading" element={<Grading />} />
          {/* 🔴 静态段必须写在 /grading/:code 之前：队列页不是某个学员代号 */}
          <Route path="/grading/queue" element={<GradingQueue />} />
          {/* 旧「待办」页退役：待办只是队列的一个筛子，老链接一律重定向过去 */}
          <Route path="/grading/todo" element={<Navigate to="/grading/queue?mine=1" replace />} />
          <Route path="/grading/:code" element={<GradingStudent />} />

          {/* 录入线：录入记录看进来了什么，审核台管谁来放行 */}
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/review" element={<Review />} />

          {/* 维护线：低频但必须记账的四样东西（判据沉淀 = 产线自己的判断经验，挂产线不挂考点） */}
          <Route path="/kg" element={<Kg />} />
          <Route path="/model" element={<Model />} />
          <Route path="/cause" element={<Cause />} />
          <Route path="/criteria" element={<Criteria />} />

          {/* 🔴 真库：走 /api/kb 薄读 API（node console/server/kb-read-api.mjs，:4310），只读无写口 */}
          <Route path="/kb/questions" element={<KbQuestions />} />
          <Route path="/kb/artifacts" element={<KbArtifacts />} />

          <Route path="/export-preview" element={<ExportPreview />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
