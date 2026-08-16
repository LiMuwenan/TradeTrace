import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:everything_tool/model/StockModels.dart';

class StockTransactionDialog extends StatefulWidget {
  final int stockId;
  final TransactionTrade? transaction;

  const StockTransactionDialog({
    super.key,
    required this.stockId,
    this.transaction,
  });

  @override
  State<StockTransactionDialog> createState() => _StockTransactionDialogState();
}

class _StockTransactionDialogState extends State<StockTransactionDialog> {
  final _formKey = GlobalKey<FormState>();
  late DateTime _date;
  final _priceController = TextEditingController();
  final _sharesController = TextEditingController();
  final _commissionController = TextEditingController();
  final _noteController = TextEditingController();
  String _type = '买入';
  bool _useExpected = false;

  // 预期价格计算
  final _ratioController = TextEditingController(text: '0.015-0.02');
  final _expectedBuyLowController = TextEditingController();
  final _expectedBuyHighController = TextEditingController();
  final _expectedSellLowController = TextEditingController();
  final _expectedSellHighController = TextEditingController();

  bool _calculating = false;

  @override
  void initState() {
    super.initState();
    if (widget.transaction != null) {
      final t = widget.transaction!;
      _date = DateTime.parse(t.date);
      _priceController.text = t.price.toString();
      _sharesController.text = t.shares.abs().toString();
      _commissionController.text = t.commission.toString();
      _noteController.text = t.note ?? '';
      _type = t.type;
      _useExpected = t.expectedRange != null;
      if (_useExpected) {
        _ratioController.text = t.expectedRange!;
        _expectedBuyLowController.text = t.expectedBuyLow?.toString() ?? '';
        _expectedBuyHighController.text = t.expectedBuyHigh?.toString() ?? '';
        _expectedSellLowController.text = t.expectedSellLow?.toString() ?? '';
        _expectedSellHighController.text = t.expectedSellHigh?.toString() ?? '';
      }
    } else {
      _date = DateTime.now();
    }
  }

  void _calculateFromRatio() {
    if (_calculating) return;
    _calculating = true;
    final price = double.tryParse(_priceController.text) ?? 0;
    final ratioText = _ratioController.text.trim();
    final parts = ratioText.split('-');
    if (parts.length == 2 && price > 0) {
      final low = double.tryParse(parts[0]) ?? 0;
      final high = double.tryParse(parts[1]) ?? 0;
      _expectedBuyLowController.text = (price * (1 - low)).toStringAsFixed(3);
      _expectedBuyHighController.text =
          (price * (1 - high)).toStringAsFixed(3);
      _expectedSellLowController.text =
          (price * (1 + low)).toStringAsFixed(3);
      _expectedSellHighController.text =
          (price * (1 + high)).toStringAsFixed(3);
    }
    _calculating = false;
  }

  void _calculateFromPrice() {
    if (_calculating) return;
    _calculating = true;
    final price = double.tryParse(_priceController.text) ?? 0;
    final buyLow = double.tryParse(_expectedBuyLowController.text);
    final sellHigh = double.tryParse(_expectedSellHighController.text);
    if (buyLow != null && sellHigh != null && price > 0) {
      final lowRatio = 1 - buyLow / price;
      final highRatio = sellHigh / price - 1;
      _ratioController.text =
          '${lowRatio.toStringAsFixed(3)}-${highRatio.toStringAsFixed(3)}';
    }
    _calculating = false;
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2010),
      lastDate: DateTime.now(),
    );
    if (picked != null) {
      setState(() => _date = picked);
    }
  }

  void _submit() {
    if (!_formKey.currentState!.validate()) return;
    final price = double.parse(_priceController.text);
    final absShares = int.parse(_sharesController.text);
    final shares = _type == '买入' ? absShares : -absShares;
    final commission = double.tryParse(_commissionController.text) ?? 0;
    final txn = TransactionTrade(
      id: widget.transaction?.id,
      stockId: widget.stockId,
      date: DateFormat('yyyy-MM-dd').format(_date),
      price: price,
      shares: shares,
      commission: commission,
      type: _type,
      expectedRange: _useExpected ? _ratioController.text : null,
      expectedBuyLow:
          _useExpected ? double.tryParse(_expectedBuyLowController.text) : null,
      expectedBuyHigh: _useExpected
          ? double.tryParse(_expectedBuyHighController.text)
          : null,
      expectedSellLow: _useExpected
          ? double.tryParse(_expectedSellLowController.text)
          : null,
      expectedSellHigh: _useExpected
          ? double.tryParse(_expectedSellHighController.text)
          : null,
      note: _noteController.text.isNotEmpty ? _noteController.text : null,
      createdAt:
          widget.transaction?.createdAt ?? DateTime.now().toIso8601String(),
    );
    Navigator.pop(context, txn);
  }

  @override
  void dispose() {
    _priceController.dispose();
    _sharesController.dispose();
    _commissionController.dispose();
    _noteController.dispose();
    _ratioController.dispose();
    _expectedBuyLowController.dispose();
    _expectedBuyHighController.dispose();
    _expectedSellLowController.dispose();
    _expectedSellHighController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.transaction != null;
    return AlertDialog(
      title: Text(isEdit ? '编辑交易' : '添加交易'),
      content: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                title: const Text('日期'),
                trailing: Text(DateFormat('yyyy-MM-dd').format(_date)),
                onTap: _pickDate,
                contentPadding: EdgeInsets.zero,
              ),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: '买入', label: Text('买入')),
                  ButtonSegment(value: '卖出', label: Text('卖出')),
                ],
                selected: {_type},
                onSelectionChanged: (v) => setState(() => _type = v.first),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _priceController,
                decoration: const InputDecoration(labelText: '价格'),
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                validator: (v) => (v == null || v.isEmpty) ? '请输入价格' : null,
              ),
              TextFormField(
                controller: _sharesController,
                decoration: const InputDecoration(labelText: '股数'),
                keyboardType: TextInputType.number,
                validator: (v) => (v == null || v.isEmpty) ? '请输入股数' : null,
              ),
              TextFormField(
                controller: _commissionController,
                decoration: const InputDecoration(labelText: '手续费'),
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                title: const Text('预期价格'),
                value: _useExpected,
                onChanged: (v) {
                  setState(() => _useExpected = v);
                  if (v) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      _calculateFromRatio();
                    });
                  }
                },
                contentPadding: EdgeInsets.zero,
              ),
              if (_useExpected) ...[
                TextFormField(
                  controller: _ratioController,
                  decoration: const InputDecoration(
                    labelText: '预期比例范围 (如 0.015-0.02)',
                  ),
                  onChanged: (_) => _calculateFromRatio(),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _expectedBuyLowController,
                        decoration: const InputDecoration(labelText: '预期买入低'),
                        onChanged: (_) => _calculateFromPrice(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: _expectedBuyHighController,
                        decoration: const InputDecoration(labelText: '预期买入高'),
                        onChanged: (_) => _calculateFromPrice(),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextFormField(
                        controller: _expectedSellLowController,
                        decoration: const InputDecoration(labelText: '预期卖出低'),
                        onChanged: (_) => _calculateFromPrice(),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextFormField(
                        controller: _expectedSellHighController,
                        decoration: const InputDecoration(labelText: '预期卖出高'),
                        onChanged: (_) => _calculateFromPrice(),
                      ),
                    ),
                  ],
                ),
              ],
              TextFormField(
                controller: _noteController,
                decoration: const InputDecoration(labelText: '备注'),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context), child: const Text('取消')),
        FilledButton(onPressed: _submit, child: const Text('保存')),
      ],
    );
  }
}