import type { ParseResult, ParsedRow, SkippedRow } from './types'
import type { OcrLine } from './types'
import { assignColumn, fallbackAnchors, findHeaderAnchors, groupIntoBands } from './layout'
import type { ColumnAnchors, RowBand } from './layout'

export const TEMPLATE_ZHESHANG = 'ths_zheshang_v1'
export const TEMPLATE_GENERIC = 'ths_generic_v1'

export interface ParseOptions {
  imageWidth: number
  /** 用于校验「日期不得晚于今天」，格式 yyyy-MM-dd */
  today: string
}

interface OperationMatch {
  type: '买入' | '卖出' | '股息' | '税补缴' | '银证转账' | '申购配号'
  name: string
  tax: boolean
}

const AMOUNT_TOLERANCE = 0.02

function clean(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

/** 从操作列文本判定业务类型；未匹配返回 null（表头/页脚/月份行等） */
export function matchOperation(text: string): OperationMatch | null {
  const t = clean(text)
  if (/银行转[存取]/.test(t)) return { type: '银证转账', name: '', tax: false }
  if (/申购配号/.test(t)) return { type: '申购配号', name: '', tax: false }
  if (/股息红利税补缴|红利税补缴/.test(t)) {
    const tax = t.match(/(?:股息红利税补缴|红利税补缴)[-－—]?(.+?)(?=\s|$)/)
    return { type: '税补缴', name: clean(tax?.[1] ?? ''), tax: true }
  }
  const dividend = t.match(/股息入账[-－—]?(.+?)(?=\s|$)/)
  if (dividend) return { type: '股息', name: clean(dividend[1]), tax: false }
  const sell = t.match(/(?:证券)?卖出[-－—]?(.+?)(?=\s|$)/)
  if (sell) return { type: '卖出', name: clean(sell[1]), tax: false }
  const buy = t.match(/(?:证券)?买入[-－—]?(.+?)(?=\s|$)/)
  if (buy) return { type: '买入', name: clean(buy[1]), tax: false }
  return null
}

function numbers(text: string): number[] {
  const found = text.match(/-?\d[\d,]*\.?\d*/g) ?? []
  return found.map((raw) => Number(raw.replace(/,/g, ''))).filter((n) => Number.isFinite(n))
}

function round2(value: number): number {
  return Math.round(value * 100) / 100
}

function columnsOf(bands: RowBand[], anchors: ColumnAnchors): Record<string, string> {
  const out: Record<string, string[]> = { op: [], price: [], amount: [] }
  for (const band of bands) {
    for (const line of band.lines) {
      out[assignColumn(line, anchors)].push(line.text)
    }
  }
  return {
    op: clean(out.op.join(' ')),
    price: clean(out.price.join(' ')),
    amount: clean(out.amount.join(' ')),
  }
}

function averageConfidence(bands: RowBand[]): number {
  const values = bands.flatMap((band) => band.lines.map((line) => line.confidence))
  if (values.length === 0) return 0
  return values.reduce((sum, v) => sum + v, 0) / values.length
}

function parseDate(text: string, year: number, today: string): { date: string; time: string } | null {
  const match = text.match(/(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/)
  if (!match) return null
  const date = `${year}-${match[1]}-${match[2]}`
  if (Number.isNaN(Date.parse(date))) return null
  if (date > today) return null
  return { date, time: `${match[3]}:${match[4]}` }
}

/**
 * 解析同花顺浙商证券版式。
 * 输入为 OCR 文本行，输出候选交易 + 被跳过的非交易行；不做任何网络或引擎调用。
 */
export function parseThsStatement(lines: OcrLine[], options: ParseOptions): ParseResult {
  const warnings: string[] = []
  const bands = groupIntoBands(lines)
  const anchors =
    findHeaderAnchors(lines) ?? fallbackAnchors(options.imageWidth)
  const templateId = findHeaderAnchors(lines) ? TEMPLATE_ZHESHANG : TEMPLATE_GENERIC
  if (templateId === TEMPLATE_GENERIC) warnings.push('未识别到标准表头，按兜底列宽解析，请核对字段')

  const accountLine = lines.find((line) => /证券(?:公司)?/.test(line.text) && /\*\d{3,4}/.test(line.text))
  const accountHint = accountLine ? clean(accountLine.text) : ''

  // 找到表头所在行带，只看其下方的行
  const headerBand = bands.find((band) =>
    band.lines.some((line) => line.text.includes('操作')) &&
    band.lines.some((line) => line.text.includes('金额')),
  )
  const startIndex = headerBand ? bands.indexOf(headerBand) + 1 : 0

  const candidates: ParsedRow[] = []
  const skipped: SkippedRow[] = []
  let year = Number(options.today.slice(0, 4))

  let index = startIndex
  while (index < bands.length) {
    const band = bands[index]
    const opText = columnsOf([band], anchors).op

    // 月份分组行：更新年份，继续
    const month = opText.match(/^(\d{4})-(\d{2})$/)
    if (month) {
      year = Number(month[1])
      index += 1
      continue
    }
    if (/无符合条件的流水数据/.test(opText) || /更多数据请调整时间范围/.test(opText)) {
      skipped.push({ rowIndex: index, kind: /无符合/.test(opText) ? '空状态' : '页脚', raw: opText, reason: '非交易行' })
      index += 1
      continue
    }

    const operation = matchOperation(opText)
    if (!operation) {
      index += 1
      continue
    }

    // 行块 = 当前行带 + 后续未出现新操作的行带（通常 1 个）
    const blockBands: RowBand[] = [band]
    let cursor = index + 1
    while (cursor < bands.length && blockBands.length < 3) {
      const nextOp = columnsOf([bands[cursor]], anchors).op
      if (matchOperation(nextOp) || /^\d{4}-\d{2}$/.test(nextOp)) break
      blockBands.push(bands[cursor])
      cursor += 1
    }

    const columns = columnsOf(blockBands, anchors)
    const rowIndex = index

    if (operation.type === '银证转账' || operation.type === '申购配号') {
      skipped.push({
        rowIndex,
        kind: operation.type,
        raw: Object.values(columns).join(' | '),
        reason: operation.type === '银证转账' ? '银证转账不计入交易' : '新股申购不计入交易',
      })
      index = cursor
      continue
    }

    const parsed = parseTradingRow(operation, columns, blockBands, rowIndex, templateId, year, options.today)
    if ('skip' in parsed) {
      skipped.push({ rowIndex, kind: '无法识别', raw: Object.values(columns).join(' | '), reason: parsed.skip })
    } else {
      candidates.push(parsed.row)
    }
    index = cursor
  }

  return { templateId, accountHint, candidates, skipped, warnings }
}

function parseTradingRow(
  operation: OperationMatch,
  columns: Record<string, string>,
  blockBands: RowBand[],
  rowIndex: number,
  templateId: string,
  year: number,
  today: string,
): { row: ParsedRow } | { skip: string } {
  const warnings: string[] = []
  const dateInfo = parseDate(columns.op, year, today)
  if (!dateInfo) return { skip: '缺少可识别的日期（可能被截断）' }

  const priceNumbers = numbers(columns.price)
  const amountNumbers = numbers(columns.amount)

  const rawBlock = blockBands.map((band) => clean(band.lines.map((line) => line.text).join(' ')))
  let confidence = averageConfidence(blockBands)

  if (operation.type === '买入' || operation.type === '卖出') {
    if (priceNumbers.length < 2) return { skip: '价格或数量缺失（可能被截断）' }
    const price = priceNumbers[0]
    const shares = Math.abs(priceNumbers[1])
    if (price <= 0 || shares <= 0) return { skip: '价格或数量非法' }

    if (amountNumbers.length === 0) {
      warnings.push('金额缺失，费用无法交叉校验')
      confidence -= 0.25
      return {
        row: finalizeRow({
          rowIndex, templateId, rawBlock, type: operation.type, name: operation.name,
          date: dateInfo.date, time: dateInfo.time, price,
          shares: operation.type === '卖出' ? -shares : shares,
          commission: 0, dividend: undefined, amount: price * shares,
          confidence: Math.max(0.3, confidence - 0.05), warnings,
        }),
      }
    }

    const amount = Math.abs(amountNumbers[0])
    const feeShown = amountNumbers.length >= 2 ? amountNumbers[1] : null
    const gross = round2(price * shares)
    const expectedFee = operation.type === '买入' ? round2(amount - gross) : round2(gross - amount)

    let commission = expectedFee
    if (feeShown !== null) {
      if (Math.abs(feeShown - expectedFee) > AMOUNT_TOLERANCE) {
        warnings.push(
          `金额与价格×数量不一致：按金额反推费用 ${expectedFee}，费用列 ${feeShown}，请人工确认`,
        )
        confidence -= 0.2
        commission = feeShown
      } else {
        commission = feeShown
      }
    } else {
      const maxReasonable = round2(gross * 0.003 + 5)
      if (expectedFee > maxReasonable) {
        warnings.push('金额与价格×数量不一致，请人工确认')
        confidence -= 0.2
      }
      warnings.push('费用列缺失，已按金额反推，请确认')
      confidence -= 0.1
    }
    if (commission < 0) {
      warnings.push('反推费用为负，请人工确认')
      commission = Math.abs(commission)
      confidence -= 0.2
    }

    return {
      row: finalizeRow({
        rowIndex, templateId, rawBlock, type: operation.type, name: operation.name,
        date: dateInfo.date, time: dateInfo.time, price,
        shares: operation.type === '卖出' ? -shares : shares,
        commission: round2(commission), dividend: undefined, amount: round2(amount),
        confidence, warnings,
      }),
    }
  }

  // 股息与税补缴：价格列是分红参数，不是成交价
  if (amountNumbers.length === 0) return { skip: '股息金额缺失（可能被截断）' }
  const dividend = round2(amountNumbers[0])
  const priceRaw = priceNumbers.length > 0 ? priceNumbers[0] : null
  const feeShown = amountNumbers.length >= 2 ? amountNumbers[1] : null

  if (operation.type === '股息' && dividend < 0) warnings.push('负股息：将按红利税补缴口径入库，请确认')
  if (operation.type === '税补缴' && dividend > 0) warnings.push('税补缴金额为正，请确认符号')
  if (feeShown !== null && Math.abs(feeShown) > AMOUNT_TOLERANCE) {
    warnings.push(`股息行存在费用 ${feeShown}，请确认`)
    confidence -= 0.1
  }

  const isTax = operation.type === '税补缴' || (operation.type === '股息' && dividend < 0)
  return {
    row: finalizeRow({
      rowIndex, templateId, rawBlock, type: '股息', name: operation.name,
      date: dateInfo.date, time: dateInfo.time, price: 0, shares: 0,
      commission: 0, dividend,
      amount: dividend, confidence,
      warnings,
      note: [
        isTax ? '股息红利税补缴' : '股息入账',
        priceRaw !== null ? `价格列原始值 ${priceRaw}（分红参数，未作为成交价）` : '',
      ].filter(Boolean).join('；'),
    }),
  }
}

interface FinalizeArgs {
  rowIndex: number
  templateId: string
  rawBlock: string[]
  type: ParsedRow['type']
  name: string
  date: string
  time: string
  price: number
  /** 带符号股数：买入正、卖出负、股息 0 */
  shares: number
  commission: number
  dividend: number | undefined
  amount: number
  confidence: number
  warnings: string[]
  note?: string
}

function finalizeRow(args: FinalizeArgs): ParsedRow {
  const confidence = Math.min(0.99, Math.max(0.3, args.confidence - args.warnings.length * 0.05))
  return {
    rowIndex: args.rowIndex,
    templateId: args.templateId,
    rawBlock: args.rawBlock,
    type: args.type,
    name: args.name,
    date: args.date,
    time: args.time,
    price: args.price,
    shares: args.shares,
    commission: args.commission,
    dividend: args.dividend,
    amount: args.amount,
    confidence,
    warnings: args.warnings,
    note: args.note,
  }
}
