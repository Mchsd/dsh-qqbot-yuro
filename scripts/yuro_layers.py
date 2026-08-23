# -*- coding: utf-8 -*-
"""Yuro 数据目录解析（配置驱动，2026-08-23 插件化）。

由 dsh-qqbot-yuro 插件注入环境变量（spawn.js buildScriptEnv）：
  - YURO_WORK_DIR    群聊工作区目录名（相对 ~/.dsh/），默认 work-qq-group
  - YURO_LLM_BASE_URL  LLM 网关 base url，默认 http://127.0.0.1:18081/v1
  - YURO_MODEL         群聊默认模型名（可空）

脚本内统一：
  WORK = yuro_layers.work_dir()      # 绝对路径：~/.dsh/<workDir>
  BASE = yuro_layers.base_url()      # LLM 网关
  MODEL = yuro_layers.model()        # 模型名

不再硬编码具体盘符/用户名/实例名——全部由插件配置驱动。
"""

import os

DEFAULT_WORK = 'work-qq-group'
DEFAULT_BASE = 'http://127.0.0.1:18081/v1'


def _dsh_dir():
    return os.path.expanduser('~/.dsh')


def work_dir(bot=None):
    """群聊工作区绝对路径（~/.dsh/<workDir>）。bot 参数保留兼容，不改变目录。"""
    name = os.environ.get('YURO_WORK_DIR') or DEFAULT_WORK
    return os.path.join(_dsh_dir(), name)


def memories_dir(bot=None):
    return os.path.join(_dsh_dir(), 'qqbot-memories-group')


def base_url():
    return os.environ.get('YURO_LLM_BASE_URL') or DEFAULT_BASE


def model():
    return os.environ.get('YURO_MODEL') or ''


def token_id(bot=None):
    """计费 token 渠道 id（由部署方配置；缺省 0 表示不参与预算统计）。"""
    try:
        return int(os.environ.get('YURO_TOKEN_ID') or 0)
    except ValueError:
        return 0


def port(bot=None):
    return int(os.environ.get('YURO_PORT') or 8898)


def bot_name(bot=None):
    return os.environ.get('YURO_BOT_NAME') or 'yuro'
