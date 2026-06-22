// features/ai_coaching/ai_coaching_repository.dart — 오늘의 분석 API 저장소
//
// `/ai-agent/daily-coaching` 호출을 캡슐화한다. 화면은 이 저장소만 호출하고
// 페이로드 구성·동의 재시도·응답 파싱은 모두 여기서 담당한다 (chat_repository 동일 패턴).

import 'dart:math';

import '../../core/api/api_client.dart';
import '../../core/api/api_error.dart';
import '../dashboard/home_models.dart';
import 'ai_coaching_models.dart';

/// Backend-facing repository for the daily analysis tab.
class AiCoachingRepository {
  /// Creates a daily-coaching repository.
  ///
  /// Args:
  ///   apiClient: Minimal API client for `/api/v1`.
  AiCoachingRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  /// Daily coaching endpoint below `/api/v1`.
  static const String _coachingPath = '/ai-agent/daily-coaching';

  /// Consent grant endpoint for sensitive health analysis.
  static const String _consentPath =
      '/me/privacy/consents/sensitive_health_analysis';

  final ApiClient _apiClient;
  final Random _random = Random();

  /// Runs daily coaching for [day] using today's confirmed meals and supplements.
  ///
  /// On a `403` with `consent_required`, grants the sensitive-health-analysis
  /// consent once and retries the original request (same as the chat tab).
  ///
  /// Args:
  ///   day: Analysis date used for the payload and the request cache key.
  ///   meals: Today's confirmed meals to map into the `foods` payload.
  ///   supplements: Registered supplements to map into the `supplements` payload.
  ///
  /// Returns:
  ///   Parsed [DailyCoachingResult].
  ///
  /// Raises:
  ///   ApiError: If the backend returns an unexpected status code.
  Future<DailyCoachingResult> runDailyCoaching({
    required DateTime day,
    required List<HomeMeal> meals,
    required List<HomeSupplement> supplements,
  }) async {
    final DailyCoachingRequest request = DailyCoachingRequest(
      requestId: _newRequestId(),
      date: _formatDate(day),
      foods: meals.expand(_foodsForMeal).toList(growable: false),
      supplements: supplements
          .map(_supplementPayload)
          .toList(growable: false),
    );
    final Map<String, dynamic> body = request.toJson();
    try {
      return await _postCoaching(body);
    } on ApiError catch (error) {
      if (!_isConsentRequired(error)) {
        rethrow;
      }
      await _grantSensitiveHealthAnalysisConsent();
      // Retry exactly once after the consent is granted.
      return _postCoaching(body);
    }
  }

  /// Releases repository resources.
  void close() {
    _apiClient.close();
  }

  Future<DailyCoachingResult> _postCoaching(Map<String, dynamic> body) async {
    final Map<String, dynamic> json = await _apiClient.postJson(
      _coachingPath,
      body: body,
    );
    return DailyCoachingResult.fromJson(json);
  }

  Future<void> _grantSensitiveHealthAnalysisConsent() async {
    await _apiClient.postJson(
      _consentPath,
      expectedStatusCodes: const <int>{201},
    );
  }

  /// Maps a meal's food items into the agent `foods` payload entries.
  ///
  /// lemon_ai_agent `app_intake._build_food` 계약: `name`/`meal_type` 필수,
  /// 영양소는 `nutrients[{name, amount, unit}]`. `display_name` 류 키는
  /// KeyError 로 코칭 전체가 실패한다(첫 라이브 E2E 스모크에서 확인).
  /// 값이 없는 영양소는 0 으로 지어내지 않고 생략한다.
  List<Map<String, dynamic>> _foodsForMeal(HomeMeal meal) {
    return meal.foodItems
        .map(
          (HomeFoodItem item) => <String, dynamic>{
            'name': item.displayName,
            'meal_type': meal.mealType,
            'nutrients': <Map<String, dynamic>>[
              if (item.proteinG > 0)
                <String, dynamic>{
                  'name': 'protein',
                  'amount': item.proteinG,
                  'unit': 'g',
                },
              if (item.carbG > 0)
                <String, dynamic>{
                  'name': 'carbohydrate',
                  'amount': item.carbG,
                  'unit': 'g',
                },
              if (item.fatG > 0)
                <String, dynamic>{
                  'name': 'fat',
                  'amount': item.fatG,
                  'unit': 'g',
                },
            ],
          },
        )
        .toList(growable: false);
  }

  /// Maps a registered supplement into the agent `supplements` payload entry.
  Map<String, dynamic> _supplementPayload(HomeSupplement supplement) {
    return <String, dynamic>{
      'product_name': supplement.displayName,
      'ingredients': <Map<String, dynamic>>[],
      'times_per_day': supplement.schedule?.timesPerDay ?? 1,
      'user_confirmed': true,
    };
  }

  /// Formats [day] as a `YYYY-MM-DD` date string.
  String _formatDate(DateTime day) {
    final String month = day.month.toString().padLeft(2, '0');
    final String date = day.day.toString().padLeft(2, '0');
    return '${day.year}-$month-$date';
  }

  /// Builds a unique request id from a timestamp and random suffix.
  String _newRequestId() {
    final int micros = DateTime.now().microsecondsSinceEpoch;
    final int salt = _random.nextInt(1 << 32);
    return 'mobile-daily-coaching-$micros-${salt.toRadixString(16)}';
  }

  static bool _isConsentRequired(ApiError error) {
    return error.statusCode == 403 && error.code == 'consent_required';
  }
}
