# 题目结构考古 · DB 层（老区备课帮 `ai_lesson_prep`）

> 承接 [需求总纲.md](需求总纲.md) §十二「题目结构与备课帮**后期互通**」。
> 本文 = **老区题目相关库表的全字段实测底稿**，供 [数据结构.md](数据结构.md) §2.1 定终稿 + 写互通契约。
> 姊妹篇 = `题目结构考古-契约层.md`（MCP/HTTP 出入参口径，另出）。

## 〇、考古方法与证据边界

| 项 | 事实 |
|---|---|
| 证据源 | **真库直读**（非静态文件推断）：Docker MySQL `127.0.0.1:3307` / 库 `ai_lesson_prep` / `root` |
| 通路 | python + pymysql 纯通路（`sys.stdout.reconfigure('utf-8')`），🔴 未用 mysqldump 经 PS 重定向 |
| 只读保证 | 全程仅 `SELECT` + `information_schema` + `SHOW INDEX`；零 DDL、零写入 |
| 快照时间 | 2026-08-17 |
| 代码侧交叉验证 | 同步做了一遍 book-server / book-ui / teacher-mcp 只读代码考古（`BlockJsonValidator` / `BlockJsonConverter` / `FormatController` / `QuestionBlockRender` / `blockSchema.ts` / `ShelfService` / `PunchService` / `store/dict.ts`），结论内联在 §1.2 / §2 / §2.6 / §3.5 / §4.5，逐条带 `路径:行号` |
| 代码路径口径 | 五份 book-server（`codeplace-O/C/A/B` + `_build-wt`）的关键 Java 文件 **md5 完全相同**，故统一引 `codeplace-O` |
| 库规模 | 全库 **105 表**；其中题目相关 **41 表**（余下=若依 `sys_*` / snail-job `sj_*` / 教务排课课时） |
| ⚠️ 覆盖不到的 | **打卡（punch）表在本地 dev 库不存在**——全库 105 表无任何 `punch*` / `sku*` / `grading*` 表（已 `information_schema` 全实例扫描：14 个库里都没有）。打卡数据结构=**借用书架三表**（见 §3.5，已由 DB 证实）；prod-only 表若存在则本文**未核实** |
| ⚠️ dev ≠ prod | 本文所有行数/分布来自 **dev 库**。prod 打卡书已清零重录（记忆：`daily-punch-first-ingest`），量级不同，**结构一致性未逐表核对** |

---

## §0 一句话结论

**老区题目模型的骨架 = 一张宽主表（`biz_question`，61 列）+ 三份并存的正文载体（`stem_text` 纯文本 / `biz_question_block.block_json` 结构化块 / `biz_text_content` 长文本外置）+ 一圈 M:N 卫星表（考点/图/题型/模型/易错/自由标签）+ 三套互不相通的载体（书架 `biz_shelf_*` / 试卷 `biz_paper_*` / 教辅 `biz_book_*`）。**

三句话展开：

1. **真正有价值、v2 应该继承的三样**：
   - 🥇 **`block_json` 块流规范**（`{v,rows:[{cells:[…]}]}`，只有 `text`/`image`/`option` 三型，text 里是 **Markdown + 内联 `$LaTeX$`**）——12236 份真实数据 + **一份真校验器（`BlockJsonValidator`）+ 三处锁定契约**验证过，**是老区最成熟的一件资产**，v2 的 `blocks_json` 与它同宗但**丢了 `option` 块型**（§2.4 缺口①）。
   - 🥈 **打标三件套的落库形状**：`biz_question_knowledge`（题↔考点 M:N + `is_primary` + `source`）、`biz_free_tag`+`biz_question_free_tag`（自由标签字典化 + `position` 位置码）、`source_raw`（原始来源前缀全文可回滚）。这三个设计 v2 已基本平移，**方向是对的**。
   - 🥉 **两张被低估的知识库表**：`biz_solution_model` 43 条（`trigger_feature`→`action_conclusion` 招式二元组 + `difficulty_tier`/`freq_band` 双旋钮）和 `biz_question_pattern` 326 条（题型目录锚在考点上，`biz_question_pattern_rel` 挂 868 题）。**v2 的 `exam_model` 只覆盖了前者，`题型目录` 在 v2 完全没有对位表**（§5.3 缺口）。

2. **历史包袱的三种典型形态**（§6 完整清单，共 **31 个死列 / 12 个单值列**）：
   - **加了列没人写**：`stem_embedding`/`embedding_model`/`embedding_updated_at`（向量三件套 0/15674）、`aux_tags`、`reviewed_by`/`reviewed_at`、`file_bin_url`。
   - **兼容垫片没拆**：`difficult` 与 `dim4_difficulty` 双列并存且**已漂移 33 行**；`question_type` 与 `dim2_qtype` 双列并存且**漂移 630 行**；`dim3_skill`/`dim5_structure` 注释自己写着「已撤维恒空」。
   - **注释与数据打架（最危险）**：`dim1_kp_id` 注释写「主考点(biz_subject **叶子**)」，实测 **7620/12091 指向 level=2（章）**，且被引用的 322 个考点里 **108 个有子节点根本不是叶子**；`subject_id` 注释写「科目锚 level1」，实测 **2592 行不是 level1**；`mother_question_id` 注释写「SSOT 在 trace」，而 `biz_variation_trace` **只有 6 行**、`mother_question_id` 有 **5260 行**——**声明的事实源是空的**。
   - **同一份东西存多份拷贝然后漂移**（本次代码考古新确认）：同一个题型词表有 **4 份拷贝**（`sys_dict_data` SSOT + BE enum 镜像 + FE store 常量 + MCP 硬编码），且**已经漂移**（DDL 列注释把「填空/判断」的码写反了，FE 里还留着修这个错的注释）；同一份 block 渲染逻辑有 **3 份实现**（FE 组件 + book-v1 主题 JS + punch-v1 主题 JS）；图片缺省宽度有 **4 个不同的值**（45/40/40/100）；`styleMeta` 这个 JSON 列在**六层里有两个名字**，传错的那个是**静默丢弃**（§2.6）。

3. **对 v2 的总判断**：**不要合库、不要迁表，只做「一道题的交换格式」**。理由——老区一道完整的题散落在 **9 张表 + 1 个 OSS 桶**，且 46% 的题（7226/15674）**根本没有答案**；直接吃老区的库等于把 31 个死列和三处注释谎言一起继承。互通的正确形态是 §5 的**最小交换集（13 字段）**，双向都能无损往返，其余字段单边保留。

---

## §1 逐表全字段表

> 「在用?」列的统计口径：`非空且非空串非 `[]`/`{}`/`null`` 的行数 / 全表行数（百分比）+ 去重基数。
> **死列**=0 行有值；**单值列**=有值但去重基数=1（无信息量）；**近死列**=<3%。
> 「v2」列：**要** / **不要** / **改造**。

### 1.1 `biz_question` — 题目主表（**15674 行**，61 列）

| 字段 | 类型 | 注释 | 在用? | v2 | 理由 |
|---|---|---|---|---|---|
| `id` | bigint PK auto_inc | — | 15674 (100%) 全部为雪花号（min `2069819158257750018`，**无一个自增小 id**） | **改造** | 声明 auto_increment 但实际全由应用发雪花号——**列定义与实际写入方式不一致**。v2 已定 `id TEXT` 防截尾，正确 |
| `question_type` | tinyint NOT NULL | 1选择 2填空 3判断 4计算 5解答 | 100%，9 个取值 | **要** | 权威题型列。但与 `dim2_qtype` 打架（见下） |
| `is_anchor` | tinyint(1) | 压轴题标记 | 100%，88 行=1 | 改造 | 语义 = difficulty=4 的另一种说法，v2 用 `difficulty` 一列表达即可 |
| `subject_id` | varchar(20) NOT NULL | 科目锚 **level1** | 100%，231 个取值 | **改造** | 🔴 **注释谎言**：13082 行指 level1，但 level3=1444 / level4=739 / level5=312 / level2=97，**2592 行不是教材根**。v2 靠 `question_kp` 挂树即可，不要这根冗余锚 |
| `dim1_kp_id` | varchar(20) | ①主考点(biz_subject **叶子**) | 12091 (77.1%)，297 取值 | **不要** | 🔴 **双重问题**：①与 `biz_question_knowledge(is_primary=1)` 冗余（34 行已漂移不一致）；②注释说叶子，实测 level2=7620 是大头。v2 用 `question_kp.is_primary` 单一事实源，**正确** |
| `stem_text` | mediumtext + FULLTEXT | 题干纯文本(全文检索用) | 15595 (99.5%) | **改造** | 三份正文载体之一。v2 无此列——建议保留为 **`blocks_json` 的派生检索列**（v2 若要全文搜必须有），但**不许当事实源** |
| `stem_hash` | char(32) | 题面归一化MD5(去重) | 14682 (93.7%)，去重 14655 | **要** | = v2 `match_key`。实测重复 hash **23 组 / 50 行**，说明闸有效但没堵死 |
| `stem_text_content_id` | bigint | — | **10 (0.1%) 近死列** | **不要** | 题干外置指针基本没启用（`biz_text_content` 里 content_type='S' 只 33 行） |
| `answer_text_content_id` | bigint | — | 8445 (53.9%) | 改造 | 答案外置指针。v2 用 `answer_blocks_json` 内联，不需要指针 |
| `analyze_text_content_id` | bigint | — | 5522 (35.2%) | 改造 | 同上 |
| `version` | int | 题目格式版本码 | 100% **单值 1010** | **不要** | 从没 bump 过 |
| `exam_year` | varchar(10) | 年份 | 895 (5.7%)，4 取值 | 改造 | 并入 v2 `prov_json` |
| `region_code` | varchar(12) | 地区码 → `biz_region.code` | 846 (5.4%)，150 取值 | 改造 | ⚠️ **`biz_region` 表在库里不存在**（105 表无此表）——软引用悬空。并入 `prov_json` |
| `source_type` | tinyint | 1中考2模拟3期末4月考5单元6自编7期中9其他 | 11926 (76.1%)，8 取值 | **不要** | 🔴 **语义已污染**：`source_type=3`（字典=**期末**）有 **9603 行**，其中 7427 行 `import_source=lecture-pipeline`、`source_raw` 全是《同步典例考点讲义》——**是管线硬编码默认值，不是真来源**。v2 用 `source_kind`（scan/manual/model/pipeline）+ `prov_json`，**设计更干净** |
| `source_raw` | varchar(255) | 原始来源前缀全文(可回滚) | 11913 (76.0%)，3391 取值 | **要** ⭐ | **老区最实用的溯源字段**。真实值形如 `三上数学同步典例考点讲义（人教版） / 第四单元 多位数乘一位数·计算篇 / 【考点】课后小测`——书/章/栏目三段用 ` / ` 分隔。v2 `prov_json` 应把它**原样收进一个 `source_raw` 字符串键**，不要解析后丢原文 |
| `mother_question_id` | bigint | 母题指针(派生缓存,**SSOT在trace**) | 5260 (33.6%)，1897 个母题 | **要** | 🔴 **注释谎言**：声明的 SSOT `biz_variation_trace` **只有 6 行**。实际血缘 100% 靠这一列。0 行悬空、0 行自引用（数据本身干净）。一个母题带 3 个变式最常见（1445 组） |
| `variant_relation` | varchar(16) | 数值变式/情境变式/结构变式/同源 | 5260 (33.6%)，**25 取值** | **不要** | 🔴 **注释与数据完全不符**：实际值是 `对应练习1`(1705) / `对应练习2`(1702) / `对应练习3`(1459) / `变式训练N` / `精练题NN`——**这是教辅书里的栏目标签，不是变式算子**。真正的算子词表应在 `biz_variation_trace.method`（而那表是空的）。v2 用 `prov_json.{model_id,params}` 表达生成血缘，方向对 |
| `annotate_version` | int NOT NULL | 标注 schema 版本 | 100% **单值 0** | **不要** | 从没 bump |
| `annotate_status` | tinyint NOT NULL | 0未标 1已标全 2部分 | 100%，2 取值（0=14140 / 1=1534） | 改造 | 与 `label_status` 高度重叠，v2 一个 `status` 够 |
| `mother_source` | varchar(16) | textbook书原生(金标)/ai反推 | 7167 (45.7%)，2 取值（`教材配套`7161 / `同书母题`6） | 改造 | ⚠️ 实际值是中文 `教材配套`/`同书母题`，与注释写的 `textbook`/`ai` 不同。并入 `prov_json` |
| `stem_embedding` | blob | 题干向量预留,本期空 | **0 死列** | **不要** | |
| `embedding_model` | varchar(64) | — | **0 死列** | **不要** | |
| `embedding_updated_at` | datetime | — | **0 死列** | **不要** | 🔴 向量三件套整组从未启用 |
| `label_status` | tinyint | 0未标 1AI已标 2已审 3存疑 | 100%，3 取值（0=14140 / 1=1483 / **2=51**） | 改造 | **只有 51 道题被人审过**（0.3%）。v2 `status` 四态（草稿/已审/上架/退役）语义更清 |
| `label_confidence` | decimal(4,3) | AI 自评置信度 | 915 (5.8%) | 不要 | AI 自评置信度实践中没用起来 |
| `labeled_by` | varchar(64) | AI 模型名或人员 | 1534 (9.8%)，4 取值：`full-run`837 / `mcp-ingest-items`361 / `5`285 / `claude-prep-20260709`51 | 改造 | ⚠️ 值 `5` 是**用户 id 串进了模型名列**（脏）。v2 若要留，收进审计表而非主表 |
| `labeled_at` | datetime | — | 1534 (9.8%) | 改造 | |
| `reviewed_by` | varchar(64) | — | **0 死列** | **不要** | 审核留痕列建了没用（人审只体现在 `label_status=2` 的 51 行上） |
| `reviewed_at` | datetime | — | **0 死列** | **不要** | |
| `aux_tags` | json | 辅标签:错因/情境/考查角度/母题 | **0 死列** | **不要** | 被 `biz_free_tag` 关联表取代 |
| `import_source` | varchar(32) | main主书/kuangk狂K/textin | 100%，**14 取值** | **要** | 真实取值：`lecture-pipeline`7427 / `main`5700 / `lecture-readyA`635 / `mcp-ingest`522 / `textbook-imagebook`485 / `lecture-1x`386 / `lecture-1s`279 / `kbA`77 / `mcp-prep`49 / `shjb-full`46 / `shelf-book6-2.2`30 / `崔崔讲义`25 / `mcp-all`11 / `punch-sanshengsi-selfmade`2。**与注释完全不同**（注释三个值一个都没出现）——但值本身有用：这是「哪条管线灌的」。≈ v2 `source_kind`，但老区粒度更细 |
| `import_batch_id` | varchar(64) | — | 12456 (79.5%)，176 批 | **要** | 批次可回滚，形如 `mcp-20260730-162044-4cmm`。v2 `ingest_batch.id` 对位 |
| `status` | char(1) | 0草稿 1发布 2软删 | 100% **单值 1** | **不要** | 🔴 **软删机制形同虚设**——15674 行全是「发布」，一个草稿一个软删都没有。删题走真 DELETE（证据：`biz_question_block` 有 **26 行孤儿**，主题已被物理删除） |
| `create_by` / `create_user` | varchar(64) / bigint | 若依用户名 / sys_user.id | 99.8%，各 6/5 取值 | 改造 | v2 单人使用，一个 `created_at` 够 |
| `remark` | varchar(500) | — | **0 死列** | **不要** | |
| `base_score` | decimal(5,2) | 题自身标准分值 | 992 (6.3%) | 不要 | 分值实际由 `biz_paper_question.score` 承担（100% 有值） |
| `is_collected` | tinyint(1) | 0=misikt老题 1=自有化新题 | 100% **单值 1** | **不要** | 老题清理已完成，标记失去意义 |
| `create_time` / `update_time` | datetime | — | 100% | **要** | |
| `update_by` | varchar(64) | — | 99.8% | 不要 | |
| `is_public` | tinyint(1) NOT NULL | 公共题库审核闸 | 100%（1=14024 / 0=1650） | **要** ⭐ | 🔴 **真正在用的上架闸就是这一列**（不是 `status`）。v2 `status='上架'` 对位。记忆里「ingest 只入草稿、必须 set-public 才前端可见」说的就是它 |
| `stem_img_url` | varchar(500) | 题干渲染图(可选缓存) | **159 (1.0%) 近死列** | 不要 | |
| `answer_img_url` | varchar(500) | — | **0 死列** | **不要** | |
| `explain_img_url` | varchar(500) | — | **0 死列** | **不要** | |
| `file_bin_url` | varchar(500) | 原站 data.bin(笔迹层,不实现) | **0 死列** | **不要** | 注释自己写「不实现」 |
| `dim2_qtype` | tinyint | ②题型 1选择/4填空/5解答/6证明 | 15649 (99.8%)，9 取值 | **不要** | 🔴 **与 `question_type` 重复且已漂移 630 行**（`question_type=2`(填空) 115 行 vs `dim2_qtype=2` 708 行）。v2 一列 `qtype` |
| `dim3_skill` | varchar(500) | [兼容垫片]已撤维恒空 | **0 死列** | **不要** | 注释自己判了死刑，列还在 |
| `dim4_difficulty` | tinyint | ④难度 1-4 | 100%，**5 取值**（**0=867** / 1=1194 / 2=12916 / 3=638 / 4=59） | **改造** | 🔴 两个问题：①字典 `biz_question_difficulty` 只定义 1-4，**867 行是 0（越界）**；②**82% 全挤在「2 中等」**——难度维度实质未分化。v2 `difficulty 1-5` 要配**判档 rubric**才有意义，否则会重蹈 |
| `difficult` | int | [兼容垫片]旧难度列 | 100%，5 取值 | **不要** | 🔴 与 `dim4_difficulty` **已漂移 33 行**——典型「垫片列不同步」事故 |
| `discipline` | varchar(20) | 分科(科学专属) | **0 死列** | 改造 | 科学分科维度设计了但一条没写（尽管库里有 1150 道科学题）。v2 若做科学线要重新设计 |
| `dim5_structure` | varchar(500) | [冻结]结构指纹 | **0 死列** | **不要** | |
| `exam_paper_id` / `exam_paper_name` | bigint / varchar(200) | 出处试卷 冗余 | **0 死列** ×2 | **不要** | |
| `source_ref` | varchar(200) | PRD-C-213 素材源 | **0 死列** | **不要** | |
| `star_level` | char(1) | PRD-C-213 星级 | **8 (0.1%) 近死列** | **不要** | |
| `topic_tag` | varchar(50) | PRD-C-213 专项名 | **0 死列** | **不要** | 🔴 PRD-C-213 三件套（`source_ref`/`star_level`/`topic_tag`）**整组基本没落地** |

