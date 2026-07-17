import 'dart:io';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as path;
import '../models/sample_model.dart';
import '../utils/helpers.dart';

class PdfService {
  static PdfService? _instance;

  PdfService._();

  factory PdfService() {
    _instance ??= PdfService._();
    return _instance!;
  }

  Future<File> generateInvestorReport({
    required String userName,
    required String landLocation,
    required double landArea,
    required List<SampleModel> samples,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    final pdf = pw.Document();

    final analyzed = samples.where((s) => s.isAnalyzed || s.isVerified).toList();
    final totalValue = analyzed.fold<double>(0, (sum, s) => sum + (s.gradeEstimate ?? 0));

    pdf.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(40),
        header: (context) => _buildHeader(),
        footer: (context) => _buildFooter(context),
        build: (context) => [
          _buildTitle('AfriMine AI — Investor Report'),
          pw.SizedBox(height: 10),
          _buildDateRange(startDate, endDate),
          pw.SizedBox(height: 20),

          // Land Overview
          _buildSection('Land Overview'),
          _buildInfoTable([
            ['Owner', userName],
            ['Location', landLocation],
            ['Area', '${landArea.toStringAsFixed(1)} acres'],
            ['Total Samples', samples.length.toString()],
            ['Analyzed Samples', analyzed.length.toString()],
            ['Estimated Total Value', 'KES ${Helpers.formatCurrency(totalValue, symbol: '')}'],
          ]),
          pw.SizedBox(height: 20),

          // Mineral Distribution
          _buildSection('Mineral Distribution'),
          _buildMineralDistribution(analyzed),
          pw.SizedBox(height: 20),

          // Sample Summary Table
          _buildSection('Sample Details'),
          _buildSampleTable(samples.take(20).toList()),
          if (samples.length > 20)
            pw.Padding(
              padding: const pw.EdgeInsets.only(top: 8),
              child: pw.Text(
                '... and ${samples.length - 20} more samples',
                style: pw.TextStyle(fontStyle: pw.FontStyle.italic, color: PdfColors.grey600),
              ),
            ),
          pw.SizedBox(height: 20),

          // Recommendations
          _buildSection('Recommendations'),
          _buildRecommendations(analyzed),
          pw.SizedBox(height: 20),

          // Disclaimer
          _buildDisclaimer(),
        ],
      ),
    );

    final appDir = await getApplicationDocumentsDirectory();
    final reportsDir = Directory(path.join(appDir.path, 'reports'));
    if (!await reportsDir.exists()) {
      await reportsDir.create(recursive: true);
    }

