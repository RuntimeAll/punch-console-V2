/**
 * 批次 → 卷面照片清单。
 *
 * 🔴 原型阶段用本地真卷测试显示效果（用户点名）：照片拷自老区
 * 订阅特训/学员/小崽子/批改拍照/第01~05天（每天两页），放 console/public/sheets/。
 * mock 批次的轨内天对不上照片天数时按 5 天循环取，只为看显示效果。
 * 正式版 = 收件箱照片按批次挂接（批改模块可迁云边界内），换掉本文件即可，页面不变。
 */
export function photosOfBatch(dayInTrack: number): string[] {
  const n = ((dayInTrack - 1) % 5) + 1
  return [`/sheets/d${n}-p1.jpg`, `/sheets/d${n}-p2.jpg`]
}
