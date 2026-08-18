import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

class AppConfig {
  static const _keyWebdavUrl = 'webdav_url';
  static const _keyUsername = 'webdav_username';
  static const _keyPassword = 'webdav_password';
  static const _keyDeviceId = 'device_id';
  static const _keyLastSync = 'last_sync_timestamp';
  static const _keyRemoteDeviceId = 'remote_device_id';

  static AppConfig? _instance;
  late SharedPreferences _prefs;

  AppConfig._();

  static Future<AppConfig> getInstance() async {
    if (_instance == null) {
      _instance = AppConfig._();
      _instance!._prefs = await SharedPreferences.getInstance();
    }
    return _instance!;
  }

  // ========== 坚果云 WebDAV 配置 ==========

  String get webdavUrl =>
      _prefs.getString(_keyWebdavUrl) ?? 'https://dav.jianguoyun.com/dav/';

  set webdavUrl(String v) => _prefs.setString(_keyWebdavUrl, v);

  String get username => _prefs.getString(_keyUsername) ?? '';
  set username(String v) => _prefs.setString(_keyUsername, v);

  String get password => _prefs.getString(_keyPassword) ?? '';
  set password(String v) => _prefs.setString(_keyPassword, v);

  bool get isConfigured =>
      username.isNotEmpty && password.isNotEmpty;

  /// 保存坚果云 WebDAV 配置
  Future<void> saveConfig({
    required String webdavUrl,
    required String username,
    required String password,
    required String remoteDeviceId,
  }) async {
    await _prefs.setString(_keyWebdavUrl, webdavUrl);
    await _prefs.setString(_keyUsername, username);
    await _prefs.setString(_keyPassword, password);
    await _prefs.setString(_keyRemoteDeviceId, remoteDeviceId);
  }

  // ========== 设备 ID ==========

  String get deviceId {
    String? id = _prefs.getString(_keyDeviceId);
    if (id == null || id.isEmpty) {
      id = const Uuid().v4().substring(0, 8);
      _prefs.setString(_keyDeviceId, id);
    }
    return id;
  }

  // ========== 远程设备 ID ==========

  String get remoteDeviceId => _prefs.getString(_keyRemoteDeviceId) ?? '';
  set remoteDeviceId(String v) => _prefs.setString(_keyRemoteDeviceId, v);

  // ========== 同步时间戳 ==========

  String get lastSyncTimestamp => _prefs.getString(_keyLastSync) ?? '';
  set lastSyncTimestamp(String v) => _prefs.setString(_keyLastSync, v);
}