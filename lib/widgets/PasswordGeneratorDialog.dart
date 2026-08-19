import 'dart:math';

import 'package:flutter/material.dart';

/// 随机密码生成器对话框，返回生成的密码
class PasswordGeneratorDialog extends StatefulWidget {
  const PasswordGeneratorDialog({super.key});

  @override
  State<PasswordGeneratorDialog> createState() =>
      _PasswordGeneratorDialogState();
}

class _PasswordGeneratorDialogState extends State<PasswordGeneratorDialog> {
  final _random = Random();
  int _length = 16;
  bool _useUpper = true;
  bool _useLower = true;
  bool _useDigits = true;
  bool _useSymbols = true;
  late String _generated;

  static const _upper = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  static const _lower = 'abcdefghijklmnopqrstuvwxyz';
  static const _digits = '0123456789';
  static const _symbols = '!@#\$%^&*()-_=+[]{}';

  @override
  void initState() {
    super.initState();
    _generated = _generate();
  }

  String _generate() {
    var pool = '';
    if (_useUpper) pool += _upper;
    if (_useLower) pool += _lower;
    if (_useDigits) pool += _digits;
    if (_useSymbols) pool += _symbols;
    if (pool.isEmpty) return '';

    // 保证每类已选字符至少出现一次
    final chars = <String>[];
    if (_useUpper) chars.add(_upper[_random.nextInt(_upper.length)]);
    if (_useLower) chars.add(_lower[_random.nextInt(_lower.length)]);
    if (_useDigits) chars.add(_digits[_random.nextInt(_digits.length)]);
    if (_useSymbols) chars.add(_symbols[_random.nextInt(_symbols.length)]);
    while (chars.length < _length) {
      chars.add(pool[_random.nextInt(pool.length)]);
    }
    chars.shuffle(_random);
    return chars.join();
  }

  void _toggle(bool current, void Function(bool) setter) {
    final active = [_useUpper, _useLower, _useDigits, _useSymbols]
        .where((v) => v)
        .length;
    if (current && active <= 1) return; // 至少保留一类
    setter(!current);
    setState(() {
      _generated = _generate();
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('生成随机密码'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: SelectableText(
                _generated,
                style: const TextStyle(
                    fontFamily: 'monospace', fontSize: 16),
              ),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () =>
                    setState(() => _generated = _generate()),
                icon: const Icon(Icons.refresh),
                label: const Text('重新生成'),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Text('长度'),
                const SizedBox(width: 12),
                Expanded(
                  child: Slider(
                    min: 8,
                    max: 32,
                    divisions: 24,
                    value: _length.toDouble(),
                    label: '$_length',
                    onChanged: (v) => setState(() {
                      _length = v.round();
                      _generated = _generate();
                    }),
                  ),
                ),
                SizedBox(
                  width: 40,
                  child: Text('$_length',
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontWeight: FontWeight.w500)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 16,
              runSpacing: 8,
              children: [
                _buildToggle('大写', _useUpper, (v) => _useUpper = v),
                _buildToggle('小写', _useLower, (v) => _useLower = v),
                _buildToggle('数字', _useDigits, (v) => _useDigits = v),
                _buildToggle('符号', _useSymbols, (v) => _useSymbols = v),
              ],
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消')),
        FilledButton(
          onPressed: () => Navigator.pop(context, _generated),
          child: const Text('使用'),
        ),
      ],
    );
  }

  Widget _buildToggle(String label, bool value, void Function(bool) setter) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Checkbox(
          value: value,
          onChanged: (_) => _toggle(value, setter),
        ),
        Text(label),
      ],
    );
  }
}
