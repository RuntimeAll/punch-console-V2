# -*- coding: utf-8 -*-
"""网盘账对账 —— 总表（记录/网盘分发/分享链接总表.md）× 库（artifact.link/note）
==============================================================================
🔴 为什么要有这道闸（2026-08-22 窗W）：网盘分享账**同时活在两处**——
  ① `记录/网盘分发/分享链接总表.md`：人读正本（制度、纪律、有效期、备注），网盘分发 skill 回填；
  ② `kb.db artifact.link` + `note` JSON 的「网盘路径/网盘分享语」：机器account，发布物料与展示台读它。
两处并存本身合理（人读账 vs 机器账），但**没有对账闸就会漂移**：改一处忘另一处 = 发出去的链
和账上的链对不上，是发布线最贵的错。本工具就是那道闸。

🔴 口径分野（2026-08-22 实测得出，别再当漏账）：库里 36 册有链 = **v2 出品 5 册**
（发布包3+组卷册2，进总表）+ **老区平移历史册 31 册**（细类=历史册、source_line=
punch-console 吃库，链是老区建的）。总表首行明写「链接不平移——v2 出品从零记」，
所以历史册链**不进总表**，只留在库里作历史存档；对账 B 项因此只查 v2 出品。

对账四项（任一不符即非零退出，列明细不静默）：
  A. 总表有链 → 库里对应 artifact.link 必须一字不差；
  B. 库里有链的 **v2 出品册**（细类≠历史册） → 总表必须有行（漏记的点名）；
  C. 链接格式：必须 https://pan.baidu.com/s/… 且带 ?pwd=<4位提取码>，与「提取码」列一致；
  D. 网盘路径：总表路径 == 库 note.网盘路径（两边都有才比），且必须在 /apps/文档自动上传同步/ 下
     （第三方应用唯一可写根——写别处=传不上去）。

用法：
  python 工具箱/挂账/网盘账对账.py            # 对账（只读，有差异 exit 1）
  python 工具箱/挂账/网盘账对账.py --list      # 顺带打印全库有链册（含未进总表的）
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
SHEET = ROOT / '记录' / '网盘分发' / '分享链接总表.md'
PAN_ROOT = '/apps/文档自动上传同步/'
RX_LINK = re.compile(r'https://pan\.baidu\.com/s/[A-Za-z0-9_-]+\?pwd=([a-z0-9]{4})')
RX_AID = re.compile(r'\b(A\d{8}[0-9a-z]+)\b')


def read_sheet():
    """总表 → [{册, 路径, 链, 码, 日期, aid}]（只吃表格行）"""
    rows = []
    for line in SHEET.read_text(encoding='utf-8').splitlines():
        if not line.startswith('|') or line.startswith('|---') or '| 册/资料 |' in line:
            continue
        cells = [c.strip().strip('`') for c in line.strip('|').split('|')]
        if len(cells) < 7:
            continue
        m = RX_LINK.search(cells[2])
        aid = RX_AID.search(cells[6])
        rows.append({'册': cells[0], '路径': cells[1], '链': m.group(0) if m else cells[2],
                     '码': cells[3], '日期': cells[5], '备注': cells[6],
                     'aid': aid.group(1) if aid else None,
                     '码_链内': m.group(1) if m else None})
    return rows


def main():
    ap = argparse.ArgumentParser(description='网盘账对账（总表 × 库）')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()

    conn = sqlite3.connect('file:%s?mode=ro' % (ROOT / '知识库' / 'kb.db').as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    db, hist = {}, {}
    for r in conn.execute("SELECT id, name, link, note, 细类 FROM artifact "
                          "WHERE link IS NOT NULL AND link != ''"):
        pan = None
        if r['note']:
            try:
                pan = (json.loads(r['note']) or {}).get('网盘路径')
            except Exception:
                pass
        rec = {'name': r['name'], 'link': r['link'], 'pan': pan, '细类': r['细类']}
        (hist if r['细类'] == '历史册' else db)[r['id']] = rec
    conn.close()

    sheet = read_sheet()
    print(f'总表 {len(sheet)} 条｜库里 v2 出品有链 {len(db)} 册'
          f'｜老区平移历史册有链 {len(hist)} 册（按口径不进总表，只作历史存档）')
    bad = []

    # A/C/D：逐条查总表
    for s in sheet:
        if not s['码_链内']:
            bad.append(('C', s['册'], f"链接不合格式（缺 ?pwd=）：{s['链'][:60]}"))
        elif s['码'] and s['码_链内'] != s['码']:
            bad.append(('C', s['册'], f"提取码列={s['码']} 与链内 pwd={s['码_链内']} 不符"))
        if s['路径'] and not s['路径'].startswith(PAN_ROOT):
            bad.append(('D', s['册'], f"网盘路径不在可写根下：{s['路径']}"))
        if not s['aid']:
            bad.append(('A', s['册'], '备注里没写 artifact id，无法与库对账'))
            continue
        rec = db.get(s['aid']) or hist.get(s['aid'])
        if not rec:
            bad.append(('A', s['册'], f"库里 {s['aid']} 无 link（账上有链库里没有）"))
            continue
        if rec['link'].strip() != s['链']:
            bad.append(('A', s['册'], f"链不一致：总表 {s['链'][-14:]} ≠ 库 {rec['link'][-14:]}"))
        pan = rec['pan']
        if pan and s['路径'] and pan.rstrip('/') != s['路径'].rstrip('/'):
            bad.append(('D', s['册'], f"网盘路径不一致：总表 {s['路径']} ≠ 库 {pan}"))

    # B：库里有链但总表没记
    in_sheet = {s['aid'] for s in sheet if s['aid']}
    miss = [(aid, v['name']) for aid, v in db.items() if aid not in in_sheet]
    for aid, nm in miss:
        bad.append(('B', nm, f'{aid} 库里有链，总表无行（建完链没回填？）'))

    if a.list:
        print('\nv2 出品有链册：')
        for aid, v in sorted(db.items()):
            mark = '✓总表' if aid in in_sheet else '🔴未记'
            print(f'  {mark} {aid} {v["name"][:30]}  {v["link"][-12:]}')
        print(f'\n老区平移历史册有链 {len(hist)} 册（存档，不进总表）：')
        for aid, v in list(sorted(hist.items()))[:5]:
            print(f'  · {aid} {v["name"][:30]}  {v["link"][-12:]}')
        if len(hist) > 5:
            print(f'  …另 {len(hist) - 5} 册')

    print()
    if bad:
        print(f'🔴 对账不过：{len(bad)} 项')
        for kind, who, why in bad:
            print(f'  [{kind}] {who[:34]}：{why}')
        return 1
    print('🟢 对账通过：总表与库逐条一致（链/提取码/网盘路径三项）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
