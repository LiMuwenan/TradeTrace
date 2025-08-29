import 'package:flutter/material.dart';

import 'package:password/page/AccountListPage.dart';

void main() {
  runApp(AccountManagerApp());
}

class AccountManagerApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '账号密码管理器',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        visualDensity: VisualDensity.adaptivePlatformDensity,
      ),
      home: AccountListPage(),
    );
  }
}