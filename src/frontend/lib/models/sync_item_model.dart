class SyncItemModel {
  final String id;
  final String entityType; // 'sample', 'user', 'field_test'
  final String entityId;
  final String action; // 'create', 'update', 'delete'
  final Map<String, dynamic>? data;
  final int retryCount;
  final String? lastError;
  final DateTime createdAt;

  SyncItemModel({
    required this.id,
    required this.entityType,
    required this.entityId,
    required this.action,
    this.data,
    this.retryCount = 0,
    this.lastError,
    required this.createdAt,
  });

  factory SyncItemModel.fromJson(Map<String, dynamic> json) {
    return SyncItemModel(
      id: json['id'] as String? ?? '',
      entityType: json['entity_type'] as String? ?? '',
      entityId: json['entity_id'] as String? ?? '',
      action: json['action'] as String? ?? '',
      data: _parseMap(json['data']),
      retryCount: _parseInt(json['retry_count']) ?? 0,
      lastError: json['last_error'] as String?,
      createdAt: _parseDateTime(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'entity_type': entityType,
      'entity_id': entityId,
      'action': action,
      'data': data,
      'retry_count': retryCount,
      'last_error': lastError,
      'created_at': createdAt.toIso8601String(),
    };
  }

  Map<String, dynamic> toDbMap() {
    return {
      'id': id,
      'entity_type': entityType,
      'entity_id': entityId,
      'action': action,
      'data': data != null ? data.toString() : null,
      'retry_count': retryCount,
      'last_error': lastError,
      'created_at': createdAt.toIso8601String(),
    };
  }

  factory SyncItemModel.fromDbMap(Map<String, dynamic> map) {
    return SyncItemModel(
      id: map['id'] as String? ?? '',
      entityType: map['entity_type'] as String? ?? '',
      entityId: map['entity_id'] as String? ?? '',
      action: map['action'] as String? ?? '',
      retryCount: _parseInt(map['retry_count']) ?? 0,
      lastError: map['last_error'] as String?,
      createdAt: _parseDateTime(map['created_at']),
    );
  }

  static int? _parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is String) return int.tryParse(value);
    return null;
  }

  static DateTime _parseDateTime(dynamic value) {
    if (value is DateTime) return value;
    if (value is String) {
      try {
        return DateTime.parse(value);
      } catch (_) {
        return DateTime.now();
      }
    }
    return DateTime.now();
  }

  static Map<String, dynamic>? _parseMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    return null;
  }

  SyncItemModel copyWith({
    int? retryCount,
    String? lastError,
  }) {
    return SyncItemModel(
      id: id,
      entityType: entityType,
      entityId: entityId,
      action: action,
      data: data,
      retryCount: retryCount ?? this.retryCount,
      lastError: lastError ?? this.lastError,
      createdAt: createdAt,
    );
  }

  bool get canRetry => retryCount < 3;
}