    final fileName = 'afrimine_report_${DateTime.now().millisecondsSinceEpoch}.pdf';
    final file = File(path.join(reportsDir.path, fileName));
    await file.writeAsBytes(await pdf.save());
    return file;
  }

  pw.Widget _buildHeader() {
    return pw.Container(
      padding: const pw.EdgeInsets.only(bottom: 10),
      decoration: const pw.BoxDecoration(
        border: pw.Border(bottom: pw.BorderSide(color: PdfColors.green800, width: 2)),
      ),
      child: pw.Row(
        mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
        children: [
          pw.Text('AfriMine AI', style: pw.TextStyle(
            fontSize: 20,
            fontWeight: pw.FontWeight.bold,
            color: PdfColors.green800,
          )),
          pw.Text('Mineral Detection Platform', style: pw.TextStyle(
            fontSize: 10,
            color: PdfColors.grey600,
          )),
        ],
      ),
    );
  }

  pw.Widget _buildFooter(pw.Context context) {
    return pw.Container(
      padding: const pw.EdgeInsets.only(top: 10),
      decoration: const pw.BoxDecoration(
        border: pw.Border(top: pw.BorderSide(color: PdfColors.grey300)),
      ),
      child: pw.Row(
        mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
        children: [
          pw.Text('Generated: ${Helpers.formatDateTime(DateTime.now())}', style: pw.TextStyle(
            fontSize: 8,
            color: PdfColors.grey600,
          )),
          pw.Text('Page ${context.pageNumber} of ${context.pagesCount}', style: pw.TextStyle(
            fontSize: 8,
            color: PdfColors.grey600,
          )),
        ],
      ),
    );
  }

  pw.Widget _buildTitle(String title) {
    return pw.Text(title, style: pw.TextStyle(
      fontSize: 24,
      fontWeight: pw.FontWeight.bold,
      color: PdfColors.green900,
    ));
  }

  pw.Widget _buildDateRange(DateTime? start, DateTime? end) {
    final startStr = start != null ? Helpers.formatDate(start) : 'All time';
    final endStr = end != null ? Helpers.formatDate(end) : 'Present';
    return pw.Text('Period: $startStr — $endStr', style: pw.TextStyle(
      fontSize: 11,
      color: PdfColors.grey700,
    ));
  }

  pw.Widget _buildSection(String title) {
    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.start,
      children: [
        pw.Container(
          padding: const pw.EdgeInsets.symmetric(vertical: 4, horizontal: 8),
          decoration: pw.BoxDecoration(
            color: PdfColors.green50,
            borderRadius: pw.BorderRadius.circular(4),
          ),
          child: pw.Text(title, style: pw.TextStyle(
            fontSize: 14,
            fontWeight: pw.FontWeight.bold,
            color: PdfColors.green800,
          )),
        ),
        pw.SizedBox(height: 8),
      ],
    );
  }

  pw.Widget _buildInfoTable(List<List<String>> rows) {
    return pw.TableHelper.fromTextArray(
      headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 10),
      cellStyle: const pw.TextStyle(fontSize: 10),
      headerDecoration: const pw.BoxDecoration(color: PdfColors.green100),
      cellAlignment: pw.Alignment.centerLeft,
      data: rows,
      columnWidths: {0: const pw.FlexColumnWidth(2), 1: const pw.FlexColumnWidth(3)},
    );
  }

  pw.Widget _buildMineralDistribution(List<SampleModel> samples) {
    final distribution = <String, int>{};
    for (final sample in samples) {
      final mineral = sample.mineralType ?? 'Unknown';
      distribution[mineral] = (distribution[mineral] ?? 0) + 1;
    }

    if (distribution.isEmpty) {
      return pw.Text('No analyzed samples available', style: pw.TextStyle(
        fontStyle: pw.FontStyle.italic,
        color: PdfColors.grey600,
      ));
    }

    final data = distribution.entries.map((e) => [e.key, e.value.toString()]).toList();
    return pw.TableHelper.fromTextArray(
      headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 10),
      cellStyle: const pw.TextStyle(fontSize: 10),
      headerDecoration: const pw.BoxDecoration(color: PdfColors.green100),
      headers: ['Mineral', 'Count'],
      data: data,
    );
  }

  pw.Widget _buildSampleTable(List<SampleModel> samples) {
    if (samples.isEmpty) {
      return pw.Text('No samples recorded', style: pw.TextStyle(
        fontStyle: pw.FontStyle.italic,
        color: PdfColors.grey600,
      ));
    }

    final data = samples.map((s) => [
      Helpers.formatDate(s.createdAt),
      s.mineralType ?? 'Pending',
      s.status.toUpperCase(),
      s.hasLocation ? Helpers.formatCoordinate(s.latitude!, s.longitude!) : 'N/A',
      s.gradeEstimate != null ? '${s.gradeEstimate!.toStringAsFixed(2)} g/t' : '-',
    ]).toList();

    return pw.TableHelper.fromTextArray(
      headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9),
      cellStyle: const pw.TextStyle(fontSize: 8),
      headerDecoration: const pw.BoxDecoration(color: PdfColors.green100),
      headers: ['Date', 'Mineral', 'Status', 'Location', 'Grade'],
      data: data,
      cellAlignments: {
        0: pw.Alignment.centerLeft,
        1: pw.Alignment.centerLeft,
        2: pw.Alignment.center,
        3: pw.Alignment.centerLeft,
        4: pw.Alignment.centerRight,
      },
    );
  }

  pw.Widget _buildRecommendations(List<SampleModel> samples) {
    final recommendations = <String>[];

    if (samples.isEmpty) {
      recommendations.add('Begin systematic sampling across your land parcel to establish baseline mineral data.');
    } else {
      final verified = samples.where((s) => s.isVerified).length;
      final withGrade = samples.where((s) => s.gradeEstimate != null && s.gradeEstimate! > 0).length;

      if (verified < samples.length) {
        recommendations.add('Complete verification of ${samples.length - verified} pending samples for investor readiness.');
      }
      if (withGrade > 0) {
        recommendations.add('Focus exploration on high-grade zones identified in the analysis.');
      }
      recommendations.add('Consider expanding sampling grid to adjacent areas for comprehensive coverage.');
    }

    recommendations.add('All estimates are preliminary. Professional geological survey recommended for investment decisions.');

    return pw.Column(
      crossAxisAlignment: pw.CrossAxisAlignment.start,
      children: recommendations.map((r) => pw.Padding(
        padding: const pw.EdgeInsets.only(bottom: 4),
        child: pw.Row(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Text('• ', style: pw.TextStyle(fontWeight: pw.FontWeight.bold)),
            pw.Expanded(child: pw.Text(r, style: const pw.TextStyle(fontSize: 10))),
          ],
        ),
      )).toList(),
    );
  }

  pw.Widget _buildDisclaimer() {
    return pw.Container(
      padding: const pw.EdgeInsets.all(12),
      decoration: pw.BoxDecoration(
        color: PdfColors.grey100,
        borderRadius: pw.BorderRadius.circular(4),
      ),
      child: pw.Text(
        'DISCLAIMER: This report is generated by AfriMine AI based on field samples and AI analysis. '
        'Results are preliminary estimates and should not be used as the sole basis for investment decisions. '
        'Professional geological surveys, laboratory assays, and due diligence are required before any '
        'mining investment or resource claims.',
        style: pw.TextStyle(fontSize: 8, color: PdfColors.grey700, fontStyle: pw.FontStyle.italic),
      ),
    );
  }
}
