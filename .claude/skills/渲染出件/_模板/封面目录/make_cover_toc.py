# -*- coding: utf-8 -*-
"""封面目录生成（v2 渲染线）：config.json -> cover.png + toc.png [-> 拼进正文 PDF 并盖页码]

用法（路径可相对 v2 根，脚本自己解析）:
  python make_cover_toc.py --config 产物/打卡/<册名>/_源/前页.config.json \
      --outdir 产物/打卡/<册名>/_源/_前页
  python make_cover_toc.py --config <cfg> --outdir <out> \
      --body 产物/打卡/<册名>/题目卷.pdf --final 产物/打卡/<册名>/成品.pdf --stamp-pages

依赖: 本机 Chrome/Edge；--body 组装需 pymupdf (pip install pymupdf)

v2 化说明（老区平移 .claude/skills/封面目录生成/scripts/make_cover_toc.py）:
  · 零老区引用：v2 根按本文件位置自解析（同 punchkit/core.py 的写法）；
  · 相对路径一律相对 v2 根展开（数据纪律：文件指针全相对路径）；
  · Chrome 调用换成 v2「渲染出件」SKILL.md §4 的三坑配方（headless=new / 临时 profile /
    出完 sleep 再验文件存在）。
  · 模板是纯内联 SVG+CSS，无外链、无 MathJax、无图片素材 —— 离线可渲。
"""
import argparse
import html
import json
import os
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")   # 闸的拒收话走 stderr，一并救中文

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "templates")

# 本文件在 <v2根>/.claude/skills/渲染出件/_模板/封面目录/ → 上跳 5 层 = v2 根
V2_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
# 成品落点约定：产物/<产线>/<册名>/（artifact 只存相对 v2 根的指针）
PRODUCTS = os.path.join(V2_ROOT, "产物")

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# 🔴 Chrome 三坑配方（正本=「渲染出件」SKILL.md §4，照抄别复验）：
#    ① 撞正开着的 Chrome 会静默不写文件 → 必须临时 profile，出完 sleep 再验文件存在；
#    ② 本机有代理 → --no-proxy-server；
#    ③ 出 PDF 时必须补 --no-pdf-header-footer（旧 flag 已失效，缺了每页印时间戳+本地路径）。
CHROME_BASE = [
    "--headless=new", "--disable-gpu", "--no-proxy-server",
    "--virtual-time-budget=20000", "--run-all-compositor-stages-before-draw",
]
# 出 PDF 时在 CHROME_BASE 之上再加这条（本脚本走 PNG 通路，留此常量供同线复用/查配方）
CHROME_PDF_EXTRA = ["--no-pdf-header-footer"]

# 🔴 目录页容量闸：一页最多 5 行（2026-08-01 十天打卡册实锤，硬列 10 行会截出画布）。
#    十天册的正解=两天一组合并成 5 组。模板 .list.compact 的 CSS 注释自称能塞 6 章，
#    但实测口径以 5 为准；确要试 6 行的用 --allow-rows 6 显式放行并**必须目检**。
MAX_TOC_ROWS = 5

ROW_TPL = """
      <div class="row">
        <div class="num">{num}</div>
        <div class="mid"><div class="ch">{ch}</div><div class="ttl">{title}</div><div class="desc">{desc}</div></div>
        <div class="pg"><div class="n">{page}</div><div class="lab">PAGE</div></div>
      </div>"""


def rel2root(p):
    """输出路径：相对 = 相对 v2 根展开；绝对原样（文件指针全相对 v2 根纪律）"""
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(V2_ROOT, p))


def infile(p, what):
    """输入文件：先按 v2 根解析，不存在再退回当前目录；都没有 → 拒收并说清锚点规则"""
    if not p:
        return p
    if os.path.isabs(p):
        cand = [p]
    else:
        cand = [os.path.abspath(os.path.join(V2_ROOT, p)), os.path.abspath(p)]
    for c in cand:
        if os.path.isfile(c):
            return c
    sys.exit(f"{what} 找不到：{p}\n"
             f"  相对路径锚在 v2 根 {V2_ROOT}（也试过当前目录 {os.getcwd()}）；"
             f"请给相对 v2 根的路径或绝对路径。")


def find_chrome():
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("未找到 Chrome/Edge，请安装或在 CHROME_CANDIDATES 里补路径")


