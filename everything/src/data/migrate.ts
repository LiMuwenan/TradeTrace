import { createStableId } from './ids'
import { computeDedupeKey, createEmptyState } from './types'
import type {
  Account,
  EntityMeta,
  Stock,
  TradeState,
  TransactionKind,
  TransactionSource,
  TransactionTrade,
  TTrade,
} from './types'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asKind(value: unknown): TransactionKind {
  return value === '卖出' || value === '股息' ? value : '买入'
}

function asSource(value: unknown): TransactionSource {
  return value === 'ocr' || value === 'import' ? value : 'manual'
}

/** 公共审计字段：v1 迁移与 v2 校验共用 */
function baseMeta(item: Record<string, unknown>, now: string): EntityMeta | null {
  if (typeof item.id !== 'string' || !item.id) return null
  const createdAt = asString(item.createdAt, now)
  return {
    id: item.id,
    createdAt,
    updatedAt: asString(item.updatedAt, createdAt),
    ...(typeof item.deletedAt === 'string' && item.deletedAt ? { deletedAt: item.deletedAt } : {}),
    ...(typeof item.legacyId === 'number' ? { legacyId: item.legacyId } : {}),
  }
}

function optionalNumber(value: unknown): { value?: number } {
  return typeof value === 'number' && Number.isFinite(value) ? { value } : {}
}

function optionalString(value: unknown): { value?: string } {
  return typeof value === 'string' && value ? { value } : {}
}

/** v1 → v2：数字 ID 换 UUID、补齐审计字段、来源与幂等键 */
export function migrateV1ToV2(raw: unknown, deviceId: string, now: string): TradeState {
  if (!isRecord(raw)) return createEmptyState(deviceId, now)

  const accountIds = new Map<number, string>()
  const accounts: Account[] = []
  for (const item of Array.isArray(raw.accounts) ? raw.accounts : []) {
    if (!isRecord(item)) continue
    const legacyId = asNumber(item.id, NaN)
    if (!Number.isFinite(legacyId)) continue
    const createdAt = asString(item.createdAt, now)
    const account: Account = {
      id: createStableId(`v1:account:${legacyId}`),
      createdAt,
      updatedAt: createdAt,
      legacyId,
      name: asString(item.name),
    }
    accountIds.set(legacyId, account.id)
    accounts.push(account)
  }

  const stockIds = new Map<number, string>()
  const stockCodes = new Map<string, string>()
  const stocks: Stock[] = []
  for (const item of Array.isArray(raw.stocks) ? raw.stocks : []) {
    if (!isRecord(item)) continue
    const legacyId = asNumber(item.id, NaN)
    if (!Number.isFinite(legacyId)) continue
    const accountId = accountIds.get(asNumber(item.accountId, NaN))
    if (!accountId) continue
    const createdAt = asString(item.createdAt, now)
    const stock: Stock = {
      id: createStableId(`v1:stock:${legacyId}`),
      createdAt,
      updatedAt: createdAt,
      legacyId,
      accountId,
      name: asString(item.name),
      code: asString(item.code),
    }
    stockIds.set(legacyId, stock.id)
    stockCodes.set(stock.id, stock.code)
    stocks.push(stock)
  }

  const transactionIds = new Map<number, string>()
  const transactions: TransactionTrade[] = []
  for (const item of Array.isArray(raw.transactions) ? raw.transactions : []) {
    if (!isRecord(item)) continue
    const legacyId = asNumber(item.id, NaN)
    if (!Number.isFinite(legacyId)) continue
    const stockId = stockIds.get(asNumber(item.stockId, NaN))
    if (!stockId) continue
    const createdAt = asString(item.createdAt, now)
    const date = asString(item.date)
    const type = asKind(item.type)
    const price = asNumber(item.price)
    const shares = asNumber(item.shares)
    const commission = asNumber(item.commission)
    const dividend = optionalNumber(item.dividend).value
    const time = optionalString(item.time).value
    const note = optionalString(item.note).value
    const expectedRange = optionalString(item.expectedRange).value
    const expectedBuyLow = optionalNumber(item.expectedBuyLow).value
    const expectedBuyHigh = optionalNumber(item.expectedBuyHigh).value
    const expectedSellLow = optionalNumber(item.expectedSellLow).value
    const expectedSellHigh = optionalNumber(item.expectedSellHigh).value

    const trade: TransactionTrade = {
      id: createStableId(`v1:transaction:${legacyId}`),
      createdAt,
      updatedAt: createdAt,
      legacyId,
      stockId,
      date,
      price,
      shares,
      commission,
      type,
      source: 'manual',
      dedupeKey: computeDedupeKey(stockCodes.get(stockId) ?? '', {
        date,
        type,
        shares,
        price,
        commission,
        dividend,
      }),
      ...(dividend !== undefined ? { dividend } : {}),
      ...(time !== undefined ? { time } : {}),
      ...(note !== undefined ? { note } : {}),
      ...(expectedRange !== undefined ? { expectedRange } : {}),
      ...(expectedBuyLow !== undefined ? { expectedBuyLow } : {}),
      ...(expectedBuyHigh !== undefined ? { expectedBuyHigh } : {}),
      ...(expectedSellLow !== undefined ? { expectedSellLow } : {}),
      ...(expectedSellHigh !== undefined ? { expectedSellHigh } : {}),
    }
    transactionIds.set(legacyId, trade.id)
    transactions.push(trade)
  }

  const tTrades: TTrade[] = []
  for (const item of Array.isArray(raw.tTrades) ? raw.tTrades : []) {
    if (!isRecord(item)) continue
    const legacyId = asNumber(item.id, NaN)
    if (!Number.isFinite(legacyId)) continue
    const buyTransactionId = transactionIds.get(asNumber(item.buyTransactionId, NaN))
    const sellTransactionId = transactionIds.get(asNumber(item.sellTransactionId, NaN))
    if (!buyTransactionId || !sellTransactionId) continue
    const createdAt = asString(item.createdAt, now)
    tTrades.push({
      id: createStableId(`v1:ttrade:${legacyId}`),
      createdAt,
      updatedAt: createdAt,
      legacyId,
      buyTransactionId,
      sellTransactionId,
      shares: asNumber(item.shares),
    })
  }

  return {
    ...createEmptyState(deviceId, now),
    revision: 1,
    accounts,
    stocks,
    transactions,
    tTrades,
  }
}

