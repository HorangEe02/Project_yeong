// features/profile/profile_repository.dart — 신체 정보 스냅샷 저장소
//
// 가이드 08 (a). `GET /health/profile-snapshots/latest` 로 최신 스냅샷을 읽고
// `POST /health/profile-snapshots` 로 저장한다. 403 consent_required 수신 시
// sensitive_health_analysis 동의를 1회 grant 한 뒤 재시도한다(chat_repository 패턴).

import '../../core/api/api_client.dart';
import '../../core/api/api_error.dart';
import 'profile_models.dart';

/// 신체 정보 스냅샷 백엔드 저장소.
class ProfileRepository {
  /// API 클라이언트를 주입받아 생성한다.
  ProfileRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  /// 최신 스냅샷 조회 경로 (ApiClient base 가 이미 `/api/v1` 로 끝남).
  static const String _latestPath = '/health/profile-snapshots/latest';

  /// 스냅샷 생성 경로.
  static const String _createPath = '/health/profile-snapshots';

  /// 민감 건강 분석 동의 grant 경로.
  static const String _consentPath =
      '/me/privacy/consents/sensitive_health_analysis';

  final ApiClient _apiClient;

  /// 최신 신체 정보 스냅샷을 가져온다 (없으면 null).
  Future<BodyProfileSnapshot?> fetchLatest() async {
    final Map<String, dynamic> json = await _withConsentRetry(
      () => _apiClient.getJson(_latestPath),
    );
    return BodyProfileSnapshot.fromLatestJson(json);
  }

  /// 신체 정보 스냅샷을 저장하고 저장된 스냅샷을 돌려준다.
  Future<BodyProfileSnapshot?> save(BodyProfileSnapshot snapshot) async {
    final Map<String, dynamic> json = await _withConsentRetry(
      () => _apiClient.postJson(
        _createPath,
        body: snapshot.toCreateJson(),
        expectedStatusCodes: const <int>{201},
      ),
    );
    return BodyProfileSnapshot.fromLatestJson(json);
  }

  /// 리포지토리 자원을 정리한다.
  void close() {
    _apiClient.close();
  }

  /// [request] 를 실행하고, 403 consent_required 면 동의 1회 후 재시도한다.
  Future<Map<String, dynamic>> _withConsentRetry(
    Future<Map<String, dynamic>> Function() request,
  ) async {
    try {
      return await request();
    } on ApiError catch (error) {
      if (!_isConsentRequired(error)) rethrow;
      await _grantSensitiveHealthAnalysisConsent();
      return request();
    }
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
