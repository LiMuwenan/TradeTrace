import 'package:flutter/material.dart';
import 'package:everything_tool/page/HomePage.dart';

void main() {
  runApp(const EverythingToolApp());
}

class EverythingToolApp extends StatelessWidget {
  const EverythingToolApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'EverythingTool',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: Colors.blue,
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}