/**
 * dsh-qqbot-yuro 配置项（宽松解析，缺省走默认值）
 *
 * cordis.patch.yml 挂载：
 *   - id: dsh-qqbot-yuro
 *     name: dsh-qqbot-yuro
 *     config:
 *       botName: yuro           # 机器人名字（影响 --bot 注入与占位提示）
 *       pythonPath: python      # python 可执行名/路径
 *       workDir: work-qq-group  # 群聊工作区目录名（相对 ~/.dsh/）
 *       llmBaseUrl: http://127.0.0.1:18081/v1   # LLM 网关（兴趣判断/识图/预算共用）
 *       model: <MODEL>          # 群聊默认模型名
 *       personaFile: null       # 可选：人设文件绝对路径（systemPrompt 注入）
 *       skillsDir: null         # 可选：yuro-* 技能目录（技能自管理工具用）
 */

export const DEFAULTS = {
  botName: 'yuro',
  pythonPath: 'python',
  workDir: 'work-qq-group',
  llmBaseUrl: 'http://127.0.0.1:18081/v1',
  model: '<MODEL>',
  personaFile: null,
  skillsDir: null,
  scriptTimeoutMs: 60000,
  maxOutputChars: 4000,
}

export function resolveConfig(raw = {}) {
  const c = { ...DEFAULTS, ...(raw ?? {}) }
  if (typeof c.botName !== 'string' || !/^[A-Za-z0-9_-]+$/.test(c.botName)) {
    console.warn('[dsh-qqbot-yuro] botName 非法，回退 yuro:', c.botName)
    c.botName = 'yuro'
  }
  return c
}
