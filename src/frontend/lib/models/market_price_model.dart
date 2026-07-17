class MarketPriceModel {
  final String mineral;
  final double pricePerOz;
  final double changePercent;
  final double changeAbsolute;
  final String currency;
  final DateTime lastUpdated;
  final String? source;

  MarketPriceModel({
    required this.mineral,
    required this.pricePerOz,
    required this.changePercent,
    required this.changeAbsolute,
    this.currency = 'USD',
    required this.lastUpdated,
    this.source,
  });

  factory MarketPriceModel.fromJson(Map<String, dynamic> json) {
    return MarketPriceModel(
      mineral: json['mineral'] as String? ?? 'Unknown',
      pricePerOz: _parseDouble(json['price_per_oz']) ?? 0.0,
      changePercent: _parseDouble(json['change_percent']) ?? 0.0,
      changeAbsolute: _parseDouble(json['change_absolute']) ?? 0.0,
      currency: json['currency'] as String? ?? 'USD',
      lastUpdated: _parseDateTime(json['last_updated']),
      source: json['source'] as String?,
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
      'mineral': mineral,
      'price_per_oz': pricePerOz,
      'change_percent': changePercent,
      'change_absolute': changeAbsolute,
      'currency': currency,
      'last_updated': lastUpdated.toIso8601String(),
      'source': source,
    };
  }

  bool get isPositive => changePercent >= 0;
  String get formattedPrice => '\$${pricePerOz.toStringAsFixed(2)}';
  String get formattedChange {
    final sign = isPositive ? '+' : '';
    return '$sign${changePercent.toStringAsFixed(2)}%';
  }

  // Mock data for development
  static List<MarketPriceModel> getMockPrices() {
    return [
      MarketPriceModel(
        mineral: 'Gold',
        pricePerOz: 2345.80,
        changePercent: 1.24,
        changeAbsolute: 28.80,
        lastUpdated: DateTime.now(),
        source: 'Mock Data',
      ),
      MarketPriceModel(
        mineral: 'Copper',
        pricePerOz: 4.12,
        changePercent: -0.58,
        changeAbsolute: -0.024,
        lastUpdated: DateTime.now(),
        source: 'Mock Data',
      ),
      MarketPriceModel(
        mineral: 'Titanium',
        pricePerOz: 32.50,
        changePercent: 0.85,
        changeAbsolute: 0.27,
        lastUpdated: DateTime.now(),
        source: 'Mock Data',
      ),
      MarketPriceModel(
        mineral: 'Iron Ore',
        pricePerOz: 0.045,
        changePercent: -1.20,
        changeAbsolute: -0.00055,
        lastUpdated: DateTime.now(),
        source: 'Mock Data',
      ),
    ];
  }
}
