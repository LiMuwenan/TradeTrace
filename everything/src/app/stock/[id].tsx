import { useLocalSearchParams } from 'expo-router'
import { useMemo, useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import { TransactionForm, TTradeForm } from '@/components/forms'
import {
  ActionSheet,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Fab,
  IconButton,
  Loading,
  Money,
  Pill,
  RowButton,
  Screen,
  Sheet,
  TopBar,
} from '@/components/ui'
import type { ActionItem } from '@/components/ui'
import {
  sortTransactionsDesc,
  stockCycleSummary,
  stockTransactions,
  tTradeDetails,
  tTradesBySell,
} from '@/data/stats'
import { useTrade } from '@/data/trade-context'
import type { TransactionTrade } from '@/data/types'
import { transactionCost } from '@/data/types'
import { colors, spacing, typography } from '@/theme/tokens'
import { formatNumber, formatPrice, shortDate } from '@/utils/format'
import { goBack } from '@/utils/navigation'

function typeTone(type: TransactionTrade['type']) {
  if (type === '买入') return 'buy' as const
  if (type === '卖出') return 'sell' as const
  return 'dividend' as const
}

export default function StockDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const stockId = id
  const { state, ready, actions } = useTrade()

  const [formVisible, setFormVisible] = useState(false)
  const [editing, setEditing] = useState<TransactionTrade | null>(null)
  const [menuTrade, setMenuTrade] = useState<TransactionTrade | null>(null)
  const [linkSell, setLinkSell] = useState<TransactionTrade | null>(null)
  const [linkListSell, setLinkListSell] = useState<TransactionTrade | null>(null)
  const [pendingDelete, setPendingDelete] = useState<TransactionTrade | null>(null)
  const [pendingDeleteTT, setPendingDeleteTT] = useState<string | null>(null)

  const stock = state.stocks.find((item) => item.id === stockId && !item.deletedAt)
  const transactions = useMemo(
    () => sortTransactionsDesc(stockTransactions(state, stockId)),
    [state, stockId],
  )
  const summary = useMemo(() => stockCycleSummary(transactions), [transactions])
  const ttrades = useMemo(() => tTradeDetails(state, stockId), [state, stockId])

  if (!ready) return <Screen><Loading /></Screen>
  if (!stock) {
    return (
      <Screen scroll>
        <TopBar title="股票" onBack={goBack} />
        <EmptyState title="股票不存在" description="该股票可能已被删除。" />
      </Screen>
    )
  }

  function openCreate() {
    setEditing(null)
    setFormVisible(true)
  }

  function openEdit(trade: TransactionTrade) {
    setEditing(trade)
    setFormVisible(true)
  }

  function tLabelFor(sellId: string): string {
    const links = ttrades.filter((row) => row.ttrade.sellTransactionId === sellId)
    if (links.length === 0) return ''
    return links
      .map((row) => `${shortDate(row.buy.date)}买入 T${formatNumber(row.ttrade.shares, 0)}股`)
      .join(', ')
  }

  const linkedCount = menuTrade
    ? tTradesBySell(state, menuTrade.id).length
    : 0

  const menuItems: ActionItem[] = menuTrade
    ? [
        { label: '编辑交易', onPress: () => openEdit(menuTrade) },
        ...(menuTrade.type === '卖出'
          ? [{ label: '关联做T', onPress: () => setLinkSell(menuTrade) }]
          : []),
        ...(menuTrade.type === '卖出' && linkedCount > 0
          ? [{ label: '查看 / 删除做T关联', onPress: () => setLinkListSell(menuTrade) }]
          : []),
        {
          label: '删除交易',
          danger: true,
          onPress: () => setPendingDelete(menuTrade),
        },
      ]
    : []

  const clearProfit = summary.totalCost - summary.cycleCost

  return (
    <Screen scroll fab={<Fab label="添加交易" onPress={openCreate} />}>
      <TopBar
        title={`${stock.name}${stock.code ? ` ${stock.code}` : ''}`}
        subtitle="个股交易流水"
        onBack={goBack}
      />

      <Card style={styles.summaryCard}>
        <View style={styles.summaryRow}>
          <SummaryItem label="持有" value={`${formatNumber(summary.totalShares, 0)} 股`} />
          <SummaryItem label="持仓成本" value={formatPrice(summary.avgCost)} />
          <SummaryItem
            label="持仓收益"
            value={`${summary.cycleCost >= 0 ? '+' : '-'}${formatNumber(Math.abs(summary.cycleCost), 2)}`}
            tone={summary.cycleCost >= 0 ? colors.profit : colors.loss}
          />
        </View>
        <View style={styles.summaryDivider} />
        <View style={styles.summaryRow}>
          <SummaryItem
            label="总成本"
            value={summary.totalShares === 0 ? '0.000' : formatPrice(summary.totalAvgCost)}
          />
          <SummaryItem
            label="总收益"
            value={`${summary.totalCost >= 0 ? '+' : '-'}${formatNumber(Math.abs(summary.totalCost), 2)}`}
            tone={summary.totalCost >= 0 ? colors.profit : colors.loss}
          />
          <SummaryItem
            label="清仓收益"
            value={`${clearProfit >= 0 ? '+' : '-'}${formatNumber(Math.abs(clearProfit), 2)}`}
            tone={clearProfit >= 0 ? colors.profit : colors.loss}
          />
        </View>
      </Card>

      <View style={styles.listHeader}>
        <Text style={styles.sectionLabel}>交易流水</Text>
        <Text style={styles.countLabel}>{transactions.length} 笔</Text>
      </View>

      {transactions.length === 0 ? (
        <Card muted>
          <EmptyState
            title="暂无交易记录"
            description="点击右下角按钮录入第一笔买入或卖出。"
            action={<Button label="添加交易" onPress={openCreate} />}
          />
        </Card>
      ) : (
        <View style={styles.list}>
          {transactions.map((trade) => {
            const tLabel = tLabelFor(trade.id)
            const cost = transactionCost(trade)
            return (
              <RowButton key={trade.id} onPress={() => openEdit(trade)}>
                <Card style={styles.tradeCard}>
                  <View style={styles.flex}>
                    <View style={styles.tradeTitleRow}>
                      <Pill label={trade.type} tone={typeTone(trade.type)} />
                      <Text style={styles.tradeDate}>{trade.date}</Text>
                      {trade.type === '股息' ? (
                        <Text style={styles.tradeMain}>
                          股息 {formatNumber(trade.dividend ?? 0, 2)}
                        </Text>
                      ) : (
                        <Text style={styles.tradeMain}>
                          {formatNumber(Math.abs(trade.shares), 0)} 股 @{formatPrice(trade.price)}
                        </Text>
                      )}
                    </View>
                    <View style={styles.tradeMetaRow}>
                      {trade.commission > 0 ? (
                        <Text style={styles.tradeMeta}>
                          手续费 {formatNumber(trade.commission, 2)}
                        </Text>
                      ) : null}
                      {trade.source === 'ocr' ? (
                        <Text style={styles.tradeMeta}>OCR 识别</Text>
                      ) : null}
                      {trade.time ? <Text style={styles.tradeMeta}>{trade.time}</Text> : null}
                      {trade.note ? <Text style={styles.tradeMeta}>{trade.note}</Text> : null}
                    </View>
                    {tLabel ? <Text style={styles.tLink}>↓ 做T: {tLabel}</Text> : null}
                  </View>
                  <Money value={cost} />
                  <IconButton
                    glyph="···"
                    label="交易操作"
                    onPress={() => setMenuTrade(trade)}
                  />
                </Card>
              </RowButton>
            )
          })}
        </View>
      )}

      <TransactionForm
        visible={formVisible}
        stockId={stockId}
        editing={editing}
        onClose={() => setFormVisible(false)}
      />

      <TTradeForm
        visible={linkSell !== null}
        stockId={stockId}
        sell={linkSell}
        onClose={() => setLinkSell(null)}
      />

      <ActionSheet
        visible={menuTrade !== null}
        title={menuTrade ? `${menuTrade.date} ${menuTrade.type}` : '交易操作'}
        items={menuItems}
        onClose={() => setMenuTrade(null)}
      />

      <Sheet
        visible={linkListSell !== null}
        title="做T关联"
        onClose={() => setLinkListSell(null)}
      >
        {linkListSell ? (
          <View style={{ gap: spacing.sm }}>
            {tTradesBySell(state, linkListSell.id).map((row) => (
              <View key={row.ttrade.id} style={styles.linkRow}>
                <View style={styles.flex}>
                  <Text style={styles.linkTitle}>
                    {shortDate(row.buy.date)} 买入 → {shortDate(row.sell.date)} 卖出
                  </Text>
                  <Text style={styles.linkMeta}>
                    T{formatNumber(row.ttrade.shares, 0)} 股 · 收益{' '}
                    {row.profit >= 0 ? '+' : '-'}
                    {formatNumber(Math.abs(row.profit), 2)}
                  </Text>
                </View>
                <Button
                  label="删除"
                  variant="danger"
                  small
                  onPress={() => setPendingDeleteTT(row.ttrade.id)}
                />
              </View>
            ))}
          </View>
        ) : null}
      </Sheet>

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="删除交易"
        message="确定删除此交易记录？关联的做T记录也会被删除。"
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) actions.removeTransaction(pendingDelete.id)
          setPendingDelete(null)
        }}
      />

      <ConfirmDialog
        visible={pendingDeleteTT !== null}
        title="删除做T关联"
        message="确定删除这笔做T关联？原始买卖记录不受影响。"
        onCancel={() => setPendingDeleteTT(null)}
        onConfirm={() => {
          if (pendingDeleteTT != null) actions.removeTTrade(pendingDeleteTT)
          setPendingDeleteTT(null)
        }}
      />
    </Screen>
  )
}

