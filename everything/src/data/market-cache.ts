import AsyncStorage from '@react-native-async-storage/async-storage'

const PREFIX = 'tradetrace/market/cache/v1/'
export const SNAPSHOT_TTL_MS = 7 * 24 * 60 * 60 * 1000
export const KLINE_TTL_MS = 12 * 60 * 60 * 1000

export interface CacheEntry<T> {
  savedAt: string
  data: T
}

function storageKey(key: string): string {
  return `${PREFIX}${key}`
}

export async function readCache<T>(key: string): Promise<CacheEntry<T> | null> {
  try {
    const raw = await AsyncStorage.getItem(storageKey(key))
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const entry = parsed as { savedAt?: unknown; data?: unknown }
    if (typeof entry.savedAt !== 'string' || entry.data === undefined) return null
    return { savedAt: entry.savedAt, data: entry.data as T }
  } catch (error) {
    console.warn('[TradeTrace] 读取行情缓存失败', error)
    return null
  }
}

export async function writeCache<T>(key: string, data: T, now: string): Promise<void> {
  try {
    await AsyncStorage.setItem(storageKey(key), JSON.stringify({ savedAt: now, data }))
  } catch (error) {
    console.warn('[TradeTrace] 写入行情缓存失败', error)
  }
}

export function isFresh(savedAt: string, ttlMs: number, nowMs: number = Date.now()): boolean {
  const saved = Date.parse(savedAt)
  if (!Number.isFinite(saved)) return false
  return nowMs - saved <= ttlMs
}

export function snapshotKey(): string {
  return 'stocks/snapshot'
}

export function klineKey(code: string, from: string, to: string): string {
  return `kline/${code}/${from || 'all'}_${to || 'all'}`
}
