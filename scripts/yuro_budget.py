#!/usr/bin/env python3
"""Yuro 每日 token 预算 + 情绪精力联动 + 睡眠系统。

每日预算: 1 亿 token, 早 8 点重置。
功能:
  - 查询 yuro-pro 今日 token 消耗(SQLite logs 表)
  - 计算剩余 token → 精力等级 → 写入 work-qq-group/energy_state.md
  - 超限 → 发"困了要睡了"到群 → 写 SLEEP 标志
  - reset 模式: 早 8 点清空今日消耗 + 删睡眠标志 + 发"起床了"

用法:
  python yuro_budget.py            # 正常检查(每 15 分钟 cron)
  python yuro_budget.py reset      # 早 8 点重置
  python yuro_budget.py report     # 汇报今日消耗(每天汇报 cron)
"""

import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, date, timedelta

# ── 配置 ──
DB = os.environ.get('YURO_NEWAPI_DB', '')
import yuro_layers
WORK_GROUP = yuro_layers.work_dir()
ENERGY_FILE = os.path.join(WORK_GROUP, 'energy_state.md')
SLEEP_FLAG = os.path.join(WORK_GROUP, 'SLEEPING')
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.yuro_budget_state.json')

DAILY_LIMIT = 100_000_000  # 1 亿 token/天
RESET_HOUR = 8             # 早 8 点重置
MANUAL_RESET_FILE = os.path.join(WORK_GROUP, 'budget_reset_state.json')  # [2026-08-21] 手动重置点(主人 /重置 指令写入)

# QQ 群发消息配置(从 cordis.patch.yml 读 appSecret, 不发到日志)
APP_ID = '__QQ_BOT_APP_ID__'
GROUP_OPENID = '__GROUP_OPENID__'
SECRET_FILE = os.environ.get('YURO_SECRET_FILE', '')  # 可选: appSecret 来源(未配置则读不到, 预算通知跳过)


def get_app_secret():
    """从 cordis.patch.yml 提取 appSecret(不回显)"""
    try:
        text = open(SECRET_FILE, encoding='utf-8').read()
        m = re.search(r"appSecret:\s*'([^']+)'", text)
        return m.group(1) if m else ''
    except Exception:
        return ''


def get_today_tokens():
    """查询今日(token_id={yuro_layers.token_id()})消耗的 prompt+completion token 数。
    预算周期 = 早 8 点 → 次日早 8 点(与 RESET_HOUR 一致): 凌晨 0-8 点消耗归入前一天周期,
    8 点 reset 后新周期从 0 开始, "早八重置"才真正生效。
    [2026-08-21] 手动重置点: 主人 /重置 指令写 budget_reset_state.json → 周期起点取 max(自然8点, 手动点)"""
    now = datetime.now()
    if now.hour >= RESET_HOUR:
        period_start = now.replace(hour=RESET_HOUR, minute=0, second=0, microsecond=0)
    else:
        period_start = (now - timedelta(days=1)).replace(hour=RESET_HOUR, minute=0, second=0, microsecond=0)
    # 手动重置点（若晚于自然起点则生效; 早 8 点后自然周期覆盖自动失效）
    try:
        if os.path.exists(MANUAL_RESET_FILE):
            st = json.load(open(MANUAL_RESET_FILE, encoding='utf-8'))
            manual_at = datetime.fromisoformat(st.get('at', ''))
            if manual_at > period_start:
                period_start = manual_at
    except Exception:
        pass
    try:
        # 只读模式连接(避免与 new-api 容器写锁冲突: disk I/O error)
        conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0), COUNT(*) "
            f"FROM logs WHERE token_id={yuro_layers.token_id()} AND created_at >= ?",
            (int(period_start.timestamp()),))
        p, c, n = cur.fetchone()
        conn.close()
        return int(p) + int(c), int(n), int(p), int(c)
    except Exception as e:
        print(f'查询消耗失败: {e}')
        return 0, 0, 0, 0


def energy_level(used, limit):
    """根据已用比例计算精力等级"""
    ratio = used / limit if limit else 0
    if ratio >= 1.0:
        return '休眠', 0
    if ratio >= 0.9:
        return '濒临耗尽', 0.1
    if ratio >= 0.6:
        return '疲惫', 0.4
    if ratio >= 0.3:
        return '正常', 0.7
    return '充沛', 1.0


