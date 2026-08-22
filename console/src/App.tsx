import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Shell from '@/layout/Shell'
import Workbench from '@/pages/workbench'
import Todo from '@/pages/todo'
import Grading from '@/pages/grading'
import GradingQueue from '@/pages/grading-queue'
import GradingStudent from '@/pages/grading-student'
import Ingest from '@/pages/ingest'
import Review from '@/pages/review'
import Cause from '@/pages/cause'
// 正式页组：直连 kb.db 的只读真库页（2026-08-21 用户令转正——覆盖原 mock 路由，不再「·真库」并列）
import KbQuestions from '@/pages/kb-questions'
import KbArtifacts from '@/pages/kb-artifacts'
import KbPapersPage from '@/pages/kb-papers'
import KbDeliverablesPage from '@/pages/kb-deliverables'
import KbKg from '@/pages/kb-kg'
import KbModelsPage from '@/pages/kb-models'
import KbCriteriaPage from '@/pages/kb-criteria'
import KbTemplatesPage from '@/pages/kb-templates'
import NotFound from '@/pages/not-found'

/** 老地址搬家：保住查询串（/kb/papers?paper=xxx 这类直链散在报告里，断了找不回） */
function RedirectQ({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={{ pathname: to, search }} replace />
}

/**
 * 全站路由表（唯一一份）。页面组只改自己 pages/<目录>/index.tsx，**不要动本文件**；
 * 需要新路由先找地基工在这里挂，避免各组各挂各的。
 *
 * 🔴 2026-08-21 真库转正（用户令「真库直接覆盖回去」）：
 * - 正式路由 = 真库页：/questions /artifacts /papers /kg /model /criteria /templates；
 * - 被覆盖的 mock 页（questions/question-detail/artifacts/kg/model/criteria/export-preview/
 *   print-sample-paper）**摘路由退役**，源文件留在 pages/ 原地不删（cause 还 import 着
 *   kg/KpTraceLink 等件，动文件必断 build；真正清尾等各线真库化时一并做）；
 * - 未去 mock 的页收进导航「待办」组，路由原地不动：/ /todo /grading* /ingest /review /cause。
 */
export function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 带壳的正常页面 */}
        <Route element={<Shell />}>
          {/* ── 正式页（真库只读，走 /api/kb 薄读 API，:4310） ── */}
          <Route path="/questions" element={<KbQuestions />} />
          <Route path="/artifacts" element={<KbArtifacts />} />
          <Route path="/papers" element={<KbPapersPage />} />
          {/* 成品速览：artifact.files_json 拉平成一件一行，点行直接预览（成品库/ 下的原文件） */}
          <Route path="/deliverables" element={<KbDeliverablesPage />} />
          <Route path="/kg" element={<KbKg />} />
          <Route path="/model" element={<KbModelsPage />} />
          <Route path="/criteria" element={<KbCriteriaPage />} />
          <Route path="/templates" element={<KbTemplatesPage />} />

          {/* ── 老地址重定向（真库转正前的 /kb/* 与旧模版库地址，一律带查询串搬家） ── */}
          <Route path="/kb/questions" element={<RedirectQ to="/questions" />} />
          <Route path="/kb/artifacts" element={<RedirectQ to="/artifacts" />} />
          <Route path="/kb/papers" element={<RedirectQ to="/papers" />} />
          <Route path="/kb/kg" element={<RedirectQ to="/kg" />} />
          <Route path="/kb/models" element={<RedirectQ to="/model" />} />
          <Route path="/kb/criteria" element={<RedirectQ to="/criteria" />} />
          <Route path="/kb/templates" element={<RedirectQ to="/templates" />} />
          <Route path="/export-preview" element={<RedirectQ to="/templates" />} />
          {/* mock 题目详情页已退役；老链接落回真库题库列表（mock 假 id 在真库本就无详情可看） */}
          <Route path="/questions/:id" element={<Navigate to="/questions" replace />} />

          {/* ── 待办 · 未去 mock（各归 PRD-005/006 等线，真库化后逐页转正） ── */}
          <Route path="/" element={<Workbench />} />
          {/* 待办列表 = 自由事项表（定稿 D-14），与工作台那份「现算待办视图」并列不合并 */}
          <Route path="/todo" element={<Todo />} />
          <Route path="/grading" element={<Grading />} />
          {/* 🔴 静态段必须写在 /grading/:code 之前：队列页不是某个学员代号 */}
          <Route path="/grading/queue" element={<GradingQueue />} />
          {/* 旧「待办」页退役：待办只是队列的一个筛子，老链接一律重定向过去 */}
          <Route path="/grading/todo" element={<Navigate to="/grading/queue?mine=1" replace />} />
          <Route path="/grading/:code" element={<GradingStudent />} />
          {/* 录入线：录入记录看进来了什么，审核台管谁来放行 */}
          <Route path="/ingest" element={<Ingest />} />
          <Route path="/review" element={<Review />} />
          {/* 错因管理沉淀「学生的错」（挂考点），与判据沉淀（产线自己的判断经验）两页别混 */}
          <Route path="/cause" element={<Cause />} />

          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
