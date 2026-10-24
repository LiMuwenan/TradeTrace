import { createId } from './ids'
import { computeDedupeKey } from './types'
import type {
  Account,
  EntityMeta,
  Stock,
  StockInput,
  TradeState,
  TransactionInput,
  TransactionTrade,
  TTrade,
  TTradeInput,
} from './types'

type MutableLists = Pick<TradeState, 'accounts' | 'stocks' | 'transactions' | 'tTrades'>

/** 任何变更都推进快照版本，供同步合并判断新旧 */
function touch(state: TradeState, now: string, patch: Partial<MutableLists>): TradeState {
  return { ...state, ...patch, revision: state.revision + 1, updatedAt: now }
}

/** 软删除：只写墓碑，不物理移除，保证另一台设备上的旧副本不会复活数据 */
function tombstone<T extends EntityMeta>(
  items: T[],
  match: (item: T) => boolean,
  now: string,
): T[] {
  return items.map((item) =>
    match(item) && !item.deletedAt ? { ...item, deletedAt: now, updatedAt: now } : item,
  )
}

export function addAccount(state: TradeState, name: string, now: string): TradeState {
  const account: Account = {
    id: createId(),
    name,
    createdAt: now,
    updatedAt: now,
  }
  return touch(state, now, { accounts: [...state.accounts, account] })
}

export function deleteAccount(state: TradeState, accountId: string, now: string): TradeState {
  const stockIds = new Set(
    state.stocks.filter((item) => item.accountId === accountId && !item.deletedAt).map((item) => item.id),
  )
  const transactionIds = new Set(
    state.transactions
      .filter((item) => stockIds.has(item.stockId) && !item.deletedAt)
      .map((item) => item.id),
  )
  return touch(state, now, {
    accounts: tombstone(state.accounts, (item) => item.id === accountId, now),
    stocks: tombstone(state.stocks, (item) => stockIds.has(item.id), now),
    transactions: tombstone(state.transactions, (item) => transactionIds.has(item.id), now),
    tTrades: tombstone(
      state.tTrades,
      (item) =>
        transactionIds.has(item.buyTransactionId) || transactionIds.has(item.sellTransactionId),
      now,
    ),
  })
}

export function addStock(state: TradeState, input: StockInput, now: string): TradeState {
  const stock: Stock = {
    ...input,
    id: createId(),
    createdAt: now,
    updatedAt: now,
  }
  return touch(state, now, { stocks: [...state.stocks, stock] })
}

export function updateStock(state: TradeState, stock: Stock, now: string): TradeState {
  return touch(state, now, {
    stocks: state.stocks.map((item) =>
      item.id === stock.id ? { ...stock, updatedAt: now } : item,
    ),
  })
}

export function deleteStock(state: TradeState, stockId: string, now: string): TradeState {
  const transactionIds = new Set(
    state.transactions
      .filter((item) => item.stockId === stockId && !item.deletedAt)
      .map((item) => item.id),
  )
  return touch(state, now, {
    stocks: tombstone(state.stocks, (item) => item.id === stockId, now),
    transactions: tombstone(state.transactions, (item) => transactionIds.has(item.id), now),
    tTrades: tombstone(
      state.tTrades,
      (item) =>
        transactionIds.has(item.buyTransactionId) || transactionIds.has(item.sellTransactionId),
      now,
    ),
  })
}

export function addTransaction(
  state: TradeState,
  input: TransactionInput,
  now: string,
): TradeState {
  const stock = state.stocks.find((item) => item.id === input.stockId)
  const trade: TransactionTrade = {
    ...input,
    id: createId(),
    createdAt: now,
    updatedAt: now,
    source: input.source ?? 'manual',
    dedupeKey: input.dedupeKey ?? computeDedupeKey(stock?.code ?? '', input),
  }
  return touch(state, now, { transactions: [...state.transactions, trade] })
}

export function updateTransaction(
  state: TradeState,
  trade: TransactionTrade,
  now: string,
): TradeState {
  const stock = state.stocks.find((item) => item.id === trade.stockId)
  const updated: TransactionTrade = {
    ...trade,
    updatedAt: now,
    dedupeKey: computeDedupeKey(stock?.code ?? '', trade),
  }
  return touch(state, now, {
    transactions: state.transactions.map((item) => (item.id === updated.id ? updated : item)),
  })
}

export function deleteTransaction(
  state: TradeState,
  transactionId: string,
  now: string,
): TradeState {
  return touch(state, now, {
    transactions: tombstone(state.transactions, (item) => item.id === transactionId, now),
    tTrades: tombstone(
      state.tTrades,
      (item) =>
        item.buyTransactionId === transactionId || item.sellTransactionId === transactionId,
      now,
    ),
  })
}

export function addTTrade(state: TradeState, input: TTradeInput, now: string): TradeState {
  const ttrade: TTrade = {
    ...input,
    id: createId(),
    createdAt: now,
    updatedAt: now,
  }
  return touch(state, now, { tTrades: [...state.tTrades, ttrade] })
}

export function deleteTTrade(state: TradeState, ttradeId: string, now: string): TradeState {
  return touch(state, now, {
    tTrades: tombstone(state.tTrades, (item) => item.id === ttradeId, now),
  })
}

export function deleteTTradesBySell(state: TradeState, sellId: string, now: string): TradeState {
  return touch(state, now, {
    tTrades: tombstone(state.tTrades, (item) => item.sellTransactionId === sellId, now),
  })
}
