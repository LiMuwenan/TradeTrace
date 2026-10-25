import { describe, expect, it } from 'vitest'

import { candidateToInput, normalizeStockName, resolveStockId } from './normalize'
import type { ParsedRow } from './types'

const candidate: ParsedRow = {
  rowIndex: 3,
  templateId: 'ths_zheshang_v1',
  rawBlock: [],
  type: '买入',
  name: '工商银行',
  date: '2026-10-23',
  time: '09:49',
  price: 8.5,
  shares: 1000,
  commission: 5.09,
  amount: 8505.09,
  confidence: 0.95,
  warnings: [],
}

describe('normalize', () => {
  it('去除除权除息与风险标识前缀', () => {
    expect(normalizeStockName('XD工商银行')).toBe('工商银行')
    expect(normalizeStockName('XR贵州茅台')).toBe('贵州茅台')
    expect(normalizeStockName('DR平安银行')).toBe('平安银行')
    expect(normalizeStockName('*ST海航')).toBe('海航')
    expect(normalizeStockName('ST 中珠')).toBe('中珠')
    expect(normalizeStockName('N华新')).toBe('华新')
    expect(normalizeStockName('工商银行')).toBe('工商银行')
  })

  it('按归一化名称映射到已有股票', () => {
    const stocks = [
      { id: 's1', name: '工商银行', code: '601398' },
      { id: 's2', name: '贵州茅台', code: '600519' },
    ]
    expect(resolveStockId('XD工商银行', stocks)).toBe('s1')
    expect(resolveStockId('招商银行', stocks)).toBeNull()
  })

  it('候选转换保留来源与备注，卖出股数为负', () => {
    const input = candidateToInput(candidate, 's1', { imageHash: 'hash', templateId: 'ths_zheshang_v1', lineNo: 3 })
    expect(input).toMatchObject({
      stockId: 's1',
      date: '2026-10-23',
      time: '09:49',
      shares: 1000,
      price: 8.5,
      commission: 5.09,
      type: '买入',
      source: 'ocr',
      sourceRef: { imageHash: 'hash', templateId: 'ths_zheshang_v1', lineNo: 3 },
    })
  })

  it('股息候选转换带上 dividend', () => {
    const input = candidateToInput(
      { ...candidate, type: '股息', shares: 0, price: 0, dividend: -16.89, amount: -16.89 },
      's1',
      { imageHash: 'h2', templateId: 'ths_zheshang_v1' },
    )
    expect(input.dividend).toBe(-16.89)
    expect(input.shares).toBe(0)
  })
})
