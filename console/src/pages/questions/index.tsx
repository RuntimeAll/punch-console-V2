import { useMemo, useState } from 'react'
import { Button, Card, Col, Empty, Form, Input, Row, Select, Space, Switch, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { BlockFlow, PageFrame } from '@/components'
import type { Question } from '@/mock'
import {
  dictOf, findPattern, kpNameOf, kpVocabulary, labelPathMap, qtypeLabel, questionPatterns,
  questions, questionsUnderPath, sourceQuestions, tagDomains, tagText, tagsOfDomain, treePathText,
} from '@/mock'
import {
  chapterOf, crossAxisKp, hasFigure, isGenerated, isStubKey, matchesTags, searchableText, sourceText, summaryText,
} from './helpers'
import { KgTreePanel } from './KgTreePanel'
import { DifficultyStars, KpTags, StatusTag, TagChips } from './parts'

/**
 * 题库 /questions —— 左树右表两栏：
 *   左 = 教材树目录（版本 → 年级学期 → 单元 → 小节 → 考点）
 *   右 = 若依式三段（筛选区 + 表格 + 分页），原样保留
 * 归属：页面组「题库」。
 *
 * 交互口径（评审时按这条讲）：
 * - 树 + 筛选行 + 关键字是**「与」关系**，命中数实时算（页头右上角那行）。
 * - 树点任意层级 = 按 treePath **前缀**筛，所以点「第三单元」一次拿到该单元下所有小节的题。
 * - 表格是**扫读面**：一行一题，题面只出首行摘要，用来快速定位。
 * - 🔴 要看题的真身，行内「展开原题」就地混排渲染（走 <BlockFlow size="compact">），
 *   图在题面第几段就渲在第几段；**列表里不许出现独立「配图区」**（老版被否定的头号交互）。
 * - 行点击 = 进详情页 /questions/:id（详情页才是本次评审的核心页）。
 *
 * 🔴🔴 第五轮新增两条口径（定稿 D-9 / D-19）：
 * ① **题源类 / 生成类开关**：默认只看题源类（scan/manual），生成类（model/pipeline）开了才见。
 *    这不是省地方，是**记账口径**——自己产的变式混进来，「我录了多少题」这本账就废了。
 * ② **标签筛选**：标签 = 域 + 名（场景/方法/思想/图形特征四域，见 TAG_DOMAINS），
 *    多选是「与」（同时带这几个标签）。标签不上树、只做归类，与考点两条轴别混。
 *
 * 🔴 URL 承载两个跨页参数：?tree=<树key>（树选中）与 ?pattern=<题型目录id>（详情页点题型目录跳回来）。
 *   两者都是**事实源在 URL**，不做本地 state —— 详情页要能带着筛选把人送回列表。
 */

/** 「全部」选项的哨兵值：用空串而不是 undefined，Select 的 allowClear 才好回落 */
const ALL = ''

export default function Questions() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  /** 改一个 URL 参数（空值 = 删掉这个参数）；replace：筛来筛去别在后退栈里堆一串 */
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    setSearchParams(next, { replace: true })
  }

  // ── 树选中：URL 是事实源 ────────────────────────────────────────
  const rawTreeKey = searchParams.get('tree') ?? ''
  // 校验一遍：URL 里塞了树上没有的 key（手敲错、树改过）一律当没选，别让页面显示一条假路径
  const treeKey = rawTreeKey && labelPathMap()[rawTreeKey] ? rawTreeKey : ''
  const setTreeKey = (key: string) => setParam('tree', key)

  // ── 题型目录筛选：URL 是事实源（详情页「题型目录」点过来就是这条链）────────
  const rawPatternId = searchParams.get('pattern') ?? ''
  // 同样校验：目录里没有的 id 一律当没选（否则会显示一条查不到名字的假范围）
  const patternId = rawPatternId && findPattern(rawPatternId) ? rawPatternId : ''
  const setPatternId = (id: string) => setParam('pattern', id)

  // ── 筛选条件（本地 state）────────────────────────────────────────
  const [kp, setKp] = useState<string>(ALL)
  const [doc, setDoc] = useState<string>(ALL)
  const [qtype, setQtype] = useState<string>(ALL)
  const [status, setStatus] = useState<string>(ALL)
  const [tags, setTags] = useState<string[]>([])
  const [keyword, setKeyword] = useState<string>('')
  const [expandedKeys, setExpandedKeys] = useState<readonly string[]>([])
  /** 🔴 D-9 口径开关：默认 false = 只看题源类；打开才把生成类放进来 */
  const [showGenerated, setShowGenerated] = useState(false)

  /**
   * 来源的下拉项从 mock 现算（题上只有一条 sourceRaw 来源原文，不再拆 doc/page 两截）；
   * 🔴 题型下拉改吃**字典**（dictOf('qtype')）而不是从数据里现凑：
   * 字典是值域正本，数据里没出现过的题型也该在下拉里（否则筛不出「一道都没有」这个事实）。
   */
  const docOptions = useMemo(() => Array.from(new Set(questions.map((q) => q.sourceRaw))), [])
  const qtypeOptions = useMemo(() => dictOf('qtype'), [])

  /**
   * 标签下拉：**按域分组**（antd 的 optgroup），值用 tagText（域·名）保证跨域唯一。
   * 🔴 域与词池都来自 mock 正本（tagDomains / tagsOfDomain），开新域这里零改。
   */
  const tagOptions = useMemo(
    () =>
      tagDomains().map((d) => ({
        label: d,
        options: tagsOfDomain(d).map((t) => ({ value: tagText(t), label: t.name })),
      })),
    [],
  )

  /** 当前树选中对应的 label 路径（空数组 = 没选，questionsUnderPath 会返回全部） */
  const treePath = useMemo(() => (treeKey ? (labelPathMap()[treeKey] ?? []) : []), [treeKey])

  /**
   * 树这一层筛出来的题。
   * 🔴 标准姿势 = questionsUnderPath(labelPathMap()[key])，
   *   别按 key 切字符串反推 label 路径（单元名带空格，切出来必错）。
   */
  const scoped = useMemo(() => questionsUnderPath(treePath), [treePath])

  /**
   * 树 ∩ 筛选行 ∩ 标签 ∩ 关键字 —— 🔴 但**先不管**题源类/生成类开关。
   * 分两步是为了能如实说出「另有 N 道生成类被口径折叠」：
   * 折叠掉的东西必须报数，否则用户会以为库里根本没有这些题。
   */
  const matched = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    return scoped.filter((q) => {
      if (kp && !q.kps.some((k) => kpNameOf(k.kpId) === kp)) return false
      if (doc && q.sourceRaw !== doc) return false
      if (qtype && q.qtypeCode !== qtype) return false
      if (status && q.status !== status) return false
      if (patternId && q.patternId !== patternId) return false
      if (!matchesTags(q, tags)) return false
      if (kw && !searchableText(q).includes(kw)) return false
      return true
    })
  }, [scoped, kp, doc, qtype, status, patternId, tags, keyword])

  /** 最终列表 = 命中集按口径开关过一道 */
  const filtered = useMemo(
    () => (showGenerated ? matched : matched.filter((q) => !isGenerated(q))),
    [matched, showGenerated],
  )

  /** 被口径折叠掉的生成类条数（要报数，见上面注释） */
  const hiddenGenerated = matched.length - filtered.length

  /** 当前口径下的**基数**（右上角那行的分母）：题源类 12 道 / 全库 14 道 */
  const baseTotal = showGenerated ? questions.length : sourceQuestions().length

  /** 筛选行是不是有条件在生效（空态文案要据此说人话） */
  const hasRowFilter = Boolean(kp || doc || qtype || status || patternId || tags.length || keyword.trim())

  /** 只清筛选行，不动树 */
  const clearRowFilters = () => {
    setKp(ALL)
    setDoc(ALL)
    setQtype(ALL)
    setStatus(ALL)
    setTags([])
    setKeyword('')
    setPatternId('')
  }

  /** 「重置」= 回到刚进页面的样子，树选中与口径开关也一并回落（树自己那颗「清除」只清树） */
  const reset = () => {
    clearRowFilters()
    setTreeKey('')
    setShowGenerated(false)
  }

  /**
   * 从「按归属筛」切到「按能力标签筛」：清掉树选中，改用考点下拉。
   * 🔴 反向不做（选考点下拉时不自动跳树）：
   *   「角度计算问题」这片叶子归属下 0 道题，却有 5 道题把它当副考点——
   *   自动跳树会让下拉从 5 道变 0 道，等于把一个筛选器悄悄改成另一个口径。
   */
  const switchToKpTag = (kpName: string) => {
    setTreeKey('')
    setKp(kpName)
  }

  const columns: ColumnsType<Question> = [
    {
      title: '题号',
      dataIndex: 'id',
      width: 88,
      render: (id: string) => <Typography.Text style={{ fontFamily: 'monospace' }}>{id}</Typography.Text>,
    },
    {
      title: '题面',
      key: 'stem',
      ellipsis: { showTitle: true },
      render: (_, q) => (
        <span title={summaryText(q)}>
          {hasFigure(q) ? (
            <Tag style={{ marginInlineEnd: 6 }} color="default">
              含图
            </Tag>
          ) : null}
          {summaryText(q)}
        </span>
      ),
    },
    {
      // 章节 = treePath 倒数第二级（小节）；hover 出整条树路径，省得为了看归属点进详情
      title: '章节',
      key: 'chapter',
      width: 140,
      ellipsis: { showTitle: false },
      render: (_, q) => {
        const chapter = chapterOf(q)
        if (!chapter) return <Typography.Text type="secondary">未挂树</Typography.Text>
        return (
          <Typography.Text style={{ fontSize: 12 }} title={treePathText(q.treePath)}>
            {chapter}
          </Typography.Text>
        )
      },
    },
    {
      title: '考点',
      key: 'kps',
      width: 180,
      render: (_, q) => <KpTags kps={q.kps} />,
    },
    {
      // 🔴 标签与考点分两列摆：标签是不成树的归类（域·名），考点是上树的能力轴，合并就分不清了
      title: '标签',
      key: 'tags',
      width: 190,
      render: (_, q) => <TagChips tags={q.tags} />,
    },
    {
      title: '来源',
      key: 'source',
      width: 150,
      ellipsis: { showTitle: false },
      // 来源原文（sourceRaw）：哪本教辅哪一页 / 哪场考试 / 哪个出题器，hover 看全文
      render: (_, q) => (
        <Typography.Text type="secondary" style={{ fontSize: 12 }} title={sourceText(q)}>
          {sourceText(q)}
        </Typography.Text>
      ),
    },
    {
      title: '题型',
      key: 'qtype',
      width: 80,
      // 题上存的是字典码，中文现查（字典是值域正本）
      render: (_, q) => qtypeLabel(q.qtypeCode),
    },
    {
      title: '难度',
      key: 'difficulty',
      width: 72,
      render: (_, q) => <DifficultyStars code={q.diffCode} />,
    },
    {
      title: '状态',
      key: 'status',
      width: 68,
      render: (_, q) => <StatusTag status={q.status} />,
    },
    {
      // 🔴 题源类 / 生成类要一眼看得出（定稿 D-9）：生成类别混进「我录了多少题」的账
      title: '来源类',
      key: 'sourceKind',
      width: 76,
      render: (_, q) =>
        isGenerated(q) ? (
          <Tag color="purple" style={{ marginInlineEnd: 0 }} title={`生成类：${q.sourceRaw}`}>
            生成
          </Tag>
        ) : (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            题源
          </Typography.Text>
        ),
    },
  ]

  /**
   * 空态文案：🔴 一律说人话，说清「为什么是空的、下一步点哪」。
   * 五种空法各写各的，别一句「暂无数据」糊过去——走查时这几句就是设计说明。
   */
  const renderEmpty = () => {
    const treeNodeStub = treeKey ? isStubKey(treeKey) : false
    const lastLabel = treePath[treePath.length - 1] ?? ''

    // ① 选中的是还没铺开的空壳枝
    if (treeNodeStub) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span>
              「{lastLabel}」这一枝<b>还没铺</b>：教材树上只有个名字，底下的单元 / 小节 / 考点都没建，
              所以一道题也挂不上来。
            </span>
          }
        >
          <Button size="small" onClick={() => setTreeKey('')}>
            看全部题目
          </Button>
        </Empty>
      )
    }

    // ② 一道都没剩，但**全被口径开关折叠了** —— 这不是没题，是没打开生成类
    if (hiddenGenerated > 0) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span>
              当前条件命中 {matched.length} 道，但<b>全是生成类</b>（模型 / 管线产的变式），
              被「只看题源类」的默认口径折叠了。
            </span>
          }
        >
          <Button size="small" type="primary" ghost onClick={() => setShowGenerated(true)}>
            打开生成类，看这 {hiddenGenerated} 道
          </Button>
        </Empty>
      )
    }

    // ③ 树选中的这一枝本身就没题（是考点叶时顺带说清两条轴的差额，别让人以为库里没这类题）
    if (treeKey && scoped.length === 0) {
      const cross = crossAxisKp(treeKey)
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span>
              「{lastLabel}」这一枝下还没有题（树按<b>归属</b>算：题的 treePath 要落在这条路径上）。
              {cross ? (
                <>
                  <br />
                  不过有 {cross.byTag} 道题把「{cross.name}」当<b>能力标签</b>用，归属挂在别的枝上。
                </>
              ) : null}
            </span>
          }
        >
          <Space size={8}>
            {cross ? (
              <Button size="small" type="primary" ghost onClick={() => switchToKpTag(cross.name)}>
                按考点标签看这 {cross.byTag} 道
              </Button>
            ) : null}
            <Button size="small" onClick={() => setTreeKey('')}>
              看全部题目
            </Button>
          </Space>
        </Empty>
      )
    }

    // ④ 这一枝有题，是筛选行把它们滤没了
    if (treeKey && hasRowFilter) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<span>「{lastLabel}」下有 {scoped.length} 道题，但当前筛选条件一道都没留下。</span>}
        >
          <Button size="small" onClick={clearRowFilters}>
            只留树筛选
          </Button>
        </Empty>
      )
    }

    // ⑤ 没选树，纯粹是筛选条件没命中
    return (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有题命中当前筛选条件。">
        <Button size="small" onClick={reset}>
          重置
        </Button>
      </Empty>
    )
  }

  return (
    <PageFrame
      title="题库"
      desc="挂账 + 展示面：左边教材树定位到章节，右边筛到题，展开就地看混排原题，点行进详情。录题/改题归 agent，本页只读。"
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          命中 {filtered.length} / {showGenerated ? '全库' : '题源类'} {baseTotal} 道
          {treeKey ? ` · 树范围 ${scoped.length} 道` : ''}（mock）
        </Typography.Text>
      }
    >
      <Row gutter={[12, 12]} wrap align="top">
        {/* 左栏：教材树 */}
        <Col flex="0 0 270px" style={{ minWidth: 0 }}>
          <KgTreePanel selectedKey={treeKey} onSelectKey={setTreeKey} onSwitchToKpTag={switchToKpTag} />
        </Col>

        {/* 右栏：若依三段（筛选区 + 表格 + 分页），原样保留 */}
        <Col flex="1 1 640px" style={{ minWidth: 0 }}>
          {/* ① 筛选区 */}
          <Card size="small" style={{ marginBottom: 12 }}>
            <Form layout="inline" style={{ rowGap: 8 }}>
              <Form.Item label="考点">
                <Select
                  value={kp}
                  onChange={setKp}
                  style={{ width: 190 }}
                  options={[
                    { value: ALL, label: '全部考点' },
                    ...kpVocabulary.map((k) => ({ value: k, label: k })),
                  ]}
                />
              </Form.Item>
              <Form.Item label="来源">
                <Select
                  value={doc}
                  onChange={setDoc}
                  style={{ width: 210 }}
                  options={[{ value: ALL, label: '全部来源' }, ...docOptions.map((d) => ({ value: d, label: d }))]}
                />
              </Form.Item>
              <Form.Item label="题型">
                <Select
                  value={qtype}
                  onChange={setQtype}
                  style={{ width: 110 }}
                  options={[
                    { value: ALL, label: '全部' },
                    ...qtypeOptions.map((t) => ({ value: t.code, label: t.label })),
                  ]}
                />
              </Form.Item>
              <Form.Item label="状态">
                <Select
                  value={status}
                  onChange={setStatus}
                  style={{ width: 100 }}
                  // 🔴 四态照定稿摆全（草稿/已审/上架/退役），别只摆有数据的那两个
                  options={[
                    { value: ALL, label: '全部' },
                    { value: '上架', label: '上架' },
                    { value: '已审', label: '已审' },
                    { value: '草稿', label: '草稿' },
                    { value: '退役', label: '退役' },
                  ]}
                />
              </Form.Item>
              <Form.Item
                label="标签"
                tooltip="标签 = 域 + 名（场景 / 方法 / 思想 / 图形特征），下拉按域分组；多选 = 同时带这几个标签（与）"
              >
                <Select
                  mode="multiple"
                  value={tags}
                  onChange={setTags}
                  style={{ width: 240 }}
                  placeholder="全部标签"
                  maxTagCount="responsive"
                  allowClear
                  options={tagOptions}
                />
              </Form.Item>
              <Form.Item
                label="题型目录"
                tooltip="题型目录 = 这类题长什么样（识别 / 归类用），与「怎么解」的解题模型分工不同"
              >
                <Select
                  value={patternId}
                  onChange={setPatternId}
                  style={{ width: 220 }}
                  options={[
                    { value: ALL, label: '全部题型目录' },
                    ...questionPatterns.map((p) => ({ value: p.id, label: p.name })),
                  ]}
                />
              </Form.Item>
              <Form.Item label="关键字">
                <Input
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  placeholder="题面 / 题号 / 标签"
                  allowClear
                  style={{ width: 180 }}
                />
              </Form.Item>
              <Form.Item>
                {/* 重置 = 连树带筛选、连口径开关一起回到初始态 */}
                <Button onClick={reset}>重置</Button>
              </Form.Item>
            </Form>

            {/*
              🔴 口径行（定稿 D-9）：题源类 / 生成类开关 + 一句说明。
              说明必须摆在开关旁边——「为什么默认看不到生成类」这件事，
              不写在这儿就只能靠人记，走查时第一个被问的就是它。
            */}
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #f0f0f0' }}>
              <Space size={8} align="start" wrap>
                <Space size={6}>
                  <Switch size="small" checked={showGenerated} onChange={setShowGenerated} />
                  <Typography.Text style={{ fontSize: 12 }}>含生成类</Typography.Text>
                </Space>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  默认只看<b>题源类</b>（扫的 / 手录的）；生成类 = 模型或管线产的变式，开了才见 ——
                  别让自己产的题混进「我录了多少题」这本账。
                  {hiddenGenerated > 0 ? `当前有 ${hiddenGenerated} 道生成类被折叠。` : ''}
                </Typography.Text>
              </Space>
            </div>

            {/*
              树 / 题型目录选中时挂范围条：左栏面包屑窄、要折行，这里一行摆得下整条路径，
              且紧挨着表格——让人一眼看清「右表现在只在这个范围里筛」。× 即清除。
            */}
            {treeKey || patternId ? (
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #f0f0f0' }}>
                {treeKey ? (
                  <>
                    <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineEnd: 6 }}>
                      树范围
                    </Typography.Text>
                    <Tag closable onClose={() => setTreeKey('')} style={{ marginInlineEnd: 12 }}>
                      {treePathText(treePath)}
                    </Tag>
                  </>
                ) : null}
                {patternId ? (
                  <>
                    <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineEnd: 6 }}>
                      题型目录
                    </Typography.Text>
                    <Tag
                      closable
                      onClose={() => setPatternId('')}
                      style={{ marginInlineEnd: 0 }}
                      title={findPattern(patternId)?.desc}
                    >
                      {findPattern(patternId)?.name ?? patternId}
                    </Tag>
                  </>
                ) : null}
              </div>
            ) : null}
          </Card>

          {/* ② 表格 + ③ 分页 */}
          <Table<Question>
            rowKey="id"
            size="small"
            columns={columns}
            dataSource={filtered}
            locale={{ emptyText: renderEmpty() }}
            /**
             * 🔴 固定像素而不是 'max-content'：题面列靠 ellipsis 截断，
             * max-content 会让它撑到整句话那么宽，表格横到天边去。
             * 1286 = 各列固定宽之和（题号 88 + 章节 140 + 考点 180 + 标签 190 + 来源 150
             * + 题型 80 + 难度 72 + 状态 68 + 来源类 76 = 1044）+ 展开列 82 + 题面最小可读宽 160。
             */
            scroll={{ x: 1286 }}
            pagination={{
              pageSize: 8,
              showSizeChanger: false,
              showTotal: (total) => `共 ${total} 道`,
              hideOnSinglePage: false,
            }}
            onRow={(q) => ({
              style: { cursor: 'pointer' },
              onClick: () => navigate(`/questions/${q.id}`),
            })}
            expandable={{
              expandedRowKeys: expandedKeys as string[],
              onExpandedRowsChange: (keys) => setExpandedKeys(keys as string[]),
              // 🔴 展开区 = 完整题面的块流混排（图在中间就渲在中间、选项流式并排），不是「配图区」
              expandedRowRender: (q) => (
                <div style={{ padding: '2px 4px 6px' }}>
                  <BlockFlow blocks={q.blocks} size="compact" />
                </div>
              ),
              // 自定义展开按钮：文字比图标好懂；必须 stopPropagation，否则会连带触发行点击进详情
              expandIcon: ({ expanded, onExpand, record }) => (
                <Button
                  type="link"
                  size="small"
                  style={{ paddingInline: 0 }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onExpand(record, e)
                  }}
                >
                  {expanded ? '收起' : '展开原题'}
                </Button>
              ),
              columnWidth: 82,
            }}
          />

          <Space style={{ marginTop: 10 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              走查提示：打开「含生成类」看 q-4014 这道模型变式怎么进出这本账；标签下拉里挑「方法·凑整拆数」
              看四域分组；展开 q-4012 / q-4013 看选项流式并排与图选项整块换行；
              树上点「四年级下册（未铺）」看空壳枝的空态。
            </Typography.Text>
          </Space>
        </Col>
      </Row>
    </PageFrame>
  )
}
