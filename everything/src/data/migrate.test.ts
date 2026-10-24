import { describe, expect, it } from 'vitest'

import { detectStateVersion, migrateV1ToV2, normalizeState } from './migrate'
import { sortTransactionsAsc, stockCycleSummary } from './stats'
import type { TransactionTrade } from './types'

/** 迁移使用确定性 UUID v5，保证多设备迁移同一份旧数据时 ID 一致 */
const UUID_STABLE = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const NOW = '2026-10-24T00:00:00.000Z'
const DEVICE = 'device-1'

function v1State() {
  return {
    version: 1,
    accounts: [
      { id: 1, name: '华泰', createdAt: '2026-01-01T00:00:00.000Z' },
      { id: 2, name: '中信', createdAt: '2026-01-02T00:00:00.000Z' },
    ],
    stocks: [
      { id: 1, accountId: 1, name: '贵州茅台', code: '600519', createdAt: '2026-01-01T01:00:00.000Z' },
      { id: 2, accountId: 2, name: '平安银行', code: '000001', createdAt: '2026-01-02T01:00:00.000Z' },
    ],
    transactions: [
      {
        id: 1,
        stockId: 1,
        date: '2026-01-01',
        price: 10,
        shares: 100,
        commission: 5,
        type: '买入',
        createdAt: '2026-01-01T02:00:00.000Z',
      },
      {
        id: 2,
        stockId: 1,
        date: '2026-01-10',
        price: 12,
        shares: -100,
        commission: 5,
        type: '卖出',
        createdAt: '2026-01-10T02:00:00.000Z',
      },
      {
        id: 3,
        stockId: 1,
        date: '2026-01-20',
        price: 0,
        shares: 0,
        commission: 0,
        type: '股息',
        dividend: 50,
        createdAt: '2026-01-20T02:00:00.000Z',
      },
      {
        id: 4,
        stockId: 1,
        date: '2026-02-01',
        price: 10,
        shares: 200,
        commission: 0,
        type: '买入',
        createdAt: '2026-02-01T02:00:00.000Z',
      },
      {
        id: 5,
        stockId: 2,
        date: '2026-01-05',
        price: 8,
        shares: 100,
        commission: 2,
        type: '买入',
        createdAt: '2026-01-05T02:00:00.000Z',
      },
    ],
    tTrades: [
      {
        id: 1,
        buyTransactionId: 1,
        sellTransactionId: 2,
        shares: 50,
        createdAt: '2026-01-10T03:00:00.000Z',
      },
    ],
  }
}

