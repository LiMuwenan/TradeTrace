import { beforeEach, describe, expect, it, vi } from 'vitest'

const { store } = vi.hoisted(() => {
  const storage = new Map<string, string>()
  return { store: storage }
})

vi.mock('@react-native-async-storage/async-storage', () => ({
  default: {
    getItem: vi.fn(async (key: string) => store.get(key) ?? null),
    setItem: vi.fn(async (key: string, value: string) => {
      store.set(key, value)
    }),
    removeItem: vi.fn(async (key: string) => {
      store.delete(key)
    }),
  },
}))

import {
  DEFAULT_MARKET_CONFIG,
  loadMarketConfig,
  normalizeMarketUrl,
  saveMarketConfig,
  validateMarketUrl,
} from './market-config'

describe('market-config', () => {
  beforeEach(() => store.clear())

  it('默认未配置地址，超时 8 秒，缓存开启', () => {
    expect(DEFAULT_MARKET_CONFIG).toMatchObject({
      baseUrl: '',
      timeoutMs: 8000,
      cacheEnabled: true,
    })
  })

  it('归一化去掉末尾斜杠与 /api/v1 后缀', () => {
    expect(normalizeMarketUrl(' http://192.168.1.10:8000/ ')).toBe('http://192.168.1.10:8000')
    expect(normalizeMarketUrl('http://192.168.1.10:8000/api/v1/')).toBe('http://192.168.1.10:8000')
  })

  it('拒绝空地址、非 http 协议与 localhost', () => {
    expect(() => validateMarketUrl('')).toThrow('请填写行情服务地址')
    expect(() => validateMarketUrl('192.168.1.10:8000')).toThrow('http://')
    expect(() => validateMarketUrl('http://localhost:8000')).toThrow('局域网 IP')
  })

  it('保存后可读回，脏数据回退默认值', async () => {
    await saveMarketConfig({ ...DEFAULT_MARKET_CONFIG, baseUrl: 'http://192.168.1.10:8000' })
    expect((await loadMarketConfig()).baseUrl).toBe('http://192.168.1.10:8000')

    store.set('tradetrace/market/v1', '{bad json')
    expect(await loadMarketConfig()).toEqual(DEFAULT_MARKET_CONFIG)
  })
})
