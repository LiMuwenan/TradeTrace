import 'package:flutter/material.dart';
import 'package:everything_tool/model/StockModels.dart';
import 'package:everything_tool/utils/DatabaseHelper.dart';
import 'package:everything_tool/page/stock/StockTransactionDialog.dart';
import 'package:everything_tool/page/stock/TTradeDialog.dart';

class StockDetailPage extends StatefulWidget {
  final Stock stock;
  const StockDetailPage({super.key, required this.stock});

  @override
  State<StockDetailPage> createState() => _StockDetailPageState();
}

class _StockDetailPageState extends State<StockDetailPage> {
  final _db = DatabaseHelper();
  List<TransactionTrade> _transactions = [];
  List<Map<String, dynamic>> _tTrades = [];
  Map<String, double> _summary = {};
  double _holding = 0;
  double _cumulativeCost = 0;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final transactions = await _db.getTransactionTradesByStock(widget.stock.id!, 'DESC');
    final tTrades = await _db.getTTradesWithDetails(widget.stock.id!);
    final summary = await _db.getStockFifoSummary(widget.stock.id!);
    setState(() {
      _transactions = transactions;
      _tTrades = tTrades;
      _summary = summary;
      _holding = summary['total_shares'] ?? 0;
      _cumulativeCost = summary['total_cost'] ?? 0;
    });
  }

  Future<void> _addTransaction() async {
    final result = await showDialog<TransactionTrade>(
      context: context,
      builder: (ctx) => StockTransactionDialog(stockId: widget.stock.id!),
    );
    if (result != null) {
      await _db.insertTransactionTrade(result);
      _loadData();
    }
  }

  Future<void> _openTTradeDialog(TransactionTrade sellTxn) async {
    final result = await showDialog<TTrade>(
      context: context,
      builder: (ctx) =>
          TTradeDialog(stockId: widget.stock.id!, sellTransaction: sellTxn),
    );
    if (result != null) {
      await _db.insertTTrade(result);
      _loadData();
    }
  }

  Future<void> _editTransaction(TransactionTrade t) async {
    final result = await showDialog<TransactionTrade>(
      context: context,
      builder: (ctx) => StockTransactionDialog(
          stockId: widget.stock.id!, transaction: t),
    );
    if (result != null) {
      await _db.updateTransactionTrade(result);
      _loadData();
    }
  }

  Future<void> _deleteTransaction(TransactionTrade t) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除确认'),
        content: const Text('确定删除此交易记录？关联的做T记录也会被删除。'),
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
      await _db.deleteTTradesBySellId(t.id!);
      await _db.deleteTransactionTrade(t.id!);
      _loadData();
    }
  }

  String _getTTradeLabel(TransactionTrade sellTxn) {
    final ttList = _tTrades
        .where((tt) => tt['sell_transaction_id'] == sellTxn.id)
        .toList();
    if (ttList.isEmpty) return '';
    final parts = ttList.map((tt) {
      final buyDate = (tt['buy_date'] as String).substring(5);
      final tShares = tt['shares'];
      return '${buyDate}买入 T${tShares}股';
    }).join(', ');
    return '  \u2193 做T: $parts';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.stock.name}${widget.stock.code}'),
      ),
      body: Column(
        children: [
          Container(
            margin: const EdgeInsets.all(16),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildSummaryItem(
                        '持有', '${_holding.toStringAsFixed(0)}股'),
                    _buildSummaryItem(
                        '持仓成本', (_summary['avg_cost'] ?? 0).toStringAsFixed(3)),
                    _buildSummaryItem(
                      '持仓收益',
                      (_summary['cycle_cost'] ?? 0) >= 0
                          ? '+${(_summary['cycle_cost'] ?? 0).toStringAsFixed(2)}'
                          : (_summary['cycle_cost'] ?? 0).toStringAsFixed(2),
                      (_summary['cycle_cost'] ?? 0) >= 0 ? Colors.red : Colors.green,
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                const Divider(height: 1),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _buildSummaryItem(
                      '总成本',
                      (_summary['total_shares'] ?? 0) == 0
                          ? '0.00'
                          : (_summary['total_avg_cost'] ?? 0).toStringAsFixed(3),
                    ),
                    _buildSummaryItem(
                      '总收益',
                      _cumulativeCost >= 0
                          ? '+${_cumulativeCost.toStringAsFixed(2)}'
                          : _cumulativeCost.toStringAsFixed(2),
                      _cumulativeCost >= 0 ? Colors.red : Colors.green,
                    ),
                    _buildSummaryItem(
                      '清仓收益',
                        (_cumulativeCost-(_summary['cycle_cost'] ?? 0)) >= 0
                          ? '+${(_cumulativeCost-(_summary['cycle_cost'] ?? 0)).toStringAsFixed(2)}'
                          : (_cumulativeCost-(_summary['cycle_cost'] ?? 0)).toStringAsFixed(2),
                      (_cumulativeCost-(_summary['cycle_cost'] ?? 0)) >= 0 ? Colors.red : Colors.green,
                    ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: _transactions.isEmpty
                ? const Center(child: Text('暂无交易记录'))
                : ListView.builder(
                    itemCount: _transactions.length,
                    itemBuilder: (context, index) {
                      final t = _transactions[index];
                      final ttLabel = _getTTradeLabel(t);
                      return ListTile(
                        title: Text(
                          '${t.date.substring(5)} ${t.type} ${t.shares.abs()}股 @${t.price.toStringAsFixed(2)}',
                        ),
                        subtitle: Text(
                          '费用: ${t.cost.toStringAsFixed(2)}'
                          '${t.note != null && t.note!.isNotEmpty ? ' | 备注: ${t.note}' : ''}'
                          '$ttLabel',
                          style: ttLabel.isNotEmpty
                              ? TextStyle(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .primary)
                              : null,
                        ),
                        trailing: Text(
                          t.cost >= 0
                              ? '+${t.cost.toStringAsFixed(2)}'
                              : t.cost.toStringAsFixed(2),
                          style: TextStyle(
                            color: t.cost >= 0 ? Colors.red : Colors.green,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        onTap: () => _editTransaction(t),
                        onLongPress: () {
                          showModalBottomSheet(
                            context: context,
                            builder: (ctx) => SafeArea(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  ListTile(
                                    leading: const Icon(Icons.edit),
                                    title: const Text('编辑'),
                                    onTap: () {
                                      Navigator.pop(ctx);
                                      _editTransaction(t);
                                    },
                                  ),
                                  if (t.type == '卖出')
                                    ListTile(
                                      leading: const Icon(Icons.link),
                                      title: const Text('关联做T'),
                                      onTap: () {
                                        Navigator.pop(ctx);
                                        _openTTradeDialog(t);
                                      },
                                    ),
                                  ListTile(
                                    leading: const Icon(Icons.delete,
                                        color: Colors.red),
                                    title: const Text('删除',
                                        style: TextStyle(color: Colors.red)),
                                    onTap: () {
                                      Navigator.pop(ctx);
                                      _deleteTransaction(t);
                                    },
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      );
                    },
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addTransaction,
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildSummaryItem(String label, String value, [Color? color]) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
        const SizedBox(height: 4),
        Text(value,
            style: TextStyle(
                fontSize: 15, fontWeight: FontWeight.w500, color: color)),
      ],
    );
  }
}