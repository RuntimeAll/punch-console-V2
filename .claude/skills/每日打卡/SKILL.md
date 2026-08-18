---
name: 每日打卡
description: 制作/续造「每日打卡」类册子——N 天×每天 M 题×一天一页的连续练习册（题目卷+答案卷双 PDF，发网盘售卖）。当用户说"做一个N天打卡""每日打卡""打卡册""每日一练""连着练N天""再来一期打卡""续造下一期""改打卡版式/题量""出一本小册"时用。四步=母题定性→出题入库+组册初稿(🔴用户点头才铺全册)→全量铺开(DSL留档+实算全绿)→发布(网盘+artifact挂账带宣发字段，发布动作永远用户手机人工)。🔴 库中心：题先入库、组册从库取、渲染从库读、页面可看。🔴 v2 编排：两库只经 工具箱 脚本与闸写入，出题段调「举一反三」，组卷走 工具箱/组卷/paper_tool.py，渲染调「渲染出件」，上传调「网盘分发」，物料调「发布物料」，挂账调「资料挂账」。绝不调老区/备课帮任何服务。
---

# 每日打卡 —— 四步流水线（流程正本=认知/业务流程.md §二）

## 🔴🔴 飞轮铁律（写死，不是可选项——每次出题都要让知识库变厚一分）

1. **出题必回流**：**题先入库再组册**（不是出完册子补录）——每道题经 `工具箱/回流/ingest_flow.py`
   入 kb.question（草稿）：blocks v2 + 血缘（prov 记 model_id/params/seed，变式带 mother_qid/variant_op）
   + 考点叶子 + source_kind='model'（自编参数化）/'manual'（手写）。**过三闸才算出完**，拒收就修，不许绕。
2. **模型必留档**：母题定性产出的解题模型 `model_tool.py solution-add` 进 solution_model；
   每个考点的出题路径（DSL 生成器）`model_tool.py exam-add` 进 exam_model（dsl_ref 指向真文件）——
   保证**每个考点后续都能持续再出题**。
3. **出题前必查库**：`model_tool.py coverage --kp <考点>`（这考点已有几题几模型）→ 有模型走快线；
   🔴 **库存未用题优先**（组卷 `take.unused_only`），**不够才 DSL 新造**；相似前查由 ingest_flow 的
   match_key 闸兜底。
4. **册结构必进库**：册=artifact 壳，一天=一张 paper，题序=paper_item.ord，分值=paper_item.score——
   `工具箱/组卷/paper_tool.py` 是这两表的唯一写入通路。**渲染从库读**（render-pack/v1），
   出件之后册/天/题都能在展示台页面打开看到。
5. **每次执行落 skill_log**：工具自动落账；步骤级里程碑用
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

## 2. 第二步 · 出题入库 + 组册初稿（🚧 审核门）

**口径反转**：先有库里的题，才有册。册子不是"渲染出来的一堆 PDF"，是库里的
artifact→paper→paper_item 结构，PDF 只是它的一次出件。

1. **先查库**：逐考点 `model_tool.py coverage --kp <考点>` 对账，库存够就直接用（组卷 `take`
   自动只捞**未进过任何卷**的题）；不够的缺口才进第 2 步新造。
2. **不够才新造**：选模版别 fork——`cd .claude/skills/每日打卡/_模板 && python -m punchkit` 看骨架菜单；
   一本册 = 骨架(layouts, 学科无关) × 渲染器(renderers, 学科相关)；`LAYOUT='<key>'` 一行换装。
   🔴 绝不在册 `_源/` 里私长 CSS。新造题走 DSL：建 `产物/打卡/<册名>/_源/qbank.py`
   （DSL 单一事实源：题面/过程/答案同源一组参数，verify() 三断言=题面零重复/同天同节答案不撞/题量配比）。
3. **入库（草稿）**：qbank 吐题目包 JSON（blocks v2 + kp 名 + prov{model_id,params,seed} + confidence）→
   `ingest_flow.py check` 干跑 → `ingest_flow.py ingest`。
   🔴 **题面 md 只放算式/文字本体，不带「计算：」类指令词**（见 §5 坑清单最后一条）。
4. **组册**：写组卷 spec（样例=`工具箱/组卷/paper_tool.py` 文件头；一天一个 paper，
   `layout.sections` 与 `sections[].name` 必须同名对位）→
   `python 工具箱/组卷/paper_tool.py assemble --spec <组卷.json>`。
   第一次不给 `artifact.id`（工具建壳并回吐 id），之后重排都带上它。
   组卷闸会拒：退役题/裸题、同册重复题、take 取不足（**如实报差额，绝不静默凑**）、节名对不上 layout。
5. **渲样张（从库读）**：
   `paper_tool.py render-pack --artifact <id> --paper-ord 1 --out 产物/打卡/<册名>/_源/render-pack-d1.json`
   → `python 工具箱/渲染/render_paper.py <那个 json> --out-dir 产物/打卡/<册名> --stem <册名>`
   （管道与坑单走「渲染出件」skill）→ PDF 转 PNG 逐页目检 → 连 `大纲.md`（考点覆盖表）交用户。
