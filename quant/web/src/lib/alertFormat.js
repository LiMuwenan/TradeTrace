/**
 * 预警展示的文案口径：与后端推送正文保持一致，避免页面和手机看到两套说法。
 */
export const RULE_TYPE_LABELS = {
  breakout: '突破',
  oversold: '超跌',
  volume_surge: '放量',
  volume_shrink: '缩量',
  ma_cross: '均线穿越',
}

export function ruleLabel(type) {
  return RULE_TYPE_LABELS[type] || type || '—'
}

export function num(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : String(value)
}

/** 一条预警的指标摘要，例如「前 60 日最高 12.10」「回落 23.50%（阈值 20%）」。 */
export function metricText(alert) {
  if (!alert) return '—'
  const value = num(alert.value)
  const threshold = num(alert.threshold)
  if (alert.ruleType === 'oversold') return `回落 ${value}%（阈值 ${threshold}%）`
  if (alert.ruleType === 'volume_surge' || alert.ruleType === 'volume_shrink') {
    return `量比 ${value}（阈值 ${threshold}）`
  }
  if (alert.ruleType === 'ma_cross') return `均线 ${value}`
  if (alert.ruleType === 'breakout') return `区间最高 ${value}`
  return `触发值 ${value}`
}

export const PUSH_RESULT_LABELS = {
  ok: '成功',
  fallback: '降级送达',
  failed: '失败',
}

/** 推送状态只反映「有没有成功送到手机」，与是否已读无关。 */
export function pushStateText(alert) {
  if (!alert) return '—'
  if (alert.pushedAt) return `已推送（${alert.pushChannel || '未知通道'}）`
  return '未送达'
}
