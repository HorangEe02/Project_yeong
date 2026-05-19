/// 인증 도메인 예외 — Repository 가 던지고 Notifier 가 catch 해 사용자 메시지로 변환.
library;

/// 422 응답에서 detail.code == "consent_required" 일 때.
///
/// missing 에는 백엔드가 요구한 추가 동의 타입 리스트 (예: ["chronic_disease"]).
class ConsentRequiredException implements Exception {
  const ConsentRequiredException(this.missing);
  final List<String> missing;

  @override
  String toString() => 'ConsentRequiredException(missing=$missing)';
}

/// 409 — 이미 가입된 이메일.
class EmailAlreadyExistsException implements Exception {
  const EmailAlreadyExistsException();
}

/// 401 — 잘못된 credentials.
class InvalidCredentialsException implements Exception {
  const InvalidCredentialsException();
}

/// 401 + refresh 실패 → 자동 로그아웃 트리거.
class RefreshFailedException implements Exception {
  const RefreshFailedException();
}
