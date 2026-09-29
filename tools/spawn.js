/**
 * python 脚本安全调用封装。
 * - spawnSync 直传 argv（不经 shell，无命令注入面）
 * - argv 白名单字符集（沿用 sandbox-tools ARG_SAFE 放宽版）
 * - 通过环境变量向脚本注入插件配置（workDir / llmBaseUrl / model），
 *   脚本侧 yuro_layers.py 优先读取，实现「配置驱动」而非硬编码路径
 * - 超时 + 输出截断
 */
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ARG_SAFE = /^[A-Za-z0-9_\-./:?&=#%+@~ ]+$/

export function scriptDir() {
  return path.join(__dirname, 'scripts')
}

export function validateArg(arg) {
  const s = String(arg ?? '')
  if (!ARG_SAFE.test(s)) {
    throw new Error(`参数包含非法字符: ${s.slice(0, 40)}`)
  }
  return s
}

/** 构造注入给脚本的环境变量（插件配置 → 脚本可见） */
export function buildScriptEnv(config, baseEnv = process.env) {
  const env = { ...baseEnv }
  if (config.workDir) env.YURO_WORK_DIR = config.workDir
  if (config.llmBaseUrl) env.YURO_LLM_BASE_URL = config.llmBaseUrl
  if (config.model && config.model !== '<MODEL>') env.YURO_MODEL = config.model
  if (config.a2aBridgeDir) env.A2A_BRIDGE_DIR = config.a2aBridgeDir
  return env
}

function runImpl(script, args, config, timeoutMs, validate) {
  const safeArgs = validate ? args.map(validateArg) : args.map((a) => String(a))
  const fullArgs = [path.join(scriptDir(), script), ...safeArgs]
  const start = Date.now()
  const r = spawnSync(config.pythonPath, fullArgs, {
    timeout: timeoutMs,
    maxBuffer: 2 * 1024 * 1024,
    encoding: 'utf8',
    env: buildScriptEnv(config),
    windowsHide: true,
  })
  const out = (r.stdout || '').toString().trim()
  const err = (r.stderr || '').toString().trim()
  const truncated = out.length > config.maxOutputChars
    ? out.slice(0, config.maxOutputChars) + '\n...[截断]'
    : out
  return {
    ok: r.status === 0 && !r.error,
    code: r.status,
    stdout: truncated,
    stderr: err.slice(0, 800),
    ms: Date.now() - start,
    timedOut: r.error?.code === 'ETIMEDOUT' || r.signal === 'SIGTERM',
  }
}

/**
 * @param {string} script 脚本文件名（scripts/ 下）
 * @param {string[]} args 位置参数（已校验）
 * @param {object} config resolveConfig 结果
 */
export function runPython(script, args, config) {
  return runImpl(script, args, config, config.scriptTimeoutMs, true)
}

/**
 * raw 版：argv 不过白名单（消息类参数可含中文/引号）。
 * spawnSync 数组直传不经 shell，无命令注入面；仅用于 A2A 等消息型工具。
 * @param {object} opts { timeoutMs?: number }
 */
export function runPythonRaw(script, args, config, opts = {}) {
  return runImpl(script, args, config, opts.timeoutMs ?? config.scriptTimeoutMs, false)
}
