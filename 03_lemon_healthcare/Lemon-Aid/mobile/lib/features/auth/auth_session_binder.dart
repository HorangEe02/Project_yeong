// features/auth/auth_session_binder.dart — AuthService → 세션 토큰 브리지
//
// AuthService 의 액세스 토큰 스트림을 TokenSessionController 로 흘려보낸다.
// 토큰이 들어오면 세션이 채택(다운스트림 ApiClient 가 bearerToken 재사용)하고,
// null(로그아웃)이면 비운다. 이 배선이 Supabase 세션으로 operator 토큰 paste 를
// 대체하면서 다운스트림은 그대로 두게 한다.

import 'dart:async';

import 'auth_service.dart';
import 'token_session.dart';

/// [AuthService] 토큰 스트림을 [TokenSessionController] 에 연결하는 브리지.
class AuthSessionBinder {
  /// [authService] 와 [session] 을 잇는 브리지를 만든다.
  AuthSessionBinder({
    required AuthService authService,
    required TokenSessionController session,
  }) : _authService = authService,
       _session = session;

  final AuthService _authService;
  final TokenSessionController _session;
  StreamSubscription<String?>? _subscription;
  bool _disposed = false;

  /// 인증 상태 토큰 변화를 세션으로 전달하기 시작한다(중복 start 무해).
  void start() {
    if (_disposed) return;
    _subscription ??= _authService.accessTokenChanges.listen(_apply);
  }

  Future<void> _apply(String? token) async {
    // dispose 후 도착한(또는 진행 중이던) 이벤트는 세션을 건드리지 않는다 —
    // 실제 SecureBearerTokenStore 배선 시 dispose 후 저장소 쓰기를 막는다.
    if (_disposed) return;
    if (token == null || token.trim().isEmpty) {
      await _session.clearBearerToken();
    } else {
      await _session.saveBearerToken(token);
    }
  }

  /// 전달을 멈추고 구독을 해제한다. 호출 후 이 바인더는 재사용할 수 없다.
  Future<void> dispose() async {
    _disposed = true;
    await _subscription?.cancel();
    _subscription = null;
  }
}
