import { useEffect, useState } from 'react'
import { StyleSheet, Text, View } from 'react-native'

import { Button, Card, ConfirmDialog, Field, Loading, Screen, TopBar } from '@/components/ui'
import { appendConflictLog } from '@/data/repository'
import { pullFromCloud, pushToCloud } from '@/data/sync'
import {
  DEFAULT_WEBDAV_URL,
  loadSyncConfig,
  normalizeBaseUrl,
  remotePath,
  saveSyncConfig,
} from '@/data/sync-config'
import type { SyncConfig } from '@/data/sync-config'
import { useTrade } from '@/data/trade-context'
import { colors, spacing, typography } from '@/theme/tokens'
import { nowIso } from '@/utils/format'
import { goBack } from '@/utils/navigation'

export default function SettingsScreen() {
  const { state, actions, ready } = useTrade()
  const [config, setConfig] = useState<SyncConfig | null>(null)
  const [url, setUrl] = useState(DEFAULT_WEBDAV_URL)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remoteDeviceId, setRemoteDeviceId] = useState('')
  const [busy, setBusy] = useState<'upload' | 'download' | null>(null)
  const [notice, setNotice] = useState('')
  const [noticeOk, setNoticeOk] = useState(true)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    let alive = true
    loadSyncConfig().then((loaded) => {
      if (!alive) return
      setConfig(loaded)
      setUrl(loaded.webdavUrl)
      setUsername(loaded.username)
      setPassword(loaded.password)
      setRemoteDeviceId(loaded.remoteDeviceId)
    })
    return () => {
      alive = false
    }
  }, [])

  function showNotice(message: string, ok: boolean) {
    setNotice(message)
    setNoticeOk(ok)
  }

  /** 保存当前表单，返回保存后的配置（校验失败返回 null） */
  async function persist(): Promise<SyncConfig | null> {
    if (!config) return null
    if (!username.trim() || !password.trim()) {
      showNotice('请填写坚果云账号与应用密码', false)
      return null
    }
    const next: SyncConfig = {
      ...config,
      webdavUrl: normalizeBaseUrl(url),
      username: username.trim(),
      password: password.trim(),
      remoteDeviceId: remoteDeviceId.trim(),
    }
    await saveSyncConfig(next)
    setConfig(next)
    setUrl(next.webdavUrl)
    return next
  }

  async function saveOnly() {
    const saved = await persist()
    if (saved) showNotice('配置已保存', true)
  }

  async function upload() {
    if (!ready) {
      showNotice('本机数据仍在加载，请稍候再同步', false)
      return
    }
    const saved = await persist()
    if (!saved) return
    setBusy('upload')
    const result = await pushToCloud(saved, state)
    if (result.ok) {
      const next = { ...saved, lastSyncAt: nowIso() }
      await saveSyncConfig(next)
      setConfig(next)
    }
    setBusy(null)
    showNotice(result.message, result.ok)
  }

  async function download() {
    setConfirming(false)
    if (!ready) {
      showNotice('本机数据仍在加载，请稍候再同步', false)
      return
    }
    const saved = await persist()
    if (!saved) return
    setBusy('download')
    const result = await pullFromCloud(saved, state, nowIso())
    if (result.ok && result.state) {
      actions.replaceState(result.state)
      await appendConflictLog(result.conflicts ?? [])
      const next = { ...saved, lastSyncAt: nowIso() }
      await saveSyncConfig(next)
      setConfig(next)
    }
    setBusy(null)
    showNotice(result.message, result.ok)
  }

  if (!config) {
    return (
      <Screen>
        <TopBar title="应用设置" onBack={goBack} />
        <Loading />
      </Screen>
    )
  }

  return (
    <Screen scroll>
      <TopBar title="应用设置" subtitle="坚果云同步" onBack={goBack} />

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>本设备</Text>
        <Text style={styles.deviceId}>{config.deviceId}</Text>
        <Text style={styles.hint}>
          把此 ID 填到另一台设备的「远程设备 ID」里，对方即可下载本机数据。
        </Text>
        <Text style={styles.hint}>云端文件：{remotePath(config.deviceId)}</Text>
      </Card>

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>坚果云 WebDAV</Text>
        <Text style={styles.hint}>两端填写同一个坚果云账号，使用「安全设置」里生成的应用密码。</Text>
        <Field
          label="WebDAV 地址"
          value={url}
          onChangeText={setUrl}
          placeholder={DEFAULT_WEBDAV_URL}
          autoCapitalize="none"
        />
        <Field
          label="坚果云账号"
          value={username}
          onChangeText={setUsername}
          placeholder="注册邮箱或手机号"
          autoCapitalize="none"
        />
        <Field
          label="应用密码"
          value={password}
          onChangeText={setPassword}
          placeholder="安全设置中生成的应用密码"
          secure
          autoCapitalize="none"
        />
        <Field
          label="远程设备 ID"
          value={remoteDeviceId}
          onChangeText={setRemoteDeviceId}
          placeholder="例如：a3f2c8b1"
          autoCapitalize="none"
          maxLength={8}
        />
        <Button label="保存配置" variant="secondary" onPress={saveOnly} />
      </Card>

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>同步</Text>
        <Text style={styles.hint}>
          {config.lastSyncAt ? `上次同步：${config.lastSyncAt.slice(0, 19).replace('T', ' ')}` : '尚未同步过'}
        </Text>
        <View style={styles.syncActions}>
          <View style={styles.syncButton}>
            <Button
              label={busy === 'upload' ? '上传中…' : '上传到云端'}
              onPress={upload}
              disabled={busy !== null || !ready}
            />
          </View>
          <View style={styles.syncButton}>
            <Button
              label={busy === 'download' ? '合并中…' : '合并下载'}
              variant="secondary"
              onPress={() => setConfirming(true)}
              disabled={busy !== null || !ready || !remoteDeviceId.trim()}
            />
          </View>
        </View>
        {notice ? (
          <Text style={[styles.notice, { color: noticeOk ? colors.inkSecondary : colors.profit }]}>
            {notice}
          </Text>
        ) : null}
      </Card>

      <Card muted style={styles.card}>
        <Text style={styles.cardTitle}>说明</Text>
        <Text style={styles.steps}>
          1. 坚果云官网登录后，在「安全设置」生成应用密码{'\n'}
          2. A 端填写账号与应用密码后点击「上传到云端」{'\n'}
          3. B 端填写同一账号，并在「远程设备 ID」填入 A 端 ID{'\n'}
          4. B 端点击「合并下载」，按修改时间合并双端数据，不会覆盖本机新增记录{'\n'}
          5. 同步文件为 JSON（{remotePath('{设备ID}')}），仅含交易数据，不含密码管理{'\n'}
          6. Web 端受浏览器跨域策略限制，同步可能失败；Android 端可正常使用
        </Text>
      </Card>

      <ConfirmDialog
        visible={confirming}
        title="合并下载"
        message={`将把远程设备 ${remoteDeviceId.trim() || '（未填写）'} 的数据与本机记录按修改时间合并，不会删除本机新增的记录。`}
        confirmLabel="合并下载"
        onConfirm={download}
        onCancel={() => setConfirming(false)}
      />
    </Screen>
  )
}

const styles = StyleSheet.create({
  card: { marginBottom: spacing.md },
  cardTitle: { ...typography.body, fontWeight: '600', color: colors.ink, marginBottom: spacing.sm },
  deviceId: {
    ...typography.number,
    fontSize: 22,
    fontWeight: '700',
    color: colors.accent,
    letterSpacing: 2,
  },
  hint: { ...typography.caption, color: colors.inkTertiary, marginTop: 4, lineHeight: 18 },
  syncActions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  syncButton: { flex: 1 },
  notice: { ...typography.caption, marginTop: spacing.md, lineHeight: 18 },
  steps: { ...typography.caption, color: colors.inkSecondary, lineHeight: 20 },
})
