import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:file_picker/file_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import 'dart:io';
import 'dart:convert';

import 'package:password/model/AccountItem.dart';
import 'package:password/widgets/AccountDialog.dart';
import 'package:password/widgets/AccountListItem.dart';
import 'package:password/utils/SharedPreferencesHelper.dart';

class AccountListPage extends StatefulWidget {
  @override
  _AccountListPageState createState() => _AccountListPageState();
}

class _AccountListPageState extends State<AccountListPage> {
  List<AccountItem> accounts = [];
  List<AccountItem> filteredAccounts = [];
  TextEditingController searchController = TextEditingController();
  final SharedPreferencesHelper _prefsHelper = SharedPreferencesHelper();

  @override
  void initState() {
    super.initState();
    _loadAccounts();
    searchController.addListener(() {
      _filterAccounts();
    });
  }

  Future<void> _loadAccounts() async {
    List<AccountItem> loadedAccounts = await _prefsHelper.getAccounts();
    setState(() {
      accounts = loadedAccounts;
      filteredAccounts = accounts;
    });
  }

  void _filterAccounts() {
    final query = searchController.text.toLowerCase();
    setState(() {
      filteredAccounts = accounts.where((account) {
        return account.appName.toLowerCase().contains(query) ||
            account.username.toLowerCase().contains(query);
      }).toList();
    });
  }

