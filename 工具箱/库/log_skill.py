# -*- coding: utf-8 -*-
"""skill 账单记账器（D-15）——skill 级动作的 skill_log 落账入口。

工具（kg_tool/ingest_flow/model_tool/artifact_tool）每次执行已自动落账；
本脚本给 skill 编排层用：一次 skill 执行收尾时记一笔总账。

用法：
  python 工具箱/库/log_skill.py 每日打卡 初稿样张 成功 "浙教七上有理数 D1 样张双PDF已出"
  python 工具箱/库/log_skill.py 举一反三 变体生成 失败 "实算闸 2 题未过，退回改参"
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / '知识库' / 'kb.db'


def main():
    if len(sys.argv) < 4 or sys.argv[3] not in ('成功', '失败'):
        sys.exit('用法：python log_skill.py <skill> <action> <成功|失败> [detail]')
    skill, action, result = sys.argv[1], sys.argv[2], sys.argv[3]
    detail = sys.argv[4] if len(sys.argv) > 4 else None
    conn = sqlite3.connect(str(DB))
    conn.execute(
        'INSERT INTO skill_log(skill,action,args_digest,result,detail,created_at) VALUES (?,?,?,?,?,?)',
        (skill, action, None, result, detail, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    print(f'skill_log：{skill}/{action} {result}')


if __name__ == '__main__':
    main()
