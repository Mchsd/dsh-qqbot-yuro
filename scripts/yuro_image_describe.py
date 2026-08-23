#!/usr/bin/env python3
"""Yuro 图片理解 v2 — 描述 + SauceNAO 角色识别 + 群内角色库（2026-08-21）。

v2 新增（解决"叙述与图片不匹配/认不出角色"）：
  - SauceNAO 反向搜索层: 权威识别角色名/作品/画师（免费 100 次/天, 无 key 优雅跳过）
  - 群内角色库 anime_chars.md: 识别结果沉淀, 同角色再遇零成本命中（本地知识库）
  - 描述 prompt 结构化: 要求输出角色特征（发色/发型/服装）, 与搜索层互补
  - 旧缓存兼容: 已有缓存无 sauce 字段时只补 SauceNAO（不重跑视觉模型）

用法:
  python yuro_image_describe.py <url|path>      # 单张: 生成+缓存（后台模式, 无参输出描述）
  python yuro_image_describe.py --read-cache-only <path>  # 只读缓存, 单行 JSON（inbound 集成用）
  python yuro_image_describe.py --batch <dir>   # 批量生成 → manifest.json
  python yuro_image_describe.py --cache-info    # 缓存统计
  python yuro_image_describe.py --roles         # 角色库内容

SauceNAO key: 环境变量 SAUCENAO_KEY 或文件 C:/Users/<USER>/.dsh/saucenao.key（一行）。
无 key 时 SauceNAO 层自动跳过（只输出视觉描述, 与原行为一致）。
"""

from __future__ import annotations  # Python 3.9 兼容 dict | None 注解

import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path
import yuro_layers  # [2026-08-23 插件化] 配置驱动

# Windows 管道输出强制 UTF-8（node 端 spawnSync encoding='utf-8' 解码）
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ── 配置 ──
BASE = yuro_layers.base_url()
MODEL = 'mimo-v2.5'
DSH_DIR = Path(yuro_layers.work_dir()).parent
CACHE_DIR = Path(yuro_layers.work_dir()) / 'images_cache'
ROLE_DB = Path(yuro_layers.work_dir()) / 'anime_chars.md'
SAUCE_KEY_FILE = DSH_DIR / 'saucenao.key'
SAUCE_URL = 'https://saucenao.com/search.php'
SAUCE_THRESHOLD = 70.0  # 相似度阈值(%)，低于视为未命中
SAUCE_QUOTA_FILE = DSH_DIR / 'sauce_quota.json'  # 每日剩余额度持久化(免费~100次/天)
SAUCE_QUOTA_MIN = 2  # 剩余<=2 时跳过 SauceNAO(留余量), 次日自动恢复
DB = os.environ.get('YURO_NEWAPI_DB', '')

DESCRIBE_PROMPT = (
    '请用中文描述这张图片：\n'
    '1) 画面内容（人物/场景/动作/文字）\n'
    '2) 如果是动漫/游戏角色，详细描述发型、发色、瞳色、服装、标志性道具等特征'
    '（如果明确认识这个角色请直接说出名字和作品，例如"初音未来（VOCALOID）"）\n'
    '不超过100字，输出一段平文本，不要分点，不要思考过程。'
)
# lite 模式（未@消息的日常表情包快速识别）：一句话 + 类型，低成本
LITE_PROMPT = (
    '用一句话中文描述这张图片（25字以内），并标注类型：表情包/截图/插画/照片/其他。'
    '格式如："表情包：猫猫震惊脸" 或 "插画：蓝发少女全身像"。不要思考过程，直接给答案。'
)
EMOTION_PROMPT = (
    '请用 3 个以内的中文词（逗号分隔）概括这张图片表达的情绪/氛围，'
    '例如：开心,调皮 或 无语 或 委屈。只输出词，不要其他内容。不要思考过程，直接给答案。'
)
IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


# ── 基础 ──

def get_api_key():
    """优先环境变量 DSH_PRO_KEY，其次 SQLite 读 yuro-pro 完整 key。"""
    env = os.environ.get('DSH_PRO_KEY')
    if env and env.strip():
        return env.strip()
    try:
        import sqlite3
        conn = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
        cur = conn.cursor()
        cur.execute("SELECT key FROM tokens WHERE name='yuro-pro'")
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception as e:
        print(f'警告: 读取 yuro-pro key 失败: {e}', file=sys.stderr)
    return ''


