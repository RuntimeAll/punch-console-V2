# -*- coding: utf-8 -*-
"""
骨架 `daily_v1` —— 每日一练定版（🔴 **本库默认模版**，2026-08-03 用户拍板）
==========================================================================
移植自**线上主题 `punch-v1`**（`codeplace-O/.../export-themes/punch-v1/punch-v1.html`，
三升四《每日一练》线上就长这样），并按用户要求做了六处定制。

🔴 **定制之后它不再等于线上 punch-v1**（页码替天数、水印可拔插、标题小标题参数化）。
   本地交付件走本骨架；线上阅读页仍是 punch-v1。要让线上也变成这样，
   **得开 PRD 卡把主题文件改了走部署链**，不是本地改完就完事。
   （根治方案 = PRD-017「本地与线上同源消费主题文件」，🟢 dev 全绿、未上 prod。）

## 六处定制（用户 2026-08-03 逐条点的）

| # | 要求 | 参数 |
|---|---|---|
| 1 | 标题 = 年级 + 当前阶段 + **《练习册类型》** + **（第N天）** | `title_parts` / `accent`（第N天骨架自动追加） |

🔴 **标题字符串里不许塞空格**：中文标题连排即可（`title_join` 缺省 `''`），
断句靠书名号《》与括号（）本身。混用半角/全角空格 = 一行里三种间距，读着碎。
真要留白调 CSS `letter-spacing`，别改字符串。
| 2 | 小标题 = 时间 + 教材 + 类型，**浅灰、不加粗不标红** | `subtitle_parts` |
| 3 | 今日目标**弹性**（可留可去） | `show_goals`（缺省 True；该天没 goals 自动不出） |
| 4 | 四个框各对应不同题型、各自填不同内容 | `sections[].box` + `sections[].slot` |
| 5 | 天数改**页码**，且**居中** | 自动，`page_no` |
| 6 | 水印**拔插式、可移除** | `watermark`（None=彻底移除 / str=换文字 / dict=换文字+图） |

🔴 **水印口径（2026-08-03 用户点名）：网盘交付版 `watermark=None` 无水印，
只有小红书公开预览图才带水印。** 客户花钱买的资料卷面带广告 = 减损体验；
公开露出的图不带水印 = 白送给盗图的。**两者目的相反，别用同一份。**

## 四个框（`box`）分别长什么样 —— 照搬线上

| box | 排布 | 作答留白 | 典型题型 |
|---|---|---|---|
| `oral` | 5 列 × N 行，行距 3.6mm | 无（就地写得数） | 口算 |
| `vertical` | 5 列一行 | **38mm**（竖式最占地方） | 列竖式计算 |
| `stepwise` | 4 列一行 | **33mm** | 脱式计算 |
| `app` | 单栏、每题独占 | **每题 24mm** | 应用题 / 轮换位长题面 |

🔴 长题面必须用 `app`（单栏）——`oral`/`vertical`/`stepwise` 是多栏网格，
长题面进去会被从中间劈开（线上踩过，实测把数学式劈成 `5-|a-` / `1|`）。

🔴 **学科无关**：科学要用直接挂 `renderers.get('science')`。
"""
from .. import core

SPEC = {
    'key': 'daily_v1',
    'name': '每日一练定版（默认）',
    '学科': '通用',
    '长相': '整页外框；居中大标题（可红字 accent）+ 小标题；班级/姓名/日期栏；'
            '今日目标条（可关）；四个横向分隔的题目框；**页码居中**页脚；水印可拔插',
    '适合': '🔴 **默认模版**。结构完整、仪式感强、与线上阅读页同源血统；'
            '口算/竖式/脱式/应用题四段式的每日一练首选',
    '每页': '1 天',
    '槽位': '由 ctx["sections"] 逐节指定；每节还要选一个 box（oral/vertical/stepwise/app）',
    '旋钮': 'title_parts(第N天自动追加,可 day_in_title=False 关)｜subtitle_parts(浅灰)｜'
            'accent(主标题红字,子串命中)｜show_goals｜watermark(None可移除)｜'
            'sections[].box｜sections[].work=留白mm｜sections[].count_label｜'
            'sections[].ans_cols=答案卷该节压成几列(解答链长的节降到2列才读得下)',
    '数据形状': 'days = [day, ...]；day = [第1节items, ...]，与 ctx["sections"] 等长。'
                '（与 dense_sections / boxed_sections 同契约 → 三者可一行互换）',
    '用过的册': '（新立，源自线上 punch-v1 = 三升四每日一练）',
}

