import { Platform } from 'react-native'

/** 设计变量：暖白底 + 墨色文字 + A股红涨绿跌语义 */
export const colors = {
  bg: '#F4F2EC',
  surface: '#FFFFFF',
  surfaceMuted: '#EDEAE2',
  ink: '#16181B',
  inkSecondary: '#5B6068',
  inkTertiary: '#8E9299',
  line: '#E3DFD4',
  accent: '#123B66',
  accentSoft: '#E7EDF5',
  profit: '#C63A46',
  profitSoft: '#FBECEE',
  loss: '#17795C',
  lossSoft: '#E8F3EE',
  warning: '#B4741F',
  overlay: 'rgba(22, 24, 27, 0.45)',
} as const

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const

export const radius = {
  sm: 8,
  md: 12,
  lg: 18,
  xl: 24,
  pill: 999,
} as const

export const typography = {
  eyebrow: { fontSize: 11, letterSpacing: 1.6, fontWeight: '600' as const },
  hero: { fontSize: 34, fontWeight: '700' as const, letterSpacing: -0.8 },
  title: { fontSize: 22, fontWeight: '700' as const, letterSpacing: -0.4 },
  section: { fontSize: 13, fontWeight: '600' as const, letterSpacing: 0.4 },
  body: { fontSize: 15, fontWeight: '400' as const },
  label: { fontSize: 12, fontWeight: '500' as const },
  caption: { fontSize: 12, fontWeight: '400' as const },
  number: {
    fontVariant: ['tabular-nums'] as const,
    fontFamily: Platform.select({ web: 'ui-monospace, SFMono-Regular, Menlo, monospace', default: 'monospace' }),
  },
}

export const layout = {
  maxWidth: 760,
  sheetWidth: 520,
} as const
