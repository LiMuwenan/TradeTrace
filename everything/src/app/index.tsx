import { router } from 'expo-router'
import { useMemo, useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import {
  Button,
  Card,
  EmptyState,
  Eyebrow,
  Fab,
  Field,
  Loading,
  Money,
  RowButton,
  Screen,
  SectionTitle,
  Sheet,
} from '@/components/ui'
import { accountRows, mergedProfit } from '@/data/stats'
import { useTrade } from '@/data/trade-context'
import { colors, radius, spacing, typography } from '@/theme/tokens'
import { formatNumber } from '@/utils/format'

export default function HomeScreen() {
  const { state, ready, actions } = useTrade()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const rows = useMemo(() => accountRows(state), [state])
  const total = useMemo(() => mergedProfit(state), [state])
  const holdingStocks = rows.reduce((sum, row) => sum + row.holdingCount, 0)

  function submitAccount() {
    const trimmed = name.trim()
    if (!trimmed) {
      setError('请输入账户名称')
      return
    }
    actions.createAccount(trimmed)
    setName('')
    setError('')
    setAdding(false)
  }

  if (!ready) return <Screen><Loading /></Screen>

  return (
    <Screen scroll fab={<Fab label="添加账户" onPress={() => setAdding(true)} />}>
      <View style={styles.header}>
        <View style={styles.flex}>
          <Eyebrow>Trade Trace</Eyebrow>
          <Text style={styles.title}>交易记录</Text>
        </View>
        <View style={styles.headerActions}>
          <Button
            label="收益统计"
            variant="secondary"
            small
            onPress={() => router.push('/summary')}
          />
          <Button
            label="设置"
            variant="ghost"
            small
            onPress={() => router.push('/settings')}
          />
        </View>
      </View>

      <View style={styles.hero}>
        <Text style={styles.heroLabel}>累计收益</Text>
        <Text
          style={[
            styles.heroValue,
            typography.number,
            { color: total >= 0 ? '#FF7B86' : '#5FD3A6' },
          ]}
        >
          {total >= 0 ? '+' : '-'}
          {formatNumber(Math.abs(total), 2)}
        </Text>
        <View style={styles.heroMetaRow}>
          <View style={styles.heroMeta}>
            <Text style={styles.heroMetaValue}>{rows.length}</Text>
            <Text style={styles.heroMetaLabel}>账户</Text>
          </View>
          <View style={styles.heroMetaDivider} />
          <View style={styles.heroMeta}>
            <Text style={styles.heroMetaValue}>
              {state.stocks.filter((stock) => !stock.deletedAt).length}
            </Text>
            <Text style={styles.heroMetaLabel}>股票</Text>
          </View>
          <View style={styles.heroMetaDivider} />
          <View style={styles.heroMeta}>
            <Text style={styles.heroMetaValue}>{holdingStocks}</Text>
            <Text style={styles.heroMetaLabel}>持仓</Text>
          </View>
        </View>
      </View>

      <SectionTitle
        right={
          <Button
            label="管理账户"
            variant="ghost"
            small
            onPress={() => router.push('/accounts')}
          />
        }
      >
        账户
      </SectionTitle>

      {rows.length === 0 ? (
        <Card muted>
          <EmptyState
            title="还没有账户"
            description="先创建一个证券账户，再按账户记录股票与买卖流水。"
            action={<Button label="创建账户" onPress={() => setAdding(true)} />}
          />
        </Card>
      ) : (
        <View style={styles.list}>
          {rows.map((row) => (
            <RowButton
              key={row.accountId}
              onPress={() =>
                router.push({ pathname: '/account/[id]', params: { id: row.accountId } })
              }
            >
              <Card style={styles.accountCard}>
                <View style={styles.accountMain}>
                  <Text style={styles.accountName}>{row.name}</Text>
                  <Text style={styles.accountMeta}>
                    {row.stockCount} 只股票 · 持仓 {row.holdingCount} 只
                  </Text>
                </View>
                <View style={styles.accountProfit}>
                  <Money value={row.profit} />
                  <Text style={styles.accountProfitLabel}>累计收益</Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </Card>
            </RowButton>
          ))}
        </View>
      )}

      <Text style={styles.footerNote}>
        数据保存在本机，可通过「设置」使用坚果云 WebDAV 同步；尚未连接 lianghua 后端。
      </Text>

      <Sheet
        visible={adding}
        title="添加账户"
        onClose={() => setAdding(false)}
        footer={
          <>
            <Button label="取消" variant="secondary" onPress={() => setAdding(false)} />
            <Button label="添加" onPress={submitAccount} />
          </>
        }
      >
        <Field
          label="账户名称"
          value={name}
          onChangeText={(text) => {
            setName(text)
            setError('')
          }}
          placeholder="例如：华泰证券"
          autoFocus
          error={error}
        />
      </Sheet>
    </Screen>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingTop: spacing.lg,
    paddingBottom: spacing.lg,
    gap: spacing.md,
  },
  headerActions: { flexDirection: 'row', gap: spacing.sm },
  title: { ...typography.title, fontSize: 26, color: colors.ink, marginTop: 2 },
  hero: {
    backgroundColor: colors.ink,
    borderRadius: radius.xl,
    padding: spacing.xl,
  },
  heroLabel: {
    ...typography.label,
    color: '#A7ACB5',
    letterSpacing: 1,
  },
  heroValue: { fontSize: 40, fontWeight: '700', letterSpacing: -1.2, marginTop: spacing.xs },
  heroMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.xl,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.12)',
  },
  heroMeta: { flex: 1, alignItems: 'flex-start' },
  heroMetaDivider: { width: 1, height: 28, backgroundColor: 'rgba(255,255,255,0.12)' },
  heroMetaValue: {
    ...typography.number,
    color: colors.surface,
    fontSize: 18,
    fontWeight: '600',
  },
  heroMetaLabel: { ...typography.caption, color: '#8F949D', marginTop: 2 },
  list: { gap: spacing.sm },
  accountCard: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.lg,
    gap: spacing.md,
  },
  accountMain: { flex: 1 },
  accountName: { ...typography.body, fontWeight: '600', color: colors.ink },
  accountMeta: { ...typography.caption, color: colors.inkTertiary, marginTop: 3 },
  accountProfit: { alignItems: 'flex-end' },
  accountProfitLabel: { ...typography.caption, color: colors.inkTertiary, marginTop: 2 },
  chevron: { fontSize: 22, color: colors.inkTertiary, marginLeft: spacing.xs },
  footerNote: {
    ...typography.caption,
    color: colors.inkTertiary,
    textAlign: 'center',
    marginTop: spacing.xxl,
  },
})
