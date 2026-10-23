import { useEffect, useMemo, useState } from 'react'
import { Text, View } from 'react-native'

import { Button, Field, Pill, RowButton, Segmented, Sheet, SwitchRow } from '@/components/ui'
import { useTrade } from '@/data/trade-context'
import { availableBuys, tTradesBySell } from '@/data/stats'
import type { TransactionKind, TransactionTrade } from '@/data/types'
import { colors, radius, spacing, typography } from '@/theme/tokens'
import { formatNumber, formatPrice, isValidDateString, shortDate, todayString } from '@/utils/format'

const TYPE_OPTIONS: { value: TransactionKind; label: string }[] = [
  { value: '买入', label: '买入' },
  { value: '卖出', label: '卖出' },
  { value: '股息', label: '股息' },
]

function parseNumber(value: string): number | undefined {
  const parsed = Number(value.trim())
  return Number.isFinite(parsed) ? parsed : undefined
}

function fixed(value: number): string {
  return value.toFixed(3)
}

export function TransactionForm({
  visible,
  stockId,
  editing,
  onClose,
}: {
  visible: boolean
  stockId: number
  editing: TransactionTrade | null
  onClose: () => void
}) {
  const { actions } = useTrade()
  const [date, setDate] = useState(todayString())
  const [type, setType] = useState<TransactionKind>('买入')
  const [price, setPrice] = useState('')
  const [shares, setShares] = useState('')
  const [commission, setCommission] = useState('')
  const [dividend, setDividend] = useState('')
  const [note, setNote] = useState('')
  const [useExpected, setUseExpected] = useState(false)
  const [ratio, setRatio] = useState('0.015-0.02')
  const [buyLow, setBuyLow] = useState('')
  const [buyHigh, setBuyHigh] = useState('')
  const [sellLow, setSellLow] = useState('')
  const [sellHigh, setSellHigh] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!visible) return
    setErrors({})
    if (editing) {
      setDate(editing.date)
      setType(editing.type)
      setPrice(editing.price ? String(editing.price) : '')
      setShares(editing.shares ? String(Math.abs(editing.shares)) : '')
      setCommission(editing.commission ? String(editing.commission) : '')
      setDividend(editing.dividend != null ? String(editing.dividend) : '')
      setNote(editing.note ?? '')
      setUseExpected(editing.expectedRange != null)
      setRatio(editing.expectedRange ?? '0.015-0.02')
      setBuyLow(editing.expectedBuyLow != null ? String(editing.expectedBuyLow) : '')
      setBuyHigh(editing.expectedBuyHigh != null ? String(editing.expectedBuyHigh) : '')
      setSellLow(editing.expectedSellLow != null ? String(editing.expectedSellLow) : '')
      setSellHigh(editing.expectedSellHigh != null ? String(editing.expectedSellHigh) : '')
    } else {
      setDate(todayString())
      setType('买入')
      setPrice('')
      setShares('')
      setCommission('')
      setDividend('')
      setNote('')
      setUseExpected(false)
      setRatio('0.015-0.02')
      setBuyLow('')
      setBuyHigh('')
      setSellLow('')
      setSellHigh('')
    }
  }, [visible, editing])

  const isDividend = type === '股息'

  function calculateFromRatio(nextPrice = price, nextRatio = ratio) {
    const base = parseNumber(nextPrice)
    const parts = nextRatio.trim().split('-')
    if (!base || base <= 0 || parts.length !== 2) return
    const low = parseNumber(parts[0])
    const high = parseNumber(parts[1])
    if (low == null || high == null) return
    setBuyLow(fixed(base * (1 - low)))
    setBuyHigh(fixed(base * (1 - high)))
    setSellLow(fixed(base * (1 + low)))
    setSellHigh(fixed(base * (1 + high)))
  }

  function calculateFromPrice(nextBuyLow: string, nextSellHigh: string) {
    const base = parseNumber(price)
    const low = parseNumber(nextBuyLow)
    const high = parseNumber(nextSellHigh)
    if (!base || base <= 0 || low == null || high == null) return
    setRatio(`${fixed(1 - low / base)}-${fixed(high / base - 1)}`)
  }

  function toggleExpected(next: boolean) {
    setUseExpected(next)
    if (next) calculateFromRatio()
  }

  function submit() {
    const nextErrors: Record<string, string> = {}
    if (!isValidDateString(date)) nextErrors.date = '日期格式应为 YYYY-MM-DD'

    let parsedPrice = 0
    let parsedShares = 0
    let parsedCommission = 0
    let parsedDividend = 0

    if (isDividend) {
      parsedDividend = parseNumber(dividend) ?? NaN
      if (!Number.isFinite(parsedDividend) || parsedDividend <= 0) {
        nextErrors.dividend = '请输入大于 0 的股息金额'
      }
    } else {
      parsedPrice = parseNumber(price) ?? NaN
      parsedShares = parseNumber(shares) ?? NaN
      parsedCommission = parseNumber(commission) ?? 0
      if (!Number.isFinite(parsedPrice) || parsedPrice <= 0) nextErrors.price = '请输入价格'
      if (!Number.isInteger(parsedShares) || parsedShares <= 0) {
        nextErrors.shares = '请输入正整数股数'
      }
      if (!Number.isFinite(parsedCommission) || parsedCommission < 0) {
        nextErrors.commission = '手续费不能为负数'
      }
    }

    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    const payload = {
      stockId,
      date,
      type,
      price: isDividend ? 0 : parsedPrice,
      shares: isDividend ? 0 : type === '买入' ? parsedShares : -parsedShares,
      commission: isDividend ? 0 : parsedCommission,
      dividend: isDividend ? parsedDividend : undefined,
      expectedRange: !isDividend && useExpected ? ratio.trim() : undefined,
      expectedBuyLow: !isDividend && useExpected ? parseNumber(buyLow) : undefined,
      expectedBuyHigh: !isDividend && useExpected ? parseNumber(buyHigh) : undefined,
      expectedSellLow: !isDividend && useExpected ? parseNumber(sellLow) : undefined,
      expectedSellHigh: !isDividend && useExpected ? parseNumber(sellHigh) : undefined,
      note: note.trim() || undefined,
    }

    if (editing) {
      actions.editTransaction({ ...payload, id: editing.id, createdAt: editing.createdAt })
    } else {
      actions.createTransaction(payload)
    }
    onClose()
  }

  const previewCost = useMemo(() => {
    const parsedPrice = parseNumber(price) ?? 0
    const parsedShares = parseNumber(shares) ?? 0
    if (isDividend) return parseNumber(dividend) ?? 0
    return -parsedPrice * parsedShares - (parseNumber(commission) ?? 0)
  }, [price, shares, commission, dividend, isDividend])

  return (
    <Sheet
      visible={visible}
      title={editing ? '编辑交易' : '添加交易'}
      onClose={onClose}
      footer={
        <>
          <Button label="取消" variant="secondary" onPress={onClose} />
          <Button label="保存" onPress={submit} />
        </>
      }
    >
      <Field
        label="日期"
        value={date}
        onChangeText={setDate}
        placeholder="YYYY-MM-DD"
        error={errors.date}
      />
      <View style={{ flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md }}>
        <Button label="今天" variant="ghost" small onPress={() => setDate(todayString())} />
      </View>

      <Text style={styles.fieldLabel}>类型</Text>
      <Segmented options={TYPE_OPTIONS} value={type} onChange={setType} />

      <View style={{ height: spacing.lg }} />

      {isDividend ? (
        <Field
          label="股息金额"
          value={dividend}
          onChangeText={setDividend}
          keyboardType="decimal-pad"
          placeholder="0.00"
          error={errors.dividend}
        />
      ) : (
        <>
          <View style={styles.row}>
            <View style={styles.half}>
              <Field
                label="价格"
                value={price}
                onChangeText={(text) => {
                  setPrice(text)
                  if (useExpected) calculateFromRatio(text, ratio)
                }}
                keyboardType="decimal-pad"
                placeholder="0.000"
                error={errors.price}
              />
            </View>
            <View style={styles.half}>
              <Field
                label="股数"
                value={shares}
                onChangeText={setShares}
                keyboardType="numeric"
                placeholder="0"
                error={errors.shares}
              />
            </View>
          </View>
          <Field
            label="手续费"
            value={commission}
            onChangeText={setCommission}
            keyboardType="decimal-pad"
            placeholder="0.00"
            error={errors.commission}
          />

          <SwitchRow
            label="预期价格"
            description="按比例自动计算买入/卖出区间"
            value={useExpected}
            onToggle={toggleExpected}
          />
          {useExpected ? (
            <View style={{ gap: spacing.sm, marginTop: spacing.sm }}>
              <Field
                label="预期比例范围"
                value={ratio}
                onChangeText={(text) => {
                  setRatio(text)
                  calculateFromRatio(price, text)
                }}
                placeholder="0.015-0.02"
              />
              <View style={styles.row}>
                <View style={styles.half}>
                  <Field
                    label="预期买入低"
                    value={buyLow}
                    onChangeText={(text) => {
                      setBuyLow(text)
                      calculateFromPrice(text, sellHigh)
                    }}
                    keyboardType="decimal-pad"
                  />
                </View>
                <View style={styles.half}>
                  <Field label="预期买入高" value={buyHigh} onChangeText={setBuyHigh} keyboardType="decimal-pad" />
                </View>
              </View>
              <View style={styles.row}>
                <View style={styles.half}>
                  <Field label="预期卖出低" value={sellLow} onChangeText={setSellLow} keyboardType="decimal-pad" />
                </View>
                <View style={styles.half}>
                  <Field
                    label="预期卖出高"
                    value={sellHigh}
                    onChangeText={(text) => {
                      setSellHigh(text)
                      calculateFromPrice(buyLow, text)
                    }}
                    keyboardType="decimal-pad"
                  />
                </View>
              </View>
            </View>
          ) : null}
        </>
      )}

      <Field label="备注" value={note} onChangeText={setNote} placeholder="可选" />

      <View style={styles.preview}>
        <Text style={styles.previewLabel}>本笔费用</Text>
        <Text
          style={[
            styles.previewValue,
            typography.number,
            { color: previewCost >= 0 ? colors.profit : colors.loss },
          ]}
        >
          {previewCost >= 0 ? '+' : ''}
          {formatNumber(previewCost, 2)}
        </Text>
      </View>
    </Sheet>
  )
}

