# dsh-qqbot-yuro 🐳

**Yuro 拟人化 QQ 群聊机器人插件** —— 基于 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（DSH）qqbot 通道的 cordis 插件。

为 QQ 群聊 bot 注入拟人化生活感：**情绪 / 作息 / 精力 / 成员画像 / 兴趣过滤 / 预算 / 识图 / 下载 / 技能自进化** 等一整套能力。

> 本插件不含任何运行时的个人数据（人设、画像、记忆、密钥均不在仓库内，部署后由机器人自行积累）。

---

## 🧭 架构：插件能做什么 vs 需要 patch

探明上游 `@tencent-connect/dsh-qqbot`（v0.4.0）后，其第三方扩展面如下：

| 能力面 | 官方 API | 本插件承载 |
|---|---|---|
| **工具**（识图/下载/预算/作息/群睡/精力/生日/文件） | ✅ `ctx.tools.register` | ✅ `tools/` + `scripts/` |
| **技能自管理**（yuro-\* 技能 list/read/write/remove） | ✅ `ctx.tools` | ✅ `tools/skill.js` |
| **persona 提示词注入** | ✅ `systemPrompt.section` | ✅ `index.js`（内置默认人设 + 可覆盖） |
| **入站对话机制**（斜杠指令/兴趣过滤/作息睡眠门控/成员画像/主动消息） | ❌ 无扩展点 | ⚠️ 需 `patches/` 配套 patch |
| **出站格式化**（占位提示/思考摘要/markdown 降级/回复延迟） | ❌ 需 bot 实例，不可注入 | ⚠️ 需 `patches/` 配套 patch |

> **为什么**：上游 `im-qqbot` 插件把消息入站 `bot.on('message')` 与出站 `bot` 实例全部封装在插件内部，`inject` 仅暴露 `agents`，不注册消息事件、不提供中间件注册点。第三方插件无法经官方 API 拦截入站消息或拿到发送实例。因此**入站/出站机制由仓库 `patches/` 目录的 patch 提供**，插件本体通过官方 API 承载工具/技能/人设。

---

## 📦 目录结构

```
dsh-qqbot-yuro/
├── index.js           # cordis 插件入口（tools + skill + persona）
├── config.js          # 配置项
├── package.json
├── tools/             # 工具定义层（defs/spawn/skill）
│   ├── defs.js        #   8 个脚本工具注册
│   ├── spawn.js       #   python 安全调用封装（argv 白名单 + 配置注入）
│   └── skill.js       #   yuro-* 技能自管理工具
├── scripts/           # python 实现层（配置驱动，无硬编码路径）
│   ├── yuro_layers.py #   数据目录/网关解析（读插件注入的环境变量）
│   ├── yuro_budget.py #   每日 token 预算 + 精力联动 + 睡眠
│   ├── yuro_routine.py#   生活作息状态机
│   ├── yuro_group_sleep.py  # 单群临时睡眠
│   ├── yuro_group_energy.py # 群精力曲线
│   ├── yuro_image_describe.py # 图片识别（含反查）
│   ├── yuro_birthday.py #  群友生日祝福
│   ├── yuro_download.py #  下载到工作区
│   └── yuro_file_tools.py # 文件查看/搜索/转码
├── patches/           # 入站+出站机制 patch（配合 dsh-qqbot 使用）
│   └── dsh-qqbot-yuro.patch
└── skills/            # 群聊技能模板（可部署到 ~/.dsh/skills）
    ├── comfyui-image-gen/
    ├── sticker-sender/
    ├── yuro-download/
    ├── yuro-file-ops/
    └── yuro-self-evolve/
```

---

## 🚀 安装

### 前置
- Node.js ≥ 20，pnpm
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`npm install -g @deepseek-ai/dsh`）
- QQ 开放平台机器人账号 + `@tencent-connect/dsh-qqbot` 插件已装
- 可用的 LLM 网关（默认 `http://127.0.0.1:18081/v1`，OpenAI 兼容）

### 步骤

```bash
# 1. 添加插件
npx -p @deepseek-ai/dsh dsh plugin --profile qqbot add github:<your>/dsh-qqbot-yuro

# 2. 在 profile 的 cordis.patch.yml 挂载
#    - insert:
#        - id: dsh-qqbot-yuro
#          name: dsh-qqbot-yuro
#          config:
#            botName: yuro
#            workDir: work-qq-group
#            llmBaseUrl: http://127.0.0.1:18081/v1
#            model: <MODEL>

# 3. 应用入站/出站 patch（见 patches/README）
```

---

## ⚙️ 配置

| 配置项 | 默认 | 说明 |
|---|---|---|
| `botName` | `yuro` | 机器人名（影响 --bot 注入与内置人设） |
| `pythonPath` | `python` | python 可执行名/路径 |
| `workDir` | `work-qq-group` | 群聊工作区目录名（相对 `~/.dsh/`） |
| `llmBaseUrl` | `http://127.0.0.1:18081/v1` | LLM 网关（兴趣/识图/预算/反思共用） |
| `model` | `<MODEL>` | 群聊默认模型名（必填） |
| `personaFile` | 内置默认 | 可选：外部人设文件绝对路径 |
| `skillsDir` | 无 | 可选：yuro-\* 技能目录 |

**脚本环境变量**（由插件注入，脚本层读取，实现配置驱动）：
- `YURO_WORK_DIR` — 工作区目录名
- `YURO_LLM_BASE_URL` — LLM 网关
- `YURO_MODEL` — 模型名
- `YURO_NEWAPI_DB` — 可选：new-api 计费库路径（未配置则预算脚本跳过）

---

## 🛠️ 能力

### 工具（插件经官方 API 注册）
| 工具 | 说明 |
|---|---|
| `yuro_download` | 下载 http/https 到工作区 |
| `yuro_file_tools` | 工作区文件 info/head/tail/grep/count/convert |
| `yuro_image_describe` | 图片识别（full/lite/缓存） |
| `yuro_budget` | 今日 token 预算报告 |
| `yuro_routine` | 生活作息查看/切换 |
| `yuro_group_sleep` | 单群临时睡眠 |
| `yuro_group_energy` | 群精力查询 |
| `yuro_birthday` | 生日检查/列表 |
| `yuro_skill` | yuro-\* 技能自管理 |

### Persona（内置拟人化人设）
- 内置默认人设（情绪/作息/性格/边界），可 `personaFile` 覆盖
- 热更新重载（文件 mtime 感知）

### 入站/出站机制（patch 提供）
- 斜杠指令、兴趣过滤、作息睡眠门控、成员画像、主动消息、占位提示、markdown 降级

---

## 🤝 贡献

欢迎 Issue / PR。请注意：
1. 不提交任何真实密钥 / openid / 个人路径（仓库保持占位符约定）
2. commit message 用中性表述，不出现隐私相关术语
3. 涉及上游扩展点的能力，欢迎向上游 `tencent-connect/dsh-qqbot` 提 PR（当前最大诉求：暴露消息中间件注册点，让入站机制可插件化）

---

## 📄 License

[MIT](./LICENSE)。