**索引**：`PK(id)` / `idx_subject(subject_id)` / `idx_kp(dim1_kp_id)` / `idx_type_diff(question_type)` / `idx_mother(mother_question_id)` / `idx_stem_hash(stem_hash)` / `idx_source_type` / `idx_label_status` / **`FULLTEXT ft_stem(stem_text)`**。
🔴 注意 `idx_type_diff` 名字暗示是 (type,difficulty) 复合索引，**实际只有 `question_type` 一列**。

**🔴 主表最重要的一条结论：这 61 列里真正每行都有意义的只有 ~18 列**，其余是死列(17)、单值列(4)、垫片重复列(4)、注释谎言列(3)、低覆盖遗留列(~15)。

### 1.2 正文三载体

#### `biz_question_block` — 结构化块（**12236 行**，8 列）★核心资产

| 字段 | 类型 | 注释 | 在用? | v2 | 理由 |
|---|---|---|---|---|---|
| `question_id` | bigint **PK** | 一题一份 block 文档,作 PK | 12236 (100%) | **要** | **一题一份文档、question_id 直接当主键**——这个设计干净，v2 直接把三个 blocks 列放在 `question` 表里等价 |
| `block_json` | **json** | block 文档(§10.1 schema: `{v,rows:[{cells:[block]}]}`) | 12236 (100%)，去重 11751 | **要** ⭐ | 见 §2 全文剖析 |
| `v` | int | schema 版本号(当前 1) | 100% **单值 1** | 改造 | 从没 bump，但**版本位本身该留**（v2 块流应留 schema 版本，否则改结构没退路） |
| `update_by` | bigint | 最后保存者(服务端 LoginHelper 强制) | 12185 (99.6%)，5 取值 | 不要 | |
| `create_time` / `update_time` | datetime | — | 99.6% | 要 | |
| `answer_block_json` | **mediumtext** | C-204:答案 blockJson(走 convertRichText 统一渲染) | **891 (7.3%)** | **要** | 🔴 见下「三列区别对待」 |
| `analyze_block_json` | **mediumtext** | C-204:解析 blockJson | **891 (7.3%)** | **要** | 同上。891/891 与 answer 完全同步（同一批写入） |

**🔴 三列的区别对待（代码级实证，解释了为什么类型不一致、为什么只有 7.3%）**

| 维度 | `block_json` | `answer_block_json` / `analyze_block_json` |
|---|---|---|
| DB 类型 | `json` | `mediumtext` |
| 建列通道 | Flyway 迁移 `codeplace-O/book-server/ruoyi-admin/src/main/resources/db/_archived_2026-06-20/V23__create_biz_question_block.sql:22` | 🔴 **临时 Python 脚本 ALTER**：`.claude/skills/必刷题整书录入/scripts/c204_schema_patch.py:130-133` → **类型不一致的直接原因＝不是同一条通道加的列** |
| Java 写入点 | `QuestionServiceImpl.java:962-967 / 1093-1106 / 1140-1185`、`IngestServiceImpl.java:526-530` | 🔴 **零 Java 写入点**（`setAnswerBlockJson` 全仓只出现在**读**的 VO 回填上） |
| 实际唯一写入者 | BE 事务 | 🔴 离线脚本 `c204_format_analysis.py:59` 直连 MySQL `UPDATE`，源数据取 `biz_text_content` 的 A/E |
| 落库前校验 | 必过 `BlockJsonValidator.validate()`（4 处调用） | 🔴 **无任何校验**（脚本绕过 BE） |

**⇒ 结论：`block_json` 是「BE 受管资产」（Flyway + validator + 事务写入口）；`answer/analyze_block_json` 是「C-204 补丁资产」（脚本建列、脚本回填、只读消费）。** 类型差异是历史通道差异，不是语义设计。
**⇒ v2 的对应纪律**：三列同构块流收在一张表**很对**，但**三列必须共用同一个校验器和同一条写入通道**——老区正是因为「补丁列走旁路」才只回填了 7.3% 且无校验。

**数据卫生**：**26 行孤儿**（`question_id` 指向已被物理删除的题）——`biz_question` 无软删导致。
**主键**：`@TableId(type=IdType.INPUT)`（`BizQuestionBlock.java:43-44`）——不走雪花不走自增，调用方显式 set，与「一题一份」语义一致。
**多租户**：本表无 `tenant_id`，必须列入 `application.yml` 的 `tenant.excludes`（`V23__create_biz_question_block.sql:13-15`）。

#### `biz_text_content` — 长文本外置（**14025 行**，6 列）

| 字段 | 类型 | 注释 | 在用? | v2 | 理由 |
|---|---|---|---|---|---|
| `id` | bigint PK | — | 100% | — | |
| `question_id` | bigint NOT NULL | 反查 biz_question.id | 100%，8464 个题 | 改造 | |
| `content_type` | char(1) NOT NULL | S=题干 / A=答案 / E=解析 | 100%，3 取值：**A=8450 / E=5542 / S=33** | 改造 | 🔴 **S（题干）实质废弃**——题干在 `stem_text`+`block_json`，这张表事实上只承担答案与解析 |
| `content` | mediumtext | 长文本内容(LaTeX 源/纯文本) | 100% | **要** | **答案/解析的真事实源**（8450 vs block 层的 891） |
| `create_time`/`update_time` | datetime | — | 100% | | |

**唯一键** `uk_question_type(question_id, content_type)` — 一题每型至多一份，设计正确。
**数据卫生**：**8 行 `content` 里有裸 `<img src=...>` HTML**（图片混进文本层，见 §2.5 坑④）。
🔴 **表注释本身是 GBK 乱码**：`棰樼洰涓夎?绱犻暱鏂囨湰澶栫疆` —— 见 §6.3。

#### 三载体覆盖实测（分母 15674）

| 载体 | 行数 | 说明 |
|---|---|---|
| `stem_text` 非空 | **15595 (99.5%)** | 唯一近乎全覆盖的题面载体 |
| 有 `block_json` | **12210 (77.9%)** | **3462 题只有纯文本没有块**（老题/未回填） |
| 只有 block 没有 stem_text | 77 | |
| 有答案（`text_content.A`） | **8448 (53.9%)** | |
| 有解析（`text_content.E`） | **5542 (35.4%)** | |
| 有 `answer_block_json` | 891 (5.7%) | |
| 🔴 **一点答案都没有** | **7226 (46.1%)** | 近一半题是「光题面」 |

### 1.3 打标与 DNA 卫星表

#### `biz_question_knowledge` — 题↔考点 M:N（**12265 行**）★

| 字段 | 类型 | 注释 | 在用? | v2 | 理由 |
|---|---|---|---|---|---|
| `id` | bigint PK | — | 100% | 不要 | v2 用复合 PK 更省 |
| `question_id` | bigint | — | 100%，12065 题 | **要** | |
| `knowledge_id` | varchar(20) | 关联 biz_subject.id（**叶子**） | 100%，**322 取值** | **要** | 🔴 **注释谎言**：322 个被用考点里 **108 个有子节点**（非叶子）；level 分布 **level2=7595 / level1=1700 / level3=1463 / level4=1089 / level5=418**——**主力挂在「章」级，不是考点级**。v2 若要「按考点/专项分轨」（v2 头号设计目标），**必须在闸上强制挂叶子**，否则学情分母算不准 |
| `source` | varchar(8) | U=用户/S=标准库/AI=AI锚定 | 100%，**2 取值**（`U`=12240 / `书`=25） | 改造 | ⚠️ 实际值 `U` 和中文 `书`，注释里的 `S`/`AI` 一个没出现 |
| `is_primary` | tinyint(1) NOT NULL | 1主/0副 | 100%（1=12068 / 0=197） | **要** ⭐ | v2 `question_kp.is_primary` 同构。**但老区没强制「主考点恰一」**——v2 已写「闸保证」，是正确的改进 |
| `create_time` | datetime | — | 99.8% | | |

**唯一键** `uk_qk_src(question_id, knowledge_id, source)` — 🔴 **把 `source` 放进唯一键是设计缺陷**：同一题同一考点被人和 AI 各挂一次会产生两行。
**基数实测**：一题挂 1 个考点=11919 / 2 个=92 / 3 个=54 → **99% 单考点**，M:N 能力基本没用上。
**一致性**：`dim1_kp_id` 与 `is_primary=1` 行 **漂移 34 行**。
**孤儿**：0（`knowledge_id` 全部能在 `biz_subject` 找到）✅

#### `biz_free_tag`（143 行）+ `biz_question_free_tag`（327 行）— 自由标签

| 表.字段 | 类型 | 在用? | v2 | 理由 |
|---|---|---|---|---|
| `biz_free_tag.name` | varchar(255) UNIQUE | 143，全唯一 | **要** | 真实 top 值：`模型:大招8 距离问题`146 / `模型:大招9 相遇问题`146 / `模型:大招10 追及问题`146 / `分类讨论`51 / `数形结合`29 / `新考向`20 / `韦达定理`15 / `易错`14。🔴 **词表已被污染**：`模型:xxx` 前缀说明有人拿自由标签当解题模型用（那是 `biz_solution_model` 的活） |
| `biz_free_tag.use_count` | int NOT NULL | 143 | **不要** | 🔴 **反规范化计数已漂移：143 个标签里 74 个 `use_count` 与实际关联数不一致**（51.7% 错）。v2 用 `COUNT(*)` 现算 |
| `biz_question_free_tag.position` | tinyint NOT NULL | 327，5 取值（0=206/1=95/2=20/3=5/4=1） | 改造 | 注释「出现位置 0/1/2/3/4 — **决定 FE 颜色**」——**表现层信息进了数据层**。v2 `tags_json` 不该带颜色位 |
| 覆盖 | — | 只 **206/15674 题（1.3%）** 有自由标签 | | 好设计但基本没用起来 |

#### `biz_question_ai` — AI 派生 DNA（**1799 行 / 覆盖 11.5%**，26 列）

| 字段 | 类型 | 注释 | 在用? | v2 | 理由 |
|---|---|---|---|---|---|
| `question_id` | bigint | — | 100%，1799 题 | 要 | `uk_q_ver(question_id, annotate_version)` |
| `annotate_version` | int | — | 100% **单值 1** | 不要 | |
| `solution_skeleton` | mediumtext | 解法骨架(步骤序列,【】标最难步)=**变式生成基因** | **191 (10.6%)** | **要** ⭐ | 设计非常好，落地极少。真实样例：`【赋值 AB=6x 整体处理】→ C/D 为中点得 CE=m=x、DE=n=5/2·x → 逐式代入，仅 5m−2n=0 与 AB 无关`。**`【】` 标最难步**是个聪明的低成本记法，v2 值得抄 |
| `assessment_type` | varchar(128) | 考察类型 | 74 (4.1%)，12 取值 | 改造 | 有字典 `biz_question_assessment_type`（10 值：概念辨析/直接计算/公式套用/性质判定/应用建模/探究归纳/证明推理/作图/纠错/阅读理解迁移）——**词表本身有价值，v2 可直接抄这 10 个值** |
| `hard_point_count` | tinyint | 难点个数(0=基础题) | 698 (38.8%)，4 取值 | 不要 | 由 `hard_points` 数组长度可算 |
| `breakthrough_points` | json | 突破点/难点(半开放) | 646 (35.9%)，去重 150 | 改造 | 样例 `["赋值特值/整体代换破解不变量"]` |
| `scenario` | varchar(128) | 场景=**变式表皮基因** | 605 (33.6%)，81 取值 | 改造 | 有字典 `biz_anno_SCENE`（纯数学/现实生活/数学文化/科学跨学科）|
| `math_thoughts` | json | 数学思想(⊂小闭集) | **0 死列** | 不要 | 有字典 `biz_anno_METHOD`（8 值：数形结合/分类讨论/化归转化/方程函数/数学建模/待定系数/特殊与一般/数学归纳）但**一条没写**——字典建了、列建了、没人填 |
| `tags` | json | 检索标签 3-6 | 552 (30.7%) | 改造 | 与 `biz_free_tag` 功能重复（**两套标签系统并存**） |
| `difficulty_reason` | varchar(500) | 难度综合判级依据 | 1175 (65.3%) | **要** | 覆盖率最高的一列。可审计的判档理由，v2 想做 rubric 就需要它 |
| `anchor_id` | varchar(20) | 锚定 subject 节点 | 614 (34.1%) | 不要 | 与 `question_kp` 重复 |
| `confidence` | decimal(4,3) | 锚定置信 | **48 (2.7%) 近死列** | 不要 | |
| `need_anchor_review` | tinyint(1) | 锚定存疑待人审 | 100%，2 取值 | 改造 | ≈ v2 `review_ticket(kind='kp低置信')`，v2 用工单表更好 |
| `reasoning` | text | agent 抽取依据 | **0 死列** | 不要 | |
| `label_status` | tinyint | 1AI已标 2已审 3存疑 | 100% **单值 1** | 不要 | **1799 条 AI 标注一条都没被人审过** |
| `labeled_by` | varchar(64) | — | 1798，4 取值（`sync-light`1102 / `mcp-ingest-items`361 / `5`284 / `manual-edit`51） | 改造 | 同主表：值 `5` 是脏数据 |
| `parametric_slots` | json | C:参数槽位[{量名,当前值,类型,约束}] | **9 (0.5%) 近死列** | **要** ⭐ | 设计=出题 DSL 的雏形。样例 `[{"量名":"AB","当前值":"6x(赋值)","类型":"长度","约束":"正"}]`。**≈ v2 `exam_model.params_json`，但老区是挂在「题」上而非「模型」上——v2 挂模型是对的** |
| `modeling_frame` | json | C:建模骨架 | **0 死列** | 不要 | |
| `conditions` | json | C:条件与小问 | **0 死列** | 不要 | |
| `variation_profile` | json | D:变式路由,每算子{可用,原料指针,依据,风险,自动盘} | **41 (2.3%) 近死列** | 改造 | 样例 `{"数值":{"可用":true,"风险":"low"},"结构":{...},"推广":{...},"升维":{"可用":true,"风险":"high"}}`。**「算子×可用×风险」三元组的想法好**，但 41/15674 说明没跑起来 |
| `hard_points` | json | B:难点[] | 161 (8.9%) | 改造 | 样例 `["思路缺失","计算失误"]`——取值来自字典 `biz_anno_ERROR`（7 值）。**≈ v2 `error_cause`** |
| `verify_kind` | varchar(32) | B:验证方式 | 100% **单值 `LLM核验`** | 不要 | sympy 留位从没启用 |
| `dna_type` | varchar(50) | [冻结]三集合是方法论非存储维 | 97 (5.4%) | 不要 | |

**🔴 这张表的教训**：26 列里 **4 个死列 + 3 个近死列 + 3 个单值列**，最高覆盖率的列（`difficulty_reason`）也只有 65% 的 1799 行 = 全库 7.5%。**「一次设计 26 个 DNA 维度」的做法失败了**；v2 只在 `exam_model` 里放 `params_json`+`dsl_ref` 两个口子，方向正确。

