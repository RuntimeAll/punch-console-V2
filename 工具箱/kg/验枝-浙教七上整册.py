# -*- coding: utf-8 -*-
"""整册铺枝自证（🔴 只读断言，一条 SELECT 都不写库）——沙盘与主位同一把尺。

用法：
    python 验枝-浙教七上整册.py                 # 默认量主位 <v2根>/知识库/kb.db
    python 验枝-浙教七上整册.py --db <副本路径>  # 量沙盘副本

判据（铺 整册枝-浙教七上.json + 别名 16 条【§A 八条 + §A2 补遗八条】后应成立）：
  12 新小节 / 42 新叶 / 全库 71 现行考点叶 / 四单元 status=现行 /
  kp 102 节点 / kp_alias 66 条（23 存量 + 27 内联【24 原 + 3 短名转别名】+ 16 命令）/
  抽样叶过 gates.assert_leaf_kp / 三条 resolve 单命中。
退出码 0=全绿，1=有 FAIL。
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import assert_leaf_kp, LeafKpError  # noqa: E402

DEFAULT_DB = Path(__file__).resolve().parents[2] / '知识库' / 'kb.db'
NEW_UNITS = ('100003', '100004', '100005', '100006')
RESOLVE_CASES = [
    ('有理数的大小比较', '100001004002'),   # 讲义名→既有叶（别名清单 §A#4）
    ('有理数与无理数', '100003003001'),     # 洗名→新叶（§B#7）
    ('合并同类项', '100004003001'),         # 合并→新叶（§B#16）
]

fails = []


def chk(name, got, want):
    ok = got == want
    print(f'[{"PASS" if ok else "FAIL"}] {name}: 实际={got} 期望={want}')
    if not ok:
        fails.append(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=str(DEFAULT_DB))
    args = ap.parse_args()
    p = Path(args.db)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}')
    c = sqlite3.connect(f'file:{p.as_posix()}?mode=ro', uri=True)   # 🔴 只读打开
    print(f'量库：{p}\n')

    chk('新小节数（100003~100006）', c.execute(
        "SELECT COUNT(*) FROM kp WHERE level='小节' AND substr(id,1,6) IN (?,?,?,?)",
        NEW_UNITS).fetchone()[0], 12)
    chk('新叶数（100003~100006 考点层）', c.execute(
        "SELECT COUNT(*) FROM kp WHERE level='考点' AND substr(id,1,6) IN (?,?,?,?)",
        NEW_UNITS).fetchone()[0], 42)
    chk('总叶数（全库现行考点叶）', c.execute(
        "SELECT COUNT(*) FROM kp k WHERE k.level='考点' AND k.status='现行' "
        "AND NOT EXISTS(SELECT 1 FROM kp x WHERE x.parent_id=k.id)").fetchone()[0], 71)
    chk('总叶数（kg_tool show 口径：无子且非退役）', c.execute(
        "SELECT COUNT(*) FROM kp k WHERE k.status!='退役' "
        "AND NOT EXISTS(SELECT 1 FROM kp x WHERE x.parent_id=k.id)").fetchone()[0], 71)

    for u in NEW_UNITS:
        nm, st = c.execute('SELECT name, status FROM kp WHERE id=?', (u,)).fetchone()
        chk(f'单元 {u} {nm} 状态', st, '现行')

    chk('kp 节点总数', c.execute('SELECT COUNT(*) FROM kp').fetchone()[0], 102)
    chk('kp_alias 总数', c.execute('SELECT COUNT(*) FROM kp_alias').fetchone()[0], 66)

    for kid in ('100003003001', '100004003001', '100006002004', '100005003001'):
        try:
            assert_leaf_kp(c, kid)
            nm = c.execute('SELECT name FROM kp WHERE id=?', (kid,)).fetchone()[0]
            print(f'[PASS] gates.assert_leaf_kp({kid} {nm}) 通过')
        except LeafKpError as e:
            print(f'[FAIL] gates.assert_leaf_kp({kid}): {e}')
            fails.append(f'leafgate {kid}')

    for bad, why in (('100003003', '小节层'), ('100006', '单元层')):
        try:
            assert_leaf_kp(c, bad)
            print(f'[FAIL] 叶子闸负例 {bad}（{why}）竟然放行')
            fails.append(f'leafgate-neg {bad}')
        except LeafKpError:
            print(f'[PASS] 叶子闸负例 {bad}（{why}）如期拒收')

    # resolve 抽测（复刻 kg_tool 的 名字精确→别名精确→只留叶子 口径）
    for word, want in RESOLVE_CASES:
        hits = [r[0] for r in c.execute('SELECT id FROM kp WHERE name=?', (word,))]
        hits = [i for i in hits if _is_leaf(c, i)]
        via = '名字精确'
        if not hits:
            hits = [r[0] for r in c.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (word,))]
            hits = [i for i in hits if _is_leaf(c, i)]
            via = '别名精确'
        chk(f'resolve {word!r}（{via}，须单命中）', hits, [want])

    short = c.execute("SELECT id, name FROM kp WHERE level='考点' AND length(name)<3").fetchall()
    print(f'{"[WARN]" if short else "[PASS]"} 叶名<3字巡查：{short if short else "无"}'
          + ('　← 草案原名逐字照办，resolve 短名风险已记入交付报告' if short else ''))

    print('\n=== ' + ('全绿' if not fails else f'{len(fails)} 条 FAIL：{fails}') + ' ===')
    sys.exit(1 if fails else 0)


def _is_leaf(c, i):
    return c.execute(
        "SELECT 1 FROM kp k WHERE k.id=? AND k.status!='退役' "
        "AND NOT EXISTS(SELECT 1 FROM kp x WHERE x.parent_id=k.id)", (i,)).fetchone() is not None


if __name__ == '__main__':
    main()
