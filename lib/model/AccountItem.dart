class AccountItem {
  String id;
  String appName;
  String username;
  String password;
  DateTime createdAt;

  AccountItem({
    required this.appName,
    required this.username,
    required this.password,
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
      'createdAt': createdAt.toIso8601String(),
    };
  }

  factory AccountItem.fromMap(Map<String, dynamic> map) {
    return AccountItem(
      id: map['id'],
      appName: map['appName'],
      username: map['username'],
      password: map['password'],
      createdAt: DateTime.parse(map['createdAt']),
    );
  }
}