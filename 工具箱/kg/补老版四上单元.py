# -*- coding: utf-8 -*-
"""窗Q · 四上枝补老版教材单元（KG 整理·使用中补枝第一例）
==============================================================================
🔴 为什么补：窗O 的四上枝按 26秋新版教材铺（9 单元），但**存量教辅与考卷仍考老版单元**
——2026-08-22 四上期末卷实弹实证：除数是两位数的除法/公顷和平方千米/数学广角（合理安排
时间）都在卷上，无枝可挂。备课线也实教过（苏俊宇 L3 课内同步=公顷和平方千米）。
窗O 定则「目录壳=教材章节」对老版**真教材单元**同样成立：补壳收题，note 标明老版身份。

补 3 单元 + 2 小节 + 14 考点（追加式，不动既有 9 单元）：
  400010 除数是两位数的除法（老版U6）：口算除法(2考点) / 笔算除法(6考点)
  400011 公顷和平方千米（老版U2·短单元无节）：4 考点直挂
  400012 数学广角（老版U8·优化）：2 考点直挂——其中「植树问题」🔴低置信
        （系老版五上广角内容，期末卷混编进四上，暂挂此单元待人审）

用法：--plan 只打计划；--apply --db <路径> 执行（幂等：同名跳过）。
守恒：只 INSERT kp；question/question_kp 零触碰；既有 kp 行逐行哈希一致。
"""
import argparse
import hashlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

NOTE = '窗Q·老版人教四上单元补枝(存量考卷实证仍考,26秋新版已调整) 2026-08-22'
LOW_ZS = '🔴低置信归属:植树问题系老版五上数学广角内容,期末卷混编进四上,暂挂此单元待人审'

SPEC = [
    ('400010', '除数是两位数的除法', '老版人教四上第6单元', [
        ('口算除法', ['除数是两位数的口算除法', '除数是两位数的除法估算']),
        ('笔算除法', ['商一位数的笔算除法', '商两位数的笔算除法', '商的位数判断',
                      '商的变化规律', '除法的验算', '除法的实际应用']),
    ]),
    ('400011', '公顷和平方千米', '老版人教四上第2单元·短单元无节', [
        (None, ['公顷的认识', '平方千米的认识', '面积单位的换算与比较',
                '面积的实际估算与应用']),
    ]),
    ('400012', '数学广角', '老版人教四上第8单元·优化', [
        (None, ['合理安排时间（优化）', '植树问题']),
    ]),
]


def build_rows():
    rows = []
    for uid, uname, utag, secs in SPEC:
        uord = int(uid[-3:])
        rows.append((uid, uname, '400', '单元', uord, f'{utag}｜{NOTE}'))
        si = 0
        direct = 0
        for sname, kps in secs:
            if sname is None:
                parent = uid
            else:
                si += 1
                parent = f'{uid}{si:03d}'
                rows.append((parent, sname, uid, '小节', si, NOTE))
            for kname in kps:
                if sname is None:
                    direct += 1
                    ki = direct
                else:
                    ki = kps.index(kname) + 1
                note = (LOW_ZS + '｜' + NOTE) if kname == '植树问题' else NOTE
                rows.append((f'{parent}{ki:03d}', kname, parent, '考点', ki, note))
    return rows


def main():
    ap = argparse.ArgumentParser(description='四上枝补老版单元（窗Q）')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--db')
    a = ap.parse_args()

    rows = build_rows()
    stat = {}
    for r in rows:
        stat[r[3]] = stat.get(r[3], 0) + 1
    print('补枝计划：', '，'.join(f'{k}{v}' for k, v in stat.items()), f'＝{len(rows)} 节点')
    if a.plan or not a.apply:
        for rid, name, parent, level, order, note in rows:
            pad = {'单元': '', '小节': '  ', '考点': '    '}[level]
            flag = ' 🔴低置信' if '低置信' in note else ''
            print(f'{pad}[{rid}] {name}{flag}')
        return

    assert a.db, '--apply 必须显式给 --db'
    conn = sqlite3.connect(a.db)
    try:
        assert conn.execute("SELECT 1 FROM kp WHERE id='400'").fetchone(), \
            '🔴 四上枝 (400) 不在库——先跑 铺小学枝四上.py'
        pre = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
               for t in ('kp', 'question', 'question_kp')}
        h0 = hashlib.sha256()
        pre_ids = set()
        for row in conn.execute('SELECT id,name,parent_id,level,ord,status FROM kp ORDER BY id'):
            pre_ids.add(row[0])
            h0.update(repr(tuple(row)).encode('utf-8'))
        pre_hash = h0.hexdigest()

        ins = skip = 0
        inserted = set()
        with conn:
            for rid, name, parent, level, order, note in rows:
                if conn.execute('SELECT 1 FROM kp WHERE parent_id=? AND name=?',
                                (parent, name)).fetchone():
                    skip += 1
                    continue
                conn.execute('INSERT INTO kp(id,name,parent_id,level,ord,status,note) '
                             "VALUES(?,?,?,?,?,'现行',?)",
                             (rid, name, parent, level, order, note))
                ins += 1
                inserted.add(rid)

        post = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                for t in ('kp', 'question', 'question_kp')}
        h1 = hashlib.sha256()
        for row in conn.execute('SELECT id,name,parent_id,level,ord,status FROM kp ORDER BY id'):
            if row[0] not in inserted:
                h1.update(repr(tuple(row)).encode('utf-8'))
        assert h1.hexdigest() == pre_hash, '🔴 守恒闸炸：存量 kp 行被改动'
        for t in ('question', 'question_kp'):
            assert post[t] == pre[t], f'🔴 守恒闸炸：{t} 行数变了'
        print(f"✅ 补枝完成：kp +{ins}（幂等跳过 {skip}）；kp {pre['kp']}→{post['kp']}；"
              f"question/question_kp 零触碰（{post['question']}/{post['question_kp']}）")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
