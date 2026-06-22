import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/auth/auth_service.dart';
import 'package:lemon_aid_mobile/features/auth/auth_session_binder.dart';
import 'package:lemon_aid_mobile/features/auth/token_session.dart';

/// Stream-driven fake AuthService for binder tests (no live Supabase).
class _FakeAuthService implements AuthService {
  final StreamController<String?> _controller =
      StreamController<String?>.broadcast();
  String? _current;

  void emit(String? token) {
    _current = token;
    _controller.add(token);
  }

  Future<void> close() => _controller.close();

  @override
  String? get currentAccessToken => _current;

  @override
  Stream<String?> get accessTokenChanges => _controller.stream;

  @override
  Future<void> signInWithEmail({
    required String email,
    required String password,
  }) async {}

  @override
  Future<void> signUpWithEmail({
    required String email,
    required String password,
  }) async {}

  @override
  Future<void> signInWithSocial(AuthSocialProvider provider) async {}

  @override
  Future<void> sendPasswordReset(String email) async {}

  @override
  Future<void> signOut() async {}
}

void main() {
  test('binder adopts an emitted access token into the session', () async {
    final _FakeAuthService auth = _FakeAuthService();
    final TokenSessionController session = TokenSessionController(
      store: MemoryBearerTokenStore(),
      releaseMode: true,
    );
    final AuthSessionBinder binder = AuthSessionBinder(
      authService: auth,
      session: session,
    )..start();
    addTearDown(() async {
      await binder.dispose();
      await auth.close();
    });

    auth.emit('header.payload.sig');
    await pumpEventQueue();

    expect(session.bearerToken, 'header.payload.sig');
  });

  test('binder clears the session on sign-out (null token)', () async {
    final _FakeAuthService auth = _FakeAuthService();
    final TokenSessionController session = TokenSessionController(
      store: MemoryBearerTokenStore(initialToken: 'old.token.sig'),
      releaseMode: true,
    );
    await session.bootstrap();
    final AuthSessionBinder binder = AuthSessionBinder(
      authService: auth,
      session: session,
    )..start();
    addTearDown(() async {
      await binder.dispose();
      await auth.close();
    });

    auth.emit(null);
    await pumpEventQueue();

    expect(session.bearerToken, isNull);
  });

  test('binder stops forwarding after dispose', () async {
    final _FakeAuthService auth = _FakeAuthService();
    final TokenSessionController session = TokenSessionController(
      store: MemoryBearerTokenStore(),
      releaseMode: true,
    );
    final AuthSessionBinder binder = AuthSessionBinder(
      authService: auth,
      session: session,
    )..start();
    addTearDown(auth.close);

    await binder.dispose();
    auth.emit('late.token.sig');
    await pumpEventQueue();

    expect(session.bearerToken, isNull);
  });
}
