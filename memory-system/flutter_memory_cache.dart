// =============================================================================
// AfriMine AI — Flutter Offline Memory Cache
//
// Local SQLite cache that mirrors the Supabase memory system.
// Enables offline-first: field workers can analyze samples without internet,
// then sync when connectivity returns.
//
// Dependencies:
//   sqflite: ^2.3.0
//   path: ^1.8.0
//   http: ^1.2.0
//   connectivity_plus: ^6.0.0
//
// Usage:
//   final cache = MemoryCache();
//   await cache.initialize();
//
//   // Save analysis locally
//   await cache.saveAnalysis(analysisData);
//
//   // Search cached analyses
//   final similar = await cache.findSimilarAnalyses('gold quartz migori');
//
//   // Sync with Supabase when online
//   await cache.syncToSupabase(supabaseUrl, supabaseToken);
// =============================================================================

import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;
import 'package:http/http.dart' as http;

/// Offline memory cache for AfriMine AI.
///
/// Stores analyses, knowledge snippets, and pending sync items locally.
/// Uses SQLite for persistence and simple text matching for local search.
class MemoryCache {
  static const String _dbName = 'afrimine_memory.db';
  static const int _dbVersion = 1;
  static const int _maxCachedAnalyses = 200;
  static const int _maxCachedKnowledge = 500;

  Database? _db;

  // ===========================================================================
  // Initialization
  // ===========================================================================

  /// Initialize the local SQLite database.
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
    // Cached analyses
    await db.execute('''
      CREATE TABLE cached_analyses (
        analysis_id TEXT PRIMARY KEY,
        session_id TEXT,
        user_id TEXT NOT NULL,
        mineral_type TEXT,
        location_json TEXT,
        sample_data_json TEXT,
        detected_minerals_json TEXT,
        estimated_grade REAL,
        grade_unit TEXT,
        confidence_score REAL,
        estimated_value REAL,
        agent_outputs_json TEXT NOT NULL,
        embedding_json TEXT,
        search_text TEXT NOT NULL,
        is_synced INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
      )
    ''');

    // Cached knowledge (snippets from geological knowledge base)
    await db.execute('''
      CREATE TABLE cached_knowledge (
        knowledge_id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        content_json TEXT NOT NULL,
        related_minerals_json TEXT,
        embedding_json TEXT,
        search_text TEXT NOT NULL,
        cached_at TEXT NOT NULL
      )
    ''');

    // Pending sync queue (items to upload when online)
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

    // Cached user preferences / long-term memory
    await db.execute('''
      CREATE TABLE cached_ltm (
        namespace TEXT NOT NULL,
        key TEXT NOT NULL,
        value_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (namespace, key)
      )
    ''');

    // Full-text search index for analyses
    await db.execute('''
      CREATE VIRTUAL TABLE analyses_fts USING fts5(
        analysis_id, search_text, mineral_type, location_region,
        content=cached_analyses, content_rowid=rowid
      )
    ''');

    // Full-text search index for knowledge
    await db.execute('''
      CREATE VIRTUAL TABLE knowledge_fts USING fts5(
        knowledge_id, search_text, category,
        content=cached_knowledge, content_rowid=rowid
      )
    ''');

