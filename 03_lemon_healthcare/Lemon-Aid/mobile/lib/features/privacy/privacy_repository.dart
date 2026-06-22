// features/privacy/privacy_repository.dart — 동의 관리 · 탈퇴 저장소
//
// 가이드 08 (f) · 백엔드 privacy.py 계약.
//   consents()         = GET    /me/privacy/consents
//   grant(type)        = POST   /me/privacy/consents/{type}      (201)
//   revoke(type)       = DELETE /me/privacy/consents/{type}      (200)
//   requestDeletion()  = POST   /me/data-deletion-requests       (202)
//   deletionStatus(id) = GET    /me/data-deletion-requests/{id}
//
// 탈퇴 사유 서버 수집 필드는 백엔드 공백(DeletionRequestCreate 에 사유 없음) —
// 사유는 로컬 수집만 한다.

import '../../core/api/api_client.dart';

/// 사용자가 설정에서 다루는 동의 6종.
///
/// 백엔드 ConsentType 9종 중 사용자 노출 대상만 선별(가이드 (f)).
enum UserConsentType {
  /// 민감 건강 분석.
  sensitiveHealthAnalysis('sensitive_health_analysis', '민감 건강 분석'),

  /// 건강 기기 데이터.
  healthDeviceData('health_device_data', '건강 기기 데이터'),

  /// OCR 이미지 처리.
  ocrImageProcessing('ocr_image_processing', 'OCR 이미지 처리'),

  /// 음식 이미지 처리.
  foodImageProcessing('food_image_processing', '음식 이미지 처리'),

  /// 데이터 보관.
  dataRetention('data_retention', '데이터 보관'),

  /// OCR 원문(텍스트) 임시 보관 — "OCR 텍스트 전체"에서 원문 확인용.
  rawOcrTextRetention('raw_ocr_text_retention', 'OCR 원문 보관');

  const UserConsentType(this.code, this.label);

  /// 백엔드 동의 코드.
  final String code;

  /// 한국어 표시명.
  final String label;
}

/// 동의 관리 · 탈퇴 백엔드 저장소.
class PrivacyRepository {
  /// API 클라이언트를 주입받아 생성한다.
  PrivacyRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  /// 현재 사용자의 동의 코드별 grant 상태를 가져온다.
  ///
  /// Returns:
  ///   동의 코드 → granted(bool) 맵.
  Future<Map<String, bool>> consents() async {
    final Map<String, dynamic> json = await _apiClient.getJson(
      '/me/privacy/consents',
    );
    final Object? items = json['consents'];
    final Map<String, bool> result = <String, bool>{};
    if (items is List<Object?>) {
      for (final Object? item in items) {
        if (item is Map<String, dynamic>) {
          final Object? type = item['consent_type'] ?? item['type'];
          final Object? granted = item['granted'] ?? item['is_granted'];
          if (type is String) {
            result[type] = granted is bool ? granted : granted != null;
          }
        }
      }
    }
    return result;
  }

  /// 동의를 grant 한다.
  Future<void> grant(UserConsentType type) async {
    await _apiClient.postJson(
      '/me/privacy/consents/${type.code}',
      expectedStatusCodes: const <int>{201},
    );
  }

  /// 동의를 revoke 한다.
  Future<void> revoke(UserConsentType type) async {
    await _apiClient.delete(
      '/me/privacy/consents/${type.code}',
      expectedStatusCodes: const <int>{200},
    );
  }

  /// 전체 데이터 삭제 요청을 보낸다 (202).
  ///
  /// Returns:
  ///   삭제 요청 id (없으면 빈 문자열).
  Future<String> requestDeletion() async {
    final Map<String, dynamic> json = await _apiClient.postJson(
      '/me/data-deletion-requests',
      body: <String, dynamic>{'request_type': 'all_user_data'},
      expectedStatusCodes: const <int>{202},
    );
    return (json['id'] as Object?)?.toString() ?? '';
  }

  /// 삭제 요청 상태를 조회한다.
  Future<String> deletionStatus(String requestId) async {
    final Map<String, dynamic> json = await _apiClient.getJson(
      '/me/data-deletion-requests/${Uri.encodeComponent(requestId)}',
    );
    return (json['status'] as Object?)?.toString() ?? '';
  }

  /// 리포지토리 자원을 정리한다.
  void close() {
    _apiClient.close();
  }
}
