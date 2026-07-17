import 'package:flutter/material.dart';
import '../models/market_price_model.dart';
import '../utils/constants.dart';

class MarketPriceCard extends StatelessWidget {
  final MarketPriceModel price;

  const MarketPriceCard({super.key, required this.price});

  @override
  Widget build(BuildContext context) {
    final isPositive = price.isPositive;
    final changeColor = isPositive ? AppColors.success : AppColors.error;
    final arrowIcon = isPositive ? Icons.trending_up : Icons.trending_down;

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              _getMineralColor().withOpacity(0.08),
              _getMineralColor().withOpacity(0.02),
            ],
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: _getMineralColor().withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(_getMineralIcon(), color: _getMineralColor(), size: 20),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    price.mineral,
                    style: AppTextStyles.heading3.copyWith(fontSize: 16),
                  ),
                ),
              ],
            ),
            const Spacer(),
            Text(
              price.formattedPrice,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: _getMineralColor(),
                
              ),
            ),
            const SizedBox(height: 2),
            Text(
              'per troy oz',
              style: AppTextStyles.caption,
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: changeColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(arrowIcon, size: 14, color: changeColor),
                  const SizedBox(width: 4),
                  Text(
                    price.formattedChange,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: changeColor,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _getMineralColor() {
    switch (price.mineral.toLowerCase()) {
      case 'gold':
        return AppColors.gold;
      case 'copper':
        return AppColors.copper;
      case 'titanium':
        return AppColors.info;
      default:
        return AppColors.primary;
    }
  }

  IconData _getMineralIcon() {
    switch (price.mineral.toLowerCase()) {
      case 'gold':
        return Icons.monetization_on;
      case 'copper':
        return Icons.circle;
      case 'titanium':
        return Icons.diamond;
      default:
        return Icons.landscape;
    }
  }
}
