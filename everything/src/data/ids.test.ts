import { describe, expect, it } from 'vitest'

import { createId, createStableId } from './ids'

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const UUID_V5 = /^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

describe('createId', () => {
  it('生成 UUID v4 形态的字符串', () => {
    for (let i = 0; i < 100; i += 1) {
      expect(createId()).toMatch(UUID_V4)
    }
  })

  it('连续 1000 个不重复', () => {
    const ids = new Set(Array.from({ length: 1000 }, () => createId()))
    expect(ids.size).toBe(1000)
  })
})

describe('createStableId', () => {
  it('生成 UUID v5 形态，且同一输入永远相同', () => {
    const first = createStableId('v1:transaction:12')
    const second = createStableId('v1:transaction:12')
    expect(first).toMatch(UUID_V5)
    expect(first).toBe(second)
  })

  it('不同输入不重复', () => {
    const ids = new Set(['account', 'stock', 'transaction', 'ttrade'].flatMap((kind) =>
      Array.from({ length: 200 }, (_, index) => createStableId(`v1:${kind}:${index}`)),
    ))
    expect(ids.size).toBe(800)
  })
})

