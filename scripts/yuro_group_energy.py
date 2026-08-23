#!/usr/bin/env python3
"""群级精力（2026-08-22）: 群睡眠机制 × 精力系统联动。
用法: python yuro_group_energy.py [--bot yuro|yume] status <group>   # stdout = 精力百分比整数(0-100), exit 0
      python yuro_group_energy.py [--bot yuro|yume] explain <group>   # 多行明细(主人 /状态 用)
规则（2026-08-22）:
- 群清醒 + 作息清醒 → 100%（正常）
- 群睡 OR 作息睡(sleep/winding) → 15%（低精力 → 回答频率降低，冷却×4）
- 群睡且距 07:30 自动恢复 <2h（深度睡眠）→ 8%（<10% → 仅回答 @ 和指令）
精力调制档位（inbound.js 消费）: <80 冷却×2 / <30 冷却×4 / <10 仅@+指令
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yuro_layers

WORK = Path(yuro_layers.work_dir())
SLEEP_STATE = WORK / 'group_sleep_state.json'
ROUTINE_FILE = WORK / 'routine_state.md'
ROUTINE_SLEEP_STAGES = ('sleep', 'winding')


def load_sleep_state():
    try:
        return json.loads(SLEEP_STATE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_sleep_state(st):
    try:
        SLEEP_STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    except Exception:
        pass


def routine_stage() -> str:
    try:
        txt = ROUTINE_FILE.read_text(encoding='utf-8')
        m = re.search(r'^阶段[:：]\s*(\w+)', txt, re.M)
        return m.group(1) if m else ''
    except Exception:
        return ''


def compute(group: str) -> tuple[int, dict]:
    """返回 (pct, 明细)"""
    now = datetime.now()
    stage = routine_stage()
    # 群睡眠状态（过期自动清除）
    st = load_sleep_state()
    item = st.get(group)
    group_sleep = False
    hours_left = 0.0
    if item:
        try:
            until = datetime.fromisoformat(item['until'])
            if now < until:
                group_sleep = True
                hours_left = (until - now).total_seconds() / 3600
            else:
                st.pop(group, None)
                save_sleep_state(st)
        except Exception:
            st.pop(group, None)
            save_sleep_state(st)
    routine_sleep = stage in ROUTINE_SLEEP_STAGES
    if group_sleep:
        # U 型曲线: 刚睡 20%(还能应两句) → 熟睡 8%(仅@+指令) → 快醒浅睡 15%(迷糊但应答略回)
        if hours_left >= 7:
            pct = 20
        elif hours_left >= 2:
            pct = 8
        else:
            pct = 15
    elif routine_sleep:
        pct = 15  # 例行睡眠(作息): 统一低精力
    else:
        pct = 100
    detail = {
        'group': group,
        'pct': pct,
        'group_sleep': group_sleep,
        'hours_left': round(hours_left, 1),
        'routine_stage': stage or '未知',
        'routine_sleep': routine_sleep,
    }
    return pct, detail


def fmt_detail(d: dict) -> str:
    if d['group_sleep']:
        hl = d['hours_left']
        gs = '刚睡(剩 %sh)' % hl if hl >= 7 else '熟睡中(剩 %sh, 仅@可唤醒)' % hl if hl >= 2 else '浅睡(剩 %sh, 快醒了)' % hl
    else:
        gs = '清醒'
    rs = '睡眠/睡前' if d['routine_sleep'] else '清醒'
    return (f'精力: {d["pct"]}%\n群睡眠: {gs}\n作息阶段: {d["routine_stage"]} ({rs})')


if __name__ == '__main__':
    raw = sys.argv[1:]
    args = []
    i = 0
    while i < len(raw):
        if raw[i] == '--bot' and i + 1 < len(raw):
            i += 2
            continue
        args.append(raw[i])
        i += 1
    mode = args[0] if args else 'status'
    group = args[1] if len(args) > 1 else ''
    if not group:
        print('缺少 group 参数', file=sys.stderr)
        sys.exit(2)
    pct, detail = compute(group)
    if mode == 'explain':
        print(fmt_detail(detail))
    else:
        print(pct)
    sys.exit(0)
