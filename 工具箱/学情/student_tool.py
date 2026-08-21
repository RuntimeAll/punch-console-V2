# -*- coding: utf-8 -*-
"""学员档案与轨工具（grading.db · student/track）——备课与出题的个性化依据入口
==============================================================================
定位：学员正本的唯一写入口。备课线（一对一）与订阅特训线（群打卡）**同一张 student 表**
——学员就是学员，不因来源分家；学情肖像统一落 `student.profile_json`。

🔴 纪律：
  - grading.db 单写者，动它先在 记录/开发注册.md 排写窗口；
  - 肖像 profile_json 是**结构化**的（见 §肖像契约），不是自由文本袋——备课 skill 与出题
    要按键取用，键名漂移=静默失效；
  - 学情随课更新走 `profile-patch`（合并式，不覆盖历史弱点清单），别手改库。

肖像契约（profile_json）：
    {
      "画像":     "一句话说清这是个什么学生",
      "课堂规格": {"时长": "90分钟", "范式": "思维10ʹ→专项40ʹ→同步30ʹ→总结10ʹ", "注意力": "..."},
      "学情基线": {"日期": "2026-08-14", "定于": "用户拍板/摸底",
                   "已通关": [...], "薄弱": [...], "盲区": [...]},
      "弱点清单": [{"点": "...", "出处": "第10课热身再练", "日期": "2026-08-09", "状态": "在练"}],
      "口味与禁忌": [...],
      "料源":     [...],
      "备课铁律": [...]
    }

用法：
    python 工具箱/学情/student_tool.py add   --code 苏俊宇 --grade 四年级 ... --profile <json文件>
    python 工具箱/学情/student_tool.py track-add --student 苏俊宇 --name "..." --kp-scope <json文件|->
    python 工具箱/学情/student_tool.py profile-patch --code 好好 --patch <json文件>
    python 工具箱/学情/student_tool.py show  [--code 苏俊宇]     # 学员 360（现算）
"""
import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / '批改产线' / 'grading.db'
KB = ROOT / '知识库' / 'kb.db'
PROFILE_KEYS = ('画像', '课堂规格', '学情基线', '弱点清单', '口味与禁忌', '料源', '备课铁律')


def load_json(p):
    if p == '-':
        return json.load(sys.stdin)
    return json.loads(Path(p).read_text(encoding='utf-8'))


def check_profile(prof):
    """肖像闸：键名必须在契约内（防漂移），画像必填。"""
    if not isinstance(prof, dict):
        sys.exit('🔴 profile 必须是 JSON 对象')
    bad = [k for k in prof if k not in PROFILE_KEYS]
    if bad:
        sys.exit('🔴 肖像键不在契约内：%s——契约键=%s（要加键先改 student_tool 契约，'
                 '别让备课 skill 取不到）' % (bad, list(PROFILE_KEYS)))
    if not prof.get('画像'):
        sys.exit('🔴 「画像」必填：一句话说清这是个什么学生，备课 skill 开工第一眼看它')


def check_kp_scope(ids):
    """考点闸：轨的考点集必须是 kb.db 里现行的本体层节点（空集允许但要显式声明）。"""
    if not ids:
        return 0, ['（空集：本轨考点范围在 v2 KG 里尚无对应枝，已如实留空）']
    conn = sqlite3.connect('file:%s?mode=ro' % KB.as_posix(), uri=True)
    ok, bad = 0, []
    for kid in ids:
        row = conn.execute("SELECT name, level, status FROM kp WHERE id=?", (kid,)).fetchone()
        if row is None:
            bad.append('%s 不存在' % kid)
        elif row[2] != '现行':
            bad.append('%s(%s) 非现行' % (kid, row[0]))
        elif row[1] not in ('考点', '题型'):
            bad.append('%s(%s) 是%s层，考点集只收本体层' % (kid, row[0], row[1]))
        else:
            ok += 1
    conn.close()
    if bad:
        sys.exit('🔴 考点集不过闸：\n  ' + '\n  '.join(bad))
    return ok, []


def cmd_add(a):
    prof = load_json(a.profile) if a.profile else {}
    check_profile(prof)
    conn = sqlite3.connect(DB)
    with conn:
        conn.execute(
            'INSERT INTO student(code,grade,textbook_ver,status,service_tier,joined_at,'
            'profile_json,note,created_at) VALUES(?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(code) DO UPDATE SET grade=excluded.grade,'
            'textbook_ver=excluded.textbook_ver,status=excluded.status,'
            'service_tier=excluded.service_tier,joined_at=excluded.joined_at,'
            'profile_json=excluded.profile_json,note=excluded.note',
            (a.code, a.grade, a.textbook_ver, a.status, a.service_tier, a.joined_at,
             json.dumps(prof, ensure_ascii=False), a.note, date.today().isoformat()))
    print('✅ 学员落档：%s（%s / %s / %s）肖像 %d 键'
          % (a.code, a.grade, a.status, a.service_tier, len(prof)))
    conn.close()


