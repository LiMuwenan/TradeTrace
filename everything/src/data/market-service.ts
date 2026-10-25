import type { MarketApiError } from './api/client'
import { fetchHealth, fetchKline, fetchSnapshot, searchStocks } from './api/market'
import type { KlineResponse, MarketStock } from './api/market'
import {
  KLINE_TTL_MS,
  SNAPSHOT_TTL_MS,
  isFresh,
  klineKey,
  readCache,
  snapshotKey,
  writeCache,
} from './market-cache'
import { loadMarketConfig } from './market-config'

export interface StockDictionaryResult {
  stocks: MarketStock[]
  generatedAt: string
  fromCache: boolean
  /** true 表示本次展示的是过期缓存，页面必须提示「数据可能不是最新」 */
  stale: boolean
  /** 降级原因；网络正常时为空 */
  error: string
}

export interface KlineResult {
  data: KlineResponse
  fromCache: boolean
  stale: boolean
  error: string
}

function errorText(error: unknown): string {
  if (error instanceof Error) return error.message
  return '未知错误'
}

async function config() {
  return loadMarketConfig()
}

/**
 * 股票字典：TTL 内直接读缓存；否则联网刷新并回写。
 * 联网失败时回退旧缓存（stale=true），无缓存则抛出错误。
 */
export async function loadStockDictionary(options: { force?: boolean } = {}): Promise<StockDictionaryResult> {
  const cfg = await config()
  const cached = await readCache<{ generatedAt: string; stocks: MarketStock[] }>(snapshotKey())
  const fresh = cached !== null && isFresh(cached.savedAt, SNAPSHOT_TTL_MS)
  if (cached && fresh && !options.force) {
    return {
      stocks: cached.data.stocks,
      generatedAt: cached.data.generatedAt,
      fromCache: true,
      stale: false,
      error: '',
    }
  }
  try {
    const snapshot = await fetchSnapshot(cfg.baseUrl, { timeoutMs: cfg.timeoutMs })
    if (cfg.cacheEnabled) {
      await writeCache(snapshotKey(), { generatedAt: snapshot.generatedAt, stocks: snapshot.stocks }, new Date().toISOString())
    }
    return {
      stocks: snapshot.stocks,
      generatedAt: snapshot.generatedAt,
      fromCache: false,
      stale: false,
      error: '',
    }
  } catch (error) {
    if (cached) {
      return {
        stocks: cached.data.stocks,
        generatedAt: cached.data.generatedAt,
        fromCache: true,
        stale: true,
        error: errorText(error),
      }
    }
    throw error
  }
}

export async function searchMarketStocks(keyword: string): Promise<MarketStock[]> {
  const cfg = await config()
  return searchStocks(cfg.baseUrl, keyword, { timeoutMs: cfg.timeoutMs })
}

/** 日K：TTL 内读缓存；失败回退缓存并标记 stale */
export async function loadKline(
  code: string,
  from: string,
  to: string,
): Promise<KlineResult> {
  const cfg = await config()
  const key = klineKey(code, from, to)
  const cached = await readCache<KlineResponse>(key)
  if (cached && isFresh(cached.savedAt, KLINE_TTL_MS)) {
    return { data: cached.data, fromCache: true, stale: false, error: '' }
  }
  try {
    const data = await fetchKline(cfg.baseUrl, code, { from, to, timeoutMs: cfg.timeoutMs })
    if (cfg.cacheEnabled) await writeCache(key, data, new Date().toISOString())
    return { data, fromCache: false, stale: false, error: '' }
  } catch (error) {
    if (cached) {
      return { data: cached.data, fromCache: true, stale: true, error: errorText(error) }
    }
    throw error
  }
}

/** 连接测试：成功后回写 lastConnectedAt/lastHealthStatus */
export async function testMarketConnection(baseUrl?: string): Promise<{ ok: boolean; message: string }> {
  const cfg = await loadMarketConfig()
  const target = (baseUrl ?? cfg.baseUrl).trim()
  try {
    const health = await fetchHealth(target, { timeoutMs: cfg.timeoutMs })
    if (health.schemaVersion !== 1 || health.status !== 'ok') {
      return { ok: false, message: '服务响应异常：请确认这是 TradeTrace 行情服务' }
    }
    const { saveMarketConfig } = await import('./market-config')
    await saveMarketConfig({
      ...cfg,
      baseUrl: target.replace(/\/+$/, ''),
      lastConnectedAt: new Date().toISOString(),
      lastHealthStatus: 'ok',
    })
    return { ok: true, message: `连接成功（服务版本 ${health.version}）` }
  } catch (error) {
    const err = error as MarketApiError | Error
    return { ok: false, message: errorText(err) }
  }
}
