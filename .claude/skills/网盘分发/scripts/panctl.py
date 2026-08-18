# -*- coding: utf-8 -*-
"""panctl —— 百度网盘分发工具（ai-bkb「网盘分发」skill 的执行底座）。

设计口径（2026-07-30 实测定版）：
  * 写/读盘一律走**官方 API**（合规、稳）。官方应用只能写 `/apps/<应用名>/`，
    但其下可任意建嵌套目录，足够镜像整个 SKU 树。
  * 只有**建分享链接**官方接口被资质卡（errno=2 / MCP errno=13998 invalid app），
    退到 cookie 网页版通路；cookie 快照约 15 分钟就被百度轮换失效，
    故 share 前必须"现导现用"（见 SKILL.md §4）。

子命令：
  auth status                     查 access_token 有效期 + cookie 新鲜度
  auth code <code>                首次授权：用授权码换 token 并回填 env
  auth refresh                    用 refresh_token 续期 access_token
  ls <网盘路径>                    列目录（可读全盘，非只限 /apps/）
  tree <网盘路径>                  递归列出（含 fs_id）
  upload <本地路径> [网盘子路径]    上传文件/目录（分片+秒传+幂等覆盖）
  share <网盘路径...>              建分享链接（cookie 通路）
  deliver <本地路径> [网盘子路径]   全流程：上传 → 建分享 → 出对照表
"""
import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ENV_PATH = r"d:\workplace\ai-bkb-v2\password\baidu-pan.env"
COOKIE_PATH = r"d:\workplace\ai-bkb-v2\password\baidu-pan-cookies.json"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 绕本机代理直连
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
CHUNK = 4 * 1024 * 1024          # 普通用户 4MB/片（会员 16/32MB）
SHARE_DAILY_CAP = 300            # 百度硬限：单账号每日分享链接上限


# ---------------------------------------------------------------- env / 凭据

def load_env():
    env = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, rest = line.split("=", 1)
            env[k.strip()] = re.split(r"\s+#", rest, 1)[0].strip()
    return env


def save_env(fields):
    with open(ENV_PATH, encoding="utf-8") as f:
        text = f.read()
    for k, v in fields.items():
        text = re.sub(rf"(?m)^{k}=.*$", f"{k}={v}", text)
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(text)


def app_root(env):
    return "/apps/" + env["BAIDU_PAN_APP_NAME"]


def netpath(env, sub):
    """把相对子路径解析成网盘绝对路径；已是 /apps/ 或 / 开头的绝对路径原样返回。"""
    sub = (sub or "").replace("\\", "/").strip("/")
    if not sub:
        return app_root(env)
    if sub.startswith("apps/"):
        return "/" + sub
    return app_root(env) + "/" + sub


# ---------------------------------------------------------------- HTTP 基元

def _open(req, timeout):
    last = None
    for attempt in range(3):
        try:
            with OPENER.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            try:
                return json.loads(body)
            except Exception:
                last = RuntimeError(f"HTTP {e.code}: {body}")
        except Exception as e:                       # 网络抖动重试
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last


def api(url, params, data=None, timeout=60):
    """官方 REST API 调用（access_token 走 query）。"""
    full = url + "?" + urllib.parse.urlencode(params)
    body = urllib.parse.urlencode(data).encode() if data else None
    headers = {"User-Agent": UA}
    if body:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    return _open(urllib.request.Request(full, data=body, headers=headers,
                                        method="POST" if body else "GET"), timeout)


def cookie_headers():
    if not os.path.exists(COOKIE_PATH):
        die("缺 cookie 文件：%s\n  → 让 agent 用 playwright 打开 pan.baidu.com 确认登录后导出 storageState（见 SKILL.md §4）"
            % COOKIE_PATH)
    with open(COOKIE_PATH, encoding="utf-8") as f:
        state = json.load(f)
    jar = {}
    for c in state.get("cookies", []):
        if "baidu.com" in (c.get("domain") or "") and c.get("name"):
            jar.setdefault(c["name"], c["value"])
    return {
        "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items()),
        "User-Agent": UA,
        "Referer": "https://pan.baidu.com/disk/main",
        "Origin": "https://pan.baidu.com",
    }, len(jar)


