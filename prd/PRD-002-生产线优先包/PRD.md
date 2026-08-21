# PRD-002 · 生产线优先包（批次② · 每日打卡+举一反三真跑）

> 立卡：2026-08-18（调度中心发号）｜状态：✅ **已完成**（2026-08-21 调度中心补记：
> 卡内各件随批次战役逐一落地——KG 工具+回流通路+六 skill+库中心组卷渲染+D-20 检索三层
> +D-21 等级审全部收口，判据见 CLAUDE.md §6 与 记录/迁移记录.md；本卡未单独收口是记账疏漏，
> 现补正。后续 KG 演进归 PRD-009、产出归 PRD-010）
> 🔴 动因（用户原话）：*"我的重点是每日打卡，还有举一反三，使用频率非常高，我希望在我使用的时候越用，
> 我的知识库就越厚，而且对后续的备课+出题质量会直线上升，特别是出试卷和出打卡的时候。"*
> 前置：批次① ✅（两库真、三闸绿、判据 134 条在库）。正本：认知/数据结构.md、认知/业务流程.md。

## 0. 一句话

让**每日打卡**和**举一反三**在 v2 真库上跑起来，并把**飞轮**焊死：每次出题都让知识库变厚一分。

## 1. 🔴 飞轮铁律（本卡的灵魂，写死进每个 skill，不是可选项）

1. **出题必回流**：打卡册/变式卷出完，每道题入 kb.question（带 blocks_json v2 + 血缘 mother_qid/variant_op +
   考点 question_kp 叶子 + source_kind='model'/'manual'）——通过闸（validate_blocks/叶子闸/执行阀）才算出完；
2. **模型必留档**：母题定性产出的解题模型进 solution_model（触发→动作二元组+tier/freq）；
   DSL 出题路径进 exam_model（每个考点都能持续再出题）；
3. **出题前必查库**：相似前查（match_key）→ 模型快线（库里有模型直接用）→ 考点覆盖对账（这个考点已有几题/几模型）；
4. **每次执行落 skill_log**；判据沉淀随手记（criterion）。

## 2. 交付清单

