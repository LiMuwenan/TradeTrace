import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:everything_tool/utils/AppConfig.dart';

class WebDavService {
  final AppConfig _config;

  WebDavService(this._config);

  String lastError = '';

  /// 构建完整的 WebDAV URL
  String _buildUrl(String key) {
    final base = _config.webdavUrl;
    return base.endsWith('/') ? '$base$key' : '$base/$key';
  }

  /// 构建 Basic Auth 请求头
  Map<String, String> _authHeaders() {
    final credentials = base64Encode(
      utf8.encode('${_config.username}:${_config.password}'),
    );
    return {'Authorization': 'Basic $credentials'};
  }

  /// 上传文件到坚果云 WebDAV
  Future<bool> upload(String key, Uint8List data) async {
    try {
      final uri = Uri.parse(_buildUrl(key));
      final response = await http.put(
        uri,
        headers: _authHeaders(),
        body: data,
      );

      if (response.statusCode == 200 || response.statusCode == 201 || response.statusCode == 204) {
        return true;
      }
      lastError = 'HTTP ${response.statusCode}: ${response.body}';
      return false;
    } catch (e) {
      lastError = e.toString();
      return false;
    }
  }

  /// 从坚果云 WebDAV 下载二进制文件
  Future<Uint8List?> download(String key) async {
    try {
      final uri = Uri.parse(_buildUrl(key));
      final response = await http.get(uri, headers: _authHeaders());

      if (response.statusCode == 200) {
        return response.bodyBytes;
      }
      return null;
    } catch (e) {
      return null;
    }
  }
}