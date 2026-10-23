class AccountItem {
  static const List<String> presetTags = [
    '游戏',
    '开发',
    '工作',
    '金融',
    '学习',
    '其他',
  ];

  String id;
  String appName;
  String username;
  String password;
  String? tag;
  DateTime createdAt;

  AccountItem({
    required this.appName,
    required this.username,
    required this.password,
    this.tag,
    DateTime? createdAt,
    String? id,
  })  : id = id ?? DateTime.now().millisecondsSinceEpoch.toString(),
        createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'appName': appName,
      'username': username,
      'password': password,
      'tag': tag,
      'createdAt': createdAt.toIso8601String(),
    };
  }

  factory AccountItem.fromMap(Map<String, dynamic> map) {
    return AccountItem(
      id: map['id'],
      appName: map['appName'],
      username: map['username'],
      password: map['password'],
      tag: map['tag'],
      createdAt: DateTime.parse(map['createdAt']),
    );
  }
}