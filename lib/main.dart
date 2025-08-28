import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'package:intl/intl.dart';

void main() {
  runApp(AccountManagerApp());
}

class AccountManagerApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '账号密码管理器',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: AccountListPage(),
    );
  }
}

class AccountItem {
  String id;
  String appName;
  String username;
  String password;
  DateTime createdAt;

  AccountItem({
    required this.appName,
    required this.username,
    required this.password,
    DateTime? createdAt,
    String? id,
  })  : id = id ?? DateTime.now().millisecondsSinceEpoch.toString(),
        createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'appName': appName,
      'username': username,
      'password': password,
      'createdAt': createdAt.toIso8601String(),
    };
  }

  factory AccountItem.fromMap(Map<String, dynamic> map) {
    return AccountItem(
      id: map['id'],
      appName: map['appName'],
      username: map['username'],
      password: map['password'],
      createdAt: DateTime.parse(map['createdAt']),
    );
  }
}

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('账号密码管理器'),
        elevation: 0,
        actions: [
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
            child: ListView.builder(
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

class AccountListItem extends StatefulWidget {
  final AccountItem account;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  const AccountListItem({
    required this.account,
    required this.onEdit,
    required this.onDelete,
  });

  @override
  _AccountListItemState createState() => _AccountListItemState();
}

class _AccountListItemState extends State<AccountListItem> {
  bool _isExpanded = false;
  bool _showPassword = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: EdgeInsets.symmetric(vertical: 4, horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        boxShadow: [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 2,
            offset: Offset(0, 1),
          ),
        ],
      ),
      child: ExpansionTile(
        leading: CircleAvatar(
          backgroundColor: Colors.blue[100],
          child: Text(
            widget.account.appName.isNotEmpty ? widget.account.appName[0] : '?',
            style: TextStyle(color: Colors.blue[800]),
          ),
        ),
        title: Text(
          widget.account.appName,
          style: TextStyle(fontWeight: FontWeight.w500),
        ),
        subtitle: Text(
          widget.account.username,
          style: TextStyle(color: Colors.grey),
        ),
        trailing: Icon(
          _isExpanded ? Icons.expand_less : Icons.expand_more,
          color: Colors.grey,
        ),
        onExpansionChanged: (expanded) {
          setState(() {
            _isExpanded = expanded;
          });
        },
        children: [
          Divider(height: 1),
          Padding(
            padding: EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 账号信息
                _buildDetailRow('应用名称', widget.account.appName),
                SizedBox(height: 12),
                _buildDetailRow('用户名', widget.account.username),
                SizedBox(height: 12),
                // 密码信息
                Row(
                  children: [
                    Text(
                      '密码: ',
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: Colors.grey[700],
                      ),
                    ),
                    Expanded(
                      child: Text(
                        _showPassword ? widget.account.password : '••••••••',
                        style: TextStyle(fontFamily: _showPassword ? null : 'monospace'),
                      ),
                    ),
                    IconButton(
                      icon: Icon(
                        _showPassword ? Icons.visibility_off : Icons.visibility,
                        color: Colors.blue,
                      ),
                      onPressed: () {
                        setState(() {
                          _showPassword = !_showPassword;
                        });
                      },
                    ),
                  ],
                ),
                SizedBox(height: 12),
                _buildDetailRow(
                    '创建日期',
                    DateFormat('yyyy-MM-dd HH:mm').format(widget.account.createdAt)
                ),
                SizedBox(height: 16),
                // 操作按钮
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: widget.onEdit,
                      child: Text('编辑', style: TextStyle(color: Colors.blue)),
                    ),
                    SizedBox(width: 8),
                    TextButton(
                      onPressed: () {
                        // 确认删除对话框
                        showDialog(
                          context: context,
                          builder: (BuildContext context) {
                            return AlertDialog(
                              title: Text('确认删除'),
                              content: Text('确定要删除${widget.account.appName}的账号信息吗？'),
                              actions: [
                                TextButton(
                                  onPressed: () => Navigator.of(context).pop(),
                                  child: Text('取消'),
                                ),
                                TextButton(
                                  onPressed: () {
                                    Navigator.of(context).pop();
                                    widget.onDelete();
                                  },
                                  child: Text('删除', style: TextStyle(color: Colors.red)),
                                ),
                              ],
                            );
                          },
                        );
                      },
                      child: Text('删除', style: TextStyle(color: Colors.red)),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '$label: ',
          style: TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.grey[700],
          ),
        ),
        Expanded(
          child: Text(value),
        ),
      ],
    );
  }
}

class AccountDialog extends StatefulWidget {
  final AccountItem? existingItem;
  final Function(String, String, String) onSave;

  const AccountDialog({
    this.existingItem,
    required this.onSave,
  });

  @override
  _AccountDialogState createState() => _AccountDialogState();
}

class _AccountDialogState extends State<AccountDialog> {
  final _formKey = GlobalKey<FormState>();
  late TextEditingController _appNameController;
  late TextEditingController _usernameController;
  late TextEditingController _passwordController;

  @override
  void initState() {
    super.initState();
    _appNameController = TextEditingController(text: widget.existingItem?.appName ?? '');
    _usernameController = TextEditingController(text: widget.existingItem?.username ?? '');
    _passwordController = TextEditingController(text: widget.existingItem?.password ?? '');
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.existingItem != null ? '编辑账号' : '添加新账号',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              SizedBox(height: 16),
              TextFormField(
                controller: _appNameController,
                decoration: InputDecoration(
                  labelText: '应用/网站名称',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return '请输入应用或网站名称';
                  }
                  return null;
                },
              ),
              SizedBox(height: 16),
              TextFormField(
                controller: _usernameController,
                decoration: InputDecoration(
                  labelText: '用户名/账号',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return '请输入用户名或账号';
                  }
                  return null;
                },
              ),
              SizedBox(height: 16),
              TextFormField(
                controller: _passwordController,
                decoration: InputDecoration(
                  labelText: '密码',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return '请输入密码';
                  }
                  return null;
                },
                obscureText: true,
              ),
              SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: Text('取消'),
                  ),
                  SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: () {
                      if (_formKey.currentState!.validate()) {
                        widget.onSave(
                          _appNameController.text,
                          _usernameController.text,
                          _passwordController.text,
                        );
                        Navigator.of(context).pop();
                      }
                    },
                    child: Text('保存'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SharedPreferencesHelper {
  static const String _accountsKey = 'saved_accounts';

  Future<void> saveAccounts(List<AccountItem> accounts) async {
    final prefs = await SharedPreferences.getInstance();
    final accountsJson = accounts.map((account) => account.toMap()).toList();
    await prefs.setString(_accountsKey, json.encode(accountsJson));
  }

  Future<List<AccountItem>> getAccounts() async {
    final prefs = await SharedPreferences.getInstance();
    final accountsJson = prefs.getString(_accountsKey);
    if (accountsJson != null) {
      final List<dynamic> decoded = json.decode(accountsJson);
      return decoded.map((item) => AccountItem.fromMap(item)).toList();
    }
    return [];
  }
}