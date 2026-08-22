# -*- coding: utf-8 -*-
"""资料挂账工具（PRD-002 交付件 #8 底座）——artifact / template 两表的唯一写入通路。

用途：产线出货一条命令挂账（D-7 资料一本账）；渲染模版登记（D-11 模版库）。
页面只展示，写动作全在这里；每次执行落 skill_log。

用法：
  python artifact_tool.py add --name 浙教七上有理数·5天打卡 --kind 打卡册 \
      --file 产物/打卡/浙教七上有理数5天/题目卷.pdf --file 产物/打卡/.../答案卷.pdf \
      --kp 有理数混合运算 --kp 与绝对值有关的计算 --source-line 每日打卡 \
      [--template daily_v1] [--note '{"小红书标题":"…","宣发描述":"…"}']
  python artifact_tool.py files --id A2026… --file 产物/打卡/…/题目卷.pdf --file 产物/打卡/…/答案卷.pdf
      # 🔴 库中心口径：组卷 paper_tool assemble 先建 artifact 壳，PDF 后渲——出货时用本命令补挂真文件
  python artifact_tool.py status --id A2026… --to 已交付
  python artifact_tool.py link --id A2026… --url "https://pan.baidu.com/s/xxx?pwd=ab12"
  python artifact_tool.py note --id A2026… --json 宣发字段.json    # 宣发字段整包回填 note
  python artifact_tool.py list
  python artifact_tool.py template-add --id daily_v1 --name 每日一练定版 \
      --purpose 打卡册一天一页 --book-kinds 打卡册 --params '{"layout":"daily_v1"}' [--pitfalls …]
  python artifact_tool.py template-list
"""
import argparse
import json
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '库'))
from gates import assert_mounted_kp, LeafKpError  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / '知识库' / 'kb.db'


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def open_db(path):
    import sqlite3
    p = Path(path)
    if not p.exists():
        sys.exit(f'🔴 库不存在：{p}')
    conn = sqlite3.connect(str(p))
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def log_skill(conn, action, digest, result, detail, t0):
    conn.execute(
        'INSERT INTO skill_log(skill,action,args_digest,result,detail,duration_ms,created_at) VALUES (?,?,?,?,?,?,?)',
        ('资料挂账', action, str(digest)[:200], result, str(detail)[:500],
         int((time.time() - t0) * 1000), now()))
    conn.commit()


def resolve_kp_words(conn, words):
    """册的 kp_ids_json ＝**覆盖范围指针**，不是题挂载（2026-08-21 窗M 改口径）：
    走存量挂载闸 assert_mounted_kp（现行+本体层即可，考点/题型都收、不要求枝末端）——
    「必须末端」是题挂载防学情分母失真的闸，册级覆盖挂已细分的考点天经地义
    （一册盖整片考点含其全部题型）。同款先例＝model_tool 的 allow_node。"""
    ids = []
    for w in words or []:
        w = str(w)
        if re.fullmatch(r'\d{6,15}', w):
            assert_mounted_kp(conn, w)
            ids.append(w)
            continue
        hits = [r[0] for r in conn.execute('SELECT id FROM kp WHERE name=?', (w,))]
        if not hits:
            hits = [r[0] for r in conn.execute('SELECT kp_id FROM kp_alias WHERE alias=?', (w,))]
        ok = []
        for h in dict.fromkeys(hits):
            try:
                assert_mounted_kp(conn, h)
                ok.append(h)
            except LeafKpError:
                pass
        if len(ok) != 1:
            sys.exit(f'🔴 考点 {w!r} resolve 命中现行本体节点 {len(ok)} 个（要恰一）：{ok}')
        ids.append(ok[0])
    return list(dict.fromkeys(ids))


def check_rel_file(f):
    p = Path(f)
    if p.is_absolute():
        sys.exit(f'🔴 文件指针必须相对 v2 根（老货架 717 行绝对路径全断）：{f}')
    if not (ROOT / p).exists():
        sys.exit(f'🔴 成品件不存在：{f}——挂账挂的是真出的货，不是意向')
    return str(p).replace('\\', '/')


_BAD_NAME = re.compile(r'[\\/:*?"<>|\r\n]+')


