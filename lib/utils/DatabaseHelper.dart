import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:everything_tool/model/StockModels.dart';
import 'package:everything_tool/model/AccountItem.dart';

class DatabaseHelper {
  static final DatabaseHelper _instance = DatabaseHelper._internal();
  static final int _version = 11;
  factory DatabaseHelper() => _instance;
  DatabaseHelper._internal();

  static Database? _database;
  static String? _dbPath;

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  /// 获取数据库文件路径
  Future<String> getDbPath() async {
    if (_dbPath != null) return _dbPath!;
    final dir = await getApplicationDocumentsDirectory();
    _dbPath = join(dir.path, 'stock_trading.db');
    return _dbPath!;
  }

  Future<Database> _initDatabase() async {
    final path = await getDbPath();
    return await databaseFactoryFfi.openDatabase(path,
        options: OpenDatabaseOptions(
          version: _version,
          onCreate: _onCreate,
          onUpgrade: _onUpgrade,
        ));
  }

  /// 关闭数据库（用于同步时替换文件）
  Future<void> closeDatabase() async {
    if (_database != null) {
      await _database!.close();
      _database = null;
    }
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE t_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');
    await db.execute('''
      CREATE TABLE t_stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (account_id) REFERENCES t_accounts(id) ON DELETE CASCADE
      )
    ''');
    await db.execute('''
      CREATE TABLE t_transaction_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        price REAL NOT NULL,
        shares INTEGER NOT NULL,
        commission REAL DEFAULT 0,
        type TEXT NOT NULL,
        dividend REAL,
        expected_range TEXT,
        expected_buy_low REAL,
        expected_buy_high REAL,
        expected_sell_low REAL,
        expected_sell_high REAL,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (stock_id) REFERENCES t_stocks(id) ON DELETE CASCADE
      )
    ''');
    await db.execute('''
      CREATE TABLE t_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buy_transaction_id INTEGER NOT NULL,
        sell_transaction_id INTEGER NOT NULL,
        shares INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (buy_transaction_id) REFERENCES t_transaction_trades(id) ON DELETE CASCADE,
        FOREIGN KEY (sell_transaction_id) REFERENCES t_transaction_trades(id) ON DELETE CASCADE
      )
    ''');
    await db.execute('''
      CREATE TABLE t_password_account (
        id TEXT PRIMARY KEY,
        app_name TEXT NOT NULL,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    ''');
  }

  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    if (oldVersion < 8) {
      await _migrateV1ToV2(db);
    }
    if (oldVersion < 8) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS t_password_account (
          id TEXT PRIMARY KEY,
          app_name TEXT NOT NULL,
          username TEXT NOT NULL,
          password TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      ''');
    }
    if (oldVersion < 11) {
      await _migrateV10ToV11(db);
    }
  }

  Future<void> _migrateV1ToV2(Database db) async {
    // 检查旧表是否存在，存在则迁移数据
    final tables = await db.rawQuery(
      "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('accounts', 'stocks', 'TransactionTrades', 'trades')"
    );
    final oldTableNames = tables.map((t) => t['name'] as String).toSet();
    if (oldTableNames.isEmpty) return;

    // 1. accounts → t_accounts
    if (oldTableNames.contains('accounts')) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS t_accounts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
      ''');
      await db.execute(
        'INSERT INTO t_accounts (id, name, created_at) SELECT id, name, created_at FROM accounts'
      );
      await db.execute('DROP TABLE accounts');
    }

    // 2. stocks → t_stocks
    if (oldTableNames.contains('stocks')) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS t_stocks (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          account_id INTEGER NOT NULL,
          name TEXT NOT NULL,
          code TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (account_id) REFERENCES t_accounts(id) ON DELETE CASCADE
        )
      ''');
      await db.execute(
        'INSERT INTO t_stocks (id, account_id, name, code, created_at) SELECT id, account_id, name, code, created_at FROM stocks'
      );
      await db.execute('DROP TABLE stocks');
    }

    // 3. TransactionTrades → t_transaction_trades
    if (oldTableNames.contains('TransactionTrades')) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS t_transaction_trades (
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
          FOREIGN KEY (stock_id) REFERENCES t_stocks(id) ON DELETE CASCADE
        )
      ''');
      await db.execute(
        'INSERT INTO t_transaction_trades (id, stock_id, date, price, shares, commission, type, expected_range, expected_buy_low, expected_buy_high, expected_sell_low, expected_sell_high, note, created_at) SELECT id, stock_id, date, price, shares, commission, type, expected_range, expected_buy_low, expected_buy_high, expected_sell_low, expected_sell_high, note, created_at FROM TransactionTrades'
      );
      await db.execute('DROP TABLE TransactionTrades');

    }

    // 4. trades → t_trades（字段名变更：buy_TransactionTrade_id → buy_transaction_id）
    if (oldTableNames.contains('trades')) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS t_trades (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          buy_transaction_id INTEGER NOT NULL,
          sell_transaction_id INTEGER NOT NULL,
          shares INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (buy_transaction_id) REFERENCES t_transaction_trades(id) ON DELETE CASCADE,
          FOREIGN KEY (sell_transaction_id) REFERENCES t_transaction_trades(id) ON DELETE CASCADE
        )
      ''');
      await db.execute(
        'INSERT INTO t_trades (id, buy_transaction_id, sell_transaction_id, shares, created_at) SELECT id, buy_TransactionTrade_id, sell_transaction_id, shares, created_at FROM trades'
      );
      await db.execute('DROP TABLE trades');
    }
  }

  Future<void> _migrateV10ToV11(Database db) async {
    // 检查 dividend 列是否已存在
    final columns = await db.rawQuery("PRAGMA table_info('t_transaction_trades')");
    final hasDividend = columns.any((c) => c['name'] == 'dividend');
    if (!hasDividend) {
      await db.execute(
        "ALTER TABLE t_transaction_trades ADD COLUMN dividend REAL"
      );
    }
  }

  // ========== Account CRUD ==========
  Future<int> insertAccount(Account account) async {
    final db = await database;
    return await db.insert('t_accounts', account.toMap());
  }

  Future<List<Account>> getAccounts() async {
    final db = await database;
    final maps = await db.query('t_accounts', orderBy: 'id');
    return maps.map((m) => Account.fromMap(m)).toList();
  }

  Future<int> deleteAccount(int id) async {
    final db = await database;
    return await db.delete('t_accounts', where: 'id = ?', whereArgs: [id]);
  }

  // ========== Stock CRUD ==========
  Future<int> insertStock(Stock stock) async {
    final db = await database;
    return await db.insert('t_stocks', stock.toMap());
  }

  Future<List<Stock>> getStocksByAccount(int accountId) async {
    final db = await database;
    final maps = await db.query('t_stocks',
        where: 'account_id = ?',
        whereArgs: [accountId],
        orderBy: 'created_at DESC');
    return maps.map((m) => Stock.fromMap(m)).toList();
  }

  Future<int> deleteStock(int id) async {
    final db = await database;
    return await db.delete('t_stocks', where: 'id = ?', whereArgs: [id]);
  }

  Future<int> updateStock(Stock stock) async {
    final db = await database;
    return await db.update('t_stocks', stock.toMap(),
        where: 'id = ?', whereArgs: [stock.id]);
  }

  // ========== TransactionTrade CRUD ==========
  Future<int> insertTransactionTrade(TransactionTrade t) async {
    final db = await database;
    return await db.insert('t_transaction_trades', t.toMap());
  }

  Future<int> updateTransactionTrade(TransactionTrade t) async {
    final db = await database;
    return await db.update('t_transaction_trades', t.toMap(),
        where: 'id = ?', whereArgs: [t.id]);
  }

  Future<int> deleteTransactionTrade(int id) async {
    final db = await database;
    return await db.delete('t_transaction_trades', where: 'id = ?', whereArgs: [id]);
  }

  Future<List<TransactionTrade>> getTransactionTradesByStock(int stockId, String sort) async {
    final db = await database;
    final maps = await db.query('t_transaction_trades',
        where: 'stock_id = ?',
        whereArgs: [stockId],
        orderBy: 'date $sort');
    return maps.map((m) => TransactionTrade.fromMap(m)).toList();
  }

  Future<TransactionTrade?> getTransactionTradeById(int id) async {
    final db = await database;
    final maps =
        await db.query('t_transaction_trades', where: 'id = ?', whereArgs: [id]);
    if (maps.isEmpty) return null;
    return TransactionTrade.fromMap(maps.first);
  }

  /// 获取某只股票的可关联买入记录（未完全被做T关联的）
  Future<List<TransactionTrade>> getAvailableBuyTransactionTrades(
      int stockId, int? excludeSellId) async {
    final db = await database;
    final buys = await db.query('t_transaction_trades',
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
        if (tt['buy_transaction_id'] == t.id &&
            tt['sell_transaction_id'] != excludeSellId) {
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
      JOIN t_transaction_trades b ON tt.buy_transaction_id = b.id
      JOIN t_transaction_trades s ON tt.sell_transaction_id = s.id
      WHERE b.stock_id = ?
      ORDER BY tt.created_at ASC
    ''', [stockId]);
    return result;
  }

  /// 删除某笔卖出关联的所有做T记录
  Future<void> deleteTTradesBySellId(int sellId) async {
    final db = await database;
    await db.delete('t_trades',
        where: 'sell_transaction_id = ?', whereArgs: [sellId]);
  }

  // ========== 收益统计 ==========

  /// 股票持仓汇总
  Future<Map<String, double>> getStockSummary(int stockId) async {
    final db = await database;
    final result = await db.rawQuery('''
      SELECT 
        COALESCE(SUM(shares), 0) as total_shares,
        COALESCE(SUM(-price * shares - commission), 0) as total_cost
      FROM t_transaction_trades
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
    final transactions = await getTransactionTradesByStock(stockId, 'ASC');

    double allTimeCost = 0; // 总收益
    int allTimeShares = 0; // 总持仓
    double currentCycleCost = 0; // 持仓收益
    bool inCycle = false; // 是否新建仓

    for (final t in transactions) {
      allTimeCost += t.cost;
      allTimeShares += t.shares;

      if (t.type == '买入') {
        if (!inCycle && t.shares > 0) {
          currentCycleCost = 0;
          inCycle = true;
        }
        currentCycleCost += t.cost;
      } else {
        currentCycleCost += t.cost;

        if (allTimeShares == 0) {  // 清仓
          currentCycleCost = 0;
          inCycle = false;
        }
      }
    }

    if (allTimeShares == 0) {  // 清仓
      currentCycleCost = 0;
      inCycle = false;
    }

    final double avgCost =
        allTimeShares > 0 ? (currentCycleCost / allTimeShares).abs() : 0;
    final double allTimeAvgCost =
        allTimeShares != 0 ? (allTimeCost / allTimeShares).abs() : 0;

    return {
      'total_shares': allTimeShares.toDouble(),
      'total_cost': allTimeCost,
      'avg_cost': avgCost,
      'cycle_cost': currentCycleCost,
      'total_avg_cost': allTimeAvgCost,
    };
  }

  /// 账户维度收益
  Future<Map<String, double>> getAccountProfit(int accountId) async {
    final db = await database;
    final result = await db.rawQuery('''
      SELECT COALESCE(SUM(-t.price * t.shares - t.commission), 0) as profit
      FROM t_transaction_trades t
      JOIN t_stocks s ON t.stock_id = s.id
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
      JOIN t_transaction_trades b ON tt.buy_transaction_id = b.id
      JOIN t_transaction_trades s ON tt.sell_transaction_id = s.id
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

  // ========== AccountItem (密码管理) CRUD ==========

  Future<void> insertAccountItem(AccountItem item) async {
    final db = await database;
    await db.insert('t_password_account', {
      'id': item.id,
      'app_name': item.appName,
      'username': item.username,
      'password': item.password,
      'created_at': item.createdAt.toIso8601String(),
    });
  }

  Future<void> updateAccountItem(AccountItem item) async {
    final db = await database;
    await db.update(
      't_password_account',
      {
        'app_name': item.appName,
        'username': item.username,
        'password': item.password,
        'created_at': item.createdAt.toIso8601String(),
      },
      where: 'id = ?',
      whereArgs: [item.id],
    );
  }

  Future<void> deleteAccountItem(String id) async {
    final db = await database;
    await db.delete('t_password_account', where: 'id = ?', whereArgs: [id]);
  }

  Future<List<AccountItem>> getAccountItems() async {
    final db = await database;
    final maps = await db.query('t_password_account', orderBy: 'created_at DESC');
    return maps.map((m) => AccountItem.fromMap({
      'id': m['id'],
      'appName': m['app_name'],
      'username': m['username'],
      'password': m['password'],
      'createdAt': m['created_at'],
    })).toList();
  }

  Future<void> saveAllAccountItems(List<AccountItem> items) async {
    final db = await database;
    await db.transaction((txn) async {
      await txn.delete('t_password_account');
      for (final item in items) {
        await txn.insert('t_password_account', {
          'id': item.id,
          'app_name': item.appName,
          'username': item.username,
          'password': item.password,
          'created_at': item.createdAt.toIso8601String(),
        });
      }
    });
  }
}