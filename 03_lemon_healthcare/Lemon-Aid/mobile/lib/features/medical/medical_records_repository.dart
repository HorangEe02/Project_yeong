// features/medical/medical_records_repository.dart — 만성질환 레코드 저장소
//
// 가이드 08 (b) · 백엔드 medical_records.py 계약.
//   list()           = GET  /medical-records
//   addCondition()   = POST /medical-records (201) → POST /medical-records/{id}/confirm
//   archive()        = POST /medical-records/{id}/confirm  {status:"archived"}
// 403 consent_required 수신 시 sensitive_health_analysis 동의 1회 후 재시도.

import '../../core/api/api_client.dart';
import '../../core/api/api_error.dart';
import 'medical_models.dart';

/// 만성질환(의료) 레코드 백엔드 저장소.
class MedicalRecordsRepository {
  /// API 클라이언트를 주입받아 생성한다.
  MedicalRecordsRepository({required ApiClient apiClient})
    : _apiClient = apiClient;

  /// 레코드 목록·생성 경로 (ApiClient base 가 이미 `/api/v1` 로 끝남).
  static const String _recordsPath = '/medical-records';

  /// 민감 건강 분석 동의 grant 경로.
  static const String _consentPath =
      '/me/privacy/consents/sensitive_health_analysis';

  /// 백엔드 condition_text 최대 길이 (PatientConditionInput).
  static const int maxConditionTextLength = 180;

  final ApiClient _apiClient;

  /// 만성질환 레코드 목록을 가져온다.
  ///
  /// Args:
  ///   includeArchived: archived 레코드 포함 여부.
  Future<List<MedicalRecord>> list({bool includeArchived = false}) async {
    final Map<String, dynamic> json = await _withConsentRetry(
      () => _apiClient.getJson(
        _recordsPath,
        queryParameters: <String, String>{
          'include_archived': includeArchived.toString(),
        },
      ),
    );
    return MedicalRecord.listFromJson(json);
  }

  /// 만성질환을 추가한다 (create → confirm 2단계).
  ///
  /// Returns:
  ///   확정된 [MedicalRecord].
  Future<MedicalRecord> addCondition(String text) async {
    final String trimmed = text.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError.value(text, 'text', '질환명을 입력해주세요.');
    }
    final String capped = trimmed.length > maxConditionTextLength
        ? trimmed.substring(0, maxConditionTextLength)
        : trimmed;

    final Map<String, dynamic> created = await _withConsentRetry(
      () => _apiClient.postJson(
        _recordsPath,
        body: <String, dynamic>{
          'record_type': 'condition',
          'source': 'user_manual',
          'condition': <String, dynamic>{
            'condition_text': capped,
            'clinical_status': 'active',
            'source': 'user_confirmed',
          },
          'user_confirmed': true,
        },
        expectedStatusCodes: const <int>{201},
      ),
    );
    final String recordId = (created['id'] as Object?)?.toString() ?? '';
    return _confirm(recordId, status: 'active');
  }

  /// 만성질환을 보관 처리한다 (confirm status:"archived").
  Future<MedicalRecord> archive(String recordId) {
    return _confirm(recordId, status: 'archived');
  }

  /// 리포지토리 자원을 정리한다.
  void close() {
    _apiClient.close();
  }

  Future<MedicalRecord> _confirm(
    String recordId, {
    required String status,
  }) async {
    final String encodedId = Uri.encodeComponent(recordId);
    final Map<String, dynamic> json = await _withConsentRetry(
      () => _apiClient.postJson(
        '$_recordsPath/$encodedId/confirm',
        body: <String, dynamic>{'user_confirmed': true, 'status': status},
        expectedStatusCodes: const <int>{200},
      ),
    );
    return MedicalRecord.fromJson(json);
  }

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
