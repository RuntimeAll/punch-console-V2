import { useMemo, useState } from 'react'
import { Alert, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ErrCodeMapEntry, ErrorCause } from '@/mock'
import { ambiguousCodes, errCodeMap, kpNameOf, resolveErrCode } from '@/mock'
// 🔴 溯源换算的唯一实现在 kg 组，本页单向依赖（见 kg/trace.ts 顶部的依赖方向说明）
import { KpTraceLink } from '@/pages/kg/KpTraceLink'

/**
 * 页签③：错因码翻译表（数据结构.md §2.3 err_code_map）。
 * 归属：维护组「错因管理」自用。
 *
 * 🔴 它在链条上的位置：批改脚本吐出来的是**局部码**（dist / order / sign…），
 *   要落成沉淀里的错因，中间必须过这张表。所以它是**批改回流的接线口**——
 *   接错了，沉淀就归错类，学情跟着歪。
 *
 * 🔴🔴 主键是**复合键 (考点, 码)**，不是 code 一个字段。理由是实锤不是洁癖：
 *   产线码 dist 在「混合运算」线 = 运算律简算用错，在「整式」线 = 去括号/合并同类项出错。
 *   **同码两义**，而这个歧义已经印进过学员交付报告。无作用域的 (码→错因) 映射必然串义。
 *   ⇒ 页面必须把这对**并排摆出来**：不摆，看表的人永远理解不了为什么键要带考点。
 *
 * 🔴 kpId 为空串 = **通用兜底**（跨考点都成立的码，如誊写笔误）：
 *   只有带作用域的键都没命中时才允许落到它，绝不能反过来拿它去盖住有作用域的映射
 *   （resolveErrCode 的查找顺序就是这条纪律的实现，「试一条」小工具演的就是它）。
 */

/** 「试一条」的默认选择：写死常量，不许用 Date.now / 随机（mock 必须每次长一样） */
const DEMO_KP = 'renjiao/g4a/u4/s4/k1'
const DEMO_CODE = 'dist'
/** 表里**没有**登记的一片叶，专供演示「查不到就如实说查不到，不猜」 */
const OFF_MAP_KP = 'renjiao/g4a/u5/s4/k1'

/** 同码两义那几行的底色。🔴 「禁大色块」：只给最浅一档的提示底 */
const HIT_BG = '#fafafa'

