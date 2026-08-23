---
name: yuro-download
description: 下载网络文件到工作区 downloads/ 目录。Use when 需要下载图片/文件/资料时。
---

# 下载文件（yuro-download）

## 适用场景
- 群友分享链接要你下载看看
- 主人让你下载某个资源
- 需要保存网页图片/文档到本地

## 方法
1. 确认链接是 http/https
2. 用 sandbox_exec 跑下载脚本：
   `sandbox_exec("yuro_download.py", ["<完整URL>"])`
   - 不带文件名 → 自动从 URL 推断文件名
   - 指定文件名 → `["<URL>", "自定义名"]`（只保留字母数字._-）
3. 下载到 downloads/ 目录后，用 file 工具读取或处理

## 注意
- 仅 http/https 协议，文件 ≤20MB，30 秒超时
- URL 含 ?&=# 等字符没问题（已加入白名单）
- 下载的图片可以配合看图能力描述给群友听
- 下载失败会给出原因（大小超限/网络错误/HTTP 状态码）