function normalizeAccount(item: Record<string, unknown>, now: string): Account | null {
  const meta = baseMeta(item, now)
  if (!meta || typeof item.name !== 'string') return null
  return { ...meta, name: item.name }
}

function normalizeStock(item: Record<string, unknown>, now: string): Stock | null {
  const meta = baseMeta(item, now)
  if (!meta || typeof item.accountId !== 'string' || !item.accountId) return null
  return {
    ...meta,
    accountId: item.accountId,
    name: asString(item.name),
    code: asString(item.code),
  }
}

function normalizeTransaction(
  item: Record<string, unknown>,
  now: string,
  stockCodes: Map<string, string>,
): TransactionTrade | null {
  const meta = baseMeta(item, now)
  if (!meta || typeof item.stockId !== 'string' || !item.stockId) return null
  if (typeof item.date !== 'string' || !item.date) return null
  if (item.type !== '买入' && item.type !== '卖出' && item.type !== '股息') return null

  const type = item.type
  const price = asNumber(item.price)
  const shares = asNumber(item.shares)
  const commission = asNumber(item.commission)
  const date = item.date
  const dividend = optionalNumber(item.dividend).value
  const time = optionalString(item.time).value
  const note = optionalString(item.note).value
  const expectedRange = optionalString(item.expectedRange).value
  const expectedBuyLow = optionalNumber(item.expectedBuyLow).value
  const expectedBuyHigh = optionalNumber(item.expectedBuyHigh).value
  const expectedSellLow = optionalNumber(item.expectedSellLow).value
  const expectedSellHigh = optionalNumber(item.expectedSellHigh).value
  const sourceRef = isRecord(item.sourceRef) ? (item.sourceRef as unknown as TransactionTrade['sourceRef']) : undefined

  return {
    ...meta,
    stockId: item.stockId,
    date,
    price,
    shares,
    commission,
    type,
    source: asSource(item.source),
    dedupeKey:
      asString(item.dedupeKey) ||
      computeDedupeKey(stockCodes.get(item.stockId) ?? '', {
        date,
        type,
        shares,
        price,
        commission,
        dividend,
      }),
    ...(dividend !== undefined ? { dividend } : {}),
    ...(time !== undefined ? { time } : {}),
    ...(note !== undefined ? { note } : {}),
    ...(sourceRef !== undefined ? { sourceRef } : {}),
    ...(expectedBuyLow !== undefined ? { expectedBuyLow } : {}),
    ...(expectedBuyHigh !== undefined ? { expectedBuyHigh } : {}),
    ...(expectedSellLow !== undefined ? { expectedSellLow } : {}),
    ...(expectedSellHigh !== undefined ? { expectedSellHigh } : {}),
    ...(expectedRange !== undefined ? { expectedRange } : {}),
  }
}

