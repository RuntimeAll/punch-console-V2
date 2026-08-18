# -*- coding: utf-8 -*-
"""
punchkit.core —— 打卡册版式库 · 共用管道
=========================================
🔴 **这里只放「所有版式都一样」的东西**。任何一处「某个版式才需要」的逻辑都不许进来，
   那属于 `layouts/<版式>.py`。判断标准：**换个版式还成立吗？** 不成立就别放这。

管的六件事（原先在每册 `_源/gen_打卡.py` 里各抄一份，共 6 份，改一处漏五处）：
  ① HTML 外壳 + MathJax 离线注入      ② 玉米水印 base64 内联
  ③ Chrome 出 PDF（🔴 三坑照抄）      ④ 页数断言
  ⑤ PDF → PNG 目检图                  ⑥ 通用闸：题目卷不泄答案（结构层判定）

不管的：CSS、卡片排版、题目渲染、题量配比、内容闸 —— 全在版式模块与册子的 qbank/days 里。
"""
import base64
import os
import re
import subprocess
import sys

# ── 路径（v2 化：按本文件位置自解析 v2 根，零老区引用；换机器只改 CHROME） ──
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
# core.py 在 <v2根>/.claude/skills/每日打卡/_模板/punchkit/ → 上跳 5 层 = v2 根
V2_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       '..', '..', '..', '..', '..'))
MATHJAX = ('file:///' + os.path.join(V2_ROOT, '工具箱', '渲染', 'mathjax', 'es5',
                                     'tex-mml-chtml.js').replace('\\', '/'))
WATERMARK_PNG = os.path.join(V2_ROOT, '.claude', 'skills', '每日打卡', '_模板', '玉米水印.png')

_wm_cache = None


def watermark_img():
    """玉米水印 <img>，base64 内联（离线可渲，不依赖文件路径）"""
    global _wm_cache
    if _wm_cache is None:
        with open(WATERMARK_PNG, 'rb') as fh:
            _wm_cache = ('<img src="data:image/png;base64,'
                         + base64.b64encode(fh.read()).decode() + '"/>')
    return _wm_cache


def utf8_stdout():
    """🔴 GBK 控制台遇 emoji 会 UnicodeEncodeError 直接杀进程（踩过），脚本开头必调"""
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


# ═══════════════ ① HTML 外壳 ═══════════════
_SHELL = ('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
          '<title>%s</title><style>%s</style>'
          '<script>window.MathJax={tex:{inlineMath:[["\\\\(","\\\\)"]]},'
          'chtml:{scale:1.0}};</script><script src="%s"></script></head>'
          '<body class="%s">%s</body></html>')


def build_html(title, css, body, ans):
    """套外壳。body class = qsheet / asheet，版式 CSS 靠它区分题目卷与答案卷。"""
    return _SHELL % (title, css, MATHJAX, 'asheet' if ans else 'qsheet', body)


# ═══════════════ ③ 出 PDF：🔴 三坑照抄，别自己改 ═══════════════
def to_pdf(html_path, pdf_path, budget_ms=20000):
    """
    🔴 三个坑，每个都实伤过：
      1. 必须 `--headless=new` —— 旧的 `--headless` 静默不生成文件
      2. 必须等进程结束（这里用 subprocess.run，PowerShell 里则是 Start-Process -Wait）
         —— 不等就会读到**上一次**的旧文件，"大小一模一样"，排查半天
      3. `--no-pdf-header-footer` 必须排在 `--print-to-pdf` **之前**，否则不生效
    另加：--virtual-time-budget 等 MathJax 排完；--run-all-compositor-stages 保证画完。
    🔴 第四坑（2026-08-18 render_paper 沙盘上报后修进本体）：撞正开着的 Chrome 会**静默不写文件**
      ——必须带独立 --user-data-dir 临时 profile；出完验文件真实存在，不存在就抛错不装成功。
    """
    import tempfile
    with tempfile.TemporaryDirectory(prefix='punchkit-chrome-') as prof:
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--no-proxy-server',
                        '--user-data-dir=' + prof,
                        '--no-pdf-header-footer',
                        '--virtual-time-budget=%d' % budget_ms,
                        '--run-all-compositor-stages-before-draw',
                        '--print-to-pdf=' + pdf_path,
                        'file:///' + html_path.replace('\\', '/')],
                       check=True, capture_output=True, timeout=300)
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        raise RuntimeError('🔴 Chrome 声称跑完但 PDF 不存在/为空：%s' % pdf_path)


# ═══════════════ ④ 页数 ═══════════════
def page_count(pdf_path):
    with open(pdf_path, 'rb') as fh:
        return len(re.findall(rb'/Type\s*/Page[^s]', fh.read()))


# ═══════════════ ⑤ 目检图 ═══════════════
def to_png(pdf_path, out_dir, prefix, dpi=118, limit=3):
    """PDF 逐页转 PNG。🔴 出卷后必须 Read 亲自看过——数据对不等于渲染对。"""
    try:
        import fitz
    except ImportError:
        return []
    doc = fitz.open(pdf_path)
    out = []
    for i, pg in enumerate(doc):
        if i >= limit:
            break
        p = os.path.join(out_dir, '_chk_%s_p%d.png' % (prefix, i + 1))
        pg.get_pixmap(dpi=dpi).save(p)
        out.append(p)
    doc.close()
    return out