  void _addOrEditAccount({AccountItem? existingItem}) {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        String appName = existingItem?.appName ?? '';
        String username = existingItem?.username ?? '';
        String password = existingItem?.password ?? '';

        return AccountDialog(
          existingItem: existingItem,
          onSave: (newAppName, newUsername, newPassword) async {
            if (existingItem != null) {
              // 编辑现有项
              existingItem.appName = newAppName;
              existingItem.username = newUsername;
              existingItem.password = newPassword;
              await _prefsHelper.saveAccounts(accounts);
            } else {
              // 添加新项
              AccountItem newAccount = AccountItem(
                appName: newAppName,
                username: newUsername,
                password: newPassword,
              );
              accounts.add(newAccount);
              await _prefsHelper.saveAccounts(accounts);
            }
            _loadAccounts(); // 重新加载列表
          },
        );
      },
    );
  }

  void _deleteAccount(String id) async {
    accounts.removeWhere((account) => account.id == id);
    await _prefsHelper.saveAccounts(accounts);
    _loadAccounts(); // 重新加载列表
  }

  // 导出数据到JSON文件
  Future<void> _exportData() async {
    try {
      // 请求存储权限
      PermissionStatus status = await Permission.storage.request();
      if (!status.isGranted) {
        // 将账户列表转换为JSON
        final accountsJson = accounts.map((account) => account.toMap()).toList();
        final jsonString = jsonEncode(accountsJson);

        // 获取下载目录
        final String? downloadsDir = await FilePicker.platform.getDirectoryPath();
        if (downloadsDir == null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('无法访问存储目录')),
          );
          return;
        }

        // 创建文件名（带时间戳）
        final timestamp = DateFormat('yyyyMMdd_HHmmss').format(DateTime.now());
        final file = File('${downloadsDir}/account_backup_$timestamp.json');

        // 写入文件
        await file.writeAsString(jsonString);

        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('数据已导出到: ${file.path}')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('需要存储权限才能导出数据')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('导出失败: $e')),
      );
    }
  }

  // 从JSON文件导入数据
  Future<void> _importData() async {
    try {
      // 请求存储权限
      if (await Permission.storage.request().isGranted) {
        // 选择文件
        FilePickerResult? result = await FilePicker.platform.pickFiles(
          type: FileType.custom,
          allowedExtensions: ['json'],
        );

        if (result != null) {
          // 读取文件内容
          final file = File(result.files.single.path!);
          final jsonString = await file.readAsString();

          // 解析JSON
          final List<dynamic> jsonList = jsonDecode(jsonString);
          final List<AccountItem> importedAccounts = jsonList
              .map((item) => AccountItem.fromMap(item))
              .toList();

          // 确认导入对话框
          showDialog(
            context: context,
            builder: (BuildContext context) {
              return AlertDialog(
                title: Text('导入确认'),
                content: Text('将导入 ${importedAccounts.length} 个账号。这会覆盖当前所有数据，确定要继续吗？'),
                actions: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: Text('取消'),
                  ),
                  TextButton(
                    onPressed: () async {
                      Navigator.of(context).pop();

                      // 替换当前数据
                      setState(() {
                        accounts = importedAccounts;
                      });

                      // 保存到本地存储
                      await _prefsHelper.saveAccounts(accounts);
                      _loadAccounts();

                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('成功导入 ${importedAccounts.length} 个账号')),
                      );
                    },
                    child: Text('确定导入', style: TextStyle(color: Colors.blue)),
                  ),
                ],
              );
            },
          );
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('需要存储权限才能导入数据')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('导入失败: $e')),
      );
    }
  }

  // 合并导入数据（不覆盖现有数据）
  Future<void> _mergeData() async {
    try {
      // 请求存储权限
      if (!await Permission.storage.request().isGranted) {
        // 选择文件
        FilePickerResult? result = await FilePicker.platform.pickFiles(
          type: FileType.custom,
          allowedExtensions: ['json'],
        );

        if (result != null) {
          // 读取文件内容
          final file = File(result.files.single.path!);
          final jsonString = await file.readAsString();

          // 解析JSON
          final List<dynamic> jsonList = jsonDecode(jsonString);
          final List<AccountItem> importedAccounts = jsonList
              .map((item) => AccountItem.fromMap(item))
              .toList();

          // 过滤掉已存在的账号（基于ID）
          final newAccounts = importedAccounts.where(
                  (imported) => !accounts.any((existing) => existing.id == imported.id)
          ).toList();

          // 添加新账号
          accounts.addAll(newAccounts);

          // 保存到本地存储
          await _prefsHelper.saveAccounts(accounts);
          _loadAccounts();

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('成功合并 ${newAccounts.length} 个新账号')),
          );
        }
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('需要存储权限才能导入数据')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('导入失败: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('账号密码管理器'),
        elevation: 0,
        actions: [
          // 导入按钮
          PopupMenuButton(
            icon: Icon(Icons.more_vert),
            itemBuilder: (BuildContext context) => [
              PopupMenuItem(
                child: ListTile(
                  leading: Icon(Icons.import_export),
                  title: Text('导出数据'),
                  onTap: () {
                    Navigator.pop(context);
                    _exportData();
                  },
                ),
              ),
              PopupMenuItem(
                child: ListTile(
                  leading: Icon(Icons.file_download),
                  title: Text('导入数据（覆盖）'),
                  onTap: () {
                    Navigator.pop(context);
                    _importData();
                  },
                ),
              ),
              PopupMenuItem(
                child: ListTile(
                  leading: Icon(Icons.merge),
                  title: Text('导入数据（合并）'),
                  onTap: () {
                    Navigator.pop(context);
                    _mergeData();
                  },
                ),
              ),
            ],
          ),
          IconButton(
            icon: Icon(Icons.add),
            onPressed: () => _addOrEditAccount(),
          ),
        ],
      ),
      body: Column(
        children: [
          // 搜索框
          Container(
            padding: EdgeInsets.all(16),
            color: Colors.grey[100],
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black12,
                    blurRadius: 4,
                    offset: Offset(0, 2),
                  ),
                ],
              ),
              child: TextField(
                controller: searchController,
                decoration: InputDecoration(
                  hintText: '搜索应用或账号...',
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16),
                  prefixIcon: Icon(Icons.search, color: Colors.grey),
                ),
              ),
            ),
          ),
          // 数据列表
          Expanded(
            child: filteredAccounts.isEmpty
                ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.lock, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    '暂无账号数据',
                    style: TextStyle(fontSize: 18, color: Colors.grey),
                  ),
                  SizedBox(height: 8),
                  Text(
                    '点击右下角+按钮添加账号',
                    style: TextStyle(color: Colors.grey),
                  ),
                  SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _importData,
                    icon: Icon(Icons.file_download),
                    label: Text('从备份文件导入'),
                  ),
                ],
              ),
            )
                : ListView.builder(
              itemCount: filteredAccounts.length,
              itemBuilder: (context, index) {
                return AccountListItem(
                  account: filteredAccounts[index],
                  onEdit: () => _addOrEditAccount(existingItem: filteredAccounts[index]),
                  onDelete: () => _deleteAccount(filteredAccounts[index].id),
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _addOrEditAccount(),
        child: Icon(Icons.add),
        backgroundColor: Colors.blue,
      ),
    );
  }
}