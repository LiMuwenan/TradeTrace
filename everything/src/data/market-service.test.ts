import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { store } = vi.hoisted(() => ({ store: new Map<string, string>() }))

vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {
    getItem: vi.fn(async (key: string) => store.get(key) ?? null),
    setItem: vi.fn(async (key: string, value: string) => {
      store.set(key, value)
    }),
    removeItem: vi.fn(async (key: string) => {
      store.delete(key)
    }),
  },
}))

vi.mock('./market-config', () => ({
  loadMarketConfig: vi.fn(),
  DEFAULT_MARKET_CONFIG: { baseUrl: '', timeoutMs: 8000, cacheEnabled: true, lastConnectedAt: '', lastHealthStatus: '' },
}))

import { loadMarketConfig } from './market-config'
import { loadKline, loadStockDictionary } from './market-service'

const BASE = 'http://192.168.1.10:8000'
const baseConfig = {
  baseUrl: BASE,
  timeoutMs: 8000,
  cacheEnabled: true,
  lastConnectedAt: '',
  lastHealthStatus: '' as const,
}

function ok(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) } as unknown as Response
}

describe('market-service', () => {
  beforeEach(() => {
    store.clear()
    vi.unstubAllGlobals()
    vi.useRealTimers()
    vi.mocked(loadMarketConfig).mockResolvedValue(baseConfig)
  })

  afterEach(() => vi.useRealTimers())

  it('命中新鲜缓存时不发请求', async () => {
    const fetchMock = vi.fn(async () =>
      ok({ schemaVersion: 1, generatedAt: '2026-10-25T00:00:00Z', count: 0, stocks: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const first = await loadStockDictionary()
    expect(first.fromCache).toBe(false)
    expect(fetchMock).toHaveBeenCalledTimes(1) // 首次无缓存 → 拉取

    const second = await loadStockDictionary()
    expect(second.fromCache).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('网络失败但有旧缓存时返回 stale，不抛错', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-25T00:00:00.000Z'))
    vi.stubGlobal('fetch', vi.fn(async () =>
      ok({ schemaVersion: 1, generatedAt: '2026-10-20T00:00:00Z', count: 1, stocks: [{ code: '600519', name: '贵州茅台', market: 'SH', industry: '' }] }),
    ))
    await loadStockDictionary()

    // 超过快照 TTL，缓存过期后会尝试联网；断网时回退旧缓存
    vi.setSystemTime(new Date('2026-11-10T00:00:00.000Z'))
    vi.mocked(loadMarketConfig).mockResolvedValue({ ...baseConfig, cacheEnabled: false })
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    const result = await loadStockDictionary()
    expect(result.stocks).toHaveLength(1)
    expect(result.stale).toBe(true)
    expect(result.error).toContain('无法连接')
  })

  it('未配置地址且无缓存时给出明确错误', async () => {
    vi.mocked(loadMarketConfig).mockResolvedValue({ ...baseConfig, baseUrl: '' })
    await expect(loadStockDictionary()).rejects.toMatchObject({ kind: 'config' })
  })

  it('K 线请求失败但有缓存时返回 stale', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-25T00:00:00.000Z'))
    vi.stubGlobal('fetch', vi.fn(async () =>
      ok({ schemaVersion: 1, code: '600519', market: 'SH', raw: { dates: ['2026-10-23'], open: [], high: [], low: [], close: [1], volume: [] }, qfq: { dates: [], open: [], high: [], low: [], close: [], volume: [] }, hfq: { dates: [], open: [], high: [], low: [], close: [], volume: [] } }),
    ))
    await loadKline('600519', '2026-10-01', '2026-10-25')

    // 超过日K TTL（12 小时），再次请求会联网；断网时回退旧缓存
    vi.setSystemTime(new Date('2026-10-26T00:00:00.000Z'))
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    const result = await loadKline('600519', '2026-10-01', '2026-10-25')
    expect(result.stale).toBe(true)
    expect(result.data.raw.dates).toEqual(['2026-10-23'])
  })
})
