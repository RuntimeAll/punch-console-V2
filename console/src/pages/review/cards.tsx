import { useState } from 'react'
import { Alert, Button, Card, Checkbox, Collapse, Input, Radio, Space, Tag, Tooltip, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { BlockFlow } from '@/components'
import type { DoneMark } from './actions'
import type { ReviewTicket } from '@/mock'
import { findExamModel, findQuestion } from '@/mock'
import { LEVEL_COLOR, LEVEL_WORD, NEW_LEAF, SRC_WHY, payloadOf, srcLevelOf } from './actions'

/**
 * 审核台的四类工单卡。四类**长得不一样是故意的**——处理动作不同，卡就不该长一个样：
 * 图审要并排看图、题审转正要看整题、考点低置信要摆候选、隔离行要看原始记录。
 *
 * 三条共用纪律：
 * 🔴 detail = 工单原话，原样展示不截断（人审要判的就是这段原话，改写过的话没法判）。
 * 🔴 题目内容一律走 <BlockFlow>，图在题面第几段就渲在第几段，不许另起「配图区」。
 * 🔴 只出结论不干活：卡上的动作是「判成什么」，真改库/真重录都是 agent 侧的事。
 */

/** 卡片公共入参：t = 工单；onDone = 直接落判；onAsk = 要人写一句话（走弹窗必填） */
type CardProps = {
  t: ReviewTicket
  onDone: (t: ReviewTicket, action: string, note?: string) => void
  onAsk: (t: ReviewTicket, action: string, prompt: string) => void
}

const PRIORITY_COLOR: Record<ReviewTicket['priority'], string | undefined> = {
  高: 'red',
  中: 'gold',
  低: undefined,
}

/**
 * 来源等级：这条工单是从哪种源、哪一级审核等级来的（定稿 D-18 / D-21）。
 * 🔴 审之前先知道该用多大力气：文字层源有守恒基准（复核报警处即可），图片 OCR 源没有基准（逐图核），
 *   等级 L1 抽检看一眼就过、L3 逐题细审要对着原件抠。
 * 🔴 等级是**逐题**的：工单指不到批次里那一行（行级碎片 / 整题重录）时就不编一个等级出来，照实写。
 */
function SrcLevel({ t }: { t: ReviewTicket }) {
  const sl = srcLevelOf(t)
  return (
    <span className="rv-srclevel">
      <span className="rv-srclevel-k">来源等级</span>
      {sl ? (
        <Space size={4}>
          <Tooltip title={SRC_WHY[sl.srcKind]}>
            <Tag color={sl.srcKind === '图片OCR' ? 'orange' : undefined} style={{ marginInlineEnd: 0 }}>
              {sl.srcKind}
            </Tag>
          </Tooltip>
          {sl.level ? (
            <Tag color={LEVEL_COLOR[sl.level]} style={{ marginInlineEnd: 0 }}>
              {sl.level === '人工' ? '人工' : sl.level + ' · ' + LEVEL_WORD[sl.level]}
            </Tag>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
              未指到具体题（按批次口径审）
            </Typography.Text>
          )}
        </Space>
      ) : (
        <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
          无来源批次
        </Typography.Text>
      )}
    </span>
  )
}

/** 卡头：工单号 + 标题 + 优先级 + 现态 + 来源等级 + 建单日期 */
export function TicketHead({ t }: { t: ReviewTicket }) {
  return (
    <Space size={8} wrap style={{ paddingBlock: 2 }}>
      <Typography.Text style={{ fontFamily: 'monospace', fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
        {t.id}
      </Typography.Text>
      <span style={{ fontWeight: 500 }}>{t.title}</span>
      <Tag color={PRIORITY_COLOR[t.priority]} style={{ marginInlineEnd: 0 }}>
        {t.priority}优先
      </Tag>
      <Tag color={t.state === '处理中' ? 'blue' : undefined} style={{ marginInlineEnd: 0 }}>
        {t.state}
      </Tag>
      <SrcLevel t={t} />
      <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>
        {t.createdAt}
      </Typography.Text>
    </Space>
  )
}

/** 着落点：这条工单能点到哪去（批次 / 题 / 考察模型，至少有一个） */
export function TicketLinks({ t }: { t: ReviewTicket }) {
  const model = t.modelId ? findExamModel(t.modelId) : undefined
  return (
    <Space size={12} wrap style={{ fontSize: 12 }}>
      {t.batchId ? <Link to={`/ingest?batch=${t.batchId}`}>来源批次 {t.batchId}</Link> : null}
      {t.questionId ? <Link to={`/questions/${t.questionId}`}>题目 {t.questionId}</Link> : null}
      {model ? <Link to="/model">考察模型 {model.id}（{model.name}）</Link> : null}
    </Space>
  )
}

/** 工单原话（机器拦下时到底说了什么）——原样，不改写、不截断 */
export function Quote({ text }: { text: string }) {
  return (
    <div>
      <div className="rv-label">工单原话</div>
      <div className="rv-quote">{text}</div>
    </div>
  )
}

// ── ① 图审：左看图右核对 ────────────────────────────────────────────
const FIGURE_CHECKS = [
  { value: 'pos', label: '图与题同位：图排在题面文字的原位置，不是被甩到题尾' },
  { value: 'match', label: '图内容与题面对得上：图上的数值 / 标注与题面文字一致' },
  { value: 'origin', label: '按工单原话点名的那一处，已对照原卷 / 讲义确认' },
]

export function FigureReviewCard({ t, onDone, onAsk }: CardProps) {
  const q = t.questionId ? findQuestion(t.questionId) : undefined
  const [checked, setChecked] = useState<string[]>([])
  const allChecked = checked.length === FIGURE_CHECKS.length
  const canPass = Boolean(q) && allChecked

  return (
    <Card size="small" className="rv-card" title={<TicketHead t={t} />} style={{ marginBottom: 12 }}>
      <div className="rv-split">
        <div className="rv-left">
          <div className="rv-label">题面（块流原位混排，图在第几段就渲在第几段）</div>
          {q ? (
            <div className="rv-stem">
              <BlockFlow blocks={q.blocks} />
            </div>
          ) : (
            <Alert
              type="warning"
              showIcon
              message={`库里查不到 ${t.questionId ?? '这道题'}`}
              description="题不在库里就没法核图，只能驳回让 agent 重投。"
            />
          )}
          {q ? (
            <Collapse
              size="small"
              style={{ marginTop: 10 }}
              defaultActiveKey={[]}
              items={[
                {
                  key: 'more',
                  label: '答案 / 解析（解析里也可能有图，一并核）',
                  children: (
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <div>
                        <div className="rv-label">答案</div>
                        <BlockFlow blocks={q.answerBlocks} size="compact" />
                      </div>
                      <div>
                        <div className="rv-label">解析</div>
                        <BlockFlow blocks={q.analysisBlocks} size="compact" />
                      </div>
                    </Space>
                  ),
                },
              ]}
            />
          ) : null}
        </div>

        <div className="rv-right">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Quote text={t.detail} />
            <div>
              <div className="rv-label">核对要点（三条都核过才给通过）</div>
              <Checkbox.Group value={checked} onChange={(v) => setChecked(v as string[])}>
                <Space direction="vertical" size={4}>
                  {FIGURE_CHECKS.map((c) => (
                    <Checkbox key={c.value} value={c.value} style={{ fontSize: 13 }}>
                      {c.label}
                    </Checkbox>
                  ))}
                </Space>
              </Checkbox.Group>
            </div>
            <TicketLinks t={t} />
            <Space size={8}>
              <Tooltip title={canPass ? '' : q ? '三条核对要点还没勾完' : '题不在库里，不能通过'}>
                <Button type="primary" disabled={!canPass} onClick={() => onDone(t, '通过')}>
                  通过
                </Button>
              </Tooltip>
              <Button
                danger
                onClick={() => onAsk(t, '驳回', '驳回理由（必填）：哪儿对不上、要 agent 怎么改。写不清楚，下一个人接不住。')}
              >
                驳回
              </Button>
            </Space>
          </Space>
        </div>
      </div>
    </Card>
  )
}

// ── ② 题审转正：草稿题看整题再定去留 ────────────────────────────────
export function PromoteCard({ t, onDone, onAsk }: CardProps) {
  const q = t.questionId ? findQuestion(t.questionId) : undefined

  return (
    <Card size="small" className="rv-card" title={<TicketHead t={t} />} style={{ marginBottom: 12 }}>
      <div className="rv-split">
        <div className="rv-left">
          {q ? (
            <>
              <div className="rv-label">
                草稿题 {q.id}
                {/* 状态四态直接照渲（草稿/已审/上架/退役），别在页面里再翻译一次 */}
                <Tag style={{ marginInlineStart: 6 }}>{q.status}</Tag>
              </div>
              <div className="rv-stem">
                <BlockFlow blocks={q.blocks} />
              </div>
              <Collapse
                size="small"
                style={{ marginTop: 10 }}
                defaultActiveKey={['ans']}
                items={[
                  {
                    key: 'ans',
                    label: '答案 / 解析（转正前必须是补齐的）',
                    children: (
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <div>
                          <div className="rv-label">答案</div>
                          <BlockFlow blocks={q.answerBlocks} size="compact" />
                        </div>
                        <div>
                          <div className="rv-label">解析</div>
                          <BlockFlow blocks={q.analysisBlocks} size="compact" />
                        </div>
                      </Space>
                    ),
                  },
                ]}
              />
            </>
          ) : (
            <Alert
              type="info"
              showIcon
              message="这条工单没有已入库的题"
              description="题还没成题（或口径打架要整题重录），只能按工单原话与批次账判：定稿一个口径交 agent 重录，或直接驳回不录。"
            />
          )}
        </div>

        <div className="rv-right">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Quote text={t.detail} />
            <TicketLinks t={t} />
            <Space size={8} wrap>
              {q ? (
                <Button type="primary" onClick={() => onDone(t, '转正', `${q.id} 由草稿转为在用`)}>
                  转正（放进在用）
                </Button>
              ) : (
                <Button
                  type="primary"
                  onClick={() =>
                    onAsk(
                      t,
                      '定稿口径',
                      '定稿口径（必填）：这题最终按哪个答案 / 哪种算法算。agent 按这一条重录整题，写不清楚就等于没定。',
                    )
                  }
                >
                  定稿口径，交 agent 重录
                </Button>
              )}
              <Button
                danger
                onClick={() => onAsk(t, '驳回', '驳回理由（必填）：为什么不录这题（条件不足 / 原卷有误 / 重复题）。')}
              >
                驳回
              </Button>
            </Space>
          </Space>
        </div>
      </div>
    </Card>
  )
}

// ── ③ 考点低置信：从候选里定一个，或建新叶子 ────────────────────────
export function LowConfCard({ t, onDone, onAsk }: CardProps) {
  const q = t.questionId ? findQuestion(t.questionId) : undefined
  const [picked, setPicked] = useState<string>('')
  const [leafName, setLeafName] = useState<string>('')
  const isNew = picked === NEW_LEAF
  const canConfirm = picked !== '' && (!isNew || leafName.trim() !== '')

  const confirm = () => {
    if (isNew) onDone(t, '建新叶子', `新叶子：${leafName.trim()}`)
    else onDone(t, '收编为别名', `收编到：${picked}`)
  }

  return (
    <Card size="small" className="rv-card" title={<TicketHead t={t} />} style={{ marginBottom: 12 }}>
      <div className="rv-split">
        <div className="rv-left">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Quote text={t.detail} />
            {q ? (
              <div>
                <div className="rv-label">这道题（{q.id}）</div>
                <div className="rv-stem">
                  <BlockFlow blocks={q.blocks} size="compact" />
                </div>
              </div>
            ) : (
              <Alert
                type="info"
                showIcon
                message="这题还没入库"
                description="没有 questionId，着落点在考察模型上——模型先定名，考点叶才好定名。"
              />
            )}
          </Space>
        </div>

        <div className="rv-right">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <div>
              <div className="rv-label">当时的检索候选（按置信度从高到低），选一个：</div>
              <Radio.Group value={picked} onChange={(e) => setPicked(e.target.value)}>
                <Space direction="vertical" size={4}>
                  {(t.candidates ?? []).map((c) => (
                    <Radio key={c} value={c} style={{ fontSize: 13 }}>
                      {c}
                    </Radio>
                  ))}
                  {/* 🔴 必须留这一项：候选全不对时，人审的动作是建新叶子，不是硬挑一个凑合 */}
                  <Radio value={NEW_LEAF} style={{ fontSize: 13 }}>
                    都不对，建新叶子
                  </Radio>
                </Space>
              </Radio.Group>
            </div>

            {isNew ? (
              <Input
                value={leafName}
                onChange={(e) => setLeafName(e.target.value)}
                placeholder="新叶子名（如：破十法）"
                maxLength={30}
              />
            ) : null}

            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              收编为别名 = 把机器的这个说法挂到选中的叶子下当别名，下次同类题直接命中；建新叶子 =
              教材树上真加一片叶。两个动作都只出结论，改树是 agent 的事。
            </Typography.Text>

            <TicketLinks t={t} />
            <Space size={8}>
              <Tooltip title={canConfirm ? '' : isNew ? '先写新叶子名' : '先从候选里选一个'}>
                <Button type="primary" disabled={!canConfirm} onClick={confirm}>
                  {isNew ? '建新叶子' : '收编为别名'}
                </Button>
              </Tooltip>
              <Button
                danger
                onClick={() => onAsk(t, '驳回', '驳回理由（必填）：为什么这几个候选都不用、也不建叶子（如：这题该重打标 / 该退回重录）。')}
              >
                驳回
              </Button>
            </Space>
          </Space>
        </div>
      </div>
    </Card>
  )
}

// ── ④ 隔离行：看原始记录再定改判还是废弃 ────────────────────────────
export function QuarantineCard({ t, onAsk }: CardProps) {
  return (
    <Card size="small" className="rv-card" title={<TicketHead t={t} />} style={{ marginBottom: 12 }}>
      <div className="rv-split">
        <div className="rv-left">
          <div className="rv-label">红灯原始记录（工单 payload，折叠）</div>
          <Collapse
            size="small"
            defaultActiveKey={[]}
            items={[
              {
                key: 'payload',
                label: `${t.id} · JSON 原始记录`,
                children: <pre className="rv-pre">{payloadOf(t)}</pre>,
              },
            ]}
          />
        </div>

        <div className="rv-right">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            <Quote text={t.detail} />
            <TicketLinks t={t} />
            <Space size={8} wrap>
              <Button
                type="primary"
                onClick={() =>
                  onAsk(
                    t,
                    '改判重投',
                    '改判成什么（必填）：这行归位到第几题 / 重投到哪个批次。agent 照这句执行，含糊就等于没判。',
                  )
                }
              >
                改判重投
              </Button>
              <Button danger onClick={() => onAsk(t, '废弃', '废弃理由（必填）：这行为什么可以扔（重复 / 图注 / 页眉页脚）。')}>
                废弃
              </Button>
            </Space>
          </Space>
        </div>
      </div>
    </Card>
  )
}

// ── 已处理区：本轮点过的工单收在这儿，随时回看判了什么 ──────────────
export function DoneList({ tickets, marks }: { tickets: ReviewTicket[]; marks: Record<string, DoneMark> }) {
  if (tickets.length === 0) return null
  return (
    <Collapse
      size="small"
      defaultActiveKey={[]}
      style={{ marginTop: 4 }}
      items={[
        {
          key: 'done',
          label: `已处理（${tickets.length}）`,
          children: (
            <div>
              {tickets.map((t) => {
                const m = marks[t.id]
                return (
                  <div className="rv-done-row" key={t.id}>
                    <Space size={8} wrap>
                      <Typography.Text style={{ fontFamily: 'monospace', fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
                        {t.id}
                      </Typography.Text>
                      <span>{t.title}</span>
                      <Tag color={m.action === '驳回' || m.action === '废弃' ? 'red' : 'green'} style={{ marginInlineEnd: 0 }}>
                        {m.action}
                      </Tag>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {m.at}
                      </Typography.Text>
                    </Space>
                    {m.note ? <div className="rv-done-note">{m.note}</div> : null}
                  </div>
                )
              })}
            </div>
          ),
        },
      ]}
    />
  )
}
