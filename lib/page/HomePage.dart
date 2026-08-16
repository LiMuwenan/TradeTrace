import 'package:flutter/material.dart';
import 'package:everything_tool/page/AccountListPage.dart';
import 'package:everything_tool/page/stock/StockHomePage.dart';

/// 工具项配置模型
class ToolItem {
  final String name;
  final IconData icon;
  final String description;
  final WidgetBuilder pageBuilder;

  const ToolItem({
    required this.name,
    required this.icon,
    required this.description,
    required this.pageBuilder,
  });
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final TextEditingController _searchController = TextEditingController();
  List<ToolItem> _filteredTools = [];

  /// 工具注册表 — 新增工具只需在此列表添加一项
  final List<ToolItem> _tools = const [
    ToolItem(
      name: '密码管理',
      icon: Icons.lock_outline,
      description: '账号密码存储',
      pageBuilder: _buildPasswordPage,
    ),
    ToolItem(
      name: '股票记录',
      icon: Icons.trending_up,
      description: '交易日志与做T',
      pageBuilder: _buildStockPage,
    ),
  ];

  static Widget _buildPasswordPage(BuildContext context) {
    return AccountListPage();
  }

  static Widget _buildStockPage(BuildContext context) {
    return const StockHomePage();
  }

  @override
  void initState() {
    super.initState();
    _filteredTools = List.from(_tools);
    _searchController.addListener(_filterTools);
  }

  void _filterTools() {
    final query = _searchController.text.toLowerCase();
    setState(() {
      _filteredTools = _tools.where((tool) {
        return tool.name.toLowerCase().contains(query) ||
            tool.description.toLowerCase().contains(query);
      }).toList();
    });
  }

  void _navigateToTool(ToolItem tool) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: tool.pageBuilder),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('EverythingTool'),
        elevation: 0,
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (value) {
              if (value == 'about') {
                showAboutDialog(
                  context: context,
                  applicationName: 'EverythingTool',
                  applicationVersion: '1.0.0',
                  children: [
                    const Text('个人常用工具集合应用'),
                  ],
                );
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'about', child: Text('关于')),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // 搜索框
          Container(
            padding: const EdgeInsets.all(16),
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: Container(
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surface,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.05),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: TextField(
                controller: _searchController,
                decoration: const InputDecoration(
                  hintText: '搜索工具...',
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(horizontal: 16),
                  prefixIcon: Icon(Icons.search, color: Colors.grey),
                ),
              ),
            ),
          ),
          // 工具网格
          Expanded(
            child: _filteredTools.isEmpty
                ? const Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.apps, size: 64, color: Colors.grey),
                        SizedBox(height: 16),
                        Text('未找到匹配的工具',
                            style: TextStyle(fontSize: 16, color: Colors.grey)),
                      ],
                    ),
                  )
                : Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: GridView.builder(
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 1.0,
                      ),
                      itemCount: _filteredTools.length,
                      itemBuilder: (context, index) {
                        return _buildToolCard(_filteredTools[index]);
                      },
                    ),
                  ),
          ),
          // 底部提示
          if (_filteredTools.length <= 2)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                '更多工具即将上线',
                style: TextStyle(color: Colors.grey.shade500, fontSize: 13),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildToolCard(ToolItem tool) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade200),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => _navigateToTool(tool),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  tool.icon,
                  size: 24,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                tool.name,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 2),
              Text(
                tool.description,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey.shade500,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}