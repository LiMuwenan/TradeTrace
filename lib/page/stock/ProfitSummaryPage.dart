import 'package:flutter/material.dart';
import 'package:everything_tool/utils/DatabaseHelper.dart';

class ProfitSummaryPage extends StatefulWidget {
  const ProfitSummaryPage({super.key});

  @override
  State<ProfitSummaryPage> createState() => _ProfitSummaryPageState();
}

class _ProfitSummaryPageState extends State<ProfitSummaryPage>
    with SingleTickerProviderStateMixin {
  final _db = DatabaseHelper();
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('收益统计'),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabs: const [
            Tab(text: '按账户'),
            Tab(text: '按个股'),
            Tab(text: '合并账户'),
            Tab(text: '按做T'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _AccountProfitView(),
          _StockProfitView(),
          _MergedProfitView(),
          _TTradeProfitView(),
        ],
      ),
    );
  }
}

class _AccountProfitView extends StatefulWidget {
  const _AccountProfitView();

  @override
  State<_AccountProfitView> createState() => _AccountProfitViewState();
}

class _AccountProfitViewState extends State<_AccountProfitView> {
  final _db = DatabaseHelper();
  List<Map<String, dynamic>> _data = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final accounts = await _db.getAccounts();
    final result = <Map<String, dynamic>>[];
    for (final a in accounts) {
      final profit = await _db.getAccountProfit(a.id!);
      result.add({
        'name': a.name,
        'profit': profit['profit'] ?? 0,
      });
    }
    setState(() {
      _data = result;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_data.isEmpty) {
      return const Center(child: Text('暂无数据'));
    }
    return ListView(
      children: _data.map((d) {
        final profit = d['profit'] as double;
        return ListTile(
          title: Text(d['name']),
          trailing: Text(
            profit >= 0
                ? '+${profit.toStringAsFixed(2)}'
                : profit.toStringAsFixed(2),
            style: TextStyle(
              color: profit >= 0 ? Colors.red : Colors.green,
              fontWeight: FontWeight.w500,
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _StockProfitView extends StatefulWidget {
  const _StockProfitView();

  @override
  State<_StockProfitView> createState() => _StockProfitViewState();
}

class _StockProfitViewState extends State<_StockProfitView> {
  final _db = DatabaseHelper();
  List<Map<String, dynamic>> _data = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final accounts = await _db.getAccounts();
    final result = <Map<String, dynamic>>[];
    for (final a in accounts) {
      final stocks = await _db.getStocksByAccount(a.id!);
      for (final s in stocks) {
        final summary = await _db.getStockSummary(s.id!);
        result.add({
          'account': a.name,
          'name': '${s.name}${s.code}',
          'profit': summary['total_cost'] ?? 0,
        });
      }
    }
    setState(() {
      _data = result;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_data.isEmpty) {
      return const Center(child: Text('暂无数据'));
    }
    return ListView(
      children: _data.map((d) {
        final profit = d['profit'] as double;
        return ListTile(
          title: Text(d['name']),
          subtitle: Text('账户: ${d['account']}'),
          trailing: Text(
            profit >= 0
                ? '+${profit.toStringAsFixed(2)}'
                : profit.toStringAsFixed(2),
            style: TextStyle(
              color: profit >= 0 ? Colors.red : Colors.green,
              fontWeight: FontWeight.w500,
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _MergedProfitView extends StatefulWidget {
  const _MergedProfitView();

  @override
  State<_MergedProfitView> createState() => _MergedProfitViewState();
}

class _MergedProfitViewState extends State<_MergedProfitView> {
  final _db = DatabaseHelper();
  double _totalProfit = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final accounts = await _db.getAccounts();
    double total = 0;
    for (final a in accounts) {
      final profit = await _db.getAccountProfit(a.id!);
      total += profit['profit'] ?? 0;
    }
    setState(() {
      _totalProfit = total;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('合并账户总收益',
              style: TextStyle(fontSize: 16, color: Colors.grey)),
          const SizedBox(height: 16),
          Text(
            _totalProfit >= 0
                ? '+${_totalProfit.toStringAsFixed(2)}'
                : _totalProfit.toStringAsFixed(2),
            style: TextStyle(
              fontSize: 36,
              fontWeight: FontWeight.bold,
              color: _totalProfit >= 0 ? Colors.red : Colors.green,
            ),
          ),
        ],
      ),
    );
  }
}

class _TTradeProfitView extends StatefulWidget {
  const _TTradeProfitView();

  @override
  State<_TTradeProfitView> createState() => _TTradeProfitViewState();
}

class _TTradeProfitViewState extends State<_TTradeProfitView> {
  final _db = DatabaseHelper();
  List<Map<String, dynamic>> _data = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final accounts = await _db.getAccounts();
    final result = <Map<String, dynamic>>[];
    for (final a in accounts) {
      final stocks = await _db.getStocksByAccount(a.id!);
      for (final s in stocks) {
        final ttrades = await _db.getTTradesWithDetails(s.id!);
        for (final tt in ttrades) {
          final profit = await _db.getTTradeProfit(tt['id']);
          result.add({
            'stock': '${s.name}${s.code}',
            'buyDate': (tt['buy_date'] as String).substring(5),
            'sellDate': (tt['sell_date'] as String).substring(5),
            'shares': tt['shares'],
            'profit': profit,
          });
        }
      }
    }
    setState(() {
      _data = result;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_data.isEmpty) {
      return const Center(child: Text('暂无做T记录'));
    }
    return ListView(
      children: _data.map((d) {
        final profit = d['profit'] as double;
        return ListTile(
          title: Text(d['stock']),
          subtitle: Text(
              '${d['buyDate']} 买入 \u2192 ${d['sellDate']} 卖出, T${d['shares']}股'),
          trailing: Text(
            profit >= 0
                ? '+${profit.toStringAsFixed(2)}'
                : profit.toStringAsFixed(2),
            style: TextStyle(
              color: profit >= 0 ? Colors.red : Colors.green,
              fontWeight: FontWeight.w500,
            ),
          ),
        );
      }).toList(),
    );
  }
}