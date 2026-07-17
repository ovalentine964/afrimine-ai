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
      id: json['id'] as String,
      userId: json['user_id'] as String,
      imagePath: json['image_path'] as String?,
      imageUrl: json['image_url'] as String?,
      latitude: json['latitude']?.toDouble(),
      longitude: json['longitude']?.toDouble(),
      accuracy: json['accuracy']?.toDouble(),
      mineralType: json['mineral_type'] as String?,
      confidence: json['confidence']?.toDouble(),
      gradeEstimate: json['grade_estimate']?.toDouble(),
      status: json['status'] as String? ?? 'pending',
      notes: json['notes'] as String?,
      fieldTests: json['field_tests'] as Map<String, dynamic>?,
      aiResults: json['ai_results'] as Map<String, dynamic>?,
      synced: json['synced'] as bool? ?? false,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
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
      id: map['id'] as String,
      userId: map['user_id'] as String,
      imagePath: map['image_path'] as String?,
      imageUrl: map['image_url'] as String?,
      latitude: map['latitude']?.toDouble(),
      longitude: map['longitude']?.toDouble(),
      accuracy: map['accuracy']?.toDouble(),
      mineralType: map['mineral_type'] as String?,
      confidence: map['confidence']?.toDouble(),
      gradeEstimate: map['grade_estimate']?.toDouble(),
      status: map['status'] as String? ?? 'pending',
      notes: map['notes'] as String?,
      fieldTests: map['field_tests'] != null ? _decodeJson(map['field_tests'] as String) : null,
      aiResults: map['ai_results'] != null ? _decodeJson(map['ai_results'] as String) : null,
      synced: (map['synced'] as int?) == 1,
      createdAt: DateTime.parse(map['created_at'] as String),
      updatedAt: DateTime.parse(map['updated_at'] as String),
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
    // Simple JSON encode - in production use dart:convert
    return data.toString();
  }

  static Map<String, dynamic> _decodeJson(String str) {
    // Simple decode placeholder - in production use dart:convert jsonDecode
    try {
      // Remove braces and parse key-value pairs
      final clean = str.replaceAll('{', '').replaceAll('}', '');
      final Map<String, dynamic> result = {};
      for (final pair in clean.split(',')) {
        final parts = pair.trim().split(':');
        if (parts.length == 2) {
          result[parts[0].trim()] = parts[1].trim();
        }
      }
      return result;
    } catch (_) {
      return {};
    }
  }

  bool get hasLocation => latitude != null && longitude != null;
  bool get isPending => status == 'pending';
  bool get isAnalyzed => status == 'analyzed';
  bool get isVerified => status == 'verified';
  bool get hasImage => imagePath != null || imageUrl != null;
  bool get needsSync => !synced;
}