function SummaryItem({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: string
}) {
  return (
    <View style={styles.summaryItem}>
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text
        style={[styles.summaryValue, typography.number, tone ? { color: tone } : null]}
        numberOfLines={1}
      >
        {value}
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  summaryCard: { marginTop: spacing.sm },
  summaryRow: { flexDirection: 'row', alignItems: 'center' },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryLabel: { ...typography.caption, color: colors.inkTertiary },
  summaryValue: { fontSize: 15, fontWeight: '600', color: colors.ink, marginTop: 4 },
  summaryDivider: { height: 1, backgroundColor: colors.line, marginVertical: spacing.md },
  listHeader: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  sectionLabel: { ...typography.section, color: colors.inkSecondary },
  countLabel: { ...typography.caption, color: colors.inkTertiary, ...typography.number },
  list: { gap: spacing.sm },
  tradeCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.md,
  },
  tradeTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flexWrap: 'wrap',
  },
  tradeDate: { ...typography.caption, color: colors.inkTertiary, ...typography.number },
  tradeMain: { ...typography.body, color: colors.ink, ...typography.number },
  tradeMetaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: 4,
  },
  tradeMeta: { ...typography.caption, color: colors.inkSecondary },
  tLink: { ...typography.caption, color: colors.accent, marginTop: 4 },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
  },
  linkTitle: { ...typography.body, color: colors.ink },
  linkMeta: { ...typography.caption, color: colors.inkTertiary, marginTop: 2 },
})
