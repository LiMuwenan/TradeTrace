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

/** 迁移后的 v1 交易没有 legacyId 时排在最后，保持“旧数据在前”的阅读顺序 */
function legacyRank(trade: TransactionTrade): number {
  return trade.legacyId ?? Number.MAX_SAFE_INTEGER
}

/**
 * 按日期升序；同日期优先按 v1 旧 ID，再按创建时间与 UUID。
 * 这样迁移前后同一份数据的建仓顺序完全一致，六项指标不会回归。
 */
export function sortTransactionsAsc(trades: TransactionTrade[]): TransactionTrade[] {
  return [...trades].sort((a, b) => {
    if (a.date !== b.date) return a.date.localeCompare(b.date)
    const rank = legacyRank(a) - legacyRank(b)
    if (rank !== 0) return rank
    if (a.createdAt !== b.createdAt) return a.createdAt.localeCompare(b.createdAt)
    return a.id.localeCompare(b.id)
  })
}

/** 个股流水倒序展示：最新交易在最上面 */
export function sortTransactionsDesc(trades: TransactionTrade[]): TransactionTrade[] {
  return sortTransactionsAsc(trades).reverse()
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

export function stockTransactions(state: TradeState, stockId: string): TransactionTrade[] {
  return state.transactions.filter((trade) => trade.stockId === stockId && !trade.deletedAt)
}

export function stockProfit(state: TradeState, stockId: string): number {
  return stockSummary(stockTransactions(state, stockId)).totalCost
}

export function accountProfit(state: TradeState, accountId: string): number {
  const stockIds = new Set(
    state.stocks
      .filter((stock) => stock.accountId === accountId && !stock.deletedAt)
      .map((stock) => stock.id),
  )
  return state.transactions
    .filter((trade) => stockIds.has(trade.stockId) && !trade.deletedAt)
    .reduce((sum, trade) => sum + transactionCost(trade), 0)
}

/**
 * 合并账户总收益：只统计「账户与股票都未删除」的交易。
 * 合并同步后可能出现账户已删、但本机新增了该账户下股票的情况，
 * 若不校验父链，这里会与 accountProfit 算出两套口径。
 */
export function mergedProfit(state: TradeState): number {
  const accountIds = new Set(
    state.accounts.filter((account) => !account.deletedAt).map((account) => account.id),
  )
  const stockIds = new Set(
    state.stocks
      .filter((stock) => !stock.deletedAt && accountIds.has(stock.accountId))
      .map((stock) => stock.id),
  )
  return state.transactions
    .filter((trade) => !trade.deletedAt && stockIds.has(trade.stockId))
    .reduce((sum, trade) => sum + transactionCost(trade), 0)
}

/** 做T单笔收益：买卖手续费按份额比例分摊 */
export function tTradeProfit(ttrade: TTrade, buy: TransactionTrade, sell: TransactionTrade): number {
  const buyCommission =
    buy.shares !== 0 ? buy.commission * (ttrade.shares / Math.abs(buy.shares)) : 0
  const sellCommission =
    sell.shares !== 0 ? sell.commission * (ttrade.shares / Math.abs(sell.shares)) : 0
  return (sell.price - buy.price) * ttrade.shares - buyCommission - sellCommission
}

export function tTradeDetails(state: TradeState, stockId: string): TTradeDetail[] {
  const byId = new Map(
    state.transactions.filter((trade) => !trade.deletedAt).map((trade) => [trade.id, trade]),
  )
  return state.tTrades
    .filter((ttrade) => !ttrade.deletedAt)
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
export function tTradesBySell(state: TradeState, sellId: string): TTradeDetail[] {
  const byId = new Map(
    state.transactions.filter((trade) => !trade.deletedAt).map((trade) => [trade.id, trade]),
  )
  return state.tTrades
    .filter((ttrade) => ttrade.sellTransactionId === sellId && !ttrade.deletedAt)
    .map((ttrade) => {
      const buy = byId.get(ttrade.buyTransactionId)
      const sell = byId.get(ttrade.sellTransactionId)
      if (!buy || !sell) return null
      return { ttrade, buy, sell, profit: tTradeProfit(ttrade, buy, sell) }
    })
    .filter((row): row is TTradeDetail => row !== null)
}

/** 可关联的买入记录：买入股数 > 已被做T占用的股数（不含当前这笔卖出） */
export function availableBuys(
  state: TradeState,
  stockId: string,
  excludeSellId?: string,
): TransactionTrade[] {
  return sortTransactionsAsc(
    state.transactions.filter(
      (trade) => trade.stockId === stockId && trade.type === '买入' && !trade.deletedAt,
    ),
  ).filter((buy) => {
    const linked = state.tTrades
      .filter(
        (ttrade) =>
          ttrade.buyTransactionId === buy.id &&
          ttrade.sellTransactionId !== excludeSellId &&
          !ttrade.deletedAt,
      )
      .reduce((sum, ttrade) => sum + ttrade.shares, 0)
    return buy.shares > linked
  })
}

export interface AccountRow {
  accountId: string
  name: string
  stockCount: number
  holdingCount: number
  profit: number
}

export function accountRows(state: TradeState): AccountRow[] {
  return state.accounts
    .filter((account) => !account.deletedAt)
    .map((account) => {
      const stocks = state.stocks.filter(
        (stock) => stock.accountId === account.id && !stock.deletedAt,
      )
      const holdingCount = stocks.filter(
        (stock) => stockCycleSummary(stockTransactions(state, stock.id)).totalShares > 0,
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
  stockId: string
  accountName: string
  label: string
  profit: number
}

export function stockProfitRows(state: TradeState): StockProfitRow[] {
  return state.accounts
    .filter((account) => !account.deletedAt)
    .flatMap((account) =>
      state.stocks
        .filter((stock) => stock.accountId === account.id && !stock.deletedAt)
        .map((stock) => ({
          stockId: stock.id,
          accountName: account.name,
          label: `${stock.name}${stock.code}`,
          profit: stockProfit(state, stock.id),
        })),
    )
}

export interface TTradeProfitRow {
  id: string
  stockLabel: string
  buyDate: string
  sellDate: string
  shares: number
  profit: number
}

export function allTTradeRows(state: TradeState): TTradeProfitRow[] {
  return state.stocks
    .filter((stock) => !stock.deletedAt)
    .flatMap((stock) =>
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
