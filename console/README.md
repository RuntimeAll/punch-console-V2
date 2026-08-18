# 展示台 console

## 真库页怎么起（/kb/questions、/kb/artifacts）

这两页不吃 mock，直连 `知识库/kb.db`，取数走本目录下的薄读 API，**必须两个进程都起**：

```powershell
# ① kb 薄读 API（:4310，只读打开；KB_DB 不给就用 <v2根>/知识库/kb.db）
node console\server\kb-read-api.mjs
#   worktree 里指自己的沙盘库：$env:KB_DB='...\开发位\wt-xxx\知识库\kb.db'; node console\server\kb-read-api.mjs

# ② 展示台（vite 已把 /api/kb 代理到 :4310）
cd console; pnpm exec vite --port 4300 --strictPort --host 127.0.0.1
```

- 🔴 API **只读**（node:sqlite `readOnly:true`），且只接 GET——页面上一个写按钮都没有，
  改题/挂考点/挂账一律走 skill 与 `工具箱/` 脚本。
- 🔴 公式渲染用 `public/mathjax/`（从 `工具箱/渲染/mathjax/es5/` 原样拷来，含 output/ 字体子树），
  不联网不打 CDN；md 进 DOM 前一律过 `src/kb/mathjax.ts` 的 `mdToHtml`（先转义后放定界符）。
- 真库页的类型与组件都在 `src/kb/`，**不碰 `src/mock/types.ts`**（那是 mock 页的公共契约件）。

端点：`/api/kb/stats`、`/kg/tree`、`/questions`（kp 含别名 resolve、status、source_kind、分页）、
`/questions/:id`、`/artifacts`、`/artifacts/:id`、`/papers/:id`。

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
