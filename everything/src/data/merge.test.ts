import { describe, expect, it } from 'vitest'

import { mergeStates } from './merge'
import { createEmptyState } from './types'
import type { Account, TradeState, TransactionTrade } from './types'

const T0 = '2026-01-01T00:00:00.000Z'
const T1 = '2026-01-02T00:00:00.000Z'
const T2 = '2026-01-03T00:00:00.000Z'
const T3 = '2026-01-04T00:00:00.000Z'

function account(id: string, name: string, updatedAt: string, deletedAt?: string): Account {
  return {
    id,
    name,
    createdAt: T0,
    updatedAt,
    ...(deletedAt !== undefined ? { deletedAt } : {}),
  }
}

function trade(
  id: string,
  updatedAt: string,
  overrides: Partial<TransactionTrade> = {},
): TransactionTrade {
  return {
    id,
    stockId: 'stock-1',
    date: '2026-01-02',
    price: 10,
    shares: 100,
    commission: 0,
    type: '买入',
    source: 'manual',
    dedupeKey: `key-${id}`,
    createdAt: T0,
    updatedAt,
    ...overrides,
  }
}

function state(deviceId: string, parts: Partial<TradeState>): TradeState {
  return { ...createEmptyState(deviceId, T0), revision: 3, ...parts }
}

describe('mergeStates', () => {
  it('两端各自新增的数据合并后都在', () => {
    const local = state('local', {
      accounts: [account('a1', '华泰', T1)],
      transactions: [trade('t1', T1)],
    })
    const remote = state('remote', {
      accounts: [account('a2', '中信', T2)],
      transactions: [trade('t2', T2)],
    })
    const result = mergeStates(local, remote, T3)

    expect(result.state.accounts.map((item) => item.id).sort()).toEqual(['a1', 'a2'])
    expect(result.state.transactions.map((item) => item.id).sort()).toEqual(['t1', 't2'])
    expect(result.conflicts).toHaveLength(0)
    expect(result.state.deviceId).toBe('local')
    expect(result.state.revision).toBe(4)
    expect(result.state.updatedAt).toBe(T3)
  })

  it('远端软删除不会被本地旧副本复活', () => {
    const local = state('local', { accounts: [account('a1', '华泰', T1)] })
    const remote = state('remote', { accounts: [account('a1', '华泰', T2, T2)] })
    const result = mergeStates(local, remote, T3)

    expect(result.state.accounts).toHaveLength(1)
    expect(result.state.accounts[0].deletedAt).toBe(T2)
    expect(result.conflicts).toHaveLength(1)
    expect(result.conflicts[0]).toMatchObject({
      entity: 'account',
      id: 'a1',
      winner: 'remote',
    })
  })

  it('远端更新的字段生效', () => {
    const local = state('local', { accounts: [account('a1', '华泰', T1)] })
    const remote = state('remote', { accounts: [account('a1', '华泰证券', T2)] })
    const result = mergeStates(local, remote, T3)

    expect(result.state.accounts[0].name).toBe('华泰证券')
    expect(result.conflicts).toHaveLength(1)
    expect(result.conflicts[0].winner).toBe('remote')
  })

  it('时间戳相同且一方为墓碑时删除优先', () => {
    const local = state('local', { transactions: [trade('t1', T1)] })
    const remote = state('remote', {
      transactions: [trade('t1', T1, { deletedAt: T1 })],
    })
    const result = mergeStates(local, remote, T3)

    expect(result.state.transactions[0].deletedAt).toBe(T1)
    expect(result.conflicts[0].winner).toBe('remote')
  })

  it('内容未变化时不记冲突', () => {
    const local = state('local', { accounts: [account('a1', '华泰', T1)] })
    const remote = state('remote', { accounts: [account('a1', '华泰', T2)] })
    const result = mergeStates(local, remote, T3)

    expect(result.conflicts).toHaveLength(0)
    expect(result.state.accounts[0].updatedAt).toBe(T2)
  })

  it('重复合并幂等：与同一远端再合并不改变实体，也不再产生冲突', () => {
    const local = state('local', {
      accounts: [account('a1', '华泰', T1)],
      transactions: [trade('t1', T1)],
    })
    const remote = state('remote', {
      accounts: [account('a1', '华泰证券', T2)],
      transactions: [trade('t2', T2)],
    })
    const first = mergeStates(local, remote, T3)
    const second = mergeStates(first.state, remote, T3)

    expect(second.state.accounts).toEqual(first.state.accounts)
    expect(second.state.transactions).toEqual(first.state.transactions)
    expect(second.conflicts).toHaveLength(0)
  })
})
