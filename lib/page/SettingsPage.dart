import 'package:flutter/material.dart';
import 'package:everything_tool/utils/AppConfig.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _webdavUrlController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _remoteDeviceIdController = TextEditingController();
  bool _obscurePassword = true;
  bool _isLoading = true;
  String _deviceId = '';

  @override
  void initState() {
    super.initState();
    _loadConfig();
  }

  Future<void> _loadConfig() async {
    final config = await AppConfig.getInstance();
    setState(() {
      _webdavUrlController.text = config.webdavUrl;
      _usernameController.text = config.username;
      _passwordController.text = config.password;
      _remoteDeviceIdController.text = config.remoteDeviceId;
      _deviceId = config.deviceId;
      _isLoading = false;
    });
  }

  Future<void> _saveConfig() async {
    final webdavUrl = _webdavUrlController.text.trim();
    final username = _usernameController.text.trim();
    final password = _passwordController.text.trim();
    final remoteDeviceId = _remoteDeviceIdController.text.trim();

    if (username.isEmpty || password.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('请填写坚果云账号和密码')),
        );
      }
      return;
    }

    if (remoteDeviceId.isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('请填写远程设备 ID（可在另一台设备的设置页查看）')),
        );
      }
      return;
    }

    final config = await AppConfig.getInstance();
    await config.saveConfig(
      webdavUrl: webdavUrl.isEmpty ? 'https://dav.jianguoyun.com/dav/' : webdavUrl,
      username: username,
      password: password,
      remoteDeviceId: remoteDeviceId,
    );

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('配置已保存')),
      );
    }
  }

  @override
  void dispose() {
    _webdavUrlController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _remoteDeviceIdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('应用设置'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 设备信息
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '设备信息',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      '本设备 ID（将此 ID 填入另一台设备的"远程设备 ID"中）',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            _deviceId,
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // 远程设备 ID
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '远程设备 ID',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      '填写另一台设备的 ID，同步时将拉取该设备的数据',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _remoteDeviceIdController,
                      decoration: const InputDecoration(
                        labelText: '远程设备 ID',
                        hintText: '例如：a3f2c8b1',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // 坚果云 WebDAV 配置
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '坚果云 WebDAV 配置',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      '两端需要配置相同的坚果云账号',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _webdavUrlController,
                      decoration: const InputDecoration(
                        labelText: 'WebDAV 地址',
                        hintText: 'https://dav.jianguoyun.com/dav/',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _usernameController,
                      decoration: const InputDecoration(
                        labelText: '坚果云账号',
                        hintText: '注册邮箱或手机号',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      decoration: InputDecoration(
                        labelText: '应用密码',
                        hintText: '在坚果云安全设置中生成的应用密码',
                        border: const OutlineInputBorder(),
                        isDense: true,
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword ? Icons.visibility_off : Icons.visibility,
                          ),
                          onPressed: () {
                            setState(() {
                              _obscurePassword = !_obscurePassword;
                            });
                          },
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _saveConfig,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        child: const Text('保存配置'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            // 同步说明
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      '同步说明',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      '1. 在坚果云官网登录后，进入"安全设置"生成"应用密码"\n'
                      '2. 在两端设置页中配置相同的坚果云账号和应用密码\n'
                      '3. 在 A 端设置页查看"本设备 ID"\n'
                      '4. 在 B 端设置页的"远程设备 ID"中填入 A 端的 ID\n'
                      '5. 在 B 端点击首页同步按钮，即可拉取 A 端数据\n'
                      '6. 同步会直接上传 .db 文件，并在另一端下载替换\n'
                      '7. 同步包含：股票账户、交易记录、做T关联、密码管理 全部数据',
                      style: TextStyle(fontSize: 13, color: Colors.grey, height: 1.6),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}