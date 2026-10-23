/** 数字与日期格式化：统一两位小数、千分位与正负号 */

export function formatNumber(value: number, digits = 2): string {
  if (!Number.isFinite(value)) return (0).toFixed(digits)
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** 金额：正数带 + 号，负数带 - 号 */
export function formatSigned(value: number, digits = 2): string {
  const text = formatNumber(Math.abs(value), digits)
  return `${value >= 0 ? '+' : '-'}${text}`
}

/** 数量：股数按整数展示，浮点尾差四舍五入 */
export function formatShares(value: number): string {
  return formatNumber(value, Math.abs(value % 1) < 1e-6 ? 0 : 2)
}

export function formatPrice(value: number): string {
  return formatNumber(value, 3)
}

/** 2026-10-23 → 10-23 */
export function shortDate(date: string): string {
  return date.length >= 10 ? date.slice(5, 10) : date
}

export function todayString(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export function isValidDateString(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  return (
    date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day
  )
}

export function nowIso(): string {
  return new Date().toISOString()
}
