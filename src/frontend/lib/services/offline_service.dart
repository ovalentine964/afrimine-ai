import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../models/analysis.dart';
import '../models/sample.dart';

final offlineServiceProvider = Provider<OfflineService>((ref) {
  final service = OfflineService();
  ref.onDispose(() => service.close());
  return service;
});

/// Offline-first SQLite storage with sync queue.
///
/// Stores samples, analyses, and knowledge locally so the app
/// works fully offline. When connectivity returns, sync queue
/// items are uploaded to the Go backend.
class OfflineService {
  static const _dbName = 'afrimine_offline.db';
  static const _dbVersion = 1;
  static const _maxCachedSamples = 500;
  static const _maxCachedAnalyses = 200;

  Database? _db;

  // ===========================================================================
  // INITIALIZATION
  // ===========================================================================

  Future<void> initialize() async {
    final dbPath = p.join(await getDatabasesPath(), _dbName);
    _db = await openDatabase(
      dbPath,
      version: _dbVersion,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  Future<void> _onCreate(Database db, int version) async {
    // Samples table
    await db.execute('''
      CREATE TABLE samples (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        location_json TEXT,
        photo_paths TEXT,
        photo_urls TEXT,
        xrf_readings_json TEXT,
        field_notes TEXT,
        voice_note_path TEXT,
        voice_note_url TEXT,
        is_synced INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        vector_clock_json TEXT
      )
    ''');

    // Analyses table
    await db.execute('''
      CREATE TABLE analyses (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        sample_ids TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        agent_outputs_json TEXT,
        detected_minerals TEXT,
        estimated_grade REAL,
        grade_unit TEXT,
        confidence_score REAL,
        estimated_value_usd REAL,
        report_url TEXT,
        report_html TEXT,
        pipeline_duration_ms INTEGER,
        is_synced INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        completed_at TEXT
      )
    ''');

    // Sync queue table
    await db.execute('''
      CREATE TABLE sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL CHECK (action IN ('create', 'update', 'delete')),
        data_json TEXT,
        created_at TEXT NOT NULL,
        retry_count INTEGER NOT NULL DEFAULT 0,
        last_error TEXT
      )
    ''');

    // Cached knowledge snippets
    await db.execute('''
      CREATE TABLE cached_knowledge (
        knowledge_id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        content_json TEXT NOT NULL,
        search_text TEXT NOT NULL,
        cached_at TEXT NOT NULL
      )
    ''');

    // Settings
    await db.execute('''
      CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    ''');

    // Indexes
    await db.execute(
      'CREATE INDEX idx_samples_synced ON samples (is_synced) WHERE is_synced = 0',
    );
    await db.execute(
      'CREATE INDEX idx_samples_created ON samples (created_at DESC)',
    );
    await db.execute(
      'CREATE INDEX idx_analyses_status ON analyses (status, created_at DESC)',
    );
    await db.execute(
      'CREATE INDEX idx_analyses_synced ON analyses (is_synced) WHERE is_synced = 0',
    );
    await db.execute(
      'CREATE INDEX idx_sync_pending ON sync_queue (created_at)',
    );
  }

  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    // Future migrations go here
  }

  Database get db {
    if (_db == null) {
      throw StateError('OfflineService not initialized. Call initialize() first.');
    }
    return _db!;
  }

  // ===========================================================================
  // SAMPLES
  // ===========================================================================

  /// Save a sample locally.
  Future<void> saveSample(MineralSample sample) async {
    await db.insert(
      'samples',
      {
        'id': sample.id,
        'user_id': sample.userId,
        'location_json': sample.location != null ? jsonEncode(sample.location!.toJson()) : null,
        'photo_paths': jsonEncode(sample.photoPaths),
        'photo_urls': jsonEncode(sample.photoUrls),
        'xrf_readings_json': sample.xrfReadings != null ? jsonEncode(sample.xrfReadings!.toJson()) : null,
        'field_notes': sample.fieldNotes,
        'voice_note_path': sample.voiceNotePath,
        'voice_note_url': sample.voiceNoteUrl,
        'is_synced': sample.isSynced ? 1 : 0,
        'created_at': sample.createdAt.toIso8601String(),
        'updated_at': sample.updatedAt.toIso8601String(),
        'vector_clock_json': sample.vectorClock != null ? jsonEncode(sample.vectorClock) : null,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Get cached samples.
  Future<List<MineralSample>> getCachedSamples({int limit = 20, int offset = 0}) async {
    final rows = await db.query(
      'samples',
      orderBy: 'created_at DESC',
      limit: limit,
      offset: offset,
    );
    return rows.map(_rowToSample).toList();
  }

  /// Get a single cached sample.
  Future<MineralSample?> getCachedSample(String id) async {
    final rows = await db.query('samples', where: 'id = ?', whereArgs: [id], limit: 1);
    if (rows.isEmpty) return null;
    return _rowToSample(rows.first);
  }

  /// Get unsynced samples count.
  Future<int> getUnsyncedSampleCount() async {
    final result = await db.rawQuery('SELECT COUNT(*) FROM samples WHERE is_synced = 0');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  MineralSample _rowToSample(Map<String, dynamic> row) {
    return MineralSample(
      id: row['id'] as String,
      userId: row['user_id'] as String?,
      location: row['location_json'] != null
          ? SampleLocation.fromJson(jsonDecode(row['location_json'] as String))
          : null,
      photoPaths: (jsonDecode(row['photo_paths'] as String? ?? '[]') as List).cast<String>(),
      photoUrls: (jsonDecode(row['photo_urls'] as String? ?? '[]') as List).cast<String>(),
      xrfReadings: row['xrf_readings_json'] != null
          ? XrfReadings.fromJson(jsonDecode(row['xrf_readings_json'] as String))
          : null,
      fieldNotes: row['field_notes'] as String?,
      voiceNotePath: row['voice_note_path'] as String?,
      voiceNoteUrl: row['voice_note_url'] as String?,
      isSynced: row['is_synced'] == 1,
      createdAt: DateTime.parse(row['created_at'] as String),
      updatedAt: DateTime.parse(row['updated_at'] as String),
      vectorClock: row['vector_clock_json'] != null
          ? jsonDecode(row['vector_clock_json'] as String) as Map<String, dynamic>
          : null,
    );
  }

  // ===========================================================================
  // ANALYSES
  // ===========================================================================

  /// Save an analysis locally.
  Future<void> saveAnalysis(Analysis analysis) async {
    await db.insert(
      'analyses',
      {
        'id': analysis.id,
        'user_id': analysis.userId,
        'sample_ids': jsonEncode(analysis.sampleIds),
        'status': analysis.status.name,
        'agent_outputs_json': jsonEncode({
          if (analysis.analysisResult != null) 'analysis_result': analysis.analysisResult!.rawOutput,
          if (analysis.geologyResult != null) 'geology_result': analysis.geologyResult!.rawOutput,
          if (analysis.marketResult != null) 'market_result': analysis.marketResult!.rawOutput,
          if (analysis.complianceResult != null) 'compliance_result': analysis.complianceResult!.rawOutput,
        }),
        'detected_minerals': jsonEncode(analysis.analysisResult?.detectedMinerals ?? []),
        'estimated_grade': analysis.estimatedGrade,
        'grade_unit': analysis.gradeUnit,
        'confidence_score': analysis.confidenceScore,
        'estimated_value_usd': analysis.estimatedValueUsd,
        'report_url': analysis.reportUrl,
        'report_html': analysis.reportHtml,
        'pipeline_duration_ms': analysis.pipelineDurationMs,
        'is_synced': analysis.isSynced ? 1 : 0,
        'created_at': analysis.createdAt.toIso8601String(),
        'completed_at': analysis.completedAt?.toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Get cached analyses.
  Future<List<Analysis>> getCachedAnalyses({int limit = 20, int offset = 0}) async {
    final rows = await db.query(
      'analyses',
      orderBy: 'created_at DESC',
      limit: limit,
      offset: offset,
    );
    return rows.map(_rowToAnalysis).toList();
  }

  /// Get a single cached analysis.
  Future<Analysis?> getCachedAnalysis(String id) async {
    final rows = await db.query('analyses', where: 'id = ?', whereArgs: [id], limit: 1);
    if (rows.isEmpty) return null;
    return _rowToAnalysis(rows.first);
  }

  Analysis _rowToAnalysis(Map<String, dynamic> row) {
    final agentOutputs = row['agent_outputs_json'] != null
        ? jsonDecode(row['agent_outputs_json'] as String) as Map<String, dynamic>
        : <String, dynamic>{};

    return Analysis(
      id: row['id'] as String,
      userId: row['user_id'] as String?,
      sampleIds: (jsonDecode(row['sample_ids'] as String? ?? '[]') as List).cast<String>(),
      status: AnalysisStatus.fromString(row['status'] as String),
      analysisResult: agentOutputs['analysis_result'] != null
          ? AnalysisResult.fromJson(agentOutputs['analysis_result'] as Map<String, dynamic>)
          : null,
      geologyResult: agentOutputs['geology_result'] != null
          ? GeologyResult.fromJson(agentOutputs['geology_result'] as Map<String, dynamic>)
          : null,
      marketResult: agentOutputs['market_result'] != null
          ? MarketResult.fromJson(agentOutputs['market_result'] as Map<String, dynamic>)
          : null,
      complianceResult: agentOutputs['compliance_result'] != null
          ? ComplianceResult.fromJson(agentOutputs['compliance_result'] as Map<String, dynamic>)
          : null,
      reportUrl: row['report_url'] as String?,
      reportHtml: row['report_html'] as String?,
      estimatedGrade: (row['estimated_grade'] as num?)?.toDouble(),
      gradeUnit: row['grade_unit'] as String?,
      confidenceScore: (row['confidence_score'] as num?)?.toDouble(),
      estimatedValueUsd: (row['estimated_value_usd'] as num?)?.toDouble(),
      pipelineDurationMs: row['pipeline_duration_ms'] as int?,
      isSynced: row['is_synced'] == 1,
      createdAt: DateTime.parse(row['created_at'] as String),
      completedAt: row['completed_at'] != null
          ? DateTime.tryParse(row['completed_at'] as String)
          : null,
    );
  }

  // ===========================================================================
  // SYNC QUEUE
  // ===========================================================================

  /// Add an item to the sync queue.
  Future<void> enqueueSync(
    String entityType,
    String entityId,
    String action,
    Map<String, dynamic> data,
  ) async {
    await db.insert('sync_queue', {
      'entity_type': entityType,
      'entity_id': entityId,
      'action': action,
      'data_json': jsonEncode(data),
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'retry_count': 0,
    });
  }

  /// Get pending sync items.
  Future<List<Map<String, dynamic>>> getPendingSyncItems({int limit = 50}) async {
    return db.query(
      'sync_queue',
      orderBy: 'created_at ASC',
      limit: limit,
    );
  }

  /// Get count of pending sync items.
  Future<int> getPendingSyncCount() async {
    final result = await db.rawQuery('SELECT COUNT(*) FROM sync_queue');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  /// Remove a sync item after successful upload.
  Future<void> removeSyncItem(int id) async {
    await db.delete('sync_queue', where: 'id = ?', whereArgs: [id]);
  }

  /// Increment retry count for a sync item.
  Future<void> incrementSyncRetry(int id) async {
    await db.rawUpdate(
      'UPDATE sync_queue SET retry_count = retry_count + 1 WHERE id = ?',
      [id],
    );
  }

  /// Get sync stats.
  Future<Map<String, int>> getSyncStats() async {
    final pending = await getPendingSyncCount();
    final unsyncedSamples = await getUnsyncedSampleCount();
    final unsyncedAnalyses = Sqflite.firstIntValue(
      await db.rawQuery('SELECT COUNT(*) FROM analyses WHERE is_synced = 0'),
    ) ?? 0;

    return {
      'pending_sync': pending,
      'unsynced_samples': unsyncedSamples,
      'unsynced_analyses': unsyncedAnalyses,
    };
  }

  // ===========================================================================
  // KNOWLEDGE CACHE
  // ===========================================================================

  /// Cache a knowledge snippet for offline access.
  Future<void> cacheKnowledge(Map<String, dynamic> knowledge) async {
    await db.insert(
      'cached_knowledge',
      {
        'knowledge_id': knowledge['knowledge_id'] ?? _generateId(),
        'category': knowledge['category'] ?? 'general',
        'title': knowledge['title'] ?? '',
        'content_json': jsonEncode(knowledge['content'] ?? knowledge),
        'search_text': '${knowledge['title'] ?? ''} ${knowledge['description'] ?? ''}'.toLowerCase(),
        'cached_at': DateTime.now().toUtc().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Search cached knowledge.
  Future<List<Map<String, dynamic>>> searchKnowledge(String query, {int limit = 5}) async {
    final rows = await db.query(
      'cached_knowledge',
      where: 'search_text LIKE ?',
      whereArgs: ['%${query.toLowerCase()}%'],
      orderBy: 'cached_at DESC',
      limit: limit,
    );
    return rows.map((row) {
      return {
        ...row,
        'content': jsonDecode(row['content_json'] as String),
      };
    }).toList();
  }

  // ===========================================================================
  // SETTINGS
  // ===========================================================================

  /// Save a setting.
  Future<void> saveSetting(String key, String value) async {
    await db.insert(
      'settings',
      {
        'key': key,
        'value': value,
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Get a setting.
  Future<String?> getSetting(String key) async {
    final rows = await db.query('settings', where: 'key = ?', whereArgs: [key], limit: 1);
    if (rows.isEmpty) return null;
    return rows.first['value'] as String;
  }

  /// Get all settings.
  Future<Map<String, String>> getAllSettings() async {
    final rows = await db.query('settings');
    return {for (final row in rows) row['key'] as String: row['value'] as String};
  }

  // ===========================================================================
  // UTILITIES
  // ===========================================================================

  String _generateId() {
    final random = Random();
    final timestamp = DateTime.now().millisecondsSinceEpoch.toRadixString(36);
    final randomPart = random.nextInt(0xFFFFFF).toRadixString(36).padLeft(5, '0');
    return '$timestamp-$randomPart';
  }

  /// Clear all local data (for logout).
  Future<void> clearAll() async {
    await db.delete('samples');
    await db.delete('analyses');
    await db.delete('sync_queue');
    await db.delete('cached_knowledge');
    // Keep settings
  }

  /// Close the database connection.
  Future<void> close() async {
    await _db?.close();
    _db = null;
  }
}
