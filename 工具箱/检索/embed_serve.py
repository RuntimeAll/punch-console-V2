# -*- coding: utf-8 -*-
"""语意层常驻 serve（D-20 第③层的「热身一次」版）——预载 bge-small-zh-v1.5，之后每次算向量毫秒级。

为什么要它（PRD-002 遗留账 → PRD-003 阶段4 收）：冷载路径每调一次就起一次 sidecar，
`import torch` + 载权重要 5~6s；找题/组卷/入库收尾一天几十次，全花在热身上。
serve 起一次常驻，embed_tool / query_core / find_questions / ingest_flow 探活 :4315
在就走它，不在就**回落现行冷载路径**。

🔴 五条（每条都是闸，不是注释）：
  · **venv 与模型权重只读复用主位**：解释器 = <主位>\\工具箱\\检索\\.venv\\Scripts\\python.exe，
    权重 = <主位>\\punch-console\\embed\\models（punch-console 已冻结只读，权重继续用）。
    本文件**绝不 pip install 任何东西、绝不建新 venv**；缺依赖=明确报错带命令。
  · **serve 是加速器不是依赖**：它挂了整条检索线只是变慢，绝不许变成「查不出来」——
    回落由客户端（embed_tool.embed_texts）负责，本文件只管把话说清楚。
  · **只绑 127.0.0.1**，且 handler 再查一次来客地址（回环之外一律 403）；/shutdown 同此闸。
  · **编码坑照 _embed_worker.py 已修的路数**：请求体**按字节读再显式 utf-8 解**——
    本机 python 默认走 GBK，中文题面会被解成乱码带代理对（\\udcxx），喂进 tokenizers 的
    Rust 侧直接抛 `TextEncodeInput must be Union[...]`，报错原文一个字不提编码。
    出参固定 utf-8；stdout/stderr 开头 reconfigure（GBK 控制台 emoji 杀进程）。
  · **端口不许复用**：allow_reuse_address=False，撞端口就报错退出，绝不悄悄起第二个把第一个盖住
    （两个 serve 各载一份 500MB 模型还互相抢，是最难查的那种"好像变慢了"）。

协议（字段名即契约；出错一律 {"ok":false,"error":"原话"}，绝不回空向量充数）：
  GET  /health   → 200 {"ok":true,"model":"bge-small-zh-v1.5","dim":512,"model_dir":"…",
                        "pid":1234,"port":4315,"uptime_s":12.3,"served":7,"texts":123,"load_s":5.8}
  POST /embed    ← {"texts":["…", …],"batch":64}  或  {"text":"…"}
                 → 200 {"ok":true,"model":…,"dim":512,"count":N,"vecs_b64":["…", …],"ms":12}
                 🔴 vecs_b64 里每条 base64 解出来**就是 question_vec.vec 的 BLOB 本体**
                    （float32 小端连续、已 L2 归一化 ⇒ 余弦=点积），存进库零转换=存取同构。
  POST /shutdown → 200 {"ok":true,…} 然后进程退出（启动台 --stop 走这条，优雅停）

起法：
  python 工具箱\\检索\\embed_serve.py                 # 系统 python 起也行：自动改用主位 venv 接管
  <主位venv>\\python.exe 工具箱\\检索\\embed_serve.py --no-reexec --port 4315
  python 工具箱\\启动台.py                            # 🔴 正路：幂等拉起 :4310 读 API + :4315 本 serve
"""
import argparse
import base64
import importlib.util
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from embed_tool import (DEFAULT_SERVE_PORT, EmbedError, MAIN_ROOT,  # noqa: E402
                        model_name_of, resolve_model_dir, resolve_venv)

HERE = Path(__file__).resolve().parent
HOST = '127.0.0.1'                       # 🔴 只绑回环：本机进程间用，不对外
MAX_BODY = 16 * 1024 * 1024              # 单次请求上限（一批 256 题的题面远远够）

STATE = {'model': None, 'name': None, 'dim': None, 'model_dir': None,
         'started': time.time(), 'load_s': None, 'served': 0, 'texts': 0, 'port': None}
LOCK = threading.Lock()                  # SentenceTransformer.encode 不保证线程安全：一次只算一批


def now():
    return datetime.now().strftime('%H:%M:%S')


def log(msg):
    print(f'[{now()}] {msg}', flush=True)


def health():
    return {
        'ok': STATE['model'] is not None,
        'service': 'embed_serve',
        'model': STATE['name'], 'dim': STATE['dim'], 'model_dir': STATE['model_dir'],
        'pid': __import__('os').getpid(), 'port': STATE['port'],
        'uptime_s': round(time.time() - STATE['started'], 1),
        'load_s': STATE['load_s'], 'served': STATE['served'], 'texts': STATE['texts'],
    }


