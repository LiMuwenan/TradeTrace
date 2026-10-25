import { describe, expect, it } from 'vitest'

import type { OcrLine } from './types'
import { assignColumn, findHeaderAnchors, groupIntoBands } from './layout'

function line(text: string, x: number, y: number, width = 60, height = 20): OcrLine {
  return { text, x, y, width, height, confidence: 0.95 }
}

const header = [
  line('操作', 10, 100, 40),
  line('价格/数量', 150, 100, 80),
  line('金额/费用', 280, 100, 80),
]

describe('layout', () => {
  it('按纵坐标聚行带，容差内合并、超出另起一带', () => {
    const bands = groupIntoBands([
      line('证券买入-工商银行', 10, 160),
      line('8.500', 150, 161),
      line('买 10-23 09:49', 10, 181),
      line('1000', 150, 182),
    ])
    expect(bands).toHaveLength(2)
    expect(bands[0].lines.map((l) => l.text)).toEqual(['证券买入-工商银行', '8.500'])
    expect(bands[1].lines.map((l) => l.text)).toEqual(['买 10-23 09:49', '1000'])
  })

  it('表头三列锚点可定位', () => {
    expect(findHeaderAnchors(header)).toEqual({ op: 10, price: 150, amount: 280 })
    expect(findHeaderAnchors([line('随便', 1, 1)])).toBeNull()
  })

  it('列归属按最近表头左边界', () => {
    const anchors = findHeaderAnchors(header)!
    expect(assignColumn(line('证券买入', 12, 160, 120), anchors)).toBe('op')
    expect(assignColumn(line('8.500', 152, 160), anchors)).toBe('price')
    expect(assignColumn(line('-8,505.09', 285, 160), anchors)).toBe('amount')
  })
})
