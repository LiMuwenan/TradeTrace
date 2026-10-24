import AsyncStorage from '@react-native-async-storage/async-storage'

import { detectStateVersion, normalizeState } from './migrate'
import { loadRawState, saveRawState } from './storage'
import { createDeviceId, loadSyncConfig } from './sync-config'
import type { MergeConflict } from './merge'
import { createEmptyState } from './types'
import type { TradeState } from './types'

/** 冲突日志：只保留最近 50 条，避免无限增长 */
const CONFLICT_KEY = 'tradetrace/conflicts/v1'
const CONFLICT_LIMIT = 50

export interface ConflictLogEntry extends MergeConflict {
  at: string
}

function nowIso(): string {
  return new Date().toISOString()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isConflictEntry(value: unknown): value is ConflictLogEntry {
  if (!isRecord(value)) return false
  return (
    typeof value.entity === 'string' &&
    typeof value.id === 'string' &&
    typeof value.localUpdatedAt === 'string' &&
    typeof value.remoteUpdatedAt === 'string' &&
    (value.winner === 'local' || value.winner === 'remote') &&
    typeof value.at === 'string'
  )
}

/**
 * 加载 → 迁移/校验 → 必要时写回 v2。
 * 数据损坏或版本无法识别时只返回空状态且不写盘，避免覆盖仍可能恢复的原始数据。
 */
export async function loadState(): Promise<TradeState> {
  const config = await loadSyncConfig()
  const deviceId = config.deviceId || createDeviceId()
  const now = nowIso()
  const raw = await loadRawState()

  if (raw.status === 'corrupt') {
    console.warn('[TradeTrace] 本地数据无法解析，已跳过写盘以免覆盖原始数据')
    return createEmptyState(deviceId, now)
  }

  const data = raw.status === 'ok' ? raw.data : null
  const version = detectStateVersion(data)
  if (raw.status === 'ok' && version === null) {
    console.warn('[TradeTrace] 本地数据版本无法识别，已跳过写盘以免覆盖原始数据')
    return createEmptyState(deviceId, now)
  }

  const state = normalizeState(data, deviceId, now)
  const record = isRecord(data) ? data : null
  const needsWrite =
    raw.status === 'empty' ||
    version === 1 ||
    (version === 2 && (!record || record.deviceId !== state.deviceId))
  if (needsWrite) await saveRawState(state)
  return state
}

export async function saveState(state: TradeState): Promise<void> {
  await saveRawState(state)
}

export async function loadConflictLog(): Promise<ConflictLogEntry[]> {
  try {
    const raw = await AsyncStorage.getItem(CONFLICT_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isConflictEntry)
  } catch (error) {
    console.warn('[TradeTrace] 读取冲突日志失败', error)
    return []
  }
}

function sameConflict(a: MergeConflict, b: MergeConflict): boolean {
  return (
    a.entity === b.entity &&
    a.id === b.id &&
    a.localUpdatedAt === b.localUpdatedAt &&
    a.remoteUpdatedAt === b.remoteUpdatedAt
  )
}

/** 新冲突写在前，最多保留 50 条；重复合并同一份云端数据不会重复记账 */
export async function appendConflictLog(
  conflicts: MergeConflict[],
  now: string = nowIso(),
): Promise<ConflictLogEntry[]> {
  const existing = await loadConflictLog()
  if (conflicts.length === 0) return existing
  const fresh = conflicts.filter((item) => !existing.some((entry) => sameConflict(entry, item)))
  if (fresh.length === 0) return existing
  const next = [...fresh.map((item) => ({ ...item, at: now })), ...existing].slice(
    0,
    CONFLICT_LIMIT,
  )
  try {
    await AsyncStorage.setItem(CONFLICT_KEY, JSON.stringify(next))
  } catch (error) {
    console.warn('[TradeTrace] 保存冲突日志失败', error)
  }
  return next
}
