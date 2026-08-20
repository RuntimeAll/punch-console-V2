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

端点共 **16 条 = 15 读 + 1 写**（原 7 读 → PRD-003 +2 读 +1 写 → PRD-007 +6 读）：

- 读（15）：`/api/kb/stats`、`/kg/tree`、`/questions`、`/questions/:id`、`/artifacts`、
  `/artifacts/:id`、`/artifact-members`（合刊关系）、`/materials`（物料清单）、`/papers/:id`、
  以及 PRD-007 的六个：`/kg/aliases`（别名层 + 一词多挂/断链告警）、`/kp/:id`（考点节点详情=聚合落点）、
  `/models`（三张脸：exam_model / solution_model / question_pattern**已停用**）、
  `/criteria`（判据沉淀，废止带替代链）、`/templates`（模版库，params/pitfalls 展开）、
  `/semantic/health`（语意 serve :4315 探活，唯一不碰库的读口）。
- 写（1）：`POST /api/kb/sale-state` —— 🔴 **PRD-007 一个写口都没加**，页面只读的原则不破。

`/questions` 的参数：`kp`（含别名 resolve）、`status`、`source_kind`、`qtype`/`difficulty`/`tag`/`unused`、
分页 `page`/`size`，加 PRD-007 的 `textbook`/`use_level`/`src_book`（来源三维，可重复给=OR，
写「未标」查没记的）、`ticket=1`（只看还挂着待处理工单的题）、`like=`（语意搜索）。

🔴 三条口径，改代码前先看：
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
node --test console\server\kb-read-api-prd003.test.mjs   # 发布运营域 + 写端点越界闸（26 条）
node --test console\server\kb-read-api-prd007.test.mjs   # 维护域 6 口 + 题库增强（17 条）
cd console; pnpm build                                    # tsc -b && vite build
```

两个测试套都在临时目录按 `工具箱/库/schema_kb.sql` 现建空库跑，**不碰 `知识库/kb.db`**；
默认端口 4311 / 4314（可用 `KB_API_TEST_PORT` 顶掉），绝不撞主位常驻的 4310。

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
