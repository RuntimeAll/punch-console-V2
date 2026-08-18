import { useState } from 'react'
import { Alert, Button, Card, Descriptions, Form, Input, Modal, Popconfirm, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { isStub } from '@/mock'
import { KpTraceSections } from './KpTraceSections'
import type { MaintMap } from './maint'
import { labelOf, patchOf } from './maint'
import { traceOfKpKey } from './trace'
import { COUNT_BY_KEY, NODE_BY_KEY, PATH_BY_KEY, descendantsOf } from './tree-view'

/**
 * 右栏：选中节点的详情。
 * 归属：维护组「知识图谱」自用。
 *
 * 三种态各有各的说法，别用一套模板糊过去：
 * ① 没选中      → 说清这页是干嘛的、先看哪一屏
 * ② 选中的是枝  → 枝概览（下辖几节几叶、挂了多少题、哪几片叶是空的）
 * ③ 选中的是叶  → 考点档案 + 维护动作（加别名 / 改名 / 退役）
 *
 * 🔴 维护动作是**原型演示态**：只改本页临时 state，不落库、不回填题目。
 *   真给一片叶子改名要连带回写它下面每道题的 treePath，那是 agent 侧的事务动作。
 *   页面把这句话明写在动作旁边，别让走查的人以为点一下就真改了库。
 */

export function LeafDetail({
  selectedKey,
  maint,
  onAddAlias,
  onRemoveAlias,
  onRename,
  onRetire,
}: {
  selectedKey: string
  maint: MaintMap
  onAddAlias: (key: string, alias: string) => void
  onRemoveAlias: (key: string, alias: string) => void
  onRename: (key: string, name: string) => void
  onRetire: (key: string, retired: boolean) => void
}) {
  const navigate = useNavigate()
  const [aliasOpen, setAliasOpen] = useState(false)
  const [renameOpen, setRenameOpen] = useState(false)
  const [aliasDraft, setAliasDraft] = useState('')
  const [nameDraft, setNameDraft] = useState('')

  const node = selectedKey ? NODE_BY_KEY[selectedKey] : undefined

  // ① 没选中
  if (!node) {
    return (
      <Card size="small" title="家底速览">
        <Typography.Paragraph style={{ marginBottom: 8 }}>
          左边点一个节点开始看。这页回答三个维护问题：
        </Typography.Paragraph>
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 2, color: 'rgba(0,0,0,0.65)' }}>
          <li>目录铺到哪儿了 —— 哪一枝还是空壳（标「未铺」的两枝就是）</li>
          <li>哪片叶子是空的 —— 勾上「只看零挂载考点」，剩下的就是缺口</li>
          <li>词表乱不乱 —— 一片叶子有几个别名、有没有被改过名 / 退过役</li>
        </ol>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '10px 0 0' }}>
          🔴 建叶子、拖拽改归属、删节点这类<b>结构</b>动作不在本页，走 agent。
          本页只做「看家底」＋别名/改名/退役这几个轻量词表动作。
        </Typography.Paragraph>
      </Card>
    )
  }

  const path = PATH_BY_KEY[selectedKey] ?? []
  const patch = patchOf(maint, selectedKey)
  const name = labelOf(node, maint)
  const count = COUNT_BY_KEY[selectedKey] ?? 0
  const stub = isStub(node)

  /** 面包屑：最后一段用现名（改过名要能一眼看出来） */
  const trail = (
    <span style={{ fontSize: 12, lineHeight: 1.9 }}>
      {path.map((label, i) => (
        <span key={label}>
          {i > 0 ? <span style={{ color: 'rgba(0,0,0,0.25)', margin: '0 4px' }}>/</span> : null}
          <Typography.Text type={i === path.length - 1 ? undefined : 'secondary'}>
            {i === path.length - 1 ? name : label}
          </Typography.Text>
        </span>
      ))}
    </span>
  )

  // ② 选中的是枝（版本 / 年级学期 / 单元 / 小节）
  if (node.kind !== '考点') {
    const kids = descendantsOf(node)
    const leaves = kids.filter((n) => n.kind === '考点')
    const zeroLeaves = leaves.filter((n) => (COUNT_BY_KEY[n.key] ?? 0) === 0)

    return (
      <Card
        size="small"
        title={
          <Space size={8}>
            <span>{name}</span>
            <Tag style={{ marginInlineEnd: 0 }}>{node.kind}</Tag>
          </Space>
        }
        extra={
          count > 0 ? (
            <Button size="small" onClick={() => navigate(`/questions?tree=${encodeURIComponent(selectedKey)}`)}>
              在题库里看这一枝（{count} 题）
            </Button>
          ) : null
        }
      >
        {stub ? (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="这一枝还没铺"
            description="教材树上只有个名字，底下的单元 / 小节 / 考点一个都没建。铺目录是 agent 侧动作（从教材目录抽结构再灌树），本页只如实标出来——空目录假装铺好了是事故。"
          />
        ) : null}

        <Descriptions
          size="small"
          column={1}
          styles={{ label: { width: 76 } }}
          items={[
            { key: 'path', label: '路径', children: trail },
            {
              key: 'scale',
              label: '下辖',
              children: stub
                ? '—'
                : `${kids.filter((n) => n.kind === '单元').length} 单元 · ${kids.filter((n) => n.kind === '小节').length} 小节 · ${leaves.length} 考点叶`,
            },
            {
              key: 'mount',
              label: '挂题',
              children: stub ? '—' : `${count} 道题，落在 ${leaves.length - zeroLeaves.length} 片叶上`,
            },
          ]}
        />

        {!stub && zeroLeaves.length > 0 ? (
          <div style={{ marginTop: 12 }}>
            <Typography.Text strong style={{ fontSize: 13 }}>
              零挂载的叶子（{zeroLeaves.length} / {leaves.length}）
            </Typography.Text>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '2px 0 6px' }}>
              目录有、题没有。这是维护时真正要盯的缺口，不是「数据没录完」。
            </Typography.Paragraph>
            <div>
              {zeroLeaves.map((leaf) => (
                <Tag key={leaf.key} style={{ marginBottom: 4, color: 'rgba(0,0,0,0.55)' }}>
                  {labelOf(leaf, maint)}
                </Tag>
              ))}
            </div>
          </div>
        ) : null}
      </Card>
    )
  }

  // ③ 选中的是考点叶
  /**
   * 🔴 判词⑤：考点详情 = **聚合落点**。四小节（题目 / 模型 / 错因 / 最近沉淀）
   *   全部由 traceOfKpKey 现算，本文件不自己捞数据、不自己拼匹配规则——
   *   同一套匹配 /model /cause /questions/:id 也在用，只许有一份实现（trace.ts）。
   * 🔴 匹配认的是树上的**原名**（node.label），不是本页临时改的名：
   *   改名是原型演示态、没回填过题目与词表，拿新名去匹配会当场把家当匹配没。
   */
  const trace = traceOfKpKey(selectedKey)

  return (
    <Card
      size="small"
      title={
        <Space size={8} wrap>
          <span>{name}</span>
          <Tag style={{ marginInlineEnd: 0 }}>考点叶</Tag>
          {patch.retired ? (
            <Tag color="default" style={{ marginInlineEnd: 0, color: 'rgba(0,0,0,0.45)' }}>
              已退役
            </Tag>
          ) : null}
        </Space>
      }
      extra={
        count > 0 ? (
          <Button size="small" onClick={() => navigate(`/questions?tree=${encodeURIComponent(selectedKey)}`)}>
            在题库里看（{count} 题）
          </Button>
        ) : null
      }
    >
      <Descriptions
        size="small"
        column={1}
        styles={{ label: { width: 76 } }}
        items={[
          { key: 'path', label: '所属路径', children: trail },
          {
            key: 'origin',
            label: '原名',
            children:
              patch.renamedTo === undefined ? (
                <Typography.Text type="secondary">未改名</Typography.Text>
              ) : (
                <Space size={6}>
                  <Typography.Text delete type="secondary">
                    {node.label}
                  </Typography.Text>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    （本页临时改名，未回填题目）
                  </Typography.Text>
                </Space>
              ),
          },
          {
            key: 'alias',
            label: '别名',
            children:
              patch.aliases.length === 0 ? (
                <Typography.Text type="secondary">暂无别名</Typography.Text>
              ) : (
                <span>
                  {patch.aliases.map((a) => (
                    <Tag
                      key={a}
                      closable
                      onClose={(e) => {
                        e.preventDefault()
                        onRemoveAlias(selectedKey, a)
                      }}
                      style={{ marginInlineEnd: 4, marginBottom: 4 }}
                    >
                      {a}
                    </Tag>
                  ))}
                </span>
              ),
          },
          {
            // 🔴 一行看完家底：四小节的数一次报齐，再往下才是逐项清单
            key: 'assets',
            label: '家当',
            children: trace ? (
              <Space size={6} wrap>
                <Typography.Text style={{ fontSize: 13 }}>
                  题 {trace.questions.length} · 考察模型 {trace.models.length} · 错因 {trace.causes.length} · 沉淀{' '}
                  {trace.depositTotal}
                </Typography.Text>
                {trace.questions.length === 0 ? (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    （零挂载：目录有、题没有）
                  </Typography.Text>
                ) : null}
              </Space>
            ) : (
              <Typography.Text type="secondary">—</Typography.Text>
            ),
          },
          { key: 'key', label: '树 key', children: <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{node.key}</span> },
        ]}
      />

      {/* 🔴 聚合落点四小节（判词⑤）：题目 / 考察模型 / 错因 / 最近沉淀，空的照写「暂无」 */}
      {trace ? <KpTraceSections trace={trace} /> : null}

      {/* 维护动作：轻量词表动作，且只在本页临时态生效 */}
      <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
        <Space size={8} wrap>
          <Button
            size="small"
            onClick={() => {
              setAliasDraft('')
              setAliasOpen(true)
            }}
          >
            加别名
          </Button>
          <Button
            size="small"
            onClick={() => {
              setNameDraft(name)
              setRenameOpen(true)
            }}
          >
            改名
          </Button>
          {patch.retired ? (
            <Button size="small" onClick={() => onRetire(selectedKey, false)}>
              恢复启用
            </Button>
          ) : (
            <Popconfirm
              title="退役这片考点叶？"
              description={
                <span style={{ display: 'inline-block', maxWidth: 300 }}>
                  退役后不再往这片叶子上挂新题，已挂的 {count} 道题原地不动，等 agent 迁走。
                  <br />
                  本页只改临时状态，不落库。
                </span>
              }
              okText="退役"
              cancelText="取消"
              onConfirm={() => onRetire(selectedKey, true)}
            >
              <Button size="small" danger>
                退役
              </Button>
            </Popconfirm>
          )}
        </Space>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '8px 0 0' }}>
          🔴 这三个动作是<b>原型演示态</b>：只改本页临时状态，刷新即还原。真改名要连带回写挂在这片叶下每道题的
          treePath，属 agent 侧事务动作；建叶子 / 改归属 / 删节点更不在本页。
        </Typography.Paragraph>
      </div>

      {/* 加别名 */}
      <Modal
        title={`加别名 · ${name}`}
        open={aliasOpen}
        okText="加上"
        cancelText="取消"
        okButtonProps={{ disabled: aliasDraft.trim().length === 0 }}
        onCancel={() => setAliasOpen(false)}
        onOk={() => {
          onAddAlias(selectedKey, aliasDraft.trim())
          setAliasOpen(false)
        }}
      >
        <Form layout="vertical">
          <Form.Item
            label="别名"
            help="这片叶子在别的教辅 / 老师口头里的叫法。别名只影响检索命中，不改归属。"
          >
            <Input
              value={aliasDraft}
              onChange={(e) => setAliasDraft(e.target.value)}
              placeholder="如：梯形拼图"
              maxLength={30}
              onPressEnter={() => {
                if (aliasDraft.trim()) {
                  onAddAlias(selectedKey, aliasDraft.trim())
                  setAliasOpen(false)
                }
              }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 改名 */}
      <Modal
        title={`改名 · ${node.label}`}
        open={renameOpen}
        okText="改名"
        cancelText="取消"
        okButtonProps={{ disabled: nameDraft.trim().length === 0 }}
        onCancel={() => setRenameOpen(false)}
        onOk={() => {
          onRename(selectedKey, nameDraft.trim())
          setRenameOpen(false)
        }}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="改名会波及题目"
          description={`这片叶子下面挂着 ${count} 道题，它们的 treePath 末段存的是旧名。真改名必须连带回写这 ${count} 道题，本页只演示改名后的样子。`}
        />
        <Form layout="vertical">
          <Form.Item label="新名称">
            <Input value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} maxLength={40} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}

export default LeafDetail
