import { useMemo, useState } from 'react'
import { Alert, Button, Form, Input, Modal, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { ErrorCause } from '@/mock'
import { depositCountByCause, errorCauses, kpLeaves } from '@/mock'
// 🔴 溯源换算的唯一实现在 kg 组，本页单向依赖（见 kg/trace.ts 顶部的依赖方向说明）
import { KpTraceLinks } from '@/pages/kg/KpTraceLink'
import { kpKeyOf } from '@/pages/kg/trace'

/**
 * 页签②：错因库（词表层）。
 * 归属：维护组「错因管理」自用。
 *
 * 🔴 词表层是**低频且高杠杆**的东西：改一条错因的口径，全部历史沉淀的归类跟着变。
 *   所以这张表要把 definition **完整摊开**——判定口径就是这条错因的全部价值，
 *   折叠起来等于没写。
 * 🔴 kpNames 为空数组 = 跨考点通用错因（誊写笔误就是），必须渲成
 *   「不限考点（跨考点通用）」，不许留白让人以为数据缺了（页面组约定 §7）。
 *
 * 🔴🔴 判词⑤：挂靠考点这一列是错因 → 知识图谱的**溯源链**，每个词点得动，
 *   落到 /kg?kp=&lt;树key&gt; 那片叶。三态各有各的说法，一个都不许糊：
 *   - 空数组       → 「不限考点（跨考点通用）」，这是**正常态**，不是缺数据
 *   - 名字有、树上有 → 蓝字，点得动
 *   - 名字有、树上没 → 灰色虚线「未上树」（七上那一枝还没铺，点不动是如实显示）
 */

/** 本页新增的错因用这个前缀，表格据此打「本页新增」标 */
const LOCAL_PREFIX = 'ec-local-'

/**
 * 本页新增错因的自增序号。
 * 🔴 不许用 Date.now()：全站纪律「mock 不许有活时间」——时间戳会让同一份演示每次跑出不同 id，
 *   截图对不上、走查说不清是哪条。自增计数器每次会话从 1 开始，稳定可复述。
 */
let localSeq = 0

/** 从沉淀跳过来时那一行的底色。🔴 「禁大色块」：只给最浅一档的提示底，不铺饱和色 */
const HIT_BG = '#fafafa'

export function CauseLibTab({
  causes,
  onAdd,
  highlightId = '',
  onClearHighlight,
}: {
  causes: ErrorCause[]
  onAdd: (c: ErrorCause) => void
  /** 沉淀行点错因 Tag 跳过来时要高亮的那条（'' = 没有） */
  highlightId?: string
  onClearHighlight?: () => void
}) {
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm<{ name: string; definition: string; kpNames?: string[]; mappedCodes?: string[] }>()

  const counts = useMemo(() => depositCountByCause(), [])

  /** 词表里写了、但教材树上找不到同名叶的考点词（页头一句话交代欠账） */
  const offTree = useMemo(() => {
    const set = new Set<string>()
    for (const c of causes) for (const k of c.kpNames) if (kpKeyOf(k) === undefined) set.add(k)
    return Array.from(set)
  }, [causes])

  /**
   * 挂靠考点的候选。
   * 🔴 用 tags 模式而不是死下拉：错因的考点名跨学段（「有理数加减混合运算」是七上，
   *   四上教材树里根本没有这片叶），硬绑教材树会逼着人乱挂。候选给两处的并集，
   *   允许自己敲——错因词表与教材树是两套词，别互相绑架。
   */
  const kpOptions = useMemo(() => {
    const set = new Set<string>()
    for (const c of errorCauses) for (const k of c.kpNames) set.add(k)
    for (const k of kpLeaves()) set.add(k)
    return Array.from(set).map((k) => ({ value: k, label: k }))
  }, [])

  const columns: ColumnsType<ErrorCause> = [
    {
      title: '错因名',
      key: 'name',
      width: 132,
      render: (_, c) => (
        <div>
          <Typography.Text strong style={{ fontSize: 13 }}>
            {c.name}
          </Typography.Text>
          {c.id.startsWith(LOCAL_PREFIX) ? (
            <div>
              <Tag color="orange" style={{ marginInlineEnd: 0, marginTop: 2 }}>
                本页新增
              </Tag>
            </div>
          ) : null}
          {/* 🔴 从沉淀跳过来的那条：底色太淡怕看不见，行内再明说一次它是被点名的 */}
          {c.id === highlightId ? (
            <div style={{ marginTop: 2 }}>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                ← 从批改沉淀跳来
              </Typography.Text>
            </div>
          ) : null}
        </div>
      ),
    },
    {
      title: '沉淀',
      key: 'count',
      width: 74,
      align: 'right',
      render: (_, c) => (
        <span>
          {counts[c.id] ?? 0}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {' '}
            条
          </Typography.Text>
        </span>
      ),
    },
    {
      // 🔴 完整展示不折叠：判定口径就是这条错因的全部价值
      title: '定义（判定口径）',
      dataIndex: 'definition',
      key: 'definition',
      render: (s: string) => <Typography.Text style={{ fontSize: 13, lineHeight: 1.8 }}>{s}</Typography.Text>,
    },
    {
      // 🔴 判词⑤：错因 → 知识图谱的溯源链就在这一列
      title: '挂靠考点',
      key: 'kpNames',
      width: 240,
      render: (_, c) => (
        <KpTraceLinks
          names={c.kpNames}
          empty={
            // 🔴 空数组不是「没填」、更不是溯源断点，是「跨考点通用」，必须写出来
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12 }}
              title="像誊写笔误那样哪个考点都可能犯 —— 不挂叶是它的正常态，不是欠账"
            >
              不限考点（跨考点通用）
            </Typography.Text>
          }
        />
      ),
    },
    {
      // 🔴 这列只是「这条错因收编了哪些码」的展示口径，**不是翻译权威**：
      //   真正的翻译走复合键 (考点, 码)，见「错因码翻译表」页签（同码两义就是那儿的活样本）
      title: (
        <Tooltip title="展示口径而已 —— 真正的翻译权威是复合键 (考点, 码)，在「错因码翻译表」页签；同一个码在不同考点下可能翻成不同错因">
          <span>映射码</span>
        </Tooltip>
      ),
      key: 'mappedCodes',
      width: 148,
      render: (_, c) => (
        <span>
          {c.mappedCodes.map((m) => (
            <Tag key={m} style={{ marginInlineEnd: 4, marginBottom: 4, fontFamily: 'monospace', fontSize: 12 }}>
              {m}
            </Tag>
          ))}
        </span>
      ),
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} size={10} wrap>
        <Button onClick={() => setOpen(true)}>新增错因</Button>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          错因 {causes.length} 条 · 其中跨考点通用 {causes.filter((c) => c.kpNames.length === 0).length} 条
          {offTree.length > 0 ? ` · ${offTree.length} 个考点词教材树上还没有同名叶（灰色虚线「未上树」的就是它们）` : ''}
        </Typography.Text>
        {highlightId ? (
          <Button size="small" type="link" style={{ padding: 0, height: 'auto' }} onClick={onClearHighlight}>
            清除定位
          </Button>
        ) : null}
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
        message="词表改一次，全部历史沉淀跟着重新归类"
        description="所以这层是低频动作：新增一条错因之前先确认它不是已有错因的换句话说法（「符号处理错」和「去括号变号错」就是同一条）。本页的新增是原型演示态，只加到本页临时列表，不落库；真正的收编与重归类走 agent。"
      />

      <Table<ErrorCause>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={causes}
        pagination={false}
        // 从沉淀跳来的那条给最浅一档底色（禁大色块），行内还有一句「← 从批改沉淀跳来」兜底
        onRow={(c) => ({ style: c.id === highlightId ? { background: HIT_BG } : undefined })}
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 10, marginBottom: 0 }}>
        走查提示：「挂靠考点」里的蓝字点得动 —— 点「三位数乘两位数的计算」落到 /kg 那片叶，
        在叶子的「③ 关联错因」里能反过来看见这条错因，一来一回对得上。
        「誊写笔误」写的是「不限考点（跨考点通用）」，那是<b>正常态</b>不是欠账；
        灰色虚线的词（如绝对值那几个）是教材树还没铺到，点不动是如实显示。
      </Typography.Paragraph>

      <Modal
        title="新增错因"
        open={open}
        okText="加到词表"
        cancelText="取消"
        onCancel={() => setOpen(false)}
        onOk={() => {
          form
            .validateFields()
            .then((v) => {
              onAdd({
                id: `${LOCAL_PREFIX}${(localSeq += 1)}`,
                name: v.name.trim(),
                definition: v.definition.trim(),
                kpNames: v.kpNames ?? [],
                mappedCodes: v.mappedCodes ?? [],
              })
              form.resetFields()
              setOpen(false)
            })
            // 校验没过就停在弹窗里（antd 已经把红字标在表单上），不让它变成未捕获的 rejection
            .catch(() => undefined)
        }}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item
            name="name"
            label="错因名"
            rules={[{ required: true, message: '错因名不能空' }]}
            help="一句名词短语，如「符号处理错」。别写成一整句判定规则，那是定义该干的事。"
          >
            <Input placeholder="如：单位换算错" maxLength={20} />
          </Form.Item>
          <Form.Item
            name="definition"
            label="定义（判定口径）"
            rules={[{ required: true, message: '定义不能空 —— 没有口径的错因等于没有' }]}
            help="写清楚「什么算、什么不算」。批改时靠这段话把机器错因码归到这条错因下。"
            style={{ marginTop: 18 }}
          >
            <Input.TextArea rows={4} placeholder="如：面积/长度单位在转换时倍率取错或漏换，算式本身无误……" maxLength={300} showCount />
          </Form.Item>
          <Form.Item
            name="kpNames"
            label="挂靠考点"
            help="留空 = 跨考点通用错因（像誊写笔误那样，哪个考点都可能犯）。可直接敲新词，不受教材树限制。"
          >
            <Select mode="tags" placeholder="不填就是跨考点通用" options={kpOptions} maxTagCount={6} />
          </Form.Item>
          <Form.Item name="mappedCodes" label="收编的机器错因码" help="机器批改输出的原始码，一条错因可收编多个，如 E-UNIT-01。">
            <Select mode="tags" placeholder="如：E-UNIT-01" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default CauseLibTab
