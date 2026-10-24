import { describe, expect, it } from 'vitest'

import { mergeStates } from './merge'
import {
  accountProfit,
  accountRows,
  availableBuys,
  mergedProfit,
  sortTransactionsAsc,
  sortTransactionsDesc,
  stockCycleSummary,
  stockSummary,
  stockTransactions,
  tTradeDetails,
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
import type { TransactionTrade, TradeState, TTrade } from './types'

const T0 = '2026-01-01T00:00:00.000Z'
const T1 = '2026-01-02T00:00:00.000Z'
const T2 = '2026-01-03T00:00:00.000Z'
const T3 = '2026-01-04T00:00:00.000Z'

function trade(
  partial: Partial<TransactionTrade> & Pick<TransactionTrade, 'id' | 'type'>,
): TransactionTrade {
  return {
    stockId: 'stock-1',
    date: '2026-01-01',
    price: 0,
    shares: 0,
    commission: 0,
    source: 'manual',
    dedupeKey: `key-${partial.id}`,
    createdAt: T0,
    updatedAt: T0,
    ...partial,
  }
}

describe('transactionCost', () => {
  it('买入为负费用，卖出为正收益，股息为收入', () => {
    expect(transactionCost(trade({ id: 't1', type: '买入', price: 10, shares: 100, commission: 5 }))).toBe(-1005)
    expect(transactionCost(trade({ id: 't2', type: '卖出', price: 12, shares: -100, commission: 5 }))).toBe(1195)
    expect(transactionCost(trade({ id: 't3', type: '股息', dividend: 50 }))).toBe(50)
  })
})

describe('stockSummary / stockCycleSummary', () => {
  const trades = [
    trade({ id: 't1', type: '买入', date: '2026-01-01', price: 10, shares: 100 }),
    trade({ id: 't2', type: '卖出', date: '2026-01-10', price: 12, shares: -100 }),
    trade({ id: 't3', type: '买入', date: '2026-02-01', price: 10, shares: 200 }),
    trade({ id: 't4', type: '买入', date: '2026-02-02', price: 11, shares: 100 }),
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

  it('同一天的多笔交易按旧 ID 顺序计算', () => {
    const summary = stockCycleSummary([
      trade({ id: 'b', legacyId: 2, type: '卖出', date: '2026-01-01', price: 12, shares: -100 }),
      trade({ id: 'a', legacyId: 1, type: '买入', date: '2026-01-01', price: 10, shares: 100 }),
    ])
    expect(summary.cycleCost).toBe(0)
  })
})

describe('排序', () => {
  it('同日期依次按 legacyId、createdAt、ID 升序', () => {
    const legacy2 = trade({ id: 'b', legacyId: 2, type: '卖出' })
    const legacy1 = trade({ id: 'a', legacyId: 1, type: '买入' })
    expect(sortTransactionsAsc([legacy2, legacy1]).map((item) => item.id)).toEqual(['a', 'b'])

    const late = trade({ id: 'z', type: '买入', createdAt: T2 })
    const early = trade({ id: 'y', type: '买入', createdAt: T1 })
    expect(sortTransactionsAsc([late, early]).map((item) => item.id)).toEqual(['y', 'z'])
  })

  it('倒序时最新交易在前', () => {
    const older = trade({ id: 'a', type: '买入', date: '2026-01-01' })
    const newer = trade({ id: 'b', type: '卖出', date: '2026-01-02' })
    expect(sortTransactionsDesc([older, newer]).map((item) => item.id)).toEqual(['b', 'a'])
  })
})

describe('做T', () => {
  const buy = trade({ id: 't1', type: '买入', price: 10, shares: 100, commission: 10 })
  const sell = trade({ id: 't2', type: '卖出', price: 12, shares: -100, commission: 12 })
  const ttrade: TTrade = {
    id: 'tt1',
    buyTransactionId: 't1',
    sellTransactionId: 't2',
    shares: 50,
    createdAt: T0,
    updatedAt: T0,
  }

  it('收益按份额比例分摊手续费', () => {
    expect(tTradeProfit(ttrade, buy, sell)).toBeCloseTo(100 - 5 - 6)
  })

  it('可关联买入排除当前卖出已占用的份额', () => {
    const state: TradeState = {
      ...createEmptyState('device-1', T0),
      transactions: [buy, sell],
      tTrades: [ttrade],
    }
    expect(availableBuys(state, 'stock-1', 't2')).toHaveLength(1)
    expect(availableBuys(state, 'stock-1')).toHaveLength(1)

    const fullyLinked = { ...state, tTrades: [{ ...ttrade, shares: 100 }] }
    expect(availableBuys(fullyLinked, 'stock-1')).toHaveLength(0)
    expect(availableBuys(fullyLinked, 'stock-1', 't2')).toHaveLength(1)
  })
})

function buildState(): TradeState {
  let state = addAccount(createEmptyState('device-1', T0), '华泰', T0)
  const accountId = state.accounts[0].id
  state = addStock(state, { accountId, name: '贵州茅台', code: '600519' }, T0)
  const stockId = state.stocks[0].id
  state = addTransaction(
    state,
    { stockId, date: '2026-01-02', price: 10, shares: 100, commission: 0, type: '买入' },
    T1,
  )
  state = addTransaction(
    state,
    { stockId, date: '2026-01-03', price: 12, shares: -100, commission: 0, type: '卖出' },
    T2,
  )
  const [buy, sell] = state.transactions
  return addTTrade(
    state,
    { buyTransactionId: buy.id, sellTransactionId: sell.id, shares: 50 },
    T2,
  )
}

describe('软删除过滤', () => {
  it('墓碑交易不计入收益与流水', () => {
    const state = buildState()
    const sell = state.transactions[1]
    const next = deleteTransaction(state, sell.id, T3)

    expect(stockTransactions(next, state.stocks[0].id)).toHaveLength(1)
    expect(mergedProfit(next)).toBe(-1000)
    expect(accountProfit(next, state.accounts[0].id)).toBe(-1000)
    expect(tTradeDetails(next, state.stocks[0].id)).toHaveLength(0)
  })

  it('墓碑股票与账户不出现在汇总行', () => {
    const state = buildState()
    const afterStock = deleteStock(state, state.stocks[0].id, T3)
    expect(accountRows(afterStock)[0].stockCount).toBe(0)
    expect(accountRows(afterStock)[0].holdingCount).toBe(0)
    expect(mergedProfit(afterStock)).toBe(0)

    const afterAccount = deleteAccount(state, state.accounts[0].id, T3)
    expect(accountRows(afterAccount)).toHaveLength(0)
    expect(mergedProfit(afterAccount)).toBe(0)
  })

  it('账户收益与合并收益口径一致', () => {
    const state = buildState()
    expect(accountProfit(state, state.accounts[0].id)).toBe(200)
    expect(mergedProfit(state)).toBe(200)
  })

  it('账户已删除后本机新增的股票交易不计入合并收益', () => {
    const local = buildState()
    const accountId = local.accounts[0].id
    // 远端在 T2 删除了账户与其下股票；本机在 T3 又给该账户加了新股票
    const remote = deleteAccount(local, accountId, T2)
    let next = addStock(local, { accountId, name: '平安银行', code: '000001' }, T3)
    const newStock = next.stocks.find((item) => item.id !== local.stocks[0].id)
    expect(newStock).toBeDefined()
    next = addTransaction(
      next,
      { stockId: newStock!.id, date: '2026-01-05', price: 8, shares: 100, commission: 2, type: '买入' },
      T3,
    )

    const merged = mergeStates(next, remote, T3).state
    expect(merged.accounts[0].deletedAt).toBe(T2)
    expect(merged.stocks.filter((item) => !item.deletedAt)).toHaveLength(1)
    expect(mergedProfit(merged)).toBe(0)
  })
})

describe('合并后统计', () => {
  it('覆盖双端交易', () => {
    const local = buildState()
    const remote = createEmptyState('remote-device', T0)
    remote.transactions.push(
      trade({
        id: 'remote-1',
        stockId: local.stocks[0].id,
        type: '买入',
        price: 10,
        shares: 100,
      }),
    )
    const merged = mergeStates(local, remote, T3).state
    expect(mergedProfit(merged)).toBe(-800)
    expect(stockTransactions(merged, local.stocks[0].id)).toHaveLength(3)
  })
})
