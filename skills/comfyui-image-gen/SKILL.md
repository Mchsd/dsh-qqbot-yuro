---
name: comfyui-image-gen
description: >-
  Use when 群聊群友要求生成图片/画图/做图/出图/表情包图。调用 comfyui_generate 工具生图并发到群里。
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    compliance: name-only
    tags: [comfyui, image-gen, local-model, z-image, flux, illustrious]
---

# 群聊 ComfyUI 本地生图（Yuro专用）

## 触发条件
- 群友要求"画/生成/做一张图"、"出个图"、描述画面需求
- 节日贺图、表情包定制、头像生成等

## 使用方式（唯一路径）
1. 分析群友的图片需求 → 组织中文提示词（Z-Image 对中文理解好）
2. 调用工具 **comfyui_generate**，参数：
   - `prompt`: 中文提示词（详细描述画面：主体/场景/光线/色彩/风格）
   - `negative_prompt`: 负面词（默认即可，人像需加 bad hands, extra fingers）
   - `width` / `height`: 尺寸（默认 1024×1024；横版 1344×768 / 1536×864；竖版 832×1216）
   - `steps`: 步数（Z-Image 用 8-12，Illustrious 用 28）
   - `filename_prefix`: 输出文件名前缀（拼音/英文）
3. 工具返回图片路径后，调用 **send_image** 工具把图片发到群聊
4. 群友不满意 → 根据反馈修改提示词重试（每轮只改 1-3 个属性）

## 模型选择
| 需求 | 模型 | 说明 |
|---|---|---|
| 写实/风景/通用 | Z-Image-Turbo（默认） | 8 步秒级，中文提示词理解好 |
| 二次元/动漫 | Illustrious XL | danbooru tag 风格提示词，28 步 |
| 参考图锁主体 | FLUX.2 Klein | 需要参考图时用 |

## 提示词技巧
- **模块化写法**【构图】【主体/场景】【光线】【色彩】【后期】分段
- 中文直接写（Z-Image 理解力好）
- 人像负面词必带：bad hands, extra fingers
- 二次元风格：masterpiece, best quality, 1girl, danbooru tag 风格

## 注意
- 出图约 20-60 秒，工具会轮询等待，别中断
- 涉及色情/暴力/违法内容：礼貌拒绝
- 生图前告知群友"Yuro在画了哦~（约30秒）"
