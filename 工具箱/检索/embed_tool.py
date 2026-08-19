# -*- coding: utf-8 -*-
"""语意向量层（D-20 第③层落地）——question_vec 的唯一写入通路，零外部 API。

正本＝认知/数据结构.md §三c：③语意=本地 bge-small-zh-v1.5 sidecar（权重复用 punch-console/embed/models，
venv=工具箱/检索/.venv），向量落 question_vec（模型名同存，换模型重算），量级内 numpy 现算余弦。

用法（--db 缺省=脚本位置自解析 <v2根>/知识库/kb.db；worktree 里跑=天然沙盘）：
  python 工具箱/检索/embed_tool.py build [--force] [--limit N]      # 给缺向量的题算向量入库
  python 工具箱/检索/embed_tool.py query --text "路程速度时间的应用题" [--topk 8]
  python 工具箱/检索/embed_tool.py stat                              # 覆盖率/模型/维度 + serve 探活
公共参数：--venv <venv 里的 python.exe>  --model-dir <模型权重根>（两者都可覆盖，缺省见下）
          --serve-port <口>（缺省 4315 / 环境变量 EMBED_SERVE_PORT）  --no-serve（强制走冷载）

🔴 六条：
  · **常驻 serve 优先**（PRD-003 阶段4）：探活 127.0.0.1:4315 在 ⇒ 走它（毫秒级，模型早载好了）；
    不在 ⇒ **回落下面这条冷载路径，行为一字不变**。serve 是加速器不是依赖，
    它挂了这条线只是变慢，绝不许变成「查不出来」。起法=`python 工具箱/启动台.py`；
  · 算向量的是 venv 里的 _embed_worker.py（sidecar），主脚本只做「取文本 / 存 BLOB / 点乘排序」，
    系统 python 不需要 torch；worktree 里本位没有 .venv/权重时**只读复用主位**
    （主位由 .git 指针机械解析，见 _main_root）——🔴 只执行/只读，绝不 pip install 进主位 venv；
  · 文本口径 = **题面全部 text 块 md 拼接**（query_core.plain_text，与 match_key 同源思路），
    纯图题无正文 → 如实列出跳过，绝不塞空串充数；
  · BLOB = float32 小端连续 + 模型名 + dim 同存；**模型名对不上的向量一律不参与比对**（换模型=重算，不混存）；
  · 向量已 L2 归一化 ⇒ 余弦 = 点积，numpy 一次矩阵乘全扫（万级题量内够用，不引向量库）；
  · venv / 模型缺失 → **明确报错带建法**，绝不静默降级成「没有结果」。
每次执行落 skill_log（skill='找题'）。
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

def _utf8(stream):
    """py 头双 reconfigure（GBK 控制台 emoji 杀进程）——但要挡住一条实伤（2026-08-19 本卡踩中）：

    🔴 本文件是**懒加载**的（ingest_flow 入库收尾时才 import 它），那一刻调用方很可能
       正把 stdout 重定向到 StringIO（contextlib.redirect_stdout，测试与批处理里到处都是），
       而 StringIO **没有 .reconfigure** —— 裸调用当场 AttributeError，
       整个语意层就这么"消失"了（收尾只打一行"检索模块加载失败"，人根本不会往编码上想）。
       有则调，没有就算：本来就不是真控制台，也没有 GBK 问题。
    """
    try:
        stream.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError, OSError):
        pass


_utf8(sys.stdout)
_utf8(sys.stderr)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_core import plain_text, first_text  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                                   # …/ai-bkb-v2（worktree 里=本位沙盘）


def _main_root(root):
    """worktree 里跑时的**主位**——venv 与模型权重只读复用它。由 .git 指针机械解析，不硬编码路径。

    · 主位：<root>/.git 是**目录** ⇒ 就是它自己；
    · worktree：<root>/.git 是**文件**，内容 `gitdir: <主位>/.git/worktrees/<位名>`
      ⇒ 上溯到 .git 的父目录就是主位。
    🔴 只读复用的边界：只**执行**主位 venv 里的 python、只**读**主位的模型权重；
       绝不 pip install 进主位 venv、绝不建新 venv、绝不写主位任何文件（PRD-003 D 线红线）。
    """
    g = Path(root) / '.git'
    if g.is_dir():
        return Path(root)
    if g.is_file():
        try:
            txt = g.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return Path(root)
        for line in txt.splitlines():
            if line.strip().lower().startswith('gitdir:'):
                p = Path(line.split(':', 1)[1].strip())
                if not p.is_absolute():
                    p = (Path(root) / p).resolve()
                for anc in [p] + list(p.parents):
                    if anc.name == '.git':
                        return anc.parent
    return Path(root)


MAIN_ROOT = _main_root(ROOT)                             # 主位（本位就是主位时=ROOT）
DEFAULT_DB = ROOT / '知识库' / 'kb.db'
DEFAULT_VENV = HERE / '.venv' / 'Scripts' / 'python.exe'
MAIN_VENV = MAIN_ROOT / '工具箱' / '检索' / '.venv' / 'Scripts' / 'python.exe'
DEFAULT_MODEL_DIR = ROOT / 'punch-console' / 'embed' / 'models'
MAIN_MODEL_DIR = MAIN_ROOT / 'punch-console' / 'embed' / 'models'
WORKER = HERE / '_embed_worker.py'
CHUNK = 256                                              # 一次喂给 sidecar 的题数（JSON 别撑太大）


class EmbedError(Exception):
    """语意层不可用（venv/模型/子进程）——带建法的明确报错，不静默。"""


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ══════════════════════════════════════════════════════════════════════
# 环境解析（🔴 缺什么就说缺什么 + 怎么建，绝不静默降级）
# ══════════════════════════════════════════════════════════════════════
def _one_venv(p):
    if p.is_dir():                                       # 给了 venv 根目录也认
        for cand in (p / 'Scripts' / 'python.exe', p / 'bin' / 'python'):
            if cand.is_file():
                return cand
    return p if p.is_file() else None


def resolve_venv(venv):
    """venv 里的 python。缺省顺序=**本位 → 主位**（worktree 里本位没有 .venv 就只读复用主位的）。"""
    cands = [Path(venv)] if venv else list(dict.fromkeys([DEFAULT_VENV, MAIN_VENV]))
    for p in cands:
        got = _one_venv(p)
        if got:
            return got
    raise EmbedError(
        '语意层 venv 不可用：' + ' / '.join(str(c) for c in cands) + ' 都不存在。\n'
        f'  建法（在 v2 根跑，不装进系统 python）：\n'
        f'    uv venv 工具箱\\检索\\.venv\n'
        f'    uv pip install --python 工具箱\\检索\\.venv\\Scripts\\python.exe sentence-transformers\n'
        f'  或用 --venv 指到别处的 python（主位现成的：{MAIN_VENV}）')


def resolve_model_dir(base):
    """模型权重目录解析（写法参考 punch-console/embed/embed.py：ModelScope 的 cache 会嵌好几层，
    版本间还会变，所以在根下递归找「带 config.json 且同目录有 modules.json/model.safetensors」的那层）。

    缺省顺序=**本位 → 主位**（worktree 里 punch-console/ 不在本位，权重只读复用主位那份）。"""
    cands = [Path(base)] if base else list(dict.fromkeys([DEFAULT_MODEL_DIR, MAIN_MODEL_DIR]))
    for p in cands:
        if (p / 'config.json').is_file():
            return p
        if p.is_dir():
            for cfg in sorted(p.rglob('config.json')):
                if (cfg.parent / 'modules.json').is_file() or (cfg.parent / 'model.safetensors').is_file():
                    return cfg.parent
    raise EmbedError(
        '语意层模型权重找不到：' + ' / '.join(str(c) for c in cands) +
        ' 下都没有可用的模型目录（要有 config.json + modules.json/model.safetensors）。\n'
        f'  建法：python punch-console\\embed\\embed.py --download   （走 ModelScope 拉 bge-small-zh-v1.5，'
        f'🔴 本机 HuggingFace 大文件经代理会被掐）\n'
        f'  或用 --model-dir 指到已有权重（主位现成的：{MAIN_MODEL_DIR}）')


def model_name_of(model_dir):
    """权重目录 → 模型名（存进 question_vec.model，换模型=重算的判据）。
    ModelScope 布局 …/models/AI-ModelScope--bge-small-zh-v1.5/snapshots/master ⇒ bge-small-zh-v1.5。"""
    skip = {'snapshots', 'master', 'models', 'model', '.'}
    for seg in reversed(Path(model_dir).parts):
        s = str(seg)
        if s.lower() in skip or (len(s) >= 8 and all(c in '0123456789abcdef' for c in s.lower())):
            continue
        return s.split('--')[-1]
    return Path(model_dir).name


# ══════════════════════════════════════════════════════════════════════
# 常驻 serve 客户端（工具箱/检索/embed_serve.py）
# 🔴 探活在就走它（毫秒级）；不在就回落下面的冷载 sidecar——回落路径一字不改
# ══════════════════════════════════════════════════════════════════════
SERVE_HOST = '127.0.0.1'
DEFAULT_SERVE_PORT = int(os.environ.get('EMBED_SERVE_PORT') or 4315)
# 🔴 本机装了代理：urllib 默认吃 HTTP(S)_PROXY 环境变量，连 127.0.0.1 也会被劫走
#    （等价于 curl 必须 --noproxy "*"，CLAUDE.md §5 已记）。这个 opener 显式清空代理。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# 🔴 本机实伤（2026-08-19 实测）：连**没人监听的**本地端口不是秒回 ConnectionRefused，
#    而是**一直没响应直到超时**（有东西在丢 SYN）。所以探活超时必须短——它是"serve 不在"时
#    每次调用都要白付的固定成本。0.6s：健康的本地 serve 回 /health 是毫秒级，绰绰有余；
#    serve 不在时也只比冷载多花 0.6s（冷载本身 5~6s），可以忽略。
SERVE_PROBE_TIMEOUT = 0.6


def serve_port_of(port=None):
    return int(port or DEFAULT_SERVE_PORT)


def _serve_call(port, path, payload=None, timeout=5.0):
    url = f'http://{SERVE_HOST}:{serve_port_of(port)}{path}'
    data, headers = None, {'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')   # 🔴 固定 utf-8
        headers['Content-Type'] = 'application/json; charset=utf-8'
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method='POST' if data is not None else 'GET')
    with _OPENER.open(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode('utf-8'))


def serve_health(port=None, timeout=SERVE_PROBE_TIMEOUT):
    """探活常驻 serve：活着→/health 的 dict；不在/不健康→**None**。

    🔴 只回 None 不抛：回落决定权在调用方（embed_texts），探活本身不该让整条线失败。
    """
    try:
        info = _serve_call(port, '/health', None, timeout)
    except Exception:
        return None
    return info if isinstance(info, dict) and info.get('ok') else None


def serve_embed(texts, port=None, batch=64, timeout=300):
    """走常驻 serve 算向量 → (向量表, dim, 模型名)。任何不对劲一律抛 EmbedError（调用方回落冷载）。"""
    np = _np()
    res = _serve_call(port, '/embed', {'texts': list(texts), 'batch': int(batch)}, timeout)
    if not res.get('ok'):
        raise EmbedError(f'serve 报错：{res.get("error")}')
    b64 = res.get('vecs_b64') or []
    if len(b64) != len(texts):
        raise EmbedError(f'serve 返回条数 {len(b64)} ≠ 送入 {len(texts)}——数量对不上不收')
    dim = int(res['dim'])
    vecs = []
    for s in b64:
        buf = base64.b64decode(s)
        if len(buf) != dim * 4:
            raise EmbedError(f'serve 向量 {len(buf)} 字节 ≠ dim {dim} × 4——float32 小端契约对不上')
        vecs.append(np.frombuffer(buf, dtype='<f4'))     # 解出来就是 question_vec.vec 本体
    return vecs, dim, res['model']


# ══════════════════════════════════════════════════════════════════════
# sidecar 调用
# ══════════════════════════════════════════════════════════════════════
def embed_texts(texts, venv=None, model_dir=None, batch=64, quiet=False,
                serve_port=None, use_serve=True):
    """文本表 → (向量表, dim, 模型名)。

    🔴 两条路：
      · 常驻 serve（embed_serve.py）探活在 ⇒ 走它，毫秒级；
      · 不在、或 serve 半路出错 ⇒ **回落冷载 sidecar，行为一字不变**（起 venv 里的 _embed_worker.py）。
    显式给了 --model-dir 且与 serve 载的那份不是同一个目录 ⇒ 不混用，直接走冷载（向量不许跨权重混）。
    """
    if use_serve:
        h = serve_health(serve_port)
        if h:
            skip = None
            if model_dir:                    # 显式指了权重：与 serve 载的不同就不混用
                try:
                    want = Path(str(resolve_model_dir(model_dir)))
                    if want != Path(str(h.get('model_dir') or '')):
                        skip = f'--model-dir={want} 与 serve 载的 {h.get("model_dir")} 不是同一份'
                except EmbedError:
                    skip = '--model-dir 解析不了（下面冷载会把原因说全）'
            if skip:
                if not quiet:
                    print(f'  · serve :{serve_port_of(serve_port)} 在，但跳过（{skip}）→ 走冷载',
                          flush=True)
            else:
                t0 = time.time()
                try:
                    vecs, dim, name = serve_embed(texts, serve_port, batch)
                    if not quiet:
                        print(f'  serve :{serve_port_of(serve_port)}（pid={h.get("pid")}）'
                              f'模型={name} dim={dim}；{len(texts)} 条 {time.time() - t0:.2f}s',
                              flush=True)
                    return vecs, dim, name
                except Exception as e:       # noqa: BLE001 —— serve 挂了只是变慢，不许变成查不出来
                    print(f'⚠️ 常驻 serve 算不动（{e}）——回落冷载 sidecar，不静默失败',
                          file=sys.stderr, flush=True)
    py = resolve_venv(venv)
    mdir = resolve_model_dir(model_dir)
    name = model_name_of(mdir)
    if not WORKER.is_file():
        raise EmbedError(f'sidecar 脚本缺失：{WORKER}')
    payload = json.dumps({'model_dir': str(mdir), 'texts': list(texts), 'batch': batch},
                         ensure_ascii=False)
    if not quiet:
        print(f'  sidecar：{py}\n  模型：{name} ← {mdir}\n  待算 {len(texts)} 条…', flush=True)
    t0 = time.time()
    try:
        proc = subprocess.run([str(py), str(WORKER)], input=payload, capture_output=True,
                              text=True, encoding='utf-8', errors='replace')
    except OSError as e:
        raise EmbedError(f'sidecar 起不来：{e}（venv python={py}）')
    if not proc.stdout.strip():
        raise EmbedError(f'sidecar 无输出（退出码 {proc.returncode}）。stderr 末段：\n'
                         + '\n'.join(proc.stderr.strip().splitlines()[-8:]))
    try:
        res = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        raise EmbedError(f'sidecar 输出不是 JSON（{e}）：{proc.stdout[:300]}')
    if not res.get('ok'):
        raise EmbedError(f'sidecar 报错：{res.get("error")}\n  （模型目录={mdir}；'
                         f'依赖装法 uv pip install --python {py} sentence-transformers）')
    if res.get('count') != len(texts):
        raise EmbedError(f'sidecar 返回条数 {res.get("count")} ≠ 送入 {len(texts)}——数量对不上不收')
    if not quiet:
        print(f'  算完 {res["count"]} 条 dim={res["dim"]}，{time.time() - t0:.1f}s', flush=True)
    return res['vecs'], int(res['dim']), name


# ══════════════════════════════════════════════════════════════════════
# question_vec 读写
# ══════════════════════════════════════════════════════════════════════
def _np():
    try:
        import numpy as np
        return np
    except ImportError:
        raise EmbedError('系统 python 缺 numpy（余弦全扫要它）：pip install numpy')


def save_vecs(conn, pairs, model, dim):
    """pairs=[(qid, [float,…])] → question_vec 落 float32 小端 BLOB（同 id 覆盖=换模型重算）。"""
    np = _np()
    ts = now()
    rows = []
    for qid, vec in pairs:
        arr = np.asarray(vec, dtype='<f4')
        if arr.shape[0] != dim:
            raise EmbedError(f'{qid} 向量维度 {arr.shape[0]} ≠ {dim}——维度不齐不入库')
        rows.append((qid, model, dim, memoryview(arr.tobytes()), ts))
    conn.executemany(
        'INSERT INTO question_vec(question_id,model,dim,vec,updated_at) VALUES (?,?,?,?,?) '
        'ON CONFLICT(question_id) DO UPDATE SET model=excluded.model, dim=excluded.dim, '
        'vec=excluded.vec, updated_at=excluded.updated_at', rows)
    conn.commit()
    return len(rows)


def load_matrix(conn, model, ids=None):
    """库里该模型的全部向量 → (id 表, 矩阵)。🔴 模型名对不上的一律不参与比对。"""
    np = _np()
    sql = 'SELECT question_id, dim, vec FROM question_vec WHERE model=?'
    params = [model]
    if ids is not None:
        ids = list(ids)
        if not ids:
            return [], None
        sql += f' AND question_id IN ({",".join(["?"] * len(ids))})'
        params += ids
    qids, vecs, dim = [], [], None
    for qid, d, blob in conn.execute(sql, params):
        if dim is None:
            dim = d
        elif d != dim:
            raise EmbedError(f'库内向量维度不齐（{dim} vs {d}，题 {qid}）——同模型不该出现，先 build --force')
        qids.append(qid)
        vecs.append(np.frombuffer(blob, dtype='<f4'))
    if not qids:
        return [], None
    return qids, np.vstack(vecs)


def rank(conn, text, candidate_ids=None, topk=8, venv=None, model_dir=None, quiet=True,
         serve_port=None, use_serve=True):
    """语意排序：查询文本 → [(qid, 相似度)]（降序）。

    candidate_ids=None 全库扫；给了就只在这批候选里排（🔴 ①②层先 SQL 过滤，③层只负责排序）。
    返回 (命中表, 说明 dict)——说明里如实带「候选里有几道还没算向量」，绝不假装它们不存在。
    """
    np = _np()
    qvec, dim, model = embed_texts([text], venv, model_dir, quiet=quiet,
                                   serve_port=serve_port, use_serve=use_serve)
    qv = np.asarray(qvec[0], dtype='<f4')
    qids, mat = load_matrix(conn, model, candidate_ids)
    total_cand = len(candidate_ids) if candidate_ids is not None else \
        conn.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    info = {'model': model, 'dim': dim, 'candidates': total_cand, 'vectored': len(qids),
            'missing': total_cand - len(qids)}
    if not qids:
        return [], info
    if mat.shape[1] != qv.shape[0]:
        raise EmbedError(f'查询向量 dim={qv.shape[0]} 与库内 dim={mat.shape[1]} 不一致——'
                         f'换过模型就跑 build --force 重算')
    score = mat @ qv                                     # 已 L2 归一化 ⇒ 点积=余弦
    order = np.argsort(-score)[:max(1, int(topk))]
    return [(qids[i], float(score[i])) for i in order], info


def rank_by_qid(conn, qid, candidate_ids=None, topk=8):
    """**以题找题**：直取 question_vec 里 qid 那条向量当锚，余弦排序候选 → [(qid, 相似度)]（降序）。

    🔴 三条：
      · **不载模型、不走 serve、不起 sidecar**——锚向量库里现成的，一次 numpy 点乘就完事；
      · qid **没算过向量 = 明确报错并给出补算命令**，绝不静默改成「拿题面文本重算」或「返回空」
        （那两种都会让人以为"库里就是没有相似题"）；
      · **锚题自己不进结果**（自己跟自己恒等于 1，占个坑没意义）。
    返回 (命中表, 说明 dict)，说明里如实带「候选里有几道还没算向量」。
    """
    np = _np()
    qid = str(qid)
    row = conn.execute('SELECT model, dim, vec FROM question_vec WHERE question_id=?',
                       (qid,)).fetchone()
    if not row:
        if not conn.execute('SELECT 1 FROM question WHERE id=?', (qid,)).fetchone():
            raise EmbedError(f'--like-qid {qid}：question 表里没有这道题——以题找题的锚点不许指空')
        raise EmbedError(
            f'--like-qid {qid}：这道题还没算向量（question_vec 里没有它），以题找题没有锚。\n'
            f'  补算（只补缺的，已有的不动）：python 工具箱\\检索\\embed_tool.py build --db <本次的库>\n'
            f'  想快就先起常驻 serve：      python 工具箱\\启动台.py\n'
            f'  🔴 若它是纯图题（题面无 text 块），build 会如实跳过它——那种题只能用 --like 描述来找')
    model, dim, blob = row[0], int(row[1]), row[2]
    qv = np.frombuffer(blob, dtype='<f4')
    if qv.shape[0] != dim:
        raise EmbedError(f'{qid} 的向量 {qv.shape[0]} 维 ≠ 记的 dim={dim}——库里这条坏了，'
                         f'重算：embed_tool.py build --force')
    cand = None if candidate_ids is None else [c for c in candidate_ids if c != qid]
    qids, mat = load_matrix(conn, model, cand)
    if qids and cand is None:                            # 全库扫时手工把锚题剔出去
        keep = [i for i, q in enumerate(qids) if q != qid]
        qids = [qids[i] for i in keep]
        mat = mat[keep] if keep else None
    total_cand = len(cand) if cand is not None else \
        conn.execute('SELECT COUNT(*) FROM question WHERE id<>?', (qid,)).fetchone()[0]
    info = {'model': model, 'dim': dim, 'anchor': qid, 'candidates': total_cand,
            'vectored': len(qids), 'missing': total_cand - len(qids)}
    if not qids:
        return [], info
    if mat.shape[1] != dim:
        raise EmbedError(f'锚向量 dim={dim} 与库内 dim={mat.shape[1]} 不一致——'
                         f'同模型不该出现，先 build --force')
    score = mat @ qv                                     # 已 L2 归一化 ⇒ 点积=余弦
    order = np.argsort(-score)[:max(1, int(topk))]
    return [(qids[i], float(score[i])) for i in order], info


# ══════════════════════════════════════════════════════════════════════
# 命令
# ══════════════════════════════════════════════════════════════════════
def open_db(path):
    import sqlite3
    p = Path(path)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}（先跑 工具箱/库/init_db.py --only kb）')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def log_skill(conn, action, digest, result, detail, t0):
    try:
        conn.execute(
            'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) '
            'VALUES (?,?,?,?,?,?,?)',
            ('找题', action, str(digest)[:200], result, str(detail)[:500],
             int((time.time() - t0) * 1000), now()))
        conn.commit()
    except Exception:
        pass


def cmd_build(conn, args):
    model_name = model_name_of(resolve_model_dir(args.model_dir))
    if args.force:
        sql = 'SELECT q.id, q.blocks_json FROM question q'
        params = []
    else:
        # 缺向量 或 向量是别的模型算的（换模型=重算，不混存）
        sql = ('SELECT q.id, q.blocks_json FROM question q '
               'LEFT JOIN question_vec v ON v.question_id=q.id '
               'WHERE v.question_id IS NULL OR v.model<>?')
        params = [model_name]
    sql += ' ORDER BY q.created_at, q.id'
    if args.limit:
        sql += ' LIMIT ?'
        params = params + [int(args.limit)]
    todo = conn.execute(sql, params).fetchall()
    if not todo:
        total = conn.execute('SELECT COUNT(*) FROM question').fetchone()[0]
        have = conn.execute('SELECT COUNT(*) FROM question_vec WHERE model=?', (model_name,)).fetchone()[0]
        print(f'无需新算：{have}/{total} 题已有 {model_name} 向量（要重算加 --force）')
        return f'model={model_name}', f'skip total={total}'

    empty, texts, keys = [], [], []
    for qid, bj in todo:
        t = plain_text(bj)
        if not t:
            empty.append(qid)                            # 纯图题/坏块流：不塞空串充数
            continue
        texts.append(t)
        keys.append(qid)
    print(f'待算 {len(keys)} 题' + (f'（{len(empty)} 题无正文块跳过）' if empty else ''))
    done = 0
    for i in range(0, len(keys), CHUNK):
        chunk_ids = keys[i:i + CHUNK]
        vecs, dim, model = embed_texts(texts[i:i + CHUNK], args.venv, args.model_dir, args.batch,
                                       serve_port=args.serve_port, use_serve=not args.no_serve)
        done += save_vecs(conn, list(zip(chunk_ids, vecs)), model, dim)
        print(f'  入库 {done}/{len(keys)}')
    total = conn.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    have = conn.execute('SELECT COUNT(*) FROM question_vec WHERE model=?', (model_name,)).fetchone()[0]
    print(f'build 完成：新算 {done} 题；库内 {model_name} 向量 {have}/{total} 题')
    if empty:
        print(f'⚠️ 无正文块（纯图题？）跳过 {len(empty)} 题：{empty[:10]}'
              f'{"…" if len(empty) > 10 else ""}——如实列出，不静默补空向量')
    return f'model={model_name} force={args.force}', f'new={done} have={have}/{total} empty={len(empty)}'


def cmd_query(conn, args):
    hits, info = rank(conn, args.text, None, args.topk, args.venv, args.model_dir, quiet=False,
                      serve_port=args.serve_port, use_serve=not args.no_serve)
    print(f'语意查询「{args.text}」 模型={info["model"]} dim={info["dim"]} '
          f'候选 {info["candidates"]} 题（已算向量 {info["vectored"]}，缺 {info["missing"]}）')
    if info['missing']:
        print(f'⚠️ 有 {info["missing"]} 题还没算向量，它们不可能被排进来——补：embed_tool.py build')
    if not hits:
        print('（一条都没有：先跑 build）')
        return f'text={args.text[:40]}', 'hits=0'
    for qid, sc in hits:
        row = conn.execute('SELECT blocks_json, status FROM question WHERE id=?', (qid,)).fetchone()
        print(f'  {sc:.4f}  {qid}\t{row[1] if row else "?"}\t'
              f'{first_text(row[0]) if row else "(题已不在库)"}')
    return f'text={args.text[:40]} topk={args.topk}', f'hits={len(hits)} top={hits[0][1]:.4f}'


def cmd_stat(conn, args):
    total = conn.execute('SELECT COUNT(*) FROM question').fetchone()[0]
    rows = conn.execute('SELECT model, dim, COUNT(*), MAX(updated_at) FROM question_vec '
                        'GROUP BY model, dim ORDER BY 3 DESC').fetchall()
    print(f'question {total} 题；question_vec 分模型：')
    for m, d, n, up in rows:
        print(f'  {m}\tdim={d}\t{n} 题\t最近 {up}')
    if not rows:
        print('  （空——先跑 build）')
    try:
        cur = model_name_of(resolve_model_dir(args.model_dir))
        have = conn.execute('SELECT COUNT(*) FROM question_vec WHERE model=?', (cur,)).fetchone()[0]
        print(f'当前模型 {cur} 覆盖率 {have}/{total}' + ('' if have == total else '（差的跑 build 补）'))
    except EmbedError as e:
        print(f'⚠️ 当前模型解析不了：{str(e).splitlines()[0]}')
    port = serve_port_of(args.serve_port)
    h = serve_health(args.serve_port)
    if h:
        print(f'常驻 serve :{port} **在**（pid={h.get("pid")} 模型={h.get("model")} dim={h.get("dim")} '
              f'已服务 {h.get("served")} 次/{h.get("texts")} 条 起了 {h.get("uptime_s")}s）→ 算向量走它')
    else:
        print(f'常驻 serve :{port} **不在** → 算向量回落冷载 sidecar（每次多花 5~6s 载模型）；'
              f'起：python 工具箱\\启动台.py')
    return 'stat', f'total={total} models={len(rows)} serve={"在" if h else "不在"}'


def common_args():
    """公共参数：子命令前后都能写（default=SUPPRESS 保证子解析器不把主解析器的值冲成 None）。"""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--db', default=argparse.SUPPRESS, help=f'库（缺省 {DEFAULT_DB}）')
    p.add_argument('--venv', default=argparse.SUPPRESS,
                   help=f'venv 里的 python（缺省 本位→主位：{MAIN_VENV}）')
    p.add_argument('--model-dir', dest='model_dir', default=argparse.SUPPRESS,
                   help=f'模型权重根（缺省 本位→主位：{MAIN_MODEL_DIR}）')
    p.add_argument('--serve-port', dest='serve_port', type=int, default=argparse.SUPPRESS,
                   help=f'常驻 serve 端口（缺省 {DEFAULT_SERVE_PORT}／环境变量 EMBED_SERVE_PORT）')
    p.add_argument('--no-serve', dest='no_serve', action='store_const', const=True,
                   default=argparse.SUPPRESS, help='🔴 不探活 serve，强制走冷载 sidecar（对拍用）')
    return p


def main():
    common = common_args()
    ap = argparse.ArgumentParser(description='question_vec 语意向量层（本地 bge sidecar，零外部 API）',
                                 parents=[common])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('build', parents=[common])
    s.add_argument('--force', action='store_true', help='已有向量也重算')
    s.add_argument('--limit', type=int, help='本次最多算几题（分批跑用）')
    s.add_argument('--batch', type=int, default=64)
    s = sub.add_parser('query', parents=[common])
    s.add_argument('--text', required=True)
    s.add_argument('--topk', type=int, default=8)
    sub.add_parser('stat', parents=[common])
    args = ap.parse_args()
    args.db = getattr(args, 'db', None) or str(DEFAULT_DB)
    args.venv = getattr(args, 'venv', None)
    args.model_dir = getattr(args, 'model_dir', None)
    args.serve_port = getattr(args, 'serve_port', None)
    args.no_serve = bool(getattr(args, 'no_serve', False))

    t0 = time.time()
    conn = open_db(args.db)
    try:
        fn = {'build': cmd_build, 'query': cmd_query, 'stat': cmd_stat}[args.cmd]
        digest, detail = fn(conn, args)
        log_skill(conn, f'embed-{args.cmd}', digest, '成功', detail, t0)
    except EmbedError as e:
        print(f'🔴 {e}', file=sys.stderr)
        log_skill(conn, f'embed-{args.cmd}', str(vars(args))[:200], '失败', str(e), t0)
        conn.close()
        sys.exit(1)
    conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
