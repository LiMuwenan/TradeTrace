import { transactionCost } from './types'
import type { TradeState, TransactionTrade, TTrade } from './types'

export interface StockSummary {
  totalShares: number
  totalCost: number
  avgCost: number
}

export interface CycleSummary {
  /** 当前持仓股数 */
  totalShares: number
  /** 累计费用（含已清仓周期） */
  totalCost: number
  /** 当前持仓成本（建仓周期内累计费用 / 持仓股数） */
  avgCost: number
  /** 当前建仓周期收益 */
  cycleCost: number
  /** 累计持仓成本 */
  totalAvgCost: number
}

export interface TTradeDetail {
  ttrade: TTrade
  buy: TransactionTrade
  sell: TransactionTrade
  profit: number
}

/** 按日期、id 升序（与旧版 SQLite 的 date ASC 口径一致） */
export function sortTransactionsAsc(trades: TransactionTrade[]): TransactionTrade[] {
  return [...trades].sort((a, b) => (a.date === b.date ? a.id - b.id : a.date.localeCompare(b.date)))
}

/** 简单汇总：SUM(shares) 与 SUM(-price*shares-commission) */
export function stockSummary(trades: TransactionTrade[]): StockSummary {
  let totalShares = 0
  let totalCost = 0
  for (const trade of trades) {
    totalShares += trade.shares
    totalCost += transactionCost(trade)
  }
  return {
    totalShares,
    totalCost,
    avgCost: totalShares !== 0 ? totalCost / totalShares : 0,
  }
}

/**
 * 建仓周期汇总：持仓从 0 变正视为建仓，归零视为清仓。
 * 持仓成本 = 建仓周期累计费用 / 持仓股数（卖出利润会拉低成本）。
 */
export function stockCycleSummary(trades: TransactionTrade[]): CycleSummary {
  const ordered = sortTransactionsAsc(trades)
  let allTimeCost = 0
  let allTimeShares = 0
  let currentCycleCost = 0
  let inCycle = false

  for (const trade of ordered) {
    allTimeCost += transactionCost(trade)
    allTimeShares += trade.shares

    if (trade.type === '买入') {
      if (!inCycle && trade.shares > 0) {
        currentCycleCost = 0
        inCycle = true
      }
      currentCycleCost += transactionCost(trade)
    } else {
      currentCycleCost += transactionCost(trade)
      if (allTimeShares === 0) {
        currentCycleCost = 0
        inCycle = false
      }
    }
  }

  if (allTimeShares === 0) {
    currentCycleCost = 0
    inCycle = false
  }

  return {
    totalShares: allTimeShares,
    totalCost: allTimeCost,
    avgCost: allTimeShares > 0 ? Math.abs(currentCycleCost / allTimeShares) : 0,
    cycleCost: currentCycleCost,
    totalAvgCost: allTimeShares !== 0 ? Math.abs(allTimeCost / allTimeShares) : 0,
  }
}

export function stockTransactions(state: TradeState, stockId: number): TransactionTrade[] {
  return state.transactions.filter((t) => t.stockId === stockId)
}

export function stockProfit(state: TradeState, stockId: number): number {
  return stockSummary(stockTransactions(state, stockId)).totalCost
}

export function accountProfit(state: TradeState, accountId: number): number {
  const stockIds = new Set(state.stocks.filter((s) => s.accountId === accountId).map((s) => s.id))
  return state.transactions
    .filter((t) => stockIds.has(t.stockId))
    .reduce((sum, t) => sum + transactionCost(t), 0)
}

export function mergedProfit(state: TradeState): number {
  return state.transactions.reduce((sum, t) => sum + transactionCost(t), 0)
}

