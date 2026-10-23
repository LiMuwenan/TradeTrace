import AsyncStorage from '@react-native-async-storage/async-storage'

/** 坚果云 WebDAV 同步配置（仅保存在本机） */
export interface SyncConfig {
  webdavUrl: string
  username: string
  password: string
  /** 本设备 ID，作为云端目录名 */
  deviceId: string
  /** 另一台设备的 ID，下载时从该目录拉取 */
  remoteDeviceId: string
  lastSyncAt: string
}

export const DEFAULT_WEBDAV_URL = 'https://dav.jianguoyun.com/dav/'
export const SYNC_FOLDER = 'TradeTrace'
export const SYNC_FILE = 'tradetrace.json'

const STORAGE_KEY = 'tradetrace/webdav/v1'

/** 8 位十六进制设备 ID */
export function createDeviceId(): string {
  let id = ''
  while (id.length < 8) {
    id += Math.floor(Math.random() * 0x10000)
      .toString(16)
      .padStart(4, '0')
  }
  return id.slice(0, 8)
}

export function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim() || DEFAULT_WEBDAV_URL
  return trimmed.endsWith('/') ? trimmed : `${trimmed}/`
}

export function remotePath(deviceId: string): string {
  return `${SYNC_FOLDER}/${deviceId}/${SYNC_FILE}`
}

export function remoteUrl(config: SyncConfig, deviceId: string): string {
  return `${normalizeBaseUrl(config.webdavUrl)}${remotePath(deviceId)}`
}

export function isSyncConfigured(config: SyncConfig): boolean {
  return config.username.length > 0 && config.password.length > 0
}

export async function loadSyncConfig(): Promise<SyncConfig> {
  let stored: Partial<SyncConfig> = {}
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY)
    if (raw) stored = JSON.parse(raw) as Partial<SyncConfig>
  } catch {
    stored = {}
  }

  const config: SyncConfig = {
    webdavUrl: stored.webdavUrl ?? DEFAULT_WEBDAV_URL,
    username: stored.username ?? '',
    password: stored.password ?? '',
    deviceId: stored.deviceId ?? createDeviceId(),
    remoteDeviceId: stored.remoteDeviceId ?? '',
    lastSyncAt: stored.lastSyncAt ?? '',
  }
  // 首次运行生成设备 ID 并落盘（启用后不会再变）
  if (!stored.deviceId) await saveSyncConfig(config)
  return config
}

export async function saveSyncConfig(config: SyncConfig): Promise<void> {
  await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(config))
}
