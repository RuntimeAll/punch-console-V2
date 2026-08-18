---
name: 渲染出件
description: 把题库数据渲成印刷级成品（HTML→Chrome→PDF），题目卷/解析卷分双 PDF，可选封面目录三件套；版式=punchkit 骨架换装制（LAYOUT 一行换），模版进 template 表登记。当用户说"出 PDF""渲染成卷""出样张""换个版式""加封面目录""出图片物料 PNG"时用。🔴 渲染永远 agent 本地（系统只存模版卡+样张）；出件前 Read 自检；Chrome 三坑照抄别复验。绝不调老区/备课帮任何服务。
---

# 渲染出件 —— HTML → Chrome → PDF（横切正本=认知/业务流程.md §五）

## 0. 开工前

`python 工具箱/库/inject_criteria.py 渲染` 注入现行判据。
每次出件后 `log_skill.py 渲染出件 <动作> …` 落账（飞轮铁律 #4）。

## 1. 版式=punchkit 换装制（骨架白搬老区，v2 路径已改净）

```powershell
cd D:\workplace\ai-bkb-v2\.claude\skills\每日打卡\_模板
python -m punchkit          # 骨架 × 渲染器菜单（daily_v1 默认 / dense_sections 最通用 …）
```
- 一册 = 骨架（layouts/，学科无关）× 渲染器（renderers/，学科相关）；`LAYOUT='<key>'` 一行换装。
- 🔴 绝不在册 `_源/` 里私长 CSS；真·新版式=在 `layouts/` 加骨架文件 + `_MODULES` 挂一行。
- MathJax 本地 `工具箱/渲染/mathjax/es5/tex-mml-chtml.js`（punchkit core 已自解析，离线可渲）。
- 水印拔插：交付 PDF `watermark=None`（付费客户拿到的要干净）；小红书 PNG 带水印（防盗图）。

## 2. 双 PDF 铁律

- **题目卷与解析卷/答案卷是两个独立 PDF**；题目卷不含任何答案/解析（punchkit core 有泄答案闸）。
- 页数断言：打卡类题目卷页数=天数；答案卷 height:auto 允许多页。
- 出件前 **Read 自检**：PDF 转 PNG 逐页目检（版面破没破、公式渲没渲出来、水印对不对）。

## 3. 封面目录三件套（用户点名才做）

封面+目录+封底走独立 HTML 模板渲染；目录页行数有限（老区实锤：10 天册目录最多容 5 行，
必须两天一组分 5 组，硬列 10 行会截出画布）。AB 双号封面/目录**必须两套版式**（隔离清单第 2 维）。

模板与用法正本 = [`_模板/封面目录/README.md`](_模板/封面目录/README.md)（双主题 math/science，坑清单在里面）。
```powershell
python .claude\skills\渲染出件\_模板\封面目录\make_cover_toc.py --config <前页.config.json> `
  --outdir 产物\打卡\<册名>\_源\_前页 --body 产物\打卡\<册名>\题目卷.pdf `
  --final 产物\打卡\<册名>\成品.pdf --stamp-pages
```

## 4. Chrome 出 PDF 配方（三坑照抄，别复验）

```powershell
chrome --headless=new --disable-gpu --no-proxy-server --no-pdf-header-footer `
  --virtual-time-budget=20000 --run-all-compositor-stages-before-draw `
  --user-data-dir=<临时profile> --print-to-pdf=<出件路径> <html路径>
```
- 🔴 撞正开着的 Chrome 会**静默不写文件**：必须用临时 profile；出完 sleep 再验文件存在。
- 🔴 `--no-pdf-header-footer` 缺了每页印时间戳+本地路径+页码（旧 flag 已失效）。
- 🔴 `<`/`>` 进公式必转 `\lt `/`\gt `；中文不混进 LaTeX；PNG 物料同配方加 `--screenshot`。

## 5. template 表登记（D-11：库只是货架，渲染永远本地）

新版式定稿后登记：
```powershell
python 工具箱/挂账/artifact_tool.py template-add --id <layout_key> --name <模版名> `
  --purpose <用途一句> --book-kinds 打卡册 --params '{"layout":"<key>","纸张":"A4",...}' `
  --pitfalls "<口径与坑>"
```
停用不删（发出去的册子还是老版式）；样张可入 asset 后回填 sample_asset。
