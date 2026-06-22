import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/auth/token_session.dart';

void main() {
  test('uses debug dev bypass when no token is stored', () async {
    final TokenSessionController controller = TokenSessionController(
      store: MemoryBearerTokenStore(),
      releaseMode: false,
    );

    await controller.bootstrap();

    expect(controller.bootstrapped, isTrue);
    expect(controller.bearerToken, isNull);
    expect(controller.devBypassActive, isTrue);
    expect(controller.canEnterShell, isTrue);
  });

  test('requires a token in release mode', () async {
    final TokenSessionController controller = TokenSessionController(
      store: MemoryBearerTokenStore(),
      releaseMode: true,
    );

    await controller.bootstrap();

    expect(controller.devBypassActive, isFalse);
    expect(controller.canEnterShell, isFalse);
  });

  test('falls back when token storage bootstrap hangs in debug mode', () async {
    final TokenSessionController controller = TokenSessionController(
      store: _NeverCompletingBearerTokenStore(),
      releaseMode: false,
      bootstrapTimeout: const Duration(milliseconds: 20),
    );

    await controller.bootstrap();

    expect(controller.bootstrapped, isTrue);
    expect(controller.bearerToken, isNull);
    expect(controller.canEnterShell, isTrue);
  });

  test(
    'falls back to login when token storage bootstrap fails in release mode',
    () async {
      final TokenSessionController controller = TokenSessionController(
        store: _ThrowingBearerTokenStore(),
        releaseMode: true,
        bootstrapTimeout: const Duration(milliseconds: 20),
      );

      await controller.bootstrap();

      expect(controller.bootstrapped, isTrue);
      expect(controller.bearerToken, isNull);
      expect(controller.canEnterShell, isFalse);
    },
  );

  test('stores normalized externally issued bearer token', () async {
    final MemoryBearerTokenStore store = MemoryBearerTokenStore();
    final TokenSessionController controller = TokenSessionController(
      store: store,
      releaseMode: true,
    );

    await controller.saveBearerToken('Bearer jwt-access-token');

    expect(controller.bearerToken, 'jwt-access-token');
    expect(await store.readBearerToken(), 'jwt-access-token');
    expect(controller.canEnterShell, isTrue);
  });
}

class _NeverCompletingBearerTokenStore implements BearerTokenStore {
  @override
  Future<String?> readBearerToken() =>
      Future<String?>.delayed(const Duration(days: 1));

  @override
  Future<void> writeBearerToken(String token) async {}

  @override
  Future<void> clearBearerToken() async {}
}

class _ThrowingBearerTokenStore implements BearerTokenStore {
  @override
  Future<String?> readBearerToken() {
    throw StateError('storage unavailable');
  }

  @override
  Future<void> writeBearerToken(String token) async {}

  @override
  Future<void> clearBearerToken() async {}
}
