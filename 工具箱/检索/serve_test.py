# -*- coding: utf-8 -*-
"""常驻 serve + 以题找题 + 启动台 + 入库收尾向量 —— 一条命令自证（PRD-003 阶段4 D 线）。

  python 工具箱\\检索\\serve_test.py                      # 用缺省沙盘副本库跑全部断言
  python 工具箱\\检索\\serve_test.py --db <沙盘副本.db> --port-embed 4317 --port-kb 4316

🔴 三条测试纪律：
  · **只碰沙盘副本**：本脚本自己再拷一份 `<库>.serve_test.db` 当本次工作库，
    连基准沙盘库都不写；绝不指向主位 知识库\\kb.db（worktree 里 启动台 的库闸也会拦）；
  · **端口错开主位常驻**（缺省 embed=4317 / kb=4316，主位是 4315/4310）——
    测试实例绝不能把主位跑着的服务停掉；
  · **起过的都要停**：finally 里无条件 --stop，测试挂了也不留孤儿进程。

覆盖（每条都对应一个真会坏的地方）：
  A 存量不退      query_core_test 56 断言全绿（本卡只加不改①②层）
  B 以题找题      --like-qid 直取 question_vec 排序；不载模型/不走 serve/不起 sidecar 也出结果；
                  锚题自身排除；候选过滤生效；没向量/指空/与 --like 同给 三种拒查
  C serve 三态    不在 → 在（幂等重起跳过）→ 停回落；serve 与冷载向量对拍一致；坏请求拒收
  D 启动台        kb 读 API 起停探活、库指向沙盘副本、**只读行为验证**（对 GET 端点发 POST 必 405、
                  写口白名单恰一条 sale-state）、worktree 两道越界闸
  E 入库收尾向量  ingest 后新题自动有向量；--no-vec 关得掉；serve/venv 都不在时只打印待补命令不阻断
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
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import embed_tool  # noqa: E402
from embed_tool import EmbedError  # noqa: E402

PY = sys.executable
LAUNCH = ROOT / '工具箱' / '启动台.py'
INGEST = ROOT / '工具箱' / '回流' / 'ingest_flow.py'
QC_TEST = HERE / 'query_core_test.py'
FIND = HERE / 'find_questions.py'
DEFAULT_BASE_DB = ROOT / '试验场' / '2026-08-19-prd003沙盘' / 'D-serve' / 'kb.db'
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

FAIL, N = [], [0]


def check(name, got, want):
    N[0] += 1
    got = sorted(got) if isinstance(got, (list, set, tuple)) else got
    want = sorted(want) if isinstance(want, (list, set, tuple)) else want
    if got == want:
        print(f'  ✓ {name}')
    else:
        print(f'  ✗ {name}\n      得 {got}\n      期 {want}')
        FAIL.append(name)


def check_true(name, cond, detail=''):
    check(name + (f'（{detail}）' if detail else ''), bool(cond), True)


def check_raise(name, fn, keyword):
    N[0] += 1
    try:
        fn()
    except EmbedError as e:
        if keyword in str(e):
            print(f'  ✓ {name}（拒：{str(e).splitlines()[0][:56]}…）')
            return
        print(f'  ✗ {name}：报错了但话不对——{e}')
    except Exception as e:                                # noqa: BLE001
        print(f'  ✗ {name}：抛了非 EmbedError —— {type(e).__name__}: {e}')
    else:
        print(f'  ✗ {name}：**没报错**（静默降级=最阴的坑）')
    FAIL.append(name)


def run(cmd, timeout=300):
    """跑子进程 → (退出码, stdout, stderr)。全程 utf-8（GBK 会把中文毁掉）。"""
    p = subprocess.run([str(x) for x in cmd], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=str(ROOT),
                       env=dict(os.environ, PYTHONIOENCODING='utf-8'), timeout=timeout)
    return p.returncode, p.stdout or '', p.stderr or ''


def http(url, payload=None, timeout=10):
    data, headers = None, {'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method='POST' if data is not None else 'GET')
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'raw': body[:200]}


def cosine(a, b):
    import numpy as np
    a, b = np.asarray(a, dtype='<f8'), np.asarray(b, dtype='<f8')
    return float(a @ b / ((a @ a) ** 0.5 * (b @ b) ** 0.5))


# ══════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description='常驻 serve / 以题找题 / 启动台 / 入库向量 自证')
    ap.add_argument('--db', default=str(DEFAULT_BASE_DB), help=f'沙盘基准库（缺省 {DEFAULT_BASE_DB}）')
    ap.add_argument('--port-embed', dest='port_embed', type=int, default=4317)
    ap.add_argument('--port-kb', dest='port_kb', type=int, default=4316)
    a = ap.parse_args()

    base = Path(a.db)
    if not base.is_file():
        sys.exit(f'🔴 沙盘基准库不存在：{base}\n'
                 f'   本测试只跑副本库，请先拷一份（🔴 别指主位正本）：\n'
                 f'     copy D:\\workplace\\ai-bkb-v2\\知识库\\kb.db "{base}"')
    work = base.with_name(base.stem + '.serve_test.db')
    shutil.copy2(base, work)                              # 🔴 连基准沙盘库都不写，本次只动这份
    print(f'沙盘：基准={base}\n      本次工作库={work}（每次重拷，测试互不串）')
    print(f'端口：embed=:{a.port_embed} kb=:{a.port_kb}（主位常驻 4315/4310 不碰）')
    pe, pk = a.port_embed, a.port_kb

    def launch(*args, timeout=300):
        return run([PY, LAUNCH, '--port-embed', pe, '--port-kb', pk, *args], timeout)

    try:
        # 归零：本次端口上不许有残留实例（顺带先跑一遍 --stop 通路）
        launch('--stop', '--only', 'embed')
        launch('--stop', '--only', 'kb')

        # ── A 存量不退 ────────────────────────────────────────────────
        print('\n── A 存量不退（①②层只加不改）──')
        code, out, _err = run([PY, QC_TEST])
        check('query_core_test 退出码 0', code, 0)
        check('query_core_test 56/56 全绿', '=== 56/56 通过 ===' in out, True)

        # ── B 以题找题（--like-qid）──────────────────────────────────
        print('\n── B 以题找题：--like-qid 直取 question_vec，不载模型不走 serve ──')
        conn = sqlite3.connect(str(work))
        conn.execute('PRAGMA foreign_keys=ON')
        anchor = conn.execute(
            'SELECT question_id FROM question_vec ORDER BY question_id LIMIT 1').fetchone()[0]
        n_q = conn.execute('SELECT COUNT(*) FROM question').fetchone()[0]
        check('沙盘库题量 60（本卡实测基准）', n_q, 60)
        check('serve 未起时探活=None【三态①·不在】', embed_tool.serve_health(pe), None)

        # 🔴 机械自证「不载模型」：把 serve 与 sidecar 两条路都掐断，rank_by_qid 仍须出结果
        keep_h, keep_v, keep_e = (embed_tool.serve_health, embed_tool.resolve_venv,
                                  embed_tool.embed_texts)
        embed_tool.serve_health = lambda *x, **k: (_ for _ in ()).throw(
            AssertionError('rank_by_qid 不许探活 serve'))
        embed_tool.resolve_venv = lambda *x, **k: (_ for _ in ()).throw(
            AssertionError('rank_by_qid 不许起 sidecar'))
        embed_tool.embed_texts = lambda *x, **k: (_ for _ in ()).throw(
            AssertionError('rank_by_qid 不许算向量'))
        try:
            hits, info = embed_tool.rank_by_qid(conn, anchor, None, 5)
            check('掐断 serve+sidecar 后仍出 top5（证明真的只读库里的向量）', len(hits), 5)
        finally:
            embed_tool.serve_health, embed_tool.resolve_venv, embed_tool.embed_texts = (
                keep_h, keep_v, keep_e)
        check('分数降序', [round(s, 6) for _q, s in hits],
              sorted([round(s, 6) for _q, s in hits], reverse=True))
        check('锚题自身不在结果里', anchor in [q for q, _s in hits], False)
        check('模型名回报', info['model'], 'bge-small-zh-v1.5')
        check('维度回报', info['dim'], 512)
        check('候选=全库减锚题', info['candidates'], n_q - 1)
        check('缺向量数如实回报', info['missing'], info['candidates'] - info['vectored'])

        some = [r[0] for r in conn.execute(
            'SELECT question_id FROM question_vec ORDER BY question_id LIMIT 4')]
        hits2, info2 = embed_tool.rank_by_qid(conn, anchor, some, 5)
        check('候选过滤生效（只在给的候选里排）', set(q for q, _ in hits2) <= set(some) - {anchor}, True)
        check('候选里锚题被剔掉', info2['candidates'], len(some) - 1)

        no_vec = conn.execute(
            'SELECT id FROM question WHERE id NOT IN (SELECT question_id FROM question_vec) '
            'LIMIT 1').fetchone()
        if not no_vec:                                    # 造一道没向量的题（不动基准库）
            victim = conn.execute('SELECT question_id FROM question_vec ORDER BY question_id '
                                  'DESC LIMIT 1').fetchone()[0]
            conn.execute('DELETE FROM question_vec WHERE question_id=?', (victim,))
            conn.commit()
            no_vec = (victim,)
        check_raise('没算向量的题 → 报错且给补算命令',
                    lambda: embed_tool.rank_by_qid(conn, no_vec[0], None, 5),
                    'embed_tool.py build')
        check_raise('锚点指空 → 拒查', lambda: embed_tool.rank_by_qid(conn, 'qNOPE', None, 5),
                    '不许指空')
        conn.close()

        code, out, err = run([PY, FIND, '--db', work, '--like', 'x', '--like-qid', anchor])
        check('--like 与 --like-qid 互斥闸：退出码非 0', code != 0, True)
        check('互斥闸把话说清楚', '互斥' in err, True)
        code, out, _e = run([PY, FIND, '--db', work, '--like-qid', anchor, '--topk', '5'])
        check('CLI --like-qid 退出码 0', code, 0)
        check('CLI --like-qid 出 5 行命中', len([l for l in out.splitlines()
                                                if l.startswith('0.') or l.startswith('1.')]), 5)
        check('CLI 打印锚题', '锚题' in out, True)

        # ── C serve 三态 ─────────────────────────────────────────────
        print('\n── C serve 三态：不在 → 在 → 停回落（🔴 回落路径行为一字不变）──')
        t0 = time.time()
        vec_cold, dim_cold, name_cold = embed_tool.embed_texts(
            ['计算：$-8+15\\div(-3)\\times 2$'], quiet=True, use_serve=False)
        cold_s = time.time() - t0
        check('冷载 sidecar 出向量 dim=512', dim_cold, 512)
        check('冷载模型名', name_cold, 'bge-small-zh-v1.5')

        code, out, err = launch('--only', 'embed')
        check('启动台起 embed 退出码 0', code, 0, )
        if code:
            print(f'      stdout:\n{out}\n      stderr:\n{err}')
        h = embed_tool.serve_health(pe)
        check('serve 探活在【三态②·在】', bool(h), True)
        check('serve 报模型名', (h or {}).get('model'), 'bge-small-zh-v1.5')
        check('serve 报维度', (h or {}).get('dim'), 512)

        code2, out2, _e = launch('--only', 'embed')
        check('幂等：已在跑就跳过不重起', '已在跑' in out2, True)
        check('幂等重跑退出码 0', code2, 0)
        check('幂等没起出第二个进程（pid 不变）',
              (embed_tool.serve_health(pe) or {}).get('pid'), (h or {}).get('pid'))

        t0 = time.time()
        vec_serve, dim_serve, name_serve = embed_tool.embed_texts(
            ['计算：$-8+15\\div(-3)\\times 2$'], quiet=True, serve_port=pe)
        serve_s = time.time() - t0
        check('serve 出向量 dim=512', dim_serve, 512)
        check('serve 模型名与冷载一致', name_serve, name_cold)
        check('serve 向量长度=512（float32 小端 ⇒ BLOB 2048 字节）', len(vec_serve[0]), 512)
        check('serve 与冷载向量对拍一致（余弦≥0.99999）',
              cosine(vec_serve[0], vec_cold[0]) >= 0.99999, True)
        check_true('serve 比冷载快一个量级', serve_s * 5 < cold_s,
                   f'serve {serve_s:.2f}s vs 冷载 {cold_s:.2f}s')

        st, body = http(f'http://127.0.0.1:{pe}/embed', {'texts': []})
        check('坏请求：texts 空 → 400', st, 400)
        check('坏请求：明确回 ok=false 不给空向量', body.get('ok'), False)
        st, _b = http(f'http://127.0.0.1:{pe}/nope')
        check('未知端点 → 404', st, 404)
        st, body = http(f'http://127.0.0.1:{pe}/embed', {'text': '单条文本也认'})
        check('单条 text 也认 → 200', st, 200)
        check('单条 text 回 1 条向量', body.get('count'), 1)

        code, out, _e = run([PY, FIND, '--db', work, '--like', '有理数的加减混合运算',
                             '--topk', '3', '--serve-port', pe])
        check('find --like 走 serve 退出码 0', code, 0)
        check('find --like 出 3 行', len([l for l in out.splitlines() if l.startswith('0.')]), 3)

        # ── E 入库收尾自动增量向量（serve 在着，正好测走 serve 那条）────
        print('\n── E 入库收尾自动增量向量 ──')
        kp_leaf = sqlite3.connect(str(work)).execute(
            "SELECT id FROM kp WHERE level='考点' ORDER BY id LIMIT 1").fetchone()[0]

        def pack_file(qid, md, path):
            p = Path(path)
            p.write_text(json.dumps({'source_line': 'serve_test', 'items': [{
                'id': qid, 'blocks': {'v': 2, 'rows': [{'cells': [
                    {'type': 'text', 'role': '题面', 'md': md}]}]},
                'qtype': '计算题', 'difficulty': '巩固', 'source_kind': 'manual',
                'source_raw': 'serve_test 沙盘用例', 'kp': [kp_leaf], 'primary_kp': kp_leaf,
                'confidence': 95}]}, ensure_ascii=False), encoding='utf-8')
            return p

        tmp = work.parent
        q_auto, q_novec = 'qSRV_auto', 'qSRV_novec'
        f1 = pack_file(q_auto, '计算：$7-(-9)+(-4)$（serve_test 自动向量用例）', tmp / '_pack_auto.json')
        code, out, err = run([PY, INGEST, '--db', work, 'ingest', f1, '--serve-port', pe])
        check('ingest 入库退出码 0', code, 0)
        if code:
            print(f'      stdout:\n{out}\n      stderr:\n{err}')
        c2 = sqlite3.connect(str(work))
        row = c2.execute('SELECT model, dim, LENGTH(vec) FROM question_vec WHERE question_id=?',
                         (q_auto,)).fetchone()
        check('入库收尾自动补上了向量', bool(row), True)
        check('向量模型名对', (row or [None])[0], 'bge-small-zh-v1.5')
        check('向量 BLOB=512×4 字节', (row or [None, None, None])[2], 2048)
        check('报告里写明走了 serve', '走常驻 serve' in out, True)

        f2 = pack_file(q_novec, '计算：$12-(-6)+(-8)$（serve_test --no-vec 用例）',
                       tmp / '_pack_novec.json')
        code, out, _e = run([PY, INGEST, '--db', work, 'ingest', f2, '--no-vec'])
        check('--no-vec 入库仍成功', code, 0)
        check('--no-vec 时确实没算向量',
              c2.execute('SELECT COUNT(*) FROM question_vec WHERE question_id=?',
                         (q_novec,)).fetchone()[0], 0)
        check('--no-vec 有明说（不静默）', '--no-vec' in out, True)

        # 反例：serve 不在 + venv 也不可用 ⇒ 只打印待补命令，**不抛异常、不阻断入库**
        sys.path.insert(0, str(ROOT / '工具箱' / '回流'))
        import ingest_flow                                # noqa: PLC0415
        keep_h, keep_v = embed_tool.serve_health, embed_tool.resolve_venv
        embed_tool.serve_health = lambda *x, **k: None
        embed_tool.resolve_venv = lambda *x, **k: (_ for _ in ()).throw(
            EmbedError('语意层 venv 不可用：沙盘故意掐断'))
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                n_done, note = ingest_flow.autovec(c2, [q_novec])
        finally:
            embed_tool.serve_health, embed_tool.resolve_venv = keep_h, keep_v
        printed = buf.getvalue()
        # 🔴 回归闸（本卡实伤）：embed_tool 是懒加载的，被 import 那一刻 stdout 可能是 StringIO，
        #    而 StringIO 没有 .reconfigure ⇒ 裸 reconfigure 会 AttributeError，语意层整个消失。
        src = ('import io, sys, contextlib\n'
               f'sys.path.insert(0, r"{HERE}")\n'
               'buf = io.StringIO()\n'
               'with contextlib.redirect_stdout(buf):\n'
               '    import embed_tool\n'
               'sys.stderr.write("IMPORT-OK:%d" % embed_tool.DEFAULT_SERVE_PORT)\n')
        _c, _o, e2 = run([PY, '-c', src], timeout=60)
        check('stdout 被 redirect 成 StringIO 时 import embed_tool 不炸', 'IMPORT-OK' in e2, True)
        check('serve/venv 都不在：不抛异常，如实回 0 题', n_done, 0)
        check('serve/venv 都不在：说明串标明跳过原因', note, 'skip:no-venv')
        check('serve/venv 都不在：打印待补命令', 'embed_tool.py build' in printed, True)
        check('serve/venv 都不在：明说不阻断入库', '题已入库' in printed, True)
        check('serve/venv 都不在：题还在库里（入库没被拖下水）',
              c2.execute('SELECT COUNT(*) FROM question WHERE id=?', (q_novec,)).fetchone()[0], 1)
        c2.close()

        # ── D 启动台：kb 读 API + 越界闸 ──────────────────────────────
        print('\n── D 启动台：kb 读 API 起停探活 + worktree 越界闸 ──')
        code, out, err = launch('--only', 'kb', '--kb', work)
        check('启动台起 kb 退出码 0', code, 0)
        if code:
            print(f'      stdout:\n{out}\n      stderr:\n{err}')
        st, body = http(f'http://127.0.0.1:{pk}/api/kb/stats')
        check('kb 读 API 探活 200', st, 200)
        check('kb 读 API 挂的是沙盘副本（🔴 不是主位库）',
              Path(body.get('db_path', '')).resolve() == work.resolve(), True)
        # 🔴 只读=**行为验证**，不看自报字段。
        #    （原来这里断言的是 body['readonly']，那是 epStats 里写死的字面量 true，
        #     把写端点白名单改成 10 条它照样绿——恒真断言比没断言更坏，因为它假装守着。）
        #    真检测：对任一 GET 端点发 POST（非 sale-state 路径）必须被拒（405），
        #    且回话里的写端点白名单恰好一条 sale-state。
        for path in ('/api/kb/stats', '/api/kb/questions', '/api/kb/artifacts'):
            st, body_w = http(f'http://127.0.0.1:{pk}{path}', {'id': 'X', 'sale_state': '在售'})
            check(f'只读行为验证：POST {path} 被拒（405）', st, 405)
            check(f'POST {path} 把话说清楚（只接受 GET）', '只读' in str(body_w.get('error', '')), True)
            check(f'POST {path} 回的写端点白名单恰一条 sale-state',
                  body_w.get('写端点'), ['POST /api/kb/sale-state'])
        st, _b = http(f'http://127.0.0.1:{pk}/api/kb/nope-write', {'x': 1})
        check('只读行为验证：POST 到不存在的路径也拒（405，不是 500）', st, 405)
        code2, out2, _e = launch('--only', 'kb', '--kb', work)
        check('kb 幂等：已在跑就跳过', '已在跑' in out2, True)
        code, out, _e = launch('--stop', '--only', 'kb')
        check('kb --stop 退出码 0', code, 0)
        check('kb 停干净了（探活不通）', probe_dead(pk, '/api/kb/stats'), True)

        if embed_tool.MAIN_ROOT.resolve() != ROOT.resolve():
            code, _o, err = run([PY, LAUNCH, '--port-embed', pe, '--port-kb', pk,
                                 '--kb', embed_tool.MAIN_ROOT / '知识库' / 'kb.db'])
            check('worktree 库闸：--kb 指主位库被拒', code, 2)
            check('库闸把话说清楚', '位外' in err, True)
            code, _o, err = run([PY, LAUNCH, '--port-embed', 4315, '--kb', work])
            check('worktree 端口闸：撞主位常驻 4315 被拒', code, 2)
            check('端口闸把话说清楚', '主位常驻端口' in err, True)
        else:
            print('  ·（本位就是主位，两道 worktree 越界闸不适用，跳过）')

        # ── C 收尾：停 serve → 回落冷载，行为一字不变 ─────────────────
        print('\n── C 收尾：停 serve → 自动回落冷载【三态③】──')
        code, out, _e = launch('--stop', '--only', 'embed')
        check('embed --stop 退出码 0', code, 0)
        check('serve 停干净了，探活=None', embed_tool.serve_health(pe), None)
        sys.path.insert(0, str(ROOT / '工具箱'))
        import 启动台                                      # noqa: PLC0415
        # 🔴 停完端口上会留一堆 `TIME_WAIT … 0` 的行，只看本地端口就会捡到 pid=0 当"还占着"
        check('停后 pid_by_port=None（TIME_WAIT 残留不算占用）', 启动台.pid_by_port(pe), None)
        check('kb 端口同样干净', 启动台.pid_by_port(pk), None)
        vec_back, dim_back, name_back = embed_tool.embed_texts(
            ['计算：$-8+15\\div(-3)\\times 2$'], quiet=True, serve_port=pe)
        check('serve 没了照样出向量（回落冷载，不是"查不出来"）', dim_back, 512)
        check('回落后模型名不变', name_back, name_cold)
        check('回落后向量与冷载一致（行为一字不变）',
              cosine(vec_back[0], vec_cold[0]) >= 0.99999, True)
    finally:
        run([PY, LAUNCH, '--port-embed', pe, '--port-kb', pk, '--stop', '--only', 'embed'])
        run([PY, LAUNCH, '--port-embed', pe, '--port-kb', pk, '--stop', '--only', 'kb'])

    print(f'\n=== {N[0] - len(FAIL)}/{N[0]} 通过 ===' + ('' if not FAIL else f'\n🔴 未过：{FAIL}'))
    return 0 if not FAIL else 1


def probe_dead(port, path):
    try:
        http(f'http://127.0.0.1:{port}{path}', timeout=1.2)
        return False
    except Exception:
        return True


if __name__ == '__main__':
    raise SystemExit(main())
