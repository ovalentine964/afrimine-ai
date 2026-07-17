import 'package:flutter/material.dart';
import '../models/market_price_model.dart';
import '../services/api_service.dart';
import '../services/database_service.dart';

class MarketProvider extends ChangeNotifier {
  final ApiService _api = ApiService();
  final DatabaseService _db = DatabaseService();

  List<MarketPriceModel> _prices = [];
  bool _isLoading = false;
  String? _error;
  DateTime? _lastUpdated;

  List<MarketPriceModel> get prices => _prices;
  bool get isLoading => _isLoading;
  String? get error => _error;
  DateTime? get lastUpdated => _lastUpdated;

  MarketPriceModel? get goldPrice =>
      _prices.where((p) => p.mineral.toLowerCase() == 'gold').firstOrNull;
  MarketPriceModel? get copperPrice =>
      _prices.where((p) => p.mineral.toLowerCase() == 'copper').firstOrNull;

  Future<void> loadPrices({bool forceRefresh = false}) async {
    if (!forceRefresh && _prices.isNotEmpty) return;

    _isLoading = true;
    notifyListeners();

    try {
      _prices = await _api.getMarketPrices();
      _lastUpdated = DateTime.now();
      _error = null;

      // Cache locally
      await _db.saveMarketPrices(_prices.map((p) => p.toJson()).toList());
    } catch (e) {
      _error = e.toString();
      // Try loading from cache
      try {
        final cached = await _db.getMarketPrices();
        if (cached.isNotEmpty) {
          _prices = cached.map((json) => MarketPriceModel.fromJson(json)).toList();
        } else {
          _prices = MarketPriceModel.getMockPrices();
        }
      } catch (_) {
        _prices = MarketPriceModel.getMockPrices();
      }
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> refresh() async {
    await loadPrices(forceRefresh: true);
  }
}