def fill(tpl_path, mapping):
    t = open(tpl_path, encoding="utf-8").read()
    for k, v in mapping.items():
        t = t.replace("{{%s}}" % k, v)
    if "{{" in t:
        left = sorted(set(x.split("}}")[0] for x in t.split("{{")[1:]))
        sys.exit(f"模板占位未填全: {left}")
    return t


def render_png(chrome, html_path, png_path):
    """HTML → PNG。900×1273 = A4 比例(0.707)，2x 缩放保印刷清晰度。"""
    # 🔴 临时 profile：撞正开着的 Chrome 会静默不写文件
    prof = os.path.join(tempfile.gettempdir(), "v2_cover_toc_chrome_prof")
    if os.path.exists(png_path):
        os.remove(png_path)                       # 先删旧件，免得把上一版当成功
    subprocess.run([chrome, *CHROME_BASE,
                    "--hide-scrollbars",
                    "--force-device-scale-factor=2", "--window-size=900,1273",
                    f"--user-data-dir={prof}", f"--screenshot={png_path}",
                    "file:///" + html_path.replace("\\", "/"),
                    ], check=True, capture_output=True)
    time.sleep(1)                                 # 🔴 出完 sleep 再验文件存在
    if not os.path.exists(png_path):
        sys.exit(f"渲染失败（文件没落地）: {png_path}")


