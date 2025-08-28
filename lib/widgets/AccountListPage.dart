import 'package:flutter/material.dart';

import 'package:password/model/AccountItem.dart';
import 'package:password/widgets/AccountDialog.dart';
import 'package:password/widgets/AccountListItem.dart';
import 'package:password/utils/ShareStore.dart';

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