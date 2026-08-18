import { useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Segmented,
  Space,
  Switch,
  Tag,
  Typography,
} from 'antd'
import { Link, useSearchParams } from 'react-router-dom'
import { PageFrame } from '@/components'
import { SamplePaper, paperGroups } from '@/pages/print-sample-paper/paper'
import type { PaperTemplate } from './templates'
import { STANDARD_TPL_ID, TEMPLATES, findTemplate } from './templates'
import './preview.css'

/**
 * 模版库 /export-preview（路由沿用旧名，定位已换）
 * 归属：页面组 I「模版库」。
 *
 * 🔴 第三轮判词④：**渲染永远在 agent 本地跑（HTML → Chrome → PDF），系统只登记模版与样张。**
 *    所以这页**不是导出器、不是渲染器**，是模版的**货架**：
 *      一张模版一张卡（干什么用 / 适用哪种册 / 参数是什么 / 第几版 / 还在不在用），
 *      点开抽屉看参数全表和样张。页面只读，不生成任何文件。
 *
 * 🔴 「专项卷 · 标准版」的样张是页面里内嵌的真组件 <SamplePaper>——和 /print/sample-paper
 *    出纸用的是同一份，防止「预览好看、打出来两样」。其余模版的样张位是占位图，
 *    等 agent 本地渲完登记回来才有图（这就是本页的诚实边界）。
 */

type StatusFilter = '全部' | '在用' | '停用'

const STATUS_FILTERS: StatusFilter[] = ['全部', '在用', '停用']

/** 状态 → Tag 颜色（只用 antd 默认色板，不铺大色块） */
const statusColor: Record<PaperTemplate['status'], string> = {
  在用: 'green',
  停用: 'default',
}

