import 'package:flutter/material.dart';
import 'package:everything_tool/model/StockModels.dart';
import 'package:everything_tool/utils/DatabaseHelper.dart';

class TTradeDialog extends StatefulWidget {
  final int stockId;
  final TransactionTrade sellTransaction;

  const TTradeDialog({
    super.key,
    required this.stockId,
    required this.sellTransaction,
  });

  @override
  State<TTradeDialog> createState() => _TTradeDialogState();
}

class _TTradeDialogState extends State<TTradeDialog> {
  final _db = DatabaseHelper();
  List<TransactionTrade> _availableBuys = [];
  TransactionTrade? _selectedBuy;
  final _sharesController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _sharesController.text = widget.sellTransaction.shares.abs().toString();
    _loadAvailableBuys();
  }

  Future<void> _loadAvailableBuys() async {
    final buys = await _db.getAvailableBuyTransactionTrades(
        widget.stockId, widget.sellTransaction.id);
    setState(() => _availableBuys = buys);
  }

  void _submit() {
    if (_selectedBuy == null) return;
    final shares = int.tryParse(_sharesController.text);
    if (shares == null || shares <= 0) return;
    if (shares > _selectedBuy!.shares) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('T出股数不能超过买入股数')),
      );
      return;
    }
    final tt = TTrade(
      buyTransactionId: _selectedBuy!.id!,
      sellTransactionId: widget.sellTransaction.id!,
      shares: shares,
      createdAt: DateTime.now().toIso8601String(),
    );
    Navigator.pop(context, tt);
  }

  @override
  void dispose() {
    _sharesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('做T关联'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '卖出: ${widget.sellTransaction.date.substring(5)} '
              '${widget.sellTransaction.shares.abs()}股 '
              '@${widget.sellTransaction.price.toStringAsFixed(2)}',
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 16),
            const Text('选择关联买入记录:'),
            const SizedBox(height: 8),
            if (_availableBuys.isEmpty)
              const Text('无可关联的买入记录',
                  style: TextStyle(color: Colors.grey))
            else
              ...(_availableBuys.map((buy) {
                return RadioListTile<TransactionTrade>(
                  value: buy,
                  groupValue: _selectedBuy,
                  title: Text(
                    '${buy.date.substring(5)} 买入 ${buy.shares}股 '
                    '@${buy.price.toStringAsFixed(2)}',
                  ),
                  subtitle: Text('可关联: ${buy.shares}股'),
                  contentPadding: EdgeInsets.zero,
                  onChanged: (v) => setState(() => _selectedBuy = v),
                );
              })),
            const SizedBox(height: 16),
            TextFormField(
              controller: _sharesController,
              decoration: const InputDecoration(labelText: 'T出股数'),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('取消')),
        FilledButton(
          onPressed: _selectedBuy != null ? _submit : null,
          child: const Text('确认关联'),
        ),
      ],
    );
  }
}