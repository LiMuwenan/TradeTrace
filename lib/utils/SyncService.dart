import 'dart:io';
import 'package:everything_tool/utils/DatabaseHelper.dart';
import 'package:everything_tool/utils/AppConfig.dart';
import 'package:everything_tool/utils/WebDavService.dart';

class SyncService {
  final DatabaseHelper _db = DatabaseHelper();
  late final AppConfig _config;
  late final WebDavService _webdav;
  bool _initialized = false;

  SyncService._();

  static final SyncService _instance = SyncService._();

  static SyncService get instance => _instance;

  Future<void> init() async {
    if (_initialized) return;
    _config = await AppConfig.getInstance();
    _webdav = WebDavService(_config);
    _initialized = true;
  }

  bool get isConfigured => _config.isConfigured;

  /// 上传本地数据库到云端
  Future<String> upload() async {
    if (!_config.isConfigured) {
      return '请先在设置中配置坚果云 WebDAV 信息';
    }

    try {
      final dbPath = await _db.getDbPath();
      final file = File(dbPath);
      if (!file.existsSync()) {
        return '本地数据库文件不存在';
      }

      final remoteId = _config.remoteDeviceId;
      final bytes = await file.readAsBytes();
      final key = 'EverythingTool/$remoteId/stock_trading.db';
      final ok = await _webdav.upload(key, bytes);

      return ok ? '上传成功' : '上传失败：${_webdav.lastError}';
    } catch (e) {
      return '上传失败：$e';
    }
  }

  /// 下载远程数据库并替换本地
  Future<String> download() async {
    if (!_config.isConfigured) {
      return '请先在设置中配置坚果云 WebDAV 信息';
    }

    final remoteId = _config.remoteDeviceId;
    if (remoteId.isEmpty) {
      return '请先在设置中填写远程设备 ID';
    }

    try {
      final key = 'EverythingTool/$remoteId/stock_trading.db';
      final bytes = await _webdav.download(key);
      if (bytes == null) {
        return '远程设备 $remoteId 没有上传过数据';
      }
      if (bytes.length < 100) {
        return '远程数据库文件异常';
      }

      // 关闭当前数据库连接
      await _db.closeDatabase();

      // 替换本地数据库文件
      final dbPath = await _db.getDbPath();
      final file = File(dbPath);
      await file.writeAsBytes(bytes);

      return '下载成功，数据已替换';
    } catch (e) {
      return '下载失败：$e';
    }
  }
}