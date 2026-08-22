# 展示台 console

## 真库页怎么起（/kb/* 六页）

真库组现有 **6 页**（PRD-007 线2 去 mock 后）：`/kb/questions`、`/kb/artifacts`、`/kb/kg`、
`/kb/models`、`/kb/criteria`、`/kb/templates`。它们不吃 mock，直连 `知识库/kb.db`，
取数走本目录下的薄读 API，**必须两个进程都起**：

```powershell
# ① kb 薄读 API（:4310，只读打开；KB_DB 不给就用 <v2根>/知识库/kb.db）
node console\server\kb-read-api.mjs
#   worktree 里指自己的沙盘库：$env:KB_DB='...\开发位\wt-xxx\知识库\kb.db'; node console\server\kb-read-api.mjs

# ② 展示台（vite 已把 /api/kb 代理到 :4310）
cd console; pnpm exec vite --port 4300 --strictPort --host 127.0.0.1
```

- 🔴 API **只读**（node:sqlite `readOnly:true`）：除白名单里唯一那条写口外只接 GET——
  改题/挂考点/挂账一律走 skill 与 `工具箱/` 脚本。
  唯一写口=`POST /api/kb/sale-state`（PRD-003 拍板，只写 `artifact.sale_state` 这一列人工售卖态；
  白名单长度硬断言=1，加第二条服务直接起不来）。
- 🔴 起服务前两道自检闸：①写端点白名单=1 条且读端点数与文件头端点账对得上；
  ②`artifact` 必须有 `sale_state` 列——缺列就拒启并让你去跑
  `python 工具箱/库/apply_ddl_263.py <库>`（不许静默起来然后四个口齐 500）。
- 🔴 公式渲染用 `public/mathjax/`（从 `工具箱/渲染/mathjax/es5/` 原样拷来，含 output/ 字体子树），
  不联网不打 CDN；md 进 DOM 前一律过 `src/kb/mathjax.ts` 的 `mdToHtml`（先转义后放定界符）。
- 真库页的类型与组件都在 `src/kb/`，**不碰 `src/mock/types.ts`**（那是 mock 页的公共契约件）。

端点共 **20 条 = 19 读 + 1 写**（原 7 读 → PRD-003 +2 读 +1 写 → PRD-007 线2 +6 读 →
PRD-007 二轮 +2 读 → 成品速览 +2 读）：

- 读（19）：`/api/kb/stats`、`/kg/tree`、`/questions`、`/questions/:id`、`/artifacts`、
  `/artifacts/:id`、`/artifact-members`（合刊关系）、`/materials`（物料清单）、`/papers/:id`、
  PRD-007 线2 的六个：`/kg/aliases`（别名层 + 一词多挂/断链告警）、`/kp/:id`（考点节点详情=聚合落点）、
  `/models`（三张脸：exam_model / solution_model / question_pattern**已停用**）、
  `/criteria`（判据沉淀，废止带替代链）、`/templates`（模版库，params/pitfalls 展开）、
  `/semantic/health`（语意 serve :4315 探活，唯一不碰库的读口）；
  PRD-007 二轮的两个：`/papers`（卷库列表：卷名/题数/满分/时长/所属册）、
  `/kg/patterns`（讲义 173 题型的下落：103 已锚进 kp.desc / 70 待人工归位，对齐-003；
  🔴 唯一一条**读磁盘正本文件**的读口，路径可用 `KG_PATTERN_MAP`/`KG_PATTERN_LIST` 顶掉以便测回退）；
  成品速览的两个：`/deliverables`（数据源＝ **`artifact_file` 表**，一行一件：文件名/角色/类型/大小/
  内容指纹/所属卷血缘/所属册/交付时间，参数 `ext`（可逗号多值）/`role`（可逗号多值，值域＝
  题目卷/答案卷/分析图/分析报告/页图/封面/样张/其他）/`kind`/`q`/`page`/`size`；
  🔴 库里还没建 `artifact_file` 表时**自动回落** `files_json` 拉平并回 `source:"files_json(兼容)"`，
  页面据此挂告警说明角色/血缘列不可用——不许省这条降级，省了就是建表前整页 500）、
  `/file?path=`（🔴 **全站唯一非 JSON 出口**，把成品件原样 inline 吐给浏览器内嵌预览）。
- 写（1）：`POST /api/kb/sale-state` —— 🔴 **PRD-007 两轮 + 成品速览一个写口都没加**，页面只读的原则不破。

