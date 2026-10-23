import type { ReactNode } from 'react'
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import type { StyleProp, TextStyle, ViewStyle } from 'react-native'
import { SafeAreaView } from 'react-native-safe-area-context'

import { colors, layout, radius, spacing, typography } from '@/theme/tokens'
import { formatSigned, formatNumber } from '@/utils/format'

/* ---------------- 基础布局 ---------------- */

export function Screen({
  children,
  scroll = false,
  fab,
}: {
  children: ReactNode
  scroll?: boolean
  fab?: ReactNode
}) {
  const content = (
    <View style={styles.page}>
      <View style={styles.pageInner}>{children}</View>
    </View>
  )
  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {content}
        </ScrollView>
      ) : (
        <View style={styles.flex}>{content}</View>
      )}
      {fab ? (
        <View style={styles.fabLayer} pointerEvents="box-none">
          {fab}
        </View>
      ) : null}
    </SafeAreaView>
  )
}

export function TopBar({
  title,
  subtitle,
  onBack,
  right,
}: {
  title: string
  subtitle?: string
  onBack?: () => void
  right?: ReactNode
}) {
  return (
    <View style={styles.topBar}>
      <View style={styles.topBarSide}>
        {onBack ? <IconButton glyph="‹" label="返回" onPress={onBack} /> : null}
      </View>
      <View style={styles.topBarTitle}>
        <Text style={styles.topBarTitleText} numberOfLines={1}>
          {title}
        </Text>
        {subtitle ? <Text style={styles.topBarSubtitle}>{subtitle}</Text> : null}
      </View>
      <View style={[styles.topBarSide, styles.topBarSideRight]}>{right}</View>
    </View>
  )
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <View style={styles.sectionTitleRow}>
      <Text style={styles.sectionTitle}>{children}</Text>
      {right}
    </View>
  )
}

export function Card({
  children,
  style,
  muted = false,
}: {
  children: ReactNode
  style?: StyleProp<ViewStyle>
  muted?: boolean
}) {
  return <View style={[styles.card, muted && styles.cardMuted, style]}>{children}</View>
}

export function Divider() {
  return <View style={styles.divider} />
}

/* ---------------- 文本 ---------------- */

export function Eyebrow({ children }: { children: ReactNode }) {
  return <Text style={styles.eyebrow}>{children}</Text>
}

export function HeroNumber({
  value,
  digits = 2,
  size = 'hero',
}: {
  value: number
  digits?: number
  size?: 'hero' | 'title'
}) {
  const tone = value > 0 ? colors.profit : value < 0 ? colors.loss : colors.ink
  return (
    <Text
      style={[
        size === 'hero' ? styles.heroNumber : styles.titleNumber,
        typography.number,
        { color: tone },
      ]}
    >
      {formatSigned(value, digits)}
    </Text>
  )
}

export function Money({
  value,
  digits = 2,
  signed = true,
  style,
  muted = false,
}: {
  value: number
  digits?: number
  signed?: boolean
  style?: StyleProp<TextStyle>
  muted?: boolean
}) {
  const tone = muted
    ? colors.inkSecondary
    : value > 0
      ? colors.profit
      : value < 0
        ? colors.loss
        : colors.ink
  return (
    <Text style={[styles.money, typography.number, { color: tone }, style]}>
      {signed ? formatSigned(value, digits) : formatNumber(value, digits)}
    </Text>
  )
}

export function Pill({
  label,
  tone = 'neutral',
}: {
  label: string
  tone?: 'buy' | 'sell' | 'dividend' | 'neutral'
}) {
  const palette = {
    buy: { bg: colors.profitSoft, fg: colors.profit },
    sell: { bg: colors.lossSoft, fg: colors.loss },
    dividend: { bg: colors.accentSoft, fg: colors.accent },
    neutral: { bg: colors.surfaceMuted, fg: colors.inkSecondary },
  }[tone]
  return (
    <View style={[styles.pill, { backgroundColor: palette.bg }]}>
      <Text style={[styles.pillText, { color: palette.fg }]}>{label}</Text>
    </View>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {description ? <Text style={styles.emptyDesc}>{description}</Text> : null}
      {action ? <View style={styles.emptyAction}>{action}</View> : null}
    </View>
  )
}

