# patches/ — dsh-qqbot 入站/出站机制补丁

本目录的 `dsh-qqbot-yuro.patch` 为上游 `@tencent-connect/dsh-qqbot` 提供**入站对话机制**与**出站格式化**。

## 为什么需要它

上游 `im-qqbot` 插件把消息入站（`bot.on('message')`）与出站（`bot` 实例）封装在插件内部，官方 cordis API **无法拦截入站消息或拿到发送实例**。因此 yuro 的以下机制只能通过 patch 改写 `dsh-qqbot` 的 dist 文件实现：

**入站：**
- 斜杠指令（/帮助 /生图 /识图 /生日 /下载 /反馈 /睡觉 /起床 /预算 /状态 /重置）
- 兴趣过滤（词库 + LLM 语义，未@消息判断是否值得回复）
- 作息睡眠门控（00:00-07:30 静音，被@迷糊回应）
- 群精力曲线调制回复频率
- 成员画像 hook（消息流水，cron 聚合）
- announce 主动消息（到点任务发群）

**出站：**
- 占位提示（"收到啦！让 Yuro 想想喵~"）
- 思考摘要（💭 引用块）
- markdown 降级（QQ 不支持表格/图片）
- 回复延迟模拟（真人节奏）

## 应用方法

DSH profile 通过 pnpm patch 应用（`pnpm.onlyBuiltDependencies` / patches 机制），或手动 `patch -p1 < dsh-qqbot-yuro.patch`（在 `node_modules/@tencent-connect/dsh-qqbot` 目录内）。

> ⚠️ patch 依赖 `@tencent-connect/dsh-qqbot` 的具体版本（当前基准 v0.4.0）。升级上游后可能需 rebase。
> ⚠️ patch 内路径使用 `<USER>` / `<WORK_DIR>` 占位符，应用前替换为你的实际用户名与工作区目录名。

## 长期方向

我们希望上游 `tencent-connect/dsh-qqbot` 暴露**消息中间件注册点**（第三方插件可 `ctx` 注册入站中间件），届时本目录的入站机制可全部插件化，不再需要 patch。见仓库 README「贡献」一节。
