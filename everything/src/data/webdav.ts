import { normalizeBaseUrl, SYNC_FOLDER, remotePath } from './sync-config'
import type { SyncConfig } from './sync-config'

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

function utf8Bytes(text: string): number[] {
  const bytes: number[] = []
  for (let i = 0; i < text.length; i += 1) {
    const code = text.codePointAt(i) ?? 0
    if (code > 0xffff) i += 1
    if (code < 0x80) {
      bytes.push(code)
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f))
    } else if (code < 0x10000) {
      bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f))
    } else {
      bytes.push(
        0xf0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3f),
        0x80 | ((code >> 6) & 0x3f),
        0x80 | (code & 0x3f),
      )
    }
  }
  return bytes
}

/** Basic Auth 头内容（自行实现，避免依赖 btoa 在原生端缺失） */
export function encodeBasicAuth(username: string, password: string): string {
  const bytes = utf8Bytes(`${username}:${password}`)
  let output = ''
  for (let i = 0; i < bytes.length; i += 3) {
    const b0 = bytes[i]
    const b1 = bytes[i + 1]
    const b2 = bytes[i + 2]
    output += ALPHABET[b0 >> 2]
    output += ALPHABET[((b0 & 3) << 4) | (b1 === undefined ? 0 : b1 >> 4)]
    output += b1 === undefined ? '=' : ALPHABET[((b1 & 15) << 2) | (b2 === undefined ? 0 : b2 >> 6)]
    output += b2 === undefined ? '=' : ALPHABET[b2 & 63]
  }
  return output
}

export interface WebDavResult {
  ok: boolean
  status: number
  message: string
}

export interface WebDavDownloadResult extends WebDavResult {
  content: string
}

function authHeaders(config: SyncConfig, contentType = false): Record<string, string> {
  const headers: Record<string, string> = {
    Authorization: `Basic ${encodeBasicAuth(config.username, config.password)}`,
  }
  if (contentType) headers['Content-Type'] = 'application/json; charset=utf-8'
  return headers
}

function networkMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error)
  return `网络请求失败（Web 端可能被浏览器跨域策略拦截，Android 端可正常使用）：${detail}`
}

function folderUrl(config: SyncConfig, folder: string): string {
  return `${normalizeBaseUrl(config.webdavUrl)}${folder}`
}

/** 坚果云在目录不存在时会返回 409，这里用 MKCOL 逐级创建 */
async function ensureFolders(config: SyncConfig, deviceId: string): Promise<boolean> {
  for (const folder of [SYNC_FOLDER, `${SYNC_FOLDER}/${deviceId}`]) {
    try {
      const response = await fetch(folderUrl(config, folder), {
        method: 'MKCOL',
        headers: authHeaders(config),
      })
      if (!response.ok && response.status !== 405) return false
    } catch {
      return false
    }
  }
  return true
}

export async function uploadStateFile(
  config: SyncConfig,
  deviceId: string,
  content: string,
): Promise<WebDavResult> {
  const url = folderUrl(config, remotePath(deviceId))
  const put = () =>
    fetch(url, { method: 'PUT', headers: authHeaders(config, true), body: content })

  try {
    let response = await put()
    if (response.status === 409) {
      if (!(await ensureFolders(config, deviceId))) {
        return { ok: false, status: 409, message: '云端目录创建失败，请检查应用密码权限' }
      }
      response = await put()
    }
    if (response.ok) return { ok: true, status: response.status, message: '上传成功' }
    const detail = await response.text()
    return {
      ok: false,
      status: response.status,
      message: `上传失败：HTTP ${response.status}${detail ? ` ${detail.slice(0, 120)}` : ''}`,
    }
  } catch (error) {
    return { ok: false, status: 0, message: networkMessage(error) }
  }
}

export async function downloadStateFile(
  config: SyncConfig,
  deviceId: string,
): Promise<WebDavDownloadResult> {
  const url = folderUrl(config, remotePath(deviceId))
  try {
    const response = await fetch(url, { method: 'GET', headers: authHeaders(config) })
    if (response.status === 404) {
      return { ok: false, status: 404, content: '', message: '远程设备还没有上传过数据' }
    }
    if (!response.ok) {
      return { ok: false, status: response.status, content: '', message: `下载失败：HTTP ${response.status}` }
    }
    return { ok: true, status: response.status, content: await response.text(), message: '下载成功' }
  } catch (error) {
    return { ok: false, status: 0, content: '', message: networkMessage(error) }
  }
}
