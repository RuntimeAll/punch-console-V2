---
name: 每日打卡
description: 制作/续造「每日打卡」类册子——N 天×每天 M 题×一天一页的连续练习册（题目卷+答案卷双 PDF，发网盘售卖）。当用户说"做一个N天打卡""每日打卡""打卡册""每日一练""连着练N天""再来一期打卡""续造下一期""改打卡版式/题量""出一本小册"时用。四步=母题定性→选版式初稿(🔴用户点头才铺全册)→全量铺开(DSL留档+实算全绿)→发布(网盘+artifact挂账带宣发字段，发布动作永远用户手机人工)。🔴 v2 编排：两库只经 工具箱 脚本与闸写入，出题段调「举一反三」，渲染调「渲染出件」，上传调「网盘分发」，物料调「发布物料」，挂账调「资料挂账」。绝不调老区/备课帮任何服务。
---

# 每日打卡 —— 四步流水线（流程正本=认知/业务流程.md §二）

## 🔴🔴 飞轮铁律（写死，不是可选项——每次出题都要让知识库变厚一分）

1. **出题必回流**：册子出完，每道题经 `工具箱/回流/ingest_flow.py` 入 kb.question——
   blocks v2 + 血缘（prov 记 model_id/params/seed，变式带 mother_qid/variant_op）+ 考点叶子 +
   source_kind='model'（自编参数化）/'manual'（手写）。**过三闸才算出完**，拒收就修，不许绕。
2. **模型必留档**：母题定性产出的解题模型 `model_tool.py solution-add` 进 solution_model；
   每个考点的出题路径（DSL 生成器）`model_tool.py exam-add` 进 exam_model（dsl_ref 指向真文件）——
   保证**每个考点后续都能持续再出题**。
3. **出题前必查库**：`model_tool.py coverage --kp <考点>`（这考点已有几题几模型）→ 有模型走快线；
   相似前查由 ingest_flow 的 match_key 闸兜底。
4. **每次执行落 skill_log**：工具自动落账；步骤级里程碑用
   `python 工具箱/库/log_skill.py 每日打卡 <动作> <成功|失败> "<要点>"` 补总账。
   判据沉淀随手记（criterion，见 工具箱/库/import_criteria.py 的判重口径）。

## 0. 开工前

- **判据注入**：`python 工具箱/库/inject_criteria.py 出题 渲染`——现行判据全量读一遍再动手。
- **问清三级规格**：天数 × 每天题量 × 每天结构（几个小节/题型配比/难度曲线——逐日加码还是平行，
  用户不说就问）。题源若是教辅：先问"照录原题"还是"平行改编"。
- **KG 对齐**：本册考点先 `工具箱/kg/kg_tool.py resolve <考点名>` 逐个通；resolve 不到→
  `add-leaf`/`alias` 先补 KG（枝没铺先铺枝），**绝不裸题开工**。

## 1. 第一步 · 母题定性

确定考察范围/考点/解题方式/核心关键：
- 每类题写清「触发特征→动作结论」→ `model_tool.py solution-add`（tier/freq 双旋钮，表驱动）；
- 计算类直接定 DSL 配方（参数域/难度档）→ 写生成器（见 §2）后 `model_tool.py exam-add`。
- 现成 DSL 底座：`工具箱/dsl/有理数混合运算_qbank.py`（13 生成器+verify 双路闸，照它的骨架写新的）；
  结构型题参考 `工具箱/dsl/参考-三上混合运算/`（表达式树；🔴 其出题器 API 段 v2 禁用）。

## 2. 第二步 · 选版式出初稿（🚧 审核门）

1. 选模版别 fork：`cd .claude/skills/每日打卡/_模板 && python -m punchkit` 看骨架菜单；
   一本册 = 骨架(layouts, 学科无关) × 渲染器(renderers, 学科相关)；`LAYOUT='<key>'` 一行换装。
   🔴 绝不在册 `_源/` 里私长 CSS。
2. 建 `产物/打卡/<册名>/_源/`：`qbank.py`（DSL 单一事实源：题面/过程/答案同源一组参数，
   verify() 三断言=题面零重复/同天同节答案不撞/题量配比）+ `days.py`（分天排班表）+
   `gen_打卡.py`（瘦配置，调 punchkit；交付版 watermark=None）。
3. 只出**第 1 天**样张双 PDF（走「渲染出件」skill 的管道与坑单）+ `大纲.md`（考点覆盖表），
   PDF 转 PNG 逐页目检后交用户。
4. 🔴🔴 **门禁：用户点头（含排版过审）才进第三步**——这是流程固有闸，不算"停下等人"违例。

## 3. 第三步 · 全量铺开（DSL 出题路径必留档）

1. 钉死定稿模板，扩 `days.py` 到 dayN；出题段需要"照母题/教辅再生"时**调「举一反三」skill**
   （单向调用，血缘全程入库）。
2. **自编题全量实算过闸**：qbank `verify()` 全绿（逐题机器实算/解集唯一/册内查重——
   🔴 只在本册内查，跨册撞题不拦/范围闸/题面纯净/难度对表）；
   交解析卷加跑 `python 工具箱/验算/逐行恒等校验.py`（答案对≠过程对）。
3. **DSL 留档**：新写的生成器文件放 `工具箱/dsl/` 或册 `_源/`（相对路径），
   `model_tool.py exam-add --dsl-ref <相对路径>` 挂到考点。
4. 全册双 PDF + 单天分册（调「渲染出件」）。
5. **回流入库**：qbank 吐题目包 JSON（blocks v2 + kp 名 + prov{model_id,params,seed} + confidence）→
   `ingest_flow.py check` 干跑 → `ingest_flow.py ingest`（草稿）→ 交付定稿后 `promote`。

## 4. 第四步 · 发布

1. 干净目录集结成品（🔴 别把 `_源/` 废版 PDF 传出去）→「网盘分发」skill 上传+建链
   （一册一条**文件夹分享**链接，双号共用；改版重传必 `--force` 并验 fs_id）。
2. **挂账**：「资料挂账」skill `artifact_tool.py add`（kind=打卡册，files 指 `产物/` 相对路径，
   kp 挂本册考点）→ `link` 回填网盘链接 → `note` 回填宣发字段（小红书标题/描述/标签）。
3. 物料三件套走「发布物料」skill（AB 隔离闸全绿才交）。
4. 🔴🔴 **发布动作永远用户手机 App 人工发**（自动化发布=封号红线）。

## 5. 已知坑（老区实锤，照抄省时）

- Chrome 出 PDF：`--headless=new --disable-gpu --no-proxy-server --no-pdf-header-footer
  --virtual-time-budget=20000 --run-all-compositor-stages-before-draw --user-data-dir=<临时profile>`；
  撞正开着的 Chrome 会静默不写文件，出完 sleep 再验文件存在。
- 🔴 `<`/`>` 进公式必转 `\lt `/`\gt `（`\(a<0\)` 的 `<b` 会被当 HTML 标签吞整段）。
- 🔴 中文不进 LaTeX（「或」「，」留在公式外拼）；系数 1 省略；非最简分数不上卷面。
- 数学排版一律 MathJax（本地 `工具箱/渲染/mathjax/`，手画 CSS 根号是反面教材）。
- 页数断言：题目卷页数=天数（答案卷允许多页）；题目卷不泄答案闸在 punchkit core。
- 一册之内题面零重复=硬闸；跨册撞题不拦不报警（2026-08-17 用户拍板）。
