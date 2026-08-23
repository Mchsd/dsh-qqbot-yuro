/**
 * yuro_skill — yuro-* 技能自管理工具（迁移 sandbox self_skill 到插件形态）
 * 规则（沿蓝侧 self_skill 铁律）:
 *   - 仅 skills-group 下 yuro-* 前缀技能
 *   - write 内容 ≤8KB，需 frontmatter
 *   - remove 只删 yuro-* 技能目录
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs'
import path from 'node:path'

const MAX_BYTES = 8 * 1024
const FRONTMATTER_RE = /^---[\s\S]*?---/

function safeSkillName(name) {
  const s = String(name ?? '').trim()
  if (!/^yuro-[A-Za-z0-9_-]+$/.test(s)) return null
  return s
}

export function buildSkillTool(skillsDir) {
  const dir = path.resolve(skillsDir)

  function skillPath(skillName) {
    return path.join(dir, skillName, 'SKILL.md')
  }

  function listSkills() {
    if (!existsSync(dir)) return []
    return readdirSync(dir)
      .filter((d) => /^yuro-/.test(d) && existsSync(path.join(dir, d, 'SKILL.md')))
      .sort()
  }

  function readSkill(skillName) {
    const p = skillPath(skillName)
    if (!existsSync(p)) return null
    return readFileSync(p, 'utf8')
  }

  function writeSkill(skillName, content) {
    const text = String(content ?? '')
    if (Buffer.byteLength(text, 'utf8') > MAX_BYTES) {
      return { ok: false, message: `内容超 8KB（${(Buffer.byteLength(text, 'utf8') / 1024).toFixed(1)}KB），请精简` }
    }
    if (!FRONTMATTER_RE.test(text)) {
      return { ok: false, message: '技能需 frontmatter（--- 开头块，含 name/description）' }
    }
    const skillDir = path.join(dir, skillName)
    mkdirSync(skillDir, { recursive: true })
    writeFileSync(path.join(skillDir, 'SKILL.md'), text, 'utf8')
    return { ok: true, message: `已写入技能 ${skillName}` }
  }

  function removeSkill(skillName) {
    const skillDir = path.join(dir, skillName)
    if (!existsSync(path.join(skillDir, 'SKILL.md'))) {
      return { ok: false, message: `技能 ${skillName} 不存在` }
    }
    rmSync(skillDir, { recursive: true, force: true })
    return { ok: true, message: `已移除技能 ${skillName}` }
  }

  return defineTool({
    name: 'yuro_skill',
    description:
      '管理自己的 yuro-* 技能（list/read/write/remove）。重复出现 2-3 次的任务可沉淀为技能；' +
      '仅 yuro- 前缀；write 需 frontmatter 且 ≤8KB。技能是自我进化的载体。',
    parameters: {
      action: { type: 'string', required: true, enum: ['list', 'read', 'write', 'remove'], description: '子命令' },
      name: { type: 'string', description: '技能名（yuro-xxx；list 时省略）' },
      content: { type: 'string', description: 'write 时的完整 SKILL.md 内容（含 frontmatter）' },
    },
    output: {
      schema: { type: 'json' },
      render: (_args, value) => [{ type: 'text', text: value.message || value.stdout || '(无输出)' }],
    },
    async execute(args) {
      try {
        switch (args.action) {
          case 'list': {
            const skills = listSkills()
            return { ok: true, message: skills.length ? '已安装技能:\n- ' + skills.join('\n- ') : '暂无 yuro-* 技能' }
          }
          case 'read': {
            const n = safeSkillName(args.name)
            if (!n) return { ok: false, message: '技能名需 yuro- 前缀' }
            const text = readSkill(n)
            return text ? { ok: true, message: text } : { ok: false, message: `技能 ${n} 不存在` }
          }
          case 'write': {
            const n = safeSkillName(args.name)
            if (!n) return { ok: false, message: '技能名需 yuro- 前缀' }
            if (!args.content) return { ok: false, message: 'content 为空' }
            return writeSkill(n, args.content)
          }
          case 'remove': {
            const n = safeSkillName(args.name)
            if (!n) return { ok: false, message: '技能名需 yuro- 前缀' }
            return removeSkill(n)
          }
          default:
            return { ok: false, message: '未知 action' }
        }
      } catch (error) {
        return { ok: false, message: `yuro_skill 执行失败: ${error?.message ?? error}` }
      }
    },
  })
}
