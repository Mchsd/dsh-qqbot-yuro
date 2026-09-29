/**
 * dsh-tool-yuro 工具定义集中登记。
 * 每个工具 = 脚本包装（spawn python）+ 标准 JSON Schema 参数 + 输出渲染。
 * 统一注入 --bot <botName>（脚本侧消费配对，yuro_layers 分层）。
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { runPython, runPythonRaw } from './spawn.js'

const SCRIPT = {
  download: 'yuro_download.py',
  fileTools: 'yuro_file_tools.py',
  image: 'yuro_image_describe.py',
  budget: 'yuro_budget.py',
  routine: 'yuro_routine.py',
  groupSleep: 'yuro_group_sleep.py',
  groupEnergy: 'yuro_group_energy.py',
  birthday: 'yuro_birthday.py',
  a2a: 'yuro_a2a.py',
}

function jsonRender(_args, value) {
  const lines = [value.stdout || '(无输出)']
  if (value.stderr) lines.push('[stderr] ' + value.stderr)
  if (!value.ok) lines.push(`[exit=${value.code}${value.timedOut ? ' timeout' : ''} ms=${value.ms}]`)
  return [{ type: 'text', text: lines.join('\n') }]
}

function botArgs(config, ...rest) {
  return ['--bot', config.botName, ...rest]
}

export function buildToolDefs(config) {
  return [
    defineTool({
      name: 'yuro_download',
      description: '下载 http/https 文件到工作区 downloads/（≤20MB，30s 超时）。适合群友要文件/图片资源时使用。',
      parameters: {
        url: { type: 'string', required: true, description: '完整 http/https 链接' },
        filename: { type: 'string', description: '可选：指定保存文件名' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const a = [args.url]
        if (args.filename) a.push(args.filename)
        const r = runPython(SCRIPT.download, botArgs(config, ...a), config)
        return { ...r, stdout: r.stdout || '下载完成或失败，详见输出' }
      },
    }),

    defineTool({
      name: 'yuro_file_tools',
      description: '工作区文件操作：info(信息)/head/tail/grep/count/convert。仅限工作区与脚本目录内文件。',
      parameters: {
        command: { type: 'string', required: true, enum: ['info', 'head', 'tail', 'grep', 'count', 'convert'], description: '子命令' },
        file: { type: 'string', required: true, description: '工作区内文件路径（相对工作区或 scripts）' },
        extra: { type: 'string', description: '子命令参数（如 grep 关键词、head 行数）' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const a = [args.command, args.file]
        if (args.extra) a.push(args.extra)
        return runPython(SCRIPT.fileTools, botArgs(config, ...a), config)
      },
    }),

    defineTool({
      name: 'yuro_image_describe',
      description: '图片识别：描述图片内容（角色特征/场景），带缓存与反查。群友发图或问图里是什么时使用。',
      parameters: {
        image_path: { type: 'string', required: true, description: '图片本地路径（工作区 .qqbot/<msgId>/ 下）' },
        mode: { type: 'string', enum: ['full', 'lite', 'cache-only', 'cache-lite'], default: 'full', description: 'full=完整描述; lite=一句话; cache-only=只查缓存; cache-lite=轻量缓存' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const mode = args.mode || 'full'
        if (mode === 'cache-only') return runPython(SCRIPT.image, botArgs(config, '--read-cache-only', args.image_path), config)
        if (mode === 'cache-lite') return runPython(SCRIPT.image, botArgs(config, '--read-cache-lite', args.image_path), config)
        const a = [args.image_path]
        if (mode === 'lite') a.push('--lite')
        return runPython(SCRIPT.image, botArgs(config, ...a), config)
      },
    }),

    defineTool({
      name: 'yuro_budget',
      description: '查询今日 token 预算消耗（早 8 点起算周期）。群友问"今天花了多少/还有多少精力"时使用。',
      parameters: {
        action: { type: 'string', enum: ['report', 'check'], default: 'report', description: 'report=详细汇报; check=静默检查' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const a = args.action === 'check' ? [] : ['report']
        return runPython(SCRIPT.budget, botArgs(config, ...a), config)
      },
    }),

    defineTool({
      name: 'yuro_routine',
      description: '生活作息：查看当前阶段或手动切换（sleep/wake/work_morning/lunch/nap 等）。保持回复有生活感。',
      parameters: {
        action: { type: 'string', enum: ['status', 'force'], required: true, description: 'status=查看当前阶段; force=强制切换' },
        stage: { type: 'string', description: 'force 时的目标阶段（sleep/wake/work_morning/lunch/nap/work_afternoon/dinner/evening/winding）' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        if (args.action === 'force') {
          if (!args.stage) return { ok: false, stdout: 'force 需要 stage 参数' }
          return runPython(SCRIPT.routine, botArgs(config, 'force', args.stage), config)
        }
        return runPython(SCRIPT.routine, botArgs(config, 'status'), config)
      },
    }),

    defineTool({
      name: 'yuro_group_sleep',
      description: '单群临时睡眠管理：sleep=睡到明早7:30（该群完全安静）; wake=提前叫醒; check=查状态。',
      parameters: {
        action: { type: 'string', required: true, enum: ['sleep', 'wake', 'check'], description: '子命令' },
        group: { type: 'string', description: '群标识（缺省用最近活跃群）' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const a = [args.action]
        if (args.group) a.push(args.group)
        return runPython(SCRIPT.groupSleep, botArgs(config, ...a), config)
      },
    }),

    defineTool({
      name: 'yuro_group_energy',
      description: '查询某群当前精力百分比（睡眠/清醒的 U 型曲线调制）。回复节奏参考它。',
      parameters: {
        group: { type: 'string', description: '群标识（缺省用最近活跃群）' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const a = ['status']
        if (args.group) a.push(args.group)
        return runPython(SCRIPT.groupEnergy, botArgs(config, ...a), config)
      },
    }),

    defineTool({
      name: 'yuro_birthday',
      description: '生日管理：check=今天有没有群友生日（命中自动发祝福）; list=列出全部登记生日。',
      parameters: {
        action: { type: 'string', enum: ['check', 'list'], default: 'check' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        return runPython(SCRIPT.birthday, botArgs(config, args.action || 'check'), config)
      },
    }),

    defineTool({
      name: 'yuro_a2a',
      description: '与 Hermes(Merce) 进行 A2A 信封对话：把消息发给 Hermes 并返回她的回复。适合需要跨 agent 协作/询问 Hermes 时使用。需配置 a2aBridgeDir。',
      parameters: {
        message: { type: 'string', required: true, description: '要发给 Hermes 的消息内容' },
        conversation: { type: 'string', description: '对话 ID（缺省 dsh-hermes-default，固定对话可延续上下文）' },
      },
      output: { schema: { type: 'json' }, render: jsonRender },
      async execute(args) {
        const a = [args.message]
        if (args.conversation) a.push(args.conversation)
        return runPythonRaw(SCRIPT.a2a, a, config, { timeoutMs: 320000 })
      },
    }),
  ]
}
