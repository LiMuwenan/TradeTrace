import { createEmptyState } from './types'
import type { Account, Stock, TradeState, TransactionTrade, TTrade } from './types'

function nextId(items: { id: number }[]): number {
  return items.reduce((max, item) => Math.max(max, item.id), 0) + 1
}

export function addAccount(state: TradeState, name: string, createdAt: string): TradeState {
  const account: Account = { id: nextId(state.accounts), name, createdAt }
  return { ...state, accounts: [...state.accounts, account] }
}

export function deleteAccount(state: TradeState, accountId: number): TradeState {
  const stockIds = new Set(state.stocks.filter((s) => s.accountId === accountId).map((s) => s.id))
  const transactionIds = new Set(
    state.transactions.filter((t) => stockIds.has(t.stockId)).map((t) => t.id),
  )
  return {
    ...state,
    accounts: state.accounts.filter((a) => a.id !== accountId),
    stocks: state.stocks.filter((s) => s.accountId !== accountId),
    transactions: state.transactions.filter((t) => !stockIds.has(t.stockId)),
    tTrades: state.tTrades.filter(
      (tt) =>
        !transactionIds.has(tt.buyTransactionId) && !transactionIds.has(tt.sellTransactionId),
    ),
  }
}

export function addStock(state: TradeState, stock: Omit<Stock, 'id'>): TradeState {
  return { ...state, stocks: [...state.stocks, { ...stock, id: nextId(state.stocks) }] }
}

export function updateStock(state: TradeState, stock: Stock): TradeState {
  return {
    ...state,
    stocks: state.stocks.map((s) => (s.id === stock.id ? stock : s)),
  }
}

export function deleteStock(state: TradeState, stockId: number): TradeState {
  const transactionIds = new Set(
    state.transactions.filter((t) => t.stockId === stockId).map((t) => t.id),
  )
  return {
    ...state,
    stocks: state.stocks.filter((s) => s.id !== stockId),
    transactions: state.transactions.filter((t) => t.stockId !== stockId),
    tTrades: state.tTrades.filter(
      (tt) =>
        !transactionIds.has(tt.buyTransactionId) && !transactionIds.has(tt.sellTransactionId),
    ),
  }
}

export function addTransaction(
  state: TradeState,
  trade: Omit<TransactionTrade, 'id'>,
): TradeState {
  return {
    ...state,
    transactions: [...state.transactions, { ...trade, id: nextId(state.transactions) }],
  }
}

export function updateTransaction(state: TradeState, trade: TransactionTrade): TradeState {
  return {
    ...state,
    transactions: state.transactions.map((t) => (t.id === trade.id ? trade : t)),
  }
}

export function deleteTransaction(state: TradeState, transactionId: number): TradeState {
  return {
    ...state,
    transactions: state.transactions.filter((t) => t.id !== transactionId),
    tTrades: state.tTrades.filter(
      (tt) =>
        tt.buyTransactionId !== transactionId && tt.sellTransactionId !== transactionId,
    ),
  }
}

export function addTTrade(state: TradeState, ttrade: Omit<TTrade, 'id'>): TradeState {
  return { ...state, tTrades: [...state.tTrades, { ...ttrade, id: nextId(state.tTrades) }] }
}

export function deleteTTrade(state: TradeState, ttradeId: number): TradeState {
  return { ...state, tTrades: state.tTrades.filter((tt) => tt.id !== ttradeId) }
}

export function deleteTTradesBySell(state: TradeState, sellId: number): TradeState {
  return { ...state, tTrades: state.tTrades.filter((tt) => tt.sellTransactionId !== sellId) }
}

/** 数据校验：读取本地缓存时兜底，避免脏数据导致白屏 */
export function normalizeState(raw: unknown): TradeState {
  if (!raw || typeof raw !== 'object') return createEmptyState()
  const value = raw as Partial<TradeState>
  return {
    version: 1,
    accounts: Array.isArray(value.accounts) ? value.accounts : [],
    stocks: Array.isArray(value.stocks) ? value.stocks : [],
    transactions: Array.isArray(value.transactions) ? value.transactions : [],
    tTrades: Array.isArray(value.tTrades) ? value.tTrades : [],
  }
}
