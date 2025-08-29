import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';

import 'package:password/model/AccountItem.dart';

class SharedPreferencesHelper {
  static const String _accountsKey = 'saved_accounts';

  Future<void> saveAccounts(List<AccountItem> accounts) async {
    final prefs = await SharedPreferences.getInstance();
    final accountsJson = accounts.map((account) => account.toMap()).toList();
    await prefs.setString(_accountsKey, json.encode(accountsJson));
  }

  Future<List<AccountItem>> getAccounts() async {
    final prefs = await SharedPreferences.getInstance();
    final accountsJson = prefs.getString(_accountsKey);
    if (accountsJson != null) {
      final List<dynamic> decoded = json.decode(accountsJson);
      return decoded.map((item) => AccountItem.fromMap(item)).toList();
    }
    return [];
  }
}