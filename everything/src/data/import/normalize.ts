import type { ParsedRow } from './types'
import type { SourceRef, Stock, TransactionInput } from '../types'

/** 除权除息与风险标识：只在前缀位置剥离，避免误伤名称本身 */
const PREFIXES = ['XD', 'XR', 'DR', '*ST', 'ST', 'N', 'C', 'U']

export function normalizeStockName(raw: string): string {
  let name = raw.replace(/[\s　]/g, '').trim()
  let changed = true
  while (changed && name.length > 2) {
    changed = false
    for (const prefix of PREFIXES) {
      if (name.startsWith(prefix)) {
        const rest = name.slice(prefix.length).replace(/^[-－—:：]/, '')
        if (rest.length >= 2) {
          name = rest
          changed = true
        }
      }
    }
  }
  return name
}

export interface LookupStock {
  id: string
  name: string
  code: string
}

/** 名称 → 本地股票 ID；先精确匹配，再按归一化名称匹配；查不到返回 null（由用户手动选） */
export function resolveStockId(name: string, stocks: LookupStock[]): string | null {
  const target = normalizeStockName(name)
  const exact = stocks.find((stock) => stock.name === name)
  if (exact) return exact.id
  const matched = stocks.find((stock) => normalizeStockName(stock.name) === target)
  return matched ? matched.id : null
}

/** 候选 → 交易输入：来源固定 ocr，dedupeKey 由 state 层按合并口径生成 */
export function candidateToInput(
  candidate: ParsedRow,
  stockId: string,
  sourceRef: SourceRef,
): TransactionInput {
  const base: TransactionInput = {
    stockId,
    date: candidate.date,
    price: candidate.price,
    shares: candidate.shares,
    commission: candidate.commission,
    type: candidate.type,
    source: 'ocr',
    sourceRef,
  }
  if (candidate.time) base.time = candidate.time
  if (candidate.type === '股息') base.dividend = candidate.dividend ?? 0
  if (candidate.note) base.note = candidate.note
  return base
}

/** 类型收窄辅助：页面需要渲染股票名时使用 */
export function stockLabel(stock: Pick<Stock, 'name' | 'code'>): string {
  return stock.code ? `${stock.name}（${stock.code}）` : stock.name
}
