# -*- coding: utf-8 -*-
"""语意层 sidecar 本体（D-20 第③层）——**只在 venv 里跑**，主脚本从不 import 它。

契约（stdin 一份 JSON 进，stdout 一份 JSON 出）：
    进：{"model_dir": "<已解析好的模型目录>", "texts": ["…", …], "batch": 64}
    出：{"ok": true, "dim": 512, "count": N, "vecs": [[…], …]}
        {"ok": false, "error": "原话"}

为什么要 sidecar：torch + sentence_transformers 只装在 工具箱/检索/.venv 里，
主线工具（query_core / find_questions / paper_tool）跑在系统 python，两边不共命运——
模型环境炸了也只炸这一个子进程，主线照常做 ①② 层确定性查询。

🔴 三条：
  · 向量 **L2 归一化**（normalize_embeddings=True）⇒ 余弦相似度 = 点积，主脚本一次 numpy 点乘搞定；
  · stdout 只许出那一份 JSON —— 载模型时第三方库往 stdout 打的进度条会毁掉协议，
    故全程把 sys.stdout 顶成 stderr，最后才往真 stdout 写结果；
  · 模型目录**由主脚本解析好传进来**（找 config.json 不需要 ML 依赖），worker 不自己猜、更不联网下载。

🔴 实伤记录（2026-08-19 本卡踩中）：stdin 必须**按字节读再显式 utf-8 解**。
   本机 python 的 sys.stdin 默认走 GBK，`你好世界` 会被解成 `浣犲ソ涓栫晫` 还带上代理对（\\udcxx），
   传进 tokenizers 的 Rust 侧直接抛
   `TypeError: TextEncodeInput must be Union[TextInputSequence, …]`——
   报错原文一个字都不提编码，只看它能查一天。CLAUDE.md 的「py 头双 reconfigure」在这里要补第三条：stdin。
"""
import json
import sys
import traceback

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


def main():
    real_stdout = sys.stdout
    sys.stdout = sys.stderr          # 🔴 协议保护：任何第三方 print 都不许污染结果通道
    try:
        raw = sys.stdin.buffer.read()            # 🔴 按字节读再显式 utf-8 解（见文件头实伤记录）
        req = json.loads(raw.decode('utf-8') or '{}')
        bad = [i for i, t in enumerate(req.get('texts') or [])
               if not isinstance(t, str) or any('\ud800' <= c <= '\udfff' for c in t)]
        if bad:                                   # 代理对=上游编码已经坏了，早报早收工
            raise ValueError(f'texts[{bad[:5]}] 不是干净字符串（含代理对/非 str）——上游编码坏了，别喂进 tokenizer')
        model_dir = req.get('model_dir')
        texts = req.get('texts') or []
        batch = int(req.get('batch') or 64)
        if not model_dir:
            raise ValueError('缺 model_dir（主脚本负责解析模型目录）')
        if not texts:
            raise ValueError('texts 为空——没文本可算')

        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer(str(model_dir), device='cpu')
        vec = model.encode(texts, batch_size=batch, normalize_embeddings=True,
                           show_progress_bar=False, convert_to_numpy=True)
        vec = np.asarray(vec, dtype='float32')
        out = {'ok': True, 'dim': int(vec.shape[1]), 'count': int(vec.shape[0]),
               'vecs': [[float(x) for x in row] for row in vec]}
    except Exception as e:                       # noqa: BLE001 —— 失败也要给主脚本可解析的信号
        # 🔴 带上 traceback 末三帧：sidecar 是子进程，不给栈就只能靠猜（实伤过一次）
        tb = [x.strip() for x in traceback.format_exc().strip().splitlines()[-6:]]
        out = {'ok': False, 'error': f'{type(e).__name__}: {e}', 'trace': tb}
    print(json.dumps(out, ensure_ascii=False), file=real_stdout)
    real_stdout.flush()
    return 0 if out.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
