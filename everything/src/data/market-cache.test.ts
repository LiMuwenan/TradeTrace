import { beforeEach, describe, expect, it, vi } from 'vitest'

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

import { klineKey, readCache, SNAPSHOT_TTL_MS, isFresh, writeCache } from './market-cache'

describe('market-cache', () => {
  beforeEach(() => store.clear())

  it('写入后可读回', async () => {
    await writeCache('stocks/snapshot', { stocks: [] }, '2026-10-25T00:00:00.000Z')
    const entry = await readCache<{ stocks: unknown[] }>('stocks/snapshot')
    expect(entry?.data).toEqual({ stocks: [] })
    expect(entry?.savedAt).toBe('2026-10-25T00:00:00.000Z')
  })

  it('损坏缓存返回 null', async () => {
    store.set('tradetrace/market/cache/v1/stocks/snapshot', '{bad')
    expect(await readCache('stocks/snapshot')).toBeNull()
  })

  it('TTL 判定按保存时间计算', () => {
    const now = Date.parse('2026-10-25T00:00:00.000Z')
    expect(isFresh('2026-10-24T00:00:00.000Z', SNAPSHOT_TTL_MS, now)).toBe(true)
    expect(isFresh('2026-10-01T00:00:00.000Z', SNAPSHOT_TTL_MS, now)).toBe(false)
  })

  it('K线缓存键包含代码与区间', () => {
    expect(klineKey('600519', '2026-01-01', '2026-10-25')).toBe(
      'kline/600519/2026-01-01_2026-10-25',
    )
  })
})
