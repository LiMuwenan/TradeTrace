import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'package:password/model/AccountItem.dart';

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