export function Loading() {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.accent} />
    </View>
  )
}

/* ---------------- 交互 ---------------- */

export function Button({
  label,
  onPress,
  variant = 'primary',
  disabled = false,
  small = false,
  style,
}: {
  label: string
  onPress: () => void
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  disabled?: boolean
  small?: boolean
  style?: StyleProp<ViewStyle>
}) {
  const palette = {
    primary: { bg: colors.accent, fg: colors.surface, border: colors.accent },
    secondary: { bg: colors.surface, fg: colors.ink, border: colors.line },
    ghost: { bg: 'transparent', fg: colors.inkSecondary, border: 'transparent' },
    danger: { bg: colors.profitSoft, fg: colors.profit, border: colors.profitSoft },
  }[variant]
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        small && styles.buttonSmall,
        {
          backgroundColor: palette.bg,
          borderColor: palette.border,
          opacity: disabled ? 0.45 : pressed ? 0.75 : 1,
        },
        style,
      ]}
    >
      <Text style={[styles.buttonText, small && styles.buttonTextSmall, { color: palette.fg }]}>
        {label}
      </Text>
    </Pressable>
  )
}

export function IconButton({
  glyph,
  label,
  onPress,
  danger = false,
}: {
  glyph: string
  label: string
  onPress: () => void
  danger?: boolean
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      onPress={onPress}
      hitSlop={8}
      style={({ pressed }) => [styles.iconButton, pressed && { opacity: 0.5 }]}
    >
      <Text style={[styles.iconGlyph, danger && { color: colors.profit }]}>{glyph}</Text>
    </Pressable>
  )
}

export function Fab({ onPress, label = '新增' }: { onPress: () => void; label?: string }) {
  return (
    <Pressable
      accessibilityLabel={label}
      onPress={onPress}
      style={({ pressed }) => [styles.fab, pressed && { opacity: 0.85 }]}
    >
      <Text style={styles.fabPlus}>+</Text>
    </Pressable>
  )
}

export function RowButton({
  children,
  onPress,
  style,
}: {
  children: ReactNode
  onPress: () => void
  style?: StyleProp<ViewStyle>
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.rowButton, pressed && styles.rowButtonPressed, style]}
    >
      {children}
    </Pressable>
  )
}

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType = 'default',
  autoFocus = false,
  error,
  maxLength,
}: {
  label: string
  value: string
  onChangeText: (text: string) => void
  placeholder?: string
  keyboardType?: 'default' | 'numeric' | 'decimal-pad'
  autoFocus?: boolean
  error?: string
  maxLength?: number
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.inkTertiary}
        keyboardType={keyboardType === 'decimal-pad' ? 'decimal-pad' : keyboardType}
        autoFocus={autoFocus}
        maxLength={maxLength}
        style={[styles.input, !!error && styles.inputError]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  )
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (value: T) => void
}) {
  return (
    <View style={styles.segmented}>
      {options.map((option) => {
        const active = option.value === value
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            style={[styles.segment, active && styles.segmentActive]}
          >
            <Text style={[styles.segmentText, active && styles.segmentTextActive]}>
              {option.label}
            </Text>
          </Pressable>
        )
      })}
    </View>
  )
}

export function SwitchRow({
  label,
  description,
  value,
  onToggle,
}: {
  label: string
  description?: string
  value: boolean
  onToggle: (value: boolean) => void
}) {
  return (
    <Pressable onPress={() => onToggle(!value)} style={styles.switchRow}>
      <View style={styles.flex}>
        <Text style={styles.switchLabel}>{label}</Text>
        {description ? <Text style={styles.switchDesc}>{description}</Text> : null}
      </View>
      <View style={[styles.switchTrack, value && styles.switchTrackOn]}>
        <View style={[styles.switchKnob, value && styles.switchKnobOn]} />
      </View>
    </Pressable>
  )
}