WORK_MM = {'oral': 0, 'vertical': 38, 'stepwise': 33, 'app': 24}
COLS = {'oral': 5, 'vertical': 5, 'stepwise': 4, 'app': 1}

CSS = """
  @page { size: A4; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 210mm; }
  /* 🔴 Times 在前：数字/小数点走西文字形（SimSun 半角句点在 12pt 下点小距宽，
     小数「3.5」会视觉断成「3. 5」——线上审计批过），汉字回落 SimSun 不受影响 */
  body { font-family: "Times New Roman","SimSun",serif; color: #000; }

  .sheet { width: 210mm; height: 297mm; padding: 10mm 9mm; position: relative;
           page-break-after: always; }
  .sheet:last-child { page-break-after: auto; }
  .frame { border: 1.2pt solid #000; height: 100%; position: relative;
           display: flex; flex-direction: column; }

  /* ① 标题：年级 + 阶段 + 类型 + 时间 */
  .head { border-bottom: 1.2pt solid #000; padding: 3.6mm 0 2.6mm; text-align: center; }
  .head h1 { font-family: "SimHei", sans-serif; font-size: __H1__pt;
             letter-spacing: 1px; white-space: nowrap; }
  .head h1 .red { color: #d0021b; }
  /* 🔴 答案卷标题要**主动让位**：题目卷的标题已经快占满版心（20 字 × 23pt ≈ 162mm，
     版心 190mm），再挂 4 个字的「参考答案」必然超宽 —— 而 h1 是 nowrap，
     超宽不会折行，会直接把 .frame 顶破，左右边框一起跑到纸外（实拍到过）。
     所以答案卷整体缩一档，并把「参考答案」做成 small。 */
  .head h1 small { font-family: "SimSun", serif; font-size: .62em; font-weight: 400;
                   margin-left: 4mm; letter-spacing: 2px; }
  /* ② 小标题：时间 + 教材 + 类型。🔴 浅灰、不加粗、不标红（2026-08-03 用户点名改）
     —— 红字只留给主标题的 accent 一处，小标题也标红会跟主标题抢焦点。 */
  .head .sub { font-size: 10.5pt; color: #999; letter-spacing: .5px; margin-top: 1.6mm;
               font-weight: 400; }

  .info { display: flex; justify-content: space-around; align-items: baseline;
          font-size: 11.5pt; padding: 2.6mm 8mm; border-bottom: 1.2pt solid #000; }
  .info u { text-decoration: none; border-bottom: .8pt solid #000;
            display: inline-block; min-width: 24mm; }

  /* ③ 今日目标（弹性：show_goals=False 或当天无 goals 则整条不出） */
  .goal { font-size: 10pt; padding: 2mm 4mm; border-bottom: 1.2pt solid #000;
          line-height: 1.5; }
  .goal b { font-family: "SimHei", sans-serif; margin-right: 2mm; }
  .goal span { margin-right: 3.5mm; white-space: nowrap; }

  /* ③′ 今日必读 —— 当天的知识点/方法/易错，先讲再练（2026-08-17 加）
     🔴 它不是"目标条"的加长版：目标条是**列今天要过的考点名**，
        必读是**把今天的方法讲清楚**——学生可能压根还没学到这一节。 */
  .brief { padding: 2.2mm 4mm 2.4mm; border-bottom: 1.2pt solid #000;
           line-height: 1.62; background: #fafafa; }
  .brief .bt { font-family: "SimHei", sans-serif; font-size: 11pt;
               margin-bottom: .8mm; }
  .brief .bl { font-size: 10.5pt; text-indent: -1.4em; padding-left: 1.4em; }
  .brief .bl b { font-family: "SimHei", sans-serif; }
  .brief .warn { color: #c0272d; }

  /* ④ 四个题目框 */
  section { border-bottom: 1.2pt solid #000; padding: 2.2mm 4mm 2.5mm; }
  section.last { border-bottom: none; flex: 1; }
  h2 { font-family: "SimHei", sans-serif; font-size: 12.5pt; margin-bottom: 1.8mm; }
  h2 small { font-family: "SimSun", serif; font-size: 10.5pt; font-weight: 400; }
  h2 small.hint { color: #666; margin-left: 1mm; }

  .grid { display: grid; }
  .grid.oral { grid-template-columns: repeat(5,1fr); row-gap: 3.6mm; font-size: __Q__pt; }
  .grid.c5 { grid-template-columns: repeat(5,1fr); column-gap: 3mm; row-gap: 5mm;
             font-size: __Q__pt; }
  /* 🔴 row-gap 不能省：填空/计算题多到换行时，两行会贴在一起（2026-08-17 实拍） */
  .grid.c4 { grid-template-columns: repeat(4,1fr); column-gap: 3mm; row-gap: 5mm;
             font-size: __Q__pt; }
  .app { font-size: __Q__pt; line-height: 1.7; }
  .work { }

  /* ⑤ 页脚：页码居中（线上是左下角天数，本骨架按用户要求改） */
  .foot { display: flex; align-items: center; padding: 1.6mm 4mm;
          font-size: 10pt; color: #444; }
  .foot .l, .foot .r { flex: 1; }
  .foot .r { text-align: right; }
  .foot .pageno { flex: 0 0 auto; text-align: center; letter-spacing: 1px; }
  /* ⑥ 水印：拔插式。watermark=None 时这段整个不出现 */
  .wm { font-family: "SimHei", sans-serif; color: #666; letter-spacing: 1px; }
  .wm img { height: 1.15em; vertical-align: -0.22em; margin-right: 3px; }

  /* ══ 解析卷 ══ */
  body.asheet .head h1 { font-size: __H1A__pt; }
  body.asheet .work { display: none !important; }
  body.asheet .grid.oral { row-gap: 3.2mm; font-size: __QA__pt; }
  body.asheet .grid.c5, body.asheet .grid.c4 { font-size: __QA__pt; }
  body.asheet .app { font-size: __QA__pt; line-height: 1.6; }
  body.asheet .sheet { height: auto; }
  body.asheet .frame { height: auto; }
  body.asheet section.last { flex: none; }
"""

