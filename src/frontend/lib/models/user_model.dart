class UserModel {
  final String id;
  final String phoneNumber;
  final String? name;
  final String? email;
  final double? landAreaAcres;
  final String? landLocation;
  final double? landLat;
  final double? landLng;
  final String preferredLanguage;
  final bool offlineMode;
  final DateTime createdAt;
  final DateTime updatedAt;

  UserModel({
    required this.id,
    required this.phoneNumber,
    this.name,
    this.email,
    this.landAreaAcres,
    this.landLocation,
    this.landLat,
    this.landLng,
    this.preferredLanguage = 'en',
    this.offlineMode = true,
    required this.createdAt,
    required this.updatedAt,
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id'] as String? ?? '',
      phoneNumber: json['phone_number'] as String? ?? '',
      name: json['name'] as String?,
      email: json['email'] as String?,
      landAreaAcres: _parseDouble(json['land_area_acres']),
      landLocation: json['land_location'] as String?,
      landLat: _parseDouble(json['land_lat']),
      landLng: _parseDouble(json['land_lng']),
      preferredLanguage: json['preferred_language'] as String? ?? 'en',
      offlineMode: json['offline_mode'] as bool? ?? true,
      createdAt: _parseDateTime(json['created_at']),
      updatedAt: _parseDateTime(json['updated_at']),
    );
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

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'phone_number': phoneNumber,
      'name': name,
      'email': email,
      'land_area_acres': landAreaAcres,
      'land_location': landLocation,
      'land_lat': landLat,
      'land_lng': landLng,
      'preferred_language': preferredLanguage,
      'offline_mode': offlineMode,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  UserModel copyWith({
    String? id,
    String? phoneNumber,
    String? name,
    String? email,
    double? landAreaAcres,
    String? landLocation,
    double? landLat,
    double? landLng,
    String? preferredLanguage,
    bool? offlineMode,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return UserModel(
      id: id ?? this.id,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      name: name ?? this.name,
      email: email ?? this.email,
      landAreaAcres: landAreaAcres ?? this.landAreaAcres,
      landLocation: landLocation ?? this.landLocation,
      landLat: landLat ?? this.landLat,
      landLng: landLng ?? this.landLng,
      preferredLanguage: preferredLanguage ?? this.preferredLanguage,
      offlineMode: offlineMode ?? this.offlineMode,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  String get displayName => name ?? phoneNumber;
  double get estimatedValuePerAcre => 50000; // KES per acre base estimate
  double get totalEstimatedValue => (landAreaAcres ?? 0) * estimatedValuePerAcre;
}
