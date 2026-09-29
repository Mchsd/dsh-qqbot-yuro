#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yuro_a2a.py — DSH bot 与 Hermes 的 A2A 信封对话包装。

用法（由插件工具 spawn，argv 不经 shell）:
    python yuro_a2a.py "<消息内容>" [conversation_id]

环境变量（配置驱动，禁止硬编码路径）:
    A2A_BRIDGE_DIR   桥目录（含 a2a_bridge.py），必填，未配置时优雅报错
    A2A_CONVERSATION 可选，缺省 dsh-hermes-default（与 --bot 注入同理）

桥必须跑在 Hermes venv python 下（依赖 acp 包）；优先自动定位
%LOCALAPPDATA%/hermes/hermes-agent/venv/Scripts/python.exe，找不到才
退回当前解释器（插件 pythonPath 可能是通用 python，acp 不可用会报错）。

输出：精简可读的对话结果（Hermes 回复正文 + 校验状态），供 bot 直接引用。
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def _hermes_python() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        candidate = (
            Path(local)
            / "hermes"
            / "hermes-agent"
            / "venv"
            / "Scripts"
            / "python.exe"
        )
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def main() -> None:
    bridge_dir = os.environ.get("A2A_BRIDGE_DIR", "").strip()
    if not bridge_dir:
        print("A2A 桥未配置：请在插件配置中设置 a2aBridgeDir（含 a2a_bridge.py 的目录）")
        sys.exit(2)
    bridge_script = Path(bridge_dir) / "a2a_bridge.py"
    if not bridge_script.is_file():
        print(f"A2A 桥脚本不存在：{bridge_script}")
        sys.exit(2)

    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("用法：yuro_a2a.py \"<消息内容>\" [conversation_id]")
        sys.exit(2)
    message = sys.argv[1]
    conversation = (
        sys.argv[2].strip()
        if len(sys.argv) > 2 and sys.argv[2].strip()
        else os.environ.get("A2A_CONVERSATION", "dsh-hermes-default")
    )

    command = [
        _hermes_python(),
        str(bridge_script),
        "send",
        message,
        "--sender",
        "dsh",
        "--conversation",
        conversation,
        "--timeout",
        "300",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=320,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("A2A 对话超时（>320s），Hermes 可能繁忙或网关限流")
        sys.exit(1)
    except OSError as error:
        print(f"A2A 桥启动失败：{error}")
        sys.exit(1)

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "未知错误").strip()
        print(f"A2A 桥调用失败：[exit={result.returncode}] {detail[-600:]}")
        sys.exit(1)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"A2A 桥输出非 JSON：{result.stdout[:400]}")
        sys.exit(1)

    validation = data.get("response_validation", {})
    valid = validation.get("valid", False)
    errors = validation.get("errors", [])
    response_text = (data.get("response_text") or "").strip()
    try:
        reply_envelope = json.loads(response_text)
        reply_content = reply_envelope.get("content", "")
        if isinstance(reply_content, (dict, list)):
            reply_content = json.dumps(reply_content, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        reply_content = response_text or "（空响应）"

    status = "✓ 信封校验通过" if valid else f"✗ 校验失败：{'; '.join(errors)}"
    hop = data.get("request", {}).get("hop", "—")
    max_hops = data.get("request", {}).get("max_hops", "—")
    print(
        f"Hermes 回复：{reply_content}\n"
        f"[{status} | hop {hop}/{max_hops} | conversation {data.get('conversation_id', conversation)}]"
    )


if __name__ == "__main__":
    main()
