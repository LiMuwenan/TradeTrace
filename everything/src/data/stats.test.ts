import { describe, expect, it } from 'vitest'

import {
  availableBuys,
  accountProfit,
  mergedProfit,
  stockCycleSummary,
  stockSummary,
  tTradeProfit,
} from './stats'
import {
  addAccount,
  addStock,
  addTransaction,
  addTTrade,
  deleteAccount,
  deleteStock,
  deleteTransaction,
} from './state'
import { createEmptyState, transactionCost } from './types'
import type { TransactionTrade, TradeState } from './types'

function trade(partial: Partial<TransactionTrade> & Pick<TransactionTrade, 'id' | 'type'>): TransactionTrade {
  return {
    stockId: 1,
    date: '2026-01-01',
    price: 0,
    shares: 0,
    commission: 0,
    createdAt: '2026-01-01T00:00:00.000Z',
    ...partial,
  }
}

describe('transactionCost', () => {
  it('买入为负费用，卖出为正收益，股息为收入', () => {
    expect(transactionCost(trade({ id: 1, type: '买入', price: 10, shares: 100, commission: 5 }))).toBe(-1005)
    expect(transactionCost(trade({ id: 2, type: '卖出', price: 12, shares: -100, commission: 5 }))).toBe(1195)
    expect(transactionCost(trade({ id: 3, type: '股息', dividend: 50 }))).toBe(50)
  })
})

describe('stockSummary / stockCycleSummary', () => {
  const trades = [
    trade({ id: 1, type: '买入', date: '2026-01-01', price: 10, shares: 100 }),
    trade({ id: 2, type: '卖出', date: '2026-01-10', price: 12, shares: -100 }),
    trade({ id: 3, type: '买入', date: '2026-02-01', price: 10, shares: 200 }),
    trade({ id: 4, type: '买入', date: '2026-02-02', price: 11, shares: 100 }),
  ]

  it('简单汇总按 SUM(shares) 与费用累计', () => {
    const summary = stockSummary(trades)
    expect(summary.totalShares).toBe(300)
    expect(summary.totalCost).toBe(200 - 2000 - 1100)
    expect(summary.avgCost).toBeCloseTo((-2900) / 300)
  })

  it('清仓后重新建仓：持仓成本只算当前周期', () => {
    const summary = stockCycleSummary(trades)
    expect(summary.totalShares).toBe(300)
    expect(summary.totalCost).toBe(-2900)
    expect(summary.cycleCost).toBe(-3100)
    expect(summary.avgCost).toBeCloseTo(3100 / 300)
  })

  it('全部清仓时持仓成本归零，总收益保留', () => {
    const summary = stockCycleSummary(trades.slice(0, 2))
    expect(summary.totalShares).toBe(0)
    expect(summary.cycleCost).toBe(0)
    expect(summary.avgCost).toBe(0)
    expect(summary.totalCost).toBe(200)
  })

  it('同一天的多笔交易按 id 顺序计算', () => {
    const summary = stockCycleSummary([
      trade({ id: 2, type: '卖出', date: '2026-01-01', price: 12, shares: -100 }),
      trade({ id: 1, type: '买入', date: '2026-01-01', price: 10, shares: 100 }),
    ])
    expect(summary.cycleCost).toBe(0)
  })
})

describe('做T', () => {
  const buy = trade({ id: 1, type: '买入', price: 10, shares: 100, commission: 10 })
  const sell = trade({ id: 2, type: '卖出', price: 12, shares: -100, commission: 12 })
  const ttrade = {
    id: 1,
    buyTransactionId: 1,
    sellTransactionId: 2,
    shares: 50,
    createdAt: '2026-01-01T00:00:00.000Z',
  }

  it('收益按份额比例分摊手续费', () => {
    expect(tTradeProfit(ttrade, buy, sell)).toBeCloseTo(100 - 5 - 6)
  })

  it('可关联买入排除当前卖出已占用的份额', () => {
    const state: TradeState = {
      ...createEmptyState(),
      transactions: [buy, sell],
      tTrades: [ttrade],
    }
    expect(availableBuys(state, 1, 2)).toHaveLength(1)
    expect(availableBuys(state, 1)).toHaveLength(1)

    const fullyLinked = { ...state, tTrades: [{ ...ttrade, shares: 100 }] }
    expect(availableBuys(fullyLinked, 1)).toHaveLength(0)
    expect(availableBuys(fullyLinked, 1, 2)).toHaveLength(1)
  })
})

describe('级联删除与汇总', () => {
  function buildState(): TradeState {
    let state = createEmptyState()
    state = addAccount(state, '华泰', '2026-01-01T00:00:00.000Z')
    state = addStock(state, {
      accountId: 1,
      name: '贵州茅台',
      code: '600519',
      createdAt: '2026-01-01T00:00:00.000Z',
    })
    state = addTransaction(state, {
      stockId: 1,
      date: '2026-01-02',
      price: 10,
      shares: 100,
      commission: 0,
      type: '买入',
      createdAt: '2026-01-02T00:00:00.000Z',
    })
    state = addTransaction(state, {
      stockId: 1,
      date: '2026-01-03',
      price: 12,
      shares: -100,
      commission: 0,
      type: '卖出',
      createdAt: '2026-01-03T00:00:00.000Z',
    })
    state = addTTrade(state, {
      buyTransactionId: 1,
      sellTransactionId: 2,
      shares: 50,
      createdAt: '2026-01-03T00:00:00.000Z',
    })
    return state
  }

  it('删除交易会清理做T关联', () => {
    const state = deleteTransaction(buildState(), 1)
    expect(state.transactions).toHaveLength(1)
    expect(state.tTrades).toHaveLength(0)
  })

  it('删除股票会清理交易与做T', () => {
    const state = deleteStock(buildState(), 1)
    expect(state.stocks).toHaveLength(0)
    expect(state.transactions).toHaveLength(0)
    expect(state.tTrades).toHaveLength(0)
  })

  it('删除账户级联删除其下所有数据', () => {
    const state = deleteAccount(buildState(), 1)
    expect(state.accounts).toHaveLength(0)
    expect(state.stocks).toHaveLength(0)
    expect(state.transactions).toHaveLength(0)
  })

  it('账户收益与合并收益口径一致', () => {
    const state = buildState()
    expect(accountProfit(state, 1)).toBe(200)
    expect(mergedProfit(state)).toBe(200)
  })
})
