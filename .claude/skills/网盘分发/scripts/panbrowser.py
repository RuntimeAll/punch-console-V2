# -*- coding: utf-8 -*-
"""百度网盘 · 持久化浏览器通路（cookie 快照通路的替代品）

🔴 为什么要它：百度约 15 分钟轮换会话 cookie，**任何存盘的 cookie 快照都必然过期**——
   这是快照这个做法本身的死穴，不是「导出得不够勤」。而 MCP 的 playwright 用的是
   Temp 下的一次性 profile（playwright_chromiumdev_profile-XXXX，退出即弃），
   所以连登录态都留不住，每次都要重新扫码。

解法两条腿：
  ① **持久 profile**：浏览器数据目录固定在 password/baidu-pan-profile/，
     长效凭据（BDUSS）留在磁盘上 → 扫一次码管很久，重启电脑也还在。
  ② **页面内发请求**：不导出 cookie，直接在已登录的 pan.baidu.com 页面里 fetch，
     浏览器自己带当前有效 cookie、自己跟着百度轮换 → **过期窗口消失**。
     bdstoken（CSRF 令牌）也在页面里现取，绝不存盘。

用法（一般由 panctl.py 调用，也可直接跑）：
    python panbrowser.py login     # 打开浏览器扫码，登录态落进持久 profile
    python panbrowser.py status    # 查登录态（headless，不打扰）
"""
import json
import os
import sys
import urllib.parse

PROFILE_DIR = r"d:\workplace\ai-bkb-v2\password\baidu-pan-profile"
HOME = "https://pan.baidu.com/disk/main"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class PanBrowser:
    """持久 profile 浏览器会话；with 语句用，退出自动关。

    headless=True 适合已登录后的日常调用（不打扰用户）；
    登录/排查时用 headless=False 看得见。
    """

    def __init__(self, headless=True, timeout=30000):
        self.headless, self.timeout = headless, timeout
        self._pw = self._ctx = self._page = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        os.makedirs(PROFILE_DIR, exist_ok=True)
        self._pw = sync_playwright().start()
        # 🔴 launch_persistent_context = 用固定数据目录开浏览器（不是一次性 profile）
        self._ctx = self._pw.chromium.launch_persistent_context(
            PROFILE_DIR, headless=self.headless, user_agent=UA,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self._page.set_default_timeout(self.timeout)
        return self

    def __exit__(self, *exc):
        for closer in (getattr(self._ctx, "close", None), getattr(self._pw, "stop", None)):
            try:
                if closer:
                    closer()
            except Exception:
                pass
        return False

    # ---------------------------------------------------------------- 会话
    def goto_home(self):
        self._page.goto(HOME, wait_until="domcontentloaded")
        self._page.wait_for_timeout(2500)
        return self._page.url

    def logged_in(self):
        """登录态判定：URL 没被踢到 /login，且 bdstoken 取得到（后者才是硬证据）。"""
        url = self.goto_home()
        if "/login" in url or "passport.baidu.com" in url:
            return False
        return bool(self.bdstoken(quiet=True))

    # ---------------------------------------------------------------- 请求
    def web(self, url, data=None, timeout_ms=60000):
        """在已登录页面上下文里发请求 → 浏览器自带当前有效 cookie（同源，无 CORS）。

        data=dict → POST form-urlencoded；None → GET。返回解析后的 JSON（失败返 {}）。
        """
        if not self._page.url.startswith("https://pan.baidu.com"):
            self.goto_home()
        body = urllib.parse.urlencode(data) if data else None
        txt = self._page.evaluate(
            """async ({url, body, ms}) => {
                const ctl = new AbortController();
                const t = setTimeout(() => ctl.abort(), ms);
                try {
                    const r = await fetch(url, {
                        method: body === null ? 'GET' : 'POST',
                        headers: body === null ? {}
                            : {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: body === null ? undefined : body,
                        credentials: 'include',
                        signal: ctl.signal,
                    });
                    return await r.text();
                } finally { clearTimeout(t); }
            }""",
            {"url": url, "body": body, "ms": timeout_ms})
        try:
            return json.loads(txt)
        except Exception:
            return {"_raw": (txt or "")[:400]}

    def bdstoken(self, quiet=False):
        """现取 CSRF 令牌（绝不存盘——存了必过期）。"""
        r = self.web("https://pan.baidu.com/api/gettemplatevariable?fields="
                     + urllib.parse.quote('["bdstoken","uk","username"]'))
        res = r.get("result") if isinstance(r, dict) else None
        tok = res.get("bdstoken") if isinstance(res, dict) else None
        if not tok and not quiet:
            print(f"取 bdstoken 失败：errno={r.get('errno')} —— 多半是掉登录，跑 login 扫码")
        return tok

    def whoami(self):
        r = self.web("https://pan.baidu.com/api/gettemplatevariable?fields="
                     + urllib.parse.quote('["bdstoken","uk","username"]'))
        res = (r.get("result") if isinstance(r, dict) else None) or {}
        return res.get("bdstoken"), res.get("username"), res.get("uk")


# ---------------------------------------------------------------- CLI
def cmd_login():
    """打开有头浏览器让用户扫码；登录态自动落进持久 profile。"""
    print(f"持久 profile: {PROFILE_DIR}")
    with PanBrowser(headless=False, timeout=300000) as b:
        url = b.goto_home()
        if "/login" not in url and "passport" not in url and b.bdstoken(quiet=True):
            _, user, uk = b.whoami()
            print(f"🟢 已是登录态（{user} / uk={uk}），无需扫码")
            return 0
        print("🔵 浏览器已打开，请扫码登录（最多等 5 分钟）……")
        try:
            b._page.wait_for_url(lambda u: "/disk/" in u and "login" not in u, timeout=300000)
        except Exception:
            pass
        b._page.wait_for_timeout(3000)
        tok, user, uk = b.whoami()
        if not tok:
            print("🔴 仍未登录成功——没扫完或被风控，重跑一次")
            return 1
        print(f"🟢 登录成功：{user} / uk={uk}")
        print("   登录态已存入持久 profile，之后 share 直接用，不必再扫码。")
    return 0


def cmd_status():
    with PanBrowser(headless=True) as b:
        tok, user, uk = b.whoami()
        if tok:
            print(f"🟢 登录态有效：{user} / uk={uk}（持久 profile：{PROFILE_DIR}）")
            return 0
        print(f"🔴 未登录或已失效 → python panbrowser.py login 扫码")
        return 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    sys.exit({"login": cmd_login, "status": cmd_status}.get(cmd, cmd_status)())
