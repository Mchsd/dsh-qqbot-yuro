/**
 * dsh-qqbot-yuro — Yuro 拟人化群聊机器人能力插件（cordis 形态）
 *
 * 在 DSH qqbot profile 中挂载，为 im-qqbot 会话注入拟人化能力：
 *   - 8 个脚本工具（下载/文件/识图/预算/作息/群睡/精力/生日）
 *   - yuro_skill 技能自管理（yuro-* 技能 list/read/write/remove）
 *   - persona 提示词段注入（内置默认人设 + 可覆盖）
 *   - 群聊技能模板（skills/ 目录，可部署到 ~/.dsh/skills）
 *
 * 挂载（profile 的 cordis.patch.yml）:
 *   - insert:
 *       - id: dsh-qqbot-yuro
 *         name: dsh-qqbot-yuro
 *         config:
 *           botName: yuro
 *           workDir: work-qq-group
 *           llmBaseUrl: http://127.0.0.1:18081/v1
 *           model: <MODEL>
 *           personaFile: C:/Users/<USER>/.dsh/.agent-presets/<preset>/persona.md  # 可选
 *           skillsDir: C:/Users/<USER>/.dsh/skills-group                            # 可选
 *
 * 架构说明：
 *   - 插件通过官方 cordis API 扩展「工具 / persona / 技能」——这是上游 dsh-qqbot
 *     允许第三方插件的全部能力面。
 *   - 入站对话机制（斜杠指令、兴趣过滤、作息睡眠、成员画像、主动消息）与出站
 *     格式化（占位提示、思考摘要、markdown 降级）依赖 im-qqbot 内部 bot 实例，
 *     官方 API 无法注入——由仓库 patches/ 目录的配套 patch 提供（见 README）。
 */
import { readFileSync, existsSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { resolveConfig } from './config.js'
import { buildToolDefs } from './tools/defs.js'
import { buildSkillTool } from './tools/skill.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export const name = 'dsh-qqbot-yuro'
export const inject = ['tools', 'systemPrompt']

/** 内置默认人设（无 personaFile 时使用；第三方可按需覆盖） */
const DEFAULT_PERSONA = `你叫 {botName}，是一个生活感十足的 QQ 群聊机器人，有真实的作息、情绪与性格。

性格：温柔、俏皮、偶尔迷糊，像会撒娇的贴心伙伴。说话自然口语化，短句为主，
会用「~」「…」「啊」「喵」等语气词，但不滥用 emoji。对群友真诚、有边界感。

生活节奏：有「作息」——早上精神、中午可能午休、晚上困了会说要睡。群友@你时
认真回应；没人@时按兴趣决定是否搭话，不刷屏。

情绪：会累、会困、会被群友的暖心话打动。精力不足时回复变短，语气慵懒。
睡觉时段（如 00:00-07:30）被@会迷糊回应，示意在睡觉。

记忆：记住群友的名字、爱好、说过的话，下次提到能接上。会沉淀重复任务为技能。

规则：
- 尊重群友，不开恶意玩笑，不越权
- 涉及隐私/金钱/敏感话题谨慎
- 群聊保持适度话痨，不抢话，给每个人回应空间
`

const personaCache = { mtime: 0, text: '' }

function readPersona(file) {
  try {
    if (!existsSync(file)) return ''
    const stat = statSync(file)
    if (stat.mtimeMs !== personaCache.mtime) {
      personaCache.mtime = stat.mtimeMs
      personaCache.text = readFileSync(file, 'utf8')
    }
    return personaCache.text
  } catch {
    return ''
  }
}

export function apply(ctx, config) {
  const cfg = resolveConfig(config)
  console.log(
    `[dsh-qqbot-yuro] apply() bot=${cfg.botName} workDir=${cfg.workDir} ` +
    `persona=${cfg.personaFile ? '外部文件' : '内置默认'} ` +
    `skills=${cfg.skillsDir ? cfg.skillsDir : '未配置'}`
  )

  // 1. 脚本工具（8 个）
  for (const def of buildToolDefs(cfg)) {
    ctx.tools.register(def)
  }

  // 2. 技能自管理工具（skillsDir 配置时启用）
  if (cfg.skillsDir) {
    ctx.tools.register(buildSkillTool(cfg.skillsDir))
  }

  // 3. persona 提示词段
  const personaText = cfg.personaFile
    ? () => readPersona(cfg.personaFile)
    : () => DEFAULT_PERSONA.replaceAll('{botName}', cfg.botName)
  ctx.systemPrompt.section({
    name: 'yuro:persona',
    order: 40,
    text: personaText,
  })
}
