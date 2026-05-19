/// 토큰 저장/조회 — ``secure_storage`` 위 키 명시 wrapper.
///
/// access / refresh 토큰만 보관. 평문 SharedPreferences 사용 X (Rule 5).
library;

import 'package:riverpod_annotation/riverpod_annotation.dart';

import 'secure_storage.dart';

part 'token_storage.g.dart';

class TokenStorage {
  const TokenStorage(this._storage);

  static const String _accessKey = 'auth.access_token';
  static const String _refreshKey = 'auth.refresh_token';

  final SecureStorage _storage;

  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(_accessKey, accessToken);
    await _storage.write(_refreshKey, refreshToken);
  }

  Future<String?> readAccess() => _storage.read(_accessKey);
  Future<String?> readRefresh() => _storage.read(_refreshKey);

  Future<void> clear() async {
    await _storage.delete(_accessKey);
    await _storage.delete(_refreshKey);
  }

  /// 토큰 두 개 모두 존재하는지.
  Future<bool> hasTokens() async {
    final String? access = await readAccess();
    final String? refresh = await readRefresh();
    return access != null && access.isNotEmpty && refresh != null && refresh.isNotEmpty;
  }
}

@riverpod
TokenStorage tokenStorage(TokenStorageRef ref) {
  return TokenStorage(ref.watch(secureStorageProvider));
}
