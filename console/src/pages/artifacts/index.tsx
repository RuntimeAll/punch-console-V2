import { useMemo, useState } from 'react'
import { Button, Card, Descriptions, Drawer, Input, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PageFrame } from '@/components'
import type { Artifact } from '@/mock'
import { artifacts as mockArtifacts } from '@/mock'

/**
 * 资料清单 /artifacts
 * 归属：页面组「资料清单」。
 *
 * 🔴 这页就是「挂账 + 展示」的全部：这本册子是什么 / 做到哪一步 / 交付没有 / 文件在哪。
 *    成品由 agent 产出后挂账，所以**没有**新建、编辑、删除、审批、流程节点这些生产管理概念，
 *    唯一可写的就是抽屉里的备注（本地 mock 状态，刷新即还原）。
 *
 * 版式 = 若依式三段：筛选 → 表格 → 行内「查看」抽屉。
 */

const KINDS: Artifact['kind'][] = ['打卡册', '专项卷', '举一反三', '讲义']
const STATUSES: Artifact['status'][] = ['在产', '已交付', '已上架']

/** 状态 → Tag 颜色（只用 antd 默认色板，不自定义主色、不铺大色块） */
const statusColor: Record<Artifact['status'], string> = {
  在产: 'orange',
  已交付: 'blue',
  已上架: 'green',
}

/**
 * 文件指针里的「本地产物目录」是按类型的目录约定推导出来的示意值。
 * mock 的 Artifact 上没有文件路径字段，真接数据前这里显示的只是约定，抽屉里已注明。
 */
const dirOfKind: Record<Artifact['kind'], string> = {
  打卡册: '举一反三产物/打卡',
  专项卷: '举一反三产物/专项卷',
  举一反三: '举一反三产物/解题模型库',
  讲义: '讲义产物',
}

