import 'dart:convert';

class SampleModel {
  final String id;
  final String userId;
  final String? imagePath;
  final String? imageUrl;
  final double? latitude;
  final double? longitude;
  final double? accuracy;
  final String? mineralType;
  final double? confidence;
  final double? gradeEstimate;
  final String status; // pending, analyzed, verified
  final String? notes;
  final Map<String, dynamic>? fieldTests;
  final Map<String, dynamic>? aiResults;
  final bool synced;
  final DateTime createdAt;
  final DateTime updatedAt;

  SampleModel({
    required this.id,
    required this.userId,
    this.imagePath,
    this.imageUrl,
    this.latitude,
    this.longitude,
    this.accuracy,
    this.mineralType,
    this.confidence,
    this.gradeEstimate,
    this.status = 'pending',
    this.notes,
    this.fieldTests,
    this.aiResults,
    this.synced = false,
    required this.createdAt,
    required this.updatedAt,
  });

  factory SampleModel.fromJson(Map<String, dynamic> json) {
    return SampleModel(
      id: json['id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      imagePath: json['image_path'] as String?,
      imageUrl: json['image_url'] as String?,
      latitude: _parseDouble(json['latitude']),
      longitude: _parseDouble(json['longitude']),
      accuracy: _parseDouble(json['accuracy']),
      mineralType: json['mineral_type'] as String?,
      confidence: _parseDouble(json['confidence']),
      gradeEstimate: _parseDouble(json['grade_estimate']),
      status: json['status'] as String? ?? 'pending',
      notes: json['notes'] as String?,
      fieldTests: _parseMap(json['field_tests']),
      aiResults: _parseMap(json['ai_results']),
      synced: json['synced'] as bool? ?? false,
      createdAt: _parseDateTime(json['created_at']),
      updatedAt: _parseDateTime(json['updated_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'image_path': imagePath,
      'image_url': imageUrl,
      'latitude': latitude,
      'longitude': longitude,
      'accuracy': accuracy,
      'mineral_type': mineralType,
      'confidence': confidence,
      'grade_estimate': gradeEstimate,
      'status': status,
      'notes': notes,
      'field_tests': fieldTests,
      'ai_results': aiResults,
      'synced': synced,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  Map<String, dynamic> toDbMap() {
    return {
      'id': id,
      'user_id': userId,
      'image_path': imagePath,
      'image_url': imageUrl,
      'latitude': latitude,
      'longitude': longitude,
      'accuracy': accuracy,
      'mineral_type': mineralType,
      'confidence': confidence,
      'grade_estimate': gradeEstimate,
      'status': status,
      'notes': notes,
      'field_tests': fieldTests != null ? _encodeJson(fieldTests!) : null,
      'ai_results': aiResults != null ? _encodeJson(aiResults!) : null,
      'synced': synced ? 1 : 0,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  factory SampleModel.fromDbMap(Map<String, dynamic> map) {
    return SampleModel(
      id: map['id'] as String? ?? '',
      userId: map['user_id'] as String? ?? '',
      imagePath: map['image_path'] as String?,
      imageUrl: map['image_url'] as String?,
      latitude: _parseDouble(map['latitude']),
      longitude: _parseDouble(map['longitude']),
      accuracy: _parseDouble(map['accuracy']),
      mineralType: map['mineral_type'] as String?,
      confidence: _parseDouble(map['confidence']),
      gradeEstimate: _parseDouble(map['grade_estimate']),
      status: map['status'] as String? ?? 'pending',
      notes: map['notes'] as String?,
      fieldTests: map['field_tests'] != null ? _decodeJson(map['field_tests'] as String) : null,
      aiResults: map['ai_results'] != null ? _decodeJson(map['ai_results'] as String) : null,
      synced: (map['synced'] as int?) == 1,
      createdAt: _parseDateTime(map['created_at']),
      updatedAt: _parseDateTime(map['updated_at']),
    );
  }

  SampleModel copyWith({
    String? id,
    String? userId,
    String? imagePath,
    String? imageUrl,
    double? latitude,
    double? longitude,
    double? accuracy,
    String? mineralType,
    double? confidence,
    double? gradeEstimate,
    String? status,
    String? notes,
    Map<String, dynamic>? fieldTests,
    Map<String, dynamic>? aiResults,
    bool? synced,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return SampleModel(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      imagePath: imagePath ?? this.imagePath,
      imageUrl: imageUrl ?? this.imageUrl,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      accuracy: accuracy ?? this.accuracy,
      mineralType: mineralType ?? this.mineralType,
      confidence: confidence ?? this.confidence,
      gradeEstimate: gradeEstimate ?? this.gradeEstimate,
      status: status ?? this.status,
      notes: notes ?? this.notes,
      fieldTests: fieldTests ?? this.fieldTests,
      aiResults: aiResults ?? this.aiResults,
      synced: synced ?? this.synced,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  static String _encodeJson(Map<String, dynamic> data) {
    try {
      return jsonEncode(data);
    } catch (e) {
      return '{}';
    }
  }

  static Map<String, dynamic> _decodeJson(String str) {
    try {
      final decoded = jsonDecode(str);
      if (decoded is Map<String, dynamic>) return decoded;
      return {};
    } catch (_) {
      return {};
    }
  }

  static double? _parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is String) return double.tryParse(value);
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
    if (value is String) return _decodeJson(value);
    return null;
  }

  bool get hasLocation => latitude != null && longitude != null;
  bool get isPending => status == 'pending';
  bool get isAnalyzed => status == 'analyzed';
  bool get isVerified => status == 'verified';
  bool get hasImage => imagePath != null || imageUrl != null;
  bool get needsSync => !synced;
}
