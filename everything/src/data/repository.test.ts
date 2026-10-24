import { beforeEach, describe, expect, it, vi } from 'vitest'

const { store, getItemMock, setItemMock } = vi.hoisted(() => {
  const storage = new Map<string, string>()
  return {
    store: storage,
    getItemMock: vi.fn(async (key: string) => storage.get(key) ?? null),
    setItemMock: vi.fn(async (key: string, value: string) => {
      storage.set(key, value)
    }),
  }
})

vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {
    getItem: getItemMock,
    setItem: setItemMock,
    removeItem: vi.fn(async (key: string) => {
      store.delete(key)
    }),
  },
}))

import { appendConflictLog, loadConflictLog, loadState } from './repository'

const STATE_KEY = 'tradetrace/state/v2'
const LEGACY_KEY = 'tradetrace/state/v1'

function stateWrites(): unknown[][] {
  return setItemMock.mock.calls.filter(([key]) => key === STATE_KEY)
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

describe('loadState', () => {
  beforeEach(() => {
    store.clear()
    vi.clearAllMocks()
  })

  it('v2 数据损坏时不写盘，避免空状态覆盖原始数据', async () => {
    store.set(STATE_KEY, '{ 这不是 JSON')

    const state = await loadState()

    expect(state.accounts).toEqual([])
    expect(stateWrites()).toHaveLength(0)
  })

  it('未知版本不写盘', async () => {
    store.set(STATE_KEY, JSON.stringify({ schemaVersion: 9, accounts: [] }))

    const state = await loadState()

    expect(state.accounts).toEqual([])
    expect(stateWrites()).toHaveLength(0)
  })

  it('v1 数据迁移后写回 v2', async () => {
    store.set(LEGACY_KEY, JSON.stringify(v1State()))

    const state = await loadState()

    expect(state.schemaVersion).toBe(2)
    expect(state.transactions).toHaveLength(1)
    expect(stateWrites()).toHaveLength(1)

    const written = JSON.parse(store.get(STATE_KEY) ?? '{}') as { schemaVersion?: number }
    expect(written.schemaVersion).toBe(2)
  })

  it('首次启动写入带设备 ID 的空快照', async () => {
    const state = await loadState()

    expect(state.schemaVersion).toBe(2)
    expect(state.deviceId.length).toBeGreaterThan(0)
    expect(stateWrites()).toHaveLength(1)
  })
})

describe('appendConflictLog', () => {
  beforeEach(() => {
    store.clear()
    vi.clearAllMocks()
  })

  const conflict = {
    entity: 'account' as const,
    id: 'a1',
    localUpdatedAt: '2026-01-01T00:00:00.000Z',
    remoteUpdatedAt: '2026-01-02T00:00:00.000Z',
    winner: 'remote' as const,
  }

  it('同一冲突重复合并只记录一次', async () => {
    await appendConflictLog([conflict], '2026-01-03T00:00:00.000Z')
    const second = await appendConflictLog([conflict], '2026-01-04T00:00:00.000Z')

    expect(second).toHaveLength(1)
    expect(second[0].at).toBe('2026-01-03T00:00:00.000Z')
  })

  it('不同冲突按时间倒序累积', async () => {
    await appendConflictLog([conflict], '2026-01-03T00:00:00.000Z')
    await appendConflictLog([{ ...conflict, id: 'a2' }], '2026-01-04T00:00:00.000Z')

    const log = await loadConflictLog()
    expect(log.map((item) => item.id)).toEqual(['a2', 'a1'])
  })
})
