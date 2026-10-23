import { describe, expect, it } from 'vitest'

import { createEmptyState } from './types'
import { parsePayload, serializeState } from './sync'
import { createDeviceId, normalizeBaseUrl, remotePath, remoteUrl } from './sync-config'
import type { SyncConfig } from './sync-config'
import { encodeBasicAuth } from './webdav'

const config: SyncConfig = {
  webdavUrl: 'https://dav.jianguoyun.com/dav/',
  username: 'user',
  password: 'pass',
  deviceId: 'a3f2c8b1',
  remoteDeviceId: '',
  lastSyncAt: '',
}

describe('WebDAV 配置', () => {
  it('设备 ID 为 8 位十六进制', () => {
    for (let i = 0; i < 20; i += 1) {
      expect(createDeviceId()).toMatch(/^[0-9a-f]{8}$/)
    }
  })

  it('地址补全结尾斜杠', () => {
    expect(normalizeBaseUrl('https://dav.jianguoyun.com/dav')).toBe(
      'https://dav.jianguoyun.com/dav/',
    )
    expect(normalizeBaseUrl('')).toBe('https://dav.jianguoyun.com/dav/')
  })

  it('拼出远程文件地址', () => {
    expect(remotePath('a3f2c8b1')).toBe('TradeTrace/a3f2c8b1/tradetrace.json')
    expect(remoteUrl(config, 'a3f2c8b1')).toBe(
      'https://dav.jianguoyun.com/dav/TradeTrace/a3f2c8b1/tradetrace.json',
    )
    const noSlash = { ...config, webdavUrl: 'https://example.com/dav' }
    expect(remoteUrl(noSlash, 'abc')).toBe('https://example.com/dav/TradeTrace/abc/tradetrace.json')
  })

  it('Basic Auth 与标准 Base64 一致（含中文账号）', () => {
    expect(encodeBasicAuth('user', 'pass')).toBe(
      Buffer.from('user:pass', 'utf8').toString('base64'),
    )
    expect(encodeBasicAuth('测试@example.com', 'a:b')).toBe(
      Buffer.from('测试@example.com:a:b', 'utf8').toString('base64'),
    )
  })
})

describe('同步文件', () => {
  it('序列化后能原样解析', () => {
    const state = createEmptyState()
    state.accounts.push({ id: 1, name: '华泰', createdAt: '2026-01-01T00:00:00.000Z' })
    const parsed = parsePayload(serializeState(state, '2026-01-02T00:00:00.000Z'))
    expect(parsed).toEqual(state)
  })

  it('兼容直接存放 TradeState 的文件', () => {
    const state = createEmptyState()
    state.stocks.push({ id: 1, accountId: 1, name: '茅台', code: '600519', createdAt: '' })
    expect(parsePayload(JSON.stringify(state))).toEqual(state)
  })

  it('非法内容返回 null', () => {
    expect(parsePayload('not json')).toBeNull()
    expect(parsePayload('{"app":"tradetrace"}')).toBeNull()
    expect(parsePayload('[]')).toBeNull()
  })
})
