/// 인증 상태 — sealed class 로 Dart 3 switch 표현식 강제.
library;

import 'auth_models.dart';

sealed class AuthState {
  const AuthState();
}

/// 토큰 없음 / 로그아웃됨 — 보호된 경로 접근 시 /login 으로 redirect.
class Unauthenticated extends AuthState {
  const Unauthenticated();
}

/// 로그인/회원가입/refresh 진행 중.
class Authenticating extends AuthState {
  const Authenticating();
}

/// 토큰 보유 + 사용자 정보 확인됨.
class Authenticated extends AuthState {
  const Authenticated(this.user);
  final User user;
}

/// 실패 — 사용자에게 표시할 한국어 메시지.
class AuthFailed extends AuthState {
  const AuthFailed(this.message);
  final String message;
}
