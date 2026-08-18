import { Button, Result } from 'antd'
import { Link } from 'react-router-dom'

/** 兜底 404（挂在 Shell 里，保留侧栏方便回去） */
export default function NotFound() {
  return (
    <Result
      status="404"
      title="404"
      subTitle="这个地址不在 V2.1 的导航里（左侧菜单列的就是全部页面）。"
      extra={
        <Link to="/">
          <Button type="primary">回工作台</Button>
        </Link>
      }
    />
  )
}
