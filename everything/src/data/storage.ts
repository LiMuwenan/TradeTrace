import AsyncStorage from '@react-native-async-storage/async-storage'

import type { TradeState } from './types'

/** 本地缓存键：后续接 lianghua 后端时，替换本文件的实现即可，页面无需改动 */
const STORAGE_KEY_V2 = 'tradetrace/state/v2'
/** v1 旧键：只读回退，迁移成功后统一写入 v2 */
const STORAGE_KEY_V1 = 'tradetrace/state/v1'

/**
 * 读取结果区分「没有数据」与「数据损坏」：
 * 损坏时必须由上层禁止写盘，否则空状态会覆盖掉仍可人工恢复的原始 JSON。
 */
export type RawStateResult =
  | { status: 'ok'; data: unknown }
  | { status: 'empty' }
  | { status: 'corrupt'; error: unknown }

async function readJson(key: string): Promise<RawStateResult> {
  let text: string | null
  try {
    text = await AsyncStorage.getItem(key)
  } catch (error) {
    console.warn('[TradeTrace] 读取本地数据失败', error)
    return { status: 'corrupt', error }
  }
  if (!text) return { status: 'empty' }
  try {
    return { status: 'ok', data: JSON.parse(text) }
  } catch (error) {
    console.warn('[TradeTrace] 本地数据不是合法 JSON', error)
    return { status: 'corrupt', error }
  }
}

/** 读取原始 JSON（v2 优先，v1 兜底）；v2 损坏时不再回退，避免掩盖问题 */
export async function loadRawState(): Promise<RawStateResult> {
  const current = await readJson(STORAGE_KEY_V2)
  if (current.status !== 'empty') return current
  return readJson(STORAGE_KEY_V1)
}

export async function saveRawState(state: TradeState): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY_V2, JSON.stringify(state))
  } catch (error) {
    console.warn('[TradeTrace] 保存本地数据失败', error)
  }
}
