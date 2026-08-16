import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:everything_tool/model/StockModels.dart';

class DatabaseHelper {
  static final DatabaseHelper _instance = DatabaseHelper._internal();
  factory DatabaseHelper() => _instance;
  DatabaseHelper._internal();

  static Database? _database;

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    final dir = await getApplicationDocumentsDirectory();
    final path = join(dir.path, 'stock_trading.db');
    return await databaseFactoryFfi.openDatabase(path,
        options: OpenDatabaseOptions(version: 1, onCreate: _onCreate));
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
      )
    ''');
    await db.execute('''
      CREATE TABLE TransactionTrades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        price REAL NOT NULL,
        shares INTEGER NOT NULL,
        commission REAL DEFAULT 0,
        type TEXT NOT NULL,
        expected_range TEXT,
        expected_buy_low REAL,
        expected_buy_high REAL,
        expected_sell_low REAL,
        expected_sell_high REAL,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
      )
    ''');
    await db.execute('''
      CREATE TABLE t_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buy_TransactionTrade_id INTEGER NOT NULL,
        sell_TransactionTrade_id INTEGER NOT NULL,
        shares INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (buy_TransactionTrade_id) REFERENCES TransactionTrades(id) ON DELETE CASCADE,
        FOREIGN KEY (sell_TransactionTrade_id) REFERENCES TransactionTrades(id) ON DELETE CASCADE
      )
    ''');
  }

  // ========== Account CRUD ==========
  Future<int> insertAccount(Account account) async {
    final db = await database;
    return await db.insert('accounts', account.toMap());
  }

  Future<List<Account>> getAccounts() async {
    final db = await database;
    final maps = await db.query('accounts', orderBy: 'id');
    return maps.map((m) => Account.fromMap(m)).toList();
  }

  Future<int> deleteAccount(int id) async {
    final db = await database;
    return await db.delete('accounts', where: 'id = ?', whereArgs: [id]);
  }

  // ========== Stock CRUD ==========
  Future<int> insertStock(Stock stock) async {
    final db = await database;
    return await db.insert('stocks', stock.toMap());
  }

  Future<List<Stock>> getStocksByAccount(int accountId) async {
    final db = await database;
    final maps = await db.query('stocks',
        where: 'account_id = ?',
        whereArgs: [accountId],
        orderBy: 'created_at DESC');
    return maps.map((m) => Stock.fromMap(m)).toList();
  }

  Future<int> deleteStock(int id) async {
    final db = await database;
    return await db.delete('stocks', where: 'id = ?', whereArgs: [id]);
  }

  // ========== TransactionTrade CRUD ==========
  Future<int> insertTransactionTrade(TransactionTrade t) async {
    final db = await database;
    return await db.insert('TransactionTrades', t.toMap());
  }

  Future<int> updateTransactionTrade(TransactionTrade t) async {
    final db = await database;
    return await db.update('TransactionTrades', t.toMap(),
        where: 'id = ?', whereArgs: [t.id]);
  }

  Future<int> deleteTransactionTrade(int id) async {
    final db = await database;
    return await db.delete('TransactionTrades', where: 'id = ?', whereArgs: [id]);
  }

  Future<List<TransactionTrade>> getTransactionTradesByStock(int stockId) async {
    final db = await database;
    final maps = await db.query('TransactionTrades',
        where: 'stock_id = ?',
        whereArgs: [stockId],
        orderBy: 'date ASC');
    return maps.map((m) => TransactionTrade.fromMap(m)).toList();
  }

  Future<TransactionTrade?> getTransactionTradeById(int id) async {
    final db = await database;
    final maps =
        await db.query('TransactionTrades', where: 'id = ?', whereArgs: [id]);
    if (maps.isEmpty) return null;
    return TransactionTrade.fromMap(maps.first);
  }

  /// 获取某只股票的可关联买入记录（未完全被做T关联的）
  Future<List<TransactionTrade>> getAvailableBuyTransactionTrades(
      int stockId, int? excludeSellId) async {
    final db = await database;
    final buys = await db.query('TransactionTrades',
        where: 'stock_id = ? AND type = ?',
        whereArgs: [stockId, '买入'],
        orderBy: 'date ASC');
    final tTrades = await db.query('t_trades');
    final result = <TransactionTrade>[];
    for (final buy in buys) {
      final t = TransactionTrade.fromMap(buy);
      int linkedShares = 0;
      for (final tt in tTrades) {
        final ttShares = tt['shares'] as int;
        if (tt['buy_TransactionTrade_id'] == t.id &&
            tt['sell_TransactionTrade_id'] != excludeSellId) {
          linkedShares += ttShares;
        }
      }
      if (t.shares > linkedShares) {
        result.add(t);
      }
    }
    return result;
  }

  // ========== TTrade CRUD ==========
  Future<int> insertTTrade(TTrade tt) async {
    final db = await database;
    return await db.insert('t_trades', tt.toMap());
  }

  Future<int> deleteTTrade(int id) async {
    final db = await database;
    return await db.delete('t_trades', where: 'id = ?', whereArgs: [id]);
  }

  Future<List<Map<String, dynamic>>> getTTradesWithDetails(int stockId) async {
    final db = await database;
    final result = await db.rawQuery('''
      SELECT tt.*, 
        b.price as buy_price, b.shares as buy_shares, b.commission as buy_commission, b.date as buy_date,
        s.price as sell_price, s.shares as sell_shares, s.commission as sell_commission, s.date as sell_date
      FROM t_trades tt
      JOIN TransactionTrades b ON tt.buy_TransactionTrade_id = b.id
      JOIN TransactionTrades s ON tt.sell_TransactionTrade_id = s.id
      WHERE b.stock_id = ?
      ORDER BY tt.created_at ASC
    ''', [stockId]);
    return result;
  }

  /// 删除某笔卖出关联的所有做T记录
  Future<void> deleteTTradesBySellId(int sellId) async {
    final db = await database;
    await db.delete('t_trades',
        where: 'sell_TransactionTrade_id = ?', whereArgs: [sellId]);
  }

  // ========== 收益统计 ==========

  /// 股票持仓汇总
  Future<Map<String, double>> getStockSummary(int stockId) async {
    final db = await database;
    final result = await db.rawQuery('''
      SELECT 
        COALESCE(SUM(shares), 0) as total_shares,
        COALESCE(SUM(-price * shares - commission), 0) as total_cost
      FROM TransactionTrades
      WHERE stock_id = ?
    ''', [stockId]);
    final shares = (result.first['total_shares'] as num).toDouble();
    final cost = (result.first['total_cost'] as num).toDouble();
    return {
      'total_shares': shares,
      'total_cost': cost,
      'avg_cost': shares != 0 ? cost / shares : 0,
    };
  }

  /// 建仓计算：按建仓周期追踪持仓成本
  /// 当持仓股数从 0 变为正数时视为建仓，归零时视为清仓
  /// 持仓成本 = 建仓周期累计费用 / 持仓股数（卖出利润会拉低成本）
  Future<Map<String, double>> getStockFifoSummary(int stockId) async {
    final transactions = await getTransactionTradesByStock(stockId);

    double allTimeCost = 0;
    int allTimeShares = 0;
    int currentShares = 0;
    double currentCycleCost = 0;
    bool inCycle = false;

    for (final t in transactions) {
      allTimeCost += t.cost;
      allTimeShares += t.shares;

      if (t.type == '买入') {
        if (!inCycle && t.shares > 0) {
          currentCycleCost = 0;
          currentShares = 0;
          inCycle = true;
        }
        currentShares += t.shares;
        currentCycleCost += t.cost;
      } else {
        currentShares += t.shares;
        currentCycleCost += t.cost;

        if (currentShares == 0) {
          inCycle = false;
        }
      }
    }

    final double avgCost =
        currentShares > 0 ? (currentCycleCost / currentShares).abs() : 0;
    final double allTimeAvgCost =
        allTimeShares != 0 ? (allTimeCost / allTimeShares).abs() : 0;

    return {
      'total_shares': currentShares.toDouble(),
      'total_cost': allTimeCost,
      'avg_cost': avgCost,
      'cycle_cost': currentCycleCost,
      'total_shares_all': allTimeShares.toDouble(),
      'total_avg_cost': allTimeAvgCost,
    };
  }

  /// 账户维度收益
  Future<Map<String, double>> getAccountProfit(int accountId) async {
    final db = await database;
    final result = await db.rawQuery('''
      SELECT COALESCE(SUM(-t.price * t.shares - t.commission), 0) as profit
      FROM TransactionTrades t
      JOIN stocks s ON t.stock_id = s.id
      WHERE s.account_id = ?
    ''', [accountId]);
    return {'profit': (result.first['profit'] as num).toDouble()};
  }

  /// 做T收益
  Future<double> getTTradeProfit(int ttradeId) async {
    final db = await database;
    final result = await db.rawQuery('''
      SELECT 
        tt.shares as t_shares,
        b.price as buy_price, b.shares as buy_shares, b.commission as buy_commission,
        s.price as sell_price, s.shares as sell_shares, s.commission as sell_commission
      FROM t_trades tt
      JOIN TransactionTrades b ON tt.buy_TransactionTrade_id = b.id
      JOIN TransactionTrades s ON tt.sell_TransactionTrade_id = s.id
      WHERE tt.id = ?
    ''', [ttradeId]);
    if (result.isEmpty) return 0;
    final r = result.first;
    final tShares = (r['t_shares'] as num).toDouble();
    final buyPrice = (r['buy_price'] as num).toDouble();
    final sellPrice = (r['sell_price'] as num).toDouble();
    final buyShares = (r['buy_shares'] as num).toDouble();
    final buyComm = (r['buy_commission'] as num).toDouble();
    final sellShares = (r['sell_shares'] as num).toDouble();
    final sellComm = (r['sell_commission'] as num).toDouble();
    final buyCommRatio = buyShares != 0 ? buyComm * (tShares / buyShares.abs()) : 0.0;
    final sellCommRatio = sellShares != 0 ? sellComm * (tShares / sellShares.abs()) : 0.0;
    return (sellPrice - buyPrice) * tShares - buyCommRatio - sellCommRatio;
  }
}