🔴 `/api/kb/file` 的五道闸（改这段代码前先读全）：路径必须以 `成品库/` 开头（成品库归一后
`files_json` 全指这里）、无 `..` 段、非绝对路径、`resolve` 后仍在 `<v2根>/成品库/` 之内、
扩展名在 `pdf/png/jpg/jpeg/md` 白名单里。**不许为了"先能看"把前缀放宽到 `产物/` 或仓根**——
放宽一层就等于把整个仓（`password/` 就在隔壁）挂上 HTTP。归一没做完时库里还指着 `产物/…` 的行，
`/deliverables` 会照实回 `previewable:false`（顶层 `outside_root_total` 给总数），页面显示
「指针待归一」而不是给个点了 403 的死链接。

二轮另给三个存量端点加了字段（都不新增写口）：`/artifacts` 加 `细类` + 人话名三件套
（`display_name`/`display_from`/`code_name`）+ `retired`；`/templates` 加 `层` + `refs` 引用链；
`/papers/:id` 加 `stem`（截 120 字）+ `kps`（考点挂靠）。

`/questions` 的参数：`kp`（含别名 resolve）、`status`、`source_kind`、`qtype`/`difficulty`/`tag`/`unused`、
分页 `page`/`size`，加 PRD-007 的 `textbook`/`use_level`/`src_book`（来源三维，可重复给=OR，
写「未标」查没记的）、`ticket=1`（只看还挂着待处理工单的题）、`like=`（语意搜索）。

🔴 六条口径，改代码前先看：
- **推来的东西必须自报是推的**：人话名随行回 `display_from`、模版层随行回 `层_from` + `层_待回填`、
  来源册随行回 `src_book_from`。页面照着显示，**不许把推的显示成登记的**。
- **引用链只画 params 里读得到的**：配方→版式来自 `params.layout` 且**只认落在版式层的**那张
  （两张配方共享同一 layout key 不得互相引用——这是二轮实测抓到的真 bug，已由测试钉死）；
  版式→组件来自 params 文本点名。读不到就 `refs:[]`，页面显示「引用未登记」，绝不按常识写死。
- **缺列/缺文件优雅回退，但不假装有值**：`artifact.细类` 缺列 ⇒ `细类_available:false` + 整列 null，
  页面退回全量一张表；题型锚定正本文件缺失 ⇒ `available:false` + 说清哪个文件，**不编计数**。
  两条回退路径都有测试覆盖（回退分支写了不测 = 等于没写）。
- **满分只认 `paper.layout_json.full_score`**：`paper_item.score` 实查全库为 NULL，
  拿逐题分值求和会得到 0——「满分 0 分」比「未记」坏得多。
- **来源册是现推的不是库里的列**：prov 各产线各记各的键，读 API 按固定优先序推
  （卷名 › 卷 › punch_doc→artifact › 讲→source_raw 首段 › model_id），每行随行回 `src_book_from`
  说明这一格从哪来——页面照着显示，不许另发明第二套。
- **`--like` 是加速器不是依赖**：serve 挂了 `/semantic/health` 回 `ok:false`（页面收起搜索框），
  `?like=` 直接 500 明确报错——**绝不静默退回「按时间排」冒充语意命中**。
- **prov_json 一律先 `json_valid` 再 `json_extract`**：库里一条坏 JSON 会让裸 `json_extract`
  整条查询抛 malformed JSON，一道坏题打死一屏题库。

🔴 `/materials?q=`、`/kg/aliases?q=`、`/criteria?q=` 与考点模糊 resolve 的关键词进 LIKE 前
一律转义 `% _ \` 并带 `ESCAPE '\'`——`q=%` 只匹配含百分号的文案，不是整库。

## 自证怎么跑

```powershell
node --test console\server\kb-read-api-prd003.test.mjs    # 发布运营域 + 写端点越界闸（26 条）
node --test console\server\kb-read-api-prd007.test.mjs    # 维护域 6 口 + 题库增强（17 条）
node --test console\server\kb-read-api-prd007b.test.mjs   # 二轮 2 口 + 细类/人话名/层与引用链（19 条）
cd console; pnpm build                                     # tsc -b && vite build
```

三个测试套都在临时目录按 `工具箱/库/schema_kb.sql` 现建空库跑，**不碰 `知识库/kb.db`**；
默认端口 4311 / 4314 / 4316（回退分支另起 4317），可用 `KB_API_TEST_PORT` 顶掉，绝不撞主位常驻的 4310。
🔴 **三个套别用一条 `node --test` 一起跑**：prd003 默认占 4311，与自测实例撞口会齐刷刷报「API 进程退出」；
逐个跑，或各给一个 `KB_API_TEST_PORT`。

---

# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend enabling type-aware lint rules by installing `oxlint-tsgolint` and editing `.oxlintrc.json`:

```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "options": {
    "typeAware": true
  },
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```

See the [Oxlint rules documentation](https://oxc.rs/docs/guide/usage/linter/rules) for the full list of rules and categories.
