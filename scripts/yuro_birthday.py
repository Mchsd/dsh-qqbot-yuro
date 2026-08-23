#!/usr/bin/env python3
"""Yuro/Yume 生日祝福系统 — 每日检查 birthdays.md，生日当天写 announce.json 群内祝福（2026-08-21）。

用法:
  python yuro_birthday.py [--bot yuro|yume] check    # 检查今天生日（命中→announce 祝福+stdout；未命中静默）
  python yuro_birthday.py [--bot yuro|yume] list     # 列出全部已登记生日

数据: work-qq-group/birthdays.md（斜杠指令 /生日 写入）
格式: - 群友名 | openid | 月-日 | 备注
cron: 每日 9:00（wrapper yuro_birthday_check.py 写死 --bot）
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import yuro_layers

WORK = Path(yuro_layers.work_dir())
BIRTHDAYS = WORK / 'birthdays.md'
ANNOUNCE = WORK / 'announce.json'
BOT = yuro_layers.bot_name()


def load_birthdays() -> list[dict]:
    try:
        lines = BIRTHDAYS.read_text(encoding='utf-8').splitlines()
    except Exception:
        return []
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln.startswith('#'):
            continue
        p = [x.strip() for x in ln.lstrip('- ').split('|')]
        if len(p) >= 3:
            out.append({'name': p[0], 'openid': p[1], 'date': p[2], 'note': p[3] if len(p) > 3 else ''})
    return out


def announce(text: str) -> None:
    ANNOUNCE.write_text(json.dumps({'text': text}, ensure_ascii=False), encoding='utf-8')


def cmd_check() -> None:
    now = datetime.now()
    today = f'{now.month}-{now.day}'
    hit = [b for b in load_birthdays() if b['date'] == today]
    if not hit:
        return  # 无生日: 静默
    emoji = '🌙' if BOT == 'Yume' else '🐳'
    lines = [f'{emoji} 今天是大日子！！']
    for b in hit:
        lines.append(f'🎂 {b["name"]} 生日快乐呀！！（{b["date"]}，{b["note"] or "公历"}）')
    lines.append(f'{BOT} 来给大家道喜啦～🎉')
    announce('\n'.join(lines))
    print('\n'.join(lines))  # stdout 供 cron 日志（deliver=local 不重复投递）


def cmd_list() -> None:
    bd = load_birthdays()
    if not bd:
        print('（暂无登记）')
        return
    for b in sorted(bd, key=lambda x: x['date']):
        print(f'{b["name"]} | {b["date"]} | {b["note"]}')


if __name__ == '__main__':
    # [2026-08-21 分层] mode 解析：消费 --bot <name> 配对参数（值不能残留）
    _raw = sys.argv[1:]
    args = []
    _i = 0
    while _i < len(_raw):
        if _raw[_i] == '--bot' and _i + 1 < len(_raw):
            _i += 2
            continue
        args.append(_raw[_i])
        _i += 1
    mode = args[0] if args else 'check'
    if mode == 'check':
        cmd_check()
    elif mode == 'list':
        cmd_list()
    else:
        print(__doc__)
