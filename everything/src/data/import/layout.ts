import type { OcrLine } from './types'

export interface RowBand {
  /** 行带中心 y（取该带首行的中心） */
  y: number
  /** 该带最大字高，用于容差 */
  height: number
  lines: OcrLine[]
}

export interface ColumnAnchors {
  op: number
  price: number
  amount: number
}

export type ColumnName = 'op' | 'price' | 'amount'

function centerY(item: OcrLine): number {
  return item.y + item.height / 2
}

/** 中位字高：作为纵向聚类的基准容差 */
export function medianHeight(lines: OcrLine[]): number {
  if (lines.length === 0) return 0
  const heights = lines.map((item) => item.height).sort((a, b) => a - b)
  return heights[Math.floor(heights.length / 2)]
}

/**
 * 把 OCR 行按纵坐标聚成「视觉行带」。
 * 同一行内的多列文本应落在同一带；上下两行文本应分属不同带。
 */
export function groupIntoBands(lines: OcrLine[], toleranceRatio = 0.6): RowBand[] {
  if (lines.length === 0) return []
  const tolerance = Math.max(2, medianHeight(lines) * toleranceRatio)
  const sorted = [...lines].sort((a, b) => centerY(a) - centerY(b) || a.x - b.x)
  const bands: RowBand[] = []
  for (const item of sorted) {
    const cy = centerY(item)
    const last = bands[bands.length - 1]
    if (last && Math.abs(cy - last.y) <= tolerance) {
      last.lines.push(item)
      last.height = Math.max(last.height, item.height)
    } else {
      bands.push({ y: cy, height: item.height, lines: [item] })
    }
  }
  return bands
}

/** 从表头文字定位三列左边界；缺失任一列返回 null（由调用方降级） */
export function findHeaderAnchors(lines: OcrLine[]): ColumnAnchors | null {
  const pick = (keyword: string) =>
    lines.find((item) => item.text.replace(/\s/g, '').includes(keyword))
  const op = pick('操作')
  const price = pick('价格')
  const amount = pick('金额')
  if (!op || !price || !amount) return null
  return { op: op.x, price: price.x, amount: amount.x }
}

/** 表头缺失时的兜底列边界：按图片宽度比例估算 */
export function fallbackAnchors(imageWidth: number): ColumnAnchors {
  return { op: imageWidth * 0.02, price: imageWidth * 0.36, amount: imageWidth * 0.66 }
}

/**
 * 按左边界最近原则归列。
 * 表头是左对齐的，因此用行首 x 与锚点比较，而不是中心点。
 */
export function assignColumn(item: OcrLine, anchors: ColumnAnchors): ColumnName {
  const midOpPrice = (anchors.op + anchors.price) / 2
  const midPriceAmount = (anchors.price + anchors.amount) / 2
  if (item.x < midOpPrice) return 'op'
  if (item.x < midPriceAmount) return 'price'
  return 'amount'
}