CN = '一二三四五六七八九十'


def cn(n):
    """1..99 的中文数字（🔴 别退回 `CN[i]` 取字符：那样第 11 天就 IndexError，
    实伤过——20 天的册子出到第 11 页整个渲染挂掉）。"""
    assert 1 <= n <= 99, '天序超出中文数字范围：%r' % n
    if n <= 10:
        return CN[n - 1]
    t, o = divmod(n, 10)
    return ('' if t == 1 else CN[t - 1]) + '十' + ('' if o == 0 else CN[o - 1])


def css(pt=None, body_pt=None):
    """pt = 主标题字号（缺省 23）；body_pt = **题目正文字号**（缺省 12，答案卷自动 −1）。

    🔴 body_pt 是 2026-08-17 加的：原来题目正文写死 12pt，六年级的卷子嫌小、
       填空题的括号更显挤。不传就还是 12，老册子一个像素都不动。
    """
    from ..renderers import math as _default
    h1 = float(pt or 23.0)
    q = float(body_pt or 12.0)
    return (CSS.replace('__H1__', '%.1f' % h1)
               .replace('__H1A__', '%.1f' % (h1 * 0.84))
               .replace('__Q__', '%.1f' % q)
               .replace('__QA__', '%.1f' % (q - 1.0)) + _default.CSS)


