# -*- coding: utf-8 -*-
"""出件跑批（PRD-008 段① 转正件）——方案 JSON → 组卷 → 渲染 → 机器验页。

来源：2026-08-20 窗G 浙教出卷战役 scratchpad「主线-浙教出件.py」+「主线-验浙教10套.py」
+「主线-换题重渲2.py／主线-续渲5套.py」的正确姿势，一并转正。

一套的完整链：
    方案 set → spec.json → paper_tool assemble（🔴 按 artifact 名幂等：先查后建）
    → paper_tool render-pack（--out 相对 v2 根）→ render_paper.py 双 PDF + 全页目检 PNG
    → 机器验页（题目卷/答案卷各自：页数≥1、题号 1..N 连号、零「待补答案」、chk PNG 与页数对齐）

🔴 血案配方（照抄别复验）：
  · **写库动作先 commit + close 再起渲染子进程**——本脚本任何库连接都是「开→查→立刻关」，
    绝不跨 subprocess 持连接（窗G 实撞：脚本自持写连接，子进程写 skill_log 被 SQLite 单写者锁死）；
  · **逐套独立子进程 + 固定正超时 + 失败重试一次**——超时值是每次调用现取的常量，
    绝不用「截止时刻 - 现在」算剩余（窗G 实撞负数剩余超时，疑系统时钟跳变，直接 ValueError 炸批）；
  · **render-pack --out 必须相对 v2 根**（paper_tool 自带这道闸，此处再挡一次，早报早改）；
  · Chrome 三坑（临时 profile／--no-proxy-server／出完验文件存在）由 render_paper.py 内部保证，
    本脚本出件后**再目验一次文件真的在盘**，不存在即判失败不装成功。

用法（--db 缺省 = <v2根>/知识库/kb.db；沙盘测试传副本）：
  python 工具箱/组卷/paper_run.py --plan 试验场/xxx/方案.json \
      --pack-dir 试验场/xxx/packs --out-root 产物/验收/xxx [--db 副本.db] \
      [--only U1·1 --only MIX·2] [--limit 2] [--timeout 900] [--verify-only]
路径相对时按 **v2 根** 解析（老货架 717 行绝对路径全断的教训）。
"""
import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
PAPER_TOOL = ROOT / '工具箱' / '组卷' / 'paper_tool.py'
RENDER = ROOT / '工具箱' / '渲染' / 'render_paper.py'
PLAN_CONTRACT = 'paper-plan/v1'
QNO = re.compile(r'(?:^|\n)\s*(\d{1,2})[.．]', re.M)
PENDING = '待补答案'


def die(msg):
    sys.exit(f'🔴 {msg}')


def rel(p):
    """出件/落包路径一律相对 v2 根（渲染与挂账都吃相对路径）。"""
    q = Path(p)
    if q.is_absolute():
        try:
            q = q.relative_to(ROOT)
        except ValueError:
            die(f'路径 {p} 不在 v2 根下——文件指针全相对路径，跨根的绝对路径必断')
    return q.as_posix()


def db_query(db, sql, params=()):
    """🔴 开→查→立刻关：绝不跨 subprocess 持库连接（SQLite 单写者）。"""
    conn = sqlite3.connect(f'file:{Path(db).as_posix()}?mode=ro', uri=True)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def run(cmd, timeout, tag, retries=1):
    """固定正超时 + 失败/超时重试一次。返回 (ok, 输出)。"""
    t = int(timeout)
    if t <= 0:
        die(f'{tag} 超时值 {t} 非正——超时永远是常量，不许拿「截止减现在」算剩余')
    out = ''
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=t)
        except subprocess.TimeoutExpired:
            out = f'超时 {t}s'
            print(f'  ⚠ {tag} 超时（第 {attempt + 1} 次 / 共 {retries + 1} 次）')
            continue
        out = (r.stdout + r.stderr).decode('utf-8', 'replace')
        if r.returncode == 0:
            return True, out
        print(f'  ⚠ {tag} 返回 {r.returncode}（第 {attempt + 1} 次 / 共 {retries + 1} 次）：'
              f'{out.strip()[-300:]}')
    return False, out


