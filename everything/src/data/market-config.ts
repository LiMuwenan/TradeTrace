import AsyncStorage from '@react-native-async-storage/async-storage'

/** 行情服务配置：地址由用户在设置页填写，不在代码里写死 */
export interface MarketConfig {
  /** 形如 http://192.168.1.10:8000，不含末尾斜杠与 /api/v1 */
  baseUrl: string
  timeoutMs: number
  cacheEnabled: boolean
  /** 最近一次连接测试成功时间（ISO） */
  lastConnectedAt: string
  /** 最近一次连接测试结果 */
  lastHealthStatus: 'ok' | 'fail' | ''
}

const STORAGE_KEY = 'tradetrace/market/v1'
export const DEFAULT_TIMEOUT_MS = 8000

export const DEFAULT_MARKET_CONFIG: MarketConfig = {
  baseUrl: '',
  timeoutMs: DEFAULT_TIMEOUT_MS,
  cacheEnabled: true,
  lastConnectedAt: '',
  lastHealthStatus: '',
}

export function normalizeMarketUrl(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, '')
  return trimmed.replace(/\/api\/v1$/i, '')
}

/** 校验并返回归一化地址；Android 的 localhost 指向手机自身，直接拦下 */
export function validateMarketUrl(raw: string): string {
  const url = normalizeMarketUrl(raw)
  if (!url) throw new Error('请填写行情服务地址')
  if (!/^https?:\/\//i.test(url)) throw new Error('地址必须以 http:// 或 https:// 开头')
  if (/^https?:\/\/localhost/i.test(url)) {
    throw new Error('Android 端 localhost 指向手机自身，请填写电脑的局域网 IP')
  }
  return url
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export async function loadMarketConfig(): Promise<MarketConfig> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_MARKET_CONFIG }
    const parsed: unknown = JSON.parse(raw)
    if (!isRecord(parsed)) return { ...DEFAULT_MARKET_CONFIG }
    return {
      baseUrl: typeof parsed.baseUrl === 'string' ? parsed.baseUrl : '',
      timeoutMs: typeof parsed.timeoutMs === 'number' ? parsed.timeoutMs : DEFAULT_TIMEOUT_MS,
      cacheEnabled: parsed.cacheEnabled !== false,
      lastConnectedAt: typeof parsed.lastConnectedAt === 'string' ? parsed.lastConnectedAt : '',
      lastHealthStatus:
        parsed.lastHealthStatus === 'ok' || parsed.lastHealthStatus === 'fail'
          ? parsed.lastHealthStatus
          : '',
    }
  } catch (error) {
    console.warn('[TradeTrace] 读取行情服务配置失败', error)
    return { ...DEFAULT_MARKET_CONFIG }
  }
}

export async function saveMarketConfig(next: MarketConfig): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}
