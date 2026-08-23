#!/usr/bin/env python3
"""群级临时睡眠（2026-08-22）: 主人 /睡觉 /起床 — 只影响单个群, 不碰精力/预算SLEEP_FLAG/全局作息表。
用法: python yuro_group_sleep.py [--bot yuro|yume] sleep <group> | wake <group> | check <group>
状态: {cwd}/group_sleep_state.json {group_openid: {until: iso}}; until = 下次 07:30（临时性: 睡到天亮自动恢复,
check 时过期自动清除; 主人随时 /起床 提前叫醒）
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yuro_layers

STATE = Path(yuro_layers.work_dir()) / 'group_sleep_state.json'


def load():
    try:
        return json.loads(STATE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')


def next_wake():
    n = datetime.now()
    target = n.replace(hour=7, minute=30, second=0, microsecond=0)
    if n >= target:
        target += timedelta(days=1)
    return target


def op_sleep(group):
    st = load()
    until = next_wake()
    st[group] = {'until': until.isoformat()}
    save(st)
    print(f'🌙 该群临时睡眠（{until.strftime("%H:%M")} 自动恢复; 主人 /起床 可提前叫醒）')


def op_wake(group):
    st = load()
    st.pop(group, None)
    save(st)
    print('🌅 该群已醒来')


def op_check(group):
    """0=睡(输出 until) / 1=醒（过期自动清除）"""
    st = load()
    item = st.get(group)
    if not item:
        sys.exit(1)
    try:
        until = datetime.fromisoformat(item['until'])
    except Exception:
        st.pop(group, None)
        save(st)
        sys.exit(1)
    if datetime.now() >= until:
        st.pop(group, None)
        save(st)
        sys.exit(1)
    print(f'sleeping until {until.strftime("%H:%M")}')
    sys.exit(0)


if __name__ == '__main__':
    # [2026-08-21 分层] mode 解析：消费 --bot <name> 配对参数（值不能残留）
    raw = sys.argv[1:]
    args = []
    i = 0
    while i < len(raw):
        if raw[i] == '--bot' and i + 1 < len(raw):
            i += 2
            continue
        args.append(raw[i])
        i += 1
    mode = args[0] if args else 'check'
    group = args[1] if len(args) > 1 else ''
    if mode == 'sleep':
        op_sleep(group)
    elif mode == 'wake':
        op_wake(group)
    elif mode == 'check':
        op_check(group)
    else:
        print(__doc__)
