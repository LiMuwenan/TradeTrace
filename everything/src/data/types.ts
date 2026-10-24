/** 交易记录领域模型（与后端对接时作为 API DTO 的基础） */

export type TransactionKind = '买入' | '卖出' | '股息'

/** 交易记录来源：手工录入 / OCR 识别 / 导入 */
export type TransactionSource = 'manual' | 'ocr' | 'import'

/** OCR 识别溯源信息 */
export interface SourceRef {
  imageHash: string
  templateId: string
  lineNo?: number
}

/** 所有实体的公共审计字段 */
export interface EntityMeta {
  /** UUID v4，同步与实体级合并的稳定主键 */
  id: string
  createdAt: string
  updatedAt: string
  /** 软删除墓碑时间，存在即视为已删除 */
  deletedAt?: string
  /** v1 数字 ID，仅用于迁移后保持同一日期内的顺序 */
  legacyId?: number
}

export interface Account extends EntityMeta {
  name: string
}

export interface Stock extends EntityMeta {
  accountId: string
  name: string
  code: string
}

export interface TransactionTrade extends EntityMeta {
  stockId: string
  /** 交易日期 yyyy-MM-dd */
  date: string
  /** 成交时间 HH:mm:ss，手工录入通常为空 */
  time?: string
  price: number
  /** 正=买入，负=卖出，股息为 0 */
  shares: number
  commission: number
  type: TransactionKind
  /** 股息金额，仅 type=股息 时使用（可为负数，表示红利税等调整） */
  dividend?: number
  source: TransactionSource
  sourceRef?: SourceRef
  /** 幂等键：同一份对账单重复导入时用于去重 */
  dedupeKey: string
  expectedRange?: string
  expectedBuyLow?: number
  expectedBuyHigh?: number
  expectedSellLow?: number
  expectedSellHigh?: number
  note?: string
}

/** 做T关联：一笔卖出 ←→ 一笔买入的份额 */
export interface TTrade extends EntityMeta {
  buyTransactionId: string
  sellTransactionId: string
  shares: number
}

/** 数据快照元信息：同步合并时用于冲突判断与增量演进 */
export interface TradeState {
  schemaVersion: 2
  /** 本机设备 ID，合并后沿用本机 */
  deviceId: string
  /** 每次变更 +1，便于后续增量同步 */
  revision: number
  updatedAt: string
  accounts: Account[]
  stocks: Stock[]
  transactions: TransactionTrade[]
  tTrades: TTrade[]
}

export function createEmptyState(deviceId = '', updatedAt = ''): TradeState {
  return {
    schemaVersion: 2,
    deviceId,
    revision: 0,
    updatedAt,
    accounts: [],
    stocks: [],
    transactions: [],
    tTrades: [],
  }
}

/** 本笔交易费用（买入为负，卖出为正，股息为收入；负股息即费用） */
export function transactionCost(trade: TransactionTrade): number {
  if (trade.type === '股息') return trade.dividend ?? 0
  return -trade.price * trade.shares - trade.commission
}

/**
 * 幂等键：把同一笔交易的字段规范化为字符串。
 * 价格与手续费保留两位，避免不同来源的浮点尾差导致重复判定失败。
 */
export function computeDedupeKey(
  code: string,
  input: Pick<TransactionTrade, 'date' | 'type' | 'shares' | 'price' | 'commission' | 'dividend'>,
): string {
  if (input.type === '股息') {
    return [code, input.date, input.type, input.shares, (input.dividend ?? 0).toFixed(2)].join('|')
  }
  return [
    code,
    input.date,
    input.type,
    input.shares,
    input.price.toFixed(2),
    input.commission.toFixed(2),
  ].join('|')
}

/** 新增交易时由 state 层补齐 id / createdAt / updatedAt / source / dedupeKey */
export type TransactionInput = Omit<
  TransactionTrade,
  'id' | 'createdAt' | 'updatedAt' | 'dedupeKey' | 'source'
> & {
  source?: TransactionSource
  dedupeKey?: string
}

export type StockInput = Omit<Stock, 'id' | 'createdAt' | 'updatedAt'>

export type TTradeInput = Omit<TTrade, 'id' | 'createdAt' | 'updatedAt'>
