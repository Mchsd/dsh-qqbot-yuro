#!/usr/bin/env python3
"""Yuro 下载工具 — 下载 URL 到 work-qq-group/downloads/（沙箱受限）。

用法:
  python yuro_download.py <url> [filename]
  python yuro_download.py https://example.com/pic.jpg            # 文件名从 URL 推断
  python yuro_download.py https://example.com/a.bin myfile.bin   # 指定文件名

安全限制（工具层强制）:
  - 仅 http/https 协议
  - 大小上限 20MB
  - 30s 超时
  - 文件名净化（只留字母数字._-），只写入 downloads/ 目录
"""
import os
import re
import sys
import urllib.error
import urllib.request

import yuro_layers  # [2026-08-22 分层] Yume/Yuro 各自 downloads/（原硬编码生产 WORK, 蓝侧会误写生产）

WORK = yuro_layers.work_dir()
DL_DIR = os.path.join(WORK, 'downloads')
MAX_BYTES = 20 * 1024 * 1024   # 20MB
TIMEOUT = 30
UA = 'Mozilla/5.0 (compatible; Yuro-Bot/1.0)'


def clean_name(name: str) -> str:
    name = re.sub(r'[^A-Za-z0-9._-]', '_', name)
    if not name or name in ('.', '..'):
        return 'download.bin'
    return name[:120]


def main() -> int:
    global WORK, DL_DIR
    args = sys.argv[1:]
    # [2026-08-22 分层] 解析 --bot <name> 配对参数（默认 yuro），并按 bot 计算工作目录
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
    DL_DIR = os.path.join(WORK, 'downloads')
    if len(args) < 1:
        print('用法: yuro_download.py [--bot yuro|yume] <url> [filename]')
        return 2
    url = args[0].strip()
    low = url.lower()
    if not (low.startswith('http://') or low.startswith('https://')):
        print('❌ 只允许 http/https 链接')
        return 2
    # 文件名：显式给定或从 URL 推断（去掉 query）
    if len(args) >= 2:
        fname = clean_name(args[1])
    else:
        fname = clean_name(os.path.basename(url.split('?')[0].split('#')[0]))
    os.makedirs(DL_DIR, exist_ok=True)
    dest = os.path.join(DL_DIR, fname)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            length = resp.headers.get('Content-Length')
            if length and length.isdigit() and int(length) > MAX_BYTES:
                print(f'❌ 文件过大: {int(length) // 1024 // 1024}MB > 20MB 上限')
                return 2
            data = resp.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                print('❌ 文件超过 20MB 上限')
                return 2
            ctype = resp.headers.get('Content-Type', '?')[:60]
        with open(dest, 'wb') as f:
            f.write(data)
        print(f'✅ 已下载: {fname} ({len(data):,} 字节)')
        print(f'路径: {dest}')
        print(f'类型: {ctype}')
        return 0
    except urllib.error.HTTPError as e:
        print(f'❌ 下载失败 HTTP {e.code}: {e.reason}')
        return 2
    except urllib.error.URLError as e:
        print(f'❌ 网络错误: {e.reason}')
        return 2
    except Exception as e:
        print(f'❌ 下载失败: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