#### 其余打标关联表

| 表 | 行数 | 关键字段 | 死列 | v2 |
|---|---|---|---|---|
| `biz_question_pattern` 题型目录 | **326** | `name`(题型1 利用数轴比较大小)、`anchor_subject_id`(锚在考点上，133 个考点)、`sort` | `description`(0) / `book_id`(0)；`source`/`status` 单值 | **要** ⭐ 见 §5.3 |
| `biz_question_pattern_rel` 题↔题型 | **868** | `question_id`(868 题，1:1)、`pattern_id`、`uk_q_p` | `is_primary` 单值 1 / `source` 单值 | **要** |
| `biz_solution_model` 解题模型词库 | **43** | `id`(DZ01/M001 人类可读码)、`name`、`model_kind`(gold 15/derived 28)、`category`(16 类)、**`trigger_feature`(什么题面信号触发)**、**`action_conclusion`(招式动作→结论)**、`difficulty_tier`(1-4)、`freq_band`(1-3) | `topic_id`(0)、`mother_question_id`(0)、`page_anchor`(0)；`book_id`/`source_book` 单值 | **要** ⭐⭐ 见 §5.3 |
| `biz_solution_model_kp` 模型↔考点 | 43 | `bind_type`(primary/native/cross) | — | **要** |
| `biz_question_model` 题↔模型 | **175** | `question_id`(126 题)、`model_id`(29 模型)、`is_primary`、`role` | `source` 单值 AI | **要** |
| `biz_pitfall` 易错库 | **193** | `title`、`description`、`knowledge_id`(70 考点)、`is_gold`；🆕科学扩展列 `trigger_feature`/`typical_error`/`correction`/`severity_tier`(1-3) **只 10 行有值(5.2%)** | `error_type` 有值 10 行且单值 / `source_anchor` 10 行单值 / `status` 单值 | **改造** |
| `biz_question_pitfall` 题↔易错 | 183 | 178 题 | `source` 单值 book | 要 |
| `biz_key_concept` 考点→关键字 | 40 | `subject_id`、`concept`、`source`(书) | — | 不要（覆盖太小） |
| `biz_label_audit` 打标审计 | **10** | `api`/`action`/`target_type`/`target_id`/`actor`/`actor_type`(agent\|human)/`payload_brief`/`result` | — | **改造** | 设计对（写接口全留痕），但只 10 行=**审计没真接上**。v2 `skill_log` 同想法 |
| `biz_dna_edit_log` 经验层留痕 | **1** | 注释自陈「只累计不消费」 | — | 不要 |

`biz_pitfall` 数据卫生：**193 条里 55 条 `title` 就是 `description` 的前缀截断**（`title` 被当摘要用，导致 `title` 是一句被切断的话，如 `'不含某项'即合并同类项后该项系数为0，需令对应系数等于0求`）。v2 `error_cause.name` 必须是**短名**，不能重蹈。

### 1.4 图与资产

#### `biz_question_image` — 题↔图 M:N（**7248 行**）

| 字段 | 类型 | 注释 | 在用? | v2 | 理由 |
|---|---|---|---|---|---|
| `question_id` | bigint | — | 100%，**5136 题有图** | 要 | |
| `asset_id` | bigint | →image_asset.id(去重层) | 100%，6371 个资产 | 改造 | **1 条指向不存在的 asset**（轻微漂移） |
| `oss_url` | varchar(1024) | 冗余 image_asset.oss_url(=blockJson图块url, **join键**) | 100% | 改造 | 🔴 **靠 URL 字符串跟 block_json 里的图块对账**——这是最脆的一环（改桶/换域名即断） |
| `block_id` | varchar(32) | 绑哪个块 | **370 (5.1%) 近死列**，只 2 取值（`stem` / 空串） | **不要** | 🔴 **块级绑定这个卖点没实现**：6003 行 NULL + 875 行空串，只 370 行写了 `stem` |
| `role` | varchar(12) | 题图/选项图/答案图/辅助图 | 7233 (99.8%)，**6 取值** | **改造** | 🔴 **中英混用脏词表**：`stem`5555 / `figure`1091 / **`题图`287** / `analysis`217 / **`选项图`44** / **`辅助图`39**。两批管线各写一套词 |
| `seq` | int | 同块内图序 | 100%，17 取值 | 要 | |
| `is_decorative` | tinyint(1) | 1装饰图(章首/版式,滤掉) | 100%（1=**23** 行） | 改造 | 想法对（滤掉版式图），实际只标了 23 张 |
| `create_time` | datetime | — | 100% | | |

🔴 **索引漂移**：**63 道题的 `block_json` 里有 `image` 块，但 `biz_question_image` 一行都没有** → 这张表**不是权威索引**，`block_json` 才是。

#### `image_asset` — 资产去重层（**7214 行**，20 列）

`src_url` / `url_hash`(char64 UNIQUE) / `host` / `asset_kind` / `ext` / `rel_path` / `local_path` / `entity_type`+`entity_id`+`entity_ref` / `status`(pending 默认) / `file_size` / `content_type` / `http_code` / `attempt_count` / `err_msg` / `download_ts` / **`oss_url`** / `oss_uploaded_ts` / `created_at`。

- **有价值的部分**：`url_hash` 唯一键做内容去重 + `status`/`attempt_count`/`err_msg` 做下载状态机 —— ≈ v2 `asset.hash`，同一个思路。
- **v2 的改进是对的**：老区 `local_path` 是**绝对路径**、`oss_url` 是**绝对 URL**（全部 7248 张图都在 `ai-book.oss-cn-hangzhou.aliyuncs.com` 单一桶）。v2 已定 `asset.rel_path` **一律相对 v2 根**——正确，且这是**互通的头号有损点**（§5.4）。
- 表名/注释仍写 `misikt 资源 URL → 本地路径映射`（`misikt` 是更早的前身系统），**改用途没改注释**。

### 1.5 三套载体（题挂在哪）

老区**三套并存、互不相通**的载体，覆盖去重后：`biz_shelf_item` **13046 题** / `biz_paper_question` **1819 题** / `biz_book_question` **893 题**，**30 题无任何载体**。

#### A. 书架 `biz_shelf_*`（主力，PRD-002）

**`biz_shelf_book`（70 行，17 列）**

| 字段 | 在用? | v2 | 说明 |
|---|---|---|---|
| `id` bigint 雪花 | 70 | 要 | |
| `book_type` varchar(16) | **6 取值**：`lecture`25 / `pdf_pending`23 / `daily_punch`12 / `textbook`4 / `workbook`4 / `special`2 | **要** | ≈ v2 `artifact.kind`。⚠️ 注释只写了 `lecture/workbook/special` 三个，实际多出 `pdf_pending`(纯 PDF 挂账壳) / `daily_punch`(打卡) / `textbook` |
| `title` / `subject_id` / `grade` / `edition` | 100% / 84.3% / 80% / 64.3% | 要 | |
| `owner_id` / `create_by` / `update_by` / `create_dept` | 100%（3 / 2 / 3 / **单值**） | 不要 | 单人使用 |
| `status` char(1) 0正常1归档 | 2 取值 | 改造 | |
| **`style_meta_json` json** | **35 (50%)** | **要** ⭐ | 见 §2.6 全文剖析 |
| `source_job_id` | **0 死列** | 不要 | 「录入直出书溯源」（PRD-001 D6）设计了没用 |
| `is_public` tinyint | 2 取值 | 要 | 注释 GBK 乱码（§6.3） |
| `remark` | 2 (2.9%) | 不要 | |

**`biz_shelf_node`（3617 行，10 列）** — 每本书自持目录树
`id`(雪花) / `book_id` / `parent_id`(NULL=根，411 行是根) / `seq` / **`node_type`（14 取值：`kp`2374 / `qtype_group`585 / `unit`235 / `module`69 / `training`60 / **`punch_day`60** / `section`55 / `tier`46 / `lecture`39 / `chapter`39 / `sec`31 / `topic`12 / `test`11 / `appendix`1，注释明说「自由值不设枚举闸」）** / `name`（卷面可见，禁内部词）/ **`kp_id` bigint = 0 死列** / `meta_json`(62 行 1.7%) / 时间戳。
🔴 `kp_id` 是**死列**——「节点可选 KG 锚」（D8）设计了一行没写。且类型是 `bigint` 而 `biz_subject.id` 是 `varchar(20)`，**类型都对不上**，注定写不进去。

**`biz_shelf_item`（16005 行，14 列）** — 内容项
`id`(雪花) / `book_id`(冗余) / `node_id` / `seq` / **`kind`（3 取值：`question`13106 / `explain`2712 / **`module`187**，注释只写了前两个）** / `question_id`(81.9%) / **`override_json`(47.5%)** / **`explain_json`(16.9%)** / **`content_json`(187, 1.2%)** / `source_page`(60.2%) / `used_count`(认证计数，5 取值) / 时间戳 / **`confidence`(95.9%, 8 取值: 45/65/70/72/75/85/92/95)**。

三个 JSON 列的真实内容：
- `override_json`（书内改题副本）**实际只装角色标签**，去重后 top6 全是同一形状：`{"role":"practice","roleSeq":2,"roleLabel":"对应练习"}` / `{"role":"example","roleLabel":"典型例题"}`。**「书内改题」的能力没用上，这列退化成了「题在书里的角色」**。
- `explain_json`（讲解块）：`{"title":"知识点一、桥梁的结构","text":"1. 桥梁的组成：⟦c:#c00000⟧主梁⟦/c⟧、…"}` —— 🔴 **自造了颜色标记语法 `⟦c:#RRGGBB⟧…⟦/c⟧`**（不是 Markdown 不是 HTML）。v2 若要吃老讲义必须实现这个方言。
- `content_json`（打卡模块）：`{"type":"oral","title":"口算题","items":[{"q":"26×4＝","a":"104"}]}` / `{"type":"stepwise","title":"脱式计算","items":[{"q":"480－72÷8×5＝","a":"435"}]}`。

**`confidence` 是老区一个被低估的好设计**：0-100 页级置信度，>=90 速过 / 60-89 常规 / <60 重点审，95.9% 覆盖。v2 `ingest_item.gates_json` 可以吸收。

#### B. 试卷 `biz_paper_*`（PRD 早期）

`biz_paper`(134) → `biz_paper_section`(169) → `biz_paper_question`(2017)；`biz_paper_category`(110) 独立分类树；`biz_paper_basket`(0 空表)。

- `biz_paper_question`：`paper_id`/`section_id`/`question_id`/`sort`/`score`，`uk_section_sort(section_id,sort)` —— **5 列全 100% 在用，零死列**，是全库最干净的表。
- `biz_paper` 死列：`region` / `school` / `exam_type`（三个都 0）；单值列：`status`(0) / `sort`(0) / `exam_year`。`paper_kind`(1普通/2备课卷) 注释 GBK 乱码。
- 🔴 **`biz_paper.id` 是混合 ID 方案**：118 行小自增 id（15 ~ 2026-07-27）+ 16 行雪花号（2026-07-27 起）—— **中途从自增切雪花，没回填**。这是 v2「一切 id 走 TEXT」纪律的历史来源。
- `biz_paper_section.title` 实况：153 个是通用 `题目`，另 15 个塞了 `从自然数到有理数::有理数的分类` 这种 **`章::节` 双冒号复合串**（结构信息塞进了 varchar(50) 标题）。

#### C. 教辅 `biz_book_*`（必刷题整书录入）

`biz_book`(**1 行**) / `biz_book_question`(893) / `biz_book_subject`(**0 空表**)。

- `biz_book` 只有 1 行 → 「教材版本 SSOT」实际只录了一本书；`biz_book_subject`（书图谱快照）**0 行，从没启用**。
- `biz_book_question` 的价值：`column_type`（**书栏目 12 取值**：`刷基础`428 / `刷提升`146 / `刷难关`81 / `刷中考`75 / `刷章测`42 / `章测`42 / `刷易错`21 / `刷素养`19 / `中考新考向备训`14 / `巩固提升`11 / `知识精讲`7 / `习题精练`7）——**「题在书里属于哪个栏目」是有价值的难度/用途信号**。⚠️ `刷章测` 与 `章测` 是同义重复（脏）。
- 死列：`book_difficulty`（868 行非 NULL 但**全是空串**——典型「写了空字符串冒充有值」）；单值列：`container_type`(全 `section`)；近死列：`role`(25, 2.8%)。

### 1.6 录入管线

**`biz_ingest_job`（46 行，23 列）** — 与 v2 `ingest_batch` 高度对位
`id`(雪花) / `teacher_id` / `subject_id`(整批粗挂) / `source_file_name` / `source_oss_url` / `source_type`(image/pdf/docx/text) / **`lane`(fast 文字层 / slow 页图 / **`hosted`** ——注释只写了前两个)** / **`answer_mode`(from_source / ai_solve / stem_only)** / **`commit_mode`(review / direct)** / `grade_hint`(21.7%) / `status`(**只 DONE/FAILED 两态存活**，注释声明的 PENDING/EXTRACT_ING/SPLIT_ING 一条不剩=中间态不落库) / `error_msg` / `question_count` / `committed_count` / `handled_time` / `dropped_json`(23.9%) / 审计列。
死列：`create_dept` / `update_by`。

🔴 **`answer_mode` × `commit_mode` 这两个旋钮是老区录入管线最有价值的抽象**（答案从哪来 × 入库要不要过审），v2 `ingest_batch` **目前没有这两列**——建议补（§5.3）。

**`biz_ingest_job_item`（262 行，19 列）** — 与 v2 `ingest_item` 对位
`id` / `job_id` / `seq` / `stem_text`(Markdown+$LaTeX$) / `question_type` / **`options_json`(38.5%)** / `answer_text` / `analyze_text` / `has_figure` / `difficulty` / **`dna_json`(72.5%)** / **`verify_verdict`(pass/fail/degrade, 38.5%)** / `need_review`(**单值 0**) / `item_status`(pending 137+66+12+22 / committed 25) / `committed_question_id`(9.5%) / **`figures_json`(24.8%)** / **`kp_anchor_json`(31.3%)** / 时间戳。

三个 JSON 列的真实形状（**v2 录入契约可直接参考**）：
```json
// dna_json
{"main_kp":{"id":"","name":"有理数大小比较"},"secondary_kps":[],"qtype":"选择","exam_type":"概念辨析",
 "skeleton":["确定比较对象：找比-2小的数","逐项应用负数比较法则判断","得出答案"],
 "hard_points":[],"hard_point_count":0,"tags":["有理数","大小比较","负数","基础概念"],
 "scene":"纯代数","difficulty":1,"model_candidates":[],"flags":[]}

// kp_anchor_json —— 命中/兜底两种形态，带 stage 与 confidence
{"kpId":"901001002002005","stage":"exact","kpName":"温度计的使用方法","fallback":false,"confidence":1.0,"matchedName":"温度计的使用方法"}
{"kpId":"901","stage":"fallback","kpName":"长度测量的规范操作","fallback":true,"confidence":0.3,"matchedName":"科学七年级上(浙教2024)"}

// figures_json —— 带 bbox 与 OCR 置信度
[{"seq":1,"bbox":[164,502,392,659],"conf":0.929,"ossUrl":"https://…/a145bb….png","assigned":true}]
```
🔴 **`kp_anchor_json` 的 `stage`+`fallback`+`confidence` 三元组值得 v2 抄**：兜底时 `kpId` 退到教材根 `901`、`confidence` 降到 0.3、`fallback=true` —— 明确区分「真命中」和「挂不上只好挂根」，这正是 v2 `review_ticket(kind='kp低置信')` 需要的输入。

⚠️ **`verify_verdict` 实况**：`degrade`67 / `pass`22 / `fail`12 —— **degrade（降级/没验成）占 2/3**，sympy 验算实际不好用。