    // Indexes
    await db.execute(
      'CREATE INDEX idx_analyses_synced ON cached_analyses (is_synced) WHERE is_synced = 0'
    );
    await db.execute(
      'CREATE INDEX idx_analyses_mineral ON cached_analyses (mineral_type, created_at DESC)'
    );
    await db.execute(
      'CREATE INDEX idx_sync_queue_pending ON sync_queue (created_at)'
    );
  }

  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    // Handle schema migrations here
  }

  Database get db {
    if (_db == null) throw StateError('MemoryCache not initialized. Call initialize() first.');
    return _db!;
  }

  // ===========================================================================
  // ANALYSIS CACHE (Episodic Memory — Local)
  // ===========================================================================

  /// Save an analysis to the local cache.
  Future<void> saveAnalysis(Map<String, dynamic> analysis) async {
    final now = DateTime.now().toUtc().toIso8601String();
    final analysisId = analysis['analysis_id'] as String? ?? _generateId();

    // Build search text for FTS
    final searchText = _buildAnalysisSearchText(analysis);

    // Extract location region
    final location = analysis['location'] as Map<String, dynamic>? ?? {};
    final region = location['region'] as String? ?? '';

    // Serialize agent outputs
    final agentOutputs = <String, dynamic>{};
    for (final agent in ['sampling', 'analysis', 'geology', 'market', 'report', 'compliance']) {
      final key = '${agent}_output';
      if (analysis[key] != null) {
        agentOutputs[key] = analysis[key];
      }
      final resultKey = '${agent}_result';
      if (analysis[resultKey] != null) {
        agentOutputs[resultKey] = analysis[resultKey];
      }
    }

    await db.insert(
      'cached_analyses',
      {
        'analysis_id': analysisId,
        'session_id': analysis['session_id'],
        'user_id': analysis['user_id'] ?? 'local',
        'mineral_type': analysis['mineral_type'],
        'location_json': jsonEncode(location),
        'sample_data_json': jsonEncode(analysis['sample_data'] ?? {}),
        'detected_minerals_json': jsonEncode(analysis['detected_minerals'] ?? []),
        'estimated_grade': analysis['estimated_grade'],
        'grade_unit': analysis['grade_unit'],
        'confidence_score': analysis['confidence_score'],
        'estimated_value': analysis['estimated_value'],
        'agent_outputs_json': jsonEncode(agentOutputs),
        'embedding_json': null, // Embeddings computed server-side
        'search_text': searchText,
        'is_synced': analysis['is_synced'] == true ? 1 : 0,
        'created_at': analysis['created_at'] ?? now,
        'updated_at': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );

    // Update FTS index
    await _updateAnalysisFts(analysisId, searchText, analysis['mineral_type'], region);

    // Add to sync queue if not synced
    if (analysis['is_synced'] != true) {
      await _enqueueSync('analysis', analysisId, 'create', analysis);
    }

    // Enforce cache limit
    await _enforceAnalysisLimit();
  }

  /// Find cached analyses matching a text query (local FTS search).
  Future<List<Map<String, dynamic>>> findSimilarAnalyses(
    String query, {
    int limit = 10,
    String? mineralFilter,
  }) async {
    // Try FTS first
    String ftsQuery = query.split(' ').map((w) => '"$w"').join(' OR ');

    String sql = '''
      SELECT a.* FROM cached_analyses a
      JOIN analyses_fts fts ON a.analysis_id = fts.analysis_id
      WHERE analyses_fts MATCH ?
    ''';
    final params = <dynamic>[ftsQuery];

    if (mineralFilter != null) {
      sql += ' AND a.mineral_type = ?';
      params.add(mineralFilter);
    }

    sql += ' ORDER BY a.confidence_score DESC LIMIT ?';
    params.add(limit);

    try {
      final results = await db.rawQuery(sql, params);
      return results.map(_deserializeAnalysis).toList();
    } catch (e) {
      // Fallback to LIKE search if FTS fails
      return _fallbackSearch(query, limit: limit, mineralFilter: mineralFilter);
    }
  }

  Future<List<Map<String, dynamic>>> _fallbackSearch(
    String query, {
    int limit = 10,
    String? mineralFilter,
  }) async {
    String sql = '''
      SELECT * FROM cached_analyses
      WHERE search_text LIKE ?
    ''';
    final params = <dynamic>['%${query.toLowerCase()}%'];

    if (mineralFilter != null) {
      sql += ' AND mineral_type = ?';
      params.add(mineralFilter);
    }

    sql += ' ORDER BY confidence_score DESC LIMIT ?';
    params.add(limit);

    final results = await db.rawQuery(sql, params);
    return results.map(_deserializeAnalysis).toList();
  }

  /// Get a specific cached analysis.
  Future<Map<String, dynamic>?> getAnalysis(String analysisId) async {
    final results = await db.query(
      'cached_analyses',
      where: 'analysis_id = ?',
      whereArgs: [analysisId],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return _deserializeAnalysis(results.first);
  }

  /// Get recent analyses (cached locally).
  Future<List<Map<String, dynamic>>> getRecentAnalyses({
    int limit = 20,
    int offset = 0,
  }) async {
    final results = await db.query(
      'cached_analyses',
      orderBy: 'created_at DESC',
      limit: limit,
      offset: offset,
    );
    return results.map(_deserializeAnalysis).toList();
  }

  Map<String, dynamic> _deserializeAnalysis(Map<String, dynamic> row) {
    return {
      ...row,
      'location': _tryDecodeJson(row['location_json']),
      'sample_data': _tryDecodeJson(row['sample_data_json']),
      'detected_minerals': _tryDecodeJson(row['detected_minerals_json']),
      'agent_outputs': _tryDecodeJson(row['agent_outputs_json']),
      'is_synced': row['is_synced'] == 1,
    };
  }

  // ===========================================================================
  // KNOWLEDGE CACHE (Semantic Memory — Local)
  // ===========================================================================

  /// Cache geological knowledge snippets for offline access.
  Future<void> cacheKnowledge(Map<String, dynamic> knowledge) async {
    final searchText = '${knowledge['title']} ${knowledge['description']}';
    final now = DateTime.now().toUtc().toIso8601String();

    await db.insert(
      'cached_knowledge',
      {
        'knowledge_id': knowledge['knowledge_id'],
        'category': knowledge['category'],
        'title': knowledge['title'],
        'description': knowledge['description'],
        'content_json': jsonEncode(knowledge['content'] ?? {}),
        'related_minerals_json': jsonEncode(knowledge['related_minerals'] ?? []),
        'embedding_json': null,
        'search_text': searchText.toLowerCase(),
        'cached_at': now,
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );

    // Enforce cache limit
    final count = Sqflite.firstIntValue(
      await db.rawQuery('SELECT COUNT(*) FROM cached_knowledge')
    ) ?? 0;

    if (count > _maxCachedKnowledge) {
      await db.rawDelete(
        'DELETE FROM cached_knowledge WHERE knowledge_id IN '
        '(SELECT knowledge_id FROM cached_knowledge ORDER BY cached_at ASC LIMIT ?)',
        [count - _maxCachedKnowledge],
      );
    }
  }

  /// Search cached knowledge by text.
  Future<List<Map<String, dynamic>>> searchKnowledge(
    String query, {
    String? category,
    int limit = 5,
  }) async {
    String sql = '''
      SELECT * FROM cached_knowledge
      WHERE search_text LIKE ?
    ''';
    final params = <dynamic>['%${query.toLowerCase()}%'];

    if (category != null) {
      sql += ' AND category = ?';
      params.add(category);
    }

    sql += ' ORDER BY cached_at DESC LIMIT ?';
    params.add(limit);

    final results = await db.rawQuery(sql, params);
    return results.map((row) {
      return {
        ...row,
        'content': _tryDecodeJson(row['content_json']),
        'related_minerals': _tryDecodeJson(row['related_minerals_json']),
      };
    }).toList();
  }

  /// Get cached pathfinder elements for a mineral.
  Future<List<Map<String, dynamic>>> getCachedPathfinders(String mineral) async {
    final results = await db.query(
      'cached_knowledge',
      where: "category = 'pathfinder_element' AND search_text LIKE ?",
      whereArgs: ['%$mineral%'],
    );

    return results.map((row) {
      final content = _tryDecodeJson(row['content_json']) as Map<String, dynamic>? ?? {};
      return {
        ...row,
        'content': content,
        'pathfinder': content['pathfinder'],
        'threshold_ppm': content['threshold_ppm'],
      };
    }).toList();
  }

  // ===========================================================================
  // LONG-TERM MEMORY CACHE
  // ===========================================================================

  /// Cache a long-term memory fact locally.
  Future<void> cacheLtm(String namespace, String key, dynamic value) async {
    await db.insert(
      'cached_ltm',
      {
        'namespace': namespace,
        'key': key,
        'value_json': jsonEncode(value),
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Retrieve a cached long-term memory fact.
  Future<dynamic> getCachedLtm(String namespace, String key) async {
    final results = await db.query(
      'cached_ltm',
      where: 'namespace = ? AND key = ?',
      whereArgs: [namespace, key],
      limit: 1,
    );
    if (results.isEmpty) return null;
    return _tryDecodeJson(results.first['value_json']);
  }

  /// Get all cached facts in a namespace.
  Future<Map<String, dynamic>> getCachedLtmNamespace(String namespace) async {
    final results = await db.query(
      'cached_ltm',
      where: 'namespace = ?',
      whereArgs: [namespace],
    );
    final map = <String, dynamic>{};
    for (final row in results) {
      map[row['key'] as String] = _tryDecodeJson(row['value_json']);
    }
    return map;
  }

  // ===========================================================================
  // SYNC (Offline → Online)
  // ===========================================================================

  /// Sync pending items to Supabase. Returns {uploaded, failed}.
  Future<Map<String, int>> syncToSupabase(String supabaseUrl, String supabaseToken) async {
    int uploaded = 0;
    int failed = 0;

    final pending = await db.query(
      'sync_queue',
      orderBy: 'created_at ASC',
      limit: 50,
    );

    for (final item in pending) {
      final entityType = item['entity_type'] as String;
      final entityId = item['entity_id'] as String;
      final action = item['action'] as String;
      final data = _tryDecodeJson(item['data_json']);
      final retryCount = item['retry_count'] as int;

      if (retryCount >= 3) {
        // Give up after 3 retries
        continue;
      }

      try {
        bool success = false;

        if (entityType == 'analysis' && action == 'create') {
          // Upload analysis to Supabase
          final response = await http.post(
            Uri.parse('$supabaseUrl/rest/v1/analysis_history'),
            headers: {
              'Authorization': 'Bearer $supabaseToken',
              'apikey': supabaseToken,
              'Content-Type': 'application/json',
              'Prefer': 'return=minimal',
            },
            body: jsonEncode(data),
          );
          success = response.statusCode == 201 || response.statusCode == 200;
        }

        if (success) {
          // Remove from sync queue
          await db.delete('sync_queue', where: 'id = ?', whereArgs: [item['id']]);
          // Mark analysis as synced
          if (entityType == 'analysis') {
            await db.update(
              'cached_analyses',
              {'is_synced': 1},
              where: 'analysis_id = ?',
              whereArgs: [entityId],
            );
          }
          uploaded++;
        } else {
          // Increment retry count
          await db.update(
            'sync_queue',
            {
              'retry_count': retryCount + 1,
              'last_error': 'HTTP request failed',
            },
            where: 'id = ?',
            whereArgs: [item['id']],
          );
          failed++;
        }
      } catch (e) {
        await db.update(
          'sync_queue',
          {
            'retry_count': retryCount + 1,
            'last_error': e.toString(),
          },
          where: 'id = ?',
          whereArgs: [item['id']],
        );
        failed++;
      }
    }

    return {'uploaded': uploaded, 'failed': failed};
  }

  /// Download latest knowledge from Supabase for offline access.
  Future<int> downloadKnowledge(String supabaseUrl, String supabaseToken) async {
    try {
      final response = await http.get(
        Uri.parse('$supabaseUrl/rest/v1/geological_knowledge?select=*&order=updated_at.desc&limit=$_maxCachedKnowledge'),
        headers: {
          'Authorization': 'Bearer $supabaseToken',
          'apikey': supabaseToken,
        },
      );

      if (response.statusCode != 200) return 0;

      final List<dynamic> items = jsonDecode(response.body);
      for (final item in items) {
        await cacheKnowledge(Map<String, dynamic>.from(item));
      }

      return items.length;
    } catch (e) {
      return 0;
    }
  }

  /// Get count of items pending sync.
  Future<int> getPendingSyncCount() async {
    final result = await db.rawQuery('SELECT COUNT(*) FROM sync_queue');
    return Sqflite.firstIntValue(result) ?? 0;
  }

  // ===========================================================================
  // INTERNAL HELPERS
  // ===========================================================================

  String _buildAnalysisSearchText(Map<String, dynamic> analysis) {
    final parts = <String>[];

    final location = analysis['location'] as Map<String, dynamic>?;
    if (location?['region'] != null) parts.add(location!['region'].toString().toLowerCase());
    if (location?['country'] != null) parts.add(location!['country'].toString().toLowerCase());

    if (analysis['mineral_type'] != null) parts.add(analysis['mineral_type'].toString().toLowerCase());

    final detected = analysis['detected_minerals'] as List?;
    if (detected != null) {
      parts.addAll(detected.map((m) => m.toString().toLowerCase()));
    }

    // Include agent output descriptions
    for (final agent in ['analysis', 'geology']) {
      final output = analysis['${agent}_output'] ?? analysis['${agent}_result'];
      if (output is Map) {
        if (output['description'] != null) parts.add(output['description'].toString().toLowerCase());
        if (output['geological_context'] != null) parts.add(output['geological_context'].toString().toLowerCase());
      }
    }

    return parts.join(' ');
  }

  Future<void> _updateAnalysisFts(
    String analysisId,
    String searchText,
    String? mineralType,
    String? region,
  ) async {
    try {
      // Delete old FTS entry
      await db.rawDelete(
        'DELETE FROM analyses_fts WHERE analysis_id = ?',
        [analysisId],
      );
      // Insert new FTS entry
      await db.rawInsert(
        'INSERT INTO analyses_fts (analysis_id, search_text, mineral_type, location_region) VALUES (?, ?, ?, ?)',
        [analysisId, searchText, mineralType ?? '', region ?? ''],
      );
    } catch (e) {
      // FTS update failure is non-critical
    }
  }

  Future<void> _enqueueSync(
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

  Future<void> _enforceAnalysisLimit() async {
    final count = Sqflite.firstIntValue(
      await db.rawQuery('SELECT COUNT(*) FROM cached_analyses')
    ) ?? 0;

    if (count > _maxCachedAnalyses) {
      // Delete oldest synced analyses first
      await db.rawDelete(
        'DELETE FROM cached_analyses WHERE analysis_id IN '
        '(SELECT analysis_id FROM cached_analyses WHERE is_synced = 1 '
        'ORDER BY created_at ASC LIMIT ?)',
        [count - _maxCachedAnalyses],
      );
    }
  }

  String _generateId() {
    final random = Random();
    final timestamp = DateTime.now().millisecondsSinceEpoch.toRadixString(36);
    final randomPart = random.nextInt(0xFFFFFF).toRadixString(36).padLeft(5, '0');
    return '$timestamp-$randomPart';
  }

  dynamic _tryDecodeJson(dynamic value) {
    if (value == null) return null;
    if (value is String) {
      try {
        return jsonDecode(value);
      } catch (_) {
        return value;
      }
    }
    return value;
  }

  /// Close the database connection.
  Future<void> close() async {
    await _db?.close();
    _db = null;
  }

  /// Clear all cached data (for logout / account switch).
  Future<void> clearAll() async {
    await db.delete('cached_analyses');
    await db.delete('cached_knowledge');
    await db.delete('sync_queue');
    await db.delete('cached_ltm');
  }
}
