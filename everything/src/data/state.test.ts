import { describe, expect, it } from 'vitest'

import {
  addAccount,
  addStock,
  addTransaction,
  addTTrade,
  deleteAccount,
  deleteStock,
  deleteTTrade,
  deleteTTradesBySell,
  deleteTransaction,
  updateStock,
  updateTransaction,
} from './state'
import { createEmptyState } from './types'
import type { TradeState } from './types'

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const T0 = '2026-01-01T00:00:00.000Z'
const T1 = '2026-01-02T00:00:00.000Z'
const T2 = '2026-01-03T00:00:00.000Z'
const T3 = '2026-01-04T00:00:00.000Z'
const T4 = '2026-01-05T00:00:00.000Z'
const T5 = '2026-01-06T00:00:00.000Z'

function buildState(): TradeState {
  const base = createEmptyState('device-1', T0)
  let state = addAccount(base, '华泰', T0)
  const accountId = state.accounts[0].id
  state = addStock(state, { accountId, name: '贵州茅台', code: '600519' }, T0)
  const stockId = state.stocks[0].id
  state = addTransaction(
    state,
    { stockId, date: '2026-01-02', price: 10, shares: 100, commission: 5, type: '买入' },
    T1,
  )
  state = addTransaction(
    state,
    { stockId, date: '2026-01-03', price: 12, shares: -100, commission: 5, type: '卖出' },
    T2,
  )
  const [buy, sell] = state.transactions
  return addTTrade(
    state,
    { buyTransactionId: buy.id, sellTransactionId: sell.id, shares: 50 },
    T3,
  )
}

describe('新增实体', () => {
  const state = buildState()

  it('账户使用 UUID 并推进 revision 与 updatedAt', () => {
    const base = createEmptyState('device-1', T0)
    const next = addAccount(base, '华泰', T1)
    expect(next.accounts[0].id).toMatch(UUID_V4)
    expect(next.accounts[0].createdAt).toBe(T1)
    expect(next.accounts[0].updatedAt).toBe(T1)
    expect(next.revision).toBe(base.revision + 1)
    expect(next.updatedAt).toBe(T1)
  })

  it('股票与做T使用 UUID', () => {
    expect(state.stocks[0].id).toMatch(UUID_V4)
    expect(state.tTrades[0].id).toMatch(UUID_V4)
  })

  it('交易自动补齐来源、幂等键与审计字段', () => {
    const buy = state.transactions[0]
    expect(buy.source).toBe('manual')
    expect(buy.dedupeKey).toBe('600519|2026-01-02|买入|100|10.00|5.00')
    expect(buy.createdAt).toBe(T1)
    expect(buy.updatedAt).toBe(T1)
    expect(buy.deletedAt).toBeUndefined()
  })
})

describe('软删除', () => {
  it('删除交易只写墓碑，并级联删除做T', () => {
    const state = buildState()
    const buyId = state.transactions[0].id
    const next = deleteTransaction(state, buyId, T4)

    expect(next.transactions).toHaveLength(2)
    expect(next.transactions[0].deletedAt).toBe(T4)
    expect(next.transactions[0].updatedAt).toBe(T4)
    expect(next.transactions[1].deletedAt).toBeUndefined()
    expect(next.tTrades).toHaveLength(1)
    expect(next.tTrades[0].deletedAt).toBe(T4)
    expect(next.revision).toBe(state.revision + 1)
  })

  it('删除股票级联删除交易与做T', () => {
    const state = buildState()
    const next = deleteStock(state, state.stocks[0].id, T4)

    expect(next.stocks).toHaveLength(1)
    expect(next.stocks[0].deletedAt).toBe(T4)
    expect(next.transactions.every((item) => item.deletedAt === T4)).toBe(true)
    expect(next.tTrades.every((item) => item.deletedAt === T4)).toBe(true)
  })

  it('删除账户级联删除其下所有数据', () => {
    const state = buildState()
    const next = deleteAccount(state, state.accounts[0].id, T4)

    expect(next.accounts).toHaveLength(1)
    expect(next.accounts[0].deletedAt).toBe(T4)
    expect(next.stocks.every((item) => item.deletedAt === T4)).toBe(true)
    expect(next.transactions.every((item) => item.deletedAt === T4)).toBe(true)
    expect(next.tTrades.every((item) => item.deletedAt === T4)).toBe(true)
  })

  it('重复删除不覆盖首次墓碑时间', () => {
    const state = buildState()
    const buyId = state.transactions[0].id
    const once = deleteTransaction(state, buyId, T4)
    const twice = deleteTransaction(once, buyId, T5)
    expect(twice.transactions[0].deletedAt).toBe(T4)
    expect(twice.transactions[0].updatedAt).toBe(T4)
  })

  it('删除做T与按卖出删除', () => {
    const state = buildState()
    const saleId = state.transactions[1].id
    const bySell = deleteTTradesBySell(state, saleId, T4)
    expect(bySell.tTrades).toHaveLength(1)
    expect(bySell.tTrades[0].deletedAt).toBe(T4)

    const byId = deleteTTrade(state, state.tTrades[0].id, T4)
    expect(byId.tTrades[0].deletedAt).toBe(T4)
  })
})

describe('更新实体', () => {
  it('更新股票刷新 updatedAt 并推进 revision', () => {
    const state = buildState()
    const stock = state.stocks[0]
    const next = updateStock(state, { ...stock, name: '茅台' }, T4)
    expect(next.stocks[0].name).toBe('茅台')
    expect(next.stocks[0].updatedAt).toBe(T4)
    expect(next.stocks[0].createdAt).toBe(stock.createdAt)
    expect(next.revision).toBe(state.revision + 1)
  })

  it('更新交易刷新 updatedAt', () => {
    const state = buildState()
    const trade = state.transactions[0]
    const next = updateTransaction(state, { ...trade, note: '补录' }, T4)
    expect(next.transactions[0].note).toBe('补录')
    expect(next.transactions[0].updatedAt).toBe(T4)
    expect(next.transactions[0].createdAt).toBe(trade.createdAt)
  })
})
