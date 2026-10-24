import { useMemo, useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import {
  Card,
  EmptyState,
  Eyebrow,
  Loading,
  Money,
  Screen,
  SectionTitle,
  Segmented,
  TopBar,
} from '@/components/ui'
import {
  accountRows,
  allTTradeRows,
  mergedProfit,
  stockProfitRows,
} from '@/data/stats'
import { useTrade } from '@/data/trade-context'
import { colors, spacing, typography } from '@/theme/tokens'
import { formatNumber, shortDate } from '@/utils/format'
import { goBack } from '@/utils/navigation'

type Tab = 'account' | 'stock' | 'merged' | 'ttrade'

const TABS: { value: Tab; label: string }[] = [
  { value: 'account', label: '账户' },
  { value: 'stock', label: '个股' },
  { value: 'merged', label: '合并' },
  { value: 'ttrade', label: '做T' },
]

export default function SummaryScreen() {
  const { state, ready } = useTrade()
  const [tab, setTab] = useState<Tab>('account')

  const accounts = useMemo(() => accountRows(state), [state])
  const stocks = useMemo(() => stockProfitRows(state), [state])
  const total = useMemo(() => mergedProfit(state), [state])
  const ttrades = useMemo(() => allTTradeRows(state), [state])

  if (!ready) return <Screen><Loading /></Screen>

  return (
    <Screen scroll>
      <TopBar title="收益统计" onBack={goBack} />

      <Segmented options={TABS} value={tab} onChange={setTab} />

      {tab === 'account' ? (
        accounts.length === 0 ? (
          <EmptyState title="暂无账户数据" description="添加账户并录入交易后即可查看。" />
        ) : (
          <View style={styles.list}>
            {accounts.map((row) => (
              <Card key={row.accountId} style={styles.row}>
                <View style={styles.flex}>
                  <Text style={styles.rowTitle}>{row.name}</Text>
                  <Text style={styles.rowMeta}>
                    {row.stockCount} 只股票 · 持仓 {row.holdingCount} 只
                  </Text>
                </View>
                <Money value={row.profit} />
              </Card>
            ))}
          </View>
        )
      ) : null}

      {tab === 'stock' ? (
        stocks.length === 0 ? (
          <EmptyState title="暂无个股数据" description="录入交易后按个股汇总累计收益。" />
        ) : (
          <View style={styles.list}>
            {stocks.map((row) => (
              <Card key={row.stockId} style={styles.row}>
                <View style={styles.flex}>
                  <Text style={styles.rowTitle}>{row.label}</Text>
                  <Text style={styles.rowMeta}>账户：{row.accountName}</Text>
                </View>
                <Money value={row.profit} />
              </Card>
            ))}
          </View>
        )
      ) : null}

      {tab === 'merged' ? (
        <Card style={styles.merged}>
          <Eyebrow>Merged P&amp;L</Eyebrow>
          <Text style={styles.mergedLabel}>合并账户总收益</Text>
          <Text
            style={[
              styles.mergedValue,
              typography.number,
              { color: total >= 0 ? colors.profit : colors.loss },
            ]}
          >
            {total >= 0 ? '+' : '-'}
            {formatNumber(Math.abs(total), 2)}
          </Text>
          <Text style={styles.mergedMeta}>
            {accounts.length} 个账户 · {stocks.length} 只股票 ·{' '}
            {state.transactions.filter((trade) => !trade.deletedAt).length} 笔交易
          </Text>
        </Card>
      ) : null}

      {tab === 'ttrade' ? (
        <>
          <SectionTitle>做T明细</SectionTitle>
          {ttrades.length === 0 ? (
            <EmptyState title="暂无做T记录" description="在卖出记录上关联买入记录后即可统计做T收益。" />
          ) : (
            <View style={styles.list}>
              {ttrades.map((row) => (
                <Card key={row.id} style={styles.row}>
                  <View style={styles.flex}>
                    <Text style={styles.rowTitle}>{row.stockLabel}</Text>
                    <Text style={styles.rowMeta}>
                      {shortDate(row.buyDate)} 买入 → {shortDate(row.sellDate)} 卖出 · T
                      {formatNumber(row.shares, 0)} 股
                    </Text>
                  </View>
                  <Money value={row.profit} />
                </Card>
              ))}
            </View>
          )}
        </>
      ) : null}
    </Screen>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  list: { gap: spacing.sm, marginTop: spacing.lg },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  rowTitle: { ...typography.body, fontWeight: '600', color: colors.ink },
  rowMeta: { ...typography.caption, color: colors.inkTertiary, marginTop: 3 },
  merged: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
    marginTop: spacing.lg,
  },
  mergedLabel: { ...typography.label, color: colors.inkSecondary, marginTop: spacing.sm },
  mergedValue: { fontSize: 44, fontWeight: '700', letterSpacing: -1.2, marginTop: spacing.md },
  mergedMeta: { ...typography.caption, color: colors.inkTertiary, marginTop: spacing.lg },
})
