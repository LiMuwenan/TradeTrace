import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:everything_tool/main.dart';

void main() {
  testWidgets('App renders HomePage with title', (WidgetTester tester) async {
    await tester.pumpWidget(const EverythingToolApp());

    // 验证 AppBar 标题存在
    expect(find.text('EverythingTool'), findsOneWidget);

    // 验证搜索框存在
    expect(find.text('搜索工具...'), findsOneWidget);

    // 验证密码管理工具卡片存在
    expect(find.text('密码管理'), findsOneWidget);

    // 验证股票记录工具卡片存在
    expect(find.text('股票记录'), findsOneWidget);
  });
}