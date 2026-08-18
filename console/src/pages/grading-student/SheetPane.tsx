import { Image, Space, Typography } from 'antd'

/**
 * 终审抽屉左栏：**当天卷面原图**（照片直显）。
 *
 * 🔴 判词两轮收敛：第一版做了 SVG 题位框 + 双向联动，用户裁「不需要这么复杂，
 *    把原图丢上来对比就行」——所以这版只做一件事：照片摆上来对着拍板，
 *    点图用 antd Image 自带的预览放大，定位靠人眼对题号。
 * 🔴 口径不变：终审看的是**整页原图**（批改线「整页直读」口径），不做逐题裁剪流。
 */
export function SheetPane({ photos, dateLabel }: { photos: string[]; dateLabel: string }) {
  return (
    <div className="gs-sheet">
      <div className="gs-sheet-bar">
        <Typography.Text strong style={{ fontSize: 13 }}>
          卷面原图
        </Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {dateLabel} · 共 {photos.length} 页 · 点图可放大
        </Typography.Text>
      </div>

      <div className="gs-sheet-box">
        <Image.PreviewGroup>
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {photos.map((src, i) => (
              <Image
                key={src}
                src={src}
                width="100%"
                alt={`卷面第 ${i + 1} 页`}
                style={{ borderRadius: 4, border: '1px solid #e8e8e8', display: 'block' }}
              />
            ))}
          </Space>
        </Image.PreviewGroup>
      </div>

      <Typography.Paragraph type="secondary" style={{ fontSize: 12, margin: '8px 0 0' }}>
        本地真卷直连（原型测试）；正式版 = 收件箱照片按批次挂接，本页不变。
      </Typography.Paragraph>
    </div>
  )
}

export default SheetPane
