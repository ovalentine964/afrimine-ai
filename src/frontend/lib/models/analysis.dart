import 'dart:convert';

/// Status of an analysis pipeline run.
enum AnalysisStatus {
  pending,
  running,
  completed,
  failed;

  factory AnalysisStatus.fromString(String value) {
    return AnalysisStatus.values.firstWhere(
      (e) => e.name == value,
      orElse: () => AnalysisStatus.pending,
    );
  }
}

/// Result from the Analysis Agent — mineral classification.
class AnalysisResult {
  final List<String> detectedMinerals;
  final String? dominantMineral;
  final double confidenceScore;
  final String? rockType;
  final String? alteration;
  final Map<String, dynamic>? rawOutput;

  const AnalysisResult({
    required this.detectedMinerals,
    this.dominantMineral,
    required this.confidenceScore,
    this.rockType,
    this.alteration,
    this.rawOutput,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    return AnalysisResult(
      detectedMinerals: (json['detected_minerals'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      dominantMineral: json['dominant_mineral'] as String?,
      confidenceScore: (json['confidence_score'] as num?)?.toDouble() ?? 0.0,
      rockType: json['rock_type'] as String?,
      alteration: json['alteration'] as String?,
      rawOutput: json,
    );
  }
}

/// Result from the Geology Agent — geological context.
class GeologyResult {
  final String? beltName;
  final String? formation;
  final String? depositModel;
  final double? resourcePotential;
  final String? geologicalContext;
  final List<String> pathfinders;
  final Map<String, dynamic>? rawOutput;

  const GeologyResult({
    this.beltName,
    this.formation,
    this.depositModel,
    this.resourcePotential,
    this.geologicalContext,
    this.pathfinders = const [],
    this.rawOutput,
  });

  factory GeologyResult.fromJson(Map<String, dynamic> json) {
    return GeologyResult(
      beltName: json['belt_name'] as String?,
      formation: json['formation'] as String?,
      depositModel: json['deposit_model'] as String?,
      resourcePotential: (json['resource_potential'] as num?)?.toDouble(),
      geologicalContext: json['geological_context'] as String?,
      pathfinders: (json['pathfinders'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      rawOutput: json,
    );
  }
}

/// Result from the Market Agent — valuation data.
class MarketResult {
  final Map<String, double> commodityPrices;
  final double? estimatedValueUsd;
  final double? cutOffGrade;
  final String? priceTrend;
  final double? royaltyRate;
  final Map<String, dynamic>? rawOutput;

  const MarketResult({
    required this.commodityPrices,
    this.estimatedValueUsd,
    this.cutOffGrade,
    this.priceTrend,
    this.royaltyRate,
    this.rawOutput,
  });

  factory MarketResult.fromJson(Map<String, dynamic> json) {
    final prices = <String, double>{};
    if (json['commodity_prices'] is Map) {
      (json['commodity_prices'] as Map).forEach((k, v) {
        prices[k.toString()] = (v as num).toDouble();
      });
    }
    return MarketResult(
      commodityPrices: prices,
      estimatedValueUsd: (json['estimated_value_usd'] as num?)?.toDouble(),
      cutOffGrade: (json['cut_off_grade'] as num?)?.toDouble(),
      priceTrend: json['price_trend'] as String?,
      royaltyRate: (json['royalty_rate'] as num?)?.toDouble(),
      rawOutput: json,
    );
  }
}

/// Result from the Compliance Agent.
class ComplianceResult {
  final bool isCompliant;
  final String? licenseType;
  final String? eiaStatus;
  final List<String> issues;
  final List<String> requirements;
  final Map<String, dynamic>? rawOutput;

  const ComplianceResult({
    required this.isCompliant,
    this.licenseType,
    this.eiaStatus,
    this.issues = const [],
    this.requirements = const [],
    this.rawOutput,
  });

  factory ComplianceResult.fromJson(Map<String, dynamic> json) {
    return ComplianceResult(
      isCompliant: json['is_compliant'] as bool? ?? false,
      licenseType: json['license_type'] as String?,
      eiaStatus: json['eia_status'] as String?,
      issues: (json['issues'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      requirements: (json['requirements'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      rawOutput: json,
    );
  }
}

/// Complete analysis record — aggregates all agent outputs.
class Analysis {
  final String id;
  final String? userId;
  final List<String> sampleIds;
  final AnalysisStatus status;
  final AnalysisResult? analysisResult;
  final GeologyResult? geologyResult;
  final MarketResult? marketResult;
  final ComplianceResult? complianceResult;
  final String? reportUrl;
  final String? reportHtml;
  final double? estimatedGrade;
  final String? gradeUnit;
  final double? confidenceScore;
  final double? estimatedValueUsd;
  final int? pipelineDurationMs;
  final bool isSynced;
  final DateTime createdAt;
  final DateTime? completedAt;

  const Analysis({
    required this.id,
    this.userId,
    this.sampleIds = const [],
    required this.status,
    this.analysisResult,
    this.geologyResult,
    this.marketResult,
    this.complianceResult,
    this.reportUrl,
    this.reportHtml,
    this.estimatedGrade,
    this.gradeUnit,
    this.confidenceScore,
    this.estimatedValueUsd,
    this.pipelineDurationMs,
    this.isSynced = false,
    required this.createdAt,
    this.completedAt,
  });

  factory Analysis.fromJson(Map<String, dynamic> json) {
    final agentOutputs = json['agent_outputs'] as Map<String, dynamic>? ?? {};

    return Analysis(
      id: json['id'] as String? ?? json['analysis_id'] as String? ?? '',
      userId: json['user_id'] as String?,
      sampleIds: (json['sample_ids'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      status: AnalysisStatus.fromString(json['status'] as String? ?? 'pending'),
      analysisResult: agentOutputs['analysis_result'] != null
          ? AnalysisResult.fromJson(agentOutputs['analysis_result'] as Map<String, dynamic>)
          : json['analysis_result'] != null
              ? AnalysisResult.fromJson(json['analysis_result'] as Map<String, dynamic>)
              : null,
      geologyResult: agentOutputs['geology_result'] != null
          ? GeologyResult.fromJson(agentOutputs['geology_result'] as Map<String, dynamic>)
          : null,
      marketResult: agentOutputs['market_result'] != null
          ? MarketResult.fromJson(agentOutputs['market_result'] as Map<String, dynamic>)
          : null,
      complianceResult: agentOutputs['compliance_result'] != null
          ? ComplianceResult.fromJson(agentOutputs['compliance_result'] as Map<String, dynamic>)
          : null,
      reportUrl: json['report_url'] as String?,
      reportHtml: json['report_html'] as String?,
      estimatedGrade: (json['estimated_grade'] as num?)?.toDouble(),
      gradeUnit: json['grade_unit'] as String?,
      confidenceScore: (json['confidence_score'] as num?)?.toDouble(),
      estimatedValueUsd: (json['estimated_value_usd'] as num?)?.toDouble(),
      pipelineDurationMs: json['pipeline_duration_ms'] as int?,
      isSynced: json['is_synced'] == true,
      createdAt: DateTime.parse(json['created_at'] as String),
      completedAt: json['completed_at'] != null
          ? DateTime.tryParse(json['completed_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'user_id': userId,
        'sample_ids': sampleIds,
        'status': status.name,
        'estimated_grade': estimatedGrade,
        'grade_unit': gradeUnit,
        'confidence_score': confidenceScore,
        'estimated_value_usd': estimatedValueUsd,
        'pipeline_duration_ms': pipelineDurationMs,
        'report_url': reportUrl,
        'is_synced': isSynced,
        'created_at': createdAt.toIso8601String(),
        if (completedAt != null) 'completed_at': completedAt!.toIso8601String(),
      };

  /// Display title for the analysis.
  String get displayTitle {
    if (analysisResult?.dominantMineral != null) {
      return '${analysisResult!.dominantMineral} Analysis';
    }
    if (analysisResult?.detectedMinerals.isNotEmpty == true) {
      return '${analysisResult!.detectedMinerals.first} Analysis';
    }
    return 'Analysis ${id.substring(0, 8)}';
  }

  /// Confidence as a percentage string.
  String get confidencePercent {
    if (confidenceScore == null) return 'N/A';
    return '${(confidenceScore! * 100).round()}%';
  }

  /// Formatted estimated value.
  String get formattedValue {
    if (estimatedValueUsd == null) return 'N/A';
    if (estimatedValueUsd! >= 1000000) {
      return '\$${(estimatedValueUsd! / 1000000).toStringAsFixed(1)}M';
    }
    if (estimatedValueUsd! >= 1000) {
      return '\$${(estimatedValueUsd! / 1000).toStringAsFixed(1)}K';
    }
    return '\$${estimatedValueUsd!.toStringAsFixed(0)}';
  }

  /// Pipeline duration formatted.
  String get durationText {
    if (pipelineDurationMs == null) return 'N/A';
    final seconds = pipelineDurationMs! / 1000;
    if (seconds >= 60) {
      return '${(seconds / 60).toStringAsFixed(1)} min';
    }
    return '${seconds.toStringAsFixed(0)}s';
  }
}

/// Streaming update from the analysis pipeline.
class AnalysisUpdate {
  final String agent;
  final String status;
  final double progress;
  final String? message;
  final Map<String, dynamic>? data;

  const AnalysisUpdate({
    required this.agent,
    required this.status,
    required this.progress,
    this.message,
    this.data,
  });

  factory AnalysisUpdate.fromJson(Map<String, dynamic> json) {
    return AnalysisUpdate(
      agent: json['agent'] as String? ?? 'unknown',
      status: json['status'] as String? ?? 'working',
      progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
      message: json['message'] as String?,
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}
