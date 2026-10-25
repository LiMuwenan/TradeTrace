import { requestJson } from './client'
import type { RequestOptions } from './client'

export interface MarketStock {
  code: string
  name: string
  market: 'SH' | 'SZ' | 'BJ'
  industry: string
}

export interface StockSnapshot {
  schemaVersion: number
  generatedAt: string
  count: number
  stocks: MarketStock[]
}

export interface StockSearchResult {
  schemaVersion: number
  count: number
  items: MarketStock[]
}

export interface KlineSeries {
  dates: string[]
  open: number[]
  high: number[]
  low: number[]
  close: number[]
  volume: number[]
}

export interface KlineResponse {
  schemaVersion: number
  code: string
  market: string
  raw: KlineSeries
  qfq: KlineSeries
  hfq: KlineSeries
}

export interface HealthResponse {
  schemaVersion: number
  status: string
  name: string
  version: string
  serverTime: string
}

export interface DatasetItem {
  name: string
  type: string
  latestDataDate: string
  lagDays: number | null
  fileCount: number
}

export interface DatasetsResponse {
  schemaVersion: number
  generatedAt: string
  items: DatasetItem[]
}

function query(params: Record<string, string | number | undefined>): string {
  const pairs = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== '')
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
  return pairs.length ? `?${pairs.join('&')}` : ''
}

export async function fetchHealth(
  baseUrl: string,
  options: RequestOptions = {},
): Promise<HealthResponse> {
  return requestJson<HealthResponse>(baseUrl, '/api/v1/health', options)
}

export async function fetchSnapshot(
  baseUrl: string,
  options: RequestOptions = {},
): Promise<StockSnapshot> {
  return requestJson<StockSnapshot>(baseUrl, '/api/v1/market/stocks/snapshot', options)
}

/** 关键词为空时直接返回空数组，不发请求（避免拉全表） */
export async function searchStocks(
  baseUrl: string,
  keyword: string,
  options: RequestOptions & { limit?: number } = {},
): Promise<MarketStock[]> {
  const q = keyword.trim()
  if (!q) return []
  const path = `/api/v1/market/stocks${query({ q, limit: options.limit })}`
  const result = await requestJson<StockSearchResult>(baseUrl, path, options)
  return result.items
}

export async function fetchKline(
  baseUrl: string,
  code: string,
  options: RequestOptions & { from?: string; to?: string } = {},
): Promise<KlineResponse> {
  const path = `/api/v1/market/stocks/${encodeURIComponent(code)}/kline${query({
    from: options.from,
    to: options.to,
  })}`
  return requestJson<KlineResponse>(baseUrl, path, options)
}

export async function fetchDatasets(
  baseUrl: string,
  options: RequestOptions = {},
): Promise<DatasetsResponse> {
  return requestJson<DatasetsResponse>(baseUrl, '/api/v1/market/datasets', options)
}
