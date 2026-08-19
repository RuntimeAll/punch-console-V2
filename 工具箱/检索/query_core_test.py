# -*- coding: utf-8 -*-
"""query_core 沙盘自证（D-20 ①精确过滤 + ②倒排 每个维度至少一条断言）。

两用：
  python 工具箱/检索/query_core_test.py                 # 自建临时库跑全部断言（不碰任何现有库）
  python 工具箱/检索/query_core_test.py --seed-db 知识库/kb.db
                                                        # 只把这 10 道测试题种进指定库（给 CLI/③层/API 冒烟用）

测试语料（10 题，一题一个坑位）：
  q01/q02 行程应用题（语意层可区分）、q03 购物应用题、q04 相反数、q05 绝对值化简（带 pattern/model/标签）、
  q06 母题混合运算 + q07/q08 两个变体（血缘对）、q09 已进卷的题、q10 退役题。
  册 ATEST 的卷 PTEST 收了 q01/q09 → 使用足迹（unused / in_artifact）有真数据可断言。
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from query_core import (build_query, count, fetch_rows, find_ids,  # noqa: E402
                        QueryError, resolve_kp_words)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / '工具箱' / '库' / 'schema_kb.sql'

KP_ROWS = [
    ('zjsx2024', '浙教版数学', None, '版本', 1),
    ('100', '七年级上册', 'zjsx2024', '年级学期', 1),
    ('100001', '有理数', '100', '单元', 1),
    ('100001002', '数轴', '100001', '小节', 2),
    ('100001002003', '相反数', '100001002', '考点', 3),
    ('100001003', '绝对值', '100001', '小节', 3),
    ('100001003003', '与绝对值有关的计算', '100001003', '考点', 3),
    ('100002', '有理数的运算', '100', '单元', 2),
    ('100002006', '有理数的混合运算', '100002', '小节', 6),
    ('100002006001', '有理数混合运算的运算顺序', '100002006', '考点', 1),
    ('100002006002', '有理数混合运算的实际应用', '100002006', '考点', 2),
]
KP_ALIAS = [('100001003003', '绝对值化简', '产线词')]
DICT_SEED = [
    ('qtype', 'q3', '应用题', 3), ('qtype', 'q7', '计算题', 7),
    ('difficulty', 'd1', '送分', 1), ('difficulty', 'd2', '巩固', 2),
    ('difficulty', 'd3', '中档', 3), ('difficulty', 'd4', '压轴', 4),
    ('source', 'scan', '扫描/拍照录入', 1), ('source', 'manual', '人工录入', 2),
    ('source', 'model', '模型生成', 3), ('source', 'pipeline', '管线生成', 4),
]
TAGS = [('tg-xc', '场景', '行程'), ('tg-gw', '场景', '购物'), ('tg-zt', '方法', '整体代入')]


def blocks(md):
    return '{"v":2,"rows":[{"cells":[{"type":"text","role":"题面","md":%s}]}]}' % (
        '"' + md.replace('\\', '\\\\').replace('"', '\\"') + '"')


# id / 题面 / qtype / diff / kp / status / source_kind / prov / mother / variant_op / pattern / tags
QUESTIONS = [
    ('qt01', '汽车从甲地开往乙地，先以每小时 60 千米的速度行驶 2 小时，再以每小时 45 千米的速度行驶 3 小时，'
             '求甲乙两地之间的路程。', 'q3', 'd3', '100002006002', '上架', 'manual', None, None, None, None,
     ['tg-xc']),
    ('qt02', '小明骑自行车上学，去时速度是每小时 15 千米，用了 0.4 小时；返回时速度是每小时 12 千米，'
             '求返回路上用的时间。', 'q3', 'd2', '100002006002', '草稿', 'manual', None, None, None, None,
     ['tg-xc']),
    ('qt03', '妈妈带 100 元去超市，买了 3 袋面粉每袋 18.5 元，又买了 2 瓶油每瓶 21 元，问还剩多少元。',
     'q3', 'd2', '100002006002', '草稿', 'manual', None, None, None, None, ['tg-gw']),
    ('qt04', '写出下列各数的相反数：$-3$，$0$，$+\\frac{2}{5}$。',
     'q7', 'd1', '100001002003', '草稿', 'manual', None, None, None, None, []),
    ('qt05', '化简：$|-3|+|2-5|-|-1|$。', 'q7', 'd3', '100001003003', '上架', 'model',
     '{"model_id":"EM-abs","seed":3}', None, None, 'PT-abs', ['tg-zt']),
    ('qt06', '计算：$-8+15\\div(-3)\\times 2$。', 'q7', 'd2', '100002006001', '草稿', 'model',
     '{"model_id":"EM-mix","seed":7}', None, None, None, []),
    ('qt07', '计算：$-12+20\\div(-4)\\times 3$。', 'q7', 'd2', '100002006001', '草稿', 'model',
     '{"mother_qid":"qt06","operator":"换数"}', 'qt06', '换数', None, []),
    ('qt08', '计算：$20\\div(-4)\\times 3-12$。', 'q7', 'd3', '100002006001', '草稿', 'model',
     '{"mother_qid":"qt06","operator":"换序"}', 'qt06', '换序', None, []),
    ('qt09', '计算：$(-2)^3\\div 4-(-5)$。', 'q7', 'd2', '100002006001', '上架', 'manual',
     None, None, None, None, []),
    ('qt10', '计算：$1+1$。（作废题，留作退役断言用）', 'q7', 'd1', '100002006001', '退役', 'manual',
     None, None, None, None, []),
]
PAPER_ITEMS = [('qt01', 1), ('qt09', 2)]      # 册 ATEST / 卷 PTEST 收了这两道


def seed(conn):
    """把测试语料种进库（全 INSERT OR IGNORE，重跑不翻倍、不覆盖已有）。"""
    cur = conn.cursor()
    for d, c, lab, o in DICT_SEED:
        cur.execute('INSERT OR IGNORE INTO dict_item(domain,code,label,ord,status) VALUES (?,?,?,?,?)',
                    (d, c, lab, o, '在用'))
    for i, (kid, name, par, lv, o) in enumerate(KP_ROWS):
        cur.execute('INSERT OR IGNORE INTO kp(id,name,parent_id,level,ord,status) VALUES (?,?,?,?,?,?)',
                    (kid, name, par, lv, o, '现行'))
    for kid, al, kind in KP_ALIAS:
        cur.execute('INSERT OR IGNORE INTO kp_alias(kp_id,alias,alias_kind) VALUES (?,?,?)', (kid, al, kind))
    for tid, dom, name in TAGS:
        cur.execute('INSERT OR IGNORE INTO tag(id,domain,name,status) VALUES (?,?,?,?)',
                    (tid, dom, name, '在用'))
    cur.execute('INSERT OR IGNORE INTO question_pattern(id,name,kp_ids_json,desc,status) VALUES (?,?,?,?,?)',
                ('PT-abs', '绝对值化简型', '["100001003003"]', '含多重绝对值的化简', '在用'))
    for n, (qid, md, qt, df, kp, st, sk, prov, mother, vop, pat, tags) in enumerate(QUESTIONS):
        ts = f'2026-08-19 09:{n:02d}:00'
        cur.execute(
            'INSERT OR IGNORE INTO question(id,blocks_json,qtype_code,diff_code,pattern_id,source_kind,'
            'source_raw,prov_json,mother_qid,variant_op,match_key,status,created_at,updated_at) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (qid, blocks(md), qt, df, pat, sk, '沙盘测试语料', prov, mother, vop, None, st, ts, ts))
        cur.execute('INSERT OR IGNORE INTO question_kp(question_id,kp_id,is_primary,anchor_json) '
                    'VALUES (?,?,1,?)', (qid, kp, '{"stage":"沙盘"}'))
        for t in tags:
            cur.execute('INSERT OR IGNORE INTO question_tag(question_id,tag_id) VALUES (?,?)', (qid, t))
    cur.execute('INSERT OR IGNORE INTO artifact(id,name,kind,status,source_line,created_at) '
                'VALUES (?,?,?,?,?,?)', ('ATEST', '沙盘测试册', '专项卷', '在产', '找题自证',
                                         '2026-08-19 09:30:00'))
    cur.execute('INSERT OR IGNORE INTO paper(id,artifact_id,kind,title,ord,status,created_at) '
                'VALUES (?,?,?,?,?,?,?)', ('PTEST', 'ATEST', '专项卷', '沙盘测试卷', 1, '草稿',
                                           '2026-08-19 09:30:00'))
    for qid, o in PAPER_ITEMS:
        cur.execute('INSERT OR IGNORE INTO paper_item(paper_id,ord,question_id,section) VALUES (?,?,?,?)',
                    ('PTEST', o, qid, '测试节'))
    conn.commit()


# ══════════════════════════════════════════════════════════════════════
FAIL = []
N = [0]


def check(name, got, want):
    N[0] += 1
    got = sorted(got) if isinstance(got, (list, set, tuple)) else got
    want = sorted(want) if isinstance(want, (list, set, tuple)) else want
    if got == want:
        print(f'  ✓ {name}')
    else:
        print(f'  ✗ {name}\n      得 {got}\n      期 {want}')
        FAIL.append(name)


def check_raise(name, fn, keyword):
    N[0] += 1
    try:
        fn()
    except QueryError as e:
        if keyword in str(e):
            print(f'  ✓ {name}（拒查：{str(e)[:52]}…）')
            return
        print(f'  ✗ {name}：报错了但话不对——{e}')
        FAIL.append(name)
        return
    except Exception as e:
        print(f'  ✗ {name}：抛了非 QueryError —— {type(e).__name__}: {e}')
        FAIL.append(name)
        return
    print(f'  ✗ {name}：**没报错**（静默放宽条件=最阴的坑）')
    FAIL.append(name)


def run_asserts(conn):
    ids = lambda f, **kw: find_ids(conn, f, **kw)  # noqa: E731

    print('\n── ② 倒排 · 考点（名 / 别名 / 数字 id 前缀取整枝）──')
    check('kp 考点名 →恰一叶子', ids({'kp': '相反数'}), ['qt04'])
    check('kp 别名 resolve（绝对值化简→100001003003）', ids({'kp': '绝对值化简'}), ['qt05'])
    check('kp 12 位叶 id', ids({'kp': '100002006002'}), ['qt01', 'qt02', 'qt03'])
    check('kp 数字 id 前缀=整节（100002006）', ids({'kp': '100002006'}),
          ['qt01', 'qt02', 'qt03', 'qt06', 'qt07', 'qt08', 'qt09', 'qt10'])
    check('kp 数字 id 前缀=整章（100001 两个小节合并）', ids({'kp': '100001'}), ['qt04', 'qt05'])
    check('kp 多值=OR', ids({'kp': ['相反数', '绝对值化简']}), ['qt04', 'qt05'])

    print('\n── ① 精确过滤 · 题型 / 难度 / 状态 / 来源类 ──')
    check('qtype 中文标签→码', ids({'qtype': '应用题'}), ['qt01', 'qt02', 'qt03'])
    check('difficulty 中文标签→码（🔴 难度不进向量）', ids({'difficulty': '中档'}),
          ['qt01', 'qt05', 'qt08'])
    check('difficulty 多值=OR', ids({'difficulty': ['送分', '中档']}),
          ['qt01', 'qt04', 'qt05', 'qt08', 'qt10'])
    check('status 直筛（退役题查得到，不静默藏）', ids({'status': '退役'}), ['qt10'])
    check('source_kind 直筛', ids({'source_kind': 'model'}), ['qt05', 'qt06', 'qt07', 'qt08'])

    print('\n── ② 倒排 · 标签 / pattern / model ──')
    check('tag 域:名', ids({'tag': '场景:行程'}), ['qt01', 'qt02'])
    check('tag 全角冒号同解', ids({'tag': '场景：行程'}), ['qt01', 'qt02'])
    check('tag 省略域（按名跨域）', ids({'tag': '购物'}), ['qt03'])
    check('tag 多值=AND（收窄，不是并集）', ids({'tag': ['场景:行程', '方法:整体代入']}), [])
    check('pattern 直筛', ids({'pattern': 'PT-abs'}), ['qt05'])
    check('model=prov_json.model_id 精确', ids({'model': 'EM-mix'}), ['qt06'])
    check('model 不误伤同族变体（变体 prov 无 model_id）', ids({'model': 'EM-abs'}), ['qt05'])

    print('\n── +6 血缘 · 母题变体 / 同母兄弟 ──')
    check('mother=<qid> 取变体', ids({'mother': 'qt06'}), ['qt07', 'qt08'])
    check('siblings 缺省不含自身', ids({'siblings': 'qt07'}), ['qt08'])
    check('siblings 含自身', ids({'siblings': 'qt07', 'siblings_include_self': True}), ['qt07', 'qt08'])
    check('siblings 传母题 id=取它的全部变体', ids({'siblings': 'qt06'}), ['qt07', 'qt08'])

    print('\n── +7 使用足迹 · 进卷与否（join paper_item 现算）──')
    check('unused=True（没进过任何卷）', ids({'unused': True}),
          ['qt02', 'qt03', 'qt04', 'qt05', 'qt06', 'qt07', 'qt08', 'qt10'])
    check('unused=False（进过卷的）', ids({'unused': False}), ['qt01', 'qt09'])
    check('in_artifact=ATEST', ids({'in_artifact': 'ATEST'}), ['qt01', 'qt09'])
    check('not_in_artifact=ATEST（组卷同册去重的前置）', ids({'not_in_artifact': 'ATEST'}),
          ['qt02', 'qt03', 'qt04', 'qt05', 'qt06', 'qt07', 'qt08', 'qt10'])

    print('\n── 题面子串 / 组合 AND / 分页与计数 ──')
    check('text 子串', ids({'text': '每小时'}), ['qt01', 'qt02'])
    check('text 元字符不被当通配（%）', ids({'text': '100%'}), [])
    check('组合 AND：整章+巩固+未进卷', ids({'kp': '100002', 'difficulty': '巩固', 'unused': True}),
          ['qt02', 'qt03', 'qt06', 'qt07'])
    check('组合 AND：应用题+行程标签+草稿', ids({'qtype': '应用题', 'tag': '场景:行程', 'status': '草稿'}),
          ['qt02'])
    check('count 与 find_ids 同口径', count(conn, {'kp': '100002006'}), 8)
    check('limit 截断（按 created_at,id 定序）', ids({'kp': '100002006'}, limit=3),
          ['qt01', 'qt02', 'qt03'])
    check('order=created_desc', find_ids(conn, {'kp': '100002006002'}, order='created_desc'),
          ['qt01', 'qt02', 'qt03'])
    check('无过滤器=全表', count(conn, {}), len(QUESTIONS))

    print('\n── 展示行（CLI/页面同一口径）──')
    row = fetch_rows(conn, {'kp': '绝对值化简'})[0]
    check('展示行·id', row['id'], 'qt05')
    check('展示行·难度中文', row['difficulty'], '中档')
    check('展示行·考点名', [k['name'] for k in row['kps']], ['与绝对值有关的计算'])
    check('展示行·题面首块非空', bool(row['stem']) and '🔴' not in row['stem'], True)
    r01 = [r for r in fetch_rows(conn, {'in_artifact': 'ATEST'}) if r['id'] == 'qt01'][0]
    check('展示行·进过几卷', r01['paper_count'], 1)

    print('\n── 🔴 拒查（翻不出就报错，绝不静默当「不过滤」）──')
    check_raise('未知过滤器键', lambda: ids({'dificulty': '中档'}), '未知过滤器键')
    check_raise('考点名零命中', lambda: ids({'kp': '不存在的考点名'}), 'resolve 命中现行叶子 0 个')
    check_raise('考点名撞到非叶子（小节名）', lambda: ids({'kp': '绝对值'}), 'resolve 命中现行叶子 0 个')
    check_raise('考点 id 前缀零命中', lambda: ids({'kp': '999999'}), '零命中')
    check_raise('标签库里没有', lambda: ids({'tag': '方法:不存在标签'}), '零命中')
    check_raise('难度字典翻不出', lambda: ids({'difficulty': '困难'}), '字典翻不出')
    check_raise('status 值域外', lambda: ids({'status': '已发布'}), '非法')
    check_raise('mother 指空', lambda: ids({'mother': 'qNOPE'}), '不许指空')
    check_raise('in_artifact 指空', lambda: ids({'in_artifact': 'ANOPE'}), '不许指空')
    check_raise('siblings_include_self 单给', lambda: ids({'siblings_include_self': True}), '条件没落地')
    check_raise('limit 非正整数', lambda: ids({}, limit=0), 'limit')

    print('\n── 全参数化自证（SQL 里除占位符外没有外部输入）──')
    sql, params = build_query(conn, {
        'kp': '100002006', 'qtype': '应用题', 'difficulty': ['巩固', '中档'], 'status': ['草稿', '上架'],
        'source_kind': 'manual', 'tag': ['场景:行程'], 'text': "'; DROP TABLE question;--",
        'unused': True, 'not_in_artifact': 'ATEST'}, limit=5)
    check('占位符个数 == 参数个数', sql.count('?'), len(params))
    check('SQL 里不含注入串', "DROP TABLE" in sql, False)
    check('注入串当普通子串查=0 条', conn.execute(sql, params).fetchall(), [])
    check('库还在（注入没落地）', conn.execute('SELECT COUNT(*) FROM question').fetchone()[0],
          len(QUESTIONS))

    print('\n── resolve_kp_words 说明可回显（查询透明）──')
    kp_ids, notes = resolve_kp_words(conn, ['100002006', '相反数'])
    check('整枝命中节点数', len(kp_ids), 4)          # 100002006 + 两叶 + 100001002003
    check('说明两条', len(notes), 2)


def main():
    ap = argparse.ArgumentParser(description='query_core 沙盘自证')
    ap.add_argument('--seed-db', help='只种测试语料进这个库（不跑断言）')
    ap.add_argument('--keep', help='把自建的临时库落到这个路径（默认用内存库）')
    args = ap.parse_args()

    if args.seed_db:
        p = Path(args.seed_db)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            sys.exit(f'🔴 库不存在：{p}（先跑 工具箱/库/init_db.py --only kb）')
        conn = sqlite3.connect(str(p))
        conn.execute('PRAGMA foreign_keys=ON')
        seed(conn)
        n = conn.execute("SELECT COUNT(*) FROM question WHERE id LIKE 'qt%'").fetchone()[0]
        print(f'测试语料已种进 {p}：question qt* 共 {n} 道，册 ATEST/卷 PTEST 收 {len(PAPER_ITEMS)} 道')
        conn.close()
        return 0

    dbp = args.keep or ':memory:'
    if args.keep and Path(args.keep).exists():
        Path(args.keep).unlink()
    conn = sqlite3.connect(dbp)
    conn.executescript(SCHEMA.read_text(encoding='utf-8'))
    conn.execute('PRAGMA foreign_keys=ON')
    seed(conn)
    print(f'沙盘：{dbp}（{len(QUESTIONS)} 题 / {len(KP_ROWS)} kp / {len(TAGS)} 标签 / 1 册 1 卷）')
    run_asserts(conn)
    conn.close()
    print(f'\n=== {N[0] - len(FAIL)}/{N[0]} 通过 ===' + ('' if not FAIL else f'\n🔴 未过：{FAIL}'))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    raise SystemExit(main())