/** 做T单笔收益：买卖手续费按份额比例分摊 */
export function tTradeProfit(ttrade: TTrade, buy: TransactionTrade, sell: TransactionTrade): number {
  const buyCommission =
    buy.shares !== 0 ? buy.commission * (ttrade.shares / Math.abs(buy.shares)) : 0
  const sellCommission =
    sell.shares !== 0 ? sell.commission * (ttrade.shares / Math.abs(sell.shares)) : 0
  return (sell.price - buy.price) * ttrade.shares - buyCommission - sellCommission
}

export function tTradeDetails(state: TradeState, stockId: number): TTradeDetail[] {
  const byId = new Map(state.transactions.map((t) => [t.id, t]))
  return state.tTrades
    .map((ttrade) => {
      const buy = byId.get(ttrade.buyTransactionId)
      const sell = byId.get(ttrade.sellTransactionId)
      if (!buy || !sell || buy.stockId !== stockId) return null
      return { ttrade, buy, sell, profit: tTradeProfit(ttrade, buy, sell) }
    })
    .filter((row): row is TTradeDetail => row !== null)
    .sort((a, b) => a.ttrade.createdAt.localeCompare(b.ttrade.createdAt))
}

/** 卖出记录关联的做T列表 */
export function tTradesBySell(state: TradeState, sellId: number): TTradeDetail[] {
  const byId = new Map(state.transactions.map((t) => [t.id, t]))
  return state.tTrades
    .filter((tt) => tt.sellTransactionId === sellId)
    .map((tt) => {
      const buy = byId.get(tt.buyTransactionId)
      const sell = byId.get(tt.sellTransactionId)
      if (!buy || !sell) return null
      return { ttrade: tt, buy, sell, profit: tTradeProfit(tt, buy, sell) }
    })
    .filter((row): row is TTradeDetail => row !== null)
}

/** 可关联的买入记录：买入股数 > 已被做T占用的股数（不含当前这笔卖出） */
export function availableBuys(
  state: TradeState,
  stockId: number,
  excludeSellId?: number,
): TransactionTrade[] {
  return sortTransactionsAsc(
    state.transactions.filter((t) => t.stockId === stockId && t.type === '买入'),
  ).filter((buy) => {
    const linked = state.tTrades
      .filter((tt) => tt.buyTransactionId === buy.id && tt.sellTransactionId !== excludeSellId)
      .reduce((sum, tt) => sum + tt.shares, 0)
    return buy.shares > linked
  })
}

export interface AccountRow {
  accountId: number
  name: string
  stockCount: number
  holdingCount: number
  profit: number
}

export function accountRows(state: TradeState): AccountRow[] {
  return state.accounts.map((account) => {
    const stocks = state.stocks.filter((s) => s.accountId === account.id)
    const holdingCount = stocks.filter(
      (s) => stockCycleSummary(stockTransactions(state, s.id)).totalShares > 0,
    ).length
    return {
      accountId: account.id,
      name: account.name,
      stockCount: stocks.length,
      holdingCount,
      profit: accountProfit(state, account.id),
    }
  })
}

export interface StockProfitRow {
  stockId: number
  accountName: string
  label: string
  profit: number
}

export function stockProfitRows(state: TradeState): StockProfitRow[] {
  return state.accounts.flatMap((account) =>
    state.stocks
      .filter((s) => s.accountId === account.id)
      .map((stock) => ({
        stockId: stock.id,
        accountName: account.name,
        label: `${stock.name}${stock.code}`,
        profit: stockProfit(state, stock.id),
      })),
  )
}

export interface TTradeProfitRow {
  id: number
  stockLabel: string
  buyDate: string
  sellDate: string
  shares: number
  profit: number
}

export function allTTradeRows(state: TradeState): TTradeProfitRow[] {
  return state.stocks.flatMap((stock) =>
    tTradeDetails(state, stock.id).map((row) => ({
      id: row.ttrade.id,
      stockLabel: `${stock.name}${stock.code}`,
      buyDate: row.buy.date,
      sellDate: row.sell.date,
      shares: row.ttrade.shares,
      profit: row.profit,
    })),
  )
}
