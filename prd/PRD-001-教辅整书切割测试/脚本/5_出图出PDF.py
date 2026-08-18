# -*- coding: utf-8 -*-
"""④ Chrome headless：预览截图 + 打印件 PDF。截完 sleep 再验文件（Chrome 延迟落盘）。"""
import sys, os, subprocess, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 讲义解析 as J
sys.stdout.reconfigure(encoding='utf-8')

ROOT = J.ROOT
OUT = os.path.join(ROOT, '产物')
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
PROFILE = os.path.join(ROOT, '_chrome_profile')

def run(args, tag):
    print('>>', tag)
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        print('   rc=%s' % p.returncode)
    err = (p.stderr or '').strip().splitlines()
    for ln in err[-4:]:
        print('   ' + ln)

def wait_file(path, tries=12):
    for _ in range(tries):
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            time.sleep(1.0)
            return True
        time.sleep(1.0)
    return False

jobs = [
    (os.path.join(OUT, '预览.html'), os.path.join(OUT, '预览截图.png'), 'shot',
     ['--window-size=1900,2600']),
    (os.path.join(OUT, '导出-题目卷.html'), os.path.join(OUT, '_导出首屏截图.png'), 'shot',
     ['--window-size=1240,1754']),
    (os.path.join(OUT, '导出-题目卷.html'), os.path.join(OUT, '导出-题目卷.pdf'), 'pdf', []),
]

for src, dst, mode, extra in jobs:
    if os.path.exists(dst):
        os.remove(dst)
    args = [CHROME, '--headless=new', '--disable-gpu', '--no-proxy-server',
            '--no-sandbox', '--hide-scrollbars', '--force-device-scale-factor=1',
            '--user-data-dir=' + PROFILE, '--virtual-time-budget=15000'] + extra
    if mode == 'shot':
        args.append('--screenshot=' + dst)
    else:
        args += ['--print-to-pdf=' + dst, '--no-pdf-header-footer']
    args.append('file:///' + src.replace('\\', '/'))
    run(args, '%s -> %s' % (mode, os.path.basename(dst)))
    ok = wait_file(dst)
    print('   %s %s %s' % ('OK ' if ok else 'FAIL',
                           os.path.basename(dst),
                           ('%.0f KB' % (os.path.getsize(dst) / 1024)) if os.path.exists(dst) else '-'))

shutil.rmtree(PROFILE, ignore_errors=True)