def store_files(files, aid, name):
    """🔴 挂账即归库（窗U 用户归一令「所有成品只走一个文件夹」）：
    指针不在 `成品库/` 下的成品件，拷入 `成品库/<aid>·<人话名>/` 后换新指针。
    渲染链出件位置照旧自由（产物/ 是工艺区）——**挂账是唯一归库动作**；
    末尾断言兜底：写库的指针必须全部以 成品库/ 开头，绝不放行库外成品。"""
    dirname = f'{aid}·{_BAD_NAME.sub("·", (name or "").strip())[:60] or "未命名"}'
    out, seen = [], {}
    for f in files:
        if f.startswith('成品库/'):
            out.append(f)
            continue
        base = f.rsplit('/', 1)[-1]
        if base in seen:
            seen[base] += 1
            stem, dot, ext = base.rpartition('.')
            base = f'{stem}·{seen[base]}.{ext}' if dot else f'{base}·{seen[base]}'
        else:
            seen[base] = 1
        new = f'成品库/{dirname}/{base}'
        dst = ROOT / new
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, dst)
        out.append(new)
    assert all(x.startswith('成品库/') for x in out), '🔴 归库闸炸：仍有库外指针'
    if out != files:
        print(f'  📦 挂账即归库：{sum(1 for a, b in zip(files, out) if a != b)} 件拷入 成品库/{dirname}/')
    return out


def cmd_add(conn, args):
    files = [check_rel_file(f) for f in (args.file or [])]
    if not files:
        sys.exit('🔴 至少挂一个成品件（--file 相对路径）')
    kp_ids = resolve_kp_words(conn, args.kp)
    if args.template:
        if not conn.execute('SELECT 1 FROM template WHERE id=?', (args.template,)).fetchone():
            sys.exit(f'🔴 template {args.template} 未登记（先 template-add）')
    aid = args.id or 'A' + datetime.now().strftime('%Y%m%d') + uuid.uuid4().hex[:6]
    files = store_files(files, aid, args.name)          # 🔴 挂账即归库（窗U）
    note = args.note
    if note:
        json.loads(note)                      # 验 JSON（宣发字段包）
    subkind = getattr(args, 'subkind', None) or '组卷册'   # 细类（§2.6d）：组卷册/发布包/历史册，DDL CHECK 兜底
    conn.execute(
        'INSERT INTO artifact(id,name,kind,status,files_json,source_line,template_id,'
        'kp_ids_json,link,note,created_at,细类) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
        (aid, args.name, args.kind, '在产', json.dumps(files, ensure_ascii=False),
         args.source_line, args.template,
         json.dumps(kp_ids, ensure_ascii=False) if kp_ids else None,
         args.link, note, now(), subkind))
    conn.commit()
    print(f'挂账：{aid} {args.name}（{args.kind}，{len(files)} 件，考点 {kp_ids}）')
    return aid, f'{args.name} files={len(files)}'


def _need(conn, aid):
    row = conn.execute('SELECT id,name,status FROM artifact WHERE id=?', (aid,)).fetchone()
    if not row:
        sys.exit(f'🔴 artifact {aid} 不存在')
    return row


def cmd_files(conn, args):
    """成品件回填（🔴 库中心口径的必需件：组卷 paper_tool assemble 先建 artifact 壳，
    PDF 是后来才渲出来的——壳要能在出货时补挂真文件）。整包替换，不做增量。"""
    row = _need(conn, args.id)
    files = [check_rel_file(f) for f in (args.file or [])]
    if not files:
        sys.exit('🔴 至少挂一个成品件（--file 相对路径）')
    files = store_files(files, args.id, row[1])         # 🔴 挂账即归库（窗U）
    conn.execute('UPDATE artifact SET files_json=? WHERE id=?',
                 (json.dumps(files, ensure_ascii=False), args.id))
    conn.commit()
    print(f'{args.id} {row[1]} 成品件回填 {len(files)} 件：' + ' '.join(files))
    return args.id, f'files={len(files)}'


def cmd_status(conn, args):
    _need(conn, args.id)
    if args.to not in ('在产', '已交付', '已上架', '退役'):
        sys.exit(f'🔴 状态 {args.to!r} 非法')
    # 退役=账面下线不物理删（PRD-008 §一③ 清理口径）：不补 delivered_at（没交付过的孤儿不许伪造交付时间）
    conn.execute('UPDATE artifact SET status=?, delivered_at=COALESCE(delivered_at, ?) WHERE id=?',
                 (args.to, now() if args.to in ('已交付', '已上架') else None, args.id))
    conn.commit()
    print(f'{args.id} → {args.to}')
    return args.id, args.to


def cmd_link(conn, args):
    _need(conn, args.id)
    if 'pwd=' not in args.url:
        print('⚠️ 链接不带 ?pwd= 提取码——对方要手敲码，多一步就多一批人流失（口径：链接自带）')
    conn.execute('UPDATE artifact SET link=? WHERE id=?', (args.url, args.id))
    conn.commit()
    print(f'{args.id} 链接回填')
    return args.id, 'link'


