import 'dart:convert';

/// GPS location data captured with a mineral sample.
class SampleLocation {
  final double latitude;
  final double longitude;
  final double? elevation;
  final double? accuracy;

  const SampleLocation({
    required this.latitude,
    required this.longitude,
    this.elevation,
    this.accuracy,
  });

  factory SampleLocation.fromJson(Map<String, dynamic> json) {
    return SampleLocation(
      latitude: (json['lat'] ?? json['latitude'] as num).toDouble(),
      longitude: (json['lon'] ?? json['longitude'] as num).toDouble(),
      elevation: (json['elevation'] as num?)?.toDouble(),
      accuracy: (json['accuracy'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'lat': latitude,
        'lon': longitude,
        if (elevation != null) 'elevation': elevation,
        if (accuracy != null) 'accuracy': accuracy,
      };

  @override
  String toString() => '${latitude.toStringAsFixed(6)}, ${longitude.toStringAsFixed(6)}';
}

/// XRF (X-ray fluorescence) readings from a portable analyzer.
class XrfReadings {
  final Map<String, double> elements; // element symbol → ppm
  final DateTime? capturedAt;

  const XrfReadings({
    required this.elements,
    this.capturedAt,
  });

  factory XrfReadings.fromJson(Map<String, dynamic> json) {
    final elements = <String, double>{};
    if (json['elements'] is Map) {
      (json['elements'] as Map).forEach((k, v) {
        elements[k.toString()] = (v as num).toDouble();
      });
    }
    return XrfReadings(
      elements: elements,
      capturedAt: json['captured_at'] != null ? DateTime.tryParse(json['captured_at']) : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'elements': elements,
        if (capturedAt != null) 'captured_at': capturedAt!.toIso8601String(),
      };

  /// Get reading for a specific element in ppm.
  double? operator [](String element) => elements[element];

  /// Common pathfinder elements for gold.
  double? get au => elements['Au'];
  double? get as_ => elements['As'];
  double? get sb => elements['Sb'];
  double? get bi => elements['Bi'];
  double? get hg => elements['Hg'];
  double? get ag => elements['Ag'];
  double? get cu => elements['Cu'];
}

/// A mineral sample collected in the field.
class MineralSample {
  final String id;
  final String? userId;
  final SampleLocation? location;
  final List<String> photoPaths;
  final List<String> photoUrls;
  final XrfReadings? xrfReadings;
  final String? fieldNotes;
  final String? voiceNotePath;
  final String? voiceNoteUrl;
  final bool isSynced;
  final DateTime createdAt;
  final DateTime updatedAt;
  final Map<String, dynamic>? vectorClock;

  const MineralSample({
    required this.id,
    this.userId,
    this.location,
    this.photoPaths = const [],
    this.photoUrls = const [],
    this.xrfReadings,
    this.fieldNotes,
    this.voiceNotePath,
    this.voiceNoteUrl,
    this.isSynced = false,
    required this.createdAt,
    required this.updatedAt,
    this.vectorClock,
  });

  factory MineralSample.fromJson(Map<String, dynamic> json) {
    return MineralSample(
      id: json['id'] as String,
      userId: json['user_id'] as String?,
      location: json['location'] != null
          ? SampleLocation.fromJson(json['location'] is String
              ? jsonDecode(json['location'] as String)
              : json['location'] as Map<String, dynamic>)
          : null,
      photoPaths: (json['photo_paths'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      photoUrls: (json['photo_urls'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      xrfReadings: json['xrf_readings'] != null
          ? XrfReadings.fromJson(json['xrf_readings'] is String
              ? jsonDecode(json['xrf_readings'] as String)
              : json['xrf_readings'] as Map<String, dynamic>)
          : null,
      fieldNotes: json['field_notes'] as String?,
      voiceNotePath: json['voice_note_path'] as String?,
      voiceNoteUrl: json['voice_note_url'] as String?,
      isSynced: json['is_synced'] == true || json['synced'] == true,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      vectorClock: json['vector_clock'] != null
          ? (json['vector_clock'] is String
              ? jsonDecode(json['vector_clock'] as String)
              : json['vector_clock'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'user_id': userId,
        'location': location?.toJson(),
        'photo_paths': photoPaths,
        'photo_urls': photoUrls,
        'xrf_readings': xrfReadings?.toJson(),
        'field_notes': fieldNotes,
        'voice_note_path': voiceNotePath,
        'voice_note_url': voiceNoteUrl,
        'is_synced': isSynced,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'vector_clock': vectorClock,
      };

  /// Copy with updated fields.
  MineralSample copyWith({
    String? id,
    String? userId,
    SampleLocation? location,
    List<String>? photoPaths,
    List<String>? photoUrls,
    XrfReadings? xrfReadings,
    String? fieldNotes,
    String? voiceNotePath,
    String? voiceNoteUrl,
    bool? isSynced,
    DateTime? createdAt,
    DateTime? updatedAt,
    Map<String, dynamic>? vectorClock,
  }) {
    return MineralSample(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      location: location ?? this.location,
      photoPaths: photoPaths ?? this.photoPaths,
      photoUrls: photoUrls ?? this.photoUrls,
      xrfReadings: xrfReadings ?? this.xrfReadings,
      fieldNotes: fieldNotes ?? this.fieldNotes,
      voiceNotePath: voiceNotePath ?? this.voiceNotePath,
      voiceNoteUrl: voiceNoteUrl ?? this.voiceNoteUrl,
      isSynced: isSynced ?? this.isSynced,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      vectorClock: vectorClock ?? this.vectorClock,
    );
  }

  /// Whether this sample has enough data for analysis.
  bool get canAnalyze => photoPaths.isNotEmpty || photoUrls.isNotEmpty;

  /// Display name for the sample.
  String get displayName {
    final dateStr = '${createdAt.year}-${createdAt.month.toString().padLeft(2, '0')}-${createdAt.day.toString().padLeft(2, '0')}';
    return 'Sample $dateStr';
  }
}
