import { describe, expect, it } from 'vitest'

import { parseThsStatement } from './parse-ths'
import {
  buyFixture,
  crossYearFixture,
  dividendFixture,
  ipoFixture,
  sellFixture,
  taxFixture,
  transferFixture,
  truncatedFixture,
} from './fixtures/ths'

describe('parseThsStatement', () => {
  it('买入：方向、名称、价格、数量、费用、时间与日期', () => {
    const result = parseThsStatement(buyFixture(), { imageWidth: 400, today: '2026-10-25' })
    expect(result.templateId).toBe('ths_zheshang_v1')
    expect(result.accountHint).toBe('浙商证券 *4768')
    expect(result.skipped).toHaveLength(0)
    const row = result.candidates[0]
    expect(row).toMatchObject({
      type: '买入',
      name: '工商银行',
      date: '2026-10-23',
      time: '09:49',
      price: 8.5,
      shares: 1000,
      commission: 5.09,
      amount: 8505.09,
    })
    expect(row.warnings).toEqual([])
  })

  it('卖出：shares 为负，费用由金额反推一致', () => {
    const row = parseThsStatement(sellFixture(), { imageWidth: 400, today: '2026-10-25' }).candidates[0]
    expect(row).toMatchObject({ type: '卖出', name: '贵州茅台', price: 1500, shares: -100, commission: 5 })
    expect(row.warnings).toEqual([])
  })

  it('股息入账：价格列不得作为成交价，dividend 为正', () => {
    const row = parseThsStatement(dividendFixture(), { imageWidth: 400, today: '2026-10-25' }).candidates[0]
    expect(row).toMatchObject({ type: '股息', shares: 0, price: 0, dividend: 166.21, commission: 0 })
    expect(row.note).toContain('8.58')
    expect(row.warnings).toEqual([])
  })

  it('红利税补缴：dividend 为负并带说明', () => {
    const row = parseThsStatement(taxFixture(), { imageWidth: 400, today: '2026-10-25' }).candidates[0]
    expect(row).toMatchObject({ type: '股息', dividend: -16.89, shares: 0, price: 0 })
    expect(row.note).toContain('红利税补缴')
  })

  it('银证转账与申购配号被跳过并标注类型', () => {
    const transfer = parseThsStatement(transferFixture(), { imageWidth: 400, today: '2026-10-25' })
    expect(transfer.candidates).toHaveLength(0)
    expect(transfer.skipped.map((s) => s.kind)).toEqual(['银证转账', '银证转账'])

    const ipo = parseThsStatement(ipoFixture(), { imageWidth: 400, today: '2026-10-25' })
    expect(ipo.candidates).toHaveLength(0)
    expect(ipo.skipped[0].kind).toBe('申购配号')
  })

  it('金额列截断：仍产出候选但带警告且置信度低', () => {
    const row = parseThsStatement(truncatedFixture(), { imageWidth: 400, today: '2026-10-25' }).candidates[0]
    expect(row.price).toBe(10)
    expect(row.shares).toBe(500)
    expect(row.warnings.join()).toContain('金额缺失')
    expect(row.confidence).toBeLessThan(0.7)
  })

  it('跨年：每行使用所属月份分组的年份', () => {
    const result = parseThsStatement(crossYearFixture(), { imageWidth: 400, today: '2027-01-10' })
    expect(result.candidates.map((c) => c.date)).toEqual(['2026-12-31', '2027-01-04'])
  })

  it('金额与价格×数量不一致时给出警告', () => {
    const lines = buyFixture().map((l) => (l.text === '-8,505.09' ? { ...l, text: '-8,600.00' } : l))
    const row = parseThsStatement(lines, { imageWidth: 400, today: '2026-10-25' }).candidates[0]
    expect(row.warnings.join()).toContain('金额与价格×数量不一致')
  })

  it('股息入账金额为负视为税补缴口径错误并提示', () => {
    const lines = dividendFixture().map((l) => (l.text === '166.21' ? { ...l, text: '-166.21' } : l))
    const row = parseThsStatement(lines, { imageWidth: 400, today: '2026-10-25' }).candidates[0]
    expect(row.dividend).toBe(-166.21)
    expect(row.warnings.join()).toContain('负股息')
  })
})
