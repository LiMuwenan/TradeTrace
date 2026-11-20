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
