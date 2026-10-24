import type { EntityMeta, TradeState } from './types'

export type EntityKind = 'account' | 'stock' | 'transaction' | 'ttrade'

export interface MergeConflict {
  entity: EntityKind
  id: string
  localUpdatedAt: string
  remoteUpdatedAt: string
  winner: 'local' | 'remote'
}

export interface MergeResult {
  state: TradeState
  conflicts: MergeConflict[]
}

/** 稳定序列化：对象键排序，避免字段插入顺序影响“内容是否相同”的判断 */
function stableValue(value: unknown): string {
  if (value === undefined) return 'undefined'
  if (Array.isArray(value)) return `[${value.map(stableValue).join(',')}]`
  if (typeof value === 'object' && value !== null) {
    const record = value as Record<string, unknown>
    const entries = Object.keys(record)
      .filter((key) => record[key] !== undefined)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableValue(record[key])}`)
    return `{${entries.join(',')}}`
  }
  return JSON.stringify(value)
}

/** 除 updatedAt 外完全一致，视为无需记冲突 */
function entityEqual(a: EntityMeta, b: EntityMeta): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)])
  keys.delete('updatedAt')
  const left = a as unknown as Record<string, unknown>
  const right = b as unknown as Record<string, unknown>
  for (const key of keys) {
    if (stableValue(left[key]) !== stableValue(right[key])) return false
  }
  return true
}

function pickWinner<T extends EntityMeta>(local: T, remote: T): 'local' | 'remote' {
  if (local.updatedAt !== remote.updatedAt) {
    return local.updatedAt > remote.updatedAt ? 'local' : 'remote'
  }
  // 同一时间戳时删除优先，避免两端同时操作把墓碑丢掉
  if (local.deletedAt && !remote.deletedAt) return 'local'
  if (remote.deletedAt && !local.deletedAt) return 'remote'
  return 'local'
}

function mergeList<T extends EntityMeta>(
  entity: EntityKind,
  localItems: T[],
  remoteItems: T[],
  conflicts: MergeConflict[],
): T[] {
  const localById = new Map(localItems.map((item) => [item.id, item]))
  const remoteById = new Map(remoteItems.map((item) => [item.id, item]))
  const ids = new Set([...localById.keys(), ...remoteById.keys()])
  const merged: T[] = []

  for (const id of ids) {
    const local = localById.get(id)
    const remote = remoteById.get(id)

    if (!local) {
      merged.push(remote as T)
      continue
    }
    if (!remote) {
      merged.push(local)
      continue
    }

    const winner = pickWinner(local, remote)
    if (!entityEqual(local, remote)) {
      conflicts.push({
        entity,
        id,
        localUpdatedAt: local.updatedAt,
        remoteUpdatedAt: remote.updatedAt,
        winner,
      })
    }
    merged.push(winner === 'local' ? local : remote)
  }

  return merged
}

/**
 * 实体级合并：按 ID 取并集，updatedAt 新者胜；同时间戳删除优先。
 * 合并结果沿用本机设备 ID，revision 取两端最大值再 +1。
 */
export function mergeStates(local: TradeState, remote: TradeState, now: string): MergeResult {
  const conflicts: MergeConflict[] = []
  const deviceId = local.deviceId || remote.deviceId

  return {
    state: {
      schemaVersion: 2,
      deviceId,
      revision: Math.max(local.revision, remote.revision) + 1,
      updatedAt: now,
      accounts: mergeList('account', local.accounts, remote.accounts, conflicts),
      stocks: mergeList('stock', local.stocks, remote.stocks, conflicts),
      transactions: mergeList('transaction', local.transactions, remote.transactions, conflicts),
      tTrades: mergeList('ttrade', local.tTrades, remote.tTrades, conflicts),
    },
    conflicts,
  }
}
