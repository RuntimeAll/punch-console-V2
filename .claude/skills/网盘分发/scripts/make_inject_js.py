# -*- coding: utf-8 -*-
"""生成「cookie 注入自愈」的 playwright 代码文件（配 browser_run_code_unsafe 的 filename 参数）。

背景（2026-07-31 定版）：playwright MCP 实例是每会话 `--isolated` 内存态（~/.claude.json 用户级
配置），重启必掉登录——**持久层 = 快照文件里的 BDUSS 身份 cookie（周~月级长命），不是浏览器**。
掉登录时把快照注入新浏览器，百度会自动重发会话层 cookie，随后即可重导新快照建分享。
凭据内联进 js 文件（默认落 TEMP），不经对话/命令行明文。

用法: python make_inject_js.py [输出路径]
"""
import io
import json
import os
import sys

SNAP = r'd:\workplace\ai-bkb-v2\password\baidu-pan-cookies.json'

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TEMP', '.'), 'pan-inject.js')
st = json.load(io.open(SNAP, encoding='utf-8'))
cookies = st.get('cookies') or []
if not cookies:
    print('🔴 快照里没有 cookie，自愈无从谈起——直接让用户扫码')
    sys.exit(1)

js = (
    'async (page) => {\n'
    '  const cookies = ' + json.dumps(cookies) + ';\n'
    '  await page.context().addCookies(cookies);\n'
    "  await page.goto('https://pan.baidu.com/disk/main');\n"
    '  await page.waitForTimeout(3000);\n'
    "  if (await page.locator('text=\u53bb\u767b\u5f55').count() > 0)"
    " return '\u26a0\ufe0f\u6ce8\u5165\u540e\u4ecd\u672a\u767b\u5f55\uff0cBDUSS \u5df2\u8fc7\u671f\uff0c\u9700\u7528\u6237\u626b\u7801';\n"
    "  await page.context().storageState({ path: 'd:/workplace/ai-bkb/password/baidu-pan-cookies.json' });\n"
    "  return '\u6ce8\u5165\u81ea\u6108\u6210\u529f\uff0c\u5feb\u7167\u5df2\u5237\u65b0\uff08' + cookies.length + ' cookies\uff09';\n"
    '}\n')
io.open(out, 'w', encoding='utf-8').write(js)
print('%s  (%d cookies)' % (out, len(cookies)))
