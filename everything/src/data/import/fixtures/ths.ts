import type { OcrLine } from '../types'

function line(text: string, x: number, y: number, width = 80, height = 20, confidence = 0.95): OcrLine {
  return { text, x, y, width, height, confidence }
}

/** 表头 + 账户头 + 月份分组；后续行接在 y=160 起 */
export function baseHeader(): OcrLine[] {
  return [
    line('浙商证券 *4768', 10, 60, 160),
    line('操作', 10, 100, 40),
    line('价格/数量', 150, 100, 80),
    line('金额/费用', 280, 100, 80),
    line('2026-10', 10, 130, 80),
  ]
}

/** 生成一条两行三列的行块；缺省值传 null 表示该字段被截断 */
export function rowBlock(
  y: number,
  col1: [string, string],
  col2: [string | null, string | null],
  col3: [string | null, string | null],
): OcrLine[] {
  const out: OcrLine[] = [line(col1[0], 10, y, 200)]
  if (col2[0]) out.push(line(col2[0], 150, y))
  if (col3[0]) out.push(line(col3[0], 280, y))
  out.push(line(col1[1], 10, y + 20, 200))
  if (col2[1]) out.push(line(col2[1], 150, y + 20))
  if (col3[1]) out.push(line(col3[1], 280, y + 20))
  return out
}

export function buyFixture(): OcrLine[] {
  return [...baseHeader(), ...rowBlock(160, ['证券买入-工商银行', '买 10-23 09:49'], ['8.500', '1000'], ['-8,505.09', '5.09'])]
}

export function sellFixture(): OcrLine[] {
  return [...baseHeader(), ...rowBlock(160, ['卖出-贵州茅台', '卖 10-22 14:05'], ['1,500.000', '100'], ['149,995.00', '5.00'])]
}

export function dividendFixture(): OcrLine[] {
  return [...baseHeader(), ...rowBlock(160, ['股息入账-工商银行', '红 10-20 16:00'], ['8.580', '0'], ['166.21', null])]
}

export function taxFixture(): OcrLine[] {
  return [...baseHeader(), ...rowBlock(160, ['股息红利税补缴-工商银行', '红 10-20 16:00'], ['0', '0'], ['-16.89', null])]
}

export function transferFixture(): OcrLine[] {
  return [...baseHeader(),
    ...rowBlock(160, ['银行转存', '银 10-19 09:00'], ['0', '0'], ['50,000.00', null]),
    ...rowBlock(220, ['银行转取', '银 10-19 10:00'], ['0', '0'], ['-20,000.00', null]),
  ]
}

export function ipoFixture(): OcrLine[] {
  return [...baseHeader(), ...rowBlock(160, ['申购配号-某新股', '新 10-18 09:30'], ['12.000', '1000'], ['12,000.00', null])]
}

export function truncatedFixture(): OcrLine[] {
  // 金额列缺失（截图底部被截断）
  return [...baseHeader(), ...rowBlock(160, ['证券买入-平安银行', '买 10-17 10:00'], ['10.000', '500'], [null, null])]
}

/** 跨年：月份分组切换后，行内年份必须跟随所属分组 */
export function crossYearFixture(): OcrLine[] {
  return [
    ...baseHeader(),
    ...rowBlock(160, ['证券买入-工商银行', '买 12-31 14:00'], ['8.500', '100'], ['-855.00', '5.00']),
    line('2027-01', 10, 220, 80),
    ...rowBlock(250, ['卖出-工商银行', '卖 01-04 10:00'], ['8.600', '100'], ['855.00', '5.00']),
  ]
}
