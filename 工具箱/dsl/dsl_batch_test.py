# -*- coding: utf-8 -*-
"""dsl_batch 一条命令自证（PRD-003 阶段4 D 线补）—— 既有沙盘用例不退 + 入库收尾向量四条路。

  python 工具箱\\dsl\\dsl_batch_test.py                     # 用缺省沙盘基准库
  python 工具箱\\dsl\\dsl_batch_test.py --db <沙盘基准.db>

🔴 三条测试纪律（与 serve_test 同）：
  · **只碰沙盘副本**：每条用例自己从基准库拷一份 `<沙盘>/D-dsl/kb.<用例>.db` 当工作库，
    连基准库都不写；绝不指向主位 知识库\\kb.db；
  · **不载真模型、不起真 serve**：走 serve 那条用**注入的假 serve**验接线（真模型那条由
    工具箱\\检索\\serve_test.py 的 E 段管），本脚本秒级可重复跑；
  · **每条修复配一条会红的反例**：serve 不在、收尾抛异常两条，都必须「打印待补命令 + 不阻断入库」。

覆盖：
  A 既有沙盘用例不退   --check-only 干跑全回滚不写库不写 spec；真跑 --no-vec 入库 16 题 + spec 写出
  B 入库收尾向量       🔴 本卡实伤：dsl_batch 直调 ingest_one，绕过了 ingest_flow 的收尾，
                       结果「16 题入库、③层一条向量都没有、屏幕上一个字不提」。四条路各一条：
                       ① serve 在 → 走 serve 批量补上，向量真落库
                       ② serve 不在 + venv 不可用 → **只打印待补命令**，不抛不阻断（🔴 反例）
                       ③ 收尾自己抛异常 → 照样只报不抛，题不回滚（🔴 反例）
                       ④ --no-vec → 明说跳过并给待补命令（不静默）
"""
import argparse
import contextlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent                    # …/工具箱/dsl
ROOT = HERE.parents[1]                                    # …/ai-bkb-v2（worktree 里=本位）
sys.path.insert(0, str(ROOT / '工具箱' / '检索'))
import embed_tool                                          # noqa: E402
from embed_tool import EmbedError                          # noqa: E402
sys.path.insert(0, str(HERE))
import dsl_batch                                           # noqa: E402

PY = sys.executable
BATCH = HERE / 'dsl_batch.py'
SAMPLE_PLAN = HERE / '_样例' / '排班-样例.json'
SANDBOX = ROOT / '试验场' / '2026-08-19-prd003沙盘'
DEFAULT_BASE_DB = SANDBOX / 'D-serve' / 'kb.db'
WORK_DIR = SANDBOX / 'D-dsl'

N_BASE_Q = 60                                             # 沙盘基准库题量（本卡实测基准）
N_PLAN_Q = 16                                             # 样例排班出题数（2 卷 × 8）
DIM = 512
MODEL = 'bge-small-zh-v1.5'

FAIL, N = [], [0]
BASE = None


def check(name, got, want):
    N[0] += 1
    if got == want:
        print(f'  ✓ {name}')
    else:
        print(f'  ✗ {name}\n      得 {got!r}\n      期 {want!r}')
        FAIL.append(name)


def check_true(name, cond, detail=''):
    check(name + (f'（{detail}）' if detail else ''), bool(cond), True)


def prep(tag):
    """本用例专用工作库 + 排班计划副本（spec 也写在工作目录里，不污染 _样例/）。"""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    db = WORK_DIR / f'kb.{tag}.db'
    shutil.copy2(BASE, db)
    plan = WORK_DIR / f'排班-{tag}.json'
    plan.write_text(SAMPLE_PLAN.read_text(encoding='utf-8'), encoding='utf-8')
    spec = plan.with_name(plan.stem + '-组卷spec.json')
    if spec.exists():
        spec.unlink()
    return db, plan, spec


def counts(db):
    c = sqlite3.connect(f'file:{Path(db).as_posix()}?mode=ro', uri=True)
    try:
        return (c.execute('SELECT COUNT(*) FROM question').fetchone()[0],
                c.execute('SELECT COUNT(*) FROM question_vec').fetchone()[0])
    finally:
        c.close()


