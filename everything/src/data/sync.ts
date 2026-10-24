import { mergeStates } from './merge'
import type { MergeConflict } from './merge'
import { isStateShape, normalizeState } from './migrate'
import { isSyncConfigured } from './sync-config'
import type { SyncConfig } from './sync-config'
import { downloadStateFile, uploadStateFile } from './webdav'
import type { TradeState } from './types'

export interface SyncPayload {
  app: 'tradetrace'
  version: 2
  exportedAt: string
  state: TradeState
}

export function serializeState(state: TradeState, exportedAt: string): string {
  const payload: SyncPayload = { app: 'tradetrace', version: 2, exportedAt, state }
  return JSON.stringify(payload)
}

/** 解析云端文件：v2 直接校验，v1（载荷或裸状态）自动迁移，非法返回 null */
export function parsePayload(text: string, deviceId: string, now: string): TradeState | null {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return null
  }
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null

  const record = raw as Record<string, unknown>
  // 兼容 v1 / v2 载荷：{ app, version, exportedAt, state }
  if (record.state && typeof record.state === 'object' && !Array.isArray(record.state)) {
    if (record.version !== 1 && record.version !== 2) return null
    if (!isStateShape(record.state)) return null
    return normalizeState(record.state, deviceId, now)
  }
  // 兼容直接存放 TradeState 的文件（v1 或 v2）
  if (isStateShape(record)) return normalizeState(record, deviceId, now)
  return null
}

export interface PushResult {
  ok: boolean
  message: string
}

export interface PullResult extends PushResult {
  state?: TradeState
  conflicts?: MergeConflict[]
}

/** 合并结果摘要：本机没有的记为新增，本机原有但现在带墓碑的记为删除 */
function mergeSummary(local: TradeState, merged: TradeState): string {
  const localById = new Map(local.transactions.map((item) => [item.id, item]))
  const mergedActive = merged.transactions.filter((item) => !item.deletedAt)

  const added = mergedActive.filter((item) => !localById.has(item.id)).length
  const removed = local.transactions.filter(
    (item) => !item.deletedAt && merged.transactions.some((row) => row.id === item.id && row.deletedAt),
  ).length

  const removedText = removed > 0 ? `，删除 ${removed} 笔` : ''
  return `新增 ${added} 笔交易${removedText}`
}

export async function pushToCloud(config: SyncConfig, state: TradeState): Promise<PushResult> {
  if (!isSyncConfigured(config)) return { ok: false, message: '请先填写坚果云账号与应用密码' }
  if (!config.deviceId) return { ok: false, message: '本设备 ID 缺失，请重新保存配置' }
  const result = await uploadStateFile(
    config,
    config.deviceId,
    serializeState(state, new Date().toISOString()),
  )
  return { ok: result.ok, message: result.message }
}

/**
 * 合并下载：不再整包覆盖本机数据。
 * 与云端快照按实体合并，本机新增的数据会保留，冲突按 updatedAt 取新。
 */
export async function pullFromCloud(
  config: SyncConfig,
  localState: TradeState,
  now: string,
): Promise<PullResult> {
  if (!isSyncConfigured(config)) return { ok: false, message: '请先填写坚果云账号与应用密码' }
  if (!config.remoteDeviceId) return { ok: false, message: '请先填写远程设备 ID' }
  const result = await downloadStateFile(config, config.remoteDeviceId)
  if (!result.ok) return { ok: false, message: result.message }

  const remote = parsePayload(result.content, localState.deviceId || config.deviceId, now)
  if (!remote) return { ok: false, message: '云端数据格式无法识别，未修改本机数据' }

  const merged = mergeStates(localState, remote, now)
  const conflictText =
    merged.conflicts.length > 0 ? `，${merged.conflicts.length} 条冲突按最新修改时间取舍` : ''

  return {
    ok: true,
    message: `合并完成：${mergeSummary(localState, merged.state)}${conflictText}`,
    state: merged.state,
    conflicts: merged.conflicts,
  }
}