def web(url, data=None, timeout=60):
    """cookie 网页版通路调用。"""
    h, _ = cookie_headers()
    body = urllib.parse.urlencode(data).encode() if data else None
    if body:
        h["Content-Type"] = "application/x-www-form-urlencoded"
    return _open(urllib.request.Request(url, data=body, headers=h,
                                        method="POST" if body else "GET"), timeout)


def bdstoken():
    """取写操作要的 CSRF 令牌（动态取，绝不存盘——存了必过期）。"""
    r = web("https://pan.baidu.com/api/gettemplatevariable?fields="
            + urllib.parse.quote('["bdstoken","uk","username"]'))
    res = r.get("result")
    tok = res.get("bdstoken") if isinstance(res, dict) else None
    if not tok:
        die("cookie 登录态已失效（errno=%s）。百度约 15 分钟轮换会话 cookie。\n"
            "  → 让 agent 用 playwright 重新导出 storageState 后立即重试（见 SKILL.md §4）"
            % r.get("errno"))
    return tok, res.get("username"), res.get("uk")


def die(msg):
    print("FAIL " + msg)
    sys.exit(1)


def human_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.1f}{u}" if u != "B" else f"{n}B"
        n /= 1024.0


# ---------------------------------------------------------------- auth

def cmd_auth(env, args):
    if args.action == "status":
        print("应用:", env.get("BAIDU_PAN_APP_NAME"), "| AppID:", env.get("BAIDU_PAN_APP_ID"))
        exp = env.get("BAIDU_PAN_TOKEN_EXPIRES_AT") or "(未授权)"
        print("access_token 到期:", exp)
        if env.get("BAIDU_PAN_ACCESS_TOKEN"):
            r = api("https://pan.baidu.com/rest/2.0/xpan/nas",
                    {"method": "uinfo", "access_token": env["BAIDU_PAN_ACCESS_TOKEN"]})
            ok = r.get("errno") == 0
            print("官方 API:", "OK" if ok else f"FAIL errno={r.get('errno')}",
                  "| 账号:", r.get("baidu_name"), "| vip_type:", r.get("vip_type"),
                  f"(分片 {CHUNK // 1024 // 1024}MB)")
        # 🔴 主通路 = 持久化浏览器（登录态在固定 profile，不会像快照那样 15 分钟过期）
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from panbrowser import PROFILE_DIR, PanBrowser
            if not os.path.isdir(PROFILE_DIR):
                print("持久浏览器: 未初始化 → panbrowser.py login 扫一次码")
            else:
                with PanBrowser(headless=True) as b:
                    _tok, u, uk = b.whoami()
                print(f"持久浏览器: {'🟢 登录态有效（%s / uk=%s）' % (u, uk) if _tok else '🔴 已失效 → panbrowser.py login'}")
        except Exception as e:
            print(f"持久浏览器: 探测失败（{e}）")
        # 退路通路（只在浏览器不可用时用；必然 15 分钟过期）
        if os.path.exists(COOKIE_PATH):
            age = (time.time() - os.path.getmtime(COOKIE_PATH)) / 60
            _, n = cookie_headers()
            print(f"cookie 快照(退路): {n} 条, 导出于 {age:.0f} 分钟前",
                  "→ 新鲜" if age < 10 else "→ 已失效(正常,主通路不依赖它)")
        else:
            print("cookie 快照(退路): 缺失（不影响主通路）")
        return

    if args.action == "code":
        r = api("https://openapi.baidu.com/oauth/2.0/token", {
            "grant_type": "authorization_code", "code": args.value,
            "client_id": env["BAIDU_PAN_APP_KEY"],
            "client_secret": env["BAIDU_PAN_SECRET_KEY"], "redirect_uri": "oob"})
    else:  # refresh
        r = api("https://openapi.baidu.com/oauth/2.0/token", {
            "grant_type": "refresh_token",
            "refresh_token": env["BAIDU_PAN_REFRESH_TOKEN"],
            "client_id": env["BAIDU_PAN_APP_KEY"],
            "client_secret": env["BAIDU_PAN_SECRET_KEY"]})
    if "access_token" not in r:
        die("换 token 失败: " + json.dumps(r, ensure_ascii=False)[:300])
    exp = time.strftime("%Y-%m-%d %H:%M:%S",
                        time.localtime(time.time() + int(r["expires_in"])))
    save_env({"BAIDU_PAN_ACCESS_TOKEN": r["access_token"],
              "BAIDU_PAN_REFRESH_TOKEN": r["refresh_token"],
              "BAIDU_PAN_TOKEN_EXPIRES_AT": exp})
    print("PASS token 已回填 env，到期:", exp)


