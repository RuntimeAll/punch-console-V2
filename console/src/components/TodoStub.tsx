import { Card, Tag } from 'antd'

/**
 * 占位桩：地基工留的空位，页面组填完肉之后**把这个组件删掉**。
 * 走查时页面上还挂着 TODO 卡片 = 这页还没做完，一眼可见。
 */
export function TodoStub({ items }: { items: string[] }) {
  return (
    <Card
      size="small"
      title={
        <span>
          <Tag color="orange">TODO</Tag>
          本页待填内容（做完请删除本组件）
        </span>
      }
      styles={{ body: { paddingTop: 8 } }}
    >
      <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 2, color: 'rgba(0,0,0,0.65)' }}>
        {items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ol>
    </Card>
  )
}

export default TodoStub