def _title(ctx, idx):
    """① 标题 = 年级 + 当前阶段 + 《练习册类型》 + **第N天**

    🔴 **「第N天」由骨架自动追加**（2026-08-03 用户澄清：标题里那个"时间"指的是
       第一天/第二天，不是年份）—— 它随天变，不能写死在 `title_parts` 里。
       不想要就传 `day_in_title=False`。
    🔴 练习册类型建议**用《》框起来**（`'《每日一练》'`），书名号前后自动不留空。
    accent 是**子串命中词**：必须真出现在标题里，否则整行全黑。
    """
    # 🔴 **中文标题不用空格分词**（2026-08-03 用户点破："文字里直接加空格，看起来不舒服"）：
    #    原先 join=' ' 半角空格 + 《》前后无空格 + 天序前全角空格 = **三种间距混在一行**，
    #    读起来很碎。中文标题连排即可，断句靠书名号与括号本身。
    #    真要留白就调 CSS letter-spacing，别往字符串里塞空格。
    # 🆕 `title_parts_of(idx)` = **随天变的标题**（2026-08-17 加，与 goals_of/subtitle_of 同套路）：
    #    分段册（前几天练乘法、中间练除法、后面练混合）**每天的标题该说今天练什么**——
    #    整册一个静态标题，会让只教乘法的那天顶着「分数乘除法」，名实不符（用户点出来的）。
    dyn = (ctx.get('title_parts_of') or (lambda i: None))(idx)
    parts = [p for p in (dyn if dyn else ctx.get('title_parts', [])) if p]
    t = ctx.get('title_join', '').join(parts)
    if ctx.get('day_in_title', True):
        # 天序进括号（与两份实体教辅原图一致：「…每日一练（第1天）」）
        t += ctx.get('day_fmt', '（第%s天）') % cn(idx + 1)
    acc = ctx.get('accent', '')
    if acc and acc in t:
        t = t.replace(acc, '<span class="red">%s</span>' % acc, 1)
    return t


def _subtitle(ctx, idx=0):
    """② 小标题 = 时间 + 教材 + 类型。
    🔴 **整条浅灰、不加粗、不标红**（2026-08-03 用户点名改）——
       红字只留给主标题的 accent 一处，小标题再标红会跟主标题抢焦点。

    🆕 `subtitle_of(idx)` = **随天变的小标题**（2026-08-17 加，与 `goals_of` 同一个套路）：
       大标题只放书名、把「第N天」降到小标题时需要它 —— 静态的 `subtitle_parts`
       会让全册每一页都印「第一天」。给了 `subtitle_of` 就以它为准，没给才回落静态那份。
    """
    dyn = (ctx.get('subtitle_of') or (lambda i: None))(idx)
    parts = [p for p in (dyn if dyn else ctx.get('subtitle_parts', [])) if p]
    if not parts:
        return ''
    return '<div class="sub">%s</div>' % ctx.get('subtitle_join', '　·　').join(parts)


def _watermark(ctx):
    """⑥ 水印拔插：None=彻底移除 / str=只换文字 /
    dict={'text','img':True,'color':'#7a7a7a','opacity':'0.7'}

    🔴 `color` / `opacity` 是给**小红书 A/B 双版本**用的（一号一版，绑定后不换）：
       同一份内容出深浅两套图，避免两个号的图被平台判重。
       ⚠️ 只许动水印的深浅和导出 dpi，**绝不动版式与内容** —— 改边距/字号会重排分页，
       可能把某天挤成两页。
    """
    wm = ctx.get('watermark', '玉米训练营')
    if not wm:
        return ''
    if isinstance(wm, str):
        wm = {'text': wm, 'img': True}
    img = core.watermark_img() if wm.get('img', True) else ''
    if img and wm.get('opacity'):
        img = img.replace('<img ', '<img style="opacity:%s" ' % wm['opacity'])
    style = (' style="color:%s"' % wm['color']) if wm.get('color') else ''
    return '<span class="wm"%s>%s%s</span>' % (style, img, wm.get('text', ''))


