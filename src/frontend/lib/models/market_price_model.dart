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
      mineral: json['mineral'] as String,
      pricePerOz: (json['price_per_oz'] as num).toDouble(),
      changePercent: (json['change_percent'] as num).toDouble(),
      changeAbsolute: (json['change_absolute'] as num).toDouble(),
      currency: json['currency'] as String? ?? 'USD',
      lastUpdated: DateTime.parse(json['last_updated'] as String),
      source: json['source'] as String?,
    );
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