# ---------------------------------------------------------------- 读盘

def list_dir(env, d):
    out, start = [], 0
    while True:
        r = api("https://pan.baidu.com/rest/2.0/xpan/file",
                {"method": "list", "access_token": env["BAIDU_PAN_ACCESS_TOKEN"],
                 "dir": d, "start": start, "limit": 1000, "order": "name"})
        if r.get("errno") != 0:
            die(f"列目录 {d} 失败: " + json.dumps(r, ensure_ascii=False)[:200])
        out += r.get("list", [])
        if len(r.get("list", [])) < 1000:
            return out
        start += 1000


def cmd_ls(env, args):
    for i in list_dir(env, netpath(env, args.path) if not args.path.startswith("/") else args.path):
        mark = "[目录]" if i["isdir"] else "      "
        size = "" if i["isdir"] else "  " + human_size(i["size"])
        print(f"{mark} {i['server_filename']}{size}  fs_id={i['fs_id']}")


def walk(env, d, depth=0, counter=None):
    """递归遍历（官方 listall 对第三方应用会 errno 20011，必须手动 walk）。"""
    counter = counter if counter is not None else [0]
    for i in list_dir(env, d):
        counter[0] += 1
        pad = "  " * depth
        if i["isdir"]:
            print(f"{pad}[目录] {i['server_filename']}/")
            walk(env, i["path"], depth + 1, counter)
        else:
            print(f"{pad}       {i['server_filename']}  {human_size(i['size'])}  fs_id={i['fs_id']}")
    return counter[0]


def cmd_tree(env, args):
    d = netpath(env, args.path) if not args.path.startswith("/") else args.path
    print("共 %d 项" % walk(env, d))


# ---------------------------------------------------------------- 上传

def chunk_md5s(path):
    md5s, size = [], os.path.getsize(path)
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            md5s.append(hashlib.md5(b).hexdigest())
    return md5s, size


def upload_one(env, local, remote):
    """官方三步链上传单文件；rtype=3 覆盖同名 → 幂等。返回 (状态, fs_id)。"""
    token = env["BAIDU_PAN_ACCESS_TOKEN"]
    md5s, size = chunk_md5s(local)
    if size == 0:
        return "跳过(空文件)", None
    block_list = json.dumps(md5s)

    r1 = api("https://pan.baidu.com/rest/2.0/xpan/file",
             {"method": "precreate", "access_token": token},
             {"path": remote, "size": size, "isdir": 0, "autoinit": 1,
              "rtype": 3, "block_list": block_list})
    if r1.get("errno") != 0:
        return "FAIL precreate errno=%s" % r1.get("errno"), None
    if r1.get("return_type") == 2:                 # 秒传：服务端已有同 md5
        return "秒传", (r1.get("info") or {}).get("fs_id")

    uploadid = r1["uploadid"]
    need = r1.get("block_list")
    need = list(range(len(md5s))) if need is None else need
    with open(local, "rb") as f:
        for seq in need:
            f.seek(seq * CHUNK)
            data = f.read(CHUNK)
            boundary = uuid.uuid4().hex
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                    f"filename=\"blob\"\r\nContent-Type: application/octet-stream\r\n\r\n"
                    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
            url = "https://d.pcs.baidu.com/rest/2.0/pcs/superfile2?" + urllib.parse.urlencode(
                {"method": "upload", "access_token": token, "type": "tmpfile",
                 "path": remote, "uploadid": uploadid, "partseq": seq})
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": UA})
            r2 = _open(req, 300)
            if not r2.get("md5"):
                return "FAIL 分片%d: %s" % (seq, json.dumps(r2, ensure_ascii=False)[:120]), None

    r3 = api("https://pan.baidu.com/rest/2.0/xpan/file",
             {"method": "create", "access_token": token},
             {"path": remote, "size": size, "isdir": 0, "rtype": 3,
              "uploadid": uploadid, "block_list": block_list})
    if r3.get("errno") != 0:
        return "FAIL create errno=%s" % r3.get("errno"), None
    return "上传(%d片)" % len(md5s), r3.get("fs_id")


