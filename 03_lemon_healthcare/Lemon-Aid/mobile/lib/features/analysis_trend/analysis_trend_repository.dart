// features/analysis_trend/analysis_trend_repository.dart — 4주 추이 API 저장소
//
// `/analysis-results` 목록 조회를 캡슐화한다. 점수 이력도 민감 건강 분석
// 스코프라 403 동의 재시도 패턴을 ai_coaching_repository와 동일하게 적용한다.

import '../../core/api/api_client.dart';
import '../../core/api/api_error.dart';
import 'analysis_trend_models.dart';

/// Backend-facing repository for the daily health score trend.
class AnalysisTrendRepository {
  /// Creates an analysis trend repository.
  ///
  /// Args:
  ///   apiClient: Minimal API client for `/api/v1`.
  AnalysisTrendRepository({required ApiClient apiClient})
    : _apiClient = apiClient;

  /// Analysis results list endpoint below `/api/v1`.
  static const String _listPath = '/analysis-results';

  /// Consent grant endpoint for sensitive health analysis.
  static const String _consentPath =
      '/me/privacy/consents/sensitive_health_analysis';

  final ApiClient _apiClient;

  /// Fetches up to [limit] persisted daily health score points (date ascending).
  ///
  /// On a `403` with `consent_required`, grants the sensitive-health-analysis
  /// consent once and retries the original request (same as the coaching tab).
  ///
  /// Args:
  ///   limit: Maximum rows to request (4주 추이 기본 28).
  ///
  /// Returns:
  ///   Parsed [ScoreTrendPoint] list, oldest first.
  ///
  /// Raises:
  ///   ApiError: If the backend returns an unexpected status code.
  Future<List<ScoreTrendPoint>> fetchDailyScoreTrend({int limit = 28}) async {
    try {
      return await _getTrend(limit);
    } on ApiError catch (error) {
      if (!_isConsentRequired(error)) {
        rethrow;
      }
      await _grantSensitiveHealthAnalysisConsent();
      // Retry exactly once after the consent is granted.
      return _getTrend(limit);
    }
  }

  Future<List<ScoreTrendPoint>> _getTrend(int limit) async {
    final Map<String, dynamic> json = await _apiClient.getJson(
      _listPath,
      queryParameters: <String, String>{
        'analysis_type': 'daily_health_score',
        'limit': '$limit',
      },
    );
    return ScoreTrendPoint.listFromJson(json);
  }

  Future<void> _grantSensitiveHealthAnalysisConsent() async {
    await _apiClient.postJson(
      _consentPath,
      expectedStatusCodes: const <int>{201},
    );
  }

  static bool _isConsentRequired(ApiError error) {
    return error.statusCode == 403 && error.code == 'consent_required';
  }
}