def esc(s):
    return html.escape(s, quote=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="参数 json（相对路径=相对 v2 根）")
    ap.add_argument("--outdir", required=True,
                    help="输出目录（相对路径=相对 v2 根；约定放 产物/<产线>/<册名>/_源/_前页）")
    ap.add_argument("--body", help="正文PDF（给则组装成品）")
    ap.add_argument("--final", help="成品PDF输出路径（配合--body）")
    ap.add_argument("--stamp-pages", action="store_true", help="给正文盖页码1..N（封面/目录不编）")
    ap.add_argument("--theme", default=None, choices=["math", "science"],
                    help="主题（封面+目录成套）：math=浅蓝数学工具风 / science=青绿科学器材风。"
                         "缺省时读 config.theme，再缺省=math")
    ap.add_argument("--cover-template", default=None,
                    help="单独指定封面模板（覆盖 --theme）：templates/ 下文件名或绝对路径")
    ap.add_argument("--toc-template", default=None,
                    help="单独指定目录模板（覆盖 --theme）：templates/ 下文件名或绝对路径")
    ap.add_argument("--allow-rows", type=int, default=MAX_TOC_ROWS,
                    help=f"显式放宽目录行数闸（默认 {MAX_TOC_ROWS}）。放宽后必须人工目检末行有没有被截。")
    a = ap.parse_args()

    cfg_path = infile(a.config, "--config")
    outdir = rel2root(a.outdir)
    cfg = json.load(open(cfg_path, encoding="utf-8"))

    # 🔴 目录页容量闸：违例拒收不静默，且**前置**——别等渲完封面才发现目录填不下
    #    （2026-08-01 十天打卡册实锤：硬列 10 行末行被截出画布）
    n_rows = len(cfg["toc"]["rows"])
    if n_rows > a.allow_rows:
        sys.exit(f"目录行数 {n_rows} > {a.allow_rows}：一页容不下，末行会被截出画布。"
                 f"十天打卡册的正解是两天一组合并成 {MAX_TOC_ROWS} 组再填 rows；"
                 f"确要硬列请显式 --allow-rows {n_rows} 并人工目检。")
    if n_rows > MAX_TOC_ROWS:
        print(f"⚠ 目录 {n_rows} 行已超实锤容量 {MAX_TOC_ROWS}（--allow-rows 放行）"
              f"——出图后必须目检末行是否被截")

    os.makedirs(outdir, exist_ok=True)
    chrome = find_chrome()

    # ---- 主题 → 封面/目录模板成套（命令行 > config > 默认 math）----
    theme = a.theme or cfg.get("theme") or "math"
    THEME = {
        "math":    ("cover.html", "toc.html"),
        "science": ("cover-science.html", "toc-science.html"),
    }
    cover_name, toc_name = THEME.get(theme, THEME["math"])
    cover_name = a.cover_template or cover_name   # 单模板覆盖
    toc_name = a.toc_template or toc_name

    def resolve(name):
        """模板名：templates/ 下文件名优先，其次当路径（相对=相对 v2 根，再退当前目录）"""
        cand = os.path.join(TPL, name)
        if os.path.isfile(cand):
            return cand
        return infile(name, "模板")

    # ---- 封面 ----
    cv = cfg["cover"]
    title = cv["title"]
    cover_tpl = resolve(cover_name)
    cover_html = fill(cover_tpl, {
        "EYEBROW": esc(cv["eyebrow"]), "TITLE": esc(title),
        "SUBTITLE": esc(cv["subtitle"]), "EN_LINE": esc(cv["en_line"]),
        "PILL": esc(cv["pill"]), "EN_SUB_HTML": cv["en_sub_html"],
        "AUTHOR": esc(cv["author"]),
    })
    if len(title) >= 7:  # 长标题自动缩号防换行压插画
        cover_html = cover_html.replace("font-size:116px", "font-size:96px")

    # 🔴 副标题过长会把右侧 EN_LINE/PILL 顶出画布被裁掉（.h2 与 .men 同一 flex 行，nowrap）
    #    → 按视觉宽度自动缩号。2026-07-14 九上暑假衔接踩坑第二次后根治。
    def _vis_w(s):
        w = 0.0
        for c in s:
            if "\u4e00" <= c <= "\u9fff":
                w += 1.0          # 汉字
            elif c == " ":
                w += 0.3
            else:
                w += 0.6          # ·/字母/数字等
        return w

    sw = _vis_w(cv["subtitle"])
    if sw > 6.5:
        cover_html = cover_html.replace("font-size:74px", "font-size:48px")
    elif sw > 5.2:
        cover_html = cover_html.replace("font-size:74px", "font-size:58px")
    hp = os.path.join(outdir, "_cover.html")
    open(hp, "w", encoding="utf-8").write(cover_html)
    cover_png = os.path.join(outdir, "cover.png")
    render_png(chrome, hp, cover_png)
    print("cover.png OK")

    # ---- 目录 ----
    tc = cfg["toc"]
    rows = "".join(ROW_TPL.format(num=esc(r["num"]), ch=esc(r["ch"]),
                                  title=esc(r["title"]), desc=esc(r["desc"]),
                                  page=esc(str(r["page"]))) for r in tc["rows"])
    toc_html = fill(resolve(toc_name), {
        "EYEBROW": esc(cv["eyebrow"]), "SUB_HTML": tc["sub_html"],
        "ROWS": rows, "LIST_CLASS": "compact" if len(tc["rows"]) > 4 else "",
        "FOOT_LEFT_HTML": tc["foot_left_html"],
        "FOOT_RIGHT_HTML": tc["foot_right_html"],
    })
    hp = os.path.join(outdir, "_toc.html")
    open(hp, "w", encoding="utf-8").write(toc_html)
    toc_png = os.path.join(outdir, "toc.png")
    render_png(chrome, hp, toc_png)
    print("toc.png OK")

    # ---- 组装 ----
    if a.body:
        if not a.final:
            sys.exit("--body 需配 --final")
        import fitz
        body = fitz.open(infile(a.body, "--body"))
        W, H = body.load_page(0).rect.width, body.load_page(0).rect.height
        book = fitz.open()
        for png in (cover_png, toc_png):
            pg = book.new_page(width=W, height=H)
            pg.insert_image(fitz.Rect(0, 0, W, H), filename=png)
        book.insert_pdf(body)
        body.close()
        if a.stamp_pages:
            NAVY, GOLD = (0.07, 0.19, 0.34), (0.78, 0.57, 0.18)
            for i in range(2, len(book)):
                pg = book.load_page(i)
                n, r = i - 1, pg.rect
                cx, yb = r.width / 2, r.height - 26
                pg.draw_line((cx - 52, yb - 5), (cx - 18, yb - 5), color=GOLD, width=0.8)
                pg.draw_line((cx + 18, yb - 5), (cx + 52, yb - 5), color=GOLD, width=0.8)
                pg.insert_textbox(fitz.Rect(cx - 36, yb - 14, cx + 36, yb + 6),
                                  str(n), fontsize=11, fontname="helv", color=NAVY, align=1)
        final = rel2root(a.final)
        os.makedirs(os.path.dirname(final), exist_ok=True)
        book.save(final, deflate=True, garbage=4)
        print(f"成品 {len(book)} 页 -> {final}")
        book.close()


if __name__ == "__main__":
    main()
