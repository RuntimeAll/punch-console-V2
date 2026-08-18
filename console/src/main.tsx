// 🔴 React 19 + antd 5 必需的兼容补丁，必须排在所有 antd import 之前
import '@ant-design/v5-patch-for-react-19'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import 'antd/dist/reset.css'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* 全站中文 + antd 5 默认亮色主题；朴素学术风：圆角收小、不改主色、不加自定义配色 */}
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: { borderRadius: 4, fontSize: 14, colorBgLayout: '#f5f5f5' },
        components: {
          Layout: { headerBg: '#ffffff', headerHeight: 56, headerPadding: '0 16px', siderBg: '#ffffff' },
          Menu: { itemBorderRadius: 4 },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </StrictMode>,
)
