import 'dart:async';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/sample_model.dart';
import '../models/sync_item_model.dart';
import '../utils/constants.dart';

class DatabaseService {
  static DatabaseService? _instance;
  static Database? _database;

  DatabaseService._();

  factory DatabaseService() {
    _instance ??= DatabaseService._();
    return _instance!;
  }

  Future<Database> get database async {
    _database ??= await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, AppConstants.dbName);

    return await openDatabase(
      path,
      version: AppConstants.dbVersion,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
      CREATE TABLE samples (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        image_path TEXT,
        image_url TEXT,
        latitude REAL,
        longitude REAL,
        accuracy REAL,
        mineral_type TEXT,
        confidence REAL,
        grade_estimate REAL,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        field_tests TEXT,
        ai_results TEXT,
        synced INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE sync_queue (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        data TEXT,
        retry_count INTEGER DEFAULT 0,
        last_error TEXT,
        created_at TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE market_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mineral TEXT NOT NULL,
        price_per_oz REAL NOT NULL,
        change_percent REAL,
        change_absolute REAL,
        currency TEXT DEFAULT 'USD',
        last_updated TEXT NOT NULL,
        source TEXT
      )
    ''');

    await db.execute('CREATE INDEX idx_samples_user ON samples(user_id)');
    await db.execute('CREATE INDEX idx_samples_status ON samples(status)');
    await db.execute('CREATE INDEX idx_sync_queue_entity ON sync_queue(entity_type, entity_id)');
  }

  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    // Handle migrations here
  }

  // ========== SAMPLES ==========

  Future<void> insertSample(SampleModel sample) async {
    final db = await database;
    await db.insert(
      'samples',
      sample.toDbMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> updateSample(SampleModel sample) async {
    final db = await database;
    await db.update(
      'samples',
      sample.toDbMap(),
      where: 'id = ?',
      whereArgs: [sample.id],
    );
  }

  Future<void> deleteSample(String id) async {
    final db = await database;
    await db.delete('samples', where: 'id = ?', whereArgs: [id]);
  }

  Future<SampleModel?> getSample(String id) async {
    final db = await database;
    final maps = await db.query('samples', where: 'id = ?', whereArgs: [id]);
    if (maps.isEmpty) return null;
    return SampleModel.fromDbMap(maps.first);
  }

  Future<List<SampleModel>> getAllSamples({String? userId, String? status}) async {
    final db = await database;
    String? where;
    List<dynamic>? whereArgs;

    if (userId != null && status != null) {
      where = 'user_id = ? AND status = ?';
      whereArgs = [userId, status];
    } else if (userId != null) {
      where = 'user_id = ?';
      whereArgs = [userId];
    } else if (status != null) {
      where = 'status = ?';
      whereArgs = [status];
    }

    final maps = await db.query(
      'samples',
      where: where,
      whereArgs: whereArgs,
      orderBy: 'created_at DESC',
    );

    return maps.map((map) => SampleModel.fromDbMap(map)).toList();
  }

  Future<List<SampleModel>> getUnsyncedSamples() async {
    final db = await database;
    final maps = await db.query('samples', where: 'synced = 0', orderBy: 'created_at ASC');
    return maps.map((map) => SampleModel.fromDbMap(map)).toList();
  }

  Future<int> getSampleCount({String? userId, String? status}) async {
    final db = await database;
    String? where;
    List<dynamic>? whereArgs;

    if (userId != null && status != null) {
      where = 'user_id = ? AND status = ?';
      whereArgs = [userId, status];
    } else if (userId != null) {
      where = 'user_id = ?';
      whereArgs = [userId];
    } else if (status != null) {
      where = 'status = ?';
      whereArgs = [status];
    }

    final result = await db.rawQuery(
      'SELECT COUNT(*) as count FROM samples${where != null ? ' WHERE $where' : ''}',
      whereArgs,
    );
    return Sqflite.firstIntValue(result) ?? 0;
  }

  // ========== SYNC QUEUE ==========

  Future<void> addToSyncQueue(SyncItemModel item) async {
    final db = await database;
    await db.insert('sync_queue', item.toDbMap(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> removeFromSyncQueue(String id) async {
    final db = await database;
    await db.delete('sync_queue', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> updateSyncItem(SyncItemModel item) async {
    final db = await database;
    await db.update('sync_queue', item.toDbMap(), where: 'id = ?', whereArgs: [item.id]);
  }

  Future<List<SyncItemModel>> getPendingSyncItems() async {
    final db = await database;
    final maps = await db.query('sync_queue', orderBy: 'created_at ASC');
    return maps.map((map) => SyncItemModel.fromDbMap(map)).toList();
  }

  Future<int> getPendingSyncCount() async {
    final db = await database;
    final result = await db.rawQuery('SELECT COUNT(*) as count FROM sync_queue');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  Future<void> clearSyncQueue() async {
    final db = await database;
    await db.delete('sync_queue');
  }

  // ========== MARKET PRICES ==========

  Future<void> saveMarketPrices(List<Map<String, dynamic>> prices) async {
    final db = await database;
    await db.delete('market_prices');
    for (final price in prices) {
      await db.insert('market_prices', price);
    }
  }

  Future<List<Map<String, dynamic>>> getMarketPrices() async {
    final db = await database;
    return await db.query('market_prices', orderBy: 'mineral ASC');
  }

  // ========== UTILITIES ==========

  Future<void> clearAll() async {
    final db = await database;
    await db.delete('samples');
    await db.delete('sync_queue');
    await db.delete('market_prices');
  }

  Future<void> close() async {
    final db = await database;
    await db.close();
    _database = null;
  }
}
