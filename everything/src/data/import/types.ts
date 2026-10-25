import type { SourceRef, TransactionKind } from '../types'

/** OCR 引擎输出的一个文本块（坐标单位为原图像素，左上角为原点） */
export interface OcrLine {
  text: string
  x: number
  y: number
  width: number
  height: number
  confidence: number
}

/** 引擎适配层：Android / Web 各自实现，解析层只依赖本接口 */
export interface OcrEngine {
  recognize(imageUri: string): Promise<OcrLine[]>
}

export type SkipKind = '银证转账' | '申购配号' | '月份分组' | '空状态' | '页脚' | '无法识别'

/** 一条候选交易：字段缺失时置空并给出 warnings，不猜测 */
export interface ParsedRow {
  rowIndex: number
  templateId: string
  rawBlock: string[]
  type: TransactionKind
  /** 归一化后的股票名称 */
  name: string
  /** yyyy-MM-dd */
  date: string
  /** HH:mm，缺失为 '' */
  time: string
  price: number
  shares: number
  commission: number
  /** 仅 type=股息：正=入账，负=税补缴 */
  dividend?: number
  /** 成交金额绝对值（股息为带符号金额） */
  amount: number
  confidence: number
  warnings: string[]
  note?: string
}

export interface SkippedRow {
  rowIndex: number
  kind: SkipKind
  raw: string
  reason: string
}

export interface ParseResult {
  templateId: string
  /** 从截图头部读到的券商与尾号，如「浙商证券 *4768」；读不到为 '' */
  accountHint: string
  candidates: ParsedRow[]
  skipped: SkippedRow[]
  warnings: string[]
}

/** 候选 → 交易输入所需的溯源信息由导入服务补齐 */
export type CandidateSourceRef = SourceRef
