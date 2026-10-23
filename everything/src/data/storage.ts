import AsyncStorage from '@react-native-async-storage/async-storage'

import { normalizeState } from './state'
import { createEmptyState } from './types'
import type { TradeState } from './types'

/** 本地缓存键：后续接 lianghua 后端时，替换本文件的实现即可，页面无需改动 */
const STORAGE_KEY = 'tradetrace/state/v1'

export async function loadTradeState(): Promise<TradeState> {
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY)
    if (!raw) return createEmptyState()
    return normalizeState(JSON.parse(raw))
  } catch (error) {
    console.warn('[TradeTrace] 读取本地数据失败', error)
    return createEmptyState()
  }
}

export async function saveTradeState(state: TradeState): Promise<void> {
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (error) {
    console.warn('[TradeTrace] 保存本地数据失败', error)
  }
}