def collect(local):
    """返回 [(本地绝对路径, 相对目标的子路径)]。"""
    local = os.path.abspath(local)
    if os.path.isfile(local):
        return [(local, os.path.basename(local))]
    out = []
    for root, _dirs, files in os.walk(local):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            out.append((p, os.path.relpath(p, local).replace("\\", "/")))
    return sorted(out, key=lambda x: x[1])


def remote_index(env, base):
    """递归取目标目录下已有文件 {相对路径: (size, fs_id)}；目录不存在返回空。"""
    idx = {}

    def rec(d, prefix):
        try:
            entries = list_dir(env, d)
        except SystemExit:
            return                                  # 目录还不存在，正常
        for i in entries:
            rel = (prefix + "/" + i["server_filename"]).lstrip("/")
            if i["isdir"]:
                rec(i["path"], rel)
            else:
                idx[rel] = (i["size"], i["fs_id"])

    rec(base, "")
    return idx


def do_upload(env, local, sub, only_ext=None, force=False):
    base = netpath(env, sub)
    items = collect(local)
    if only_ext:
        exts = tuple("." + e.lower().lstrip(".") for e in only_ext)
        items = [i for i in items if i[1].lower().endswith(exts)]
    if not items:
        die("没有要上传的文件：%s" % local)
    # 🔴 幂等：官方 precreate 不带 content-md5 不触发秒传，靠远端清单跳过同名同大小
    idx = {} if force else remote_index(env, base)
    print(f"目标: {base}   文件数: {len(items)}"
          + (f"   远端已有 {len(idx)} 个" if idx else ""))
    results = []
    for i, (p, rel) in enumerate(items, 1):
        remote = base + "/" + rel
        size = os.path.getsize(p)
        hit = idx.get(rel)
        if hit and hit[0] == size:
            status, fs_id = "跳过(已存在同大小)", hit[1]
        else:
            status, fs_id = upload_one(env, p, remote)
        flag = "FAIL" if status.startswith("FAIL") else "ok"
        print(f"  [{i}/{len(items)}] {flag} {rel}  {human_size(size)}  {status}")
        results.append({"local": p, "rel": rel, "remote": remote,
                        "fs_id": fs_id, "status": status})
    bad = [r for r in results if r["status"].startswith("FAIL")]
    print("PASS 全部成功" if not bad else f"🔴 {len(bad)} 个失败")
    return results


def cmd_upload(env, args):
    do_upload(env, args.local, args.sub, args.ext, args.force)


# ---------------------------------------------------------------- 分享

def resolve_fsid(env, path):
    """网盘路径 → fs_id（分享接口只吃 fs_id）。"""
    d, name = path.rsplit("/", 1)
    for i in list_dir(env, d):
        if i["server_filename"] == name:
            return i["fs_id"]
    return None


def gen_pwd():
    return "".join(random.choice("abcdefghijkmnpqrstuvwxyz23456789") for _ in range(4))