export default function ExportPreview() {
  // ── 货架筛选 ─────────────────────────────────────────────
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('全部')

  // ── 抽屉：当前打开的模版卡 ────────────────────────────────
  const [current, setCurrent] = useState<PaperTemplate | null>(null)
  // 样张观感（只对内嵌样张有效）：缩放不影响打印，打印永远按真实 A4 走
  const [zoom, setZoom] = useState(65)
  // 学生卷默认不带答案页；样张里默认开，方便走查一眼看到两页
  const [withAnswerSheet, setWithAnswerSheet] = useState(true)

  /**
   * 🔴 跨页约定：题目详情页「在模版库中查看」带 ?pick=<题号> 过来。
   * 原型阶段样卷选题写死在 paper.tsx 的 GROUP_DEFS（选题面板不归本页做），
   * 所以这里只**如实交代**这道题在不在标准版样张里，不假装能动态选题。
   */
  const [searchParams] = useSearchParams()
  const pick = searchParams.get('pick')
  const pickedNo = pick
    ? (paperGroups.flatMap((g) => g.items).find((it) => it.q.id === pick)?.no ?? null)
    : null

  const shown = useMemo(
    () => (statusFilter === '全部' ? TEMPLATES : TEMPLATES.filter((t) => t.status === statusFilter)),
    [statusFilter],
  )

  const inUse = TEMPLATES.filter((t) => t.status === '在用').length
  const withSample = TEMPLATES.filter((t) => t.sample === 'live').length

  return (
    <PageFrame
      title="模版库"
      desc="渲染永远在 agent 本地跑（HTML → Chrome → PDF），系统只登记模版与样张——本页不是渲染器，是模版的货架。"
      extra={
        <Space size={8} wrap>
          <Segmented
            size="small"
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as StatusFilter)}
            options={STATUS_FILTERS.map((s) => ({ label: s, value: s }))}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            共 {TEMPLATES.length} 张 · 在用 {inUse} · 已登记样张 {withSample}
          </Typography.Text>
        </Space>
      }
    >
      {/* 从题库带题过来时的如实交代（不假装能动态选题） */}
      {pick ? (
        <Alert
          type={pickedNo ? 'success' : 'warning'}
          showIcon
          style={{ marginBottom: 12 }}
          message={
            pickedNo
              ? `从题库带来的题 ${pick}：「专项卷 · 标准版」的样张里第 ${pickedNo} 题就是它。`
              : `从题库带来的题 ${pick}：不在标准版样张的选题里（原型阶段样张选题写死，选题不归模版库管）。`
          }
          action={
            <Space size={8}>
              <Button size="small" onClick={() => setCurrent(findTemplate(STANDARD_TPL_ID) ?? null)}>
                看样张
              </Button>
              <Link to={`/questions/${pick}`}>回到该题</Link>
            </Space>
          }
        />
      ) : null}

      {/* ① 模版卡片栅格 ─────────────────────────────────── */}
      <div className="ep-grid">
        {shown.map((t) => (
          <Card
            key={t.id}
            size="small"
            hoverable
            className="ep-card"
            onClick={() => setCurrent(t)}
            title={
              <Space size={6} wrap>
                <span>{t.name}</span>
                <Tag style={{ marginInlineEnd: 0 }}>{t.version}</Tag>
              </Space>
            }
            extra={
              <Tag color={statusColor[t.status]} style={{ marginInlineEnd: 0 }}>
                {t.status}
              </Tag>
            }
          >
            <p className="ep-purpose">{t.purpose}</p>

            <div className="ep-fit">
              <span className="ep-k">适用</span>
              {t.fitFor}
            </div>

            {/* 参数摘要四项：纸张 / 边距 / 字号 / 题距（全表在抽屉里） */}
            <div className="ep-brief">
              <div>
                <span className="ep-k">纸张</span>
                {t.brief.paper}
              </div>
              <div>
                <span className="ep-k">边距</span>
                {t.brief.margin}
              </div>
              <div>
                <span className="ep-k">字号</span>
                {t.brief.font}
              </div>
              <div>
                <span className="ep-k">题距</span>
                {t.brief.gap}
              </div>
            </div>

            <div className="ep-cardfoot">
              <span className="ep-note">
                {t.sample === 'live' ? '样张已登记' : '样张待登记'}
              </span>
              <Typography.Link>看参数与样张</Typography.Link>
            </div>
          </Card>
        ))}
      </div>

      {/* ② 页尾：新模版怎么来 ──────────────────────────── */}
      <Card size="small" className="ep-howto" title="新模版怎么来">
        <div className="ep-flow">
          <span className="ep-flow-step">① agent 本地把版式调好（HTML → Chrome → PDF，反复出纸看效果）</span>
          <span className="ep-flow-arrow">→</span>
          <span className="ep-flow-step">② 调稳了登记进模版库（参数 + 一页样张）</span>
          <span className="ep-flow-arrow">→</span>
          <span className="ep-flow-step">③ 这里可见，出货时照着挑</span>
        </div>
        <p className="ep-note" style={{ marginTop: 8, marginBottom: 0 }}>
          登记动作归 agent，本页只读：不新建、不改参数、不生成 PDF。模版停用了也不删——已经发出去的册子还是老版式，删了对不上账。
        </p>
      </Card>

      {/* ③ 模版抽屉：参数全表 + 样张区 ──────────────────── */}
      <Drawer
        title={current ? `${current.name} · ${current.version}` : ''}
        width="min(940px, 94vw)"
        open={Boolean(current)}
        onClose={() => setCurrent(null)}
        destroyOnHidden
        extra={
          current?.sample === 'live' ? (
            <Button type="primary" href="/print/sample-paper" target="_blank" rel="noreferrer">
              打开打印视图
            </Button>
          ) : null
        }
      >
        {current ? (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="模版编号">{current.id}</Descriptions.Item>
              <Descriptions.Item label="用途">{current.purpose}</Descriptions.Item>
              <Descriptions.Item label="适用册型">{current.fitFor}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColor[current.status]}>{current.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="登记时间">{current.registeredAt}</Descriptions.Item>
              <Descriptions.Item label="登记来源">{current.registeredBy}</Descriptions.Item>
            </Descriptions>

            <Typography.Title level={5} className="ep-h">
              版式参数全表
            </Typography.Title>
            <Descriptions size="small" column={1} bordered>
              {current.params.map((p) => (
                <Descriptions.Item key={p.label} label={p.label}>
                  {p.value}
                </Descriptions.Item>
              ))}
            </Descriptions>

            <Typography.Title level={5} className="ep-h">
              口径与坑
            </Typography.Title>
            <p className="ep-desc">{current.note}</p>

            <Typography.Title level={5} className="ep-h">
              样张
            </Typography.Title>

            {current.sample === 'live' ? (
              <>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginBottom: 10 }}
                  message="下面这张纸是按真实尺寸画的 A4（210mm 宽），用的就是 /print/sample-paper 出纸那份组件。缩放只改屏幕观感，打印仍按 100% 出纸。"
                />

                <div className="ep-bar">
                  <Space size={6}>
                    <Switch size="small" checked={withAnswerSheet} onChange={setWithAnswerSheet} />
                    <span className="ep-note">附答案速查页（学生卷正式出纸时关掉）</span>
                  </Space>
                  <Space size={8}>
                    <span className="ep-note">预览缩放</span>
                    <Segmented
                      size="small"
                      value={zoom}
                      onChange={(v) => setZoom(Number(v))}
                      options={[
                        { label: '100%', value: 100 },
                        { label: '80%', value: 80 },
                        { label: '65%', value: 65 },
                      ]}
                    />
                  </Space>
                </div>

                <div className="ep-stage">
                  <div className={`ep-zoom ep-z${zoom}`}>
                    <SamplePaper withAnswerSheet={withAnswerSheet} />
                  </div>
                </div>
              </>
            ) : (
              <div className="ep-sample-pending">
                <div className="ep-sample-mark">A4</div>
                <div className="ep-sample-title">样张待 agent 渲染登记</div>
                <p className="ep-sample-desc">
                  这张模版的 HTML 在 agent 本地调好后跑一次 Chrome 出 PDF，再把首页样张登记回来，这里才有图可看。
                  <br />
                  页面自己不渲染、不出 PDF——参数表已经登记了，先照表核。
                </p>
              </div>
            )}
          </>
        ) : null}
      </Drawer>
    </PageFrame>
  )
}
