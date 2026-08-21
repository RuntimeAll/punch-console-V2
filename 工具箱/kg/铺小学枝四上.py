# -*- coding: utf-8 -*-
"""窗O · 小学枝四上 KG——**教材同步结构**重铺（v2，推倒窗N教辅册结构重来）
==============================================================================
🔴 窗N 第一版按教辅册（基础篇/提高篇/计算篇/应用篇）铺，被用户打回：「不是正确学校
同步的章节小节」。本版章/节正本=**26秋新版四上人教教材 PDF 逐页实翻**（目录页+全册
拼版目检，2026-08-21 窗O）：9 章 14 节；考点仍取老区四上讲义解析账的 110 个（名清洗
沿窗N 口径），逐个归到教材节下。

树形（版本→年级学期→单元→小节→考点；单元内教材无分节的考点直挂单元——小节可选长）：
  小学数学 xxsx（🔴 小学不分教材版本，用户口径）
   └ 四年级上册 400
      ├ 万以上数的认识【亿以内数的认识/亿以上数的认识/数的大小比较/数的改写和求近似数】
      ├ 1亿有多大（综合与实践·直挂） ├ 角的度量【角的再认识/角的度量】
      ├ 多位数乘两位数【口算乘法/笔算乘法/用估算解决问题←单元知识结构图三分枝】
      │   （教辅误名「三位数乘两位数」，教材名为准）
      ├ 加法模型和乘法模型（教材单元内无分节·直挂） ├ 平行四边形和梯形【平行和垂直/平行四边形和梯形】
      ├ 条形统计图【单式条形统计图/复式条形统计图】 ├ 寻找宝藏（综合与实践·直挂）
      └ 复习与关联【＊数学广角：鸡兔同笼（教材p118 选学栏目）】

归节拿不准的 4 个标 🔴低置信（算盘/大数计算/数字与算式规律/假设推理法——教材无对应
明示节，按最近内容归，note 留痕人审）。教辅「应用篇」16 考点按其所用技能归节（口算应用
→口算乘法/估算应用→用估算解决问题/其余→笔算乘法），系统性决策记此一处。

用法：
  python 工具箱/kg/铺小学枝四上.py --plan             # 只打计划
  python 工具箱/kg/铺小学枝四上.py --apply --db <路径>  # 执行：删旧小学枝(验零引用)→重铺，幂等
守恒：question/question_kp 零触碰；非小学枝 kp 行前后逐行哈希一致；删枝前验挂载零引用。
"""
import argparse
import hashlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT_ID, ROOT_NAME = 'xxsx', '小学数学'
TERM_ID, TERM_NAME = '400', '四年级上册'
NOTE = '窗O·四上教材同步结构(章节=26秋新版教材实翻,考点=讲义解析账) 2026-08-22'
LOW = '🔴低置信归节:教材无对应明示节,按最近内容归'