export default function Artifacts() {
  // 清单本地副本：备注编辑写回这里（mock 本地状态，不落任何后端）
  const [rows, setRows] = useState<Artifact[]>(mockArtifacts)

  // ── 筛选段 ──────────────────────────────────────────────
  const [kind, setKind] = useState<Artifact['kind'] | undefined>()
  const [status, setStatus] = useState<Artifact['status'] | undefined>()
  const [keyword, setKeyword] = useState('')

  // ── 抽屉 ────────────────────────────────────────────────
  const [current, setCurrent] = useState<Artifact | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [saved, setSaved] = useState(false)

  const openDrawer = (row: Artifact) => {
    setCurrent(row)
    setNoteDraft(row.note ?? '')
    setSaved(false)
  }

  const saveNote = () => {
    if (!current) return
    setRows((prev) => prev.map((r) => (r.id === current.id ? { ...r, note: noteDraft } : r)))
    setCurrent({ ...current, note: noteDraft })
    setSaved(true)
  }

  const filtered = useMemo(() => {
    const kw = keyword.trim()
    return rows.filter((r) => {
      if (kind && r.kind !== kind) return false
      if (status && r.status !== status) return false
      // 关键字同时搜名称与备注（清单里备注常常才是真正记事的地方）
      if (kw && !`${r.name}${r.note ?? ''}`.includes(kw)) return false
      return true
    })
  }, [rows, kind, status, keyword])

  const columns: ColumnsType<Artifact> = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, row) => (
        <div>
          <Typography.Link onClick={() => openDrawer(row)}>{name}</Typography.Link>
          <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>{row.id}</div>
        </div>
      ),
    },
    { title: '类型', dataIndex: 'kind', key: 'kind', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (s: Artifact['status']) => <Tag color={statusColor[s]}>{s}</Tag>,
    },
    {
      title: '交付日期',
      dataIndex: 'deliveredAt',
      key: 'deliveredAt',
      width: 110,
      render: (d?: string) => d ?? '—',
    },
    {
      title: '链接',
      dataIndex: 'link',
      key: 'link',
      width: 90,
      render: (link?: string) =>
        link ? (
          <Typography.Link href={link} target="_blank" rel="noreferrer">
            网盘
          </Typography.Link>
        ) : (
          <Typography.Text type="secondary">未建链</Typography.Text>
        ),
    },
    {
      title: '备注',
      dataIndex: 'note',
      key: 'note',
      ellipsis: true,
      render: (n?: string) => n ?? '—',
    },
    {
      title: '操作',
      key: 'op',
      width: 70,
      render: (_, row) => (
        <Typography.Link onClick={() => openDrawer(row)}>查看</Typography.Link>
      ),
    },
  ]

  return (
    <PageFrame
      title="资料清单"
      desc={`成品的账本：共 ${rows.length} 条，当前筛出 ${filtered.length} 条（mock）。`}
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          只挂账与展示，生产过程归 agent；本页不做新建 / 编辑 / 删除
        </Typography.Text>
      }
    >
      {/* ① 筛选 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap size={8}>
          <Select
            placeholder="全部类型"
            allowClear
            style={{ width: 140 }}
            value={kind}
            onChange={setKind}
            options={KINDS.map((k) => ({ value: k, label: k }))}
          />
          <Select
            placeholder="全部状态"
            allowClear
            style={{ width: 140 }}
            value={status}
            onChange={setStatus}
            options={STATUSES.map((s) => ({ value: s, label: s }))}
          />
          <Input.Search
            placeholder="搜名称或备注"
            allowClear
            style={{ width: 260 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={setKeyword}
          />
          <Button
            onClick={() => {
              setKind(undefined)
              setStatus(undefined)
              setKeyword('')
            }}
          >
            重置
          </Button>
        </Space>
      </Card>

      {/* ② 表格 */}
      <Table<Artifact>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={filtered}
        pagination={false}
        locale={{ emptyText: '没有符合条件的成品' }}
      />

      {/* ③ 查看抽屉：成品信息 + 文件指针 + 备注（本地 mock 可编辑） */}
      <Drawer
        title={current?.name ?? ''}
        width={520}
        open={Boolean(current)}
        onClose={() => setCurrent(null)}
        destroyOnHidden
      >
        {current ? (
          <>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="清单编号">{current.id}</Descriptions.Item>
              <Descriptions.Item label="类型">{current.kind}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColor[current.status]}>{current.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="交付日期">{current.deliveredAt ?? '未交付'}</Descriptions.Item>
            </Descriptions>

            <Typography.Title level={5} style={{ marginTop: 20, marginBottom: 8, fontSize: 14 }}>
              文件指针
            </Typography.Title>
            <Descriptions size="small" column={1} bordered>
              <Descriptions.Item label="网盘链接">
                {current.link ? (
                  <Typography.Text copyable={{ text: current.link }}>
                    <Typography.Link href={current.link} target="_blank" rel="noreferrer">
                      {current.link}
                    </Typography.Link>
                  </Typography.Text>
                ) : (
                  <Typography.Text type="secondary">未建链（一册一条链接，双号共用）</Typography.Text>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="本地产物目录">
                <Typography.Text code style={{ fontSize: 12 }}>
                  {dirOfKind[current.kind]}/{current.name}/
                </Typography.Text>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 6, fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>
              本地目录按类型的目录约定推导显示；mock 数据里没有文件路径字段，接真数据时需要补。
            </div>

            <Typography.Title level={5} style={{ marginTop: 20, marginBottom: 8, fontSize: 14 }}>
              备注
            </Typography.Title>
            <Input.TextArea
              rows={5}
              value={noteDraft}
              onChange={(e) => {
                setNoteDraft(e.target.value)
                setSaved(false)
              }}
              placeholder="记这本册子的口径、坑、待办（例：浙教版口径；快速训练版砍半）"
            />
            <Space style={{ marginTop: 8 }} size={8}>
              <Button type="primary" onClick={saveNote} disabled={noteDraft === (current.note ?? '')}>
                保存备注
              </Button>
              {saved ? (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  已保存（mock 本地状态，刷新页面即还原）
                </Typography.Text>
              ) : null}
            </Space>
          </>
        ) : null}
      </Drawer>
    </PageFrame>
  )
}