/* ---------------- 弹层 ---------------- */

export function Sheet({
  visible,
  title,
  onClose,
  children,
  footer,
}: {
  visible: boolean
  title: string
  onClose?: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.modalRoot}
      >
        <Pressable style={styles.backdrop} onPress={onClose} />
        <View style={styles.sheet}>
          <View style={styles.sheetHeader}>
            <Text style={styles.sheetTitle}>{title}</Text>
            {onClose ? <IconButton glyph="×" label="关闭" onPress={onClose} /> : null}
          </View>
          <ScrollView
            style={styles.sheetBody}
            contentContainerStyle={styles.sheetBodyContent}
            keyboardShouldPersistTaps="handled"
          >
            {children}
          </ScrollView>
          {footer ? <View style={styles.sheetFooter}>{footer}</View> : null}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  )
}

export interface ActionItem {
  label: string
  onPress: () => void
  danger?: boolean
}

export function ActionSheet({
  visible,
  title,
  items,
  onClose,
}: {
  visible: boolean
  title?: string
  items: ActionItem[]
  onClose: () => void
}) {
  return (
    <Sheet visible={visible} title={title ?? '操作'} onClose={onClose}>
      <View style={styles.actionList}>
        {items.map((item) => (
          <Pressable
            key={item.label}
            onPress={() => {
              onClose()
              item.onPress()
            }}
            style={({ pressed }) => [styles.actionItem, pressed && styles.actionItemPressed]}
          >
            <Text style={[styles.actionText, item.danger && { color: colors.profit }]}>
              {item.label}
            </Text>
          </Pressable>
        ))}
      </View>
    </Sheet>
  )
}

export function ConfirmDialog({
  visible,
  title,
  message,
  confirmLabel = '删除',
  onConfirm,
  onCancel,
}: {
  visible: boolean
  title: string
  message: string
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.modalRoot}>
        <Pressable style={styles.backdrop} onPress={onCancel} />
        <View style={styles.confirmCard}>
          <Text style={styles.confirmTitle}>{title}</Text>
          <Text style={styles.confirmMessage}>{message}</Text>
          <View style={styles.confirmActions}>
            <Button label="取消" variant="secondary" onPress={onCancel} small />
            <Button
              label={confirmLabel}
              variant="danger"
              onPress={() => {
                onCancel()
                onConfirm()
              }}
              small
            />
          </View>
        </View>
      </View>
    </Modal>
  )
}

/* ---------------- 样式 ---------------- */