export function ErrCodeMapTab({
  causes,
  onJumpToCause,
}: {
  /** 错因词表（含本页临时新增的），用来把 causeId 翻成错因名 */
  causes: ErrorCause[]
  /** 点「翻成的错因」跳回错因库页签并高亮那条（与沉淀页签同一条溯源链） */
  onJumpToCause: (causeId: string) => void
}) {
  const nameOfCause = useMemo(() => Object.fromEntries(causes.map((c) => [c.id, c.name])), [causes])

  /** 一码多义（同一个码翻成不同错因）——这是「为什么键要带考点」的现场证据，不是异常 */
  const ambiguous = useMemo(() => ambiguousCodes(), [])
  const ambiguousCodeSet = useMemo(() => new Set(ambiguous.map((a) => a.code)), [ambiguous])

  /**
   * 一码多**域**但同义（如 carry 在乘法线说进位、在除法线说退位，都归「进退位错」）。
   * 🔴 与「一码两义」分开标：这类不是歧义，只是同一条错因在两片叶上各登记了一条注解，
   *   混成一种说法会让人以为翻译表到处都在打架。
   */
  const multiScopeCodes = useMemo(() => {
    const byCode = new Map<string, ErrCodeMapEntry[]>()
    for (const e of errCodeMap) {
      const hit = byCode.get(e.code)
      if (hit) hit.push(e)
      else byCode.set(e.code, [e])
    }
    const acc = new Set<string>()
    for (const [code, list] of byCode) {
      if (list.length > 1 && !ambiguousCodeSet.has(code)) acc.add(code)
    }
    return acc
  }, [ambiguousCodeSet])

  // ── 「试一条」小工具：现场演一遍 resolveErrCode 的查找顺序 ──────────────
  const [tryKp, setTryKp] = useState(DEMO_KP)
  const [tryCode, setTryCode] = useState(DEMO_CODE)

  const kpOptions = useMemo(() => {
    const ids = Array.from(new Set(errCodeMap.map((e) => e.kpId).filter((id) => id !== '')))
    // 🔴 额外挂一片**表里没登记**的叶：不给这个选项就演不出「查不到」这一态
    if (!ids.includes(OFF_MAP_KP)) ids.push(OFF_MAP_KP)
    return ids.map((id) => ({ value: id, label: kpNameOf(id) }))
  }, [])

  const codeOptions = useMemo(
    () => Array.from(new Set(errCodeMap.map((e) => e.code))).map((c) => ({ value: c, label: c })),
    [],
  )

  const tried = resolveErrCode(tryKp, tryCode)

  const columns: ColumnsType<ErrCodeMapEntry> = [
    {
      // 🔴 作用域是这张表的命根子：没有它，dist 那两行就成了自相矛盾的重复行
      title: '作用域考点',
      key: 'kpId',
      width: 230,
      render: (_, e) =>
        e.kpId === '' ? (
          <Typography.Text
            type="secondary"
            style={{ fontSize: 12 }}
            title="kpId 为空串 = 通用兜底：只有带作用域的键都没命中时才允许落到它，绝不能反过来盖住有作用域的映射"
          >
            不限考点（通用兜底）
          </Typography.Text>
        ) : (
          <div>
            <KpTraceLink name={kpNameOf(e.kpId)} />
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12, fontFamily: 'monospace' }}>
                {e.kpId}
              </Typography.Text>
            </div>
          </div>
        ),
    },
    {
      title: '产线码',
      key: 'code',
      width: 148,
      render: (_, e) => (
        <span>
          <Tag style={{ marginInlineEnd: 4, fontFamily: 'monospace' }}>{e.code}</Tag>
          {ambiguousCodeSet.has(e.code) ? (
            <Tooltip title="同一个码在不同考点下翻成不同错因 —— 键必须带考点，否则必串义">
              <Tag color="orange" style={{ marginInlineEnd: 0 }}>
                一码两义
              </Tag>
            </Tooltip>
          ) : null}
          {multiScopeCodes.has(e.code) ? (
            <Tooltip title="同一个码登记在两片叶上，但翻成的是同一条错因 —— 这不是歧义，只是两处各写了各自的说法">
              <Tag style={{ marginInlineEnd: 0 }}>一码多域</Tag>
            </Tooltip>
          ) : null}
        </span>
      ),
    },
    {
      title: '翻成的错因',
      key: 'causeId',
      width: 132,
      render: (_, e) => (
        <Typography.Link onClick={() => onJumpToCause(e.causeId)} style={{ fontSize: 13 }}>
          {nameOfCause[e.causeId] ?? e.causeId}
        </Typography.Link>
      ),
    },
    {
      // 🔴 不折叠：同码两义全靠这句话区分，被「…」吃掉这张表就白做了
      title: '这条映射在本作用域下的意思',
      dataIndex: 'note',
      key: 'note',
      render: (s: string) => <Typography.Text style={{ fontSize: 13, lineHeight: 1.8 }}>{s}</Typography.Text>,
    },
  ]

  return (
    <div>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="批改回流的接线口：产线码 → 错因，主键是 (考点, 码) 复合键"
        description="批改脚本吐的是局部码（dist / order / sign…），沉淀里挂的是错因，中间这一跳就靠这张表。翻错了不会报错，只会静静把沉淀归错类 —— 所以每条映射都必须写清「在这片考点下它指的是什么」。写入纪律照抄老区：同键不静默覆盖，改判走「先摘后挂」两条审计记录。"
      />

      {/* 🔴🔴 同码两义并排摆：这是整张表的存在理由，摆在最上面 */}
      {ambiguous.map((a) => (
        <div key={a.code} style={{ marginBottom: 14 }}>
          <Space size={8} wrap style={{ marginBottom: 6 }}>
            <Typography.Text strong style={{ fontSize: 13 }}>
              同码两义：产线码 <span style={{ fontFamily: 'monospace' }}>{a.code}</span>
            </Typography.Text>
            <Tag color="orange" style={{ marginInlineEnd: 0 }}>
              一个码 · {a.entries.length} 种含义
            </Tag>
          </Space>
          <Typography.Paragraph style={{ fontSize: 13, margin: '0 0 8px' }}>
            同一个码在不同考点下含义不同，所以这张表的键是 <b>(考点, 码)</b> 而不是码一个字段 ——
            无作用域的映射必然串义，而这个歧义<b>已经印进过学员的交付报告</b>。
          </Typography.Paragraph>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            {a.entries.map((e) => (
              <div
                key={`${e.kpId}|${e.code}`}
                style={{
                  flex: '1 1 300px',
                  minWidth: 280,
                  padding: '10px 12px',
                  background: HIT_BG,
                  border: '1px solid #f0f0f0',
                  // 高亮靠一条左边线，不铺色块（风格口径「禁大色块」）
                  borderLeft: '3px solid #fa8c16',
                  borderRadius: 4,
                }}
              >
                <div style={{ marginBottom: 4 }}>
                  <KpTraceLink name={kpNameOf(e.kpId)} />
                </div>
                <div style={{ marginBottom: 4 }}>
                  <Tag style={{ fontFamily: 'monospace', marginInlineEnd: 6 }}>{e.code}</Tag>
                  <span style={{ color: 'rgba(0,0,0,0.45)', marginInlineEnd: 6 }}>翻成</span>
                  <Typography.Link onClick={() => onJumpToCause(e.causeId)} style={{ fontSize: 13 }}>
                    {nameOfCause[e.causeId] ?? e.causeId}
                  </Typography.Link>
                </div>
                <Typography.Text style={{ fontSize: 13, lineHeight: 1.8 }}>{e.note}</Typography.Text>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* 「试一条」：现场演 resolveErrCode 的查找顺序（先精确后兜底，绝不颠倒） */}
      <div style={{ padding: '10px 12px', border: '1px solid #f0f0f0', borderRadius: 4, marginBottom: 12 }}>
        <Space size={8} wrap>
          <Typography.Text strong style={{ fontSize: 13 }}>
            试一条
          </Typography.Text>
          <Select size="small" value={tryKp} options={kpOptions} onChange={setTryKp} style={{ minWidth: 220 }} />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            这片叶上收到码
          </Typography.Text>
          <Select size="small" value={tryCode} options={codeOptions} onChange={setTryCode} style={{ minWidth: 110 }} />
        </Space>
        <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.8 }}>
          {tried === undefined ? (
            <Typography.Text>
              <Tag style={{ marginInlineEnd: 6 }}>查不到</Tag>
              这片考点下没登记这个码，通用兜底里也没有 ——
              <b> 如实报查不到，不拿别的作用域的含义硬套</b>（串义就是这么来的），交人工登记。
            </Typography.Text>
          ) : tried.kpId === tryKp ? (
            <Typography.Text>
              <Tag color="blue" style={{ marginInlineEnd: 6 }}>
                精确命中 (考点, 码)
              </Tag>
              翻成「
              <Typography.Link onClick={() => onJumpToCause(tried.causeId)}>
                {nameOfCause[tried.causeId] ?? tried.causeId}
              </Typography.Link>
              」：{tried.note}
            </Typography.Text>
          ) : (
            <Typography.Text>
              <Tag style={{ marginInlineEnd: 6 }}>落到通用兜底</Tag>
              这片考点下没登记这个码，退到 kpId 为空的那条 —— 翻成「
              <Typography.Link onClick={() => onJumpToCause(tried.causeId)}>
                {nameOfCause[tried.causeId] ?? tried.causeId}
              </Typography.Link>
              」：{tried.note}
            </Typography.Text>
          )}
        </div>
      </div>

      <Table<ErrCodeMapEntry>
        rowKey={(e) => `${e.kpId}|${e.code}`}
        size="small"
        columns={columns}
        dataSource={errCodeMap}
        pagination={false}
        // 一码两义的行给最浅一档底色，与上面并排摆的那对对得上
        onRow={(e) => ({ style: ambiguousCodeSet.has(e.code) ? { background: HIT_BG } : undefined })}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：把「试一条」的考点从「四则混合运算的运算顺序」换成「整式的加减·去括号合并同类项」，
        码不动还是 <span style={{ fontFamily: 'monospace' }}>dist</span> —— 翻出来的错因就从「运算顺序错」变成「符号处理错」，
        这就是键必须带考点的现场。再把考点换成「梯形的特征与分类」（表里没登记它），会看到<b>查不到</b>而不是硬套一个；
        码换成 <span style={{ fontFamily: 'monospace' }}>copy</span> 则落到通用兜底（誊写笔误跨考点都成立）。
        「翻成的错因」点得动，跳回错因库页签并高亮那条。
      </Typography.Paragraph>
    </div>
  )
}

export default ErrCodeMapTab