# (单元名, 单元note补充, [(小节名 or None, [考点名...]), ...])；考点名前 '*'=低置信归节
SPEC = [
    ('万以上数的认识', None, [
        ('亿以内数的认识', ['认识自然数', '认识计数单位和十进制计数法', '认识数位',
                            '认识数级', '大数的组成', '大数的读法', '大数的写法',
                            '组数问题', '写数问题（猜数问题）', '*数字与算式规律',
                            '*假设推理法解决数字问题']),
        ('亿以上数的认识', ['*算盘的认识和使用', '*大数计算问题']),
        ('数的大小比较', ['大数的比较', '复杂数的大小比较']),
        ('数的改写和求近似数', ['大数的改写和近似数', '近似数的最值问题']),
    ]),
    ('1亿有多大', '综合与实践', [
        (None, ['1亿有多大']),
    ]),
    ('角的度量', None, [
        ('角的再认识', ['角的认识', '角的分类', '数角']),
        ('角的度量', ['量角器的认识与使用', '用量角器量角', '用量角器画角',
                      '用三角尺画角', '角度计算问题其一：直接求角的度数',
                      '角度计算问题其二：在图形中求角的度数',
                      '角度计算问题其三：在折叠图形中求角的度数',
                      '角度计算问题其四：在三角尺中求角的度数',
                      '角度计算问题其五：在钟表中求角的度数']),
    ]),
    ('多位数乘两位数', '教辅册名「三位数乘两位数·计算/应用篇」并入，教材名为准', [
        ('口算乘法', ['三位数乘两位数的口算', '乘法基础应用其一：口算乘法与实际应用']),
        ('笔算乘法', ['三位数乘两位数的笔算', '因数中间有0的乘法', '因数末尾有0的乘法',
                      '乘法竖式的意义', '三位数乘两位数混合运算', '三位数乘两位数列式计算',
                      '积的位数问题', '积末尾的0', '乘法算式大小比较', '乘积的最值问题',
                      '积的规律其一：一个因数的变化规律', '积的规律其二：两个因数的变化规律',
                      '积的规律其三：积不变的规律（积不变性质）', '乘法算式规律', '乘法算式谜',
                      '乘法基础应用其二：简单的乘法应用题', '一般复合应用题其一：两步连乘应用',
                      '一般复合应用题其二：乘除混合应用（归一问题）',
                      '一般复合应用题其三：乘加混合应用', '一般复合应用题其四：乘减混合应用',
                      '一般复合应用题其五：稍复杂的复合应用题', '积的规律与实际问题',
                      '经济问题其一：基础认识', '经济问题其二：基础应用',
                      '经济问题其三：进阶应用', '经济问题其四：促销与盈亏',
                      '经济问题其五：促销与“买几送几”', '行程问题', '倍数问题']),
        ('用估算解决问题', ['估算', '乘法基础应用其三：估算解决实际问题']),
    ]),
    ('加法模型和乘法模型', '教材单元内无分节（窗O实翻确认），考点直挂', [
        (None, ['加法数量关系模型', '乘法模型——价格问题', '乘法模型——行程问题',
                '加法与乘法模型的综合应用']),
    ]),
    ('平行四边形和梯形', None, [
        ('平行和垂直', ['平行与垂直', '数平行线与垂线',
                        '平行与垂直作图其一：作平行线与垂线',
                        '平行与垂直作图其二：垂线与最佳路线问题',
                        '平行与垂直作图其三：画指定长、宽（边长）的长方形或正方形',
                        '在平行线之间画最大的正方形']),
        ('平行四边形和梯形', ['平行四边形和梯形的认识', '平行四边形的性质',
                              '梯形的分类：等腰梯形和直角梯形', '作平行四边形和梯形的高',
                              '画平行四边形和梯形', '裁剪平行四边形和梯形',
                              '数平行四边形和梯形', '平行四边形的周长及反求问题',
                              '平行四边形的拉伸问题', '梯形的周长及反求问题',
                              '梯形的拼接问题', '梯形底边的变化问题']),
    ]),
    ('条形统计图', None, [
        ('单式条形统计图', ['一格表示一个单位的单式条形统计图',
                            '一格表示多个单位的单式条形统计图', '绘制和表示条形统计图',
                            '统计表和条形统计图综合应用']),
        ('复式条形统计图', ['认识复式条形统计图', '绘制复式条形统计图', '统计图表综合应用']),
    ]),
    ('寻找宝藏', '综合与实践', [
        (None, ['东南、西南、东北、西北方向的初步认识',
                '根据平面图直接分析物体所在位置-东南、西南、东北、西北方向',
                '根据平面图分析路线-东南、西南、东北、西北方向',
                '根据平面图作图要求把物体写在相应位置-东南、西南、东北、西北方向',
                '几点钟方向的认识与直接判断', '根据平面图直接判断物体在几点钟方向',
                '根据平面图直接判断物体在几点钟方向并在图中相应位置标出物体',
                '较复杂平面图的作图题-几点钟方向']),
    ]),
    ('复习与关联', '第七单元（整理复习）', [
        ('数学广角：鸡兔同笼', ['解鸡兔同笼问题常用的两种方法', '鸡兔同笼问题基本题型其一',
                                '鸡兔同笼问题基本题型其二',
                                '鸡兔同笼问题变式题型其一：车辆问题',
                                '鸡兔同笼问题变式题型其二：得分问题',
                                '鸡兔同笼问题变式题型其三：运输问题',
                                '鸡兔同笼问题变式题型其四：雨天晴天问题',
                                '鸡兔同笼问题变式题型其五：租车租船问题',
                                '鸡兔同笼问题变式题型其六：多种动物问题',
                                '鸡兔同笼问题变式题型其七：百僧分馍问题']),
    ]),
]
# 小节 note 特例（教材出处）
SEC_NOTE = {'用估算解决问题': '教材无节banner，源=单元知识结构图三分枝(p55)',
            '数学广角：鸡兔同笼': '教材p118 ＊选学栏目'}
# 名缺陷改判留痕（沿窗N）：本考点带低置信改名 note+老区名别名
RENAMED_ALIAS = {'统计图表综合应用': '统计图表综合应'}


def build_rows():
    """→ [(id, name, parent, level, ord, note)]，考点低置信前缀 '*' 在此消化。"""
    rows = [(ROOT_ID, ROOT_NAME, None, '版本', 2,
             '小学不分教材版本（2026-08-21 用户口径）｜' + NOTE),
            (TERM_ID, TERM_NAME, ROOT_ID, '年级学期', 1, NOTE)]
    for ui, (uname, unote, secs) in enumerate(SPEC, 1):
        uid = f'{TERM_ID}{ui:03d}'
        rows.append((uid, uname, TERM_ID, '单元', ui,
                     (unote + '｜' + NOTE) if unote else NOTE))
        si = 0
        direct = 0
        for sname, kps in secs:
            if sname is None:
                parent = uid
            else:
                si += 1
                parent = f'{uid}{si:03d}'
                snote = SEC_NOTE.get(sname)
                rows.append((parent, sname, uid, '小节', si,
                             (snote + '｜' + NOTE) if snote else NOTE))
            for kname in kps:
                low = kname.startswith('*')
                kname = kname.lstrip('*')
                if sname is None:
                    direct += 1
                    ki = direct
                else:
                    ki = kps.index('*' + kname if low else kname) + 1
                note = NOTE
                if low:
                    note = LOW + '｜' + NOTE
                if kname in RENAMED_ALIAS:
                    note = ('🔴低置信改名:原账名「%s」疑截断｜' % RENAMED_ALIAS[kname]) + note
                rows.append((f'{parent}{ki:03d}', kname, parent, '考点', ki, note))
    return rows


