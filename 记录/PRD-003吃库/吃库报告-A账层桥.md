# PRD-003 吃库 · A 账层桥运行报告

生成：2026-08-19 19:48:37｜模式：**apply（真写库）**

## 账面

| 段 | 源行数 | 结果 |
|---|---:|---|
| doc → artifact | 82 | 入库 0｜跳过(幂等) 82｜拒收 0 |
| doc_member → artifact_member | 24 | 入库 0｜跳过(幂等) 24｜拒收 0 |
| material → material | 49 | 入库 0｜跳过(幂等) 49｜拒收 0 |
| asset → punch_map/files_json | 735 | 入库 0｜跳过(幂等) 735｜拒收 0 |

- 目标库 artifact.kind 词表：('打卡册', '专项卷', '举一反三', '讲义', '报告模版', '其他')
- 目标库 artifact.sale_state 词表：('在售', '待整理', '停售')
- sale_state 取值分布（本次规划）：

## 增量补挂 0 册

> 幂等跳过只跳"建行"不跳"补账"：册早在库、这轮又冒出新资产落位时，把新落位**并进**（不覆盖）它的 `artifact.files_json`。

- 本次补挂 **0 册**（跳过册的 files_json 与资产落位已经对齐）。

## 实写入

| 表/动作 | 行数 |
|---|---:|

## 守恒闸 G4：`files_json` ≡ `punch_map(kind='asset')`

- 本次审的是 **库态**（写完这一刻库里的两本账）
- punch_map 资产落位 **735** 条｜已吃册 files_json 里落在 `产物/历史打卡/` 下的 **735** 条
- 失联（进了 punch_map 却没人指）：**0** 条
- 幽灵（files_json 里有却没登记）：**0** 条

✅ 两边对齐。

## 人审清单（0 条）

> 拿不准的一律进这张单子，脚本绝不静默猜。

> 🔴 **老区绝对路径只作溯源**：源列 `doc.源文件路径` 落 `artifact.note` 时改名 `punch_溯源路径`，并强制同行落兄弟键 `punch_溯源路径_说明="仅溯源非指针"`。本次新入库 0 册带此键（幂等跳过的册不重写 note）。它指的是老区 `D:\workplace\ai-bkb\…`（**只读、随时可能挪窝**），谁都别拿它 open()——本库唯一的文件指针是 `files_json` 里的相对路径。

**空**。

## 幂等口径

- 骨架 = `punch_map(kind, punch_id)`：重跑时已在表里的一律跳过——不重建、不覆盖；
- `artifact_member` 无 punch_map 位（表的 kind CHECK 只认 doc/material/question/asset），
  幂等靠主键 `(parent_id, member_id)` 先查后插；
- 🔴 `sale_state` 是人工列，桥只在**首次建行**时写源值，第二遍绝不回写——
  「能发≠已发」的血案不许在吃库时复发。

