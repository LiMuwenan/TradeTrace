import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchIndexKline, fetchKline, fetchSnapshot, searchStocks } from './market'

const BASE = 'http://192.168.1.10:8000'

function ok(body: unknown) {
  return { ok: true, status: 200, text: async () => JSON.stringify(body) } as unknown as Response
}

describe('market api', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('快照请求命中协议路径', async () => {
    const fetchMock = vi.fn(async (_url: string) =>
      ok({ schemaVersion: 1, generatedAt: '2026-10-25T02:30:00Z', count: 0, stocks: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const out = await fetchSnapshot(BASE)
    expect(out.count).toBe(0)
    expect(fetchMock.mock.calls[0][0]).toBe(`${BASE}/api/v1/market/stocks/snapshot`)
  })

  it('搜索参数做 URL 编码并跳过空关键词', async () => {
    const fetchMock = vi.fn(async (_url: string) => ok({ schemaVersion: 1, count: 0, items: [] }))
    vi.stubGlobal('fetch', fetchMock)
    await searchStocks(BASE, '贵州 茅台', { limit: 20 })
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${BASE}/api/v1/market/stocks?q=${encodeURIComponent('贵州 茅台')}&limit=20`,
    )
    expect(await searchStocks(BASE, '  ')).toEqual([])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('K 线区间参数拼装正确', async () => {
    const fetchMock = vi.fn(async (_url: string) =>
      ok({
        schemaVersion: 1,
        code: '600519',
        market: 'SH',
        raw: { dates: [], open: [], high: [], low: [], close: [], volume: [] },
        qfq: { dates: [], open: [], high: [], low: [], close: [], volume: [] },
        hfq: { dates: [], open: [], high: [], low: [], close: [], volume: [] },
      }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchKline(BASE, '600519', { from: '2026-01-01', to: '2026-10-25' })
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${BASE}/api/v1/market/stocks/600519/kline?from=2026-01-01&to=2026-10-25`,
    )
  })

  it('指数 K 线按协议路径拼装并解析平铺响应', async () => {
    const fetchMock = vi.fn(async (_url: string) =>
      ok({
        schemaVersion: 1,
        code: 'sh000300',
        name: '沪深300',
        market: 'SH',
        dates: ['2026-01-02'],
        open: [3960],
        high: [4001.2],
        low: [3950.1],
        close: [3980.12],
        volume: [123456789],
      }))
    vi.stubGlobal('fetch', fetchMock)
    const out = await fetchIndexKline(BASE, 'sh000300', {
      from: '2026-01-01',
      to: '2026-10-25',
    })
    expect(fetchMock.mock.calls[0][0]).toBe(
      `${BASE}/api/v1/market/index/sh000300/kline?from=2026-01-01&to=2026-10-25`,
    )
    expect(out.schemaVersion).toBe(1)
    expect(out.code).toBe('sh000300')
    expect(out.name).toBe('沪深300')
    expect(out.market).toBe('SH')
    expect(out.dates).toEqual(['2026-01-02'])
    expect(out.open).toEqual([3960])
    expect(out.high).toEqual([4001.2])
    expect(out.low).toEqual([3950.1])
    expect(out.close).toEqual([3980.12])
    expect(out.volume).toEqual([123456789])
  })
})
