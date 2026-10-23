/** 交易记录领域模型（与后端对接时作为 API DTO 的基础） */

export type TransactionKind = '买入' | '卖出' | '股息'

export interface Account {
  id: number
  name: string
  createdAt: string
}

export interface Stock {
  id: number
  accountId: number
  name: string
  code: string
  createdAt: string
}

export interface TransactionTrade {
  id: number
  stockId: number
  /** 交易日期 yyyy-MM-dd */
  date: string
  price: number
  /** 正=买入，负=卖出，股息为 0 */
  shares: number
  commission: number
  type: TransactionKind
  /** 股息金额，仅 type=股息 时使用 */
  dividend?: number
  expectedRange?: string
  expectedBuyLow?: number
  expectedBuyHigh?: number
  expectedSellLow?: number
  expectedSellHigh?: number
  note?: string
  createdAt: string
}

/** 做T关联：一笔卖出 ←→ 一笔买入的份额 */
export interface TTrade {
  id: number
  buyTransactionId: number
  sellTransactionId: number
  shares: number
  createdAt: string
}

export interface TradeState {
  version: 1
  accounts: Account[]
  stocks: Stock[]
  transactions: TransactionTrade[]
  tTrades: TTrade[]
}

export function createEmptyState(): TradeState {
  return { version: 1, accounts: [], stocks: [], transactions: [], tTrades: [] }
}

/** 本笔交易费用（买入为负，卖出为正，股息为收入） */
export function transactionCost(trade: TransactionTrade): number {
  if (trade.type === '股息') return trade.dividend ?? 0
  return -trade.price * trade.shares - trade.commission
}
