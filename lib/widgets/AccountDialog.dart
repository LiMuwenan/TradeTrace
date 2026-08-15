import 'package:flutter/material.dart';

import 'package:everything_tool/model/AccountItem.dart';

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