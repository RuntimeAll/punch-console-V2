# 封面目录三件套模板（老区「封面目录生成」skill 平移，2026-08-18 v2 化）

`config.json 填参数 → 一条命令 → cover.png + toc.png`（可选直接拼进正文 PDF 并盖页码）。
模板是**纯内联 SVG + CSS**：无外链、无 MathJax、无图片素材，离线可渲，改配色只动 `:root` 变量。

## 一条命令

```powershell
cd D:\workplace\ai-bkb-v2
$S = '.claude\skills\渲染出件\_模板\封面目录\make_cover_toc.py'

# ① 只出封面+目录 PNG（默认 math 主题）
python $S --config 产物\打卡\<册名>\_源\前页.config.json --outdir 产物\打卡\<册名>\_源\_前页

# ② 一步到位：封面+目录+正文拼成书，并给正文盖页码 1..N
python $S --config 产物\打卡\<册名>\_源\前页.config.json --outdir 产物\打卡\<册名>\_源\_前页 `
  --body 产物\打卡\<册名>\题目卷.pdf --final 产物\打卡\<册名>\成品.pdf --stamp-pages

# ③ 科学教辅：整套切青绿科学主题
python $S --config <cfg> --outdir <out> --theme science --body <正文.pdf> --final <成品.pdf> --stamp-pages
```

- 🔴 **路径一律可写相对 v2 根**（`产物\...`）：脚本按自身位置解析 v2 根后展开，绝对路径也吃；
  输入件（`--config` / `--body` / 自定模板）在 v2 根下找不到时会退回当前目录再找一次，
  两处都没有就带着锚点规则拒收。成品落 `产物/<产线>/<册名>/`，artifact 只存相对指针。
- 参数模板拷 `example.config.json` 改；字段说明见下。
- 组装（`--body`）需 `pip install pymupdf`；渲图需本机 Chrome/Edge（脚本自动探测，Chrome→Edge）。

## 主题（`--theme`，封面+目录成套换）

| 主题 | 风格 | 模板文件 |
|---|---|---|
| `math`（默认） | 浅蓝数学工具风，navy `#153a5e`，圆规/直尺/计算器/量角器/眼镜插画，量角器角饰 | `templates/cover.html` + `templates/toc.html` |
| `science` | 青绿科学器材风，teal `#0e5f5b` + 暖橙点缀，显微镜/锥形瓶/试管/烧杯/水分子插画，烧杯+放大镜角饰 | `templates/cover-science.html` + `templates/toc-science.html` |

优先级：命令行 `--theme` > config 顶层 `"theme"` 字段 > 默认 `math`。
仍可用 `--cover-template` / `--toc-template` 单独覆盖某一张（高级用法）。

## config 字段

```jsonc
{
  "theme": "math",                     // 可选：math(默认) | science；命令行 --theme 优先
  "cover": {
    "eyebrow": "初中数学 · 浙教版",
    "title": "暑假计算册",             // 主标题（≤6字最稳，7+字自动缩字号）
    "subtitle": "七年级上册",          // 🔴 别塞长信息，见下方坑
    "en_line": "MATHEMATICS",
    "pill": "计算专项 · GRADE 7",      // 长信息塞这里，胶囊自适应
    "en_sub_html": "SUMMER <b>CALCULATION</b> WORKBOOK",
    "author": "王老师"                 // 只放名字，不加"主讲·编订"
  },
  "toc": {
    "sub_html": "七年级上册 · <b>暑假计算专项</b> · 有理数 / 整式加减 / 实数 / 幂运算",
    "rows": [                          // 🔴 最多 5 行；page = 正文页码（1起）
      {"num":"01","ch":"第 一 章","title":"有理数","desc":"相反数与绝对值 等","page":"01"},
      {"num":"02","ch":"第 二 章","title":"整式的加减","desc":"单项式与多项式 等","page":"13"}
    ],
    "foot_left_html": "<span class=\"brand\">王老师</span>",
    "foot_right_html": "浙教版 <span class=\"dot\">·</span> 全 26 页"
  }
}
```

## 老区已知坑（实锤，别重踩）

- 🔴 **目录页最多容 5 行**（2026-08-01 十天打卡册实锤）：硬列 10 行末行会被**截出画布**，
  十天册必须**两天一组合并成 5 组**再填 `rows`。脚本已上闸（`MAX_TOC_ROWS=5`），
  超了直接拒收；确要试 6 行用 `--allow-rows 6` 显式放行，**放行后必须目检末行**。
