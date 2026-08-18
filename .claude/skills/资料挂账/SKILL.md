---
name: 资料挂账
description: 产线出货一条命令挂账进 artifact 资料一本账（D-7）——登记成品件/覆盖考点/来源产线/所用模版/网盘链接/宣发字段，改状态（在产→已交付→已上架）。当用户说"挂账""登记这本册子""资料入账""改成已交付""这册链接是什么"时用。底座=工具箱/挂账/artifact_tool.py（kb.db 的 artifact/template 唯一写入通路，每次执行自动落 skill_log）。页面只展示，写动作全走本 skill。
---

# 资料挂账 —— artifact 登记原语

## 挂账时机

产线出货即挂（每日打卡 §4 / 举一反三交付段自动调本 skill）；**挂的是真出的货**——
工具会校验 files 指向的文件真实存在且是相对路径（绝对路径拒收）。

## 命令

```powershell
# 出货挂账（kind ∈ 打卡册/专项卷/举一反三/讲义/报告模版/其他）
python 工具箱/挂账/artifact_tool.py add --name <资料名> --kind 打卡册 `
  --file 产物/打卡/<册>/题目卷.pdf --file 产物/打卡/<册>/答案卷.pdf `
  --kp <考点名或id> --source-line 每日打卡 --template <模版id>

python 工具箱/挂账/artifact_tool.py link --id <A…> --url "<网盘链?pwd=码>"   # 网盘链接回填
python 工具箱/挂账/artifact_tool.py note --id <A…> --json <宣发字段.json>    # 宣发字段回填
python 工具箱/挂账/artifact_tool.py status --id <A…> --to 已交付            # 状态流转
python 工具箱/挂账/artifact_tool.py list                                    # 一本账总览
```

## 纪律

- kp 必须 resolve 到现行叶子（叶子闸同题目口径）；kp_ids_json 是将来开轨 kp_scope 的取数源，宁缺勿脏。
- 文件指针全相对 v2 根；成品正本在 `产物/`，artifact 只存指针。
- template 未登记先走「渲染出件」§5 `template-add`。
- 状态语义：在产=还在做；已交付=发出去了（delivered_at 自动记）；已上架=进了店铺/小红书。