# ══════════════════════════════════════════════════════════════════════
# 文本闸（🔴 上游编码坏了要早报，别喂进 tokenizer 才炸）
# ══════════════════════════════════════════════════════════════════════
def check_texts(req):
    texts = req.get('texts')
    if texts is None and isinstance(req.get('text'), str):
        texts = [req['text']]
    if not isinstance(texts, list):
        raise ValueError('缺 texts（字符串数组）或 text（单条字符串）')
    if not texts:
        raise ValueError('texts 为空——没文本可算')
    bad = [i for i, t in enumerate(texts)
           if not isinstance(t, str) or any('\ud800' <= c <= '\udfff' for c in t)]
    if bad:
        raise ValueError(f'texts[{bad[:5]}] 不是干净字符串（含代理对/非 str）——'
                         f'上游编码坏了（GBK 解 utf-8 的典型症状），别喂进 tokenizer')
    return texts


def encode(texts, batch):
    """算向量 → (base64 表, dim)。🔴 normalize_embeddings=True ⇒ 余弦=点积；float32 小端连续。"""
    import numpy as np
    with LOCK:
        vec = STATE['model'].encode(texts, batch_size=batch, normalize_embeddings=True,
                                    show_progress_bar=False, convert_to_numpy=True)
    arr = np.asarray(vec, dtype='<f4')
    if arr.ndim != 2 or arr.shape[0] != len(texts):
        raise ValueError(f'模型返回形状 {arr.shape} 与送入 {len(texts)} 条对不上——数量对不上不收')
    if arr.shape[1] != STATE['dim']:
        raise ValueError(f'本次 dim={arr.shape[1]} ≠ 启动时 dim={STATE["dim"]}——维度会漂就不能存，拒')
    return [base64.b64encode(arr[i].tobytes()).decode('ascii') for i in range(arr.shape[0])], arr.shape[1]


# ══════════════════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'        # 每条响应都带 Content-Length（下面统一给）
    server_version = 'embed_serve/1'
    sys_version = ''

    def log_message(self, fmt, *a):      # 默认那行 stderr 访问日志没用，自己打
        pass

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')   # 🔴 固定 utf-8
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _loopback_only(self):
        ip = (self.client_address or ('?',))[0]
        if ip in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
            return True
        self._send(403, {'ok': False, 'error': f'本 serve 只认回环地址，来客 {ip} 拒'})
        return False

    def _read_json(self):
        try:
            n = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            raise ValueError('Content-Length 非法')
        if n <= 0:
            raise ValueError('请求体为空（要 JSON）')
        if n > MAX_BODY:
            raise ValueError(f'请求体 {n} 字节超上限 {MAX_BODY}——分批送（embed_tool 按 256 题一批）')
        raw = self.rfile.read(n)                       # 🔴 按字节读
        try:
            txt = raw.decode('utf-8')                  # 🔴 再显式 utf-8 解
        except UnicodeDecodeError as e:
            raise ValueError(f'请求体不是 utf-8（{e}）——桥两头都必须 utf-8，'
                             f'GBK 会把中文毁成代理对，报错原文一个字不提编码')
        return json.loads(txt)

    def do_GET(self):
        if not self._loopback_only():
            return
        if self.path.split('?')[0] == '/health':
            return self._send(200, health())
        self._send(404, {'ok': False, 'error': '无此端点',
                         'endpoints': ['GET /health', 'POST /embed', 'POST /shutdown']})

    def do_POST(self):
        if not self._loopback_only():
            return
        path = self.path.split('?')[0]
        if path == '/shutdown':
            log(f'收到 /shutdown（已服务 {STATE["served"]} 次 / {STATE["texts"]} 条），退出')
            self._send(200, dict(health(), bye=True))
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if path != '/embed':
            return self._send(404, {'ok': False, 'error': '无此端点',
                                    'endpoints': ['GET /health', 'POST /embed', 'POST /shutdown']})
        t0 = time.time()
        try:
            req = self._read_json()
            texts = check_texts(req)
            batch = int(req.get('batch') or 64)
            b64, dim = encode(texts, batch)
        except ValueError as e:
            log(f'✗ /embed 400：{e}')
            return self._send(400, {'ok': False, 'error': str(e)})
        except Exception as e:                        # noqa: BLE001 —— 500 也要给可解析的原话
            log(f'✗ /embed 500：{type(e).__name__}: {e}')
            return self._send(500, {'ok': False, 'error': f'{type(e).__name__}: {e}'})
        ms = int((time.time() - t0) * 1000)
        STATE['served'] += 1
        STATE['texts'] += len(texts)
        log(f'/embed {len(texts)} 条 {ms}ms（累计 {STATE["served"]} 次 / {STATE["texts"]} 条）')
        self._send(200, {'ok': True, 'model': STATE['name'], 'dim': dim,
                         'count': len(texts), 'vecs_b64': b64, 'ms': ms})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # 🔴 不许 SO_REUSEADDR：撞端口就 OSError 退出，绝不悄悄起第二个把第一个盖住
    allow_reuse_address = False


