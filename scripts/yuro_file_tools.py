#!/usr/bin/env python3
"""Yuro 文件处理工具 — 文本文件的读取/搜索/统计/编码转换（沙箱受限）。

用法:
  python yuro_file_tools.py info <file>             # 文件信息: 大小/行数/编码
  python yuro_file_tools.py head <file> [n]         # 前 n 行 (默认 20, 最大 50)
  python yuro_file_tools.py tail <file> [n]         # 后 n 行
  python yuro_file_tools.py grep <file> <keyword>   # 搜索行 (ASCII 关键词)
  python yuro_file_tools.py count <file>            # 行数/字数统计
  python yuro_file_tools.py convert <file>          # 转码为 UTF-8 (GBK→UTF-8), 原地替换

说明:
  - 只处理 work-qq-group/ 和 scripts/ 下的文本文件 (防越权)
  - 中文关键词暂不支持命令行参数 (Windows 编码限制), 可用 file 工具读全文后自己找
"""
import os
import re
import sys

import yuro_layers  # [2026-08-22 分层] Yume/Yuro 白名单各自 work 目录（原硬编码生产 WORK, 蓝侧会误读生产）

WORK = ''          # main() 按 --bot 设置
SCRIPTS = r'C:\Users\<USER>\AppData\Local\<HERMES_SCRIPTS>'
MAX_LINES = 50


def safe_path(p: str):
    norm = p.replace('\\', '/')
    if norm.startswith(WORK.replace('\\', '/') + '/') or norm.startswith(SCRIPTS.replace('\\', '/') + '/'):
        if '..' not in norm:
            return p
    return None


def read_text(p: str):
    # 尝试 utf-8, 失败则 gbk (Windows 常见)
    for enc in ('utf-8', 'gbk', 'utf-8-sig'):
        try:
            with open(p, 'r', encoding=enc) as f:
                return f.read(), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(p, 'rb') as f:
        return f.read().decode('utf-8', errors='replace'), 'unknown'


def main() -> int:
    global WORK
    args = sys.argv[1:]
    # [2026-08-22 分层] 解析 --bot <name>（默认 yuro）, 白名单按 bot 工作目录
    bot = 'yuro'
    i = 0
    while i < len(args):
        if args[i] == '--bot' and i + 1 < len(args):
            bot = args[i + 1]
            i += 2
            continue
        args = args[i:]
        break
    WORK = yuro_layers.work_dir(bot)
    if len(args) < 2:
        print('用法: yuro_file_tools.py [--bot yuro|yume] <info|head|tail|grep|count|convert> <file> [参数]')
        return 2
    cmd, fpath = args[0], args[1]
    resolved = safe_path(fpath)
    if not resolved or not os.path.isfile(resolved):
        print(f'❌ 只允许 work-qq-group/ 和 scripts/ 下的文件: {fpath}')
        return 2
    try:
        if cmd == 'info':
            size = os.path.getsize(resolved)
            text, enc = read_text(resolved)
            print(f'路径: {resolved}')
            print(f'大小: {size:,} 字节 | 行数: {len(text.splitlines()):,} | 编码: {enc}')
            print(f'字符数: {len(text):,}')
            return 0
        if cmd == 'head':
            n = min(int(args[2]) if len(args) > 2 else 20, MAX_LINES)
            text, _ = read_text(resolved)
            print('\n'.join(text.splitlines()[:n]))
            return 0
        if cmd == 'tail':
            n = min(int(args[2]) if len(args) > 2 else 20, MAX_LINES)
            text, _ = read_text(resolved)
            print('\n'.join(text.splitlines()[-n:]))
            return 0
        if cmd == 'grep':
            kw = args[2] if len(args) > 2 else ''
            if not kw:
                print('❌ 需要关键词: grep <file> <keyword>')
                return 2
            text, _ = read_text(resolved)
            hits = [ln for ln in text.splitlines() if kw in ln]
            print(f'命中 {len(hits)} 行:')
            for ln in hits[:30]:
                print(f'  {ln[:150]}')
            return 0
        if cmd == 'count':
            text, _ = read_text(resolved)
            lines = text.splitlines()
            words = len(re.findall(r'\S+', text))
            print(f'行数: {len(lines):,} | 词数: {words:,} | 字符数: {len(text):,}')
            return 0
        if cmd == 'convert':
            raw = open(resolved, 'rb').read()
            for enc in ('utf-8', 'utf-8-sig'):
                try:
                    raw.decode(enc)
                    print('✅ 已是 UTF-8，无需转换')
                    return 0
                except UnicodeDecodeError:
                    continue
            text = raw.decode('gbk', errors='replace')
            with open(resolved, 'w', encoding='utf-8', newline='') as f:
                f.write(text)
            print('✅ 已从 GBK 转码为 UTF-8')
            return 0
        print(f'❌ 未知命令: {cmd}（支持 info/head/tail/grep/count/convert）')
        return 2
    except (ValueError, IndexError):
        print('❌ 参数错误，请检查')
        return 2
    except Exception as e:
        print(f'❌ 处理失败: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