| # | 件 | 说明 |
|---|---|---|
| 1 | `工具箱\kg\` KG 建树工具 | 沿用老区 id 契约（每 3 位一层）+ 新名字 + 别名表；命令：建枝/挂叶/加别名/resolve/merge；🔴 **按需铺枝**（本卡只铺第一枝：用户当前在练的专项所在册，如 浙教七上·有理数 或按用户点的） |
| 2 | `工具箱\回流\` 自产题入库轻通路 | 吃"题目 JSON（块流 v2）+ 考点名 + 血缘"，过三闸入 question；给 skill 调用 |
| 3 | skill **每日打卡** | 四步（业务流程.md §二）：母题定性→选版式初稿（🔴 用户点头才铺全册）→铺开+DSL 留档→发布（网盘+artifact 挂账带宣发字段）；出题段调「举一反三」 |
| 4 | skill **举一反三** | 四步（§三）：认母题→深解析（solution_model 入库）→算子调配（认识懂变·变一变二，tier/freq 表驱动）→变体全量实算过闸+血缘回流 |
| 5 | skill **渲染出件** | HTML→Chrome→PDF；骨架白搬老区 punchkit（LAYOUT 换装制）；题目卷/解析卷分双 PDF；封面目录三件套；template 表登记 |
| 6 | skill **网盘分发** | 白搬老区 panctl.py（官方 API 上传）+ panbrowser.py（持久浏览器建分享）；改路径进 v2；🔴 改版重传必 `--force` 并验 fs_id 变化（老坑） |
| 7 | skill **发布物料** | 小红书文案+配图+AB 隔离闸（参照老件，物料落 artifact 宣发字段） |
| 8 | skill **资料挂账** | artifact 登记原语（产线出货一条命令挂账） |

## 3. 可白搬资产（老区只读，拷进 v2 再改）

- DSL 表达式树出题器：老区各打卡册 `_源/`（如 三上混合运算 的结构型题 DSL）；
- 验算闸：`解题模型库\_验算\逐行恒等校验.py`（自编题六查的机器底座）；
- punchkit 版式骨架：`每日打卡` skill 的 `_模板/`（骨架学科无关×渲染器两层）；
- 网盘双通路脚本：`网盘分发` skill 的 `scripts\panctl.py`/`panbrowser.py`（凭据在老区 password/baidu-pan.env——
  🔴 拷进 v2\password\，不引用老区）；
- 老区经验判据已在 kb.criterion 里 134 条，skill 开工时按线注入。

## 4. 铁律

- 老区一律只读；skill 编排层全部 v2 化（写 v2 两库，绝不出现 teacher-mcp/prod 调用）；
- 主位运行态纪律照 CLAUDE.md §2；py utf-8 头；Chrome 无头配方照 CLAUDE.md §5；
- 自编题交付前逐题机器实算全绿（方法错比答案错更坑）；题目卷与解析卷分双 PDF；
- 🔴 **实弹验收**（出口判据）：用本卡产线**真出一本小册**（建议 5 天×N 题小样，专项由用户点）：
  KG 首枝铺好→举一反三出题→回流入库→渲染双 PDF→网盘上传→artifact 挂账——全链走通，
  然后回查库：题在、血缘在、模型在、DSL 在、skill_log 在。

## 5. 开工提示词（独立 session 用；调度中心直接派则忽略）

```
你在 D:\workplace\ai-bkb-v2 领 PRD-002 独立完成。先读根 CLAUDE.md、认知/业务流程.md、本卡全文。
开工领 worktree（CLAUDE.md §7）；两库只经 工具箱 脚本与闸写入；老区只读、资产拷入再改；
交付按 §2 顺序（先工具后 skill 后实弹），每完成一件 commit 并在卡 §6 勾进度；
实弹验收的专项选择与初稿样张，停下来等用户点头（这是四步流程的固有闸，不算违背"不停下等人"）。
```

## 6. 进度

- [x] 1 KG 建树工具+首枝（工具箱/kg/：kg_tool.py 建枝/挂叶/别名/resolve/merge + 首枝spec浙教七上·33叶沙盘全绿；叶子闸补退役/层级两闸；主位铺枝待合并后执行）
- [x] 2 回流入库轻通路（工具箱/回流/：ingest_flow.py 三闸+相似前查+血缘校验+promote；model_tool.py 模型留档+考点覆盖对账；沙盘 2 好题入库、6 类坏题全拒）
- [x] 3 skill 每日打卡（四步+飞轮铁律写死；DSL 底座=工具箱/dsl/有理数混合运算_qbank.py 已平移自证 ALL PASS）
- [x] 4 skill 举一反三（四步+血缘；快线三闸+答案不撞+表述闸；模型走 model_tool、题走 ingest_flow）
- [x] 5 skill 渲染出件（punchkit 平移 v2 路径全通；Chrome 三坑；template-add 登记原语）
- [x] 6 skill 网盘分发（panctl/panbrowser 平移改 v2 password；--force+fs_id 铁律；总表落 记录/网盘分发/）
- [x] 7 skill 发布物料（三件套+AB隔离闸/文案查重平移；口径正本落 记录/发布物料正本.md；宣发字段进 artifact.note）
- [x] 8 skill 资料挂账（工具箱/挂账/artifact_tool.py：add/link/note/status+template 登记，文件真存在闸+叶子闸）
- [ ] 9 🔴 实弹验收一本小册（全链+回查库）——**进行中·挂起在样张停点**（2026-08-18 用户指令先铺代码）：
  专项=浙教七上·有理数；KG 首枝已铺真库（48 节点/33 叶）；SM×1+EM×5 已留档；
  60 题 verify 全绿、D1 样张双 PDF 已出（产物/打卡/七上有理数五天打卡/）；
  待用户点头样张 → 铺全册 → 回流入库 → 渲染双 PDF → 网盘 → 挂账 → 回查库
- [x] 补 代码补全批（2026-08-18，三 opus 子代理并行）：发布包.py+合成封面.py 移植（修老区号↔版交叉 bug）、
  封面目录模板链移植（目录 5 行前置闸）、KG维护/答案实算闸 skill 壳、编制表 7/8 收口
- [ ] 10 🔴 **库中心重构**（2026-08-18 用户拍板追加：*"出题和打卡都得拿我们知识库，出来的题目和产线
  也都得存系统里面来，后面我拿题目还有打卡都是可以从页面上打开看到结果的，而且是直接入库了的"*）：
  - [x] 10a 正本+DDL：数据结构 §2.6b 载体域 paper/paper_item；业务流程 §二/§三改库中心口径；
    DDL 追加并主位显式执行（badcdfb）
  - [x] 10b 组卷工具 paper_tool（工具箱/组卷/：assemble 库存未用优先取题+组卷闸四条/render-pack/v1 导出/
    finalize 定稿+promote+覆盖考点回填/list/show；幂等重排）+ 每日打卡·举一反三两线 skill 改库中心口径；
    artifact_tool 补 files 子命令（壳先建、PDF 后挂）；端到端沙盘自证全绿（含 3 反向用例，
    脚本=试验场/2026-08-18-库中心组卷沙盘/端到端自证.py 可一键复跑）
  - [x] 10c 渲染从库读 render_paper（工具箱/渲染/：render-pack/v1 → punchkit 双 PDF；blocks→槽位适配、
    ＝链两形态兼容、figure/option/table 显式拒渲；自证 34/34+PNG 目检；punchkit core 修第四坑进本体）
  - [x] 10d console 薄读 API（server/kb-read-api.mjs，node:sqlite 只读 :4310，7 端点）+ 真库两页
    （/kb/questions 左树右表+抽屉公式渲染、/kb/artifacts 册→天→卷下钻）；build 绿+截图目检+注入自测；
    修 antd Table 打回公式原文真 bug；mock 页一律未动
  - [ ] 10e 实弹按新管线重跑——**已到样张停点（2026-08-19）**：60 题净题面过闸入库（草稿，血缘 prov 60/60）
    →组 D1 paper（12 题）→render-pack→从库渲样张双 PDF 目检全对→展示台真库两页可见
    （题库 60 题公式真渲/资料册 1 册 1 卷 12 题；:4300 已重启带 /api/kb 代理，:4310 读 API 常驻）；
    修 Chrome 相对路径废 URL 实伤一处（core+render_paper 同修）。
    待用户点头 → 组 D2~D5 → 全册双 PDF → finalize（promote+定稿+覆盖考点回填）→ 网盘 → 挂账/物料
- [ ] 11 🔴 **知识库坚实批**（2026-08-19 用户三条拍板：①实弹册不再上网盘/发布（网盘与 V1 已有，不重复录入）
  ②计算题入库=DSL 批处理规律入库零 LLM（打标注册表下沉 DSL 本体，一条命令排班→入库→组卷，
  消灭每册手写编排脚本的损耗）③知识库先坚实、每日打卡与举一反三**挂起**，确认后再走）：
  - [x] 11a 语意层地基：question_vec DDL 主位执行 + D-20 落地口径进正本（本地 bge sidecar 零外部 API，
    venv 已建 工具箱/检索/.venv，模型复用 punch-console/embed/models 184M）+ 闸④ promote 前置闸进 gates
  - [x] 11b DSL 批处理入库 dsl_batch（一条命令零 LLM：预检模型留档→出题→verify→规律打标→入库→组卷；
    沙盘 16 题端到端+缺模型拒跑+坏答案拒入全验；--check-only 全回滚）
  - [x] 11c 入库闸补全：D-21 等级审实装（机械判级 L0~L3、scan+1、L2/L3 自动开图审工单、--skip-review 显式跳过）
    + 工单原语 tickets/ticket-done + 闸④扩「已驳回也拦」并接进 ingest promote 与 paper_tool finalize 两条通路；
    gates_test 14+31 / ingest_flow_test 19 全绿
  - [x] 11d 取用方式：D-20 三层全落（query_core 八维 56/56 断言、11 条拒查不静默；find_questions CLI；
    take 同核复用差额话术不变；API 扩参 13/13；语意层本地 bge 实测行程题置顶分差明显；
    修 sidecar stdin GBK 真坑）；全套五测复跑全绿后合并（d680909）
