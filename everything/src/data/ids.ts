/** 生成 UUID 形态的稳定 ID（同步合并的主键） */

let counter = 0

function formatUuid(hex: string): string {
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/**
 * 不引入第三方依赖：时间戳 + 递增计数器 + 随机数拼成 32 位十六进制，
 * 再写入 version=4 与 variant 8/9/a/b。
 */
export function createId(): string {
  counter = (counter + 1) % 0x10000
  const time = Date.now() % 0x100000000

  const parts = [
    time.toString(16).padStart(8, '0'),
    counter.toString(16).padStart(8, '0'),
    Math.floor(Math.random() * 0x100000000).toString(16).padStart(8, '0'),
    Math.floor(Math.random() * 0x100000000).toString(16).padStart(8, '0'),
  ]

  let hex = parts.join('').slice(0, 32)
  hex = `${hex.slice(0, 12)}4${hex.slice(13)}`
  const variant = '89ab'[Math.floor(Math.random() * 4)]
  hex = `${hex.slice(0, 16)}${variant}${hex.slice(17)}`

  return formatUuid(hex)
}

/** FNV-1a 32 位散列，用于从稳定字符串派生 ID */
function fnv1a(text: string, seed: number): number {
  let hash = seed >>> 0
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash >>> 0
}

/**
 * 由字符串派生稳定 ID（UUID v5 形态）：同样的输入在任何设备上都得到同一个 ID。
 * v1 数据迁移必须用它，否则两台设备各自迁移同一份旧数据后会生成不同 UUID，
 * 合并时同一笔交易会被当成两条记录，收益翻倍。
 */
export function createStableId(scope: string): string {
  const chunks: string[] = []
  for (let index = 0; index < 4; index += 1) {
    const seed = (0x811c9dc5 ^ Math.imul(index + 1, 0x9e3779b1)) >>> 0
    chunks.push(fnv1a(`${scope}#${index}`, seed).toString(16).padStart(8, '0'))
  }

  let hex = chunks.join('')
  hex = `${hex.slice(0, 12)}5${hex.slice(13)}`
  hex = `${hex.slice(0, 16)}${'89ab'[parseInt(hex[16], 16) % 4]}${hex.slice(17)}`

  return formatUuid(hex)
}