# ═══════════════ ⑥ 通用闸：题目卷不许泄答案 ═══════════════
# 🔴 **结构层判定，绝不做子串比对**（2026-08-03 五升六册实证）：
#    子串必误报——`\frac{3}{5}` 既是口算①的答案又是脱式④题面的一部分；
#    一道题的某个中间步骤会恰好是另一道题题面的前缀。
#    靠得住的是「答案卷专有标记」：最终答案只经着色/加粗宏出，过程行只经 .ln/.st 出。
ANSWER_ONLY_MARKS = ('\\color{', '\\mathbf{', '答：', '解：',
                     'class="ln"', 'class="st"', 'class="app-sol"',
                     'class="ansv"')          # 学前（preschool）：填空处的红色答案


def leak_guard(html, extra_marks=()):
    """题目卷里出现任何一个答案卷专有标记 = 泄答案，直接 assert 挂掉。"""
    for w in tuple(ANSWER_ONLY_MARKS) + tuple(extra_marks):
        assert w not in html, '🔴 题目卷出现答案卷专有标记「%s」' % w


# ═══════════════ 总编排：一次出双卷 ═══════════════
def render_book(*, out_dir, stem, title, layout, days, ctx=None,
                expect_pages=None, png=False, pt=None):
    """
    出一册（题目卷 + 答案卷两个**独立** PDF）。

      out_dir      册目录（PDF 落这儿，中间件落 out_dir/_源/）
      stem         文件名主干，如「实数计算·十天打卡全册」
      title        HTML <title>
      layout       版式模块（见 layouts/ 的契约）
      days         册子的分天数据，**形状由版式模块自己声明**，core 不解释
      ctx          传给版式的上下文（册名、总天数、accent 等）
      expect_pages 题目卷期望页数；None=不断言。🔴 一天一页的册子应传 len(days)
      png          是否转目检图

    返回 {'question': {...}, 'answer': {...}}，含 path / pages。
    """
    utf8_stdout()
    src = os.path.join(out_dir, '_源')
    os.makedirs(src, exist_ok=True)
    # 🔴 body_pt = **题目正文字号**（2026-08-17 加）。骨架里的 12pt 是当年拍的，
    #    六年级的卷子嫌小；老骨架不认这个参数就自动回落，行为不变。
    body_pt = (ctx or {}).get('body_pt')
    try:
        css = layout.css(pt, body_pt) if body_pt else (layout.css(pt) if pt else layout.css())
    except TypeError:
        css = layout.css(pt) if pt else layout.css()
    ctx = dict(ctx or {})
    report = {}

    for key, ans, suffix in (('question', False, ''), ('answer', True, '（答案）')):
        body = ''.join(layout.render_card(i, d, ans, ctx)
                       for i, d in enumerate(days))
        html = build_html(title, css, body, ans)
        if not ans:
            leak_guard(html, getattr(layout, 'EXTRA_LEAK_MARKS', ()))
            if hasattr(layout, 'guard'):
                layout.guard(html, days, ctx)          # 版式自己的闸（如版面宽度）
        hp = os.path.join(src, '_%s%s.html' % (stem, suffix))
        pp = os.path.join(out_dir, '%s%s.pdf' % (stem, suffix))
        with open(hp, 'w', encoding='utf-8') as fh:
            fh.write(html)
        to_pdf(hp, pp)
        n = page_count(pp)
        report[key] = {'path': pp, 'pages': n,
                       'png': to_png(pp, src, key) if png else []}
        print('  %d 页  %s' % (n, os.path.basename(pp)))

    q = report['question']['pages']
    if expect_pages is not None:
        assert q == expect_pages, \
            '🔴 页数断言失败：题目卷 %d 页 ≠ 期望 %d 页' % (q, expect_pages)
        print('  🟢 页数断言通过：题目卷 %d 页' % q)
    stray_page_guard(report, len(days))
    return report


def stray_page_guard(report, day_count):
    """🔴 **残页闸**（2026-08-17 加）—— 页数断言管不着的那一类事故。

    页数断言只数**题目卷**的纸。踩过两次的坑都在**答案卷**：
    答案卡是 `height:auto` 连排的，某一天比 A4 高一点点，尾巴就被挤成
    **一张只印着半截答语和页码的白纸**，夹在册子中间。两次都是人肉目检才发现的：
      · 第 8 天：整页只有「— 8 —」5 个字符；
      · 第 2 天：51 个字。根因不是"高一点点"，是**答案卷把题面里的两张线段图整个重印了**
        （`fill` 槽位在答案卷会重印题面；图一重印就多出 122pt）——
        改走 `judge` + `word_multi` 只留算式行才压回一页。

    判据 = **字数**，不是页数：正常一天的答案页 370~780 字，被挤出来的残页 51 字，
    中间是空的，阈值取 150 两边都不沾。⚠️ 别调到 40 —— 那次就漏掉了 51 字那张。

    只报不拦（各册自己决定要不要 assert）：有的册子答案确实需要两页。
    """
    try:
        import fitz
    except ImportError:
        return True
    ok = True
    d = fitz.open(report['answer']['path'])
    for i, page in enumerate(d, 1):
        body = ''.join(page.get_text().split())
        if len(body) < 150:
            ok = False
            print('  🔴 答案卷第 %d 页只有 %d 字 → 前一天的答案卡比 A4 高，'
                  '把尾巴挤成了残页：%s' % (i, len(body), body[:36]))
    n = report['answer']['pages']
    if n > day_count and ok:
        print('  ⚠️ 答案卷 %d 页 > %d 天：有天用了两页，确认是有意的（题多过程长）'
              % (n, day_count))
    if ok:
        print('  🟢 残页闸通过：答案卷 %d 页' % n)
    return ok
