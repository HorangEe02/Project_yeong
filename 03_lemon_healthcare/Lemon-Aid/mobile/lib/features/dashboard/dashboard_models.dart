import '../../shared/models/json_readers.dart';
import 'home_models.dart';

/// Dashboard summary response displayed on the mobile home tab.
class DashboardSummary {
  /// Creates a dashboard summary.
  const DashboardSummary({
    required this.asOf,
    required this.nutrition,
    required this.activity,
    required this.weight,
    required this.supplements,
    required this.disclaimers,
    required this.algorithmVersion,
    this.healthScore = const DashboardHealthScore(
      status: HealthScoreStatus.notReady,
    ),
  });

  /// Server-side summary timestamp.
  final DateTime asOf;

  /// Nutrition summary.
  final DashboardNutritionSummary nutrition;

  /// Activity summary.
  final DashboardActivitySummary activity;

  /// Weight summary.
  final DashboardWeightSummary weight;

  /// Supplement summary.
  final DashboardSupplementSummary supplements;

  /// User-facing backend disclaimers.
  final List<String> disclaimers;

  /// Dashboard aggregation contract version.
  final String algorithmVersion;

  /// Optional daily health score block (not_ready when the backend omits it).
  final DashboardHealthScore healthScore;

  /// Parses a backend dashboard summary response.
  factory DashboardSummary.fromJson(Map<String, dynamic> json) {
    return DashboardSummary(
      asOf: DateTime.parse(readString(json, 'as_of')),
      nutrition: DashboardNutritionSummary.fromJson(
        readObject(json, 'nutrition'),
      ),
      activity: DashboardActivitySummary.fromJson(readObject(json, 'activity')),
      weight: DashboardWeightSummary.fromJson(readObject(json, 'weight')),
      supplements: DashboardSupplementSummary.fromJson(
        readObject(json, 'supplements'),
      ),
      disclaimers: readStringList(json, 'disclaimers'),
      algorithmVersion: readString(json, 'algorithm_version'),
      healthScore: DashboardHealthScore.fromSummaryJson(json),
    );
  }
}

/// Nutrition counts shown in the dashboard summary.
class DashboardNutritionSummary {
  /// Creates a nutrition summary.
  const DashboardNutritionSummary({
    required this.dataStatus,
    required this.lowCount,
    required this.highCount,
    required this.datasetVersion,
  });

  /// Whether persisted nutrition data is ready.
  final String dataStatus;

  /// Number of low nutrients.
  final int lowCount;

  /// Number of high nutrients.
  final int highCount;

  /// Nutrition dataset version.
  final String? datasetVersion;

  /// Parses a backend nutrition summary.
  factory DashboardNutritionSummary.fromJson(Map<String, dynamic> json) {
    return DashboardNutritionSummary(
      dataStatus: readString(json, 'data_status'),
      lowCount: readInt(json, 'low_count'),
      highCount: readInt(json, 'high_count'),
      datasetVersion: readOptionalString(json, 'dataset_version'),
    );
  }
}

/// Activity values shown in the dashboard summary.
class DashboardActivitySummary {
  /// Creates an activity summary.
  const DashboardActivitySummary({
    required this.dataStatus,
    required this.latestSteps,
    required this.latestActivityScore,
  });

  /// Whether persisted activity data is ready.
  final String dataStatus;

  /// Latest step count.
  final int? latestSteps;

  /// Latest activity score.
  final double? latestActivityScore;

  /// Parses a backend activity summary.
  factory DashboardActivitySummary.fromJson(Map<String, dynamic> json) {
    return DashboardActivitySummary(
      dataStatus: readString(json, 'data_status'),
      latestSteps: readOptionalInt(json, 'latest_steps'),
      latestActivityScore: readOptionalDouble(json, 'latest_activity_score'),
    );
  }
}

/// Weight values shown in the dashboard summary.
class DashboardWeightSummary {
  /// Creates a weight summary.
  const DashboardWeightSummary({
    required this.dataStatus,
    required this.latestWeightKg,
    required this.predictedWeightKg,
  });

  /// Whether persisted weight data is ready.
  final String dataStatus;

  /// Latest weight in kilograms.
  final double? latestWeightKg;

  /// Latest predicted weight in kilograms.
  final double? predictedWeightKg;

  /// Parses a backend weight summary.
  factory DashboardWeightSummary.fromJson(Map<String, dynamic> json) {
    return DashboardWeightSummary(
      dataStatus: readString(json, 'data_status'),
      latestWeightKg: readOptionalDouble(json, 'latest_weight_kg'),
      predictedWeightKg: readOptionalDouble(json, 'predicted_weight_kg'),
    );
  }
}

/// Supplement values shown in the dashboard summary.
class DashboardSupplementSummary {
  /// Creates a supplement summary.
  const DashboardSupplementSummary({
    required this.registeredCount,
    required this.requiresReviewCount,
  });

  /// Current-user registered supplement count.
  final int registeredCount;

  /// Supplement records requiring review.
  final int requiresReviewCount;

  /// Parses a backend supplement summary.
  factory DashboardSupplementSummary.fromJson(Map<String, dynamic> json) {
    return DashboardSupplementSummary(
      registeredCount: readInt(json, 'registered_count'),
      requiresReviewCount: readInt(json, 'requires_review_count'),
    );
  }
}
