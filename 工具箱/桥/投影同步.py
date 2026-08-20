"""投影同步 —— 把 kb.db（活）+ 资料库.db（冻结存档）单向投影成 punch-console 的只读展示库。

产出：知识库/资料库-投影.db（新文件；两个上游库一律 mode=ro 只读打开，一个字节不改）。

为什么要有这一层（别删这段，下次想"直接让 punch 读 kb.db"时先读完）：
  punch-console 是**冻结只读仓**（PRD-003 拍板并入 v2，代码一个字节不许改），
  它的 SQL 全部写死在 doc/question/material/asset/doc_member 五张中文列名表 + question_fts 上。
  kb.db 的形状完全不同（artifact/paper/paper_item/blocks_json/字符串 id）。
  两边对不上，又不许改代码 —— 那就只能**把 kb 的数据摆成 punch 认识的样子**，
  摆进一个**独立的新库**里。这就是投影库。

🔴 单向：投影库是**下游**，随时可被本脚本整个重建。
   任何在页面上写进投影库的东西（punch 唯一的写端点 /api/doc-state 改 doc.人工态）
   **下次同步就没了** —— 真改动一律回 :4300/agent 走 kb.db。

🔴 幂等：重跑 = 删掉投影库整个重建。没有增量、没有 upsert、不留脏行。

用法：
    python 工具箱\\桥\\投影同步.py            # 全量重建
    python 工具箱\\桥\\投影同步.py --out X.db  # 换个落点（调试用）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

# ------------------------------------------------------------------ 路径口径

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FROZEN = os.path.join(ROOT, "知识库", "资料库.db")   # 冻结存档，只读
KB = os.path.join(ROOT, "知识库", "kb.db")            # 活库，只读
OUT_DEFAULT = os.path.join(ROOT, "知识库", "资料库-投影.db")

# 新 artifact 投影成 doc 时的 id 起点。
# 🔴 punch 的 doc.id / question.id 都是 INTEGER PRIMARY KEY（rowid 别名），
#    而 kb 的 id 是字符串（A2026.../q2026...）—— 塞不进去，页面也拿 Number(id) 解析。
#    所以按**确定序**分配整数 id：同一份上游数据重跑必得同一套 id（幂等的命根子）。
DOC_ID_BASE = 90000
QID_BASE = 1_000_000
ASSET_ID_BASE = 1_000_000

# 新册一律七上数学（本批 30 张 v2 artifact 全是浙教七上有理数线的出品）
NEW_SUBJECT = "数学"
NEW_GRADE = "七年级上册"

# artifact.kind → punch doc.类型（punch 只认这六类）
KIND2TYPE = {
    "打卡册": "打卡",
    "专项卷": "专项",
    "讲义": "讲义",
    "举一反三": "专项",
    "报告模版": "其他",
    "其他": "其他",
}

# source_line → 组名（页面按组名折叠，产线名正好是最有用的那层归属）
LINE2GROUP = {
    "试卷复刻": "七上试卷复刻",
    "平行出卷": "平行卷（已退役）",
    "浙教出卷": "浙教出卷·七上有理数",
    "浙教配方出卷（窗G）·发布包": "浙教出卷·发布包",
    "出卷流水线总验收": "出卷流水线总验收",
    "每日打卡": "七上有理数五天打卡",
}


# ------------------------------------------------------------------ FTS 分词

# 🔴 逐字照抄 punch-console/web/src/db/fts.ts 的口径（中文 bigram + 英数原样）。
#    查询端用的是那份 TS，索引端用的是这份 py —— **两把切法必须一致**，
#    差一个字符类，搜出来就是空的，而且不报错（最难查的那种坏）。
_CJK = re.compile(r"[㐀-䶿一-鿿぀-ヿ豈-﫿]")
_ALNUM = re.compile(r"[0-9A-Za-z]")


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    s = unicodedata.normalize("NFKC", text or "")
    buf: list[str] = []
    cjk: list[str] = []

    def flush_alnum() -> None:
        if buf:
            out.append("".join(buf).lower())
            buf.clear()

    def flush_cjk() -> None:
        if not cjk:
            return
        if len(cjk) == 1:
            out.append(cjk[0])
        else:
            for i in range(len(cjk) - 1):
                out.append(cjk[i] + cjk[i + 1])
        cjk.clear()

    for ch in s:
        if _CJK.match(ch):
            flush_alnum()
            cjk.append(ch)
        elif _ALNUM.match(ch):
            flush_cjk()
            buf.append(ch)
        else:
            flush_alnum()
            flush_cjk()
    flush_alnum()
    flush_cjk()
    return out


def to_fts_text(text: str) -> str:
    return " ".join(tokenize(text))


# ------------------------------------------------------------------ 小工具


def ro(path: str) -> sqlite3.Connection:
    """🔴 上游一律 mode=ro 打开：物理上写不进去，比"我保证不写"可靠。"""
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def jload(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def abspath_of(rel: str) -> str:
    """v2 相对指针 → 本机绝对路径（反斜杠）。punch 的图/PDF 面板按 `\\` 切目录名。"""
    return os.path.join(ROOT, rel.replace("/", os.sep))


def stem_of(blocks_json: str) -> str:
    """blocks 块流 → punch 的一行 stem 文本。

    取**全部** role='题面' 的 text/table 块按序拼接（不是只取首个）：
    323 道新题里 34 道是多行题面（带表格、带 (1)(2)(3) 小问），
    只取首行会把小问全吃掉 —— 那样页面上的题是残的，FTS 也搜不到小问里的词。
    选项不并入：它在 blocks 里是独立的 option cell，punch schema 无处安放。
    """
    b = jload(blocks_json) or {}
    parts: list[str] = []
    for row in b.get("rows", []):
        for cell in row.get("cells", []):
            if cell.get("type") in ("text", "table") and cell.get("role") == "题面":
                md = (cell.get("md") or "").strip()
                if md:
                    parts.append(md)
    if parts:
        return "\n".join(parts)
    # 兜底：没有标 role 的，退回第一个 text 块
    for row in b.get("rows", []):
        for cell in row.get("cells", []):
            if cell.get("type") == "text" and (cell.get("md") or "").strip():
                return cell["md"].strip()
    return ""


# ------------------------------------------------------------------ 建库


def build_schema(out_path: str, frozen: sqlite3.Connection) -> sqlite3.Connection:
    """整个删掉重建。表结构逐字照抄冻结库（含中文列名与唯一索引），FTS 另建。"""
    for suffix in ("", "-wal", "-shm"):
        p = out_path + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
            except PermissionError:
                # :3000 起着的时候 better-sqlite3 攥着这个文件句柄（进程内单例），
                # Windows 下正被占用的文件删不掉 —— 报人话，别甩 WinError 32。
                raise SystemExit(
                    f"[X] 投影库正被占用，删不掉：{p}\n"
                    f"    多半是 punch-console(:3000) 还开着。先停服再重跑：\n"
                    f"    Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" |\n"
                    f"      Where-Object {{ $_.CommandLine -like '*next*start*' }} |\n"
                    f"      ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"
                )

    d = sqlite3.connect(out_path)
    d.row_factory = sqlite3.Row
    d.execute("PRAGMA journal_mode = WAL")
    d.execute("PRAGMA foreign_keys = OFF")

    ddl = frozen.execute(
        """SELECT type, name, sql FROM sqlite_master
           WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
             AND name NOT LIKE 'question_fts%'
           ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name"""
    ).fetchall()
    for r in ddl:
        d.execute(r["sql"])
    # FTS5 虚表：口径与 fts.ts 的 ensureFts 一致
    d.execute("CREATE VIRTUAL TABLE question_fts USING fts5(stem, tokenize='unicode61')")
    d.commit()
    return d


# ------------------------------------------------------------------ 产物文件索引


def index_product_files() -> dict[str, list[str]]:
    """扫 产物/验收 与 产物/打卡 下的成品 PDF，按**文件名主干**建索引。

    排除 `_源/`：那底下是渲染中间件（html/json/逐页校对图），不是成品。
    """
    idx: dict[str, list[str]] = defaultdict(list)
    for base in (os.path.join(ROOT, "产物", "验收"), os.path.join(ROOT, "产物", "打卡")):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x != "_源"]
            for fn in filenames:
                if fn.lower().endswith(".pdf"):
                    idx[os.path.splitext(fn)[0]].append(os.path.join(dirpath, fn))
    for k in idx:
        idx[k].sort()
    return idx


def classify_pdf(stem: str) -> str:
    """文件名判卷型。答案卷的两种写法：`xxx（答案）` 与 `xxx·答案卷`。"""
    return "答案卷" if ("（答案）" in stem or "答案卷" in stem) else "题目卷"


def find_pic_dir(files: list[str]) -> str | None:
    """发布包的配图目录：从成品件的公共父目录往上找带 `图/` 的那一层。

    🔴 不能写死成 `dirname(dirname(第一个件))`：批1（全套10套）的 PDF 按章分了子目录
    （`网盘件/01 第1章…/x.pdf`），比批2/批3 深一层，写死就会把 11 张配图全漏掉。
    """
    common = os.path.dirname(files[0]) if len(files) == 1 else os.path.commonpath(files)
    for _ in range(4):
        cand = os.path.join(common, "图")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(common)
        if parent == common:
            break
        common = parent
    return None


def pwd_of(link: str | None) -> str | None:
    """网盘链接尾巴上的 `?pwd=xxxx` 就是提取码 —— 页面上那个复制钮最常按的就是它。"""
    m = re.search(r"[?&]pwd=([0-9A-Za-z]+)", link or "")
    return m.group(1) if m else None


# ------------------------------------------------------------------ 主流程


def main() -> int:
    ap = argparse.ArgumentParser(description="把 kb.db + 冻结资料库.db 投影成 punch-console 只读展示库")
    ap.add_argument("--out", default=OUT_DEFAULT, help="投影库落点")
    args = ap.parse_args()

    for p in (FROZEN, KB):
        if not os.path.isfile(p):
            print(f"[X] 上游库不在：{p}")
            return 2

    frozen = ro(FROZEN)
    kb = ro(KB)
    out = build_schema(args.out, frozen)

    print("=" * 64)
    print("投影同步 · 全量重建")
    print(f"  冻结存档 {FROZEN}")
    print(f"  活库     {KB}")
    print(f"  投影库   {args.out}")
    print("=" * 64)

    warn: list[str] = []

    # ---------------------------------------------------------- ① doc

    # 老册：punch doc id ←→ kb artifact id
    punch_doc = {r["kb_id"]: int(r["punch_id"]) for r in kb.execute(
        "SELECT punch_id, kb_id FROM punch_map WHERE kind='doc'")}
    frozen_doc = {r["id"]: dict(r) for r in frozen.execute("SELECT * FROM doc")}

    arts = [dict(r) for r in kb.execute("SELECT * FROM artifact ORDER BY created_at, id")]
    old_arts = [a for a in arts if a["id"] in punch_doc]
    new_arts = [a for a in arts if a["id"] not in punch_doc]

    doc_rows: list[tuple] = []
    art2doc: dict[str, int] = {}
    retired: list[tuple[str, str]] = []

    DOC_COLS = ("id", "名称", "类型", "组名", "版本名", "科目", "年级", "考点", "册型",
                "人工态", "layout_key", "day_spec", "源文件路径", "网盘链接", "提取码",
                "线上book_id", "备注")

    # —— 老 82 册：冻结行打底，kb artifact 刷新活字段
    for a in old_arts:
        did = punch_doc[a["id"]]
        art2doc[a["id"]] = did
        base = frozen_doc.get(did)
        if base is None:
            warn.append(f"artifact {a['id']} 映射到 punch doc {did}，冻结库里没有这一行")
            continue
        n = jload(a["note"]) or {}
        doc_rows.append((
            did,
            a["name"],                                            # 名称 ← artifact
            n.get("punch_类型") or base["类型"],                   # 类型 ← note
            n.get("组名", base["组名"]),                           # 组名 ← note
            n.get("版本名") or base["版本名"],                     # 版本名 ← note
            n.get("科目") or base["科目"],
            n.get("年级") or base["年级"],                         # note 缺 13 条，退回冻结行
            base["考点"],
            n.get("册型") or base["册型"],
            a["sale_state"],                                      # 人工态 ← sale_state
            base["layout_key"],
            base["day_spec"],
            None,                                                 # 源文件路径：稍后按 v2 副本目录改写
            a["link"],                                            # 网盘链接 ← artifact.link
            n.get("提取码"),                                       # 提取码 ← note
            n.get("线上book_id") or base["线上book_id"],
            json.dumps({"artifact": a["id"], "来源": "冻结资料库 + kb 刷新"}, ensure_ascii=False),
        ))

    # —— 新 30 张 artifact：投影成新 doc 行
    used_nv: set[tuple[str, str]] = {(r[1], r[4]) for r in doc_rows}
    for i, a in enumerate(new_arts, start=1):
        did = DOC_ID_BASE + i
        art2doc[a["id"]] = did
        n = jload(a["note"]) or {}
        是退役 = isinstance(n, dict) and "退役" in n
        if 是退役:
            retired.append((a["id"], a["name"]))

        # 🔴 退役件标**停售**而不是不投：PDF 还在盘上、paper 还在库里，
        #    投影库要能对上 kb 的 112 行（守恒）；停售泳道正好是"退了役的旧件"那一档，
        #    列表默认也不会跟现役件混在一起。
        版本名 = "退役件" if 是退役 else "正本"
        if (a["name"], 版本名) in used_nv:                        # 名称+版本名 是唯一索引
            版本名 = f"{版本名}·{a['id'][-5:]}"
        used_nv.add((a["name"], 版本名))

        备注 = {"artifact": a["id"], "产线": a["source_line"], "kb状态": a["status"]}
        if 是退役:
            备注["退役"] = n.get("退役")
            备注["缘由"] = n.get("缘由")

        doc_rows.append((
            did,
            a["name"],
            KIND2TYPE.get(a["kind"], "其他"),
            LINE2GROUP.get(a["source_line"] or "", a["source_line"]),
            版本名,
            NEW_SUBJECT,
            NEW_GRADE,
            None,                                                 # 考点：稍后由题的 kp 汇总
            "单册",
            "停售" if 是退役 else a["sale_state"],
            None, None, None,
            a["link"],
            (n.get("提取码") if isinstance(n, dict) else None) or pwd_of(a["link"]),
            None,
            json.dumps(备注, ensure_ascii=False),
        ))

    out.executemany(
        f"INSERT INTO doc ({','.join(DOC_COLS)}) VALUES ({','.join('?' * len(DOC_COLS))})",
        doc_rows,
    )
    out.commit()
    print(f"[1] doc      {len(doc_rows):5d} 行（老 {len(old_arts)} + 新 {len(new_arts)}；退役标停售 {len(retired)}）")

    # ---------------------------------------------------------- ② material

    mat_rows = []
    for i, m in enumerate(kb.execute("SELECT * FROM material ORDER BY created_at, id"), start=1):
        did = art2doc.get(m["artifact_id"])
        if did is None:
            warn.append(f"material {m['id']} 的 artifact {m['artifact_id']} 没有对应 doc，丢弃")
            continue
        mat_rows.append((
            i, did, m["account"], m["is_active"], m["title"], m["body"],
            m["topics_json"], m["style_seed"], m["burned"],
            m["product_desc"], m["pan_share_text"], m["created_at"],
        ))
    kb_mat = len(mat_rows)

    # —— 补投影：material 表无行、但 artifact.note 里带宣发 JSON 的 v2 新册
    #
    # 🔴 为什么要补：发布包这类册子的文案（标题候选/正文/标签/商品描述/网盘分享语）是由
    #    「发布物料」skill 直接写进 artifact.note 的，没走 kb 的 material 表。
    #    不补的话详情页「物料 0 · 还没有发帖物料」—— 文案明明齐了却一个字看不到，
    #    而展示台存在的意义就是**手机上把文案复制走去发帖**。
    # 🔴 缺哪个字段留空，不硬造。
    note_mat = 0
    for a in new_arts:
        if kb.execute("SELECT COUNT(*) FROM material WHERE artifact_id=?", (a["id"],)).fetchone()[0]:
            continue                                              # 已有正经 material，不重复投
        n = jload(a["note"])
        if not isinstance(n, dict):
            continue
        if not any(n.get(x) for x in ("标题候选", "正文", "标签", "商品描述", "网盘分享语")):
            continue                                              # 退役缘由那种 note 不算宣发

        cand = n.get("标题候选") or []
        # 标题候选写成 "1. xxx" 的编号前缀是给人挑用的，投进去要去掉
        title = re.sub(r"^\s*\d+[.、]\s*", "", str(cand[0])).strip() if cand else None
        # 🔴 话题词存**不带 # 的裸词**：页面渲染时自己补 #（material-switch 里 `#{t}`），
        #    复制钮输出的也是裸词空格分隔（小红书要在 App 里逐个选，带 # 粘过去不成话题）。
        #    存带 # 的会渲成 ##初一数学。
        tags = [t.lstrip("#").strip() for t in str(n.get("标签") or "").split() if t.strip("#").strip()]

        mat_rows.append((
            kb_mat + note_mat + 1,
            art2doc[a["id"]],
            "A", 1,                                               # 单号首发：账号 A、在用
            title,
            n.get("正文"),
            json.dumps(tags, ensure_ascii=False) if tags else None,
            "宣发note投影",                                        # material 无备注/来源列，标记落在风格种子
            0,
            n.get("商品描述"),
            n.get("网盘分享语"),
            a["created_at"],
        ))
        note_mat += 1

    out.executemany(
        """INSERT INTO material (id, doc_id, 账号, is_active, 标题, 正文, 话题词, 风格种子,
                                 burned, 商品描述, 网盘分享语, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        mat_rows,
    )
    out.commit()
    print(f"[2] material {len(mat_rows):5d} 行（kb.material {kb_mat} + 宣发note投影 {note_mat}）")

    # ---------------------------------------------------------- ③ asset

    # —— 老 735 行：绝对路径从老区改写成 v2 内副本（映射正本 = punch_map kind='asset'）
    amap = {r["punch_id"]: r["kb_id"] for r in kb.execute(
        "SELECT punch_id, kb_id FROM punch_map WHERE kind='asset'")}

    asset_rows = []
    miss_map, miss_file = [], []
    for r in frozen.execute("SELECT * FROM asset ORDER BY id"):
        rel = amap.get(str(r["id"]))
        if not rel:
            miss_map.append((r["id"], r["doc_id"], r["类型"], r["路径"]))
            continue
        ab = abspath_of(rel)
        if not os.path.isfile(ab):
            miss_file.append((r["id"], r["doc_id"], r["类型"], rel))
            continue                                              # 🔴 缺档不硬造，如实少这一行
        asset_rows.append((r["id"], r["doc_id"], r["类型"], ab, r["配图顺序"], r["rendered_at"]))

    # —— 新册产物：先按 files_json（只有 3 张发布包有），再按文件名认领
    pdf_idx = index_product_files()
    claimed: set[str] = set()
    new_assets: list[tuple[int, str, str, int | None]] = []       # (doc_id, 类型, 绝对路径, 配图顺序)

    for a in new_arts:
        did = art2doc[a["id"]]
        files = jload(a["files_json"])
        if not files:
            continue
        for rel in files:
            ab = abspath_of(rel)
            if not os.path.isfile(ab):
                miss_file.append((a["id"], did, "files_json", rel))
                continue
            claimed.add(ab)
            new_assets.append((did, classify_pdf(os.path.splitext(os.path.basename(ab))[0]), ab, None))
        # 发布包的配图目录
        # 🔴 类型用「页图」不用「图A」：这批图没有 A/B 两版（note 写明单号首发），
        #    标成图A 的话手机端（默认 B 号）会显示"这本还没有 B 号的图"—— 图明明在盘上却看不见。
        pic_dir = find_pic_dir([abspath_of(x) for x in files])
        if pic_dir:
            for j, fn in enumerate(sorted(os.listdir(pic_dir)), start=1):
                if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    ab = os.path.join(pic_dir, fn)
                    claimed.add(ab)
                    new_assets.append((did, "页图", ab, j))

    # 认领两轮：先精确同名（挡住"卷1"把"卷1·全量"的件抢走），再前缀兜底
    def claim(art, exact: bool) -> int:
        did = art2doc[art["id"]]
        name = art["name"]
        got = 0
        for stem, paths in pdf_idx.items():
            hit = (stem == name or stem == f"{name}（答案）") if exact else stem.startswith(name)
            if not hit:
                continue
            for p in paths:
                if p in claimed:
                    continue
                claimed.add(p)
                new_assets.append((did, classify_pdf(stem), p, None))
                got += 1
        return got

    hit_exact = {a["id"]: claim(a, True) for a in new_arts}
    for a in new_arts:
        if not hit_exact[a["id"]] and not jload(a["files_json"]):
            claim(a, False)

    nid = ASSET_ID_BASE
    for did, typ, path, order in sorted(new_assets, key=lambda x: (x[0], x[1], x[2])):
        nid += 1
        asset_rows.append((nid, did, typ, path, order, None))

    out.executemany(
        "INSERT INTO asset (id, doc_id, 类型, 路径, 配图顺序, rendered_at) VALUES (?,?,?,?,?,?)",
        asset_rows,
    )
    out.commit()
    print(f"[3] asset    {len(asset_rows):5d} 行（老改写 {len(asset_rows) - len(new_assets)} + 新 {len(new_assets)}）")
    if miss_map:
        print(f"    ⚠ 老 asset 无路径映射 {len(miss_map)} 行")
    if miss_file:
        print(f"    ⚠ 指针指向的文件不在盘 {len(miss_file)} 行")

    # —— 源文件路径改写：取本册产物的公共目录（老区绝对路径在 v2 里点开一律 403，留着是坏指针）
    bydoc: dict[int, list[str]] = defaultdict(list)
    for r in asset_rows:
        bydoc[r[1]].append(r[3])
    src_fixed = 0
    for did, paths in bydoc.items():
        common = os.path.dirname(paths[0]) if len(paths) == 1 else os.path.commonpath(paths)
        if os.path.isdir(common):
            out.execute("UPDATE doc SET 源文件路径 = ? WHERE id = ?", (common, did))
            src_fixed += 1
    out.commit()
    print(f"    源文件路径改写成 v2 内目录 {src_fixed} 册")

    # ---------------------------------------------------------- ④ question

    QCOLS = ("id", "doc_id", "day", "section", "seq", "stem", "answer", "steps", "考点",
             "题型", "难度", "来源", "updated_at", "hash_L1", "实算", "向量",
             "mother_id", "var_level", "generator_id", "seed", "params")

    old_q = [tuple(r[c] for c in QCOLS) for r in frozen.execute(
        f"SELECT {','.join(QCOLS)} FROM question ORDER BY id")]
    out.executemany(
        f"INSERT INTO question ({','.join(QCOLS)}) VALUES ({','.join('?' * len(QCOLS))})",
        old_q,
    )

    qtype_label = {r["code"]: r["label"] for r in kb.execute(
        "SELECT code, label FROM dict_item WHERE domain='qtype'")}
    diff_label = {r["code"]: r["label"] for r in kb.execute(
        "SELECT code, label FROM dict_item WHERE domain='difficulty'")}
    kps: dict[str, list[str]] = defaultdict(list)
    for r in kb.execute("""SELECT qk.question_id qid, k.name, qk.is_primary
                           FROM question_kp qk JOIN kp k ON k.id = qk.kp_id
                           ORDER BY qk.is_primary DESC, k.name"""):
        kps[r["qid"]].append(r["name"])

    new_q = []
    qid = QID_BASE
    doc_kp: dict[int, Counter] = defaultdict(Counter)
    for r in kb.execute(
        """SELECT p.artifact_id, i.paper_id, i.ord, i.section, q.*
           FROM paper_item i
           JOIN paper p ON p.id = i.paper_id
           JOIN question q ON q.id = i.question_id
           ORDER BY p.artifact_id, i.paper_id, i.ord"""
    ):
        did = art2doc.get(r["artifact_id"])
        if did is None:
            warn.append(f"paper {r['paper_id']} 的 artifact {r['artifact_id']} 没有对应 doc，题丢弃")
            continue
        qid += 1
        ks = kps.get(r["id"], [])
        doc_kp[did].update(ks)
        # 🔴 实算：有答案=绿，无答案=留空（进"待算"）。绝不按"跑通了就绿"猜 ——
        #    页面那盏灯是给人看的判据，猜出来的绿等于把洞盖上。本批 583 条全部有答案。
        has_ans = bool((r["answer_blocks_json"] or "").strip())
        new_q.append((
            qid, did, None, r["section"], r["ord"],
            stem_of(r["blocks_json"]),
            None, None,
            json.dumps(ks, ensure_ascii=False) if ks else None,
            qtype_label.get(r["qtype_code"]),
            diff_label.get(r["diff_code"]),
            r["source_raw"],
            r["updated_at"], r["match_key"],
            "绿" if has_ans else None,
            None, None, r["variant_op"], None, None, None,
        ))
    out.executemany(
        f"INSERT INTO question ({','.join(QCOLS)}) VALUES ({','.join('?' * len(QCOLS))})",
        new_q,
    )
    out.commit()
    print(f"[4] question {len(old_q) + len(new_q):5d} 行（老原样拷 {len(old_q)} + 新投影 {len(new_q)}）")

    for did, c in doc_kp.items():
        out.execute("UPDATE doc SET 考点 = ? WHERE id = ?",
                    (json.dumps([k for k, _ in c.most_common(12)], ensure_ascii=False), did))
    out.commit()

    # ---------------------------------------------------------- ⑤ doc_member

    dm = []
    for i, r in enumerate(kb.execute(
            "SELECT * FROM artifact_member ORDER BY parent_id, ord, member_id"), start=1):
        p, m = art2doc.get(r["parent_id"]), art2doc.get(r["member_id"])
        if p is None or m is None:
            warn.append(f"artifact_member {r['parent_id']}→{r['member_id']} 有一端没对应 doc，丢弃")
            continue
        dm.append((i, p, m, r["ord"]))
    out.executemany(
        "INSERT INTO doc_member (id, 合刊doc_id, 成员doc_id, 排序) VALUES (?,?,?,?)", dm)
    out.commit()
    print(f"[5] doc_member {len(dm):3d} 行")

    # ---------------------------------------------------------- ⑥ question_fts

    rows = out.execute("SELECT id, stem FROM question").fetchall()
    out.executemany("INSERT INTO question_fts(rowid, stem) VALUES (?,?)",
                    [(r["id"], to_fts_text(r["stem"] or "")) for r in rows])
    out.commit()
    print(f"[6] question_fts {len(rows):4d} 行（bigram 口径 = fts.ts）")

    # ---------------------------------------------------------- 自检

    print("\n" + "=" * 64)
    print("自检")
    print("=" * 64)

    ok = True

    # 行数对账
    want = {
        "doc": len(arts),
        "material": kb_mat + note_mat,
        "asset": len(asset_rows),
        "question": len(old_q) + len(new_q),
        "doc_member": kb.execute("SELECT COUNT(*) FROM artifact_member").fetchone()[0],
        "question_fts": len(old_q) + len(new_q),
    }
    for t, n in want.items():
        got = out.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        flag = "✅" if got == n else "❌"
        if got != n:
            ok = False
        print(f"  {flag} {t:14s} {got:5d}  应有 {n}")

    # 守恒：doc = kb.artifact；question = 冻结 + paper_item
    kb_art = kb.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]
    fz_q = frozen.execute("SELECT COUNT(*) FROM question").fetchone()[0]
    pi = kb.execute("SELECT COUNT(*) FROM paper_item").fetchone()[0]
    fz_a = frozen.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    print(f"\n  守恒 doc      = kb.artifact {kb_art} = 老 {len(old_arts)} + 新 {len(new_arts)} "
          f"→ {'✅' if len(old_arts) + len(new_arts) == kb_art else '❌'}")
    print(f"  守恒 question = 冻结 {fz_q} + paper_item {pi} = {fz_q + pi}；"
          f"实投 {len(old_q) + len(new_q)} → {'✅' if len(old_q) + len(new_q) == fz_q + pi else '❌'}")
    print(f"  守恒 asset    = 冻结 {fz_a} - 缺档 {len(miss_file) + len(miss_map)} + 新 {len(new_assets)}"
          f" = {fz_a - len(miss_map) - len([m for m in miss_file if isinstance(m[0], int)]) + len(new_assets)}；"
          f"实投 {len(asset_rows)}")

    # 每 doc 抽验：产物文件真在盘 + 路径都在 v2 工作区内
    bad_path, bad_exist = [], []
    for r in out.execute("SELECT doc_id, 类型, 路径 FROM asset ORDER BY doc_id, id"):
        p = r["路径"]
        if not os.path.abspath(p).startswith(ROOT + os.sep):
            bad_path.append(p)
        elif not os.path.isfile(p):
            bad_exist.append(p)
    print(f"\n  产物指针 {len(asset_rows)} 条：越界 {len(bad_path)}｜不在盘 {len(bad_exist)} "
          f"→ {'✅' if not bad_path and not bad_exist else '❌'}")
    if bad_path or bad_exist:
        ok = False
        for p in (bad_path + bad_exist)[:10]:
            print(f"      {p}")

    # 每册抽验一条
    sample_bad = 0
    for r in out.execute("""SELECT d.id, d.名称, (SELECT COUNT(*) FROM asset a WHERE a.doc_id=d.id) n,
                                   (SELECT a.路径 FROM asset a WHERE a.doc_id=d.id ORDER BY a.id LIMIT 1) p
                            FROM doc d ORDER BY d.id"""):
        if r["n"] and not os.path.isfile(r["p"]):
            sample_bad += 1
    docs_no_asset = out.execute(
        "SELECT COUNT(*) FROM doc d WHERE NOT EXISTS(SELECT 1 FROM asset a WHERE a.doc_id=d.id)"
    ).fetchone()[0]
    print(f"  每册抽验首件在盘：坏 {sample_bad} → {'✅' if sample_bad == 0 else '❌'}"
          f"｜零产物册 {docs_no_asset} 本")

    # 泳道分布（人工态 + 现算的口径对不对，一眼看出来）
    print("\n  人工态分布：", dict(Counter(
        r[0] for r in out.execute("SELECT 人工态 FROM doc"))))
    print("  类型分布：  ", dict(Counter(
        r[0] for r in out.execute("SELECT 类型 FROM doc"))))
    print("  新册实算：  ", dict(Counter(
        r[0] for r in out.execute(f"SELECT 实算 FROM question WHERE doc_id > {DOC_ID_BASE}"))))

    # FTS 抽查：搜得到才算建对
    for kw in ("绝对值", "科学记数法", "有理数"):
        expr = " AND ".join(f'"{t}"' for t in dict.fromkeys(tokenize(kw)))
        n = out.execute(f"SELECT COUNT(*) FROM question_fts WHERE question_fts MATCH '{expr}'").fetchone()[0]
        print(f"  FTS「{kw}」命中 {n} 题 {'✅' if n else '❌'}")
        if not n:
            ok = False

    if miss_map or miss_file:
        print("\n  缺档清单：")
        for m in miss_map:
            print(f"    无映射 asset#{m[0]} doc={m[1]} {m[2]} {m[3]}")
        for m in miss_file:
            print(f"    不在盘 {m[0]} doc={m[1]} {m[2]} {m[3]}")
    if retired:
        print(f"\n  退役件标停售 {len(retired)} 行：")
        for i, (aid, nm) in enumerate(retired, 1):
            print(f"    {i}. {nm}  ({aid})")
    if warn:
        print("\n  告警：")
        for w in warn:
            print(f"    ⚠ {w}")

    out.execute("PRAGMA optimize")
    out.commit()
    out.close()
    frozen.close()
    kb.close()

    print("\n" + ("[√] 投影库重建完成，自检全绿" if ok else "[!] 投影库已建，但自检有红项，见上"))
    print(f"    {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
