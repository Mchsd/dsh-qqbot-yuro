#!/usr/bin/env python3
"""Yuro 作息状态机 — 定点吃饭/睡觉/休息/工作（2026-08-21）。

按当前时间判断 Yuro 处于哪个生活阶段，切换时更新 routine_state.md。
Yuro 的 persona 会读取该文件，回复时自然带出生活感（"刚吃完饭回来~"）。

用法:
  python yuro_routine.py update    # 判断+切换阶段（cron 每 15 分钟；无变化静默）
  python yuro_routine.py status    # 输出当前阶段（人读）
  python yuro_routine.py force <stage>  # 手动强制切换（调试/用户命令用）

阶段表（时间 → 阶段）:
  sleep 🌙 00:00-07:29   睡觉（不回复）
  wake  🌅 07:30-07:59   刚起床
  work_morning 💼 08:00-11:59  上午工作
  lunch 🍚 12:00-12:39   午饭
  nap   😴 12:40-13:39   午休
  work_afternoon 💼 13:40-17:59 下午工作
  dinner 🍜 18:00-18:39  晚饭
  evening 🎮 18:40-22:59 晚间自由（最活跃）
  winding 🌙 23:00-23:59 准备睡觉
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import yuro_layers
STATE = Path(yuro_layers.work_dir()) / 'routine_state.md'
ANNOUNCE = Path(yuro_layers.work_dir()) / 'announce.json'  # [2026-08-22] 作息切换播报(bootstrap 30s 消费发群)

# (开始分钟, 阶段, 状态文本, 事件描述)
STAGES = [
    (0,     'sleep',  '睡觉中',   '睡觉'),
    (450,   'wake',   '刚起床',   '起床'),
    (480,   'work_morning', '工作中',   '开始上午的工作'),
    (720,   'lunch',  '吃午饭',   '吃午饭'),
    (760,   'nap',    '午休',     '午休小睡'),
    (820,   'work_afternoon', '工作中', '开始下午的工作'),
    (1080,  'dinner', '吃晚饭',   '吃晚饭'),
    (1120,  'evening', '晚间自由', '进入晚间自由时间'),
    (1380,  'winding', '准备睡觉', '准备睡觉'),
    (1440,  'sleep',  '睡觉中',   '睡觉'),
]

STAGE_LABEL = {
    'sleep': '🌙 睡觉',
    'wake': '🌅 刚起床',
    'work_morning': '💼 上午工作',
    'lunch': '🍚 午饭时间',
    'nap': '😴 午休',
    'work_afternoon': '💼 下午工作',
    'dinner': '🍜 晚饭时间',
    'evening': '🎮 晚间自由',
    'winding': '🌙 准备睡觉',
}

NEXT_HINT = {
    'sleep': '07:30 起床',
    'wake': '08:00 开始工作',
    'work_morning': '12:00 午饭',
    'lunch': '12:40 午休',
    'nap': '13:40 下午工作',
    'work_afternoon': '18:00 晚饭',
    'dinner': '18:40 晚间自由',
    'evening': '23:00 睡觉',
    'winding': '00:00 睡觉',
}


def stage_for_minute(m: int) -> tuple:
    """分钟 → (阶段, 状态文本, 事件描述)。"""
    for start, stage, text, event in STAGES:
        if m < start:
            continue
    # 取最后一个 start <= m 的
    best = STAGES[-1]
    for start, stage, text, event in STAGES:
        if m >= start:
            best = (start, stage, text, event)
    return best[1:]


def current_stage() -> tuple:
    now = datetime.now()
    m = now.hour * 60 + now.minute
    stage, text, event = stage_for_minute(m)
    return stage, text, event, now


def render_state(stage, text, event, now) -> str:
    hint = NEXT_HINT.get(stage, '')
    return (
        '# Yuro 当前作息状态（yuro_routine.py 自动更新，勿手改）\n\n'
        f'状态: {text}\n'
        f'阶段: {stage}\n'
        f'阶段开始: {now.strftime("%Y-%m-%d %H:%M")}\n'
        f'最近事件: {event}\n'
        f'下次切换: {hint}\n\n'
        '## 今日作息轨迹\n'
    )


def load_track() -> list:
    """读已有轨迹行。"""
    if not STATE.exists():
        return []
    try:
        lines = STATE.read_text(encoding='utf-8').splitlines()
        in_track = False
        track = []
        for ln in lines:
            if ln.strip() == '## 今日作息轨迹':
                in_track = True
                continue
            if in_track and ln.strip().startswith('- '):
                track.append(ln.strip())
        return track
    except Exception:
        return []


def update(force_stage: str | None = None) -> str:
    stage, text, event, now = current_stage()
    if force_stage:
        stage, text, event = force_stage, STAGE_LABEL.get(force_stage, force_stage).split(' ', 1)[-1], force_stage
    track = load_track()
    # 阶段变了才写（防频繁写盘）
    if STATE.exists():
        old = STATE.read_text(encoding='utf-8')
        if f'阶段: {stage}' in old and not force_stage:
            return ''  # 无变化，静默
    entry = f'- {now.strftime("%H:%M")} {event}'
    if track and track[-1] == entry:
        return ''  # 同一事件不重复
    # 跨天清理：轨迹只留今天
    track = [t for t in track if t.startswith('- ') and not _is_old(t, now)]
    track.append(entry)
    body = render_state(stage, text, event, now)
    content = body + '\n'.join(track[-12:]) + '\n'  # 保留最近 12 条
    tmp = STATE.with_suffix('.md.tmp')
    tmp.write_text(content, encoding='utf-8')
    try:
        tmp.replace(STATE)
    except OSError:
        tmp.unlink(missing_ok=True)
    # [2026-08-22 作息播报] 切换 sleep/wake 时写 announce.json（bootstrap 30s 消费发群, 双 bot 分层文案）
    try:
        if stage in ('sleep', 'wake'):
            bot_name = yuro_layers.bot_name()
            emoji = '🌙' if bot_name == 'Yume' else '🐳'
            if stage == 'sleep':
                text = f'{emoji} 呜哇…困了，{bot_name} 要睡了…晚安大家，明早见~' if bot_name != 'Yume' else f'{emoji} 诶嘿…{bot_name} 去梦里找月光啦，晚安~'
            else:
                text = f'{emoji} 早！{bot_name} 睡饱啦，元气满满的一天从早上开始！' if bot_name != 'Yume' else f'{emoji} 早呀～{bot_name} 从月亮上下来啦，今天也一起玩吧！'
            ANNOUNCE.write_text(json.dumps({'text': text}, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
    return f'🔄 Yuro 作息切换: {STAGE_LABEL.get(stage, stage)}（{now.strftime("%H:%M")}）'


def _is_old(track_line: str, now: datetime) -> bool:
    try:
        hm = track_line[2:7]
        h, m = int(hm[:2]), int(hm[3:5])
        cur = now.hour * 60 + now.minute
        # 轨迹时间比当前晚 3 小时以上 → 昨天的残留
        return (h * 60 + m) > cur + 180
    except Exception:
        return True


def status() -> str:
    stage, text, event, now = current_stage()
    return f'{STAGE_LABEL.get(stage, stage)}（{now.strftime("%H:%M")}）→ 下次 {NEXT_HINT.get(stage, "")}'


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
    mode = args[0] if args else 'status'
    if mode == 'update':
        out = update(args[1] if len(args) > 1 else None)
        if out:
            print(out)
    elif mode == 'status':
        print(status())
    elif mode == 'force' and len(args) > 1:
        out = update(args[1])
        print(out or '已切换')
    else:
        print(__doc__)
