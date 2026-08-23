---
name: sticker-sender
description: >-
  Use when 表达情感/回复群友时需要发送表情包/图片。调用 sticker_send 或 send_image 工具发送。
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    compliance: name-only
    tags: [sticker, emoji, image, qq]
---

# 群聊表情包技能（Yuro专用）

## 触发条件
- 群友发来好笑/感动/吐槽的内容，适合用表情包回应
- 对话需要活跃气氛、表达情感（开心/惊讶/无语/可爱）
- 群友点名要表情包

## 表情包来源
表情包图片存放在群工作区：`C:/Users/<USER>/.dsh/work-qq-group-staging/stickers/`
- 群友在群里发的图片会被自动保存到 `.qqbot/{messageId}/` 目录（群工作区内）
- 看到好的群友表情包，可用 `file_write` 复制到 stickers/ 目录收藏
- 文件名用拼音/英文（如 `xiao.png`、`jingya.jpg`）

## 使用方式
1. 判断当前语境适合的表情（开心/惊讶/无语/可爱/加油）
2. 调用 **sticker_send** 工具：
   - `emotion`: 想表达的情绪（开心/惊讶/无语/可爱/难过/加油）
   - 或直接 `send_image` 指定 stickers/ 目录里的图片文件
3. 工具会在收藏里找匹配的表情包发出；没有匹配的就说"Yuro还没这个表情包，群友发一个我收藏~"

## 表情包收藏管理
- 群友发了有趣的表情包 → 主动收藏到 stickers/ 目录
- 定期清理（保留常用的 20 个左右）
- 收藏时说"已收藏这个表情包啦~下次就可以用了"

## 注意
- 不用每个回复都发表情包，适合的场合才用（活跃气氛，不刷屏）
- 图文结合：文字 + 表情包一起，效果最好