6. 🔴🔴 **门禁：用户点头（含排版过审）才进第三步**——这是流程固有闸，不算"停下等人"违例。

## 3. 第三步 · 全量铺开 20/30 天（逐天同口径，DSL 出题路径必留档）

1. 钉死定稿版式，**逐天重复第二步的 1→4**：库存优先取（`take.unused_only=true`）→ 缺口 DSL 新造 →
   `ingest_flow.py ingest` 入草稿 → spec 追加 dayN 的 paper → `paper_tool.py assemble` 一次铺完。
   🔴 assemble **幂等**：同 artifact+ord 的卷重跑=清掉该卷旧题重排（组卷是编排动作），整册重排放心跑。
   出题段需要"照母题/教辅再生"时**调「举一反三」skill**（单向调用，血缘全程入库）。
2. **自编题全量实算过闸**：qbank `verify()` 全绿（逐题机器实算/解集唯一/册内查重——
   🔴 只在本册内查，跨册撞题不拦/范围闸/题面纯净/难度对表）；
   交解析卷加跑 `python 工具箱/验算/逐行恒等校验.py`（答案对≠过程对）。
3. **DSL 留档**：新写的生成器文件放 `工具箱/dsl/` 或册 `_源/`（相对路径），
   `model_tool.py exam-add --dsl-ref <相对路径>` 挂到考点。
4. **对账**：`paper_tool.py list --artifact <id>`（卷数=天数、每卷题数=每天题量）+
   `paper_tool.py show --paper <卷id>` 抽查题序与节归属。对不上就改 spec 重跑 assemble，别手改库。

## 4. 第四步 · 发布

1. **定稿+上架**：`paper_tool.py finalize --artifact <id>`——全册 paper 置定稿 +
   册内草稿题全部 promote 上架（一个事务），artifact.kp_ids_json 覆盖考点自动回填（空时才填）。
2. **出全册双 PDF（从库读）**：`render-pack`（不带 `--paper-ord`=整册）→ `render_paper.py` 出题目卷+
   答案卷；封面目录三件套走「渲染出件」skill。🔴 页数断言：题目卷页数=天数。
3. 干净目录集结成品（🔴 别把 `_源/` 废版 PDF 传出去）→「网盘分发」skill 上传+建链
   （一册一条**文件夹分享**链接，双号共用；改版重传必 `--force` 并验 fs_id）。
4. **挂账**：「资料挂账」skill 把组卷时建的壳补全——
   `artifact_tool.py files --id <id> --file 产物/…/题目卷.pdf --file 产物/…/答案卷.pdf` →
   `link` 回填网盘链接 → `note` 回填宣发字段（小红书标题/描述/标签）→ `status --to 已交付`。
5. 物料三件套走「发布物料」skill（AB 隔离闸全绿才交）。
6. 🔴🔴 **发布动作永远用户手机 App 人工发**（自动化发布=封号红线）。
7. 交付后自证：`paper_tool.py list --artifact <id>` 卷全定稿、题全上架，页面能打开看到册/天/题。

## 5. 已知坑（老区实锤，照抄省时）

- Chrome 出 PDF：`--headless=new --disable-gpu --no-proxy-server --no-pdf-header-footer
  --virtual-time-budget=20000 --run-all-compositor-stages-before-draw --user-data-dir=<临时profile>`；
  撞正开着的 Chrome 会静默不写文件，出完 sleep 再验文件存在。
- 🔴 `<`/`>` 进公式必转 `\lt `/`\gt `（`\(a<0\)` 的 `<b` 会被当 HTML 标签吞整段）。
- 🔴 中文不进 LaTeX（「或」「，」留在公式外拼）；系数 1 省略；非最简分数不上卷面。
- 数学排版一律 MathJax（本地 `工具箱/渲染/mathjax/`，手画 CSS 根号是反面教材）。
- 页数断言：题目卷页数=天数（答案卷允许多页）；题目卷不泄答案闸在 punchkit core。
- 一册之内题面零重复=硬闸；跨册撞题不拦不报警（2026-08-17 用户拍板）。
- 🔴 **题面 md 不带「计算：」类指令词**（2026-08-18 库中心口径新增判据）：入库的 blocks 只放
  **算式/文字本体**，"计算"、"求下列各式的值"、"解方程"这类**指令词是载体/渲染层的事**——
  它随版式走（节标题、槽位提示语都在 `paper.layout_json` 里），跟着题面进库就等于把版式焊死在题上，
  同一道题换个册子/换个节就再也复用不了。库存复用率是打卡册的命根子，这条闸别绕。
- 🔴 题号/分值同理不进题面（question 表根本没有 qno/score 两列，落 paper_item.ord/score）——
  这条由块流校验器的前缀闸自动拦。