def branch_ids(conn):
    return [r[0] for r in conn.execute(
        "WITH RECURSIVE br(id) AS (SELECT id FROM kp WHERE id=? "
        "UNION ALL SELECT k.id FROM kp k JOIN br ON k.parent_id=br.id) "
        "SELECT id FROM br", (ROOT_ID,))]


def hash_rows(conn, exclude):
    h = hashlib.sha256()
    for row in conn.execute(
            'SELECT id,name,parent_id,level,ord,status FROM kp ORDER BY id'):
        if row[0] not in exclude:
            h.update(repr(tuple(row)).encode('utf-8'))
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='小学枝四上·教材同步结构重铺（窗O）')
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--db')
    a = ap.parse_args()

    rows = build_rows()
    stat = {}
    for _, _, _, level, _, _ in rows:
        stat[level] = stat.get(level, 0) + 1
    print('教材同步计划：', '，'.join(f'{k}{v}' for k, v in stat.items()),
          f'＝{len(rows)} 节点')

    if a.plan or not a.apply:
        for rid, name, parent, level, order, note in rows:
            pad = {'版本': '', '年级学期': ' ', '单元': '  ', '小节': '    ',
                   '考点': '      '}[level]
            flag = ' 🔴' + note.split('｜')[0] if note.split('｜')[0].startswith('🔴') else ''
            print(f'{pad}[{rid}] {name}{flag}')
        return

    assert a.db, '--apply 必须显式给 --db'
    conn = sqlite3.connect(a.db)
    try:
        old = branch_ids(conn)
        # 🔴 删枝前置闸：小学枝必须零引用（挂载/别名以外的账面引用一律拦）
        if old:
            ph = ','.join('?' * len(old))
            n_qkp = conn.execute(
                f'SELECT COUNT(*) FROM question_kp WHERE kp_id IN ({ph})', old).fetchone()[0]
            assert n_qkp == 0, f'🔴 小学枝挂着 {n_qkp} 条题挂载，不许推倒重铺'
            n_art = conn.execute(
                "SELECT COUNT(*) FROM artifact WHERE kp_ids_json LIKE '%\"400%'").fetchone()[0]
            assert n_art == 0, f'🔴 有 {n_art} 个 artifact 的 kp_ids_json 指着小学枝'
        pre = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
               for t in ('kp', 'question', 'question_kp')}
        pre_hash = hash_rows(conn, set(old))

        new_ids = {r[0] for r in rows}
        ins = skip = 0
        with conn:
            # 🔴 整枝全删再全插（不保 id 原位）：同 id 换名时 UPDATE 会与尚未更新的
            # 兄弟行撞 UNIQUE(parent_id,name)——旧枝零引用已过闸，全删是安全且唯一干净的路。
            if old:
                ph = ','.join('?' * len(old))
                conn.execute(f'DELETE FROM kp_alias WHERE kp_id IN ({ph})', old)
                conn.execute(f'DELETE FROM kp WHERE id IN ({ph})', old)
            for rid, name, parent, level, order, note in rows:
                conn.execute('INSERT INTO kp(id,name,parent_id,level,ord,status,note) '
                             "VALUES(?,?,?,?,?,'现行',?)",
                             (rid, name, parent, level, order, note))
                ins += 1
            for kname, alias in RENAMED_ALIAS.items():
                kp_id = conn.execute('SELECT id FROM kp WHERE name=? AND id LIKE ?',
                                     (kname, TERM_ID + '%')).fetchone()[0]
                conn.execute('INSERT OR IGNORE INTO kp_alias(kp_id,alias,alias_kind) '
                             "VALUES(?,?,'老区名')", (kp_id, alias))

        post = {t: conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                for t in ('kp', 'question', 'question_kp')}
        assert hash_rows(conn, new_ids | set(old)) == pre_hash, '🔴 守恒闸炸：非小学枝 kp 行被改动'
        for t in ('question', 'question_kp'):
            assert post[t] == pre[t], f'🔴 守恒闸炸：{t} 行数变了'
        print(f"✅ 重铺完成：旧枝清 {len(old)} → 新枝 {len(rows)}（写 {ins}/幂等跳过 {skip}）；"
              f"kp {pre['kp']}→{post['kp']}；question/question_kp 零触碰"
              f"（{post['question']}/{post['question_kp']}）")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
