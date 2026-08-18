-- =====================================================================
-- grading.db —— v2 批改产线 DDL（5 表）
-- 结构 SSOT = 认知/数据结构.md §一（逐表逐字段照抄，不自造字段）
-- 批次① 地基 · 2026-08-18
--
-- 🔴 自包含可迁云单元（D-5）：本库 + 收件箱/ + 题单快照/ + 学员/ 整目录将来上 101。
-- 🔴 跨库纪律（数据结构 §四）：库内不出现 kb 外键——考点集/题单以快照携带
--    （track.kp_scope_json / 题单快照文件），学情回流单向只读，kb 永不写本库。
-- 🔴 学情没有表（D-2）：轨级趋势/考点覆盖/过关状态一律现算；唯一落盘的是
--    出件快照 batch.xq_snapshot_json。
-- =====================================================================

-- ---------------------------------------------------------------------
-- student —— 学员（对应 D-1；数据结构 §一）
-- 代号=现状习惯（本来就没有真名可记），不是隐私限制；要加字段直接加。
-- 学员 360 视图现算不落表：档案 + 在练轨 + 全部批次 + 报告清单 + 沉淀错因 + 交付物。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student (
  code         TEXT PRIMARY KEY,           -- 代号（现状唯一标识）
  grade        TEXT,                       -- 年级
  textbook_ver TEXT,                       -- 教材版本（人教/浙教…，出题与认卷都要）
  status       TEXT CHECK(status IN ('试听','在读','暂停','结课')),
  service_tier TEXT,                       -- 服务档位（订阅特训7天/21天/一对一/打卡客户…）
  joined_at    TEXT,                       -- 入营时间
  profile_json TEXT,                       -- 🔴 肖像：学习特征/口味/注意事项（备课与出题的个性化依据）
  note         TEXT,
  created_at   TEXT
);

-- ---------------------------------------------------------------------
-- track —— 轨 = 学员 × 专项的一次征程（对应 D-1/D-1b/Q-14；数据结构 §一）
-- 开轨时机：派卷/绑定打卡练习那一刻登记；收卷认到未登记的册 → 兜底自动开轨。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS track (
  id            INTEGER PRIMARY KEY,
  student       TEXT NOT NULL REFERENCES student(code),
  name          TEXT NOT NULL,             -- 专项名（=打卡练习名）
  round         INTEGER NOT NULL DEFAULT 1,-- 🔴 复训轮次（复训=新轨，轨名展示带轮次）
  book_ref      TEXT,                      -- 册指针（kb 的 artifact.id 或册目录名，软引用不做外键）
  kp_scope_json TEXT NOT NULL,             -- 🔴 本轨考点集（kb 的 kp.id 数组）＝学情的分母
  status        TEXT CHECK(status IN ('进行中','已完结','暂停')),
  started_at    TEXT,
  finished_at   TEXT,
  UNIQUE (student, name, round)
);
CREATE INDEX IF NOT EXISTS ix_track_student ON track(student);

-- ---------------------------------------------------------------------
-- batch —— 批次 = 某轨某一天交的那份卷（对应 D-1/D-10；数据结构 §一）
-- 九态状态机唯一迁移图；待办=三个人工态（待人工认卷/待终审/故障）的过滤视图。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batch (
  id               INTEGER PRIMARY KEY,
  track_id         INTEGER NOT NULL REFERENCES track(id),  -- 🔴 非空，没有轨的批次不允许存在
  day_in_track     INTEGER NOT NULL,       -- 🔴 轨内天号，个人流水号废除
  date             TEXT,                   -- 实际交卷日
  state            TEXT NOT NULL CHECK(state IN
                     ('收件中','待认卷','待人工认卷','批改中','待终审','已确认','待出件','已出件','故障')),
  state_since      TEXT NOT NULL,          -- 现态起点：队列「停留时长」由此现算
  candidates_json  TEXT,                   -- 仅待人工认卷：撞库候选卷清单 [{track,day,sim}]
  note             TEXT,                   -- 机器原话（故障原因/撞库说明）
  auto             TEXT,                   -- 无人值守档位痕迹（L0/L1/L2）
  round            INTEGER DEFAULT 1,      -- 打回重批轮次
  task_ref         TEXT,                   -- 题单快照路径：题单快照/<track_id>/D<day>.json
  photos_json      TEXT,                   -- 本批卷面照片清单（收件箱相对路径数组）
  summary          TEXT,                   -- 英雄卡总结（出件闸校验：必须真结论非导航句）
  xq_snapshot_json TEXT,                   -- 出件那一刻的轨级学情快照（D-2：报告可复现）
  report_file      TEXT,                   -- 🔴 报告=批次字段（D-3）：学员/<代号>/报告/<轨名>-D<n>-学情分析.png
  confirmed_at     TEXT,
  exported_at      TEXT,
  UNIQUE (track_id, day_in_track, round)
);
CREATE INDEX IF NOT EXISTS ix_batch_state ON batch(state);
CREATE INDEX IF NOT EXISTS ix_batch_track ON batch(track_id);

-- ---------------------------------------------------------------------
-- item —— 逐题判定（对应 D-1；数据结构 §一）
-- 口径三条：空题×/订正对算对/抄错题面按所抄算（复锚，与 stem_seen 对照）。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS item (
  batch_id      INTEGER NOT NULL REFERENCES batch(id),
  qno           INTEGER NOT NULL,          -- 卷面题号
  verdict_pre   TEXT CHECK(verdict_pre IN ('√','×','?')),      -- 机器初判（?=存疑）
  verdict_final TEXT CHECK(verdict_final IN ('√','×','去掉')),  -- 终审拍板（去掉=作废不计分母）
  stem_seen     TEXT,                      -- 卷面誊写的题面（复锚判据）
  answer_raw    TEXT,                      -- 末行答案原文
  lines_json    TEXT,                      -- 逐行转录（作答稿）
  note          TEXT,                      -- 存疑原因/错因备注（人话，对外禁「抄错」措辞）
  error_kp_json TEXT,                      -- 🔴 错因挂 kb 的 kp.id 数组（经 err_code_map 翻译），局部七码废除
  page          INTEGER,                   -- 在第几页照片
  zooms         INTEGER,                   -- 放大次数（放大预算审计）
  PRIMARY KEY (batch_id, qno)
);

-- ---------------------------------------------------------------------
-- feedback —— 终审/打回留痕（对应 D-4；数据结构 §一）
-- 🔴 裁量：SSOT 未给主键，且同一轮可能多条留痕 ⇒ 用 rowid 表 + (batch_id, round) 索引，
--   不擅自加唯一约束。
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
  batch_id   INTEGER REFERENCES batch(id),
  round      INTEGER,                      -- 第几轮打回
  body       TEXT,                         -- 打回意见/终审改判记录
  created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_feedback_batch ON feedback(batch_id, round);