def cmd_track_add(a):
    ids = load_json(a.kp_scope) if a.kp_scope else []
    n_ok, notes = check_kp_scope(ids)
    conn = sqlite3.connect(DB)
    if conn.execute('SELECT 1 FROM student WHERE code=?', (a.student,)).fetchone() is None:
        sys.exit('🔴 学员 %s 不在档，先 add' % a.student)
    with conn:
        cur = conn.execute(
            'INSERT INTO track(student,name,round,book_ref,kp_scope_json,status,started_at) '
            'VALUES(?,?,?,?,?,?,?) ON CONFLICT(student,name,round) DO UPDATE SET '
            'book_ref=excluded.book_ref,kp_scope_json=excluded.kp_scope_json,'
            'status=excluded.status',
            (a.student, a.name, a.round, a.book_ref,
             json.dumps(ids, ensure_ascii=False), a.status, a.started_at))
    print('✅ 开轨：%s · %s（第%d轮）考点集 %d 个过闸 %s'
          % (a.student, a.name, a.round, n_ok, notes[0] if notes else ''))
    conn.close()


def cmd_profile_patch(a):
    patch = load_json(a.patch)
    check_profile(patch)
    conn = sqlite3.connect(DB)
    row = conn.execute('SELECT profile_json FROM student WHERE code=?', (a.code,)).fetchone()
    if row is None:
        sys.exit('🔴 学员 %s 不在档' % a.code)
    prof = json.loads(row[0] or '{}')
    for k, v in patch.items():
        # 🔴 弱点清单是**追加**不是覆盖（学情是流水，抹掉历史=丢诊断依据）
        if k == '弱点清单' and isinstance(v, list):
            prof.setdefault(k, []).extend(v)
        else:
            prof[k] = v
    with conn:
        conn.execute('UPDATE student SET profile_json=? WHERE code=?',
                     (json.dumps(prof, ensure_ascii=False), a.code))
    print('✅ 肖像更新：%s ← %s（弱点清单现 %d 条）'
          % (a.code, list(patch), len(prof.get('弱点清单', []))))
    conn.close()


def cmd_show(a):
    conn = sqlite3.connect('file:%s?mode=ro' % DB.as_posix(), uri=True)
    conn.row_factory = sqlite3.Row
    where, args = ('WHERE code=?', (a.code,)) if a.code else ('', ())
    for s in conn.execute(f'SELECT * FROM student {where} ORDER BY code', args):
        print('=' * 76)
        print('【%s】%s · %s · %s · %s（入营 %s）'
              % (s['code'], s['grade'], s['textbook_ver'], s['status'],
                 s['service_tier'], s['joined_at']))
        prof = json.loads(s['profile_json'] or '{}')
        if prof.get('画像'):
            print('  画像：', prof['画像'])
        base = prof.get('学情基线') or {}
        if base:
            print('  学情基线（%s · %s）：' % (base.get('日期', '?'), base.get('定于', '?')))
            for k in ('已通关', '薄弱', '盲区'):
                if base.get(k):
                    print('    %s：%s' % (k, '｜'.join(base[k])))
        for w in prof.get('弱点清单', []):
            print('  弱点· %s（%s，%s）%s' % (w.get('点'), w.get('出处'), w.get('日期'),
                                             w.get('状态', '')))
        for t in conn.execute('SELECT * FROM track WHERE student=? ORDER BY id', (s['code'],)):
            ids = json.loads(t['kp_scope_json'] or '[]')
            print('  轨· %s（第%d轮·%s）考点集 %d 个｜册=%s'
                  % (t['name'], t['round'], t['status'], len(ids), t['book_ref'] or '—'))
        n = conn.execute('SELECT COUNT(*) FROM batch b JOIN track t ON b.track_id=t.id '
                         'WHERE t.student=?', (s['code'],)).fetchone()[0]
        print('  批次：%d 份（批改流水）' % n)
    conn.close()


def main():
    ap = argparse.ArgumentParser(description='学员档案与轨（grading.db）')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add', help='学员落档（幂等 upsert）')
    p.add_argument('--code', required=True)
    p.add_argument('--grade')
    p.add_argument('--textbook-ver', dest='textbook_ver')
    p.add_argument('--status', default='在读',
                   choices=['试听', '在读', '暂停', '结课'])
    p.add_argument('--service-tier', dest='service_tier')
    p.add_argument('--joined-at', dest='joined_at')
    p.add_argument('--profile')
    p.add_argument('--note')
    p.set_defaults(func=cmd_add)

    p = sub.add_parser('track-add', help='开轨（学员×专项一次征程）')
    p.add_argument('--student', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--round', type=int, default=1)
    p.add_argument('--book-ref', dest='book_ref')
    p.add_argument('--kp-scope', dest='kp_scope')
    p.add_argument('--status', default='进行中', choices=['进行中', '已完结', '暂停'])
    p.add_argument('--started-at', dest='started_at')
    p.set_defaults(func=cmd_track_add)

    p = sub.add_parser('profile-patch', help='肖像增量更新（弱点清单追加不覆盖）')
    p.add_argument('--code', required=True)
    p.add_argument('--patch', required=True)
    p.set_defaults(func=cmd_profile_patch)

    p = sub.add_parser('show', help='学员 360（现算）')
    p.add_argument('--code')
    p.set_defaults(func=cmd_show)

    a = ap.parse_args()
    a.func(a)


if __name__ == '__main__':
    main()
