/**
 * 后端接口封装：统一 baseURL、响应解包与错误信息，避免各页面各写一套 fetch。
 */
const BASE_URL = '/api/v1'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new ApiError('无法连接后端服务，请确认服务已启动', 0)
  }

  let body
  try {
    body = await response.json()
  } catch {
    throw new ApiError(`响应不是合法 JSON（HTTP ${response.status}）`, response.status)
  }

  if (!response.ok || body.code !== 0) {
    throw new ApiError(body.message || `请求失败（HTTP ${response.status}）`, response.status)
  }
  return body.data
}

export function fetchHealth() {
  return request('/health')
}

export function fetchDataStatus() {
  return request('/data/status')
}

export function fetchWatchlist() {
  return request('/watchlist')
}

export function addToWatchlist(code) {
  return request('/watchlist', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
}

export function removeFromWatchlist(code) {
  return request(`/watchlist/${encodeURIComponent(code)}`, { method: 'DELETE' })
}

/** 指数历史回补：后台任务，立刻返回运行态；加入自选时后端会自动触发一次。 */
export function startIndexHistory(code) {
  return request(`/stocks/${encodeURIComponent(code)}/history`, { method: 'POST' })
}

export function searchStocks(keyword) {
  return request(`/stocks/search?q=${encodeURIComponent(keyword)}`)
}

/** 个股详情：日 K 与均线，`range` 为 3m / 1y / all，`adjust` 为 back（后复权）/ raw（不复权）（04 号票）。 */
export function fetchStockDetail(code, range = '1y', adjust = 'back') {
  const params = new URLSearchParams({ range })
  params.set('adjust', adjust)
  return request(`/stocks/${encodeURIComponent(code)}/detail?${params.toString()}`)
}

// --- 预警（07 号票）-------------------------------------------------------

export function fetchAlerts({ read, code, ruleType, page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
  if (read === true || read === false) params.set('read', String(read))
  if (code) params.set('code', code)
  if (ruleType) params.set('ruleType', ruleType)
  return request(`/alerts?${params.toString()}`)
}

export function fetchAlert(id) {
  return request(`/alerts/${id}`)
}

export function setAlertRead(id, read) {
  return request(`/alerts/${id}/read`, {
    method: 'PATCH',
    body: JSON.stringify({ read }),
  })
}

export function markAllAlertsRead() {
  return request('/alerts/read-all', { method: 'POST' })
}

// --- 通知设置（08 号票）---------------------------------------------------

export function fetchNotificationSettings() {
  return request('/settings/notification')
}

export function saveNotificationSettings(payload) {
  return request('/settings/notification', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function sendTestNotification() {
  return request('/settings/notification/test', { method: 'POST' })
}

export function fetchNotificationLog({ date, page = 1, pageSize = 10 } = {}) {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
  if (date) params.set('date', date)
  return request(`/notifications/log?${params.toString()}`)
}

// --- 规则管理（06 号票）---------------------------------------------------

export function fetchRules() {
  return request('/rules')
}

export function createRule(payload) {
  return request('/rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateRule(id, payload) {
  return request(`/rules/${id}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function setRuleEnabled(id, enabled) {
  return request(`/rules/${id}/enabled`, {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

/** 手动触发某交易日的求值（05 的入口，规则页与调试都走它）。 */
export function evaluateRules(date, code) {
  const body = { date }
  if (code) body.code = code
  return request('/rules/evaluate', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// --- 日报（09 号票）-------------------------------------------------------

export function fetchReports({ page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
  return request(`/reports?${params.toString()}`)
}

export function fetchReport(tradeDate) {
  return request(`/reports/${encodeURIComponent(tradeDate)}`)
}

/** 生成并投递某日日报；已投递的会保留原文，不会改写。 */
export function generateReport(tradeDate) {
  return request('/reports/generate', {
    method: 'POST',
    body: JSON.stringify({ date: tradeDate }),
  })
}

// --- 收盘流水线（10 号票）-------------------------------------------------

export function fetchPipelineRuns({ page = 1, pageSize = 20, date } = {}) {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
  if (date) params.set('date', date)
  return request(`/pipeline/runs?${params.toString()}`)
}

/** 手动重跑某交易日；catchUp 为真时补跑该日之前的缺口。 */
export function runPipeline(date, catchUp = false) {
  return request('/pipeline/run', {
    method: 'POST',
    body: JSON.stringify({ date, catchUp }),
  })
}
