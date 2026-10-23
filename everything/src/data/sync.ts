import { normalizeState } from './state'
import { isSyncConfigured } from './sync-config'
import type { SyncConfig } from './sync-config'
import { downloadStateFile, uploadStateFile } from './webdav'
import type { TradeState } from './types'

export interface SyncPayload {
  app: 'tradetrace'
  version: 1
  exportedAt: string
  state: TradeState
}

export function serializeState(state: TradeState, exportedAt: string): string {
  const payload: SyncPayload = { app: 'tradetrace', version: 1, exportedAt, state }
  return JSON.stringify(payload)
}

/** 解析云端文件，格式不合法返回 null */
export function parsePayload(text: string): TradeState | null {
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return null
  }
  if (!raw || typeof raw !== 'object') return null
  const payload = raw as Partial<SyncPayload>
  // 兼容直接存放 TradeState 的文件
  if (Array.isArray((raw as Partial<TradeState>).accounts)) {
    return normalizeState(raw)
  }
  if (!payload.state || typeof payload.state !== 'object') return null
  return normalizeState(payload.state)
}

export interface PushResult {
  ok: boolean
  message: string
}

export interface PullResult extends PushResult {
  state?: TradeState
}

export async function pushToCloud(config: SyncConfig, state: TradeState): Promise<PushResult> {
  if (!isSyncConfigured(config)) return { ok: false, message: '请先填写坚果云账号与应用密码' }
  if (!config.deviceId) return { ok: false, message: '本设备 ID 缺失，请重新保存配置' }
  const result = await uploadStateFile(config, config.deviceId, serializeState(state, new Date().toISOString()))
  return { ok: result.ok, message: result.message }
}

export async function pullFromCloud(config: SyncConfig): Promise<PullResult> {
  if (!isSyncConfigured(config)) return { ok: false, message: '请先填写坚果云账号与应用密码' }
  if (!config.remoteDeviceId) return { ok: false, message: '请先填写远程设备 ID' }
  const result = await downloadStateFile(config, config.remoteDeviceId)
  if (!result.ok) return { ok: false, message: result.message }
  const state = parsePayload(result.content)
  if (!state) return { ok: false, message: '云端数据格式无法识别，未修改本机数据' }
  return { ok: true, message: '下载成功，数据已替换', state }
}
