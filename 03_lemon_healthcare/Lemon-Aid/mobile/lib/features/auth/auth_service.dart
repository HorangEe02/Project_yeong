// features/auth/auth_service.dart — Supabase 기반 로그인 seam (가이드 01 3단계)
//
// 이 추상은 token_session.dart 의 operator dev 토큰 paste 를 대체할 자리다:
// 키(라이브 Supabase URL/anon key + 소셜 프로바이더 키)가 도착하면
// supabase_flutter 기반 SupabaseAuthService 가 이 인터페이스를 구현하고,
// AuthSessionBinder 가 발급 토큰을 TokenSessionController 로 흘려보낸다.
// 인터페이스로 두어 키/패키지 없이도 컴파일·테스트되며 배선만 남긴다
// (supabase_flutter 패키지는 Supabase.initialize 에 키가 필요하므로 키 도착
// 시 함께 추가한다 — 현재 추가 시 초기화 불가·미사용 의존성).

/// 로그인 화면이 제공하는 소셜 신원 제공자.
enum AuthSocialProvider {
  /// 카카오 OAuth.
  kakao,

  /// Apple 로그인.
  apple,

  /// Google OAuth.
  google,
}

/// 로그인/가입 흐름을 떠받치는 인증 표면.
///
/// supabase_flutter 의 GoTrue 표면 중 앱에 필요한 부분만 추린 계약이다.
/// 구현체는 액세스 토큰을 발급하고 [accessTokenChanges] 로 변화를 통지하며,
/// 자격증명/네트워크 오류 시 예외를 던진다(호출자가 사용자 메시지로 변환).
/// 이메일 인증 재전송(resend)·세션 갱신(refreshSession)은 최소 계약에서 제외했고,
/// SupabaseAuthService 구현 시 필요하면 추가한다(인터페이스 변경은 컴파일 타임에 잡힘).
abstract class AuthService {
  /// 현재 액세스 토큰. 로그아웃 상태면 null.
  String? get currentAccessToken;

  /// 인증 상태 변화마다 액세스 토큰을 방출한다(로그아웃 시 null).
  Stream<String?> get accessTokenChanges;

  /// 이메일/비밀번호로 로그인한다.
  Future<void> signInWithEmail({
    required String email,
    required String password,
  });

  /// 이메일/비밀번호 계정을 새로 만든다.
  Future<void> signUpWithEmail({
    required String email,
    required String password,
  });

  /// [provider] 로 소셜 OAuth 로그인을 시작한다.
  Future<void> signInWithSocial(AuthSocialProvider provider);

  /// [email] 로 비밀번호 복구 메일을 보낸다.
  Future<void> sendPasswordReset(String email);

  /// 로그아웃하고 현재 세션을 비운다.
  Future<void> signOut();
}