def write_energy_state(used, limit, level, sleeping):
    """写入 energy_state.md — Yuro 每次对话读取"""
    remaining = limit - used
    today = date.today().isoformat()
    mood_hint = {
        '充沛': '精神满满！看到什么都想搭话',
        '正常': '状态还行，正常聊天',
        '疲惫': '有点累了，回复变短，懒得说太多',
        '濒临耗尽': '非常困……不想说话，只想安静待着',
        '休眠': '已经睡着了，不回复任何消息',
    }.get(level, '')
    content = f"""# {yuro_layers.bot_name()} 精力状态（energy_state.md）

> 由预算系统自动更新。{yuro_layers.bot_name()} 每次对话前先读这里，根据精力调整语气。

## 今日预算
- 日期: {today}
- 已用 token: {used:,}
- 每日上限: {limit:,}
- 剩余 token: {remaining:,}
- 消耗占比: {used / limit * 100:.2f}%

## 精力等级: {level}
{mood_hint}

## 睡眠状态: {"💤 睡眠中(不回复)" if sleeping else "清醒"}

## 规则
- 精力充沛/正常 → 正常聊天, 有兴致
- 疲惫 → 回复变短, 省略号多, 提不起劲("嗯……好累……")
- 濒临耗尽 → 几乎不想说话, 很困, 反应慢
- 睡眠中 → 不回复任何消息, 直到早 8 点重置
"""
    try:
        os.makedirs(WORK_GROUP, exist_ok=True)
        with open(ENERGY_FILE, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f'写精力状态失败: {e}')
        return False


def qq_send_group(text):
    """发通知 — 通过 announce.json 让 qqbot 进程主动发群消息(WebSocket 通道, 已验证可用)。
    保留函数名兼容; 实际写 announce.json 由 bootstrap 30s 轮询发送。
    """
    try:
        os.makedirs(WORK_GROUP, exist_ok=True)
        with open(os.path.join(WORK_GROUP, 'announce.json'), 'w', encoding='utf-8') as f:
            json.dump({'text': text}, f, ensure_ascii=False)
        return True, 'announce queued'
    except Exception as e:
        return False, str(e)


def check_and_sleep():
    """检查是否超限, 超限则发困了消息 + 写睡眠标志"""
    if os.path.exists(SLEEP_FLAG):
        return  # 已睡眠
    used, count, p, c = get_today_tokens()
    if used >= DAILY_LIMIT:
        ok, msg = qq_send_group('呜……今天聊太多啦，Yuro 困了要睡了……💤 明天早上 8 点见~')
        with open(SLEEP_FLAG, 'w', encoding='utf-8') as f:
            f.write(f'sleep at {datetime.now().isoformat()}')
        write_energy_state(used, DAILY_LIMIT, '休眠', True)
        print(f'💤 超限进入睡眠(已用 {used:,} >= 1亿)。通知: {"成功" if ok else f"失败 {msg}"}')


def cmd_reset_manual():
    """[2026-08-21 主人 /重置 指令] 手动重置当日 token 计数: 写重置点(从现在起算), 不发起床消息/不动睡眠标志"""
    now = datetime.now()
    json.dump({'at': now.isoformat()}, open(MANUAL_RESET_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'✅ 当日 token 计数已重置（{now.strftime("%H:%M")} 起重新计算）• 预算 1 亿/天')


def do_reset():
    """早 8 点重置: 删睡眠标志 + 发起床消息 + 重建精力状态"""
    slept = os.path.exists(SLEEP_FLAG)
    if os.path.exists(SLEEP_FLAG):
        os.remove(SLEEP_FLAG)
    # 手动重置点已完成使命(自然周期覆盖), 顺带清理
    try:
        if os.path.exists(MANUAL_RESET_FILE):
            os.remove(MANUAL_RESET_FILE)
    except Exception:
        pass
    write_energy_state(0, DAILY_LIMIT, '充沛', False)
    # 起床消息: 睡过才说"起床了", 否则普通早安
    if slept:
        text = '早~！Yuro 睡饱啦，又是元气满满的一天！🐳☀️（今日精力已恢复）'
    else:
        text = '早上好呀~！Yuro 新的一天开始咯，精力满满！🐳☀️'
    ok, msg = qq_send_group(text)
    print(f'🌅 8 点重置完成。起床消息: {"发送成功" if ok else f"失败 {msg}"}')


def main():
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
    if mode == 'reset':
        do_reset()
        return
    if mode == 'reset-manual':  # [2026-08-21] 主人 /重置 指令
        cmd_reset_manual()
        return
    if mode == 'report':
        used, count, p, c = get_today_tokens()
        remaining = DAILY_LIMIT - used
        print(f'📊 Yuro 今日 token 消耗报告')
        print(f'  已用: {used:,} tokens ({count} 次调用)')
        print(f'  剩余: {remaining:,} / {DAILY_LIMIT:,} ({used / DAILY_LIMIT * 100:.4f}%)')
        print(f'  精力: {energy_level(used, DAILY_LIMIT)[0]}')
        return
    # check 模式(每 15 分钟)
    used, count, p, c = get_today_tokens()
    level, _ = energy_level(used, DAILY_LIMIT)
    sleeping = os.path.exists(SLEEP_FLAG)
    write_energy_state(used, DAILY_LIMIT, level, sleeping)
    # 状态文件(供下次对比)
    state = {'used': used, 'count': count, 'time': datetime.now().isoformat()}
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)
    # 超限检测
    check_and_sleep()
    # 静默(正常时无输出, cron 不投递)
    if used >= DAILY_LIMIT * 0.9:
        print(f'⚠️ Yuro 今日 token 已用 {used / DAILY_LIMIT * 100:.1f}%, 剩余 {DAILY_LIMIT - used:,}')


if __name__ == '__main__':
    main()