def run_cli(db, plan, *extra, timeout=600):
    p = subprocess.run([str(x) for x in (PY, BATCH, '--db', db, 'run', plan, *extra)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       cwd=str(ROOT), env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                       timeout=timeout)
    return p.returncode, (p.stdout or ''), (p.stderr or '')


def run_inproc(db, plan, *extra):
    """进程内跑 dsl_batch（要 monkeypatch embed_tool 才这么跑）→ (退出码, 屏幕全文)。"""
    buf = io.StringIO()
    code = None
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            dsl_batch.main(['--db', str(db), 'run', str(plan), *[str(x) for x in extra]])
        except SystemExit as e:
            code = e.code if e.code is not None else 0
    return code, buf.getvalue()


@contextlib.contextmanager
def patched(**kw):
    """临时替换 embed_tool 里的若干函数（用完必还原，别把后面的用例带坏）。"""
    keep = {k: getattr(embed_tool, k) for k in kw}
    for k, v in kw.items():
        setattr(embed_tool, k, v)
    try:
        yield
    finally:
        for k, v in keep.items():
            setattr(embed_tool, k, v)


def fake_serve_health(*_a, **_k):
    return {'pid': 99999, 'model': MODEL, 'dim': DIM}


def make_fake_embed(seen):
    def fake_embed_texts(texts, *_a, **kw):
        seen.append(kw.get('serve_port'))
        # 每条给一条可区分的确定性向量（不载模型：本脚本只验接线，不验语意质量）
        vecs = [[float((i + j) % 7) + 0.5 for j in range(DIM)] for i, _t in enumerate(texts)]
        return vecs, DIM, MODEL
    return fake_embed_texts


# ══════════════════════════════════════════════════════════════════════
def main():
    global BASE
    ap = argparse.ArgumentParser(description='dsl_batch 自证（既有沙盘用例 + 入库收尾向量）')
    ap.add_argument('--db', default=str(DEFAULT_BASE_DB), help=f'沙盘基准库（缺省 {DEFAULT_BASE_DB}）')
    a = ap.parse_args()
    BASE = Path(a.db)
    if not BASE.is_file():
        sys.exit(f'🔴 沙盘基准库不存在：{BASE}\n'
                 f'   本测试只跑副本库，请先拷一份（🔴 别指主位正本）：\n'
                 f'     copy D:\\workplace\\ai-bkb-v2\\知识库\\kb.db "{BASE}"')
    if not SAMPLE_PLAN.is_file():
        sys.exit(f'🔴 样例排班不存在：{SAMPLE_PLAN}')
    print(f'沙盘：基准={BASE}\n      工作目录={WORK_DIR}（每条用例重拷一份工作库，互不串）')

    # ── A 既有沙盘用例不退 ────────────────────────────────────────────
    print('\n── A 既有沙盘用例不退（样例排班：预检→出题→verify→打标→入库→spec）──')
    db, plan, spec = prep('dry')
    code, out, err = run_cli(db, plan, '--check-only')
    check('--check-only 退出码 0', code, 0)
    if code:
        print(f'      stdout:\n{out}\n      stderr:\n{err}')
    check('--check-only 预检通过 exam_model 全命中', '预检通过' in out and 'exam_model 全部命中' in out, True)
    check('--check-only verify 全绿', 'ALL PASS' in out, True)
    check(f'--check-only 出题 {N_PLAN_Q} 题', f'{N_PLAN_Q} 题' in out, True)
    check('--check-only 全部回滚（库题数不变）', counts(db), (N_BASE_Q, N_BASE_Q))
    check('--check-only 不写 spec', spec.exists(), False)
    # 🔴 干跑不许偷偷去算向量（题根本没进库），但也不许一个字不提
    check('--check-only 汇总明说向量跳过原因', '语意向量（D-20 第③层）：skip:--check-only' in out, True)

    # ── B④ --no-vec：明说跳过 + 给待补命令（不静默）───────────────────
    print('\n── B④ 真跑 --no-vec：入库 + spec，向量明说不补 ──')
    db, plan, spec = prep('novec')
    code, out, err = run_cli(db, plan, '--no-vec')
    check('真跑 --no-vec 退出码 0', code, 0)
    if code:
        print(f'      stdout:\n{out}\n      stderr:\n{err}')
    check(f'入库 {N_PLAN_Q} 题、向量一条没加', counts(db), (N_BASE_Q + N_PLAN_Q, N_BASE_Q))
    check('组卷 spec 写出来了', spec.exists(), True)
    check('spec 里 qids 已回填', sum(len(s['qids']) for p in json.loads(
        spec.read_text(encoding='utf-8'))['papers'] for s in p['sections']), N_PLAN_Q)
    check('--no-vec 有明说（不静默）', '--no-vec：不补语意向量' in out, True)
    check('--no-vec 也给待补命令', 'embed_tool.py build' in out, True)
    check('汇总行标明 skip:--no-vec', '语意向量（D-20 第③层）：skip:--no-vec' in out, True)

    # ── B① serve 在 → 批量走 serve 把向量补上 ─────────────────────────
    print('\n── B① serve 在：入库收尾批量走 serve 补向量（注入假 serve，不载真模型）──')
    db, plan, spec = prep('serve')
    seen = []
    with patched(serve_health=fake_serve_health, embed_texts=make_fake_embed(seen),
                 resolve_venv=lambda *x, **k: (_ for _ in ()).throw(
                     AssertionError('serve 在的时候不许回落 sidecar'))):
        code, out = run_inproc(db, plan, '--serve-port', 4317)
    check('serve 在：退出码 0', code, 0)
    if code:
        print(out)
    check(f'serve 在：{N_PLAN_Q} 题的向量真落库了',
          counts(db), (N_BASE_Q + N_PLAN_Q, N_BASE_Q + N_PLAN_Q))
    check('serve 在：报告写明走了常驻 serve', '走常驻 serve' in out, True)
    check(f'serve 在：汇总行 {N_PLAN_Q}/{N_PLAN_Q}',
          f'语意向量（D-20 第③层）：{N_PLAN_Q}/{N_PLAN_Q}' in out, True)
    check('serve 在：--serve-port 真的透传进去了', seen and set(seen) == {4317}, True)
    c = sqlite3.connect(f'file:{db.as_posix()}?mode=ro', uri=True)
    bad = c.execute('SELECT COUNT(*) FROM question_vec WHERE model<>? OR dim<>? OR LENGTH(vec)<>?',
                    (MODEL, DIM, DIM * 4)).fetchone()[0]
    c.close()
    check('serve 在：向量模型名/维度/BLOB 字节全对', bad, 0)

    # ── B② 🔴 反例：serve 不在 + venv 不可用 ⇒ 只打印待补命令，不阻断入库 ──
    print('\n── B② 🔴 反例：serve 不在 + venv 不可用 ⇒ 打印待补命令，题照样在库 ──')
    db, plan, spec = prep('novenv')
    with patched(serve_health=lambda *x, **k: None,
                 resolve_venv=lambda *x, **k: (_ for _ in ()).throw(
                     EmbedError('语意层 venv 不可用：沙盘故意掐断')),
                 embed_texts=lambda *x, **k: (_ for _ in ()).throw(
                     AssertionError('venv 都没有还去算向量=静默降级'))):
        code, out = run_inproc(db, plan)
    check('🔴 不阻断入库：退出码仍是 0', code, 0)
    check('🔴 题真的在库里（收尾没把主事务拖下水）',
          counts(db), (N_BASE_Q + N_PLAN_Q, N_BASE_Q))
    check('🔴 不静默：打印了待补命令 embed_tool.py build', 'embed_tool.py build' in out, True)
    check('🔴 待补命令指的是本次这个库', f'build --db {db}' in out, True)
    check('明说题已入库不受影响', '题已入库' in out, True)
    check('汇总行标明 skip:no-venv', '语意向量（D-20 第③层）：skip:no-venv' in out, True)
    check('组卷 spec 照常写出（向量不影响出货）', spec.exists(), True)

    # ── B③ 🔴 反例：收尾自己抛异常 ⇒ 只报不抛，题不回滚 ────────────────
    print('\n── B③ 🔴 反例：收尾抛异常 ⇒ 只报不抛（入库已 commit，不许被收尾拖下水）──')
    db, plan, spec = prep('boom')
    with patched(serve_health=lambda *x, **k: (_ for _ in ()).throw(
            RuntimeError('探活炸了：沙盘故意的'))):
        code, out = run_inproc(db, plan)
    check('🔴 收尾炸了：退出码仍是 0', code, 0)
    check('🔴 收尾炸了：题还在库里', counts(db), (N_BASE_Q + N_PLAN_Q, N_BASE_Q))
    check('🔴 收尾炸了：如实报异常类型', 'error:RuntimeError' in out, True)
    check('🔴 收尾炸了：仍给待补命令', 'embed_tool.py build' in out, True)

    print(f'\n=== {N[0] - len(FAIL)}/{N[0]} 通过 ===' + ('' if not FAIL else f'\n🔴 未过：{FAIL}'))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    raise SystemExit(main())
