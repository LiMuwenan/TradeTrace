import { beforeEach, describe, expect, it, vi } from 'vitest'

import { pullFromCloud, parsePayload, serializeState } from './sync'
import { createDeviceId, normalizeBaseUrl, remotePath, remoteUrl } from './sync-config'
import type { SyncConfig } from './sync-config'
import { createEmptyState } from './types'
import type { TradeState, TransactionTrade } from './types'
import { downloadStateFile, encodeBasicAuth } from './webdav'

vi.mock('./webdav', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./webdav')>()
  return {
    ...actual,
    downloadStateFile: vi.fn(),
  }
})

const NOW = '2026-01-04T00:00:00.000Z'
const config: SyncConfig = {
  webdavUrl: 'https://dav.jianguoyun.com/dav/',
  username: 'user',
  password: 'pass',
  deviceId: 'a3f2c8b1',
  remoteDeviceId: 'b4e1d2c3',
  lastSyncAt: '',
}

function trade(id: string, updatedAt: string): TransactionTrade {
  return {
    id,
    stockId: 'stock-1',
    date: '2026-01-02',
    price: 10,
    shares: 100,
    commission: 0,
    type: '买入',
    source: 'manual',
    dedupeKey: `key-${id}`,
    createdAt: '2026-01-01T00:00:00.000Z',
    updatedAt,
  }
}

function v1State() {
  return {
    version: 1,
    accounts: [{ id: 1, name: '华泰', createdAt: '2026-01-01T00:00:00.000Z' }],
    stocks: [
      { id: 1, accountId: 1, name: '茅台', code: '600519', createdAt: '2026-01-01T00:00:00.000Z' },
    ],
    transactions: [
      {
        id: 1,
        stockId: 1,
        date: '2026-01-02',
        price: 10,
        shares: 100,
        commission: 0,
        type: '买入',
        createdAt: '2026-01-02T00:00:00.000Z',
      },
    ],
    tTrades: [],
  }
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
  it('v2 载荷序列化后能原样解析', () => {
    const state = createEmptyState('device-1', NOW)
    state.accounts.push({
      id: 'account-1',
      name: '华泰',
      createdAt: NOW,
      updatedAt: NOW,
    })
    const parsed = parsePayload(serializeState(state, NOW), 'device-1', NOW)
    expect(parsed).toEqual(state)
  })

  it('兼容直接存放 v2 TradeState 的文件', () => {
    const state = createEmptyState('device-1', NOW)
    state.stocks.push({
      id: 'stock-1',
      accountId: 'account-1',
      name: '茅台',
      code: '600519',
      createdAt: NOW,
      updatedAt: NOW,
    })
    expect(parsePayload(JSON.stringify(state), 'device-1', NOW)).toEqual(state)
  })

  it('v1 载荷与裸 v1 状态自动升级', () => {
    const payload = JSON.stringify({ app: 'tradetrace', version: 1, exportedAt: NOW, state: v1State() })
    const fromPayload = parsePayload(payload, 'device-1', NOW)
    expect(fromPayload?.schemaVersion).toBe(2)
    expect(fromPayload?.transactions).toHaveLength(1)

    const fromBare = parsePayload(JSON.stringify(v1State()), 'device-1', NOW)
    expect(fromBare?.schemaVersion).toBe(2)
    expect(fromBare?.accounts).toHaveLength(1)
  })

  it('非法内容返回 null', () => {
    expect(parsePayload('not json', 'device-1', NOW)).toBeNull()
    expect(parsePayload('{"app":"tradetrace"}', 'device-1', NOW)).toBeNull()
    expect(parsePayload('{"app":"tradetrace","version":9,"state":{}}', 'device-1', NOW)).toBeNull()
    expect(parsePayload('[]', 'device-1', NOW)).toBeNull()
    // 声明 v2 但缺少实体数组：不能当成空状态合并
    expect(
      parsePayload('{"app":"tradetrace","version":2,"state":{"schemaVersion":2}}', 'device-1', NOW),
    ).toBeNull()
  })
})

describe('合并下载', () => {
  beforeEach(() => {
    vi.mocked(downloadStateFile).mockReset()
  })

  it('合并双端数据，不覆盖本机新增记录', async () => {
    const local = createEmptyState('local-device', NOW)
    local.transactions.push(trade('t-local', '2026-01-02T00:00:00.000Z'))
    const remote: TradeState = createEmptyState('remote-device', NOW)
    remote.transactions.push(trade('t-remote', '2026-01-03T00:00:00.000Z'))

    vi.mocked(downloadStateFile).mockResolvedValue({
      ok: true,
      status: 200,
      content: serializeState(remote, NOW),
      message: '下载成功',
    })

    const result = await pullFromCloud(config, local, NOW)
    expect(result.ok).toBe(true)
    expect(result.state?.transactions.map((item) => item.id).sort()).toEqual([
      't-local',
      't-remote',
    ])
    expect(result.state?.deviceId).toBe('local-device')
    expect(result.conflicts).toHaveLength(0)
    expect(result.message).toContain('新增 1 笔交易')
  })

  it('合并摘要区分新增与删除', async () => {
    const local = createEmptyState('local-device', NOW)
    local.transactions.push(trade('t-old', '2026-01-02T00:00:00.000Z'))

    const remote = createEmptyState('remote-device', NOW)
    remote.transactions.push({
      ...trade('t-old', '2026-01-03T00:00:00.000Z'),
      deletedAt: '2026-01-03T00:00:00.000Z',
    })
    remote.transactions.push(trade('t-new', '2026-01-03T00:00:00.000Z'))

    vi.mocked(downloadStateFile).mockResolvedValue({
      ok: true,
      status: 200,
      content: serializeState(remote, NOW),
      message: '下载成功',
    })

    const result = await pullFromCloud(config, local, NOW)
    expect(result.ok).toBe(true)
    expect(result.message).toContain('新增 1 笔交易')
    expect(result.message).toContain('删除 1 笔')
  })

  it('格式非法时不修改本机数据', async () => {
    vi.mocked(downloadStateFile).mockResolvedValue({
      ok: true,
      status: 200,
      content: 'not json',
      message: '下载成功',
    })

    const local = createEmptyState('local-device', NOW)
    const result = await pullFromCloud(config, local, NOW)
    expect(result.ok).toBe(false)
    expect(result.state).toBeUndefined()
    expect(result.message).toContain('未修改本机数据')
  })

  it('未配置远程设备时直接返回失败', async () => {
    const result = await pullFromCloud({ ...config, remoteDeviceId: '' }, createEmptyState(), NOW)
    expect(result.ok).toBe(false)
    expect(downloadStateFile).not.toHaveBeenCalled()
  })
})
