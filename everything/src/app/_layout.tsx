import '@/global.css'

import { Stack } from 'expo-router'
import { StatusBar } from 'expo-status-bar'
import { SafeAreaProvider } from 'react-native-safe-area-context'

import { TradeProvider } from '@/data/trade-context'
import { colors } from '@/theme/tokens'

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <TradeProvider>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.bg },
          }}
        />
      </TradeProvider>
    </SafeAreaProvider>
  )
}