def share_one_via(webfn, tok, fs_ids, pwd, period):
    """建一个分享；webfn = 发请求的通路（浏览器页面内 fetch 或 cookie 快照）。"""
    url = "https://pan.baidu.com/share/set?" + urllib.parse.urlencode(
        {"channel": "chunlei", "clienttype": 0, "web": 1, "bdstoken": tok})
    r = webfn(url, {"fid_list": json.dumps([int(x) for x in fs_ids]),
                    "schannel": 4,              # 4 = 带提取码的私密分享
                    "channel_list": "[]",
                    "period": str(period),      # 天数；0 = 永久
                    "pwd": pwd})
    if r.get("errno") != 0:
        return None, "errno=%s %s" % (r.get("errno"), r.get("show_msg", ""))
    link = r.get("link") or r.get("shorturl") or ""
    # 🔴 链接必须自带 ?pwd=：不带的话对方打开还要手动敲提取码，多一步就多一批人流失。
    #    百度识别 ?pwd= 参数自动填充并跳转（2026-07-31 用户点名要求）。
    if link and pwd and "pwd=" not in link:
        link = link + ("&" if "?" in link else "?") + "pwd=" + pwd
    return {"link": link, "pwd": pwd,
            "shareid": r.get("shareid"), "period": period}, None


def _share_loop(env, targets, pwd, period, delay, webfn, tok):
    out = []
    for i, t in enumerate(targets, 1):
        fs_id = t.get("fs_id") or resolve_fsid(env, t["remote"])
        if not fs_id:
            print(f"  [{i}/{len(targets)}] FAIL 找不到 {t['remote']}")
            out.append({**t, "error": "文件不存在"})
            continue
        p = pwd or gen_pwd()
        res, err = share_one_via(webfn, tok, [fs_id], p, period)
        if err:
            print(f"  [{i}/{len(targets)}] FAIL {t.get('rel') or t['remote']}: {err}")
            out.append({**t, "error": err})
        else:
            print(f"  [{i}/{len(targets)}] ok {t.get('rel') or t['remote']}  {res['link']}  码 {p}")
            out.append({**t, **res})
        if i < len(targets):                  # 🔴 人类化节奏，别撞风控
            time.sleep(delay + random.uniform(0, delay))
    return out