function normalizeTTrade(item: Record<string, unknown>, now: string): TTrade | null {
  const meta = baseMeta(item, now)
  if (!meta || typeof item.buyTransactionId !== 'string' || !item.buyTransactionId) return null
  if (typeof item.sellTransactionId !== 'string' || !item.sellTransactionId) return null
  return {
    ...meta,
    buyTransactionId: item.buyTransactionId,
    sellTransactionId: item.sellTransactionId,
    shares: asNumber(item.shares),
  }
}

function normalizeV2(raw: Record<string, unknown>, deviceId: string, now: string): TradeState {
  const stocks = (Array.isArray(raw.stocks) ? raw.stocks : [])
    .filter(isRecord)
    .map((item) => normalizeStock(item, now))
    .filter((item): item is Stock => item !== null)
  const stockCodes = new Map(stocks.map((stock) => [stock.id, stock.code]))

  const accounts = (Array.isArray(raw.accounts) ? raw.accounts : [])
    .filter(isRecord)
    .map((item) => normalizeAccount(item, now))
    .filter((item): item is Account => item !== null)

  const transactions = (Array.isArray(raw.transactions) ? raw.transactions : [])
    .filter(isRecord)
    .map((item) => normalizeTransaction(item, now, stockCodes))
    .filter((item): item is TransactionTrade => item !== null)

  const tTrades = (Array.isArray(raw.tTrades) ? raw.tTrades : [])
    .filter(isRecord)
    .map((item) => normalizeTTrade(item, now))
    .filter((item): item is TTrade => item !== null)

  return {
    schemaVersion: 2,
    deviceId: asString(raw.deviceId) || deviceId,
    revision: asNumber(raw.revision),
    updatedAt: asString(raw.updatedAt, now),
    accounts,
    stocks,
    transactions,
    tTrades,
  }
}

/** 原始数据版本：1 = 旧版数字 ID，2 = 当前 UUID 模型 */
export type StateVersion = 1 | 2

const STATE_ARRAY_KEYS = ['accounts', 'stocks', 'transactions', 'tTrades'] as const

/** 结构上是状态对象（含至少一个实体数组） */
export function isStateShape(value: unknown): value is Record<string, unknown> {
  if (!isRecord(value)) return false
  return STATE_ARRAY_KEYS.some((key) => Array.isArray(value[key]))
}

/**
 * 识别原始数据的版本，无法识别时返回 null（调用方应 fail-closed，不得写盘覆盖）。
 * - `schemaVersion` 明确时以它为准，未知值（如未来版本）返回 null；
 * - 无版本号时按实体 ID 类型判断：字符串 ID = v2，数字 ID = v1。
 */
export function detectStateVersion(raw: unknown): StateVersion | null {
  if (!isRecord(raw)) return null
  if (isRecord(raw.state)) return detectStateVersion(raw.state)
  if (raw.schemaVersion === 1) return 1
  if (raw.schemaVersion === 2) return 2
  if (raw.schemaVersion !== undefined) return null
  if (!isStateShape(raw)) return null

  for (const key of STATE_ARRAY_KEYS) {
    const list = raw[key]
    if (!Array.isArray(list)) continue
    for (const item of list) {
      if (!isRecord(item) || item.id === undefined) continue
      if (typeof item.id === 'string' && item.id) return 2
      if (typeof item.id === 'number') return 1
    }
  }
  // 结构正确但全为空数组：按 v1 处理，迁移后会补齐 v2 元信息
  return 1
}

/** 读取本地或云端数据时统一入口：v2 校验，v1 自动迁移，未知版本返回空状态 */
export function normalizeState(raw: unknown, deviceId: string, now: string): TradeState {
  const version = detectStateVersion(raw)
  if (version === null) return createEmptyState(deviceId, now)
  if (version === 2) {
    const record = isRecord(raw) && isRecord(raw.state) ? raw.state : raw
    return normalizeV2(record as Record<string, unknown>, deviceId, now)
  }
  const record = isRecord(raw) && isRecord(raw.state) ? raw.state : raw
  return migrateV1ToV2(record, deviceId, now)
}