- 🔴 **页面尺寸铁律**：模板 900×1273px = A4 比例 0.707；渲图参数
  `--window-size=900,1273 --force-device-scale-factor=2`（2x 保印刷清晰度），别乱改。
- 🔴 **Chrome 三坑照抄别复验**（正本=`../../SKILL.md` §4）：
  临时 `--user-data-dir`（撞正开着的 Chrome 会**静默不写文件**）、`--no-proxy-server`（本机有代理）、
  出完 **sleep 再验文件存在**。脚本内已按此配方写死；若改成 `--print-to-pdf` 出 PDF，
  必须再补 `--no-pdf-header-footer`（缺了每页印时间戳+本地路径+页码，旧 flag 已失效）。
  完整 PDF 行：
  `--headless=new --disable-gpu --no-proxy-server --no-pdf-header-footer --virtual-time-budget=20000 --run-all-compositor-stages-before-draw --user-data-dir=<临时profile> --print-to-pdf=<出件路径> <html路径>`
- 🔴 **副标题(subtitle)过长会把右侧 EN_LINE/PILL 顶出画布被裁掉**（`.h2` 与 `.men` 同一 flex 行、
  `nowrap`、`overflow:hidden` 直接切边）。2026-07 连踩两次后脚本已按视觉宽度自动缩号
  （>5.2→58px，>6.5→48px）。**经验：长信息优先塞 `pill`，别硬塞副标**；改完必目检右上角。
- 🔴 **主标题过长压插画**：模板已 `white-space:nowrap` + 7 字起自动缩号，但 >8 字仍需人工目检。
- 🔴 **页码对齐**：`--stamp-pages` 只给正文编 1..N（封面/目录不编）；`rows[].page` 必须填
  **正文页码**——先用 pymupdf 逐页 `get_text()` 搜章名定位章首页，再填目录。
- 🔴 **学生可见卷面纪律**：封面/目录不得出现内部词（层/★/基础过关·强化·拓展/素材/薄弱）。
- **作者位只放名字**（如"王老师"），色块下方居中；目录页脚 `foot_left_html` 同样**只留名字**，
  别塞书名前缀或"主讲编订"（2026-07-10、07-11 两次用户拍板）。
- **中文控制台**：脚本已 `sys.stdout.reconfigure(encoding='utf-8')`；命令行乱码不影响产物。

## 🔴 发小红书 AB 双号：封面/目录必须两套版式

双号防判重靠的是**版面结构不同**，不是水印、不是 dpi。正文早有两套骨架的册子，
**封面和目录最容易漏**（老区七上第二单元合刊踩过：两版共用一份前页 CSS 只换文件名，
A 号第 1 张封面和 B 号第 1 张目录是同一张脸，漏在最显眼的位置）。

⚠️ **换 `--theme`（math↔science）不算隔离**——那只换配色与插画，版心结构/对齐/信息分块没变。
要换的是**结构**：

| 维度 | 一套 | 另一套 |
|---|---|---|
| 版心 | 无框（靠底纹/留白分区） | 整页外框 |
| 对齐 | 左对齐排印层级 | 居中 |
| 清单 | 多列网格 | 引导点清单（leader dots） |
| 规格数字 | 独立数据带 | 并进页脚单行 |

单本自用、不走双号发布的书不受此限，照常出一套。

## 必做验收

渲完把成品第 1/2 页 + 任一章首页转图**目检**：封面文字没被插画压住、右上角 EN_LINE/PILL 没被切、
目录页码 = 章首页脚页码、目录末行没被截。

## 文件清单

| 文件 | 说明 |
|---|---|
| `make_cover_toc.py` | 填模板 → Chrome 渲 PNG →（可选）pymupdf 拼装+盖页码；`--theme` 成套切主题 |
| `example.config.json` | 暑假计算册实例（老区定稿那本的参数） |
| `templates/cover.html` / `toc.html` | math 主题 |
| `templates/cover-science.html` / `toc-science.html` | science 主题（2026-07-13 五上暑假练习册定稿） |

未平移：老区 `templates/_cover-science-blue.bak.html`（旧蓝色科学封面备份，已被 teal 版取代，
老区自己标注"留档不用"）。深色蓝图风封面（navy 底+金字+印章）老区也不在这套里，
要用时按本模板改 `:root` 配色衍生。
