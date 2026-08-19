# -*- coding: utf-8 -*-
"""启动台——一条命令拉起/探活/全停 v2 的两个常驻后台服务（PRD-003 阶段4）。

管两个（都只绑 127.0.0.1，都是本机进程间用）：
  kb    console/server/kb-read-api.mjs   :4310   展示台的只读数据口（node:sqlite readOnly）
  embed 工具箱/检索/embed_serve.py       :4315   语意常驻 serve（预载 bge，找题/入库收尾走它）

用法：
  python 工具箱\\启动台.py                          # 起（🔴 幂等：已在跑的探活跳过，不起第二个）
  python 工具箱\\启动台.py --status                 # 只看，不动
  python 工具箱\\启动台.py --stop                   # 全停（embed 走 /shutdown 优雅停，停不掉再 taskkill）
  python 工具箱\\启动台.py --only embed             # 只管一个（kb / embed）
  python 工具箱\\启动台.py --kb <库路径> --port-kb 4316 --port-embed 4317   # 沙盘实例

🔴 四条闸（每条都因为有过坑）：
  · **幂等**：起之前先探活；活着就打印 pid 跳过。绝不"再起一个"——两个 embed serve 各载一份模型
    互相抢 CPU，症状只是"好像变慢了"，最难查；
  · **worktree 里不许碰主位库**：本脚本在 worktree 跑时（.git 是文件），--kb 指到本位之外一律拒，
    要跑测试实例就显式指沙盘副本；真要越界得写 --allow-outside-db，让越界这件事留在命令行上；
  · **worktree 里端口自动错开**（kb 4316 / embed 4317），不跟主位常驻的 4310/4315 撞——
    撞了的话主位那两个会被 --stop 顺手停掉，比数据坏账还难发现；
  · **探活一律绕代理**（本机有代理，urllib 默认会把 127.0.0.1 也劫走，等价 curl --noproxy "*"）；
    🔴 本机还有一条实伤：连**没人监听的**本地端口不是秒回 ConnectionRefused，而是**卡到超时**
    （有东西在丢 SYN）——所以"不在"这个判断天然要等满超时，别把超时设长。

进程记录（pid/日志）落**系统临时目录**，不进 git、不脏工作区：
  %TEMP%\\ai-bkb-v2-启动台\\<位名-哈希>\\<服务>-<端口>.json / .log        （--status 会打印实际路径）
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent                    # …/工具箱
ROOT = HERE.parent                                        # …/ai-bkb-v2（worktree 里=本位）
sys.path.insert(0, str(HERE / '检索'))
from embed_tool import EmbedError, MAIN_ROOT, resolve_venv  # noqa: E402

IS_WORKTREE = MAIN_ROOT.resolve() != ROOT.resolve()
DEFAULT_KB_DB = MAIN_ROOT / '知识库' / 'kb.db'             # 缺省=主位库（主位常驻的正常起法）
# 🔴 worktree 里默认端口错开主位常驻，避免测试实例把主位的服务停掉
DEFAULT_PORT_KB = 4316 if IS_WORKTREE else 4310
DEFAULT_PORT_EMBED = 4317 if IS_WORKTREE else 4315
HOST = '127.0.0.1'
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 🔴 绕代理


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def run_dir():
    """进程记录目录：按 v2 根路径分桶（主位与各 worktree 各记各的，互不串）。"""
    tag = hashlib.sha1(str(ROOT.resolve()).lower().encode('utf-8')).hexdigest()[:8]
    d = Path(tempfile.gettempdir()) / 'ai-bkb-v2-启动台' / f'{ROOT.name}-{tag}'
    d.mkdir(parents=True, exist_ok=True)
    return d


def rec_path(name, port):
    return run_dir() / f'{name}-{port}.json'


def log_path(name, port):
    return run_dir() / f'{name}-{port}.log'


# ══════════════════════════════════════════════════════════════════════
# 探活 / 端口 / 进程
# ══════════════════════════════════════════════════════════════════════
def http_json(url, timeout=1.5):
    with _OPENER.open(urllib.request.Request(url, headers={'Accept': 'application/json'}),
                      timeout=timeout) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def probe(svc, port, timeout=1.5):
    """探活 → (活着?, 说明 dict|错误串)。"""
    url = f'http://{HOST}:{port}{svc["health"]}'
    try:
        code, body = http_json(url, timeout)
    except Exception as e:
        return False, str(e)
    if code != 200:
        return False, f'HTTP {code}'
    return True, body


def pid_by_port(port):
    """端口 → 正在**监听**它的 pid（pidfile 丢了也停得掉）；没人监听回 None。

    🔴 实伤：服务停掉后本地端口会留一堆 `TIME_WAIT ... 0` 的行，本地地址同样是 `127.0.0.1:<port>`。
       只看"本地端口对得上"就会捡到 **pid=0**，于是"端口还占着"永远为真。
       所以：只认 5 列的 TCP 行、状态 LISTENING、pid > 0。
    """
    try:
        out = subprocess.run(['netstat', '-ano', '-p', 'tcp'], capture_output=True, text=True,
                             encoding='utf-8', errors='replace', timeout=25).stdout
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != 'TCP':
            continue
        if not parts[1].endswith(f':{port}') or parts[3].upper() != 'LISTENING':
            continue
        if parts[4].isdigit() and int(parts[4]) > 0:
            return int(parts[4])
    return None


def alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        out = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/NH'],
                             capture_output=True, text=True, encoding='utf-8',
                             errors='replace', timeout=20).stdout
    except Exception:
        return False
    # 没匹配到时 tasklist 打的是「信息: 没有运行的任务…」，里头不会有 pid 这个独立字段
    return any(str(pid) in ln.split() for ln in out.splitlines())


def kill(pid):
    subprocess.run(['taskkill', '/PID', str(int(pid)), '/T', '/F'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)


# ══════════════════════════════════════════════════════════════════════
# 服务定义
# ══════════════════════════════════════════════════════════════════════
def svc_kb(args):
    node = shutil.which('node')
    script = ROOT / 'console' / 'server' / 'kb-read-api.mjs'
    env = dict(os.environ, KB_DB=str(args.kb), KB_API_PORT=str(args.port_kb))
    return {
        'name': 'kb', 'port': args.port_kb, 'health': '/api/kb/stats',
        'desc': f'kb 读 API（只读）库={args.kb}',
        'cmd': [node, str(script)] if node else None,
        'env': env, 'ready_s': 20,
        'why_no': None if node else 'PATH 里找不到 node（kb 读 API 是 node:sqlite 写的，装 node 再来）',
        'precheck': None if script.is_file() else f'脚本不在：{script}',
        'precheck2': None if Path(args.kb).is_file() else
        f'库不存在：{args.kb}（worktree 里先拷一份沙盘副本，或 python 工具箱/库/init_db.py --only kb）',
    }


def svc_embed(args):
    try:
        py = str(resolve_venv(args.venv))
        why = None
    except EmbedError as e:
        py, why = None, str(e).splitlines()[0]
    script = ROOT / '工具箱' / '检索' / 'embed_serve.py'
    # 🔴 直接用 venv 的 python + --no-reexec：不多套一层壳，pid 就是 serve 本身
    cmd = None
    if py:
        cmd = [py, str(script), '--no-reexec', '--port', str(args.port_embed)]
        if args.model_dir:
            cmd += ['--model-dir', args.model_dir]
    return {
        'name': 'embed', 'port': args.port_embed, 'health': '/health',
        'desc': 'embed 常驻 serve（预载 bge，只读复用主位 venv 与权重）',
        'cmd': cmd,
        'env': dict(os.environ), 'ready_s': 180,       # 冷机第一次载模型可能很慢，给足
        'why_no': why,
        'precheck': None if script.is_file() else f'脚本不在：{script}',
        'precheck2': None,
    }


def build_svcs(args):
    out = []
    if args.only in (None, 'kb'):
        out.append(svc_kb(args))
    if args.only in (None, 'embed'):
        out.append(svc_embed(args))
    return out


# ══════════════════════════════════════════════════════════════════════
# 动作
# ══════════════════════════════════════════════════════════════════════
def do_status(svcs):
    print(f'启动台 · 位={ROOT}' + ('（worktree）' if IS_WORKTREE else '（主位）'))
    print(f'进程记录目录：{run_dir()}')
    n_up = 0
    for s in svcs:
        up, info = probe(s, s['port'])
        if up:
            n_up += 1
            pid = info.get('pid') if isinstance(info, dict) else None
            if pid is None:
                pid = pid_by_port(s['port'])
            extra = ''
            if s['name'] == 'embed' and isinstance(info, dict):
                extra = (f" 模型={info.get('model')} dim={info.get('dim')} "
                         f"已服务 {info.get('served')} 次/{info.get('texts')} 条 起了 {info.get('uptime_s')}s")
            if s['name'] == 'kb' and isinstance(info, dict):
                extra = (f" 库={info.get('db_path')} 只读={info.get('readonly')} "
                         f"表 {info.get('table_total')}（非空 {info.get('nonempty_total')}）")
            print(f'  ● {s["name"]:<6}:{s["port"]}  在   pid={pid}{extra}')
        else:
            print(f'  ○ {s["name"]:<6}:{s["port"]}  不在（{str(info)[:70]}）')
        rec = rec_path(s['name'], s['port'])
        if rec.is_file():
            try:
                r = json.loads(rec.read_text(encoding='utf-8'))
                print(f'        记录 {rec.name}：pid={r.get("pid")} 起于 {r.get("started")} '
                      f'日志 {log_path(s["name"], s["port"])}')
            except Exception:
                pass
    return 0 if n_up == len(svcs) else 1


def do_start(svcs, args):
    bad = 0
    for s in svcs:
        up, info = probe(s, s['port'])
        if up:
            pid = (info or {}).get('pid') or pid_by_port(s['port'])
            print(f'● {s["name"]} :{s["port"]} 已在跑（pid={pid}）——探活通过，跳过（幂等）')
            continue
        for key in ('precheck', 'precheck2'):
            if s.get(key):
                print(f'🔴 {s["name"]} 起不了：{s[key]}')
                bad += 1
                break
        else:
            if not s['cmd']:
                print(f'🔴 {s["name"]} 起不了：{s["why_no"]}')
                bad += 1
                continue
            occupier = pid_by_port(s['port'])
            if occupier:
                print(f'🔴 {s["name"]} :{s["port"]} 被 pid={occupier} 占着但探活不通——'
                      f'不是本服务或者它病了。先看清楚再动手（--stop 会连它一起杀）。')
                bad += 1
                continue
            lg = log_path(s['name'], s['port'])
            print(f'· 起 {s["name"]} :{s["port"]}  {s["desc"]}')
            print(f'  命令：{" ".join(s["cmd"])}')
            print(f'  日志：{lg}')
            with open(lg, 'ab') as fh:
                fh.write(f'\n===== {now()} 启动台起 {s["name"]} :{s["port"]} =====\n'
                         .encode('utf-8'))
                flags = 0
                if os.name == 'nt':          # 脱离控制台常驻：关掉这个 shell 也不跟着死
                    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                proc = subprocess.Popen(s['cmd'], cwd=str(ROOT), env=s['env'],
                                        stdin=subprocess.DEVNULL, stdout=fh, stderr=fh,
                                        creationflags=flags)
            rec_path(s['name'], s['port']).write_text(json.dumps(
                {'name': s['name'], 'port': s['port'], 'pid': proc.pid, 'started': now(),
                 'cmd': s['cmd'], 'root': str(ROOT), 'log': str(lg)},
                ensure_ascii=False, indent=2), encoding='utf-8')
            ok = wait_ready(s, proc, args.timeout or s['ready_s'])
            if not ok:
                bad += 1
    return bad


def wait_ready(s, proc, budget):
    t0 = time.time()
    while time.time() - t0 < budget:
        if proc.poll() is not None:
            tail = tail_log(s)
            print(f'🔴 {s["name"]} 起来就退了（退出码 {proc.returncode}）。日志末段：\n{tail}')
            return False
        up, info = probe(s, s['port'], timeout=1.0)
        if up:
            print(f'  ✓ {s["name"]} :{s["port"]} 就绪（{time.time() - t0:.1f}s，pid={proc.pid}）'
                  + (f' 模型={info.get("model")} dim={info.get("dim")} 载入 {info.get("load_s")}s'
                     if s['name'] == 'embed' and isinstance(info, dict) else ''))
            return True
        time.sleep(0.4)
    print(f'🔴 {s["name"]} :{s["port"]} 等了 {budget}s 还没就绪（进程还活着，pid={proc.pid}）。'
          f'日志末段：\n{tail_log(s)}')
    return False


def tail_log(s, n=12):
    p = log_path(s['name'], s['port'])
    if not p.is_file():
        return '  （没有日志文件）'
    try:
        lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError as e:
        return f'  （日志读不了：{e}）'
    return '\n'.join('  | ' + x for x in lines[-n:]) or '  （日志是空的）'


def do_stop(svcs):
    bad = 0
    for s in svcs:
        up, _info = probe(s, s['port'])
        pid = None
        rec = rec_path(s['name'], s['port'])
        if rec.is_file():
            try:
                pid = json.loads(rec.read_text(encoding='utf-8')).get('pid')
            except Exception:
                pid = None
        if not up and not (pid and alive(pid)) and not pid_by_port(s['port']):
            print(f'○ {s["name"]} :{s["port"]} 本来就没在跑，跳过')
            rec.unlink(missing_ok=True)
            continue
        if s['name'] == 'embed' and up:          # 优雅停：让它自己收摊
            try:
                req = urllib.request.Request(f'http://{HOST}:{s["port"]}/shutdown',
                                             data=b'{}', method='POST',
                                             headers={'Content-Type': 'application/json'})
                with _OPENER.open(req, timeout=5) as r:
                    r.read()
                print(f'· {s["name"]} :{s["port"]} 已发 /shutdown')
            except Exception as e:
                print(f'· {s["name"]} /shutdown 没送到（{e}），改硬停')
        deadline = time.time() + 8
        while time.time() < deadline:
            if not probe(s, s['port'], timeout=0.6)[0] and not pid_by_port(s['port']):
                break
            time.sleep(0.3)
        # 🔴 两个 pid 都要收：记录里的可能只是 venv 的启动壳（uv 的 python.exe 是 trampoline，
        #    真正监听的是它拉起的子进程，pid 不是同一个）——只杀一个会留活口。
        holders = [x for x in (pid_by_port(s['port']), pid) if x and alive(x)]
        for h_pid in dict.fromkeys(holders):
            print(f'· {s["name"]} :{s["port"]} 还活着（pid={h_pid}），taskkill /T /F')
            kill(h_pid)
        if holders:
            time.sleep(0.6)
        still = pid_by_port(s['port'])
        if still:
            print(f'🔴 {s["name"]} :{s["port"]} 停不掉（pid={still} 还在）——人工看一眼')
            bad += 1
        else:
            print(f'✓ {s["name"]} :{s["port"]} 已停')
            rec.unlink(missing_ok=True)
    return bad


# ══════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(
        description='启动台：一条命令拉起/探活/全停 kb 读 API(:4310) + embed 常驻 serve(:4315)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='🔴 起是幂等的：已在跑的只探活不重起。worktree 里端口自动错开主位（4316/4317）。\n'
               '退出码：0=该在的都在／该停的都停；1=有服务没起来或没停掉；2=撞越界闸。\n'
               '（--status 也照这个口径：全在=0，缺一个=1，好当探活用。）')
    ap.add_argument('--stop', action='store_true', help='全停（embed 先 /shutdown 优雅停）')
    ap.add_argument('--status', action='store_true', help='只探活，不起不停')
    ap.add_argument('--only', choices=('kb', 'embed'), help='只管其中一个')
    ap.add_argument('--kb', default=str(DEFAULT_KB_DB),
                    help=f'kb 读 API 用哪个库（缺省主位库 {DEFAULT_KB_DB}）'
                         f'；🔴 worktree 里必须显式指沙盘副本')
    ap.add_argument('--port-kb', dest='port_kb', type=int, default=DEFAULT_PORT_KB)
    ap.add_argument('--port-embed', dest='port_embed', type=int, default=DEFAULT_PORT_EMBED)
    ap.add_argument('--venv', help='embed serve 用哪个 python（缺省 本位→主位 .venv）')
    ap.add_argument('--model-dir', dest='model_dir', help='模型权重根（缺省 本位→主位）')
    ap.add_argument('--timeout', type=int, help='等就绪的秒数（缺省 kb 20s / embed 180s）')
    ap.add_argument('--allow-outside-db', dest='allow_outside', action='store_true',
                    help='🔴 显式越界：允许 worktree 里的实例挂本位之外的库（默认拒）')
    args = ap.parse_args()
    args.kb = str(Path(args.kb).resolve())

    # 🔴 worktree 两道越界闸（--status 只探活不碰库不动进程，两闸都不管它）
    if IS_WORKTREE and not args.status:
        # ① 库闸：不许拿主位的库起测试实例（SQLite 单写者，双写必坏账）——只管「起」
        inside = str(Path(args.kb)).lower().startswith(str(ROOT.resolve()).lower() + os.sep)
        if not args.stop and args.only != 'embed' and not inside and not args.allow_outside:
            print(f'🔴 这是 worktree（{ROOT}），而 --kb 指到了位外：{args.kb}\n'
                  f'   worktree 里绝不碰主位的库（CLAUDE.md §2 硬纪律一）。\n'
                  f'   测试请拷一份沙盘副本再指过来，例如：\n'
                  f'     --kb {ROOT}\\试验场\\<战役>\\kb.db\n'
                  f'   真要越界：加 --allow-outside-db（让越界这件事留在命令行上）', file=sys.stderr)
            return 2
        # ② 端口闸：起和停都管——撞上主位常驻端口，--stop 会把主位的服务一起停掉
        hit = [f'kb={args.port_kb}' for _ in (1,) if args.port_kb == 4310] + \
              [f'embed={args.port_embed}' for _ in (1,) if args.port_embed == 4315]
        if hit:
            print(f'🔴 worktree 里用了主位常驻端口（{" ".join(hit)}）——'
                  f'{"--stop 会把主位的服务一起停掉" if args.stop else "会跟主位的服务抢端口"}。\n'
                  f'   请改用 4316/4317 一类（本脚本在 worktree 里的缺省就是它们）。', file=sys.stderr)
            return 2

    svcs = build_svcs(args)
    if args.status:
        return do_status(svcs)
    if args.stop:
        bad = do_stop(svcs)
        return 0 if bad == 0 else 1
    bad = do_start(svcs, args)
    print()
    do_status(svcs)
    if bad:
        print(f'\n🔴 有 {bad} 个服务没起来——上面写了原因，别当没看见')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
