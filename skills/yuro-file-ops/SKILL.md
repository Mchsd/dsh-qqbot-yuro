---
name: yuro-file-ops
description: 用文件工具处理工作区文件：读取/搜索/统计/转码。Use when 需要查看或处理文件内容时。
---

# 文件处理（yuro-file-ops）

## 适用场景
- 群友/主人让你查看某个文件的内容
- 需要统计、搜索、转换文本文件
- 整理自己的笔记/配置

## 方法
1. 小文件（<8KB）→ 直接用 file 工具读取全文
2. 大文件或需要统计 → sandbox_exec 跑 yuro_file_tools.py：
   - 文件信息: `sandbox_exec("yuro_file_tools.py", ["info", "<路径>"])`
   - 前 N 行: `["head", "<路径>", "20"]`（默认 20，最大 50）
   - 后 N 行: `["tail", "<路径>", "20"]`
   - 搜索关键词: `["grep", "<路径>", "关键词"]`（ASCII 关键词）
   - 行数统计: `["count", "<路径>"]`
   - 编码转换: `["convert", "<路径>"]`（GBK→UTF-8 原地替换）
3. 中文关键词搜索 → 用 file 工具读全文后自己找

## 注意
- 只能处理 work-qq-group-staging/ 和 scripts/ 下的文件
- 输出上限 1500 字，大文件用 head/tail 分段看
- convert 会原地覆盖文件，转码前先 info 确认编码
