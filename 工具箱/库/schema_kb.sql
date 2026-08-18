-- =====================================================================
-- kb.db —— v2 知识库 DDL
-- 结构 SSOT = 认知/数据结构.md §二（逐表逐字段照抄，不自造字段）
-- 批次① 地基 · 2026-08-18
--
-- 全局纪律（认知/数据结构.md §四 + CLAUDE.md §3）：
--   · 一切 id 走 TEXT（雪花号 JSON double 截尾会建空壳卷）
--   · 一切文件指针走相对 v2 根的路径（老货架 717 行绝对路径全断）
--   · 值域走 dict_item 或内联 CHECK；字段单名制（同物两名=静默丢）
--   · 一切靠闸不靠注释：块流校验器/考点叶子闸/执行阀五条在 工具箱/库/gates.py
--   · 本文件只建结构，不塞数据；字典 seed 走 init_db.py
-- =====================================================================

-- ---------------------------------------------------------------------
-- dict_item —— 值域字典（对应 D-16 老区精华吸收；数据结构 §2.1⑤）
-- 老区教训：四套题型编码 + 两套 source 字典并存，注释与字典互相矛盾。
-- 🔴 裁量：SSOT 写 `qtype_code TEXT REFERENCES dict_item(code)`，而 dict_item 主键是
--   (domain, code) 复合键——SQLite 的外键父列必须有 UNIQUE 索引，故本文件补
--   `ux_dict_item_code`（code 全局唯一），并约定 code 带域前缀（q1..q9 / d1..d4 / scan…）
--   以保证跨域不撞码。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dict_item (
  domain TEXT NOT NULL,                    -- 'qtype' | 'difficulty' | 'source' | 'artifact_kind' …
  code   TEXT NOT NULL,
  label  TEXT NOT NULL,
  ord    INTEGER,
  status TEXT NOT NULL CHECK(status IN ('在用','停用')),
  PRIMARY KEY (domain, code)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dict_item_code ON dict_item(code);

-- ---------------------------------------------------------------------
-- kp —— 知识图谱五层树（对应 D-12 溯源关系；数据结构 §2.2）
-- id 体系沿用老区：变长字符串每 3 位一层（level=len/3）；名字不沿用，v2 重起干净名。
-- 🔴 裁量：SSOT「P0 三修」要求「同名亲兄弟合并并加 UNIQUE(parent_id,name)」——
--   SQLite 里 NULL 互不相等，根节点（parent_id IS NULL）不受该 UNIQUE 约束，
--   故补一条 partial index 管住根级重名。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kp (
  id        TEXT PRIMARY KEY,
  name      TEXT NOT NULL,                 -- 考点名（卷面可用的干净名，叶子=名词短语不带编号年级题型）
  parent_id TEXT REFERENCES kp(id),
  level     TEXT NOT NULL CHECK(level IN ('版本','年级学期','单元','小节','考点')),
  ord       INTEGER,                       -- 同级排序（编号只在结构列，不进名字）
  status    TEXT NOT NULL CHECK(status IN ('现行','未铺','退役')),
  note      TEXT,
  UNIQUE (parent_id, name)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_kp_root_name ON kp(name) WHERE parent_id IS NULL;
CREATE INDEX IF NOT EXISTS ix_kp_parent ON kp(parent_id);

-- ---------------------------------------------------------------------
-- kp_alias —— 别名表 = 互通与产线的翻译层（对应 D-12；数据结构 §2.2）
-- 老区从来没有这层，resolve 命中率 2%~29% 的根因。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kp_alias (
  kp_id      TEXT NOT NULL REFERENCES kp(id),
  alias      TEXT NOT NULL,
  alias_kind TEXT,                         -- 词从哪来：产线词/教辅栏目词/错因码词/老区名…
  PRIMARY KEY (kp_id, alias)
);
CREATE INDEX IF NOT EXISTS ix_kp_alias_alias ON kp_alias(alias);

-- ---------------------------------------------------------------------
-- asset —— 图等二进制资产（对应 D-6 图在流内；数据结构 §2.1⑤）
-- 库里只存指针；实体落 知识库/资产/<hash前2>/<hash>.<ext>
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asset (
  hash       TEXT PRIMARY KEY,             -- 内容哈希
  kind       TEXT NOT NULL CHECK(kind IN ('figure','photo','sample')),
  rel_path   TEXT NOT NULL,                -- 🔴 一律相对 v2 根
  meta_json  TEXT,                         -- 宽高等（图宽以 docx extent 为唯一权威，像素只作提示）
  created_at TEXT
);

-- ---------------------------------------------------------------------
-- question_pattern —— 题型目录「这类题长什么样」（老区 326 条精华；数据结构 §2.1④）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_pattern (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  kp_ids_json TEXT NOT NULL,               -- 🔴 锚考点多值（模型可能考多个考点）
  desc        TEXT,
  status      TEXT NOT NULL CHECK(status IN ('在用','停用'))
);

-- ---------------------------------------------------------------------
-- solution_model —— 金标解题模型（老区 43 条，举一反三的地基；数据结构 §2.1④）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS solution_model (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  kp_ids_json       TEXT NOT NULL,         -- 多考点
  trigger_feature   TEXT NOT NULL,         -- 触发特征（看到什么就用它）
  action_conclusion TEXT NOT NULL,         -- 动作与结论
  tier              INTEGER,               -- 🔴 双旋钮之一：难度阶（表驱动，LLM 只匹配不自评）
  freq              INTEGER,               -- 🔴 双旋钮之二：考频
  status            TEXT NOT NULL CHECK(status IN ('在用','停用'))
);

-- ---------------------------------------------------------------------
-- exam_model —— 考察模型「怎么造这类题」（对应 D-9；数据结构 §2.3）
-- 计算题存模型不存实例；打卡铺开时每个考点的出题 DSL 记进本表。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_model (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  kp_ids_json TEXT NOT NULL,               -- 空数组=溯源断点，维护区点名
  dsl_ref     TEXT,                        -- 出题 DSL/表达式树指针
  params_json TEXT,                        -- 参数域 + 难度旋钮（tier/freq）
  note        TEXT,
  status      TEXT NOT NULL CHECK(status IN ('在用','停用'))
);

-- ---------------------------------------------------------------------
-- error_cause —— 错因库（对应 D-12；数据结构 §2.3）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS error_cause (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL,               -- 符号丢失/运算顺序/去括号变号…
  kp_ids_json TEXT,                        -- 空=跨考点通用
  desc        TEXT,
  status      TEXT NOT NULL CHECK(status IN ('在用','停用'))
);

-- ---------------------------------------------------------------------
-- err_code_map —— 产线错因码 → 错因（批改回流翻译层；对应 D-12；数据结构 §2.3）
-- 🔴 复合键 (kp_id, code)：同码两义实锤——`dist` 在「混合运算」线=运算律简算，
--   在「整式」线=去括号/合并同类项，且该歧义已印进洛天熙第 02 天交付报告。
-- 🔴 裁量：SSOT 原话「必须带考点作用域」⇒ kp_id 设 NOT NULL。
--   （若允许 NULL，SQLite 主键里 NULL 互不相等，同码会静默重复入库=新坑。）
-- 🔴 写入纪律（照抄老区）：同键不静默覆盖；改判走「先摘后挂」两条审计记录。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS err_code_map (
  kp_id    TEXT NOT NULL REFERENCES kp(id),
  code     TEXT NOT NULL,
  cause_id TEXT NOT NULL REFERENCES error_cause(id),
  PRIMARY KEY (kp_id, code)
);

-- ---------------------------------------------------------------------
-- cause_deposit —— 批改沉淀（学情回流落点；对应 D-12；数据结构 §2.3）
-- 跨库软引用：student/track_name/batch_ref 冗余存字符串，不做外键（grading.db 可迁云）。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cause_deposit (
  id         INTEGER PRIMARY KEY,
  student    TEXT,
  track_name TEXT,
  batch_ref  TEXT,
  qno        INTEGER,
  cause_id   TEXT REFERENCES error_cause(id),
  kp_id      TEXT,                          -- 发生在哪个考点（跨库回流，不设外键）
  note       TEXT,                          -- 现场原话
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_cause_deposit_student ON cause_deposit(student);
CREATE INDEX IF NOT EXISTS ix_cause_deposit_kp ON cause_deposit(kp_id);

-- ---------------------------------------------------------------------
-- template —— 版式模版库（对应 D-11；数据结构 §2.5）
-- 渲染永远 agent 本地（HTML→Chrome→PDF），本表只是货架。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS template (
  id            TEXT PRIMARY KEY,
  name          TEXT,
  purpose       TEXT,
  book_kinds    TEXT,
  params_json   TEXT,                       -- 纸张/边距/字号/题距/分栏/页眉脚/答案页/水印…
  pitfalls      TEXT,
  version       TEXT,
  status        TEXT NOT NULL CHECK(status IN ('在用','停用')),  -- 停用不删（发出去的册子还是老版式）
  sample_asset  TEXT REFERENCES asset(hash),
  registered_by TEXT,
  updated_at    TEXT
);

-- ---------------------------------------------------------------------
-- artifact —— 资料一本账（对应 D-7；数据结构 §2.6）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS artifact (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  kind         TEXT NOT NULL CHECK(kind IN ('打卡册','专项卷','举一反三','讲义','报告模版','其他')),
  status       TEXT NOT NULL CHECK(status IN ('在产','已交付','已上架')),
  files_json   TEXT,                        -- 成品件指针（asset hash / 相对路径 / 网盘链接）
  source_line  TEXT,
  template_id  TEXT REFERENCES template(id),
  kp_ids_json  TEXT,                        -- 覆盖考点（开轨时 kp_scope 从这取）
  delivered_at TEXT,
  link         TEXT,
  note         TEXT,
  created_at   TEXT
);

-- ---------------------------------------------------------------------
-- question —— 题目主表（对应 D-6 块流 + D-16 老区精华吸收；数据结构 §2.1①）
-- 🔴 两个刻意「没有」的字段：score（分值属载体位置）、qno（题号只是切分锚点）。
-- 🔴 正文只有块流一份：老区三载体并存（stem_text/block_json/text_content）是反面教材。
-- 🔴 小问不拆：一个题标记=一道题，(1)(2) 留在题面块流内。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question (
  id                   TEXT PRIMARY KEY,   -- qid：一律字符串
  blocks_json          TEXT NOT NULL,      -- 题面块流（规范 v2，校验器=gates.validate_blocks）
  answer_blocks_json   TEXT,               -- 答案，同构
  analysis_blocks_json TEXT,               -- 解析，同构
  qtype_code           TEXT REFERENCES dict_item(code),  -- 题型（域 qtype）
  diff_code            TEXT REFERENCES dict_item(code),  -- 难度（域 difficulty）
  pattern_id           TEXT REFERENCES question_pattern(id),
  source_kind          TEXT CHECK(source_kind IN ('scan','manual','model','pipeline')),
                                           -- D-9：题源类(scan/manual) vs 生成类(model/pipeline)
  source_raw           TEXT,               -- 来源原文，如「2024 杭州十三中二模」
  prov_json            TEXT,               -- 血缘：{doc,page} / {model_id,params,seed} / {mother_qid,operator}
  mother_qid           TEXT REFERENCES question(id),     -- 🔴 母题 SSOT 就是本列，不建平行 trace 表
  variant_op           TEXT,               -- 变式算子（不是教辅栏目名）
  match_key            TEXT,               -- 排重键（认卷撞库/册内查重）
  status               TEXT NOT NULL CHECK(status IN ('草稿','已审','上架','退役')),
                                           -- 🔴 ingest 只入草稿，promote 才可见；退役=软删，禁物理删
  created_at           TEXT,
  updated_at           TEXT
);
CREATE INDEX IF NOT EXISTS ix_question_status ON question(status);
CREATE INDEX IF NOT EXISTS ix_question_match_key ON question(match_key);
CREATE INDEX IF NOT EXISTS ix_question_mother ON question(mother_qid);
CREATE INDEX IF NOT EXISTS ix_question_pattern ON question(pattern_id);

-- ---------------------------------------------------------------------
-- question_kp —— 题↔考点绑定（对应 D-6/D-12；数据结构 §2.1③）
-- 🔴 叶子闸（gates.assert_leaf_kp）：kp_id 必须无子节点。老区注释写「挂叶子」实测 62% 挂章级，
--   直接威胁「学情按考点分轨」——分母是考点集，挂章级=分母失真。
-- 🔴 裁量：SSOT「主考点恰一（闸保证）」——DDL 只能保证「至多一」（partial unique index），
--   「至少一」留给入库闸。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_kp (
  question_id TEXT NOT NULL REFERENCES question(id),
  kp_id       TEXT NOT NULL REFERENCES kp(id),
  is_primary  INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
  anchor_json TEXT,                        -- {stage, fallback, confidence}：这个挂靠怎么来的、多可信
  PRIMARY KEY (question_id, kp_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_question_kp_primary ON question_kp(question_id) WHERE is_primary = 1;
CREATE INDEX IF NOT EXISTS ix_question_kp_kp ON question_kp(kp_id);

-- ---------------------------------------------------------------------
-- tag / question_tag —— 标签体系（对应 D-19；数据结构 §2.1⑥）
-- 首发四域：场景 / 方法 / 思想 / 图形特征；开新 domain 零改表。
-- 🔴 不存 use_count 这类计数（老区 143 个里 74 个是错的），要就现算。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tag (
  id     TEXT PRIMARY KEY,
  domain TEXT NOT NULL,                    -- '场景' | '方法' | '思想' | '图形特征' | …
  name   TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('在用','停用')),
  UNIQUE (domain, name)
);

CREATE TABLE IF NOT EXISTS question_tag (
  question_id TEXT NOT NULL REFERENCES question(id),
  tag_id      TEXT NOT NULL REFERENCES tag(id),
  PRIMARY KEY (question_id, tag_id)
);
CREATE INDEX IF NOT EXISTS ix_question_tag_tag ON question_tag(tag_id);

-- ---------------------------------------------------------------------
-- criterion —— 判据沉淀（对应 D-13；数据结构 §2.4）
-- 注入口径：agent 开工按线全量取「现行」；废止不删，带 superseded_by 链可回查。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS criterion (
  id            TEXT PRIMARY KEY,
  line          TEXT NOT NULL CHECK(line IN ('录入','批改','出题','渲染')),
  scene         TEXT NOT NULL,             -- 什么场景触发
  rule          TEXT NOT NULL,             -- 怎么判
  why           TEXT,                      -- 为什么（只写查得到证据的）
  source_ref    TEXT,                      -- 来源事故/正本
  status        TEXT NOT NULL CHECK(status IN ('现行','废止')),
  superseded_by TEXT REFERENCES criterion(id),
  created_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_criterion_line_status ON criterion(line, status);
-- 幂等判重键（import_criteria.py 按 (line,scene,rule) 判重，重跑不翻倍）
CREATE UNIQUE INDEX IF NOT EXISTS ux_criterion_lsr ON criterion(line, scene, rule);

-- ---------------------------------------------------------------------
-- ingest_template —— 录入模板库（对应 D-21；数据结构 §2.7）
-- = 老区「版式方言 A/B/C/D」那套经验的正规化容器。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_template (
  id            TEXT PRIMARY KEY,
  name          TEXT,
  layout_traits TEXT,                      -- 适用版式特征（怎么认出「这版式归我管」）
  rules_ref     TEXT,                      -- 切割规则/脚本指针
  sample_ref    TEXT,
  status        TEXT NOT NULL CHECK(status IN ('在用','停用')),
  created_at    TEXT
);

-- ---------------------------------------------------------------------
-- ingest_batch —— 录入批次（对应 D-18/D-21；数据结构 §2.7）
-- 🔴 裁量：SSOT 正文明文要求「ingest_batch 加 src_kind CHECK(...) 与 confidence，
--   图片源批次默认 status='待审'」，而同节 SQL 代码块漏写这两列 —— 以正文为准补上。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_batch (
  id          TEXT PRIMARY KEY,
  source_desc TEXT,                        -- 来源描述（哪本教辅/哪份卷）
  file_ref    TEXT,                        -- 原件指针（相对路径）
  src_kind    TEXT CHECK(src_kind IN ('文字层','图片OCR','多模态')),
  confidence  REAL,                        -- 批次置信度（执行阀第①条的入参）
  status      TEXT NOT NULL CHECK(status IN ('进行中','待审','已完成','已废弃')),
  stats_json  TEXT,                        -- 各闸通过率/拆题数/隔离数
  created_at  TEXT
);

-- ---------------------------------------------------------------------
-- ingest_item —— 批内逐题（对应 D-21；数据结构 §2.7）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingest_item (
  batch_id    TEXT NOT NULL REFERENCES ingest_batch(id),
  ord         INTEGER NOT NULL,            -- 批内序
  raw_json    TEXT,                        -- 切割原始载荷（块流候选）
  question_id TEXT REFERENCES question(id),-- 通过后指向 question（隔离/跳过为空）
  gates_json  TEXT,                        -- 各闸结果（drill 检测/排重/恒等/表述…）
  status      TEXT NOT NULL CHECK(status IN ('待审','通过','隔离','跳过')),
  PRIMARY KEY (batch_id, ord)
);
CREATE INDEX IF NOT EXISTS ix_ingest_item_status ON ingest_item(status);

-- ---------------------------------------------------------------------
-- review_ticket —— 审核台四类工单（对应 D-21；数据结构 §2.7）
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS review_ticket (
  id         INTEGER PRIMARY KEY,
  kind       TEXT NOT NULL CHECK(kind IN ('图审','kp低置信','隔离','排重冲突')),
  ref        TEXT,                         -- 指向 ingest_item / question
  status     TEXT NOT NULL CHECK(status IN ('待处理','已处理','已驳回')),
  note       TEXT,
  created_at TEXT,
  done_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_review_ticket_status ON review_ticket(status);

-- ---------------------------------------------------------------------
-- todo —— 待办列表（对应 D-14；数据结构 §2.8）
-- 🔴 页面只读；增删改走 skill/agent 直接写库。与 D-8 待办视图（业务现算）并列不合并。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS todo (
  id         INTEGER PRIMARY KEY,
  title      TEXT NOT NULL,
  detail     TEXT,
  line       TEXT CHECK(line IN ('录入','批改','出题','资料','其他')),
  status     TEXT NOT NULL CHECK(status IN ('待办','进行中','已完成','已取消')),
  priority   TEXT CHECK(priority IN ('高','中','低')),
  due        TEXT,
  ref        TEXT,                         -- 关联指针（批次/题/册/判据，可空）
  created_by TEXT CHECK(created_by IN ('人','agent')),
  created_at TEXT,
  done_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_todo_status ON todo(status);

-- ---------------------------------------------------------------------
-- skill_log —— skill 账单（对应 D-15；数据结构 §2.9）
-- 用途：高频 + 参数收敛 + 成功率稳的操作 → 优先包成 MCP 工具。不做页面，SQL 直查。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skill_log (
  id          INTEGER PRIMARY KEY,
  skill       TEXT NOT NULL,
  action      TEXT NOT NULL,
  args_digest TEXT,                        -- 参数摘要（不存全量）
  result      TEXT NOT NULL CHECK(result IN ('成功','失败')),
  detail      TEXT,
  duration_ms INTEGER,
  created_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_skill_log_skill ON skill_log(skill, created_at);