def cmd_note(conn, args):
    _need(conn, args.id)
    payload = Path(args.json).read_text(encoding='utf-8')
    json.loads(payload)
    conn.execute('UPDATE artifact SET note=? WHERE id=?', (payload, args.id))
    conn.commit()
    print(f'{args.id} 宣发字段回填（{len(payload)} 字符）')
    return args.id, 'note'


def cmd_list(conn, args):
    rows = conn.execute(
        'SELECT id,name,kind,status,link IS NOT NULL,created_at FROM artifact ORDER BY created_at').fetchall()
    for r in rows:
        print(f'{r[0]}\t{r[2]}\t{r[3]}\t{"有链" if r[4] else "无链"}\t{r[1]}')
    print(f'—— artifact 共 {len(rows)} 条')
    return 'list', f'{len(rows)}条'


def cmd_template_add(conn, args):
    if conn.execute('SELECT 1 FROM template WHERE id=?', (args.id,)).fetchone():
        conn.execute(
            'UPDATE template SET name=?,purpose=?,book_kinds=?,params_json=?,pitfalls=?,'
            'version=?,status=?,updated_at=? WHERE id=?',
            (args.name, args.purpose, args.book_kinds, args.params, args.pitfalls,
             args.version, '在用', now(), args.id))
        act = '更新'
    else:
        conn.execute(
            'INSERT INTO template(id,name,purpose,book_kinds,params_json,pitfalls,version,'
            'status,registered_by,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (args.id, args.name, args.purpose, args.book_kinds, args.params, args.pitfalls,
             args.version, '在用', 'agent', now()))
        act = '登记'
    if args.params:
        json.loads(args.params)
    conn.commit()
    print(f'template {act}：{args.id} {args.name}')
    return args.id, act


def cmd_template_list(conn, args):
    rows = conn.execute('SELECT id,name,purpose,status FROM template ORDER BY id').fetchall()
    for r in rows:
        print('\t'.join(str(x) for x in r))
    print(f'—— template 共 {len(rows)} 条')
    return 'template-list', f'{len(rows)}条'


def main():
    ap = argparse.ArgumentParser(description='artifact/template 挂账原语')
    ap.add_argument('--db', default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('add')
    s.add_argument('--name', required=True)
    s.add_argument('--kind', required=True,
                   choices=['打卡册', '专项卷', '举一反三', '讲义', '报告模版', '其他'])
    s.add_argument('--file', action='append'); s.add_argument('--kp', action='append')
    s.add_argument('--source-line', dest='source_line'); s.add_argument('--template')
    s.add_argument('--link'); s.add_argument('--note'); s.add_argument('--id')
    s.add_argument('--subkind', choices=['组卷册', '发布包', '历史册'])   # 细类（§2.6d），缺省 组卷册
    s = sub.add_parser('files'); s.add_argument('--id', required=True); s.add_argument('--file', action='append')
    s = sub.add_parser('status'); s.add_argument('--id', required=True); s.add_argument('--to', required=True)
    s = sub.add_parser('link'); s.add_argument('--id', required=True); s.add_argument('--url', required=True)
    s = sub.add_parser('note'); s.add_argument('--id', required=True); s.add_argument('--json', required=True)
    s = sub.add_parser('list')
    s = sub.add_parser('template-add')
    s.add_argument('--id', required=True); s.add_argument('--name', required=True)
    s.add_argument('--purpose'); s.add_argument('--book-kinds', dest='book_kinds')
    s.add_argument('--params'); s.add_argument('--pitfalls'); s.add_argument('--version', default='v1')
    s = sub.add_parser('template-list')
    args = ap.parse_args()

    t0 = time.time()
    conn = open_db(args.db)
    try:
        fn = {'add': cmd_add, 'files': cmd_files, 'status': cmd_status, 'link': cmd_link,
              'note': cmd_note, 'list': cmd_list,
              'template-add': cmd_template_add, 'template-list': cmd_template_list}[args.cmd]
        digest, detail = fn(conn, args)
        log_skill(conn, args.cmd, digest, '成功', detail, t0)
    except (SystemExit, LeafKpError) as e:
        msg = str(e)
        if msg and msg not in ('0',):
            print(msg, file=sys.stderr)
            try:
                log_skill(conn, args.cmd, str(vars(args))[:200], '失败', msg, t0)
            except Exception:
                pass
        conn.close()
        sys.exit(1)
    conn.close()


if __name__ == '__main__':
    main()