def _sheet(idx, secs, data, ans, ctx, page_no, first):
    """渲一张纸。first=True 的那张才有信息栏与今日必读（续页不重复）。"""
    R = ctx['renderer']
    o = ['<div class="sheet"><div class="frame">',
         '<div class="head"><h1>%s%s</h1>%s</div>'
         % (_title(ctx, idx) + ('' if first else ctx.get('cont_mark', '（续）')),
            '<small>参考答案</small>' if ans else '', _subtitle(ctx, idx) if first else '')]

    if first and not ans:
        o.append('<div class="info">班级：<u></u>姓名：<u></u>日期：<u></u></div>')
        goals = (ctx.get('goals_of') or (lambda i: None))(idx)
        if ctx.get('show_goals', True) and goals:
            o.append('<div class="goal"><b>今日目标</b>%s</div>'
                     % ''.join('<span>%s%s</span>' % ('①②③④⑤'[j] if j < 5 else '·', g)
                               for j, g in enumerate(goals)))
        brief = (ctx.get('brief_of') or (lambda i: None))(idx)
        if brief:
            o.append('<div class="brief"><div class="bt">%s</div>%s</div>'
                     % (brief.get('title', '今日必读'),
                        ''.join('<div class="bl">%s</div>' % ln
                                for ln in brief.get('lines', []))))

    for si, sec in enumerate(secs):
        grp = data[si]
        box = sec.get('box', 'app')
        last = ' last' if si == len(secs) - 1 else ''
        o.append('<section class="%s">' % last.strip())
        label = ('<small>（共 %d 道）</small>' % len(grp)) if sec.get('count_label', True) else ''
        hint = ('<small class="hint">%s</small>' % sec['hint']) if sec.get('hint') else ''
        o.append('<h2>%s、%s %s%s</h2>' % (sec.get('cn', ''), sec['name'], label, hint))
        cls = {'oral': 'grid oral', 'vertical': 'grid c5',
               'stepwise': 'grid c4', 'app': 'app'}[box]
        parts = [R.SLOTS[sec['slot']](it, i, ans, ctx) for i, it in enumerate(grp)]
        if box == 'app':
            work = sec.get('work', WORK_MM['app'])
            o.append('<div class="app">%s</div>'
                     % ''.join(p + ('<div class="work" style="height:%gmm"></div>' % work)
                               for p in parts))
        else:
            # 🆕 `cols` = **题目卷**这一节压成几列（缺省跟着 box 走）。
            #    🔴 为什么要它：填空题里「\\frac{7}{20} 米＝（ ）厘米」这类**带单位的长题面**
            #    在 4 列格子里会把「厘米」折到下一行（2026-08-17 实拍）。宽题面就给它 3 列。
            cols = sec.get('ans_cols') if ans else sec.get('cols')
            st = (' style="grid-template-columns:repeat(%d,1fr)"' % cols) if cols else ''
            o.append('<div class="%s"%s>%s</div>'
                     % (cls, st, ''.join('<div>%s</div>' % p for p in parts)))
            work = sec.get('work', WORK_MM[box])
            if work:
                o.append('<div class="work" style="height:%gmm"></div>' % work)
        o.append('</section>')

    o.append('<div class="foot"><span class="l"></span>'
             '<span class="pageno">— %d —</span>'
             '<span class="r">%s</span></div>' % (page_no, _watermark(ctx)))
    o.append('</div></div>')
    return ''.join(o)


def render_card_multi(idx, data, ans, ctx):
    """🆕 **一天两页**（2026-08-17 用户拍板：「一页不够就加一页，一天两页」）。

    `split_of(idx)` = 第 1 页放前几节；返回 None / 0 就还是一天一页。
    🔴 续页不重复信息栏与今日必读——那两块是"今天"的，一天只该出现一次；
       但标题要留（撕下来两张纸不至于认不出是哪天）。
    🔴 页码按**纸**走，不按天走：一天两页时第 N 天 = 第 2N-1、2N 页。
    """
    secs = (ctx.get('sections_of') or (lambda i: None))(idx) or ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 节，与该天 sections 的 %d 节不符' % (idx + 1, len(data), len(secs))
    # 节序号（一、二、三…）跨页连续编，别每页从「一」重来
    secs = [dict(s, cn=CN[i]) for i, s in enumerate(secs)]

    k = (ctx.get('split_of') or (lambda i: None))(idx)
    if not k or ans:                      # 答案卷不分页（height:auto，本来就连排）
        return _sheet(idx, secs, data, ans, ctx, idx + 1, True)
    assert 0 < k < len(secs), '🔴 第%d天 split_of=%r 不在 1..%d 之间' % (idx + 1, k, len(secs) - 1)
    return (_sheet(idx, secs[:k], data[:k], ans, ctx, 2 * idx + 1, True)
            + _sheet(idx, secs[k:], data[k:], ans, ctx, 2 * idx + 2, False))


render_card = render_card_multi          # 🔴 对外入口 = 支持一天多页的那个


