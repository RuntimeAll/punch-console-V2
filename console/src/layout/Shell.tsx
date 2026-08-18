import { useState } from 'react'
import type { ReactNode } from 'react'
import { Layout, Menu, Tag } from 'antd'
import type { MenuProps } from 'antd'
import {
  ApartmentOutlined,
  CheckSquareOutlined,
  DatabaseOutlined,
  DesktopOutlined,
  FolderOpenOutlined,
  ImportOutlined,
  PrinterOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

/**
 * 🔴 全站导航正本 —— 页面组不许自行加菜单项，要加先找用户拍板。
 *
 * V2.1 第二轮改成**分组结构**（三个 SubMenu + 四个单页），因为页面从 6 个涨到 11 个，
 * 平铺一列已经读不出「哪几件事是一条线上的」：
 *   工作台 / 题库 / 资料清单
 *   【批改】学员 · 队列            ← 学生的卷子
 *   【录入】录入记录 · 审核台      ← 题库的入口
 *   【维护】知识图谱 · 考察模型 · 错因管理 · 判据沉淀  ← 低频但必须记账的四样
 *   模版库
 * 🔴 分组名（批改/录入/维护）本身不是页面、不给路由，点它只展开。
 * 🔴 Sider 收起时 SubMenu 自动变浮层，所以每个分组必须有 icon（收起后只剩 icon 认路）。
 *
 * 🔴 第三轮改名（用户判词③：全站禁「台账」黑话，一律说人话）：
 *   资料台账 → 资料清单 ｜ 录入·台账 → 录入记录 ｜ 导出预览 → 模版库
 *   批改的「待办」删了：待办只是队列的一个筛子（/grading/queue?mine=1），不配单开一项。
 */

type NavLeaf = { key: string; label: string }
type NavItem =
  | { kind: 'leaf'; key: string; icon: ReactNode; label: string }
  | { kind: 'group'; key: string; icon: ReactNode; label: string; children: NavLeaf[] }

const NAV: NavItem[] = [
  { kind: 'leaf', key: '/', icon: <DesktopOutlined />, label: '工作台' },
  // 🔴 待办列表 = 自由事项表（定稿 D-14），紧挨工作台：一个是「机器算出来今天该我干什么」，
  //    一个是「我和 agent 随手记下来的活儿」，两件事挨着摆但绝不合并
  { kind: 'leaf', key: '/todo', icon: <CheckSquareOutlined />, label: '待办列表' },
  { kind: 'leaf', key: '/questions', icon: <DatabaseOutlined />, label: '题库' },
  { kind: 'leaf', key: '/artifacts', icon: <FolderOpenOutlined />, label: '资料清单' },
  {
    kind: 'group',
    key: 'g-grading',
    icon: <TeamOutlined />,
    label: '批改',
    children: [
      { key: '/grading', label: '学员' },
      { key: '/grading/queue', label: '队列' },
    ],
  },
  {
    kind: 'group',
    key: 'g-ingest',
    icon: <ImportOutlined />,
    label: '录入',
    children: [
      { key: '/ingest', label: '录入记录' },
      { key: '/review', label: '审核台' },
    ],
  },
  {
    kind: 'group',
    key: 'g-maint',
    icon: <ApartmentOutlined />,
    label: '维护',
    children: [
      { key: '/kg', label: '知识图谱' },
      { key: '/model', label: '考察模型' },
      { key: '/cause', label: '错因管理' },
      // 错因管理沉淀「学生的错」（挂考点），判据沉淀沉淀「产线自己的判断经验」（挂产线），两页别混
      { key: '/criteria', label: '判据沉淀' },
    ],
  },
  { kind: 'leaf', key: '/export-preview', icon: <PrinterOutlined />, label: '模版库' },
]

/** 三个分组默认全展开（走查时一眼看全 11 个页面，不用逐个点开找） */
const OPEN_KEYS = NAV.filter((n) => n.kind === 'group').map((n) => n.key)

/**
 * 当前路径归到哪个菜单项高亮。
 * 🔴 顺序敏感：更长的前缀必须写在前面（/grading/queue 要排在 /grading 之前，
 *   否则队列页会把「学员」点亮）。子路由 /questions/:id、/grading/:code 亮父项。
 */
function activeKey(pathname: string): string {
  if (pathname === '/') return '/'
  // 🔴 /todo 必须排在 /grading/todo 的重定向之外单独认：两者不是一个东西
  if (pathname.startsWith('/todo')) return '/todo'
  if (pathname.startsWith('/grading/queue')) return '/grading/queue'
  if (pathname.startsWith('/grading')) return '/grading'
  if (pathname.startsWith('/questions')) return '/questions'
  if (pathname.startsWith('/artifacts')) return '/artifacts'
  if (pathname.startsWith('/ingest')) return '/ingest'
  if (pathname.startsWith('/review')) return '/review'
  if (pathname.startsWith('/kg')) return '/kg'
  if (pathname.startsWith('/model')) return '/model'
  if (pathname.startsWith('/cause')) return '/cause'
  if (pathname.startsWith('/criteria')) return '/criteria'
  if (pathname.startsWith('/export-preview')) return '/export-preview'
  return ''
}

/** NAV → antd Menu items（分组项只展开不跳转，所以 label 是纯文本不套 Link） */
const MENU_ITEMS: MenuProps['items'] = NAV.map((n) =>
  n.kind === 'leaf'
    ? { key: n.key, icon: n.icon, label: <Link to={n.key}>{n.label}</Link> }
    : {
        key: n.key,
        icon: n.icon,
        label: n.label,
        children: n.children.map((c) => ({ key: c.key, label: <Link to={c.key}>{c.label}</Link> })),
      },
)

export function Shell() {
  const [collapsed, setCollapsed] = useState(false)
  const { pathname } = useLocation()

  return (
    <Layout style={{ minHeight: '100%' }}>
      {/* 顶栏常驻评审标注，任何页面都不许遮挡或改写 */}
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #f0f0f0',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'rgba(0,0,0,0.88)' }}>知识工厂 V2.1</span>
          <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>V2.1 原型</span>
        </div>
        <Tag color="orange" style={{ marginInlineEnd: 0 }}>
          mock 数据 · 设计稿评审版
        </Tag>
      </Header>

      <Layout>
        <Sider
          theme="light"
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={188}
          style={{ borderRight: '1px solid #f0f0f0' }}
        >
          <Menu
            mode="inline"
            selectedKeys={[activeKey(pathname)]}
            defaultOpenKeys={OPEN_KEYS}
            style={{ borderInlineEnd: 'none', paddingTop: 8 }}
            items={MENU_ITEMS}
          />
        </Sider>

        <Content style={{ padding: 16, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default Shell
