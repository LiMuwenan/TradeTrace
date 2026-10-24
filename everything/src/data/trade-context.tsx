import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { loadState, saveState } from './repository'
import * as mutations from './state'
import { createEmptyState } from './types'
import type { Stock, TradeState, TransactionInput, TransactionTrade, TTrade } from './types'
import { nowIso } from '@/utils/format'

interface TradeActions {
  createAccount: (name: string) => void
  removeAccount: (accountId: string) => void
  createStock: (input: Pick<Stock, 'accountId' | 'name' | 'code'>) => void
  editStock: (stock: Stock) => void
  removeStock: (stockId: string) => void
  createTransaction: (input: TransactionInput) => void
  editTransaction: (trade: TransactionTrade) => void
  removeTransaction: (transactionId: string) => void
  createTTrade: (input: Pick<TTrade, 'buyTransactionId' | 'sellTransactionId' | 'shares'>) => void
  removeTTrade: (ttradeId: string) => void
  removeTTradesBySell: (sellId: string) => void
  /** 用合并后的状态整体替换本机数据（坚果云合并下载） */
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
    loadState().then((loaded) => {
      if (!alive) return
      setState(loaded)
      setReady(true)
    })
    return () => {
      alive = false
    }
  }, [])

  const commit = useCallback((mutate: (current: TradeState, now: string) => TradeState) => {
    setState((current) => {
      const next = mutate(current, nowIso())
      void saveState(next)
      return next
    })
  }, [])

  const actions = useMemo<TradeActions>(
    () => ({
      createAccount: (name) => commit((s, now) => mutations.addAccount(s, name.trim(), now)),
      removeAccount: (accountId) => commit((s, now) => mutations.deleteAccount(s, accountId, now)),
      createStock: (input) =>
        commit((s, now) =>
          mutations.addStock(
            s,
            { accountId: input.accountId, name: input.name.trim(), code: input.code.trim() },
            now,
          ),
        ),
      editStock: (stock) => commit((s, now) => mutations.updateStock(s, stock, now)),
      removeStock: (stockId) => commit((s, now) => mutations.deleteStock(s, stockId, now)),
      createTransaction: (input) => commit((s, now) => mutations.addTransaction(s, input, now)),
      editTransaction: (trade) => commit((s, now) => mutations.updateTransaction(s, trade, now)),
      removeTransaction: (transactionId) =>
        commit((s, now) => mutations.deleteTransaction(s, transactionId, now)),
      createTTrade: (input) => commit((s, now) => mutations.addTTrade(s, input, now)),
      removeTTrade: (ttradeId) => commit((s, now) => mutations.deleteTTrade(s, ttradeId, now)),
      removeTTradesBySell: (sellId) =>
        commit((s, now) => mutations.deleteTTradesBySell(s, sellId, now)),
      replaceState: (next) => {
        setState(next)
        void saveState(next)
      },
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
