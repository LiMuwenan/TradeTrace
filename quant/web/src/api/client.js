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

export function searchStocks(keyword) {
  return request(`/stocks/search?q=${encodeURIComponent(keyword)}`)
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
