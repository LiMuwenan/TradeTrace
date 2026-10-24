import { describe, expect, it } from 'vitest'

import { computeDedupeKey, createEmptyState, transactionCost } from './types'
import type { TransactionTrade } from './types'

function trade(
  partial: Partial<TransactionTrade> & Pick<TransactionTrade, 'type'>,
): TransactionTrade {
  return {
    id: 'trade-1',
    stockId: 'stock-1',
    date: '2026-01-01',
    price: 0,
    shares: 0,
    commission: 0,
    source: 'manual',
    dedupeKey: '',
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt: '2026-01-01T00:00:00.000Z',
    ...partial,
  }
}

describe('transactionCost', () => {
  it('买入为负费用，卖出为正收益，股息为收入', () => {
    expect(transactionCost(trade({ type: '买入', price: 10, shares: 100, commission: 5 }))).toBe(
      -1005,
    )
    expect(transactionCost(trade({ type: '卖出', price: 12, shares: -100, commission: 5 }))).toBe(
      1195,
    )
    expect(transactionCost(trade({ type: '股息', dividend: 50 }))).toBe(50)
  })

  it('负股息（红利税等调整）返回负数', () => {
    expect(transactionCost(trade({ type: '股息', dividend: -20 }))).toBe(-20)
  })
})

describe('computeDedupeKey', () => {
  const base = {
    date: '2026-01-02',
    type: '买入' as const,
    shares: 100,
    price: 10,
    commission: 5,
  }

  it('价格与手续费尾差归一化后键稳定', () => {
    expect(computeDedupeKey('600519', base)).toBe(
      computeDedupeKey('600519', { ...base, price: 10.004, commission: 5.001 }),
    )
  })

  it('股票代码、日期、方向不同则键不同', () => {
    const key = computeDedupeKey('600519', base)
    expect(computeDedupeKey('000001', base)).not.toBe(key)
    expect(computeDedupeKey('600519', { ...base, date: '2026-01-03' })).not.toBe(key)
    expect(computeDedupeKey('600519', { ...base, type: '卖出', shares: -100 })).not.toBe(key)
  })

  it('股息用金额区分，不混入价格与手续费', () => {
    const dividend = { date: '2026-02-01', type: '股息' as const, shares: 0, price: 0, commission: 0, dividend: 50 }
    expect(computeDedupeKey('600519', dividend)).toBe('600519|2026-02-01|股息|0|50.00')
    expect(computeDedupeKey('600519', { ...dividend, dividend: 60 })).not.toBe(
      computeDedupeKey('600519', dividend),
    )
  })
})

describe('createEmptyState', () => {
  it('返回 v2 空状态并携带快照元信息', () => {
    expect(createEmptyState('device-1', '2026-01-01T00:00:00.000Z')).toEqual({
      schemaVersion: 2,
      deviceId: 'device-1',
      revision: 0,
      updatedAt: '2026-01-01T00:00:00.000Z',
      accounts: [],
      stocks: [],
      transactions: [],
      tTrades: [],
    })
  })
})
