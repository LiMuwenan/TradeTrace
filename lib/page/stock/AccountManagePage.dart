import 'package:flutter/material.dart';
import 'package:everything_tool/model/StockModels.dart';
import 'package:everything_tool/utils/DatabaseHelper.dart';

class AccountManagePage extends StatefulWidget {
  const AccountManagePage({super.key});

  @override
  State<AccountManagePage> createState() => _AccountManagePageState();
}

class _AccountManagePageState extends State<AccountManagePage> {
  final _db = DatabaseHelper();
  List<Account> _accounts = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final accounts = await _db.getAccounts();
    setState(() => _accounts = accounts);
  }

  Future<void> _addAccount() async {
    final controller = TextEditingController();
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('添加账户'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: '账户名称'),
          autofocus: true,
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true), child: const Text('添加')),
        ],
      ),
    );
    if (result == true && controller.text.isNotEmpty) {
      final account = Account(
        name: controller.text.trim(),
        createdAt: DateTime.now().toIso8601String(),
      );
      await _db.insertAccount(account);
      _load();
    }
  }

  Future<void> _deleteAccount(Account account) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除确认'),
        content: Text('确定删除账户「${account.name}」？该账户下所有数据将被删除。'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('删除')),
        ],
      ),
    );
    if (confirm == true) {
      await _db.deleteAccount(account.id!);
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('账户管理')),
      body: _accounts.isEmpty
          ? const Center(child: Text('暂无账户'))
          : ListView.builder(
              itemCount: _accounts.length,
              itemBuilder: (context, index) {
                final account = _accounts[index];
                return ListTile(
                  title: Text(account.name),
                  subtitle: Text('创建于 ${account.createdAt.substring(0, 10)}'),
                  trailing: IconButton(
                    icon: const Icon(Icons.delete, color: Colors.red),
                    onPressed: () => _deleteAccount(account),
                  ),
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addAccount,
        child: const Icon(Icons.add),
      ),
    );
  }
}