def do_share(env, targets, pwd, period, delay):
    """targets = [{'rel':展示名, 'fs_id':.., 'remote':..}]；返回带 share 结果的列表。

    🔴 主通路 = **持久化浏览器**（panbrowser.py）：登录态在固定 profile 里，请求在已登录
    页面内 fetch，浏览器自带当前有效 cookie 并跟着百度轮换 → 不存在「快照过期」。
    退路 = 老的 cookie 快照通路（浏览器不可用时；15 分钟必过期，只能救急）。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from panbrowser import PanBrowser
    except Exception as e:
        print(f"[通路] 浏览器模块不可用（{e}）→ 退到 cookie 快照通路")
        tok, user, _uk = bdstoken()
        print(f"cookie 登录态 OK（{user}）；本次建 {len(targets)} 个分享链接"
              f"（百度硬限 {SHARE_DAILY_CAP}/天）")
        return _share_loop(env, targets, pwd, period, delay, web, tok)

    with PanBrowser(headless=True) as b:
        tok, user, _uk = b.whoami()
        if not tok:
            die("持久 profile 未登录（或登录态已失效）。\n"
                "  → python .claude/skills/网盘分发/scripts/panbrowser.py login 扫一次码，\n"
                "    之后长期有效，不必每次重导 cookie。")
        print(f"[通路] 持久化浏览器；登录态 OK（{user}）；本次建 {len(targets)} 个分享链接"
              f"（百度硬限 {SHARE_DAILY_CAP}/天）")
        return _share_loop(env, targets, pwd, period, delay, b.web, tok)


def cmd_share(env, args):
    targets = []
    for p in args.paths:
        remote = p if p.startswith("/") else netpath(env, p)
        targets.append({"rel": remote.rsplit("/", 1)[-1], "remote": remote})
    rows = do_share(env, targets, args.pwd, args.period, args.delay)
    write_report(rows, args.report)


# ---------------------------------------------------------------- 对照表

REPORT_ROOT = r"d:\workplace\ai-bkb-v2\记录\网盘分发"


def write_report(rows, path):
    if not path:                                    # 产物落位纪律：统一根，不散落
        path = os.path.join(REPORT_ROOT,
                            "对照表-" + time.strftime("%Y%m%d-%H%M") + ".md")
    ok = [r for r in rows if r.get("link")]
    lines = ["# 网盘分发对照表", "",
             "生成时间：" + time.strftime("%Y-%m-%d %H:%M:%S"),
             f"成功 {len(ok)} / 共 {len(rows)}", "",
             "| 文件 | 链接 | 提取码 | 有效期 |", "|---|---|---|---|"]
    for r in rows:
        if r.get("link"):
            per = "永久" if str(r.get("period")) == "0" else f"{r.get('period')}天"
            lines.append(f"| {r.get('rel') or r['remote']} | {r['link']} | `{r['pwd']}` | {per} |")
        else:
            lines.append(f"| {r.get('rel') or r.get('remote')} | ❌ {r.get('error', '失败')} | - | - |")
    text = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    # 🔴 utf-8-sig：Windows 记事本/Excel/PowerShell Get-Content 才不乱码
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(text)
    print("对照表已写入:", path)
    print()
    for r in rows:
        if r.get("link"):
            print(f"  {r.get('rel') or r['remote']}\n    {r['link']}  提取码 {r['pwd']}")


# ---------------------------------------------------------------- deliver 全流程

def cmd_deliver(env, args):
    print("=== ① 上传 ===")
    ups = do_upload(env, args.local, args.sub, args.ext, args.force)
    good = [u for u in ups if not u["status"].startswith("FAIL")]
    if not good:
        die("上传全失败，不继续建分享")
    print()
    print("=== ② 建分享链接 ===")
    rows = do_share(env, good, args.pwd, args.period, args.delay)
    print()
    print("=== ③ 对照表 ===")
    write_report(rows, args.report)


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(prog="panctl", description="百度网盘分发工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("auth", help="凭据管理")
    a.add_argument("action", choices=["status", "code", "refresh"])
    a.add_argument("value", nargs="?", help="action=code 时传授权码")

    for name, helptext in (("ls", "列目录"), ("tree", "递归列目录")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("path", nargs="?", default="", help="网盘路径（相对=应用目录下；/开头=绝对）")

    p = sub.add_parser("upload", help="上传文件/目录")
    p.add_argument("local")
    p.add_argument("sub", nargs="?", default="", help="网盘子路径（应用目录下）")
    p.add_argument("--ext", nargs="*", help="只传这些扩展名，如 --ext pdf")
    p.add_argument("--force", action="store_true", help="不跳过远端已存在的同名同大小文件")

    p = sub.add_parser("share", help="建分享链接")
    p.add_argument("paths", nargs="+")
    p.add_argument("--pwd", help="固定提取码（默认每个文件随机4位）")
    p.add_argument("--period", default="7", help="有效期天数，0=永久（默认7）")
    p.add_argument("--delay", type=float, default=3.0, help="每次间隔基准秒（默认3，会加随机抖动）")
    p.add_argument("--report", help="对照表输出路径（.md）")

    p = sub.add_parser("deliver", help="全流程：上传→分享→对照表")
    p.add_argument("local")
    p.add_argument("sub", nargs="?", default="")
    p.add_argument("--ext", nargs="*")
    p.add_argument("--force", action="store_true")
    p.add_argument("--pwd")
    p.add_argument("--period", default="7")
    p.add_argument("--delay", type=float, default=3.0)
    p.add_argument("--report")

    args = ap.parse_args()
    env = load_env()
    if args.cmd != "auth" and not env.get("BAIDU_PAN_ACCESS_TOKEN"):
        die("env 里没有 access_token，先跑 `panctl auth code <授权码>`")
    {"auth": cmd_auth, "ls": cmd_ls, "tree": cmd_tree,
     "upload": cmd_upload, "share": cmd_share, "deliver": cmd_deliver}[args.cmd](env, args)


if __name__ == "__main__":
    main()