def get_saucenao_key():
    """SauceNAO API key：环境变量优先，其次 .dsh/saucenao.key 文件。无 key 返回 ''（优雅跳过）。"""
    env = os.environ.get('SAUCENAO_KEY')
    if env and env.strip():
        return env.strip()
    try:
        if SAUCE_KEY_FILE.exists():
            k = SAUCE_KEY_FILE.read_text(encoding='utf-8').strip()
            if k and not k.startswith('#'):
                return k
    except Exception:
        pass
    return ''


def load_image_b64(source: str) -> bytes:
    """URL 或本地路径 → 图片二进制。"""
    if source.startswith(('http://', 'https://')):
        req = urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'})
        return urllib.request.urlopen(req, timeout=20).read()
    return Path(source).read_bytes()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vision_call(prompt: str, image_b64: str, max_tokens: int = 256) -> str:
    """调 new-api 视觉模型。"""
    key = get_api_key()
    if not key:
        raise RuntimeError('无 API key（DSH_PRO_KEY 未设置且 SQLite 读取失败）')
    body = {
        'model': MODEL,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{image_b64}'}},
            ],
        }],
        'max_tokens': max_tokens,
        'temperature': 0.3,
    }
    req = urllib.request.Request(
        BASE + '/chat/completions',
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        d = json.load(resp)
    return (d.get('choices') or [{}])[0].get('message', {}).get('content', '').strip()


# ── SauceNAO 反向搜索层 ──

def resolve_dirs(source: str) -> None:
    """数据目录（公开样板单端，统一蓝端 staging 目录）。

    热插拔：每个入口函数调用，无需重启。
    """
    global CACHE_DIR, ROLE_DB
    CACHE_DIR = Path(yuro_layers.work_dir()) / 'images_cache'
    ROLE_DB = Path(yuro_layers.work_dir()) / 'anime_chars.md'


def get_sauce_quota() -> dict | None:
    """读配额状态文件；跨天自动失效返回 None。"""
    try:
        if SAUCE_QUOTA_FILE.exists():
            d = json.loads(SAUCE_QUOTA_FILE.read_text(encoding='utf-8'))
            if d.get('date') == time.strftime('%Y-%m-%d'):
                return d
    except Exception:
        pass
    return None


def save_sauce_quota(long_remaining, short_remaining) -> None:
    """持久化 SauceNAO 剩余额度（响应 header 自带）。"""
    try:
        SAUCE_QUOTA_FILE.write_text(json.dumps({
            'date': time.strftime('%Y-%m-%d'),
            'long_remaining': int(long_remaining) if long_remaining is not None else -1,
            'short_remaining': int(short_remaining) if short_remaining is not None else -1,
            'updated': time.strftime('%H:%M:%S'),
        }, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def sauce_nao_lookup(img_bytes: bytes) -> dict | None:
    """SauceNAO 以图搜图 → {characters, material, creator, similarity, url} 或 None。

    免费账户约 100 次/天；429 限流或网络失败返回 None（不抛异常）。
    配额保护：日剩余 <=SAUCE_QUOTA_MIN 时跳过（留余量，次日自动恢复）。
    """
    key = get_saucenao_key()
    if not key:
        return None  # 无 key 优雅跳过
    q = get_sauce_quota()
    if q and q.get('long_remaining') is not None and int(q.get('long_remaining', 99)) <= SAUCE_QUOTA_MIN:
        print(f"[sauce] 今日额度将尽(剩 {q.get('long_remaining')}), 跳过 SauceNAO", file=sys.stderr)
        return None
    boundary = '----YuroForm' + uuid.uuid4().hex
    parts = []
    for name, val in [('api_key', key), ('output_type', '2'), ('db', '999'), ('numres', '3')]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode('utf-8'))
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="img.png"\r\n'
        f'Content-Type: image/png\r\n\r\n'.encode('utf-8')
    )
    parts.append(img_bytes)
    parts.append(f'\r\n--{boundary}--\r\n'.encode('utf-8'))
    body = b''.join(parts)
    req = urllib.request.Request(
        SAUCE_URL, data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'User-Agent': 'Mozilla/5.0'},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            d = json.load(resp)
    except Exception as e:
        print(f'[sauce] 查询失败(跳过): {e}', file=sys.stderr)
        return None
    # status 0=正常, 其他(如 429)视为不可用
    hdr = d.get('header') or {}
    # 持久化剩余额度（long_remaining=日剩余, short_remaining=短时剩余）
    save_sauce_quota(hdr.get('long_remaining'), hdr.get('short_remaining'))
    if hdr.get('status') not in (0, None):
        print(f"[sauce] API 状态异常: {hdr.get('status')} {hdr.get('message', '')}", file=sys.stderr)
        return None
    best = None
    for r in (d.get('results') or []):
        rhead = r.get('header') or {}
        try:
            sim = float(rhead.get('similarity', 0))
        except (TypeError, ValueError):
            sim = 0.0
        if sim < SAUCE_THRESHOLD:
            continue
        data = r.get('data') or {}
        chars = (data.get('characters') or '').strip()
        material = (data.get('material') or data.get('source') or '').strip()
        creator = (rhead.get('creator') or data.get('member_name') or '').strip()
        ext = data.get('ext_urls') or []
        url = ext[0] if ext else ''
        if chars or material:
            best = {
                'similarity': round(sim, 1),
                'characters': chars,
                'material': material,
                'creator': creator,
                'url': url,
            }
            break  # SauceNAO 结果按索引优先级排序，第一个达标即最优
    if best is None:
        print(f'[sauce] 未命中(阈值 {SAUCE_THRESHOLD}%)', file=sys.stderr)
    return best


def sauce_to_text(sauce: dict) -> str:
    """sauce 结果 → 一行注入文本。"""
    if not sauce:
        return ''
    parts = []
    if sauce.get('characters'):
        parts.append(f'角色: {sauce["characters"]}')
    if sauce.get('material'):
        parts.append(f'作品: {sauce["material"]}')
    if sauce.get('creator'):
        parts.append(f'画师: {sauce["creator"]}')
    parts.append(f'相似度 {sauce.get("similarity", 0):.0f}%')
    return '，'.join(parts)


# ── 群内角色库（本地知识库） ──

def load_role_db() -> list[str]:
    """角色库原始行（跳过注释/空行）。"""
    if not ROLE_DB.exists():
        return []
    try:
        return [ln.strip() for ln in ROLE_DB.read_text(encoding='utf-8').splitlines()
                if ln.strip() and not ln.strip().startswith('#')]
    except Exception:
        return []


def parse_role_line(line: str):
    """'- 初音未来 | hatsune miku | VOCALOID | 蓝绿双马尾 | 3' → (cn, en, work, feat, cnt)"""
    parts = [p.strip() for p in line.lstrip('- ').split('|')]
    if len(parts) < 5:
        return None
    cn, en, work, feat, cnt = parts[0], parts[1].lower(), parts[2], parts[3], parts[4]
    try:
        cnt = int(re.sub(r'\D', '', cnt) or 0)
    except ValueError:
        cnt = 0
    return cn, en, work, feat, cnt


def role_lookup(sauce: dict | None, description: str) -> str | None:
    """角色库匹配 → 注入文本 或 None。匹配源：SauceNAO characters（英文）+ 描述文本（中文）。"""
    lines = load_role_db()
    if not lines:
        return None
    sauce_chars = ''
    if sauce and sauce.get('characters'):
        sauce_chars = sauce['characters'].lower()
    desc_l = (description or '').lower()
    for line in lines:
        p = parse_role_line(line)
        if not p:
            continue
        cn, en, work, _feat, cnt = p
        hit = False
        if en and (en in sauce_chars or en in desc_l):
            hit = True
        elif cn and cn in (description or ''):
            hit = True
        if hit:
            return f'{cn}（{work}，群内已见 {cnt} 次）'
    return None


def update_role_db(sauce: dict | None) -> None:
    """新角色入库（次数1），已有角色次数+1。原子写（临时文件+replace）。"""
    if not sauce or not sauce.get('characters'):
        return
    chars = [c.strip() for c in sauce['characters'].split(',') if c.strip()]
    if not chars:
        return
    material = sauce.get('material', '')
    lines = load_role_db()
    by_en = {}
    for i, ln in enumerate(lines):
        p = parse_role_line(ln)
        if p and p[1]:
            by_en[p[1]] = i
    changed = False
    for ch in chars:
        chl = ch.lower()
        if chl in by_en:
            idx = by_en[chl]
            p = parse_role_line(lines[idx])
            if p:
                cn, en, work, feat, cnt = p
                lines[idx] = f'- {cn} | {en} | {work} | {feat} | {cnt + 1}'
                changed = True
        else:
            lines.append(f'- {ch} | {ch} | {material} | | 1')
            changed = True
    if not changed:
        return
    ROLE_DB.parent.mkdir(parents=True, exist_ok=True)
    content = (
        '# Yuro 二次元角色库（自动积累，可手工编辑）\n'
        '# 格式: - 中文名 | 英文名 | 作品 | 特征 | 出现次数\n'
        '# 来源: SauceNAO 识别结果自动追加；中文名默认=英文名，可手工美化\n'
    ) + '\n'.join(lines) + '\n'
    tmp = ROLE_DB.with_suffix('.md.tmp')
    tmp.write_text(content, encoding='utf-8')
    try:
        tmp.replace(ROLE_DB)
    except OSError:
        tmp.unlink(missing_ok=True)


# ── 主流程 ──

def describe_one(source: str, force: bool = False) -> dict:
    """单张图片 → 完整缓存 dict（描述+情绪+sauce+role）。带缓存；旧缓存只补 sauce。"""
    resolve_dirs(source)  # 蓝绿隔离: 按图片路径选 prod/staging 数据目录
    data = load_image_b64(source)
    h = sha256_bytes(data)
    cache_file = CACHE_DIR / f'{h}.json'
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if cache_file.exists() and not force:
        d = json.loads(cache_file.read_text(encoding='utf-8'))
        if 'sauce' not in d:
            # 旧缓存(v1 无 sauce 字段): 只补 SauceNAO 层, 不重跑视觉模型
            try:
                d['sauce'] = sauce_nao_lookup(data)
                d['sauce_text'] = sauce_to_text(d['sauce'])
                d['role_text'] = role_lookup(d['sauce'], d.get('description', ''))
                d['time'] = time.strftime('%Y-%m-%d %H:%M:%S')
                cache_file.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
            except Exception as e:
                print(f'警告: 旧缓存补 sauce 失败: {e}', file=sys.stderr)
        return d

    img_b64 = base64.b64encode(data).decode('ascii')
    desc = vision_call(DESCRIBE_PROMPT, img_b64, max_tokens=512)
    emotions = vision_call(EMOTION_PROMPT, img_b64, max_tokens=128)
    sauce = sauce_nao_lookup(data)
    result = {
        'description': desc,
        'emotions': [e.strip() for e in emotions.split(',') if e.strip()],
        'sauce': sauce,
        'sauce_text': sauce_to_text(sauce),
        'role_text': role_lookup(sauce, desc),
        'source': source,
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'sha256': h,
    }
    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    update_role_db(sauce)  # 新识别角色沉淀入库
    return result


def read_cache_only(source) -> dict | None:
    """只读缓存 → 单行 JSON 所需字段；未命中返回 None。"""
    resolve_dirs(source)
    try:
        data = load_image_b64(source)
        h = sha256_bytes(data)
        cache_file = CACHE_DIR / f'{h}.json'
        if cache_file.exists():
            d = json.loads(cache_file.read_text(encoding='utf-8'))
            return {
                'description': d.get('description', ''),
                'emotions': d.get('emotions', []),
                'sauce_text': d.get('sauce_text', ''),
                'role_text': d.get('role_text', ''),
            }
    except Exception:
        pass
    return None


def describe_lite(source: str) -> str:
    """轻量识别（未@消息的日常表情包）：优先 full 缓存 → lite 缓存 → mimo 小调用。

    只描述+类型，不跑 SauceNAO/角色库/情绪（低成本）。写缓存 lite 字段。
    """
    resolve_dirs(source)
    data = load_image_b64(source)
    h = sha256_bytes(data)
    cache_file = CACHE_DIR / f'{h}.json'
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if cache_file.exists():
        try:
            d = json.loads(cache_file.read_text(encoding='utf-8'))
            if d.get('description'):
                return d['description']  # full 缓存直接复用
            if d.get('lite', {}).get('desc'):
                return d['lite']['desc']
        except Exception:
            pass
    img_b64 = base64.b64encode(data).decode('ascii')
    lite_desc = vision_call(LITE_PROMPT, img_b64, max_tokens=80)
    # 写缓存（lite 字段；不覆盖已有 full 字段）
    if cache_file.exists():
        try:
            d = json.loads(cache_file.read_text(encoding='utf-8'))
        except Exception:
            d = {}
    else:
        d = {}
    d['lite'] = {'desc': lite_desc, 'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'sha256': h}
    cache_file.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    return lite_desc


def read_cache_lite(source) -> dict | None:
    """只读轻量缓存：{desc, mode}，mode=full|lite。未命中 None。"""
    resolve_dirs(source)
    try:
        data = load_image_b64(source)
        h = sha256_bytes(data)
        cache_file = CACHE_DIR / f'{h}.json'
        if cache_file.exists():
            d = json.loads(cache_file.read_text(encoding='utf-8'))
            if d.get('description'):
                return {'desc': d['description'], 'mode': 'full'}
            if d.get('lite', {}).get('desc'):
                return {'desc': d['lite']['desc'], 'mode': 'lite'}
    except Exception:
        pass
    return None


def batch_describe(directory: str) -> list[dict]:
    """批量：目录所有图片 → 描述+情绪标签 → manifest.json。"""
    d = Path(directory)
    if not d.is_dir():
        print(f'错误: 目录不存在 {d}', file=sys.stderr)
        sys.exit(1)
    manifest = []
    for f in sorted(d.iterdir()):
        if f.suffix.lower() not in IMG_EXTS:
            continue
        try:
            r = describe_one(str(f))
            manifest.append({'file': f.name, **r})
            print(f'✓ {f.name}: {r["description"][:50]}...')
        except Exception as e:
            print(f'✗ {f.name}: {e}', file=sys.stderr)
    out = d / 'manifest.json'
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'批量完成: {len(manifest)} 张 → {out}')
    return manifest


def cache_info() -> None:
    if not CACHE_DIR.exists():
        print('缓存目录不存在（还没有描述过图片）')
        return
    files = list(CACHE_DIR.glob('*.json'))
    total = len(files)
    size = sum(f.stat().st_size for f in files)
    with_sauce = sum(1 for f in files if 'sauce' in f.read_text(encoding='utf-8', errors='ignore'))
    print(f'缓存图片数: {total} | 含角色识别: {with_sauce} | 占用: {size/1024:.1f} KB')


def show_roles() -> None:
    lines = load_role_db()
    if not lines:
        print('角色库为空（识别到角色后自动积累）')
        return
    for ln in lines:
        print(ln)


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    if args[0] == '--cache-info':
        cache_info()
    elif args[0] == '--roles':
        show_roles()
    elif args[0] == '--read-cache-only' and len(args) > 1:
        r = read_cache_only(args[1])
        if r:
            # 单行 JSON（inbound 解析；description 内换行由 json.dumps 转义保证单行）
            print(json.dumps(r, ensure_ascii=False))
        else:
            sys.exit(2)  # 未命中: exit 2 供 inbound 判断
    elif args[0] == '--read-cache-lite' and len(args) > 1:
        r = read_cache_lite(args[1])
        if r:
            print(json.dumps(r, ensure_ascii=False))
        else:
            sys.exit(2)  # 未命中: exit 2 供 inbound 判断
    elif args[0] == '--lite' and len(args) > 1:
        print(describe_lite(args[1]))
    elif args[0] == '--batch' and len(args) > 1:
        batch_describe(args[1])
    else:
        r = describe_one(args[0])
        print(r['description'])
        if r.get('emotions'):
            print(f"[情绪: {'、'.join(r['emotions'])}]")
        if r.get('sauce_text'):
            print(f"[识别: {r['sauce_text']}]")
        if r.get('role_text'):
            print(f"[角色库: {r['role_text']}]")