# ══════════════════════════════════════════════════════════════════════
# spec 组装（方案 set → paper_tool assemble 吃的 spec）
# ══════════════════════════════════════════════════════════════════════
def make_spec(st, aid):
    art = {'name': st['artifact_name'], 'kind': st.get('artifact_kind', '专项卷'),
           'source_line': st.get('source_line')}
    if aid:
        art['id'] = aid          # 🔴 名字命中就复用旧壳：不再新建 = 不再生孤儿 artifact
    return {'artifact': art,
            'papers': [{'kind': st.get('paper_kind', '专项卷'), 'title': st['title'], 'ord': 1,
                        'layout': st['layout'],
                        'sections': [{'name': s['name'], 'qids': s['qids']}
                                     for s in st['sections']]}]}


# ══════════════════════════════════════════════════════════════════════
# 机器验页
# ══════════════════════════════════════════════════════════════════════
def verify(outdir, stem, n_items):
    """题目卷/答案卷各验：文件在盘、页数≥1、题号 1..N 连号、零「待补答案」、chk PNG 与页数对齐。"""
    import fitz
    src = outdir / '_源'
    rows, bad = [], []
    for kind, fname, chk in (('题目卷', f'{stem}.pdf', '_chk_question_p%d.png'),
                             ('答案卷', f'{stem}（答案）.pdf', '_chk_answer_p%d.png')):
        fp = outdir / fname
        if not fp.exists() or fp.stat().st_size == 0:
            bad.append(f'{kind} 文件不在盘或空：{fp}')
            rows.append((kind, 0, ['文件缺失'], 0, 0))
            continue
        doc = fitz.open(fp)
        txt = ''.join(pg.get_text() for pg in doc)
        pages = doc.page_count
        doc.close()
        nums = {int(m.group(1)) for m in QNO.finditer(txt) if 1 <= int(m.group(1)) <= n_items}
        missing = [i for i in range(1, n_items + 1) if i not in nums]
        pend = txt.count(PENDING)
        pngs = sum(1 for i in range(1, pages + 1) if (src / (chk % i)).exists())
        if pages < 1:
            bad.append(f'{kind} 零页')
        if missing:
            bad.append(f'{kind} 题号缺 {missing}（应 1..{n_items} 连号）')
        if pend:
            bad.append(f'{kind} 含「{PENDING}」{pend} 处')
        if pngs != pages:
            bad.append(f'{kind} 目检图 {pngs} 张 ≠ {pages} 页（--png 出全页）')
        rows.append((kind, pages, missing, pend, pngs))
    return rows, bad


