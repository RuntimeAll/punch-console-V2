import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Button, Modal, Radio, Select, Typography, Upload } from 'antd'
import type { UploadFile } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { PaperKind } from './queue-view'
import { roster } from './queue-view'

/**
 * 收卷 —— 🔴 判词②：收卷录入**不配单开一页**，降格成队列页右上角的一个按钮 + 这个弹窗。
 *
 * 三步一屏（不是分页向导）：选谁 → 放照片 → 卷型。三步都在一屏里，
 * 因为这动作总共十几秒，分页反而更慢。
 * 🔴 弹窗里**不填轨、不填第几天**：认卷是编排器的活（收件中 → 待认卷 → 命中/多命中），
 *   在这里替机器把轨填了，等于把「多命中要人指定」那一格架空。
 * 🔴 mock 不真传：beforeUpload 一律返回 false，只留文件名。
 */

export interface IntakePayload {
  student: string
  /** 只留文件名（mock 不真传） */
  files: string[]
  kind: PaperKind
}

/** 一步：左边序号圈，右边内容 */
function Step({ no, title, children }: { no: number; title: string; children: ReactNode }) {
  return (
    <div className="gq-step">
      <div className="gq-step-no">{no}</div>
      <div className="gq-step-body">
        <div className="gq-step-title">{title}</div>
        {children}
      </div>
    </div>
  )
}

/** 走查用的示例照片（用户离线走查时不必真去挑文件） */
function sampleFile(seq: number): UploadFile {
  return { uid: `sample-${seq}`, name: `IMG_20260817_09${40 + seq}.jpg`, status: 'done' }
}

export function IntakeModal({
  open,
  onCancel,
  onSubmit,
  onWarn,
}: {
  open: boolean
  onCancel: () => void
  onSubmit: (payload: IntakePayload) => void
  /** 校验没过时喊一声（message 由页面统一持有，弹窗不自己开 message 上下文） */
  onWarn: (text: string) => void
}) {
  const [student, setStudent] = useState<string>('')
  const [files, setFiles] = useState<UploadFile[]>([])
  const [kind, setKind] = useState<PaperKind>('自动')

  // 每次打开都清干净：上一次收卷的残留留在这儿最容易收错人
  useEffect(() => {
    if (!open) return
    setStudent('')
    setFiles([])
    setKind('自动')
  }, [open])

  const submit = () => {
    if (!student) {
      onWarn('先选学员：收件箱得知道这批照片是谁的')
      return
    }
    if (files.length === 0) {
      onWarn('至少放一张照片进来（mock 不真传，只记文件名）')
      return
    }
    onSubmit({ student, files: files.map((f) => f.name), kind })
  }

  return (
    <Modal
      open={open}
      title="收卷"
      okText="收下这批"
      cancelText="取消"
      onOk={submit}
      onCancel={onCancel}
      width={560}
      destroyOnHidden
    >
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4 }}>
        收下即入队，状态从「收件中」起步：90 秒判稳（防拍一半）后自动转「待认卷」，
        是哪一天的哪张卷由编排器认，认不出才会踢回队列让你指定。
      </Typography.Paragraph>

      <Step no={1} title="谁的卷">
        <Select
          value={student || undefined}
          onChange={setStudent}
          placeholder="选学员（代号）"
          style={{ width: 300 }}
          options={roster.map((r) => ({
            value: r.code,
            label: `${r.code}　${r.grade}`,
          }))}
        />
        {student ? (
          <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
            在练：{roster.find((r) => r.code === student)?.running.join('、') || '暂无在练的轨'}
            　（轨与第几天由编排器认，这里不填）
          </Typography.Text>
        ) : null}
      </Step>

      <Step no={2} title="照片">
        <Upload.Dragger
          multiple
          accept="image/*"
          fileList={files}
          beforeUpload={() => false}
          onChange={(info) => setFiles(info.fileList)}
          style={{ padding: '8px 0' }}
        >
          <p className="ant-upload-drag-icon" style={{ marginBottom: 4 }}>
            <InboxOutlined />
          </p>
          <p style={{ fontSize: 13, margin: 0 }}>把卷子照片拖进来，或点这里选</p>
          <p style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', margin: '2px 0 0' }}>
            原型不真传，只记文件名；真通路是家长拍完直接落收件箱
          </p>
        </Upload.Dragger>
        <div style={{ marginTop: 8 }}>
          <Button size="small" onClick={() => setFiles((prev) => [...prev, sampleFile(prev.length + 1)])}>
            塞一张示例照片
          </Button>
          <Typography.Text type="secondary" style={{ fontSize: 12, marginInlineStart: 8 }}>
            已放 {files.length} 张
          </Typography.Text>
        </div>
      </Step>

      <Step no={3} title="卷型（可选）">
        <Radio.Group value={kind} onChange={(e) => setKind(e.target.value)} optionType="button" size="small">
          <Radio.Button value="自动">自动</Radio.Button>
          <Radio.Button value="手抄">手抄</Radio.Button>
          <Radio.Button value="打印">打印</Radio.Button>
        </Radio.Group>
        <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
          默认「自动」＝交给编排器判。只有拿不准（手抄卷题号乱、打印件带答题卡）时才手动点一下。
        </Typography.Text>
      </Step>
    </Modal>
  )
}

export default IntakeModal
