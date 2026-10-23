import { useMemo, useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Fab,
  Field,
  Loading,
  Screen,
  Sheet,
  TopBar,
} from '@/components/ui'
import { accountRows } from '@/data/stats'
import { useTrade } from '@/data/trade-context'
import type { Account } from '@/data/types'
import { colors, spacing, typography } from '@/theme/tokens'
import { formatNumber, shortDate } from '@/utils/format'
import { goBack } from '@/utils/navigation'

export default function AccountsScreen() {
  const { state, ready, actions } = useTrade()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [pendingDelete, setPendingDelete] = useState<Account | null>(null)

  const rows = useMemo(() => accountRows(state), [state])

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
      <TopBar title="账户管理" onBack={goBack} />

      {rows.length === 0 ? (
        <Card muted style={{ marginTop: spacing.lg }}>
          <EmptyState
            title="暂无账户"
            description="账户是交易记录的顶层容器，删除账户会连带删除其下所有股票与流水。"
            action={<Button label="创建账户" onPress={() => setAdding(true)} />}
          />
        </Card>
      ) : (
        <View style={styles.list}>
          {rows.map((row) => {
            const account = state.accounts.find((item) => item.id === row.accountId)
            return (
              <Card key={row.accountId} style={styles.row}>
                <View style={styles.flex}>
                  <Text style={styles.name}>{row.name}</Text>
                  <Text style={styles.meta}>
                    {row.stockCount} 只股票 · 累计收益{' '}
                    {row.profit >= 0 ? '+' : '-'}
                    {formatNumber(Math.abs(row.profit), 2)}
                    {account ? ` · 创建于 ${shortDate(account.createdAt.slice(0, 10))}` : ''}
                  </Text>
                </View>
                <Button
                  label="删除"
                  variant="danger"
                  small
                  onPress={() => account && setPendingDelete(account)}
                />
              </Card>
            )
          })}
        </View>
      )}

      <Text style={styles.footerNote}>
        共 {rows.length} 个账户 · 累计收益{' '}
        {formatNumber(
          rows.reduce((sum, row) => sum + row.profit, 0),
          2,
        )}
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

      <ConfirmDialog
        visible={pendingDelete !== null}
        title="删除账户"
        message={`确定删除账户「${pendingDelete?.name ?? ''}」？该账户下所有股票与交易记录将被一并删除。`}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) actions.removeAccount(pendingDelete.id)
          setPendingDelete(null)
        }}
      />
    </Screen>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  list: { gap: spacing.sm, marginTop: spacing.lg },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  name: { ...typography.body, fontWeight: '600', color: colors.ink },
  meta: { ...typography.caption, color: colors.inkTertiary, marginTop: 3 },
  footerNote: {
    ...typography.caption,
    color: colors.inkTertiary,
    marginTop: spacing.xl,
    textAlign: 'center',
  },
})