# ══════════════════════════════════════════════════════════════════════
# 起
# ══════════════════════════════════════════════════════════════════════
def load_model(model_dir):
    # 🔴 零外部 API 的**机器保证**（不是注释）：先把 HF/transformers 顶成离线，
    #    权重目录里少了文件就当场报错，绝不偷偷联网下载（本机 HF 大文件经代理还会被掐，
    #    那时症状是"起服务卡住"，比报错难查十倍）。
    import os as _os
    _os.environ.setdefault('HF_HUB_OFFLINE', '1')
    _os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    from sentence_transformers import SentenceTransformer
    import numpy as np
    t0 = time.time()
    m = SentenceTransformer(str(model_dir), device='cpu')
    warm = np.asarray(m.encode(['热身一条，顺便量 dim'], normalize_embeddings=True,
                               convert_to_numpy=True), dtype='<f4')
    return m, int(warm.shape[1]), round(time.time() - t0, 2)


def reexec_into_venv(args):
    """本解释器没有 sentence_transformers → 用**主位 venv** 的 python 接管（🔴 只读复用，不装东西）。

    用 subprocess 不用 os.execv：Windows 上 execv 是"起新进程再自杀"，PID 会变，
    看着像进程跑丢了。这里父进程留着当薄壳，Ctrl+C 同进程组一起收。
    启动台走的是「直接用 venv python 起 + --no-reexec」，没有这层壳。
    """
    py = resolve_venv(args.venv)
    if Path(py).resolve() == Path(sys.executable).resolve():
        raise EmbedError(
            f'venv python 自己也没有 sentence_transformers：{py}\n'
            f'  🔴 本卡红线：不许 pip install 进主位 venv、不许建新 venv。\n'
            f'  请人工确认主位 venv 是否被动过：'
            f'"{py}" -c "import sentence_transformers"')
    log(f'本解释器没有 sentence_transformers，改用主位 venv 接管（只读复用，不装任何东西）：\n'
        f'         {py}')
    cmd = [str(py), str(Path(__file__).resolve()), '--no-reexec'] + sys.argv[1:]
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser(
        description='语意常驻 serve（预载 bge，:4315 毫秒级出向量；挂了客户端自动回落冷载）')
    ap.add_argument('--port', type=int, default=DEFAULT_SERVE_PORT,
                    help=f'监听端口（缺省 {DEFAULT_SERVE_PORT}；worktree 测试用 4317 错开主位常驻）')
    ap.add_argument('--model-dir', dest='model_dir',
                    help='模型权重根（缺省=本位 punch-console/embed/models，没有则只读复用主位）')
    ap.add_argument('--venv', help='venv 里的 python（只在需要接管时用；缺省=本位→主位）')
    ap.add_argument('--no-reexec', dest='no_reexec', action='store_true',
                    help='不许改用 venv 接管（启动台直起 venv python 时用，避免多一层壳）')
    args = ap.parse_args()

    if importlib.util.find_spec('sentence_transformers') is None:
        if args.no_reexec:
            print(f'🔴 本解释器（{sys.executable}）没有 sentence_transformers，而 --no-reexec 禁止接管。\n'
                  f'   正路：python 工具箱\\启动台.py（它直接用主位 venv 起）\n'
                  f'   主位 venv：{MAIN_ROOT}\\工具箱\\检索\\.venv\\Scripts\\python.exe',
                  file=sys.stderr)
            return 2
        try:
            return reexec_into_venv(args)
        except EmbedError as e:
            print(f'🔴 {e}', file=sys.stderr)
            return 2

    try:
        mdir = resolve_model_dir(args.model_dir)
    except EmbedError as e:
        print(f'🔴 {e}', file=sys.stderr)
        return 2
    name = model_name_of(mdir)
    log(f'载模型 {name} ← {mdir}（第一次要几秒，这正是 serve 存在的理由）')
    try:
        model, dim, load_s = load_model(mdir)
    except Exception as e:                            # noqa: BLE001
        print(f'🔴 模型载不起来：{type(e).__name__}: {e}\n'
              f'   权重目录={mdir}；解释器={sys.executable}', file=sys.stderr)
        return 2
    STATE.update({'model': model, 'name': name, 'dim': dim, 'model_dir': str(mdir),
                  'started': time.time(), 'load_s': load_s, 'port': int(args.port)})

    try:
        httpd = Server((HOST, int(args.port)), Handler)
    except OSError as e:
        print(f'🔴 端口 {HOST}:{args.port} 绑不上（{e}）。\n'
              f'   多半已经有一个 serve 在跑——先探活：'
              f'curl.exe -s --noproxy "*" http://{HOST}:{args.port}/health\n'
              f'   幂等起法（在跑就跳过）：python 工具箱\\启动台.py', file=sys.stderr)
        return 3
    import os as _os
    log(f'serve 起：pid={_os.getpid()} http://{HOST}:{args.port} 模型={name} dim={dim} 载入 {load_s}s')
    log('探活 GET /health｜算向量 POST /embed｜停 POST /shutdown（或 python 工具箱\\启动台.py --stop）')
    try:
        httpd.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        log('Ctrl+C，退出')
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
