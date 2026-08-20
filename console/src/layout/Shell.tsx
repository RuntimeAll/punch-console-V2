import { useState } from 'react'
import type { ReactNode } from 'react'
import { Layout, Menu, Tag } from 'antd'
import type { MenuProps } from 'antd'
import {
  ApartmentOutlined,
  CheckSquareOutlined,
  DatabaseOutlined,
  FolderOpenOutlined,
  PrinterOutlined,
  ProfileOutlined,
} from '@ant-design/icons'
import { Link, Outlet, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

/**
 * 🔴 全站导航正本 —— 页面组不许自行加菜单项，要加先找用户拍板。
 *
 * 2026-08-21 真库转正版（用户令「真库直接覆盖回去，待办留到一个目录下面」）：
 *   题库 / 资料册 / 卷库                ← 真库正式页（原「·真库」组转正，后缀摘掉）
 *   【维护】知识图谱 · 考察模型 · 判据沉淀 ← 真库正式页
 *   模版库                              ← 真库正式页（老 /export-preview mock 已退役）
 *   【待办 · 未去mock】工作台 · 待办列表 · 批改两页 · 录入两页 · 错因管理
 *      ← 还没真库化的页面全收这一组，真库化一页挪出一页（批改=PRD-005，录入=PRD-006）
 * 🔴 分组名本身不是页面、不给路由，点它只展开。
 * 🔴 Sider 收起时 SubMenu 自动变浮层，所以每个分组必须有 icon（收起后只剩 icon 认路）。
 * 🔴 全站禁「台账」黑话（用户判词③），命名一律说人话。
 */

type NavLeaf = { key: string; label: string }
type NavItem =
  | { kind: 'leaf'; key: string; icon: ReactNode; label: string }
  | { kind: 'group'; key: string; icon: ReactNode; label: string; children: NavLeaf[] }

const NAV: NavItem[] = [
  { kind: 'leaf', key: '/questions', icon: <DatabaseOutlined />, label: '题库' },
  { kind: 'leaf', key: '/artifacts', icon: <FolderOpenOutlined />, label: '资料册' },
  // 卷库=paper 级视角，资料册=册级视角：同一批数据两个粒度，不合并
  { kind: 'leaf', key: '/papers', icon: <ProfileOutlined />, label: '卷库' },
  {
    kind: 'group',
    key: 'g-maint',
    icon: <ApartmentOutlined />,
    label: '维护',
    children: [
      { key: '/kg', label: '知识图谱' },
      { key: '/model', label: '考察模型' },
      { key: '/criteria', label: '判据沉淀' },
    ],
  },
  { kind: 'leaf', key: '/templates', icon: <PrinterOutlined />, label: '模版库' },
  {
    // 🔴 待办组 = 还没接真库的 mock 设计稿，进页顶栏挂橙标。真库化一页挪出一页，清空即删组。
    kind: 'group',
    key: 'g-todo-mock',
    icon: <CheckSquareOutlined />,
    label: '待办·未去mock',
    children: [
      { key: '/', label: '工作台' },
      // 待办列表 = 自由事项表（定稿 D-14），与工作台的「现算待办视图」并列不合并
      { key: '/todo', label: '待办列表' },
      { key: '/grading', label: '批改·学员' },
      { key: '/grading/queue', label: '批改·队列' },
      { key: '/ingest', label: '录入记录' },
      { key: '/review', label: '审核台' },
      // 错因管理沉淀「学生的错」（挂考点），判据沉淀沉淀「产线自己的判断经验」（挂产线），两页别混
      { key: '/cause', label: '错因管理' },
    ],
  },
]

/** 分组默认全展开（一眼看全所有页面，不用逐个点开找） */
const OPEN_KEYS = NAV.filter((n) => n.kind === 'group').map((n) => n.key)

/** 还没真库化的 mock 页前缀（与导航「待办·未去mock」组严格同一份名单，顶栏橙标靠它判） */
const MOCK_PREFIXES = ['/todo', '/grading', '/ingest', '/review', '/cause']
const isMockPath = (pathname: string) =>
  pathname === '/' || MOCK_PREFIXES.some((p) => pathname.startsWith(p))

/**
 * 当前路径归到哪个菜单项高亮。
 * 🔴 顺序敏感：更长的前缀必须写在前面（/grading/queue 要排在 /grading 之前，
 *   否则队列页会把「学员」点亮）。子路由 /grading/:code 亮父项；/kb/* 老地址只是
 *   重定向的一瞬，不用认。
 */
function activeKey(pathname: string): string {
  if (pathname === '/') return '/'
  if (pathname.startsWith('/grading/queue')) return '/grading/queue'
  const PREFIXES = [
    '/questions', '/artifacts', '/papers', '/kg', '/model', '/criteria', '/templates',
    '/todo', '/grading', '/ingest', '/review', '/cause',
  ]
  for (const p of PREFIXES) if (pathname.startsWith(p)) return p
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
      {/* 顶栏常驻数据源标注，任何页面都不许遮挡或改写 */}
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
          <span style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)' }}>桌面工厂控制台 · :4300</span>
        </div>
        {/* 🔴 顶栏这枚标签是「你现在看的是真是假」的唯一告示，必须随页面如实变：
            正式页直连 kb.db 只读；「待办·未去mock」组仍是 mock 设计稿。挂错标签 = 说谎。 */}
        {isMockPath(pathname) ? (
          <Tag color="orange" style={{ marginInlineEnd: 0 }}>
            mock 设计稿 · 待去mock
          </Tag>
        ) : (
          <Tag color="green" style={{ marginInlineEnd: 0 }}>
            真库数据 · 只读（kb.db）
          </Tag>
        )}
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
