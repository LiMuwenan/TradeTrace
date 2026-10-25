/** 行情请求错误分类：页面据此给出可执行提示，不暴露底层细节 */
export type MarketErrorKind = 'config' | 'network' | 'timeout' | 'http' | 'business' | 'parse'

export class MarketApiError extends Error {
  readonly kind: MarketErrorKind
  readonly code: string
  readonly status: number

  constructor(kind: MarketErrorKind, message: string, options: { code?: string; status?: number } = {}) {
    super(message)
    this.name = 'MarketApiError'
    this.kind = kind
    this.code = options.code ?? ''
    this.status = options.status ?? 0
  }
}

export interface RequestOptions {
  timeoutMs?: number
  signal?: AbortSignal
}

const DEFAULT_TIMEOUT_MS = 8000

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * 统一 JSON 请求：超时、网络、HTTP、业务、解析五类错误都归一为 MarketApiError。
 * baseUrl 由设置页提供，path 必须是 /api/v1 开头的绝对路径。
 */
export async function requestJson<T>(
  baseUrl: string,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const base = baseUrl.trim().replace(/\/+$/, '')
  if (!base) {
    throw new MarketApiError('config', '尚未配置行情服务地址，请到设置页填写')
  }
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(`${base}${path}`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal: options.signal ?? controller.signal,
    })
    const text = await response.text()
    let body: unknown = null
    if (text) {
      try {
        body = JSON.parse(text)
      } catch {
        if (!response.ok) {
          throw new MarketApiError('http', `服务返回 ${response.status}`, { status: response.status })
        }
        throw new MarketApiError('parse', '服务返回内容不是合法 JSON')
      }
    }
    if (!response.ok) {
      const payload = isRecord(body) ? body : null
      const code = payload && typeof payload.code === 'string' ? payload.code : `HTTP_${response.status}`
      const message =
        payload && typeof payload.message === 'string'
          ? payload.message
          : `请求失败（HTTP ${response.status}）`
      throw new MarketApiError('business', message, { code, status: response.status })
    }
    return body as T
  } catch (error) {
    if (error instanceof MarketApiError) throw error
    if (error instanceof Error && error.name === 'AbortError') {
      throw new MarketApiError('timeout', '连接超时：请确认服务已启动且手机与电脑在同一局域网')
    }
    throw new MarketApiError('network', '无法连接行情服务：请检查地址、Wi-Fi 与防火墙')
  } finally {
    clearTimeout(timer)
  }
}