**`biz_review_issue`（423 行）/ `biz_review_page`（227 行）** — PRD-006 审核
- `biz_review_issue`：`book_id`/`question_id`(可空=整页问题)/`source_page`/`issue_type`/`description`/`status`(待处理/已改/搁置)/**`source`(human 金标 / agent 自查)**。**423 行是全库最活跃的「人工反馈」数据**，v2 `review_ticket` 对位。
- `biz_review_page`：`uk_book_page(book_id,page_no)` + `reviewed`/`reviewed_by`/`reviewed_time` —— **页级确认**这个粒度很实用。

### 1.7 变式 / 举一反三

| 表 | 行数 | 结论 |
|---|---|---|
| `biz_variation_trace` | **6** | 🔴 **声明是变式血缘 SSOT，实际是空的**。6 行全是同一批补账：`method='legacy_backfill'` / `method_detail='P3.3补账;mother_source=同书母题'` / `created_by='PRD-C-206'`。`variation_degree`/`similarity_band`/`same_source` **三列全死**。注释说 `method` 是「9 算子裸名」——**9 个算子一个都没出现过** |
| `biz_variant_upload` | 62 | 母题图上传留痕（OSS 对象键/原名/大小/MIME/`biz_scene`/`oss_config_key`）。纯附件表，可用 |
| `biz_chapter_figure_map` | **0** | 「章节×图型映射（造图定型闸）」空表 |

🔴 **举一反三这条线在 DB 层几乎是空的**：血缘 6 行、图型映射 0 行、`variation_profile` 41 行、`solution_skeleton` 191 行。真正的变式生产发生在 **本地产物目录 + toolkit**，没有落库。**v2 不要再建一套空表**，先让本地跑久（CLAUDE.md §0.0）。

### 1.8 用户侧小表（全部可不继承）

`biz_question_basket`(52, 试题筐 `user_id+question_id` 复合 PK) / `biz_paper_basket`(**0**) / `biz_question_favorite`(**0**) / `biz_question_folder`(**0**) / `biz_question_note`(**0**) / `biz_export_record`(**1**, `options json {variant,watermark,ids[]}`)。
→ 5 张多用户协作表全空，**印证「单人使用」**。v2 不要建。

---

## §2 `block_json` 规范剖析

> 本节结论为**数据实扫 + 代码三处契约互证**。
> 🔒 契约锁定在三处（改一处必同步三处，`blockSchema.ts:4` 原话「共享契约（A-015 ∥ C-100 双分支锁定，不得私改」）：
> ① **DDL 注释** `codeplace-O/book-server/sql/收敛DDL-2026-07.sql:514`
> ② **Java 校验器** `codeplace-O/book-server/ruoyi-modules/ruoyi-book/src/main/java/org/dromara/book/util/BlockJsonValidator.java`
> ③ **FE 类型/解析** `codeplace-O/book-ui/src/utils/blockSchema.ts:38-45`
> ⚠️ PRD-A-015 §10.1 的 PRD 正文已归档不可查，上述三处代码/DDL 注释即现存最权威事实源。
> ⚠️ 五份 book-server（O/C/A/B/_build-wt）的 `BlockJsonConverter.java` 等关键文件 **md5 完全相同**，故统一引 `codeplace-O` 路径。

### 2.1 Schema（**全量 12236 份 + 891 份答案 + 891 份解析实扫，非抽样**）

```
文档   := { "v": 1, "rows": [ Row ] }              // 顶层只有 v 和 rows 两个 key，零例外
Row    := { "cells": [ Block ] }                   // Row 只有 cells 一个 key，零例外
Block  := TextBlock | ImageBlock | OptionBlock     // 🔴 全库只存在这三型，无第四型
```

```
TextBlock   := { "type":"text",  "md": <string> }
                 // md = Markdown + 内联 $LaTeX$；GFM 管道表格也直接写在 md 里

ImageBlock  := { "type":"image", "url": <绝对 OSS URL>,
                 "align":"center", "width": <number 百分比>,
                 "caption": <string 可选, 仅 76 处> }

OptionBlock := { "type":"option", "label":"A"|"B"|"C"|"D",
                 "content": [ TextBlock | ImageBlock ] }   // 选项体本身是块数组，可含图
```

**块型出现次数（block_json 列全量）**：`text` 14120 / `image` 5468 / `option` 5187。
**答案列 / 解析列**：`text` **only**（1260 / 1578 次）——答案与解析从不含图、不含选项。
**image 块字段全集**：`url`5467 / `type`5468 / `align`5467 / `width`5467 / `caption`76 / **`md`1（脏数据：一个 image 块混进了 md 键）**。
**option.content 子块**：`text`4886 / **`image`313**（选项里能放图，重要）。

**🔴 三型不是「碰巧只用了三型」，是校验器硬闸**（`BlockJsonValidator.java`）：

| 约束 | 代码 | 行号 |
|---|---|---|
| 块型白名单 = 3 型，第四型直接抛错 | `switch(type)` 三分支 + `default -> throw "未知 type="` | `:101-116` |
| 叶子块只许 2 型 | `LEAF_BLOCK_TYPES = Set.of("text","image")` | `:32` |
| text 必须有 `md`（string） | | `:102-107` |
| image 必须有 `url`(string) + **`width` 整数且 1-100** + `align` ∈ {left,center,right} | `IMAGE_ALIGNS = Set.of("left","center","right")` | `:34`、`:119-136` |
| option 必须有 `label`(string) + `content`(数组)，**content 内 leafOnly=true —— option 不许嵌套 option** | | `:110-112`、`:138-157` |
| rows 每项必须是 object 且有 `cells` 数组；报错定位到「第 N 行第 M 格」 | | `:66-80` |
| 调用点（必过闸） | `QuestionServiceImpl.java:963 / 1094 / 1145`、`IngestServiceImpl.java:527`；`update-block` 空白直接 400 | |

🔴 **全库没有 block 类型的 Java enum**（`domain/enums/` 下只有 `BizQuestionType.java`）——块型词表的唯一权威就是上面那个 `Set.of(...)`。
🔴 **`formula` / `blank` / `table` / `grid` / `row` / `cell` 作为块型 = 确认不存在**（`rows`/`cells` 是容器结构，不是块型）。
⚠️ **`caption` 是单边扩展**：FE 类型有它（`blockSchema.ts:22-28`「可选图序号，如"图①"，多图题由数据侧回填」），但 **Java validator 不校验、Java converter 不产出**。DB 里 76 处 caption 全是数据侧/脚本写的。

### 2.2 真实样例（脱敏后原样）

**选择题（`question_id=2069819158257750018`）**
```json
{"v": 1, "rows": [
  {"cells": [{"md": "《礼记·杂记上》记载：\"苇席以为屋，蒲席以为裳帷.\"蒲为多年生草本植物…其中涉及的自然数 2 属于（  ）", "type": "text"}]},
  {"cells": [
    {"type": "option", "label": "A", "content": [{"md": "计数", "type": "text"}]},
    {"type": "option", "label": "B", "content": [{"md": "测量", "type": "text"}]},
    {"type": "option", "label": "C", "content": [{"md": "标号", "type": "text"}]},
    {"type": "option", "label": "D", "content": [{"md": "排序", "type": "text"}]}
  ]}
]}
```
→ **四个选项是同一个 Row 里的四个 cell**（横排布局），这是 `rows/cells` 网格存在的**唯一真实用途**。

**含 LaTeX（`question_id=2069819160216489986`）**
```json
{"cells": [{"md": "在分数 $\\frac{3}{8},\\frac{17}{25},\\frac{8}{12},\\frac{9}{30},\\frac{7}{12},\\frac{5}{6}$ 中，不能化成有限小数的有（  ）", "type": "text"}]}
```
→ **公式 = md 字符串里的内联 `$…$`**，不是独立的 formula 块，不是占位符。反斜杠在 JSON 里正常转义。

**含图（`question_id=2069819161722245122`）**
```json
{"cells": [{"url": "https://ai-book.oss-cn-hangzhou.aliyuncs.com/2026/06/24/4171c8….jpg",
            "type": "image", "align": "center", "width": 45}]}
```
→ **`width: 45` = 百分比宽度**（不是 px）；`url` 是**绝对 OSS 地址**。

**含表格（`question_id=2069819165375483905`）**
```json
{"cells": [{"md": "粮库某月前 5 天进出粮食的记录如下表（其中以运进为正）：\n\n| 日期 | 1 | 2 | 3 | 4 | 5 |\n|---|---|---|---|---|---|\n| 进出粮食/吨 | $-32$ | $+84$ | $-26$ | $-56$ | $+68$ |\n\n说出各天记录的实际意义．", "type": "text"}]}
```
→ 🔴 **表格没有专门块型，是 md 里的 GFM 管道表格**（全库 **74 份** block_json 含 `|---`）。单元格里还嵌 `$LaTeX$`。

**答案/解析块（同题）**
```json
answer_block_json  : {"v":1,"rows":[{"cells":[{"type":"text","md":"B"}]}]}
analyze_block_json : {"v":1,"rows":[{"cells":[{"type":"text","md":"题目中涉及的自然数 2 属于测量．故选 B."}]}]}
```
→ 答案/解析用**同一套 schema**（同构），只是只有 text 块。**这个「三份同构块流」的设计 v2 已经继承，是对的。**

### 2.3 rows/cells 网格到底用了多少

| 每 Row 的 cell 数 | Row 数 | 说明 |
|---|---|---|
| 1 | **19775 (92.3%)** | 单块独占一行 |
| 2 | 970 | 几乎全是选项横排 |
| 3 | 289 | 同上 |
| 4 | 547 | 四选项横排 |
| 5 | 1 | |

**含 option 块的题 = 1373**；**含 image 块的题 = 4809**；
🔴 **真正的多列布局（同一 Row 里多个「非 option」cell）只有 16 道题。**

**⇒ 结论：`rows/cells` 二维网格 99.9% 只是为了「选项横排」。除此之外它就是一维块流。** v2 用扁平 `blocks_json` 数组**几乎零损失**——只要解决选项表达（下一节）。

### 2.4 与 v2 「块流」的差异表

v2 现行定义（[数据结构.md](数据结构.md) §2.1）：
`blocks_json := [{type:'text',text} | {type:'figure',asset,caption} | {type:'table',rows}]`

| 维度 | 老区 `block_json` | v2 `blocks_json` | 差异性质 | 处置建议 |
|---|---|---|---|---|
| 容器形状 | 二维 `{v,rows:[{cells:[…]}]}` | 一维数组 | **v2 更简** | ✅ 保持 v2。老区→v2：`rows.flatMap(r=>r.cells)` |
| schema 版本位 | 有 `v`（虽从未 bump） | **无** | v2 缺 | 🔴 **建议 v2 补一个版本位**（外层包 `{v:1,blocks:[…]}` 或每块带 `v`）；老区 5 年没 bump 也不等于不需要退路 |
| 文本块 | `{type:'text', md}` — 键名 **`md`**，语义=Markdown+内联`$LaTeX$` | `{type:'text', text}` — 键名 **`text`**，**语义未写明** | **键名不同 + 语义未定义** | 🔴 **两件事**：①互通要做 `md`↔`text` 键名翻译；②**v2 必须在文档里把「text 内容 = Markdown + 内联 $LaTeX$」写成硬口径**，否则各 skill 各写一套（老区靠 12236 份数据把这个口径跑实了，是免费经验） |
| 图块 | `{type:'image', url(绝对OSS), align, width(百分比), caption?}` | `{type:'figure', asset(hash), caption}` | **块名不同 + 寻址方式根本不同 + v2 丢了 align/width** | ⚠️ ①`image`↔`figure` 需翻译；②**v2 丢掉 `width` 会丢排版信息**——老区 5467 个图块全都带 `width` 百分比，这是「图在卷面占多宽」的真实生产数据，删了以后出卷排版要重新猜。**建议 v2 的 figure 块补 `width`**（`align` 可省，全库单值 `center`） |
| 选项块 | **`{type:'option', label, content:[…]}`**，5187 个块 / 1373 道题，且 **313 个选项含图** | **无 option 块型** | 🔴 **v2 缺口①（最严重）** | 三选一：(a) v2 加 `{type:'option',label,content:[…]}`（与老区同构，互通零成本）；(b) 选项塞进 text 块的 md 里（丢结构，选项含图会烂）；(c) 单开 `question_option` 表。**推荐 (a)** |
| 表格 | **无表格块**，GFM 管道表格写在 `md` 里（74 份） | **有 `{type:'table',rows}`** | v2 更强 | ⚠️ **互通有损**：老区→v2 时 md 里的表格要么解析成 table 块（有解析风险），要么原样留在 text 里（v2 得能渲染 md 表格）。**建议 v2 明确「text 块允许含 GFM 表格」**，table 块只给新录入用 |
| 答案/解析 | 同构块流（`answer_block_json`/`analyze_block_json`，但只 891 份=7.3%） | 同构块流（`answer_blocks_json`/`analysis_blocks_json`） | **v2 一致** ✅ | 老区的坑是**答案真事实源在另一张表**（`biz_text_content` 8450 行），v2 收进一列是正确的去重 |
| 存储类型 | `block_json` = **json**；`answer_block_json`/`analyze_block_json` = **mediumtext**（不一致） | 全 TEXT（SQLite） | — | SQLite 无 json 类型，正常 |

### 2.4b 生产端：md → block 的转换规则（v2 若要吃老区题，这就是逆向说明书）

**唯一转换器** = `BlockJsonConverter.java`（纯函数，不依赖 DB）。两个入口：
- `convert(FormatToBlockBo)` `:80-106` ← 端点 `POST /teacher/format/to-block`（`FormatController.java:40-58`）
- `convertRichText(...)` `:118-146` ← 端点 `POST /teacher/format/rich`（`FormatController.java:67-82`），专供「纯富文本答案/解析 → block」

**规则逐条**：

| 步 | 规则 | 行号 |
|---|---|---|
| 1 | `stem` 空 → `{v:1,rows:[]}` | `:92-94` |
| 2 | 抽图：扫 `![alt](url)`，可带 **`{w=NN}`** 宽度后缀；按图位切段 | `:46-47`、`:286-311` |
| 3 | 每文本段：按**行首** `（n）/(n)` 切小问（引导句 1 块 + 每小问 1 块）；切不到 → 整段 1 块 | `:50-51`、`:253-281` |
| 3b | 「内联小问」补丁（C-204）：同行 `计算：(1)…；(2)…` 也切，但过 **G8 守卫 `isRealSubQStart`** —— `在（2）的条件下` / `（1）（2）（3）` 连排引用**不切**（引导字集 `REF_LEAD_CHARS="在的与和对由把将这那从据如按用借参照依结合根"`，需 ≥2 个真起点才注入） | `:151-158`、`:181-240` |
| 4 | 选项：`type=1` 或 `options` 非空 → 每项一 option 块，label 按下标 A/B/C… | `:97-99`、`:331-337`、`:471-477` |
| 4b | **选项自动排版**（按可视长度）：N=4 且 maxLen≤5 → `[4]` 横排；≤20 → `[2,2]`；否则竖排；N=2/3 且 ≤12 → 横排；含图时 N=4 走 `[2,2]` | `:396-418` |
| 5 | 每块独占一 row 一 cell；多块并排走 `addMultiCellRow`（注释：前端按 `repeat(N,1fr)` 渲成 N 列） | `:527-546` |
| 6 | **逃生仓：对外永不抛** —— 任何异常 → 整题干兜 1 个 text 块 + 选项块；连兜底失败返 `{"v":1,"rows":[]}` | `:102-105`、`:142-145`、`:551-575` |
| — | 端点自检不过**不 500**，降级返回并附 `degraded:true` + `degradeReason` | `FormatController.java:45-55` |

**🔴 公式 = LaTeX 原样留在 `text.md` 的 `$…$`，不转公式块**（三条互证）：
① `FormatToBlockBo.java:32-34` 入参注释「题干 markdown（自然写法）：可含小问 `（1）（2）`、图标记 `![](url)`（可带 `{w=45}`）、**表格**、**`$LaTeX$`**」；
② validator 无 formula 分支；
③ converter 里 LaTeX **只被用来估算选项可视宽度**（`LATEX_CMD_PATTERN=\\[a-zA-Z]+` 折成 1 个 `#`），**不改写不抽块**（`:66-68`、`:433-450`；`:439-441` 注释：「删 0 会把 `$\pm\sqrt{9}=\pm3$ 误判成超短选项」）。

**🔴 图片字段名就叫 `url`**（不是 `imageUrl`/`ossUrl`/`src`）：`:518-525` 只 put `type`/`url`/`width`/`align`；缺省 `DEFAULT_IMG_WIDTH=45`、`DEFAULT_IMG_ALIGN="center"`（`:70-71`）。
上传链：MCP `upload_image` → `POST /teacher/ingest/image` → 返 **`ossUrl`** → 塞进 md 的 `![](ossUrl)`（`data_qbank.py:253/262/270`）。

**MCP 链路**（`codeplace-O/teacher-mcp/src/teacher_mcp/tools/data_qbank.py`）：
`format_question(question_type, stem, options=[])` `:231-249` → POST `/teacher/format/to-block` → 返 `{ok, block_json, degraded}`；
`ingest_question` `:274-363`（`:329-330` `if block_json: body["blockJson"]=block_json`，空则只存 `stem_text`）；
`ingest_items` `:365-488` 批量（`:469-473` 每题先调 `format_question`，失败降级只存文本）。
回读时 `shared.py:101-103` 把 `blockJson/answerBlockJson/analyzeBlockJson` 映射成蛇形。

### 2.4c 消费端：谁渲染、用什么渲染公式

**唯一 FE 渲染组件** = `codeplace-O/book-ui/src/components/business/QuestionBlockRender/index.vue`（**14 个引用点**：题目详情/编辑器、书架、试卷工作台、题卡、卷面预览、KG 讲义节点视图等），组件头 `:1-20` 自述「渲染 A-015 §10.1 锁定的 block schema，三端一致由单一组件保证」。

| type | 认哪些字段 | 怎么渲 | 行号 |
|---|---|---|---|
| `text` | `md` | `v-safe-html="textHtml(cell.md)"` → `renderRichText` | `:245-248`、`:102-104` |
| `image` | **`url`** / `width`(=容器宽百分比) / `align` / `caption?` | `<figure><img><figcaption>` | `:251-274`、`:117-131` |
| `option` | `label` / `content:[text|image]` | `<span>{{label}}.</span>` + 子块循环 | `:276-304` |

网格落地：`:236` `gridTemplateColumns: repeat(${row.cells.length}, minmax(0,1fr))` —— **cells 数直接等于列数**。
FE 独有的显示层加工（DB 无对应结构）：**figgroup**（连续 ≥2 个「单 image cell 的 row」自动并排，`:43-98`）、**caption 按全角空格切段与子图对齐**（`:157-179`）、图点击开原图（`:182-188`）。
填空位靠 **md 里的连续空格/全角空格 + CSS `white-space:pre-wrap`** 保住（`:378-387`）；表格靠 md GFM，渲染端补网格线（`:406-423`）。

**🔴 公式引擎在老区是分裂的（同一份 blockJson 三种命运）**：

| 场景 | 引擎 | 证据 |
|---|---|---|
| 浏览页（FE） | **KaTeX** + markdown-it（`html:false` 防注入，`throwOnError=false` 降级渲原文） | `book-ui/src/utils/richtext.ts:1-18`、`:38-41`（先过 `normalizeMath`，与 BE 同口径） |
| 导出主题 `book-v1` / `sujunyu-v1` / `oralcalc-v1` | **KaTeX**（本地 `katex.min.css` + auto-render） | `.../resources/export-themes/book-v1/book-v1.html:6-8` 等 |
| 导出主题 `flat-v1` / `sections-v1` | **MathJax**（`inlineMath:[['\\(','\\)']]` + svg 输出） | `export-themes/flat-v1/flat-v1.html:11/49`、`sections-v1:13/68` |
| 导出主题 `punch-v1` | **两者都不用** —— 主题不认 LaTeX，`q`/`a` 用可读数学文本（`√36`、`∛(-27)`） | `举一反三产物/打卡/_工厂索引.md:303` |

⚠️ **注意 `flat-v1` 的 inlineMath 定界符是 `\( \)` 而 DB 里存的是 `$ $`** —— 两套定界符共存是老区一个隐性坑。
**⇒ v2 纪律建议**：块流里 LaTeX 定界符**只许 `$…$` 一种**，渲染器（浏览/PDF）**只许一个引擎**。老区「三套引擎 + 两套定界符」是随主题长出来的债。

**BE 导出侧也有一份独立的 block 渲染实现**（与 FE 同构、手抄）：`BookExportService.java:249-255`「🔴 blockJson 整块喂主题（rows 原样传递，text/image/option 三型全保真，不丢图）」+ `export-themes/book-v1/book-v1.html:181-201` `renderBlockRows(...)`；`punch-v1.html:285` 注释「渲染移植自 book-v1 renderBlockRows」。
**⇒ 老区实际有 3 份 block 渲染代码**（FE 组件 / book-v1 主题 JS / punch-v1 主题 JS）。**v2 只该有一份。**

**🔴 默认图宽四层不一致（真坑，v2 别抄）**：
BE 转换器 `45`（`BlockJsonConverter.java:70`）／FE 渲染兜底 `40`（`QuestionBlockRender/index.vue:118`）／FE 编辑器新建图块 `40`（`editor.vue:173`、选项内图 `:305`）／`blockSchema.ts:138` normalize 兜底 **100**。
**⇒ v2 的 `figure.width` 必须有唯一缺省常量，且写在一个地方。**

### 2.5 老区 block 层已知的四个坑（v2 别重蹈）

| # | 坑 | 证据 |
|---|---|---|
| ① | **图片索引表不权威**：`biz_question_image` 号称是题↔图索引，但 **63 道题的 block_json 里有 image 块而索引表零记录**；反过来索引表靠 `oss_url` **字符串**跟 block 里的图对账（改桶即断） | §1.4 实测 |
| ② | **块级绑定 `block_id` 名存实亡**：设计成「这张图绑哪个块」，实际 6003 NULL + 875 空串，只 370 行写了 `stem`，去重基数=2 | `biz_question_image.block_id` |
| ③ | **`role` 词表中英混用**：`stem`/`figure`/`analysis` 与 `题图`/`选项图`/`辅助图` 并存 | §1.4 |
| ④ | **HTML 漏进文本层**：`biz_text_content` 有 **8 行** `content` 里是裸 `<img src="…" style="width:555px">`（block_json 层 **0 行**，块层是干净的） | §1.2 |

### 2.6 `style_meta_json`（书级版式/交付元数据）

**位置**：`biz_shelf_book.style_meta_json`（json，35/70 行有值 = 50%）。DDL 正本 = `codeplace-A/prd/PRD-002/DDL.sql:15`；实体 = `BizShelfBook.java:55`。

#### 🔴 字段名坑（六层，两层名字不一样）— 这就是记忆里那个「styleMeta 字段名坑」的全貌

| 层 | 名字 | 证据 |
|---|---|---|
| ① DB 列 | `style_meta_json` | `codeplace-A/prd/PRD-002/DDL.sql:15` |
| ② Java 实体 | `styleMetaJson` | `BizShelfBook.java:55` |
| ③ **Java BO（HTTP 入参）** | 🔴 **`styleMeta`**（去 Json 后缀） | `ShelfBookBo.java:33-34`、`ShelfImportBo.java:31` |
| ④ Java VO（HTTP 出参） | **`styleMeta`** | `ShelfService.java:893` `m.put("styleMeta", parse(b.getStyleMetaJson()))` |
| ⑤ FE 类型 | `styleMeta` | `book-ui/src/api/shelf/index.ts:97`、`:246` |
| ⑥ MCP | **完全没有这个字段** —— `create_book` 只发 `{title,bookType,subjectId,grade,edition}` | `teacher-mcp/src/teacher_mcp/tools/shelf.py:49-50` |

**踩坑正本（人写的，一句话说透）** `举一反三产物/打卡/_工厂索引.md:305`：
> 「建书传样式的字段名是 **styleMeta**，传 `styleMetaJson` 被**静默丢弃**。」

**🔴🔴 但真正让人记不住的根因是另一条：同一列，两个域的 HTTP 名字相反**
- **shelf 域**（`biz_shelf_book`）：HTTP 名 = **`styleMeta`**（`ShelfBookBo.java:33`）
- **special 域**（`SpecialBook`）：HTTP 名 = **`styleMetaJson`**（`SpecialService.java:75/160-161/585`、`SpecialBook.java:57`、FE `api/special/index.ts:23/79`）

**⇒ v2 教训**：**JSON 列的对外名与列名必须全链路一字不差**（要么处处 `style_meta`，要么处处 `styleMeta`），且**不要在不同域给同一概念起不同名**。老区这个坑造成的是**静默丢弃**——最难查的那一类。

#### 合并写铁律（老区做对了的一件事，v2 该抄）

`ShelfService.mergeStyleMeta(book, patch)`（`ShelfService.java:469-480`）：读旧 → `putAll` → **只 UPDATE `style_meta_json` 一列**；
`parseMap`（`:952-968`）解析失败或非对象 → **直接抛 500 拒绝写**，防止把整列抹光。
**⇒ 这正是 §3.6 说的「JSON 列必须读-改-写」的正确实现范本**（对比 `paper_slots` 整列覆盖出的事故）。

**实测 key 全集（35 行，按频次）**：

| key | 次数 | 装什么 | 真实样例 |
|---|---|---|---|
| `unit` | 23 | 所属单元 | `"有理数"` / `"数轴与绝对值"` |
| `pdfUrl` | 23 | 成品 PDF 的 OSS 地址 | `https://ai-book.oss…/e3c0a0d….pdf` |
| `coverUrl` | 23 | 封面图 | `https://ai-book.oss…/c5ee149….png` |
| `pdfPages` | 23 | 页数 | `22` |
| `punchReview` | 7 | 打卡终审留痕 | `{"at":"2026-07-30T01:33:59","passed":true}` |
| **`netdisks`** | 5 | **网盘分享链接数组** | `[{"url":"https://pan.baidu.com/s/1p8pZil…","code":"us7z","note":"含题目22页+解析22页共2个PDF","provider":"baidu"}]` |
| `subtitle` | 4 | 副标题 | `"人教版 · 三年级全册复习 ＋ 四年级衔接"` |
| `accent` | 3 | 版式强调词 | `"暑假作业"` / `"混合运算"` |
| `punchExport` | 3 | 导出任务结果 | `{"days":10,"format":"pdf","papers":["question","answer"],"status":"done","answerUrl":"…pdf","questionUrl":"…pdf","durationMs":25438,"exportedAt":"2026-08-01T22:27:59"}` |
| `theme` | 3 | 版式骨架名 | `"flat-v1"` / `"sections-v1"` |
| `variantName` | 2 | 版本名 | `"基础版"` / `"提高版"` |
| **`punchLayout`** | 2 | **版式参数** | `{"accent":"实数的运算","qPrefix":"计算：","showInfo":true,"watermark":true}` / `{"fontPt":11.2,"showInfo":true,"showGoals":true,"watermark":false}` |
| **`promo`** | 1 | **宣发文案** | `{"title":"📐七上实数计算每日打卡｜10天200题","desc":"七年级上册「实数」这一章的计算专项 ✏️\n\n📅 10 天 × 每天一页 × 20 题…#每日打卡 #暑期预习"}` |

#### BE 支持但 dev 数据里没出现的 key（代码级补全）

| key | 内容 | 写入者 | 上限 | 出处 |
|---|---|---|---|---|
| **`recipe`** | 生产配方溯源，软约定键 `factory / engine / sourceDir / scripts{} / rebuild / seed / scale{} / modules[] / syllabus / gates[] / pdf / builtAt / next` | `ShelfService.saveRecipe` | JSON ≤8000 字符 | `ShelfService.java:426-467`、端点 `ShelfController.java:141-146`、MCP `save_book_recipe`（`shelf.py:97-129`） |
| `rotatingTitle` | 轮换位标题（缺省「解决问题」），天节点 meta 可覆盖 | 产线脚本 | — | `PunchService.java:135`、`:349-354` |

`netdisks` 白名单 provider ∈ `baidu/quark/aliyun/other`，≤10 条（`ShelfService.java:65/68/226-278`）；`promo` 上限 `title≤100 / desc≤3000`（`:71-72/280-320`）。
🔴 **`netdiskUrl` / `netdisk_url` 全仓零命中** —— 网盘链接**只有数组形态** `netdisks[{provider,url,code?,note?}]`。另有一个 `netdiskCount` 是 **BE 顶层字段不在 style_meta 里**（FE `api/shelf/index.ts:142-147`）。

#### `punchLayout` 的 10 个键分四类（**类型强转事故的现场**）

`PunchService.java:137-168`：
- 布尔（`:142-143`）：`showInfo` / `showGoals` / `showWrongLog` / `watermark`
- 字符串（`:150-151`，**空串是有效值**）：`qPrefix` / `accent` / `tip` / `titlePrefix` / `titleSuffix`
- 数值（`:154`）：`fontPt`
- 数组（`:157`）：`infoFields`

🔴 代码里留着事故记录（`:162-164`）：
> 「老版本一刀切按布尔强转，`flat-v1` 的 `qPrefix:"计算："` 会变成 `true` … **静默毁值，卷面还照渲，最难查**。」

⚠️ **MCP 侧只暴露 3 个布尔**（`set_punch_layout`，`shelf.py:58-94`：`show_info`/`show_goals`/`show_wrong_log` + `reset`）——BE 支持的 `qPrefix/accent/tip/titlePrefix/titleSuffix/fontPt/infoFields/watermark` **8 个键 MCP 完全不可达**，产线脚本只能走 `PUT /teacher/shelf/book/{id}` 传 `styleMeta`（证据：`举一反三产物/打卡/七上实数的运算打卡/_源/gen_prod_migration.py:12-13/40`）。
`theme` 白名单 = `punch-v1 / flat-v1 / sections-v1`，脏值 warn 后回落缺省（`PunchService.java:101/110/253-261`）；`accent` 是**主标题红字的子串命中词，必须真的出现在标题里否则标题全黑**（`_工厂索引.md:306`）。
`netdisks` / `promo` / `theme` / `accent` **都没有 MCP 工具**（只能走 BE 端点或 FE 弹窗）。

**🔴 结论：`style_meta_json` 是个「什么都往里塞」的杂物袋**，一列同时承担了 **6 种互不相关的职责**：
1. 成品件指针（`pdfUrl`/`coverUrl`/`pdfPages`）→ v2 `artifact.files_json`
2. 分发渠道（`netdisks`）→ v2 `artifact.link`（⚠️ v2 是**单个 link 字段**，老区是**数组带 code/note/provider**——v2 应改成数组，一册一链接双号共用的口径需要 `note`）
3. 营销物料（`promo.title`/`promo.desc`）→ v2 **无对位字段** 🔴 缺口②
4. 版式参数（`punchLayout`{fontPt,qPrefix,showInfo,showGoals,watermark}、`theme`、`accent`、`subtitle`）→ v2 `template.params_json`（**v2 拆成独立 template 表是明显改进**）
5. 流程状态（`punchReview`{at,passed}、`punchExport`{status,durationMs,exportedAt}）→ v2 `artifact.status` + `skill_log`
6. 书面元数据（`unit`/`variantName`）→ v2 `artifact.name`/`note`

**v2 已经把 4 拆成 `template`、把 1/2 拆成 `artifact.files_json`/`link`，方向完全正确**。要补的是 **3（`promo` 宣发文案）**——发布物料是真业务（记忆：`发布物料正本.md`），v2 `artifact` 建议加 `promo_json`。

---

## §3 关联关系图（题↔各实体）

### 3.1 总图

```
                        biz_subject（KG 树 3400 节点, id=每3位一层 varchar(20), level 1-5）
                          ▲ 28 个 level1 教材根（数学 100/200/301-312/401-700/800/810, 科学 901-906/910/911）
                          │
          ┌───────────────┼──────────────────────────────┐
          │ knowledge_id  │ anchor_subject_id            │ subject_id
   biz_question_knowledge │                      biz_solution_model_kp
     (12265, M:N, is_primary, source)                    │ (43, bind_type=primary|native|cross)
          │        biz_question_pattern (326 题型目录)     │
          │               │ pattern_id                    │ model_id
          ▼               ▼                               ▼
   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓      biz_solution_model (43 解题模型)
   ┃      biz_question  (15674)              ┃            ▲ model_id
   ┃      PK = 雪花 bigint                   ┃            │
   ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛      biz_question_model (175, is_primary, role)
     │  │   │    │     │      │        │
     │  │   │    │     │      │        └── mother_question_id ──┐ 自引用（5260 行, 1897 母题）
     │  │   │    │     │      │             biz_variation_trace │ (6 行, 🔴 声明的 SSOT 是空的)
     │  │   │    │     │      └── biz_question_free_tag (327) → biz_free_tag (143)
     │  │   │    │     └── biz_question_pitfall (183) → biz_pitfall (193) → knowledge_id
     │  │   │    └── biz_question_ai (1799, uk(question_id, annotate_version))
     │  │   └── biz_question_image (7248, M:N) → image_asset (7214) → 单一 OSS 桶
     │  └── biz_question_block (12236, question_id 即 PK) ← 26 行孤儿
     └── biz_text_content (14025, uk(question_id, content_type) A/E/S)

   三套载体（互不相通）：
   ① biz_shelf_book(70) → biz_shelf_node(3617, 自持树) → biz_shelf_item(16005) ─question_id→ 13046 题
   ② biz_paper(134) → biz_paper_section(169) → biz_paper_question(2017) ────────────→ 1819 题
   ③ biz_book(1) → biz_book_question(893, column_type 书栏目) ────────────────────→ 893 题
   ④ 无载体孤题：30

   录入侧：biz_ingest_job(46) → biz_ingest_job_item(262) ─committed_question_id→ biz_question
   审核侧：biz_review_issue(423) / biz_review_page(227) ─book_id→ biz_shelf_book
   备课侧：biz_course_plan_lesson.paper_slots(json 含 paper_id) / .special_ids(json 含 shelf_book.id)
                                / .book_node_ids(json 含 shelf_node.id)
```

### 3.2 外键实况：**全库零物理外键，一律软引用**

已验孤儿（`LEFT JOIN … IS NULL`）：

| 引用 | 孤儿数 | 判定 |
|---|---|---|
| `biz_question_block.question_id` → `biz_question.id` | **26** | ⚠️ 题被物理删了 block 没删 |
| `biz_paper_question.question_id` → `biz_question.id` | 0 | ✅ |
| `biz_shelf_item.question_id` → `biz_question.id` | 0 | ✅ |
| `biz_question_knowledge.knowledge_id` → `biz_subject.id` | 0 | ✅ |
| `biz_question.mother_question_id` → `biz_question.id` | 0 | ✅ |
| `biz_question_image.asset_id` → `image_asset.id` | 1 | ⚠️ |
| `biz_question.region_code` → `biz_region.code` | — | 🔴 **`biz_region` 表根本不存在** |
| `biz_shelf_node.kp_id` → KG | — | 🔴 死列 + **类型不匹配**（bigint vs varchar(20)） |

### 3.3 题↔考点：基数与质量

| 指标 | 值 |
|---|---|
| 有考点的题 | 12065 / 15674（77%） |
| 一题挂 1 / 2 / 3 个考点 | 11919 / 92 / 54 → **99% 单考点，M:N 没用上** |
| 被引用的考点数 | 322（占 KG 3400 节点的 **9.5%**）→ **KG 铺得远比用得多** |
| 🔴 被引用考点中「非叶子」 | **108 / 322（33.5%）** |
| 挂在 level2（章）的关联 | **7595 / 12265（62%）** |
| `dim1_kp_id` vs `is_primary=1` 不一致 | **34 行** |

**⇒ 对 v2 的直接影响**：v2 的头号设计目标是「学情按考点/专项分轨」（记忆 `ai-bkb-v2-migration`），而 `track.kp_scope_json` 是**学情的分母**。老区的教训是——**分母算不准不是因为没建表，是因为挂载粒度失控（62% 挂到章级、1/3 挂到非叶子）**。v2 必须在 `question_kp` 写入时装**叶子闸**（`NOT EXISTS(SELECT 1 FROM kp WHERE parent_id=?)`）+ **主考点恰一闸**。

### 3.4 题↔母题/变式血缘

| 指标 | 值 |
|---|---|
| 有母题指针的题 | 5260（33.6%） |
| 不同母题数 | 1897 |
| 一母题带 1/2/3/4/5/6 个变式 | 82 / 323 / **1445** / 41 / 3 / 3 |
| 悬空母题指针 / 自引用 | 0 / 0 ✅ |
| `biz_variation_trace` 行数 | **6**（且全是一批 `legacy_backfill`） |
| `mother_source` × `import_source` | `教材配套`×`lecture-pipeline` = 4649（88%）→ **血缘几乎全来自「讲义里例题+对应练习」的天然配对，不是 AI 生成的变式** |

**⇒ 「举一反三血缘」这件事在老区 DB 里其实是「教辅书的例题-练习配对」，不是变式生产记录。** v2 用 `prov_json:{model_id,params,seed}` 表达生成血缘 + `source_kind='model'` 区分，是**更诚实的建模**。

### 3.5 题↔打卡日：**打卡没有独立表，全靠书架三表**（DB + 代码双证）

DB 侧：本地 MySQL 全实例（14 库）扫描**无任何 `punch*` 表**。
代码侧：全仓 grep **`biz_punch` 零命中**，DDL 里无任何 `CREATE TABLE ...punch...`；`punch_day`/`daily_punch` 的全部命中都是 Java 常量 / MCP 文档 / FE 路由，**没有一处是表名**。
权威声明 = `PunchService.java:42-69` 类 Javadoc（「PRD-013 D5，**已定死**」）。打卡的真实落法：

```
biz_shelf_book   book_type='daily_punch'（12 本）
                 style_meta_json = {theme, punchLayout, punchExport, punchReview, netdisks, promo}
   │
   └─ biz_shelf_node   node_type='punch_day'（60 个节点）, name='第1天'…'第10天'
                       parent_id = NULL（🔴 扁平，无「周」层）, seq=1..10
        │
        └─ biz_shelf_item
             ├ kind='module'（187 个）→ content_json = {"type":"oral"|"stepwise", "title":"口算题",
             │                                          "items":[{"q":"26×4＝","a":"104"}]}
             └ kind='question'（50 个）→ question_id → biz_question（正常题引用）
```

实测某本 10 天打卡书：10 个 `punch_day` 节点，每节点 **4 个 item**（=四个模块：开方直取/乘方与绝对值/混合运算/开方解方程）。
`daily_punch` 书的 item 分布：`module` **187** / `question` **50** → 🔴 **打卡题主要不走题库，直接以 `content_json` 的 `{q,a}` 对存在模块里**（题库化程度很低）。

**列与常量对照（代码级）**：

| 概念 | 落法 | 行号 |
|---|---|---|
| 一本打卡书 | `biz_shelf_book.book_type='daily_punch'` | `PunchService.java:43` |
| **一天** | `biz_shelf_node`：`node_type='punch_day'`（常量 `:113`）、`name='第N天'`、🔴 **`seq` 就是天号** | `:47-48`、写入 `:681-694`、查 `:749-752` |
| 天级元数据 | `biz_shelf_node.meta_json` = `{goals:[…], review:{status,issues:[{module,seq,kind,note,resolved}],at}, rotatingTitle?}` | `:658-679`、`:817-845`、`:885-899` |
| 计算模块 | `biz_shelf_item`：`kind='module'`（常量 `:115`）+ **`content_json`** + `seq` | `:49-50`、写入 `:720-732` |
| 轮换位真题 | `biz_shelf_item`：`kind='question'` + `question_id` 引用，seq 续排 | `:57-58`、`:709-719`（`:715` 注释「🔴 只存引用，题面绝不复制」） |
| 整册导出态 / 全书审定 | `biz_shelf_book.style_meta_json.punchExport` / `.punchReview` | `:560-576`、`:859-883` |

**`content_json` 的 6 种 type（全部实证；DB 里只见到 oral/stepwise 两型，其余 4 型代码支持）**：

| type | 结构 | 出处 |
|---|---|---|
| `oral` 口算 / `vertical` 竖式 / `stepwise` 脱式 | `{type,title,items:[{q,a}]}` | `PunchService.java:49-50`、`punch.py:70-74` |
| `combine` 二合一 | `{type:"combine",title,items:[{e1,e2,a}]}` — e1/e2 两个分步算式，a=综合算式（🔴 e2 的另一个操作数不得等于 e1 的结果） | `:52-53`、`punch.py:81-84` |
| `tree` 树状图 | `{type:"tree",title,items:[{l,op1,r,mid,op2,other,side,total,a}]}` — 顶层 `l op1 r = mid`；中层 `mid` 与 `other` 经 `op2` = `total`；`side="l"/"r"` 定中层结果在左/右 | `:53-56`、`punch.py:85-89` |
| `rotating` 轮换位 | **入库形态** `{type:"rotating",title,qids:["雪花号字符串",…]}`（不落 content_json，逐 qid 拆成 `kind=question` item）；**渲染形态** `{type:"rotating",title,blocks:[{qid,rows,answer}]}` | 入库 `punch.py:75-79`、`PunchService.java:706-719`；渲染 `:319-347` |

**🔴 BE 明文不校验 items 结构**（`PunchService.java:54-56`：「本层不校验 items 结构 —— 非 rotating 模块一律原样落 content_json，**题面正确性由产线闸把关**」）。落库唯一加工 = `payload.remove("itemId")`（`:722`）。

**其他关键机制**：
- **题面唯一源 = `block_json`**：轮换位渲染时 `loadBlockJson(qidSet)` 现取现渲（`:322/918`），缺 blockJson 渲「（题面缺失 qid=…）」占位（`:330-333`）；MCP `punch.py:21-22`「题库题永不复制题面文本 … 改题库即改打卡书，零漂移」。
- **G5 答案剥离**：题目卷注入的 `__PAPER_DATA__` 剥掉 `ANSWER_ONLY_ITEM_FIELDS=["a","steps","mid","total"]`（`:131-132`、`:208-231`），并从 rotating 的 `blocks[]` remove `answer`（`:222-229`）。🔴 `:126-127` 注明 **`mid`/`total` 是 tree 型的真答案**，不剥则「查看源代码」即得全卷答案。
- **`upsert_punch_day` 幂等语义 = 整天覆盖**：`itemMapper.delete(...eq(nodeId))` **旧 items 全删重插，不做逐项 diff**（`:697`）；改一天要「先 get 全量 → 改 → 整天回灌」（`punch.py:152`）。
- 4 个 MCP 工具/端点（契约已冻结，`punch.py:24-28`）：`GET /teacher/punch/days`、`GET /teacher/punch/day`、`POST /teacher/punch/upsertDay`、`POST /teacher/punch/review`。
- 产线坑记（`_工厂索引.md:307`）：轮换位引用题库真题，**目标库必须先有那些题，否则 preview 直接 500**（BE `validateQuestionsExist` `:708`）。

**⇒ 对 v2 的意义（三条）**：
1. 这印证了 v2「artifact（册）与 question（题）解耦」的判断——打卡册的题**大部分从来没进过题库**（`module` 187 vs `question` 50）。v2 若要「打卡题也进 kb」，得先决定 `{q,a}` 这种裸对要不要升级成 `question`（有 `blocks_json` 有考点），否则 `track.kp_scope_json` 又会算不出来。
2. **「题面唯一源 = block_json、册子只存 qid 引用」这条纪律是对的，v2 该继承**（v2 `artifact` 与 `question` 之间也应只走 id 引用，不复制题面）。
3. **「答案字段清单式剥离」（`ANSWER_ONLY_ITEM_FIELDS`）是个便宜有效的闸**——v2 出题目卷时同样需要，且老区的教训是 `mid`/`total` 这种「看起来是中间值其实是答案」的字段最容易漏。

### 3.6 题↔备课（间接，靠 JSON 数组软引用）

`biz_course_plan_lesson` 三个 JSON 列：
- `paper_slots` json — `[{slot_seq,name,style,rules,note,paper_id,manual_ready}]`（🔴 注释 GBK 乱码）→ 软引用 `biz_paper.id`
- `special_ids` json — `[biz_shelf_book.id,…]`
- `book_node_ids` json — `[biz_shelf_node.id,…]`

🔴 **JSON 数组里塞外键 = 记忆里 `upsert-plan-wipes-slot-bindings` 事故的根因**（整列重写会抹掉已绑 `paper_id`）。**v2 有多处同构设计**（`track.kp_scope_json`、`exam_model.kp_ids_json`、`artifact.kp_ids_json`、`item.error_kp_json`）——**这些列的写入必须是「读-改-写」而非「整列覆盖」，否则同一个事故会复现。建议 v2 在 §四跨库纪律里补一条。**

---

## §4 枚举与词表实况（`GROUP BY` 真实分布，非代码常量）

### 4.1 题型 `question_type`（字典 `biz_question_type`）

| 值 | 字典标签 | 实测行数 | 注 |
|---|---|---|---|
| 5 | 解答题 | **7602** | |
| 4 | 填空题 | 4681 | |
| 1 | 选择题 | 3001 | |
| 7 | 计算题 | 123 | |
| 2 | 判断题 | 115 | ⚠️ 主表注释说 2=填空，**字典说 2=判断题**——注释与字典冲突 |
| 9 | 实验探究题 | 97 | |
| 6 | 作图题 | 41 | |
| 8 | 证明题 | 11 | |
| 3 | 应用题 | 3 | ⚠️ 主表注释说 3=判断 |

🔴 **`question_type` 主表注释（`1选择 2填空 3判断 4计算 5解答`）与字典 `biz_question_type`（`1选择 2判断 3应用 4填空 5解答 6作图 7计算 8证明 9实验探究`）互相矛盾**。以**字典为准**（`dim2_qtype` 注释「1选择/4填空/5解答/6证明」与字典一致）。
`question_type` vs `dim2_qtype`：**一致 15044 / 不一致 630**。

### 4.2 难度 `dim4_difficulty`（字典 `biz_question_difficulty`）

| 值 | 字典标签 | 实测 |
|---|---|---|
| **0** | **（字典未定义）** | **867** 🔴 越界 |
| 1 | 基础 | 1194 |
| 2 | 中等 | **12916（82.4%）** |
| 3 | 较难 | 638 |
| 4 | 压轴 | 59 |

🔴 **难度维度实质失效**：82% 挤在「中等」，压轴只 59 道。垫片列 `difficult` 与之**漂移 33 行**。

### 4.3 来源 `source_type`（字典 `biz_question_source_type`）

| 值 | 字典标签 | 实测 | 判定 |
|---|---|---|---|
| 3 | 期末 | **9603** | 🔴 **假**：其中 7427 是 `lecture-pipeline` 灌的讲义题，`source_raw` 全是《同步典例考点讲义》 |
| NULL | — | 3748 | |
| 6 | 自编 | 1235 | 可信 |
| 9 | 其他 | 597 | |
| 2 | 模拟 | 181 | |
| 7 | 期中 | 108 | ⚠️ 主表注释说 7=期中，字典说 **7 未定义**（字典里 10=期中） |
| 1 | 中考真题 | 91 | |
| 5 | 单元 | 63 | |
| 4 | 月考 | 48 | |

字典完整值域（11 个）：`1中考真题 2模拟 3期末 4月考 5单元 6自编 9其他 10期中 11质检调研 12同步练习 13竞赛`。
🔴 **有 `12 同步练习` 这个正确值可用，但 7427 道讲义题却打了 `3 期末`。**
另有一套**并行且冲突**的字典 `biz_question_source`（8 值：`1教材/同步 2质检/调研 3竞赛 4中考真题 5模拟卷 6自编/原创 7期中 8期末`）——**两套来源字典编码互不兼容**（`3` 在一套里=期末、在另一套里=竞赛）。

### 4.4 状态与可见性

| 列 | 实测 | 判定 |
|---|---|---|
| `biz_question.status`（0草稿/1发布/2软删） | **全部 1** | 🔴 单值，软删机制未启用 |
| `biz_question.is_public` | 1=14024 / 0=1650 | ✅ **真正在用的上架闸** |
| `biz_question.label_status`（字典 `biz_question_label_status`：0AI未处理/1AI已标/2已审核/3争议） | 0=14140 / 1=1483 / **2=51** / 3=0 | 人审 51 道；「争议」态从未使用 |
| `biz_question.annotate_status`（0未标/1已标全/2部分） | 0=14140 / 1=1534 / 2=0 | 「部分」态从未使用 |
| `biz_question_ai.label_status` | **全 1** | 1799 条 AI 标注零人审 |
| `biz_ingest_job.status` | 只 `DONE` / `FAILED` | 三个中间态（PENDING/EXTRACT_ING/SPLIT_ING）**不落库** |
| `biz_ingest_job_item.item_status` | `pending`237 / `committed`25 | 🔴 **91% 拆出来的题从未入库**（勾选制的真实转化率） |
| `biz_review_issue.status` | 待处理/已改/搁置 | |

### 4.5 KG 维度字典化实况

`sys_dict_type` 里 `biz_*` 前缀共 **20 个**：

**教材维度（5 个，用于 `biz_subject` level=1 与 `biz_paper_category`）**
| 字典 | 值域 |
|---|---|
| `biz_edu_subject` | 1数学 2科学 3语文 4英语 |
| `biz_edu_stage` | 1小学 2初中 3高中 |
| `biz_edu_grade` | 1-9 年级 + 10高一 11高二 12高三 |
| `biz_edu_volume` | 1上册 2下册 |
| `biz_edu_edition` | 1浙教 2人教 3北师大 4苏教 |

🔴 **这 5 个字典码只写在 `biz_subject` 的 level=1 行上**：全表 3400 行只有 **25 行**有值（level=1 共 28 行，**3 行漏填**：`810 四年级数学·人教四上（课内）`、`910 科学五年级上(教科版)`、`911 科学六年级上(教科版)`）。level 2-5 节点**不带任何维度码**，只能靠 id 前缀（每 3 位一层）回溯到根。

**题目标注维度（5 个，`biz_anno_*`，全部为英文 code）**
| 字典 | 值域 | 落库情况 |
|---|---|---|
| `biz_anno_COG` 认知层级 | UNDERSTAND了解 / COMPREHEND理解 / MASTER掌握 / APPLY灵活运用 | 🔴 **无任何列使用** |
| `biz_anno_METHOD` 思想方法 | SHU_XING数形结合 / FEN_LEI分类讨论 / HUA_GUI化归转化 / FANG_HAN方程函数 / JIAN_MO数学建模 / DAI_DING待定系数 / TE_SHU特殊与一般 / GUI_NA数学归纳 | 🔴 对应列 `biz_question_ai.math_thoughts` = **死列** |
| `biz_anno_ERROR` 易错陷阱 | CONCEPT概念混淆 / CLASSIFY分类不全 / CALCULATION计算失误 / READING审题偏差 / EXPRESS表达不规范 / IMPLICIT隐含遗漏 / THINKING思路缺失 | 部分用于 `biz_question_ai.hard_points`（161 行），**但存的是中文标签不是 code** |
| `biz_anno_LITERACY` 核心素养 | ABSTRACT / OPERATION / REASONING / SPATIAL_VIEW / GEOMETRIC_VIEW / DATA_VIEW / MODEL_VIEW / APPLICATION / INNOVATION | 🔴 无列使用 |
| `biz_anno_SCENE` 情境 | PURE_MATH / REAL_LIFE / CULTURE / CROSS_SCI | 部分用于 `biz_question_ai.scenario`，**同样存中文** |

**⇒ 「KG/卷库维度字典化」这件事只完成了一半**：字典表建全了（20 个），但**多数字典没有任何列消费**，且消费的列存的是**中文标签而非字典 code**——字典化没落地。

#### 字典码在哪一层解析 → 🔴 **BE 只发码，FE 查字典**（代码实证）

**BE 侧不转 label**：
- `ShelfService.enrichSubjectDims`（`ShelfService.java:154-176`）只把 `biz_subject` 的结构列**原码**贴到列表行，字段名带 `Code` 后缀：`subjectCode/stageCode/gradeCode/volumeCode/editionCode`（`:170-174`），**没有任何 `*Name`/`*Label`**。
- 在 `ruoyi-book` 全模块 grep `DictUtils|refreshCache|dictDataService|getDictLabel`：**零命中**——业务模块完全不碰字典服务。
- 唯一的 BE 侧 label 是**手抄镜像 enum**，且自己声明不是 SSOT：`domain/enums/BizQuestionType.java:3-12`
  > 「🔴 唯一事实标准 = `sys_dict_data` 的 `biz_question_type`（超管可改）。本枚举是后端组卷/分组装 section 标题处用的镜像……**字典改了须同步这里**。跨层同源镜像：题管线 = `teacher-mcp/app/dicts.py QUESTION_TYPE`；前端 = `book-ui/src/store/dict.ts DICT_QUESTION_TYPE`」

**FE 侧真查字典**：`book-ui/src/store/dict.ts`
- `:5-11` 组件头「把 sys_dict 的枚举作为 SSOT 拉到前端缓存，不再各组件硬编码 `{1:'选择题',…}`」
- `:37-62` `load(dictType)` → `GET /system/dict/data/type/{dictType}` + 进程内缓存 + 防并发；`:71-76` `label(type,value)`（未命中回落原值）；`:85-94` `tagType()` 读 `list_class` 驱动徽标颜色
- `:100-119` 常量表含 `DICT_EDU_SUBJECT/STAGE/GRADE/VOLUME/EDITION`、`DICT_PAPER_TYPE`
- `:103-105` 埋了坑提示：`biz_question_source` 与 `biz_question_source_type` **是两套不同约定，别混（`source_type` 列只认后者）**

**MCP 侧也是硬编码镜像**（不查字典）：`teacher-mcp/src/teacher_mcp/domains/dicts.py:1-6`（文件头自认「后续加 `list_dict` 工具运行时动态拉取，替代本文件」）；`:19-29` 两套 source 的陷阱注释；`:35-54` `biz_anno_*` 受控词表 + `is_valid_anno`。
KG 锚定走**直连 DB 查表**返 `{id,name,level,parent_id,is_leaf}`（`shared.py:282-311`），🔴 `:292` 注释「**叶子 = 无子节点（is_leaf），别按 level 判**」——**老区自己早就知道 level 不等于叶子**（正对应 §6.3 的 `dim1_kp_id` 注释谎言）。

**⇒ 老区实际维护着「同一个词表的 4 份拷贝」**：`sys_dict_data`（SSOT）+ BE enum 镜像 + FE store 常量 + MCP 硬编码字典。**已经漂移了**：
- `收敛DDL-2026-07.sql:404` 列注释 `1选择 2填空 3判断 4计算 5解答` **与字典 `1选择 2判断 3应用 4填空 …` 冲突**（填空/判断码是反的）；FE `views/ingest/review.vue:208` 留着修复注释「修旧硬编码『填空=2』错值（字典填空=4）」——**这个漂移真的伤过人**。
- 难度：字典 4 档 `1基础/2中等/3较难/4压轴`，MCP `ingest_question` 文档却写 **3 档** `1基础/2提升/3压轴`（`data_qbank.py:302`）。

**缓存刷新铁律**（多处重复出现，说明踩过）：`DELETE /system/dict/type/refreshCache`（`SysDictTypeController.java:117-118`）；
`收敛DDL-2026-07.sql:1166`「🔴 prod 手动执行 + 执行后**必刷字典缓存**（或重启 BE）」、`dev-fix/2026-07-05-….sql:5`「否则 FE 拿旧缓存」、`V913__/V914__` 同款告警。

**⇒ v2 的正确选择**：v2 用 `CHECK(… IN (…))` 内联值域、无独立字典表、无缓存层——**一份词表一个地方，从根上消灭「4 份拷贝 + 刷缓存」这一整类问题**。代价是改值域要改 schema，但对单人本地库这是正确取舍。

**其余字典**：`biz_question_type`(9) / `biz_question_difficulty`(4) / `biz_question_source_type`(11) / `biz_question_source`(8) / `biz_question_discipline`(1物理2化学3生物4地学5综合探究，🔴 对应列 `discipline` **死列**) / `biz_question_label_status`(4) / `biz_question_annotate_status`(3) / `biz_question_assessment_type`(**10 个中文值，词表本身有价值**) / `biz_paper_type`(1单元2月考3期中4期末) / `biz_term_tag`(上学期/下学期/寒假/暑假)。

### 4.6 其他有价值的真实词表（v2 可直接抄）

| 词表 | 值 | 用途 |
|---|---|---|
`biz_question_assessment_type` | 概念辨析 / 直接计算 / 公式套用 / 性质判定 / 应用建模 / 探究归纳 / 证明推理 / 作图 / 纠错 / 阅读理解迁移 | **考察类型 10 型**，比「题型」更有教学意义 |
| `biz_solution_model.category` | 数轴 / 方程 / 线段 / 角 / 动点 / 几何 / 函数 / 数轴与绝对值 / 数轴动点问题 / 绝对值方程 / 有理数应用 / 相交线与平行线 / 列代数式与方程建模 / 列代数式与数论说理 / 动角与角的和差 / 通用（16 类） | 解题模型大类 |
| `biz_solution_model.difficulty_tier` × `freq_band` | tier 1-4 × freq 1-3 | **双旋钮**（难度阶 × 考频），记忆 `c102-variant-upgrade-strategy` 的「模型表驱动」正本 |
| `biz_book_question.column_type` | 刷基础 / 刷提升 / 刷难关 / 刷中考 / 刷章测 / 刷易错 / 刷素养 / 中考新考向备训 / 巩固提升 / 知识精讲 / 习题精练 | 教辅栏目 = 天然难度/用途信号 |
| `biz_shelf_node.node_type` | kp / qtype_group / unit / module / training / **punch_day** / section / tier / lecture / chapter / sec / topic / test / appendix（14 个自由值） | ⚠️ 注释明说「不设枚举闸」，结果 `section` 和 `sec` 同义并存 |
| `biz_shelf_item.override_json.role` | example（典型例题）/ practice（对应练习） | 题在书里的角色 |
| `biz_question_image.role` | stem / figure / analysis / 题图 / 选项图 / 辅助图 | ⚠️ 中英混用，v2 别抄这个混乱版 |

---

## §5 🔴 互通视角

> 前提（[需求总纲.md](需求总纲.md) §一 + §十二）：**运行时零交互不变**（v2 不调 book-server、不连它的库），
> 只要求**一道题能导出/导入过去**。所以互通 = **交换格式（JSON 单题信封）**，不是合库、不是同步、不是外键跨库。

### 5.1 互通必需的最小集（13 字段）— 交换一道题必须携带

| # | 语义 | 老区来源 | v2 来源 | 类型约定 | 备注 |
|---|---|---|---|---|---|
| 1 | **题 id** | `biz_question.id`（雪花 bigint） | `question.id`（TEXT） | 🔴 **一律字符串** | JSON double 会截尾（记忆 `create-paper-snowflake-truncation-trap`）。**互通信封里 id 必须带引号** |
| 2 | **题面块流** | `biz_question_block.block_json` | `question.blocks_json` | 见 §2.4 转换表 | ⚠️ 老区 3462 题**没有 block**，只能退化用 `stem_text`（纯文本→单个 text 块） |
| 3 | **答案块流** | `answer_block_json`(891) **优先**，否则 `biz_text_content(content_type='A')`(8450) | `answer_blocks_json` | 同上 | 🔴 **必须两路都读**，只读 block 层会丢 88% 的答案 |
| 4 | **解析块流** | `analyze_block_json`(891) 或 `biz_text_content(content_type='E')`(5542) | `analysis_blocks_json` | 同上 | |
| 5 | **题型** | `question_type`（tinyint，字典 `biz_question_type`） | `qtype`（TEXT 中文名） | 🔴 **交换时一律传中文标签**（选择题/填空题/…） | 不传数字码——`2` 在主表注释和字典里含义不同（§4.1） |
| 6 | **难度** | `dim4_difficulty`（0-4） | `difficulty`（1-5） | 传整数 + **值域声明** | 🔴 **值域不同**：老区 0-4（0=未定）、v2 1-5。互通需映射表，且 0 必须映射成 NULL 而非 0 |
| 7 | **主考点名** | `biz_question_knowledge(is_primary=1)` join `biz_subject.name` | `question_kp(is_primary=1)` join `kp.name` | 🔴 **传考点「名 + 全路径」，不传 id** | 见 §5.4 有损点② |
| 8 | **副考点名** | 同上 `is_primary=0` | 同上 | 名数组 | |
| 9 | **图片** | block 内 `image.url` + `biz_question_image` | `blocks_json` 内 `figure.asset` + `asset` 表 | 🔴 **传「可下载 URL + 内容 hash + width」** | 见 §5.4 有损点① |
| 10 | **排重键** | `stem_hash`（char32 MD5，归一化后） | `match_key` | 传字符串 + **归一化算法版本** | 🔴 两边必须用**同一套归一化规则**，否则 hash 对不上等于没有 |
| 11 | **来源原文** | `source_raw`（`书 / 章 / 栏目` 用 ` / ` 分隔） | `prov_json.source_raw` | 传原字符串**不解析** | 老区 3391 个不同值，是最有用的溯源信息 |
| 12 | **来源类别** | `import_source`(14 值) | `source_kind`(scan/manual/model/pipeline) | 传两个：v2 四分类 + 老区细分值 | 🔴 **不要传 `source_type`**（§4.3 已污染） |
| 13 | **自由标签** | `biz_free_tag.name` via `biz_question_free_tag` | `tags_json` | 名数组（丢 `position`） | |

**信封建议形状**（供契约层定稿参考）：
```json
{ "envelope": "question-exchange/v1",
  "origin": "beikeban" | "v2",
  "id": "2069819158257750018",
  "blocks": [...], "answer_blocks": [...], "analysis_blocks": [...],
  "qtype": "选择题", "difficulty": 2, "difficulty_scale": "0-4" | "1-5",
  "kp_primary": {"name":"有理数的大小比较","path":["数学七年级上(浙教2024)","从自然数到有理数","有理数的大小比较"]},
  "kp_others": [...],
  "assets": [{"url":"https://…","hash":"<sha256|md5>","width":45,"role":"stem"}],
  "match_key": "9bf7ae9d…", "match_key_algo": "stem-normalize/v1",
  "source_raw": "三上数学同步典例考点讲义（人教版） / 第四单元 … / 【考点】课后小测",
  "source_kind": "pipeline", "origin_pipeline": "lecture-pipeline",
  "tags": ["分类讨论","数形结合"] }
```

### 5.2 只在一边有意义的字段（不进最小集，单边保留）

**只在备课帮有意义**（v2 不要）：
`is_public`（公共题库审核闸——v2 单人无此概念，对应 `status='上架'`）、`create_by`/`create_user`/`update_by`（多用户/若依租户）、`create_dept`、`biz_question_basket`/`favorite`/`folder`/`note`（多用户协作，全空）、`biz_paper_*` 整套（v2 不做在线试卷实体，出卷是 agent 本地渲染）、`biz_export_record`（服务端导出任务队列——v2 导出在本地）、`base_score`（分值属于卷不属于题）、`used_count`（认证计数）。

**只在 v2 有意义**（备课帮吃不下）：
`source_kind` 的 `model`/`pipeline` 区分（老区无对位，`import_source` 只是管线名）、`prov_json.{model_id,params,seed}`（生成血缘——老区 `variant_relation` 存的是书栏目标签）、`asset.rel_path` 相对路径（老区全绝对 URL）、`criterion` 判据表 / `todo` / `skill_log`（老区无对位）、`cause_deposit` 批改沉淀（老区批改线不落库）、`track`/`batch`/`item` 整个批改库（老区完全没有）。

### 5.3 v2 该补的字段（老区有价值、v2 目前没有）

按价值排序：

| 优先 | 补什么 | 老区证据 | 理由 |
|---|---|---|---|
| 🔴 P0 | **`blocks_json` 加 `option` 块型** | `option` 块 5187 个 / 1373 道题，其中 **313 个选项含图** | v2 现无 option 块型，选择题选项无处可放。不补 = 互通时 1373 道选择题全部降级成纯 md 文本，含图选项直接烂。**这是 v2 块流最大的功能缺口** |
| 🔴 P0 | **`figure` 块加 `width`**（**整数 1-100，= 容器宽百分比**；`align` 可省，全库单值 center） | 5467 个 image 块 **100% 带 `width`**；校验器强制 1-100 整数（`BlockJsonValidator.java:119-136`） | 「图在卷面占多宽」是真实生产数据，删了以后每次出卷都要重新猜排版。🔴 且 v2 **必须定唯一缺省常量**——老区四层缺省不一致（45/40/40/100，§2.4c） |
| 🔴 P0 | **`blocks_json` 加 schema 版本位** | 老区有 `v`（虽从未 bump） | 改结构要有退路。建议 `{v:1,blocks:[…]}` |
| 🟡 P1 | **`question` 表加「考察类型」** | 字典 `biz_question_assessment_type` 10 个中文值（概念辨析/直接计算/公式套用/性质判定/应用建模/探究归纳/证明推理/作图/纠错/阅读理解迁移） | 比「题型」更有教学意义；出卷时「同一考点换考察类型」= 天然变式方向。词表现成可抄 |
| 🟡 P1 | **题型目录表**（对位 `biz_question_pattern`） | **326 条题型 + 868 条题↔题型关联，锚在 133 个考点上**。样例：`平方根的概念及性质`@`100003001001` | v2 完全没有对位表（`qtype` 只是「选择/填空」这种**形式**分类）。**「题型（解题 pattern）」是老区实打实沉淀的 326 条资产**，且它是「按专项分轨」的天然抓手——比考点更贴近「这一类题」 |
| 🟡 P1 | **`exam_model` 补 `trigger_feature` + `action_conclusion` 双列** | `biz_solution_model` 43 条，两列 100% 有值，都是长文本招式描述 | v2 `exam_model` 只有 `name`/`dsl_ref`/`params_json`/`note`。老区「**什么题面信号触发** → **做什么动作得什么结论**」这个二元组是模型可用的关键，塞进 `note` 会丢结构 |
| 🟡 P1 | **`ingest_batch` 补 `answer_mode` + `commit_mode`** | `from_source`/`ai_solve`/`stem_only` × `review`/`direct` | 「答案从哪来」×「要不要过审」是录入的两个真旋钮，老区实测都在用 |
| 🟡 P1 | **`artifact` 补 `promo_json`** | `style_meta_json.promo = {title, desc}` | 发布物料（小红书标题+文案）是真业务，v2 `artifact` 无处安放 |
| 🟡 P1 | **`artifact.link` 改成数组** | `style_meta_json.netdisks = [{url, code, note, provider}]` | v2 现在是单个 `link` TEXT。老区实测带 `code`(提取码)/`note`(含题目22页+解析22页)/`provider`，且「一册一条链接双号共用」的口径需要 `note` |
| 🟢 P2 | **`ingest_item` 吸收 `confidence` 数值分级** | `biz_shelf_item.confidence` 0-100，95.9% 覆盖，>=90速过/60-89常规/<60重点审 | v2 `gates_json` 是布尔闸集合，缺一个**连续置信度**做审核优先级排序 |
| 🟢 P2 | **`question_kp` 保留 `source`** | `source` = `U`(用户) / `书` | 区分「人挂的」和「管线挂的」，回头清洗时有用。⚠️ 但**别放进唯一键**（老区 `uk_qk_src` 的错，会产生同题同考点两行） |
| 🟢 P2 | **`error_cause` 补 `trigger_feature`/`typical_error`/`correction`/`severity_tier`** | `biz_pitfall` 的科学扩展四列（只 10 行有值但设计好） | 「什么信号会踩这个坑 / 典型错误动作 / 纠正要点 / 严重度 1-3」——比只有 `desc` 一列可操作 |

### 5.4 互通有损点（必须预先认账）

| # | 有损点 | 详情 | 处置 |
|---|---|---|---|
| ① | **图片资产** | 老区 **7248 个图绑定全在单一 OSS 桶** `ai-book.oss-cn-hangzhou.aliyuncs.com`，block 里是**绝对 URL**；v2 是 `asset.hash` + **相对路径**。且老区靠 `oss_url` **字符串**跟 block 对账（63 道题索引已漂移） | 🔴 互通必须**搬字节**：导出时下载图 → 算 hash → 落 v2 `资产/`；导入备课帮时上传到它的 OSS 换新 URL。**信封里必须同时带 URL 和 hash**，两边各认一个 |
| ② | **考点 id** | 老区 `biz_subject.id` = `varchar(20)` 每 3 位一层的**结构化编码**（`100003001001`），语义绑定它自己的树；v2 `kp.id` = 独立 TEXT，树从零铺 | 🔴 **绝不传考点 id**，传**考点名 + 全路径名数组**，落地时用 v2 的 `resolve(名/别名→叶子)` 原语重挂。挂不上→进 `review_ticket(kind='kp低置信')`。**老区 `kp_anchor_json` 的 `stage`/`fallback`/`confidence` 三元组正是为这个场景设计的，直接抄** |
| ③ | **雪花 id** | 老区题 id 全是 19 位雪花 bigint，超过 JS `Number.MAX_SAFE_INTEGER` | 🔴 信封里 **id 必须是 JSON 字符串**。v2 已定「一切 id 走 TEXT」，导入时**保留老区 id 作为 `prov_json.origin_id`**（可回查），v2 自己另发 id |
| ④ | **字典码依赖对方字典表** | `question_type` / `dim4_difficulty` / `source_type` / `biz_edu_*` 全是 tinyint 码，语义只在 `sys_dict_data` 里；且**同一码在两套字典里含义冲突**（§4.3） | 🔴 **交换一律传中文标签不传码**。难度额外带 `difficulty_scale` 声明值域（0-4 vs 1-5） |
| ⑤ | **表格** | 老区表格是 `md` 里的 GFM 管道表（74 份），v2 有独立 `table` 块 | 老区→v2 **保留在 text 块**（要求 v2 渲染器吃 GFM 表格），不做自动解析（解析失败会毁数据）。v2→老区：`table` 块**序列化成 GFM 表**塞进 `md` |
| ⑥ | **多列布局** | 老区 `rows/cells` 能表达横排；v2 扁平流不能 | 实测**只 16 道题真用了多列**（非选项）→ **认账丢失**，导入时降级成多个连续块 |
| ⑦ | **答案缺失** | 老区 **7226 / 15674（46%）题一点答案都没有** | 🔴 导入 v2 时**必须落成 `status='草稿'`**，不能直接上架。v2 若反向导出给备课帮，无答案的题也要标记 |
| ⑧ | **`option` 的 label 可能跳号** | 需求总纲 Q-15 悬而未决：老区抽取层**自动规整**成连续标号，v2**如实报 FAIL 交人审** | 🔴 **互通时会撞上**：从老区导入的选项 label 可能已被规整过（掩盖了漏抽）。建议信封里带 `label_normalized: true/false`。**这是 Q-15 的一个新论据：老区的自动规整让「导入的题是否漏抽」变得不可验证 → 支持 v2 现做法（如实 FAIL）** |
| ⑨ | **`⟦c:#RRGGBB⟧` 颜色方言** | 老区 `biz_shelf_item.explain_json.text` 用自造颜色标记 | 只影响讲义（2712 个 explain 块），题目层不受影响。v2 若要吃老讲义需实现方言解析器；**建议不吃**（v2 讲义线从零起） |

### 5.4b v2 → 备课帮 方向的硬约束（导出时必须满足，否则 BE 直接 400）

`BlockJsonValidator` 是**入库必过闸**（`QuestionServiceImpl.java:963/1094/1145`、`IngestServiceImpl.java:527`），所以 v2 往备课帮送题时块流必须：

| 约束 | 后果 |
|---|---|
| 块型只能是 `text` / `image` / `option` | 出现 `table` / `figure` / 任何第四型 → **`throw "未知 type="`** |
| `image` 必须同时有 `url`(string) + `width`(**整数 1-100**) + `align`∈{left,center,right} | 缺一个或 width 越界/非整数 → 抛错。v2 的 `figure.asset`(hash) **必须先换成可访问 URL** |
| `option.content` 内**只许 text/image，不许再嵌 option** | leafOnly=true |
| `text` 必须有 `md` 键 | v2 的 `text` 键名要改成 `md` |
| 外层必须是 `{v, rows:[{cells:[…]}]}` | v2 扁平数组要包成「每块一 row 一 cell」；选项要合并进同一个 row |

⚠️ 另一条：`POST /teacher/format/to-block` **自检不过不报错，降级返回 `degraded:true` + `degradeReason`**（`FormatController.java:45-55`），`BlockJsonConverter` 也是「对外永不抛」的逃生仓设计。
**⇒ 走 `format` 端点转换时必须检查 `degraded` 标志**，否则会静默拿到「整段兜成一个 text 块」的降级结果（选项、小问、图全丢），而接口返回 200。

### 5.5 互通的三条纪律（建议写进 v2 数据结构.md §四）

1. **互通是文件级、单向、按需**：`v2 →(导出信封 JSON)→ 人工/脚本 →(导入)→ 备课帮`，反向同理。**永不建实时桥、永不跨库外键**（守住需求总纲 §一「运行时零交互」）。
2. **id / 考点 / 图片三样一律「重新落地」**：老区 id 只作 `prov_json.origin_id` 留痕；考点走 `resolve` 重挂；图片搬字节重算 hash。**任何一样直接复用对方的都是埋雷。**
3. **一切枚举传中文标签 + 带值域声明**，禁传数字码（老区已有两套冲突的来源字典 + 主表注释与字典矛盾 + 难度值域不同，三重坑）。

---

## §6 死列与历史包袱清单（v2 明确不继承）

### 6.1 死列（0 行有值）— 共 **31 个**

| 表 | 死列 | 本来想干什么 |
|---|---|---|
| `biz_question` (17) | `stem_embedding` / `embedding_model` / `embedding_updated_at` | 🔴 **向量检索三件套整组从未启用** |
| | `reviewed_by` / `reviewed_at` | 人审留痕 |
| | `aux_tags` | 辅标签（被 `biz_free_tag` 取代） |
| | `remark` | |
| | `answer_img_url` / `explain_img_url` | 答案/解析渲染图缓存 |
| | `file_bin_url` | 注释自陈「笔迹层,不实现」 |
| | `dim3_skill` / `dim5_structure` | 注释自陈「已撤维恒空」/「冻结」 |
| | `exam_paper_id` / `exam_paper_name` | 出处试卷冗余 |
| | `source_ref` / `star_level`(8行) / `topic_tag` | 🔴 **PRD-C-213 三件套整组落空** |
| | `discipline` | 科学分科（库里有 1150 道科学题却一条没标） |
| `biz_question_ai` (4) | `math_thoughts` | 有 8 值字典 `biz_anno_METHOD`，零消费 |
| | `modeling_frame` / `conditions` | 建模骨架 / 条件小问 |
| | `reasoning` | agent 抽取依据 |
| `biz_solution_model` (3) | `topic_id` / `mother_question_id` / `page_anchor` | gold 模型的专题/母题/页锚 |
| `biz_question_pattern` (2) | `description` / `book_id` | 题型说明（326 条题型**全无说明**） |
| `biz_book_question` (1) | `book_difficulty` | 🔴 **868 行非 NULL 但全是空串**（假装有值） |
| `biz_shelf_book` (1) | `source_job_id` | 录入直出书溯源（PRD-001 D6） |
| `biz_shelf_node` (1) | `kp_id` | 🔴 节点 KG 锚（D8）——且 `bigint` vs `varchar(20)` **类型都不匹配，注定写不进** |
| `biz_paper` (3) | `region` / `school` / `exam_type` | |
| `biz_variation_trace` (3) | `variation_degree` / `similarity_band` / `same_source` | 变式程度/相似带/是否真同考点 |
| `biz_ingest_job` (2) | `create_dept` / `update_by` | |
| `biz_book` (2) | `cover_url` / `remark` | |
| `biz_subject` (3) | `create_by` / `update_by`（**非 NULL 但全空串**）/ `remark` | |

### 6.2 单值列（有值但去重基数=1，无信息量）— 共 **12 个（题目主线）**

`biz_question.version`(1010) / `.annotate_version`(0) / `.status`(1) / `.is_collected`(1)
`biz_question_block.v`(1)
`biz_question_ai.annotate_version`(1) / `.label_status`(1) / `.verify_kind`(LLM核验)
`biz_question_model.source`(AI) / `biz_question_pattern.source`(书) / `.status`(0)
`biz_question_pattern_rel.is_primary`(1) / `.source`(书) / `biz_question_pitfall.source`(book)
`biz_book_question.container_type`(section) / `biz_ingest_job_item.need_review`(0)
`biz_paper.status`(0) / `.sort`(0) / `biz_pitfall.status`(0) / `biz_subject.status`(0) / `.mine_visible`(1)

### 6.3 三条注释谎言（**最危险的包袱**，v2 必须靠闸而非注释）

| 列 | 注释声明 | 实测 | 后果 |
|---|---|---|---|
| `biz_question.dim1_kp_id` | 「主考点(biz_subject **叶子**)」 | 322 个被引用考点里 **108 个有子节点**；关联行 **62% 挂在 level2（章）** | 学情按考点分轨算不出正确分母 |
| `biz_question.subject_id` | 「科目锚 **level1**」 | **2592 / 15674 行不是 level1** | 按教材筛题会漏 |
| `biz_question.mother_question_id` | 「派生缓存，**SSOT 在 trace**」 | `biz_variation_trace` **只有 6 行**，而本列有 5260 行 | 声明的事实源是空的，谁按注释去 trace 查血缘就查空 |
| `biz_question.variant_relation` | 「数值变式/情境变式/结构变式/同源」 | 实际 25 个值全是 `对应练习1`/`变式训练2`/`精练题01` 等**教辅栏目标签** | 拿它当变式算子会得出错误结论 |
| `biz_question.question_type` | 「1选择 2填空 3判断 4计算 5解答」 | 字典 `biz_question_type` = 「1选择 **2判断 3应用 4填空** 5解答…」 | 🔴 **注释与字典对 2/3/4 的定义完全冲突** |
| `biz_question.import_source` | 「main主书/kuangk狂K/textin」 | 14 个实际值里**这三个只有 `main` 出现** | |
| `biz_question.mother_source` | 「textbook书原生/ai反推」 | 实际是中文 `教材配套`/`同书母题` | |
| `biz_question_knowledge.source` | 「U=用户/S=标准库/AI=AI锚定」 | 实际只有 `U` 和中文 `书` | |
| `image_asset` 表注释 | 「**misikt** 资源 URL → 本地路径映射」 | misikt 是更早的前身系统，此表现在服务于整个题库 | 改用途没改注释 |

**🔴 4 处 GBK 乱码注释**（写 DDL 时经过了 GBK 通路，与记忆 `ps-redirect-mysqldump-trap` 同源）：
`biz_text_content` **表注释**（`棰樼洰涓夎?绱犻暱鏂囨湰澶栫疆`）、`biz_paper.paper_kind`（`1æ™®é€š 2å¤‡è¯¾å·`）、`biz_shelf_book.is_public`、`biz_course_plan.default_paper_slots`、`biz_course_plan_lesson.paper_slots`。
**⇒ v2 建库脚本必须全程 UTF-8，且建完 `SELECT` 一遍注释目检。**

### 6.4 结构性包袱（v2 已避开，记录以备回查）

| 包袱 | 老区实况 | v2 现状 |
|---|---|---|
| **一个正文三处存** | `stem_text` + `block_json` + `biz_text_content`，且**答案的真事实源在第三处**（8450 vs 891） | ✅ 三列同构块流收进 `question` 一表 |
| **兼容垫片不拆** | `difficult` vs `dim4_difficulty`（漂移 33 行）、`question_type` vs `dim2_qtype`（漂移 630 行） | ✅ 无垫片 |
| **反规范化计数漂移** | `biz_free_tag.use_count` **143 个里 74 个错（51.7%）** | ✅ v2 「学情没有表，现算」同一哲学 |
| **混合 ID 方案** | `biz_paper` 118 行小自增 + 16 行雪花，中途切换未回填 | ✅ 「一切 id 走 TEXT」 |
| **软删机制形同虚设** | `status` 全 1，删题走物理 DELETE，留下 26 行孤儿 block | ⚠️ v2 `status` 有「退役」态，**但要有闸保证删 question 时清 question_kp** |
| **JSON 数组塞外键** | `paper_slots`/`special_ids`/`book_node_ids` 整列覆盖会抹绑定（已出事故） | ⚠️ **v2 有 4 处同构设计**（`kp_scope_json`/`kp_ids_json`×2/`error_kp_json`）→ 建议补「读-改-写」纪律 |
| **字典化只做了一半** | 20 个 `biz_*` 字典表建全，但 `biz_anno_COG`/`LITERACY` 零消费，`METHOD` 对应列是死列，消费的列**存中文标签而非 code** | ✅ v2 用 `CHECK(… IN (…))` 内联值域，无独立字典表——**更适合单人本地** |
| **多用户协作表全空** | `basket`/`favorite`/`folder`/`note`/`paper_basket` 五张表 0-52 行 | ✅ v2 不建 |
| **一次设计 26 个 DNA 维度** | `biz_question_ai` 26 列 / 覆盖 11.5% / 4 死列 3 近死列 3 单值列，最高覆盖列也只 65%×11.5%=7.5% | ✅ v2 只留 `exam_model.{dsl_ref,params_json}` 两个口子 |
| **难度维度未分化** | 82.4% 挤在「中等」，压轴 59 道，且 867 行越界值 0 | ⚠️ v2 `difficulty 1-5` **必须配判档 rubric**，否则重蹈 |
| **考点铺得比用得多** | KG 3400 节点，只 322 个（9.5%）被题引用 | ⚠️ v2 `kp.status` 有「未铺」态，是好设计——但要防「铺了不用」 |

---

## 附：本次考古的原始产物

脚本与全量输出落 scratchpad（非项目目录）：
`C:\Users\25606\AppData\Local\Temp\claude\d--workplace-ai-bkb\10dedbaf-cfe0-4113-ae5f-e04875893b63\scratchpad\`
- `dig01_tables.py` → 105 表清单
- `dig02_scan.py` → 全实例 14 库扫描（证明无 punch/sku/grading 表）
- `dig03_cols.py` → `cols_dump.txt` 41 表全字段 + 索引
- `dig04_usage.py` → `usage.txt` 每列 nonnull/nonempty/distinct 统计（死列判定）
- `dig05_enums.py` → `enums.txt` 枚举分布 + 字典明细 + 孤儿检查
- `dig06_samples.py` → `samples.txt` block_json / styleMeta / DNA / 录入 JSON 真实样例
- `dig07_coverage.py` → `coverage.txt` 覆盖矩阵 + ID 方案 + 一致性检查
- `dig08_extra.py` / `dig10.py` → 乱码注释清单、source_type 污染取证
- `dig09_blockfull.py` → `blockfull.txt` **12236 份 block_json 全量扫描**（块型全集/网格用量）

代码侧证据由并行考古补齐（`BlockJsonValidator` / `BlockJsonConverter` / `FormatController` / `QuestionBlockRender` / `blockSchema.ts` / `ShelfService` / `PunchService` / `store/dict.ts` / `teacher-mcp` 工具），已内联到 §1.2 / §2.1 / §2.4b / §2.4c / §2.6 / §3.5 / §4.5，逐条带 `路径:行号`。

⚠️ **未核实清单**（不许当事实用）：
- **prod 库（阿里云 RDS）的表结构与 dev 是否完全一致** —— 未连 prod。本文全部行数/分布来自 dev。
- **prod 是否存在 dev 没有的表** —— dev 侧 105 表已穷举；prod 侧未核。（punch 已排除：DB + 代码双证无专表。）
- **PRD-A-015 §10.1 的 PRD 正文原文** —— `codeplace-A/prd/` 下已无 PRD-015 目录（应在 `_归档-2026-07/`，未展开）。§2 的 schema 结论取自 DDL 注释 + Java validator + FE 契约三处互证，未读到 PRD 原文。
- **`题目结构考古-契约层.md`** —— MCP/HTTP 完整出入参口径（本文只覆盖与 block_json/styleMeta/punch/字典相关的那部分接口）。