export function TTradeForm({
  visible,
  stockId,
  sell,
  onClose,
}: {
  visible: boolean
  stockId: number
  sell: TransactionTrade | null
  onClose: () => void
}) {
  const { state, actions } = useTrade()
  const [selectedBuyId, setSelectedBuyId] = useState<number | null>(null)
  const [shares, setShares] = useState('')
  const [error, setError] = useState('')

  const buys = useMemo(
    () => (sell ? availableBuys(state, stockId, sell.id) : []),
    [state, stockId, sell],
  )

  useEffect(() => {
    if (!visible || !sell) return
    setSelectedBuyId(buys[0]?.id ?? null)
    setShares(String(Math.abs(sell.shares)))
    setError('')
  }, [visible, sell, buys])

  if (!sell) return null

  const currentSell = sell
  const selectedBuy = buys.find((buy) => buy.id === selectedBuyId) ?? null

  function submit() {
    const parsed = parseNumber(shares) ?? 0
    if (!selectedBuy) {
      setError('请选择关联的买入记录')
      return
    }
    if (!Number.isInteger(parsed) || parsed <= 0) {
      setError('请输入正整数股数')
      return
    }
    const remaining = selectedBuy.shares - linkedShares(selectedBuy.id)
    if (parsed > remaining) {
      setError(`T出股数不能超过可关联股数（${formatNumber(remaining, 0)} 股）`)
      return
    }
    if (parsed > Math.abs(currentSell.shares)) {
      setError('T出股数不能超过卖出股数')
      return
    }
    actions.createTTrade({
      buyTransactionId: selectedBuy.id,
      sellTransactionId: currentSell.id,
      shares: parsed,
    })
    onClose()
  }

  function linkedShares(buyId: number): number {
    return state.tTrades
      .filter((tt) => tt.buyTransactionId === buyId && tt.sellTransactionId !== currentSell.id)
      .reduce((sum, tt) => sum + tt.shares, 0)
  }

  return (
    <Sheet
      visible={visible}
      title="做T关联"
      onClose={onClose}
      footer={
        <>
          <Button label="取消" variant="secondary" onPress={onClose} />
          <Button label="确认关联" onPress={submit} disabled={!selectedBuy} />
        </>
      }
    >
      <View style={styles.sellInfo}>
        <Pill label="卖出" tone="sell" />
        <Text style={styles.sellText}>
          {shortDate(sell.date)} · {formatNumber(Math.abs(sell.shares), 0)} 股 @
          {formatPrice(sell.price)}
        </Text>
      </View>

      <Text style={styles.fieldLabel}>选择关联买入记录</Text>
      {buys.length === 0 ? (
        <Text style={styles.hint}>暂无可关联的买入记录</Text>
      ) : (
        <View style={{ gap: spacing.sm }}>
          {buys.map((buy) => {
            const remaining = buy.shares - linkedShares(buy.id)
            const active = buy.id === selectedBuyId
            return (
              <RowButton
                key={buy.id}
                onPress={() => {
                  setSelectedBuyId(buy.id)
                  setError('')
                }}
                style={{
                  borderWidth: 1,
                  borderColor: active ? colors.accent : colors.line,
                  backgroundColor: active ? colors.accentSoft : colors.surface,
                  padding: spacing.md,
                  borderRadius: radius.md,
                }}
              >
                <View style={styles.buyRow}>
                  <View style={styles.flex}>
                    <Text style={styles.buyTitle}>
                      {shortDate(buy.date)} 买入 {formatNumber(buy.shares, 0)} 股 @
                      {formatPrice(buy.price)}
                    </Text>
                    <Text style={styles.buySub}>可关联 {formatNumber(remaining, 0)} 股</Text>
                  </View>
                  <View style={[styles.radio, active && styles.radioActive]} />
                </View>
              </RowButton>
            )
          })}
        </View>
      )}

      <View style={{ height: spacing.md }} />
      <Field
        label="T出股数"
        value={shares}
        onChangeText={(text) => {
          setShares(text)
          setError('')
        }}
        keyboardType="numeric"
        error={error}
      />

      {tTradesBySell(state, sell.id).length > 0 ? (
        <Text style={styles.hint}>
          该卖出已有 {tTradesBySell(state, sell.id).length} 条做T关联，可继续追加。
        </Text>
      ) : null}
    </Sheet>
  )
}

const styles = {
  fieldLabel: {
    ...typography.label,
    color: colors.inkSecondary,
    marginBottom: 6,
  } as const,
  row: { flexDirection: 'row' as const, gap: spacing.md },
  half: { flex: 1 },
  flex: { flex: 1 },
  preview: {
    flexDirection: 'row' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    marginTop: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceMuted,
  },
  previewLabel: { ...typography.label, color: colors.inkSecondary } as const,
  previewValue: { fontSize: 16, fontWeight: '700' as const },
  sellInfo: {
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  sellText: { ...typography.body, color: colors.ink } as const,
  hint: { ...typography.caption, color: colors.inkTertiary } as const,
  buyRow: { flexDirection: 'row' as const, alignItems: 'center' as const, gap: spacing.md },
  buyTitle: { ...typography.body, color: colors.ink } as const,
  buySub: { ...typography.caption, color: colors.inkTertiary, marginTop: 2 } as const,
  radio: {
    width: 18,
    height: 18,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: colors.inkTertiary,
  },
  radioActive: { borderWidth: 5, borderColor: colors.accent },
}
