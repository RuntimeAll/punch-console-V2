import type { Block, Question } from '@/mock'
import { BlockFlow } from '@/components'
import { filterRows, findQuestion, firstTextOf, rowStartsWith } from '@/mock'
import './print-paper.css'

/**
 * 样卷本体（纯内容，无壳无工具条）。
 *
 * 一份定义两处用：
 * - `/print/sample-paper` 裸路由 —— 真出纸；
 * - `/export-preview` 主区 —— 屏幕上的 A4 纸样预览。
 * 🔴 两处必须是同一份组件，否则「预览好看、打出来两样」就是评审现场翻车。
 */

/** 卷面固定文案（页眉 / 卷名 / 页脚都从这里取，改名只改一处） */
export const PAPER_BRAND = '玉米训练营'
export const PAPER_TITLE = '角度与图形专练'
export const PAPER_SUBTITLE = '四年级上册 · 空间与图形'
export const PAPER_HEADER = `${PAPER_BRAND} · 四年级上册 · 专项练`

/**
 * 选题与分组（原型阶段写死；将来这份结构由「选题面板」产出）。
 * 🔴 题目内容一律从 @/mock 按 id 取，不在本文件里另抄一份题面。
 */
const GROUP_DEFS: { name: string; hint: string; ids: string[] }[] = [
  {
    name: '一、填空题',
    hint: '把答案直接填在括号里',
    ids: ['q-4008', 'q-4009', 'q-4010', 'q-4001'],
  },
  {
    name: '二、解答题',
    hint: '写出必要的计算过程',
    ids: ['q-4005', 'q-4007'],
  },
]

interface PaperGroup {
  name: string
  hint: string
  items: { no: number; q: Question }[]
}

/** 组装分组 + 全卷连续题号（1..N，跨组不重编） */
function buildGroups(): PaperGroup[] {
  let no = 0
  return GROUP_DEFS.map((g) => ({
    name: g.name,
    hint: g.hint,
    items: g.ids
      .map((id) => findQuestion(id))
      .filter((q): q is Question => Boolean(q))
      .map((q) => ({ no: (no += 1), q })),
  }))
}

export const paperGroups: PaperGroup[] = buildGroups()

/** 全卷题量（页眉副标题与说明卡都用它，别手写数字） */
export const paperTotal: number = paperGroups.reduce((s, g) => s + g.items.length, 0)

const HINT_PREFIX = '【方法点拨】'

/**
 * 答案页口径：把答案块流拆成「答案主体」+「一句方法点拨」。
 * - 题目自带 `【方法点拨】…` 行的（如 q-4001），直接用它；
 * - 没带的，取解析首行的第一句充当点拨 —— 这是**展示层派生**，不回写 mock。
 *
 * 🔴 块流 v2 起按**行**（rows）拆：拆完的仍是一份合法块流（filterRows 保证 v/rows 形状不变），
 * 直接丢给 <BlockFlow> 渲，别在这里把行拍成字符串。
 */
function splitAnswer(q: Question): { answer: Block; hint: string } {
  const answer = filterRows(q.answerBlocks, (r) => !rowStartsWith(r, HINT_PREFIX))
  const hintRow = q.answerBlocks.rows.find((r) => rowStartsWith(r, HINT_PREFIX))

  let hint = ''
  if (hintRow) hint = firstTextOf({ v: 2, rows: [hintRow] }, '').slice(HINT_PREFIX.length).trim()
  if (!hint) {
    const head = firstTextOf(q.analysisBlocks, '').split('。')[0]
    hint = head ? `${head}。` : ''
  }
  return { answer, hint }
}

/** 页脚：玉米训练营 · <卷名> · 第 N 页 / 共 M 页 */
function Footer({ page, total }: { page: number; total: number }) {
  return (
    <footer className="pp-footer">
      <span>{`${PAPER_BRAND} · ${PAPER_TITLE} · 第 ${page} 页 / 共 ${total} 页`}</span>
    </footer>
  )
}

/**
 * 两页纸样。
 * @param withAnswerSheet 是否附答案速查页。🔴 学生卷默认不带答案页，
 *        这里默认 true 是为了走查时一眼看到两页；正式导出由选题面板的开关决定。
 */
export function SamplePaper({ withAnswerSheet = true }: { withAnswerSheet?: boolean }) {
  const totalPages = withAnswerSheet ? 2 : 1

  return (
    <>
      {/* ── 页 1：题目卷 ─────────────────────────────── */}
      <section className="print-sheet pp-sheet">
        <div className="pp-header">{PAPER_HEADER}</div>

        <div className="pp-titlebar">
          <h2 className="pp-title">{PAPER_TITLE}</h2>
          <p className="pp-subtitle">{`${PAPER_SUBTITLE} · 共 ${paperTotal} 题`}</p>
        </div>

        <div className="pp-idline">
          <span>
            姓名 <i className="pp-blank pp-blank-name" />
          </span>
          <span>
            日期 <i className="pp-blank pp-blank-date" />
          </span>
          <span>
            用时 <i className="pp-blank pp-blank-time" /> 分钟
          </span>
        </div>

        <div className="pp-body">
          {paperGroups.map((g) => (
            <div key={g.name}>
              <div className="pp-group">
                <span className="pp-group-name">{g.name}</span>
                <span className="pp-group-hint">{`${g.hint}（共 ${g.items.length} 题）`}</span>
              </div>

              {g.items.map(({ no, q }) => (
                <div className="print-item pp-item" key={q.id}>
                  <div className="pp-qno">{no}.</div>
                  <div className="pp-qbody">
                    {/* 🔴 题面与配图一起混排：图在第几块就渲在第几块 */}
                    <BlockFlow blocks={q.blocks} />
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>

        <Footer page={1} total={totalPages} />
      </section>

      {/* ── 页 2：答案速查页（可选，默认不随学生卷下发）───── */}
      {withAnswerSheet ? (
        <section className="print-sheet pp-sheet">
          <div className="pp-header">{PAPER_HEADER}</div>

          <div className="pp-anshead">
            <h2 className="pp-anstitle">参考答案 · 速查</h2>
            <span className="pp-ansnote">教师留存，默认不随学生卷下发</span>
          </div>

          <div className="pp-body">
            {paperGroups.flatMap((g) =>
              g.items.map(({ no, q }) => {
                const { answer, hint } = splitAnswer(q)
                return (
                  <div className="print-item pp-ans-item" key={q.id}>
                    <div className="pp-qno">{no}.</div>
                    <div className="pp-qbody">
                      {/* 答案也是块流，同样走 BlockFlow（答案里若有图照样原位混排） */}
                      <BlockFlow blocks={answer} />
                      {hint ? <p className="pp-hint">点拨：{hint}</p> : null}
                    </div>
                  </div>
                )
              }),
            )}
          </div>

          <Footer page={2} total={totalPages} />
        </section>
      ) : null}
    </>
  )
}

export default SamplePaper