# ══════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description='方案 JSON → 组卷 → 渲染 → 机器验页')
    ap.add_argument('--plan', required=True)
    ap.add_argument('--db', default=str(DEFAULT_DB))
    ap.add_argument('--pack-dir', required=True, help='spec/render-pack 落地目录（相对 v2 根）')
    ap.add_argument('--out-root', required=True, help='出件根目录（相对 v2 根），每套一子目录')
    ap.add_argument('--only', action='append', default=[], help='只跑这些套（key·seq，如 U1·1）')
    ap.add_argument('--limit', type=int, help='只跑前 N 套')
    ap.add_argument('--timeout', type=int, default=900, help='单个子进程超时秒（常量，默认 900）')
    ap.add_argument('--verify-only', action='store_true', help='不组卷不渲染，只机器验页')
    args = ap.parse_args()

    planp = Path(args.plan)
    if not planp.is_absolute():
        planp = ROOT / planp
    plan = json.loads(planp.read_text(encoding='utf-8'))
    if plan.get('contract') != PLAN_CONTRACT:
        die(f'方案契约 {plan.get("contract")!r} 不是 {PLAN_CONTRACT}——先用 draft_paper.py 出方案')
    db = Path(args.db)
    if not db.is_absolute():
        db = ROOT / db
    if not db.exists():
        die(f'库不存在：{db}')
    pack_dir = rel(args.pack_dir)
    out_root = rel(args.out_root)
    (ROOT / pack_dir).mkdir(parents=True, exist_ok=True)

    sets = plan['sets']
    if args.only:
        want = set(args.only)
        sets = [s for s in sets if f'{s["key"]}·{s["seq"]}' in want]
        miss = want - {f'{s["key"]}·{s["seq"]}' for s in plan['sets']}
        if miss:
            die(f'--only 点名的套不在方案里：{sorted(miss)}')
    if args.limit:
        sets = sets[:args.limit]
    if not sets:
        die('没有要跑的套')
    print(f'库={db}｜{len(sets)}/{len(plan["sets"])} 套｜pack→{pack_dir}｜出件→{out_root}\n')

    done, failed = [], []
    for st in sets:
        key = f'{st["key"]}·{st["seq"]}'
        aname, title = st['artifact_name'], st['title']
        n_items = sum(len(s['qids']) for s in st['sections'])
        outdir = ROOT / out_root / title
        print(f'── {key} 《{title}》 {n_items} 题 ──')

        if not args.verify_only:
            # ① artifact 按名幂等：先查后建（查完立刻关连接）
            row = db_query(db, 'SELECT id FROM artifact WHERE name=? ORDER BY id DESC LIMIT 1',
                           (aname,))
            aid = row[0][0] if row else None
            spec_fp = ROOT / pack_dir / f'spec_{st["key"]}_{st["seq"]}.json'
            spec_fp.write_text(json.dumps(make_spec(st, aid), ensure_ascii=False, indent=1),
                               encoding='utf-8')
            ok, out = run([sys.executable, str(PAPER_TOOL), '--db', str(db),
                           'assemble', '--spec', str(spec_fp)], min(args.timeout, 300),
                          f'{key} assemble')
            if not ok:
                failed.append((key, 'assemble', out.strip()[-300:]))
                continue
            if aid is None:
                hit = [ln for ln in out.splitlines() if 'artifact 新建：' in ln]
                if not hit:
                    failed.append((key, 'assemble', '拿不到新建 artifact id：' + out.strip()[-200:]))
                    continue
                aid = hit[0].split('：')[1].split()[0]
            print(f'  组卷 artifact={aid}（{"复用" if row else "新建"}）')

            # ② render-pack（--out 相对 v2 根）
            pk = f'{pack_dir}/pack_{st["key"]}_{st["seq"]}.json'
            ok, out = run([sys.executable, str(PAPER_TOOL), '--db', str(db),
                           'render-pack', '--artifact', aid, '--out', pk],
                          min(args.timeout, 300), f'{key} render-pack')
            if not ok:
                failed.append((key, 'render-pack', out.strip()[-300:]))
                continue

            # ③ 双 PDF + 全页目检 PNG（逐套独立子进程，固定正超时，失败重试一次）
            ok, out = run([sys.executable, str(RENDER), pk,
                           '--out-dir', f'{out_root}/{title}', '--png',
                           '--db', str(db), '--no-log'], args.timeout, f'{key} 渲染')
            if not ok:
                failed.append((key, '渲染', out.strip()[-400:]))
                continue
            time.sleep(1)            # 🔴 Chrome 写盘落后于进程退出，睡一下再目验文件

        # ④ 机器验页
        rows, bad = verify(outdir, aname, n_items)
        for kind, pages, missing, pend, pngs in rows:
            print(f'  {"🔴" if (missing or pend or pages < 1) else "✅"} {kind}：'
                  f'{pages} 页｜题号缺 {missing or "无"}｜待补 {pend}｜目检图 {pngs}')
        if bad:
            failed.append((key, '验页', '；'.join(bad)))
            continue
        done.append((key, title))
        print(f'  ✅ {key} 出件+验页全绿')

    print(f'\n=== 出件并验页通过 {len(done)}/{len(sets)} 套 ===')
    for k, s, m in failed:
        print(f'🔴 {k} 挂在{s}：{m}')
    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