def _render_card_legacy(idx, data, ans, ctx):
    """一天一页的原实现，留作参照（现由 render_card_multi 统一接管，split_of 不给就等价）。

    idx  第几天（0 起）  data 该天 = [第1节items, ...]  ctx 见 SPEC['旋钮']
    """
    R = ctx['renderer']
    # 🆕 `sections_of(idx)` = **每天各自的分节配置**（2026-08-17 加）。
    #    🔴 起因（用户原话）：「题型设计不应该有一个通用的模版，所有的都应该为今日打卡完成度负责」——
    #    今天学分数乘整数就该出口算+计算，今天学量率对应就该几乎全是应用题，
    #    用一张全册通用的 sections 表硬套，等于让版面反过来决定教学内容。
    secs = (ctx.get('sections_of') or (lambda i: None))(idx) or ctx['sections']
    assert len(data) == len(secs), \
        '🔴 第%d天有 %d 节，与该天 sections 的 %d 节不符' % (idx + 1, len(data), len(secs))

    o = ['<div class="sheet"><div class="frame">',
         '<div class="head"><h1>%s%s</h1>%s</div>'
         % (_title(ctx, idx), '<small>参考答案</small>' if ans else '', _subtitle(ctx, idx))]

    if not ans:
        o.append('<div class="info">班级：<u></u>姓名：<u></u>日期：<u></u></div>')

    # ③ 今日目标：弹性
    goals = (ctx.get('goals_of') or (lambda i: None))(idx)
    if ctx.get('show_goals', True) and goals and not ans:
        o.append('<div class="goal"><b>今日目标</b>%s</div>'
                 % ''.join('<span>%s%s</span>' % ('①②③④⑤'[j] if j < 5 else '·', g)
                           for j, g in enumerate(goals)))

    # ③′ 今日必读：{'title': '…', 'lines': ['…', '…']}，行内可写 <b>/<span class="warn">
    brief = (ctx.get('brief_of') or (lambda i: None))(idx)
    if brief and not ans:
        o.append('<div class="brief"><div class="bt">%s</div>%s</div>'
                 % (brief.get('title', '今日必读'),
                    ''.join('<div class="bl">%s</div>' % ln
                            for ln in brief.get('lines', []))))

    # ④ 四个题目框
    for si, sec in enumerate(secs):
        grp = data[si]
        box = sec.get('box', 'app')
        last = ' last' if si == len(secs) - 1 else ''
        o.append('<section class="%s">' % last.strip())
        label = ('<small>（共 %d 道）</small>' % len(grp)) if sec.get('count_label', True) else ''
        # 🔴 `hint` 只放**教材通用指令**（「能简便的要简便」「得数化成最简分数」这类，
        #    人教教材原文就这么写）。绝不能放点破本节设计的话
        #    —— 「最后两题先约分再算」那种等于把答案思路直接告诉学生，这题就废了一半。
        hint = ('<small class="hint">%s</small>' % sec['hint']) if sec.get('hint') else ''
        o.append('<h2>%s、%s %s%s</h2>' % (CN[si], sec['name'], label, hint))
        cls = {'oral': 'grid oral', 'vertical': 'grid c5',
               'stepwise': 'grid c4', 'app': 'app'}[box]
        parts = [R.SLOTS[sec['slot']](it, i, ans, ctx) for i, it in enumerate(grp)]
        if box == 'app':
            work = sec.get('work', WORK_MM['app'])
            o.append('<div class="app">%s</div>'
                     % ''.join(p + ('<div class="work" style="height:%gmm"></div>' % work)
                               for p in parts))
        else:
            # 🔴 **每道题必须自己裹一层 div**：CSS grid 是按**直接子元素**分格的，
            #    而 equation 槽位在答案卷一道题要返回「题面 + 解：… + 逐行」好几个兄弟 div
            #    —— 不裹就会被拆到四个格子里，第①题的题面在第 1 格、它的答案在第 4 格，
            #    整节答案彻底错位（2026-08-04 全册目检实拍；dense_sections 早踩过同一个坑）。
            cols = sec.get('ans_cols') if ans else None
            st = (' style="grid-template-columns:repeat(%d,1fr)"' % cols) if cols else ''
            o.append('<div class="%s"%s>%s</div>'
                     % (cls, st, ''.join('<div>%s</div>' % p for p in parts)))
            work = sec.get('work', WORK_MM[box])
            if work:
                o.append('<div class="work" style="height:%gmm"></div>' % work)
        o.append('</section>')

    # ⑤ 页码居中 + ⑥ 水印（可移除）
    o.append('<div class="foot"><span class="l"></span>'
             '<span class="pageno">— %d —</span>'
             '<span class="r">%s</span></div>' % (idx + 1, _watermark(ctx)))
    o.append('</div></div>')
    return ''.join(o)