describe('migrateV1ToV2', () => {
  const migrated = migrateV1ToV2(v1State(), DEVICE, NOW)

  it('快照元信息升级为 v2', () => {
    expect(migrated.schemaVersion).toBe(2)
    expect(migrated.deviceId).toBe(DEVICE)
    expect(migrated.revision).toBe(1)
    expect(migrated.updatedAt).toBe(NOW)
    expect(migrated.accounts).toHaveLength(2)
    expect(migrated.stocks).toHaveLength(2)
    expect(migrated.transactions).toHaveLength(5)
    expect(migrated.tTrades).toHaveLength(1)
  })

  it('实体 ID 换为稳定 UUID 且保留 legacyId', () => {
    for (const account of migrated.accounts) {
      expect(account.id).toMatch(UUID_STABLE)
      expect(account.updatedAt).toBe(account.createdAt)
      expect(account.deletedAt).toBeUndefined()
      expect(account.legacyId).toBeGreaterThan(0)
    }
    for (const stock of migrated.stocks) {
      expect(stock.id).toMatch(UUID_STABLE)
      expect(stock.legacyId).toBeGreaterThan(0)
    }
    for (const trade of migrated.transactions) {
      expect(trade.id).toMatch(UUID_STABLE)
      expect(trade.legacyId).toBeGreaterThan(0)
    }
    expect(migrated.tTrades[0].id).toMatch(UUID_STABLE)
    expect(migrated.tTrades[0].legacyId).toBe(1)
  })

  it('同一份旧数据在两台设备上迁移得到相同 ID（合并不会重复）', () => {
    const first = migrateV1ToV2(v1State(), 'device-a', NOW)
    const second = migrateV1ToV2(v1State(), 'device-b', '2026-10-25T00:00:00.000Z')
    expect(first.accounts.map((item) => item.id)).toEqual(second.accounts.map((item) => item.id))
    expect(first.stocks.map((item) => item.id)).toEqual(second.stocks.map((item) => item.id))
    expect(first.transactions.map((item) => item.id)).toEqual(
      second.transactions.map((item) => item.id),
    )
    expect(first.tTrades.map((item) => item.id)).toEqual(second.tTrades.map((item) => item.id))
  })

  it('引用关系按旧 ID 正确映射', () => {
    const account1 = migrated.accounts.find((item) => item.legacyId === 1)
    const account2 = migrated.accounts.find((item) => item.legacyId === 2)
    const stock1 = migrated.stocks.find((item) => item.legacyId === 1)
    const stock2 = migrated.stocks.find((item) => item.legacyId === 2)
    expect(stock1?.accountId).toBe(account1?.id)
    expect(stock2?.accountId).toBe(account2?.id)

    const buy = migrated.transactions.find((item) => item.legacyId === 1)
    const sell = migrated.transactions.find((item) => item.legacyId === 2)
    expect(buy?.stockId).toBe(stock1?.id)
    expect(migrated.tTrades[0].buyTransactionId).toBe(buy?.id)
    expect(migrated.tTrades[0].sellTransactionId).toBe(sell?.id)
  })

  it('交易补齐来源、幂等键与审计字段', () => {
    for (const trade of migrated.transactions) {
      expect(trade.source).toBe('manual')
      expect(trade.dedupeKey.length).toBeGreaterThan(0)
      expect(trade.updatedAt).toBe(trade.createdAt)
      expect(trade.deletedAt).toBeUndefined()
    }
    const moutai = migrated.transactions.find((item) => item.legacyId === 1)
    expect(moutai?.dedupeKey).toBe('600519|2026-01-01|买入|100|10.00|5.00')
    const dividend = migrated.transactions.find((item) => item.legacyId === 3)
    expect(dividend?.dedupeKey).toBe('600519|2026-01-20|股息|0|50.00')
  })

  it('贵州茅台六项指标与迁移前口径一致', () => {
    const stock = migrated.stocks.find((item) => item.legacyId === 1)
    const trades = migrated.transactions.filter((item) => item.stockId === stock?.id)
    const summary = stockCycleSummary(trades)
    expect(summary.totalShares).toBe(200)
    expect(summary.totalCost).toBe(-1760)
    expect(summary.avgCost).toBeCloseTo(10)
    expect(summary.cycleCost).toBe(-2000)
    expect(summary.totalAvgCost).toBeCloseTo(8.8)
    expect(summary.totalCost - summary.cycleCost).toBe(240)
  })

  it('同日期交易按 legacyId 保持旧顺序', () => {
    const sameDay: TransactionTrade[] = [
      { ...migrated.transactions[1], legacyId: 2, date: '2026-03-01' },
      { ...migrated.transactions[0], legacyId: 1, date: '2026-03-01' },
    ]
    expect(sortTransactionsAsc(sameDay).map((item) => item.legacyId)).toEqual([1, 2])
  })
})

describe('normalizeState', () => {
  it('v2 状态保留设备 ID 与 revision', () => {
    const migrated = migrateV1ToV2(v1State(), DEVICE, NOW)
    const normalized = normalizeState(
      { ...migrated, revision: 7, deviceId: 'remote-device' },
      DEVICE,
      NOW,
    )
    expect(normalized.schemaVersion).toBe(2)
    expect(normalized.deviceId).toBe('remote-device')
    expect(normalized.revision).toBe(7)
    expect(normalized.transactions).toHaveLength(5)
  })

  it('v1 状态自动迁移', () => {
    const normalized = normalizeState(v1State(), DEVICE, NOW)
    expect(normalized.schemaVersion).toBe(2)
    expect(normalized.deviceId).toBe(DEVICE)
    expect(normalized.accounts.every((item) => item.id.match(UUID_STABLE))).toBe(true)
  })

  it('未知版本不迁移也不报错，交给调用方 fail-closed', () => {
    const future = { schemaVersion: 3, accounts: [{ id: 'a-1', name: '未来版本' }] }
    expect(detectStateVersion(future)).toBeNull()
    expect(normalizeState(future, DEVICE, NOW).accounts).toEqual([])
    expect(detectStateVersion({ foo: 'bar' })).toBeNull()
    expect(detectStateVersion({ schemaVersion: 2, accounts: [] })).toBe(2)
    expect(detectStateVersion({ version: 1, accounts: [{ id: 1, name: '旧' }] })).toBe(1)
  })

  it('非法输入返回空状态', () => {
    expect(normalizeState(null, DEVICE, NOW)).toMatchObject({ schemaVersion: 2, deviceId: DEVICE })
    expect(normalizeState('bad', DEVICE, NOW).accounts).toEqual([])
    expect(normalizeState({ schemaVersion: 2, accounts: 'bad' }, DEVICE, NOW).accounts).toEqual([])
  })

  it('v2 非法实体被丢弃', () => {
    const normalized = normalizeState(
      {
        schemaVersion: 2,
        accounts: [{ id: '', name: '无效' }, { id: 'a-1', name: '有效' }],
        stocks: [],
        transactions: [],
        tTrades: [],
      },
      DEVICE,
      NOW,
    )
    expect(normalized.accounts).toHaveLength(1)
    expect(normalized.accounts[0].name).toBe('有效')
  })
})
