class Account {
  int? id;
  String name;
  String createdAt;

  Account({this.id, required this.name, required this.createdAt});

  Map<String, dynamic> toMap() => {
        'id': id,
        'name': name,
        'created_at': createdAt,
      };

  factory Account.fromMap(Map<String, dynamic> map) => Account(
        id: map['id'],
        name: map['name'],
        createdAt: map['created_at'],
      );

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
          other is Account &&
              runtimeType == other.runtimeType &&
              id == other.id;

  @override
  int get hashCode => id.hashCode;
}

class Stock {
  int? id;
  int accountId;
  String name;
  String code;
  String createdAt;

  Stock({
    this.id,
    required this.accountId,
    required this.name,
    required this.code,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() => {
        'id': id,
        'account_id': accountId,
        'name': name,
        'code': code,
        'created_at': createdAt,
      };

  factory Stock.fromMap(Map<String, dynamic> map) => Stock(
        id: map['id'],
        accountId: map['account_id'],
        name: map['name'],
        code: map['code'],
        createdAt: map['created_at'],
      );
}

class TransactionTrade {
  int? id;
  int stockId;
  String date; // yyyy-MM-dd
  double price;
  int shares; // 正=买入, 负=卖出
  double commission;
  String type; // "买入" / "卖出" / "股息"
  double? dividend; // 股息金额（仅 type=股息 时使用）
  String? expectedRange;
  double? expectedBuyLow;
  double? expectedBuyHigh;
  double? expectedSellLow;
  double? expectedSellHigh;
  String? note;
  String createdAt;

  TransactionTrade({
    this.id,
    required this.stockId,
    required this.date,
    required this.price,
    required this.shares,
    this.commission = 0,
    required this.type,
    this.dividend,
    this.expectedRange,
    this.expectedBuyLow,
    this.expectedBuyHigh,
    this.expectedSellLow,
    this.expectedSellHigh,
    this.note,
    required this.createdAt,
  });

  /// 本笔交易费用（买入为负，卖出为正，股息为收入）
  double get cost {
    if (type == '股息') {
      return dividend ?? 0;
    }
    return -price * shares - commission;
  }

  Map<String, dynamic> toMap() => {
        'id': id,
        'stock_id': stockId,
        'date': date,
        'price': price,
        'shares': shares,
        'commission': commission,
        'type': type,
        'dividend': dividend,
        'expected_range': expectedRange,
        'expected_buy_low': expectedBuyLow,
        'expected_buy_high': expectedBuyHigh,
        'expected_sell_low': expectedSellLow,
        'expected_sell_high': expectedSellHigh,
        'note': note,
        'created_at': createdAt,
      };

  factory TransactionTrade.fromMap(Map<String, dynamic> map) => TransactionTrade(
        id: map['id'],
        stockId: map['stock_id'],
        date: map['date'],
        price: map['price'],
        shares: map['shares'],
        commission: map['commission'] ?? 0,
        type: map['type'],
        dividend: map['dividend'],
        expectedRange: map['expected_range'],
        expectedBuyLow: map['expected_buy_low'],
        expectedBuyHigh: map['expected_buy_high'],
        expectedSellLow: map['expected_sell_low'],
        expectedSellHigh: map['expected_sell_high'],
        note: map['note'],
        createdAt: map['created_at'],
      );
}

class TTrade {
  int? id;
  int buyTransactionId;
  int sellTransactionId;
  int shares;
  String createdAt;

  TTrade({
    this.id,
    required this.buyTransactionId,
    required this.sellTransactionId,
    required this.shares,
    required this.createdAt,
  });

  Map<String, dynamic> toMap() => {
        'id': id,
        'buy_transaction_id': buyTransactionId,
        'sell_transaction_id': sellTransactionId,
        'shares': shares,
        'created_at': createdAt,
      };

  factory TTrade.fromMap(Map<String, dynamic> map) => TTrade(
        id: map['id'],
        buyTransactionId: map['buy_transaction_id'],
        sellTransactionId: map['sell_transaction_id'],
        shares: map['shares'],
        createdAt: map['created_at'],
      );
}