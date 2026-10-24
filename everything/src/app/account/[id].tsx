import { router, useLocalSearchParams } from 'expo-router'
import { useMemo, useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import {
  ActionSheet,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Fab,
  Field,
  IconButton,
  Loading,
  Money,
  RowButton,
  Screen,
  Sheet,
  TopBar,
} from '@/components/ui'
import type { ActionItem } from '@/components/ui'
import { accountProfit, stockCycleSummary, stockProfit, stockTransactions } from '@/data/stats'
import { useTrade } from '@/data/trade-context'
import type { Stock } from '@/data/types'
import { colors, spacing, typography } from '@/theme/tokens'
import { formatNumber, formatPrice } from '@/utils/format'
import { goBack } from '@/utils/navigation'

export default function AccountDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const accountId = id
  const { state, ready, actions } = useTrade()

  const [formStock, setFormStock] = useState<Stock | null>(null)
  const [formVisible, setFormVisible] = useState(false)
  const [stockName, setStockName] = useState('')
  const [stockCode, setStockCode] = useState('')
  const [formError, setFormError] = useState('')
  const [menuStock, setMenuStock] = useState<Stock | null>(null)
  const [pendingDelete, setPendingDelete] = useState<Stock | null>(null)

  const account = state.accounts.find((item) => item.id === accountId && !item.deletedAt)

  const stocks = useMemo(() => {
    return state.stocks
      .filter((stock) => stock.accountId === accountId && !stock.deletedAt)
      .map((stock) => {
        const transactions = stockTransactions(state, stock.id)
        return {
          stock,
          summary: stockCycleSummary(transactions),
          profit: stockProfit(state, stock.id),
        }
      })
      .sort((a, b) => {
        if (b.summary.totalShares !== a.summary.totalShares) {
          return b.summary.totalShares - a.summary.totalShares
        }
        return b.stock.createdAt.localeCompare(a.stock.createdAt)
      })
  }, [state, accountId])

  const profit = useMemo(() => accountProfit(state, accountId), [state, accountId])
  const holdingCount = stocks.filter((row) => row.summary.totalShares > 0).length

  function openCreate() {
    setFormStock(null)
    setStockName('')
    setStockCode('')
    setFormError('')
    setFormVisible(true)
  }

  function openEdit(stock: Stock) {
    setFormStock(stock)
    setStockName(stock.name)
    setStockCode(stock.code)
    setFormError('')
    setFormVisible(true)
  }

  function submitStock() {
    const name = stockName.trim()
    const code = stockCode.trim()
    if (!name) {
      setFormError('请输入股票名称')
      return
    }
    if (formStock) {
      actions.editStock({ ...formStock, name, code })
    } else {
      actions.createStock({ accountId, name, code })
    }
    setFormVisible(false)
  }

  if (!ready) return <Screen><Loading /></Screen>
  if (!account) {
    return (
      <Screen scroll>
        <TopBar title="账户" onBack={goBack} />
        <EmptyState title="账户不存在" description="该账户可能已被删除。" />
      </Screen>
    )
  }

  const menuItems: ActionItem[] = menuStock
    ? [
        { label: '编辑股票', onPress: () => openEdit(menuStock) },
        {
          label: '删除股票',
          danger: true,
          onPress: () => setPendingDelete(menuStock),
        },
      ]
    : []

  return (
    <Screen scroll fab={<Fab label="添加股票" onPress={openCreate} />}>
      <TopBar title={account.name} subtitle="账户详情" onBack={goBack} />

      <Card style={styles.summaryCard}>
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>累计收益</Text>
          <Money value={profit} style={styles.summaryValue} />
        </View>
        <View style={styles.summaryDivider} />
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>股票</Text>
          <Text style={[styles.summaryValue, typography.number]}>{stocks.length}</Text>
        </View>
        <View style={styles.summaryDivider} />
        <View style={styles.summaryItem}>
          <Text style={styles.summaryLabel}>持仓</Text>
          <Text style={[styles.summaryValue, typography.number]}>{holdingCount}</Text>
        </View>
      </Card>

      <Text style={styles.sectionLabel}>股票</Text>

      {stocks.length === 0 ? (
        <Card muted>
          <EmptyState
            title="暂无股票"
            description="添加股票后即可录入买入、卖出与股息记录。"
            action={<Button label="添加股票" onPress={openCreate} />}
          />
        </Card>
      ) : (
        <View style={styles.list}>
          {stocks.map(({ stock, summary, profit: stockProfitValue }) => (
            <RowButton
              key={stock.id}
              onPress={() =>
                router.push({ pathname: '/stock/[id]', params: { id: stock.id } })
              }
            >
              <Card style={styles.stockCard}>
                <View style={styles.flex}>
                  <View style={styles.stockTitleRow}>
                    <Text style={styles.stockName}>{stock.name}</Text>
                    <Text style={styles.stockCode}>{stock.code}</Text>
                  </View>
                  <Text style={styles.stockMeta}>
                    持仓 {formatNumber(summary.totalShares, 0)} 股 · 成本{' '}
                    {formatPrice(summary.avgCost)}
                  </Text>
                  <Text
                    style={[
                      styles.stockCycle,
                      { color: summary.cycleCost >= 0 ? colors.profit : colors.loss },
                    ]}
                  >
                    持仓收益 {summary.cycleCost >= 0 ? '+' : '-'}
                    {formatNumber(Math.abs(summary.cycleCost), 2)}
                  </Text>
                </View>
                <View style={styles.stockRight}>
                  <Money value={stockProfitValue} />
                  <Text style={styles.stockProfitLabel}>累计</Text>
                </View>
                <IconButton
                  glyph="···"
                  label="股票操作"
                  onPress={() => setMenuStock(stock)}
                />
              </Card>
            </RowButton>
          ))}
        </View>
      )}

      <Sheet
        visible={formVisible}
        title={formStock ? '编辑股票' : '添加股票'}
        onClose={() => setFormVisible(false)}
        footer={
          <>
            <Button label="取消" variant="secondary" onPress={() => setFormVisible(false)} />
            <Button label="保存" onPress={submitStock} />
          </>
        }
      >
        <Field
          label="股票名称"
          value={stockName}
          onChangeText={(text) => {
            setStockName(text)
            setFormError('')
          }}
          placeholder="例如：贵州茅台"
          autoFocus
          error={formError}
        />
        <Field label="股票代码" value={stockCode} onChangeText={setStockCode} placeholder="例如：600519" />
      </Sheet>

      <ActionSheet
        visible={menuStock !== null}
        title={menuStock?.name}
        items={menuItems}
        onClose={() => setMenuStock(null)}
      />

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="删除股票"
        message={`确定删除「${pendingDelete?.name ?? ''}」？该股票下所有交易记录与做T关联将被一并删除。`}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) actions.removeStock(pendingDelete.id)
          setPendingDelete(null)
        }}
      />
    </Screen>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  summaryCard: { flexDirection: 'row', alignItems: 'center', marginTop: spacing.sm },
  summaryItem: { flex: 1, alignItems: 'center' },
  summaryLabel: { ...typography.caption, color: colors.inkTertiary },
  summaryValue: { fontSize: 18, fontWeight: '700', marginTop: 4 },
  summaryDivider: { width: 1, height: 32, backgroundColor: colors.line },
  sectionLabel: {
    ...typography.section,
    color: colors.inkSecondary,
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  list: { gap: spacing.sm },
  stockCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  stockTitleRow: { flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm },
  stockName: { ...typography.body, fontWeight: '600', color: colors.ink },
  stockCode: { ...typography.caption, color: colors.inkTertiary, ...typography.number },
  stockMeta: { ...typography.caption, color: colors.inkSecondary, marginTop: 4 },
  stockCycle: { ...typography.caption, marginTop: 3, fontWeight: '500' },
  stockRight: { alignItems: 'flex-end', marginLeft: spacing.sm },
  stockProfitLabel: { ...typography.caption, color: colors.inkTertiary, marginTop: 2 },
})
