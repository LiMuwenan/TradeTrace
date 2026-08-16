import 'package:flutter/material.dart';
import 'package:everything_tool/model/StockModels.dart';
import 'package:everything_tool/utils/DatabaseHelper.dart';
import 'package:everything_tool/page/stock/StockDetailPage.dart';
import 'package:everything_tool/page/stock/AccountManagePage.dart';
import 'package:everything_tool/page/stock/ProfitSummaryPage.dart';

class StockHomePage extends StatefulWidget {
  const StockHomePage({super.key});

  @override
  State<StockHomePage> createState() => _StockHomePageState();
}

class _StockHomePageState extends State<StockHomePage> {
  final _db = DatabaseHelper();
  List<Account> _accounts = [];
  Account? _selectedAccount;
  List<Stock> _stocks = [];
  Map<int, Map<String, double>> _summaries = {};

  @override
  void initState() {
    super.initState();
    _loadAccounts();
  }

  Future<void> _loadAccounts() async {
    final accounts = await _db.getAccounts();
    setState(() {
      _accounts = accounts;
      if (_accounts.isNotEmpty && _selectedAccount == null) {
        _selectedAccount = _accounts.first;
        _loadStocks();
      }
    });
  }

  Future<void> _loadStocks() async {
    if (_selectedAccount == null) return;
    final stocks = await _db.getStocksByAccount(_selectedAccount!.id!);
    final summaries = <int, Map<String, double>>{};
    for (final s in stocks) {
      summaries[s.id!] = await _db.getStockSummary(s.id!);
    }
    setState(() {
      _stocks = stocks;
      _summaries = summaries;
    });
  }

  Future<void> _addStock() async {
    final nameController = TextEditingController();
    final codeController = TextEditingController();
    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('添加股票'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: '股票名称'),
            ),
            TextField(
              controller: codeController,
              decoration: const InputDecoration(labelText: '股票代码'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('取消'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('添加'),
          ),
        ],
      ),
    );
    if (result == true && nameController.text.isNotEmpty) {
      final stock = Stock(
        accountId: _selectedAccount!.id!,
        name: nameController.text.trim(),
        code: codeController.text.trim(),
        createdAt: DateTime.now().toIso8601String(),
      );
      await _db.insertStock(stock);
      _loadStocks();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('股票记录'),
        actions: [
          IconButton(
            icon: const Icon(Icons.bar_chart),
            tooltip: '收益统计',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const ProfitSummaryPage()),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.manage_accounts),
            tooltip: '账户管理',
            onPressed: () async {
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const AccountManagePage()),
              );
              _loadAccounts();
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Row(
              children: [
                const Text('账户: ', style: TextStyle(fontSize: 15)),
                Expanded(
                  child: _accounts.isEmpty
                      ? const Text('请先添加账户',
                          style: TextStyle(color: Colors.grey))
                      : DropdownButton<Account>(
                          value: _selectedAccount,
                          isExpanded: true,
                          items: _accounts.map((a) {
                            return DropdownMenuItem(
                                value: a, child: Text(a.name));
                          }).toList(),
                          onChanged: (v) {
                            setState(() => _selectedAccount = v);
                            if (v != null) _loadStocks();
                          },
                        ),
                ),
              ],
            ),
          ),
          Expanded(
            child: _accounts.isEmpty
                ? const Center(child: Text('请先添加账户'))
                : _stocks.isEmpty
                    ? const Center(child: Text('暂无股票记录'))
                    : ListView.builder(
                        itemCount: _stocks.length,
                        itemBuilder: (context, index) {
                          final stock = _stocks[index];
                          final summary =
                              _summaries[stock.id!] ?? <String, double>{};
                          final totalShares = summary['total_shares'] ?? 0;
                          final totalCost = summary['total_cost'] ?? 0;
                          final avgCost = summary['avg_cost'] ?? 0;
                          return ListTile(
                            title: Text('${stock.name}${stock.code}'),
                            subtitle: Text(
                              '持有: ${totalShares.toStringAsFixed(0)}股 | '
                              '成本: ${avgCost.toStringAsFixed(3)} | '
                              '收益: ${totalCost >= 0 ? "+" : ""}${totalCost.toStringAsFixed(2)}',
                            ),
                            trailing: Text(
                              totalCost >= 0
                                  ? '+${totalCost.toStringAsFixed(2)}'
                                  : totalCost.toStringAsFixed(2),
                              style: TextStyle(
                                color:
                                    totalCost >= 0 ? Colors.red : Colors.green,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            onTap: () async {
                              await Navigator.push(
                                context,
                                MaterialPageRoute(
                                  builder: (_) =>
                                      StockDetailPage(stock: stock),
                                ),
                              );
                              _loadStocks();
                            },
                          );
                        },
                      ),
          ),
        ],
      ),
      floatingActionButton: _selectedAccount != null
          ? FloatingActionButton(
              onPressed: _addStock,
              child: const Icon(Icons.add),
            )
          : null,
    );
  }
}