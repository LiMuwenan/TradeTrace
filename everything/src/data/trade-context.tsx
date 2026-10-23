import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import * as mutations from './state'
import { loadTradeState, saveTradeState } from './storage'
import { createEmptyState } from './types'
import type { Stock, TradeState, TransactionTrade, TTrade } from './types'
import { nowIso } from '@/utils/format'

interface TradeActions {
  createAccount: (name: string) => void
  removeAccount: (accountId: number) => void
  createStock: (input: Pick<Stock, 'accountId' | 'name' | 'code'>) => void
  editStock: (stock: Stock) => void
  removeStock: (stockId: number) => void
  createTransaction: (input: Omit<TransactionTrade, 'id' | 'createdAt'>) => void
  editTransaction: (trade: TransactionTrade) => void
  removeTransaction: (transactionId: number) => void
  createTTrade: (input: Pick<TTrade, 'buyTransactionId' | 'sellTransactionId' | 'shares'>) => void
  removeTTrade: (ttradeId: number) => void
  removeTTradesBySell: (sellId: number) => void
  /** 用云端数据整体替换本机数据（坚果云同步下载） */
  replaceState: (next: TradeState) => void
}

interface TradeContextValue {
  state: TradeState
  ready: boolean
  actions: TradeActions
}

const TradeContext = createContext<TradeContextValue | null>(null)

export function TradeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<TradeState>(createEmptyState)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let alive = true
    loadTradeState().then((loaded) => {
      if (!alive) return
      setState(loaded)
      setReady(true)
    })
    return () => {
      alive = false
    }
  }, [])

  const commit = useCallback((mutate: (current: TradeState) => TradeState) => {
    setState((current) => {
      const next = mutate(current)
      void saveTradeState(next)
      return next
    })
  }, [])

  const actions = useMemo<TradeActions>(
    () => ({
      createAccount: (name) => commit((s) => mutations.addAccount(s, name.trim(), nowIso())),
      removeAccount: (accountId) => commit((s) => mutations.deleteAccount(s, accountId)),
      createStock: (input) =>
        commit((s) =>
          mutations.addStock(s, {
            accountId: input.accountId,
            name: input.name.trim(),
            code: input.code.trim(),
            createdAt: nowIso(),
          }),
        ),
      editStock: (stock) => commit((s) => mutations.updateStock(s, stock)),
      removeStock: (stockId) => commit((s) => mutations.deleteStock(s, stockId)),
      createTransaction: (input) =>
        commit((s) => mutations.addTransaction(s, { ...input, createdAt: nowIso() })),
      editTransaction: (trade) => commit((s) => mutations.updateTransaction(s, trade)),
      removeTransaction: (transactionId) =>
        commit((s) => mutations.deleteTransaction(s, transactionId)),
      createTTrade: (input) =>
        commit((s) => mutations.addTTrade(s, { ...input, createdAt: nowIso() })),
      removeTTrade: (ttradeId) => commit((s) => mutations.deleteTTrade(s, ttradeId)),
      removeTTradesBySell: (sellId) => commit((s) => mutations.deleteTTradesBySell(s, sellId)),
      replaceState: (next) => commit(() => mutations.normalizeState(next)),
    }),
    [commit],
  )

  const value = useMemo(() => ({ state, ready, actions }), [state, ready, actions])

  return <TradeContext.Provider value={value}>{children}</TradeContext.Provider>
}

export function useTrade(): TradeContextValue {
  const value = useContext(TradeContext)
  if (!value) throw new Error('useTrade 必须在 TradeProvider 内使用')
  return value
}