const styles = StyleSheet.create({
  flex: { flex: 1 },
  safe: { flex: 1, backgroundColor: colors.bg },
  scrollContent: { flexGrow: 1 },
  page: { flex: 1, paddingHorizontal: spacing.lg },
  pageInner: {
    flex: 1,
    width: '100%',
    maxWidth: layout.maxWidth,
    alignSelf: 'center',
    paddingBottom: 96,
  },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    minHeight: 56,
  },
  topBarSide: { width: 56, flexDirection: 'row', alignItems: 'center' },
  topBarSideRight: { justifyContent: 'flex-end' },
  topBarTitle: { flex: 1, alignItems: 'center' },
  topBarTitleText: { ...typography.title, color: colors.ink },
  topBarSubtitle: { ...typography.caption, color: colors.inkTertiary, marginTop: 2 },
  iconButton: {
    minWidth: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconGlyph: {
    fontSize: 24,
    lineHeight: 26,
    color: colors.inkSecondary,
    fontWeight: '500',
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  sectionTitle: { ...typography.section, color: colors.inkSecondary },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: spacing.lg,
  },
  cardMuted: { backgroundColor: colors.surfaceMuted, borderColor: colors.surfaceMuted },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: spacing.md },
  eyebrow: {
    ...typography.eyebrow,
    color: colors.inkTertiary,
    textTransform: 'uppercase',
  },
  heroNumber: { fontSize: 34, fontWeight: '700', letterSpacing: -0.8 },
  titleNumber: { fontSize: 22, fontWeight: '700' },
  money: { fontSize: 15, fontWeight: '600' },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
  },
  pillText: { fontSize: 11, fontWeight: '600' },
  empty: {
    alignItems: 'center',
    paddingVertical: spacing.xxxl,
    paddingHorizontal: spacing.lg,
  },
  emptyTitle: { ...typography.body, color: colors.ink, fontWeight: '600' },
  emptyDesc: {
    ...typography.caption,
    color: colors.inkTertiary,
    marginTop: spacing.sm,
    textAlign: 'center',
    lineHeight: 18,
  },
  emptyAction: { marginTop: spacing.lg },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xxl },
  button: {
    minHeight: 46,
    borderRadius: radius.md,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonSmall: { minHeight: 36, paddingHorizontal: spacing.md, borderRadius: radius.sm },
  buttonText: { fontSize: 15, fontWeight: '600' },
  buttonTextSmall: { fontSize: 13 },
  fabLayer: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 },
  fab: {
    position: 'absolute',
    right: spacing.xl,
    bottom: spacing.xl,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 4,
    shadowColor: '#000000',
    shadowOpacity: 0.18,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  fabPlus: { color: colors.surface, fontSize: 30, lineHeight: 32, fontWeight: '300' },
  rowButton: { borderRadius: radius.lg },
  rowButtonPressed: { opacity: 0.7 },
  field: { marginBottom: spacing.md },
  fieldLabel: {
    ...typography.label,
    color: colors.inkSecondary,
    marginBottom: 6,
  },
  input: {
    minHeight: 44,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.surface,
    color: colors.ink,
    fontSize: 15,
  },
  inputError: { borderColor: colors.profit },
  fieldError: { ...typography.caption, color: colors.profit, marginTop: 4 },
  segmented: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceMuted,
    borderRadius: radius.md,
    padding: 3,
    gap: 3,
  },
  segment: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.sm,
    alignItems: 'center',
  },
  segmentActive: { backgroundColor: colors.surface },
  segmentText: { fontSize: 13, fontWeight: '500', color: colors.inkSecondary },
  segmentTextActive: { color: colors.ink, fontWeight: '600' },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },
  switchLabel: { ...typography.body, color: colors.ink },
  switchDesc: { ...typography.caption, color: colors.inkTertiary, marginTop: 2 },
  switchTrack: {
    width: 44,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.surfaceMuted,
    padding: 3,
  },
  switchTrackOn: { backgroundColor: colors.accent },
  switchKnob: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.surface,
  },
  switchKnobOn: { transform: [{ translateX: 18 }] },
  modalRoot: {
    flex: 1,
    justifyContent: Platform.OS === 'web' ? 'center' : 'flex-end',
    alignItems: 'center',
  },
  backdrop: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: colors.overlay,
  },
  sheet: {
    width: '100%',
    maxWidth: layout.sheetWidth,
    maxHeight: Platform.OS === 'web' ? '84%' : '88%',
    backgroundColor: colors.bg,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    borderBottomLeftRadius: Platform.OS === 'web' ? radius.xl : 0,
    borderBottomRightRadius: Platform.OS === 'web' ? radius.xl : 0,
    overflow: 'hidden',
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  sheetTitle: { ...typography.title, color: colors.ink },
  sheetBody: { flexGrow: 0 },
  sheetBodyContent: { paddingHorizontal: spacing.lg, paddingVertical: spacing.md },
  sheetFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.md,
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  actionList: { gap: spacing.xs, paddingBottom: spacing.md },
  actionItem: { paddingVertical: spacing.md, paddingHorizontal: spacing.sm, borderRadius: radius.md },
  actionItemPressed: { backgroundColor: colors.surfaceMuted },
  actionText: { ...typography.body, color: colors.ink },
  confirmCard: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.xl,
    marginHorizontal: spacing.lg,
  },
  confirmTitle: { ...typography.title, color: colors.ink },
  confirmMessage: {
    ...typography.body,
    color: colors.inkSecondary,
    lineHeight: 22,
    marginTop: spacing.sm,
  },
  confirmActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: spacing.md,
    marginTop: spacing.xl,
  },
})
