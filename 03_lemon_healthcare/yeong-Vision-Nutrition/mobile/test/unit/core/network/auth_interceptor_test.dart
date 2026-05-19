/// ``AuthInterceptor`` 단위 테스트 — 토큰 첨부 흐름.
///
/// M-2 에서 401 refresh + 재시도 케이스 추가.
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/core/network/interceptors.dart';
import 'package:lemon_healthcare/core/storage/secure_storage.dart';
import 'package:lemon_healthcare/core/storage/token_storage.dart';
import 'package:mocktail/mocktail.dart';

class _FakeSecureStorage implements SecureStorage {
  _FakeSecureStorage({Map<String, String>? initial})
      : _map = <String, String>{...?initial};

  final Map<String, String> _map;

  @override
  Future<void> write(String key, String value) async => _map[key] = value;

  @override
  Future<String?> read(String key) async => _map[key];

  @override
  Future<void> delete(String key) async => _map.remove(key);

  @override
  Future<void> deleteAll() async => _map.clear();
}

class _MockRequestHandler extends Mock
    implements RequestInterceptorHandler {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      RequestOptions(path: '/fallback'),
    );
  });

  group('AuthInterceptor.onRequest', () {
    test('token 이 있으면 Bearer 헤더 첨부', () async {
      final TokenStorage tokenStorage = TokenStorage(
        _FakeSecureStorage(
          initial: <String, String>{
            'auth.access_token': 'tok_abc',
            'auth.refresh_token': 'ref_xyz',
          },
        ),
      );

      final AuthInterceptor interceptor = AuthInterceptor(tokenStorage);
      final RequestOptions options = RequestOptions(path: '/api/v1/test');
      final _MockRequestHandler handler = _MockRequestHandler();

      await interceptor.onRequest(options, handler);

      expect(options.headers['Authorization'], equals('Bearer tok_abc'));
      verify(() => handler.next(options)).called(1);
    });

    test('token 이 없으면 Authorization 헤더 미첨부', () async {
      final TokenStorage tokenStorage = TokenStorage(_FakeSecureStorage());

      final AuthInterceptor interceptor = AuthInterceptor(tokenStorage);
      final RequestOptions options = RequestOptions(path: '/api/v1/test');
      final _MockRequestHandler handler = _MockRequestHandler();

      await interceptor.onRequest(options, handler);

      expect(options.headers.containsKey('Authorization'), isFalse);
      verify(() => handler.next(options)).called(1);
    });
  });

  group('TokenStorage', () {
    test('save → read → clear 흐름', () async {
      final SecureStorage storage = _FakeSecureStorage();
      final TokenStorage tokenStorage = TokenStorage(storage);

      expect(await tokenStorage.hasTokens(), isFalse);

      await tokenStorage.save(accessToken: 'a', refreshToken: 'r');
      expect(await tokenStorage.readAccess(), equals('a'));
      expect(await tokenStorage.readRefresh(), equals('r'));
      expect(await tokenStorage.hasTokens(), isTrue);

      await tokenStorage.clear();
      expect(await tokenStorage.readAccess(), isNull);
      expect(await tokenStorage.hasTokens(), isFalse);
    });
  });
}
