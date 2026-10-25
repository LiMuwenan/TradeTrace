import { afterEach, describe, expect, it, vi } from 'vitest'

import { MarketApiError, requestJson } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as unknown as Response
}

describe('requestJson', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('未配置地址时抛 config 错误，不发起请求', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await expect(requestJson('', '/api/v1/health')).rejects.toMatchObject({ kind: 'config' })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('网络异常归一为 network', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Network request failed'))))
    await expect(requestJson('http://192.168.1.10:8000', '/api/v1/health')).rejects.toMatchObject({
      kind: 'network',
    })
  })

  it('超时归一为 timeout', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init?: RequestInit) =>
          new Promise((_resolve, reject) => {
            init?.signal?.addEventListener('abort', () => {
              const err = new Error('aborted')
              err.name = 'AbortError'
              reject(err)
            })
          }),
      ),
    )
    await expect(
      requestJson('http://192.168.1.10:8000', '/api/v1/health', { timeoutMs: 20 }),
    ).rejects.toMatchObject({ kind: 'timeout' })
  })

  it('业务错误保留 code 与 message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ code: 'RANGE_TOO_LARGE', message: '区间过大' }, 422)),
    )
    const error = (await requestJson('http://192.168.1.10:8000', '/x').catch(
      (e: unknown) => e,
    )) as MarketApiError
    expect(error).toBeInstanceOf(MarketApiError)
    expect(error).toMatchObject({ kind: 'business', code: 'RANGE_TOO_LARGE', status: 422 })
    expect(error.message).toBe('区间过大')
  })

  it('非 JSON 响应归一为 parse', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, status: 200, text: async () => '<html>' }) as unknown as Response),
    )
    await expect(requestJson('http://192.168.1.10:8000', '/x')).rejects.toMatchObject({
      kind: 'parse',
    })
  })
})
