/// 백엔드 ``/api/v1/auth/*`` 호출 wrapper — Dio raw call + Freezed JSON.
library;

import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/dio_provider.dart';
import '../domain/auth_errors.dart';
import '../domain/auth_models.dart';

part 'auth_repository.g.dart';

class AuthRepository {
  const AuthRepository(this._dio);

  final Dio _dio;

  /// POST /api/v1/auth/register.
  ///
  /// 422 + detail.code=="consent_required" → ``ConsentRequiredException``.
  /// 409 → ``EmailAlreadyExistsException``.
  Future<TokenResponse> register(RegisterRequest request) async {
    try {
      final Response<Map<String, dynamic>> response =
          await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/register',
        data: request.toJson(),
      );
      return TokenResponse.fromJson(response.data!);
    } on DioException catch (e) {
      _throwForRegisterError(e);
    }
  }

  /// POST /api/v1/auth/login.
  ///
  /// 401 → ``InvalidCredentialsException``.
  Future<TokenResponse> login(LoginRequest request) async {
    try {
      final Response<Map<String, dynamic>> response =
          await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/login',
        data: request.toJson(),
      );
      return TokenResponse.fromJson(response.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        throw const InvalidCredentialsException();
      }
      rethrow;
    }
  }

  /// POST /api/v1/auth/refresh.
  ///
  /// 실패 시 ``RefreshFailedException``.
  Future<TokenResponse> refresh(String refreshToken) async {
    try {
      final Response<Map<String, dynamic>> response =
          await _dio.post<Map<String, dynamic>>(
        '/api/v1/auth/refresh',
        data: RefreshRequest(refreshToken: refreshToken).toJson(),
      );
      return TokenResponse.fromJson(response.data!);
    } on DioException {
      throw const RefreshFailedException();
    }
  }

  Never _throwForRegisterError(DioException e) {
    if (e.response?.statusCode == 409) {
      throw const EmailAlreadyExistsException();
    }
    if (e.response?.statusCode == 422) {
      final Map<String, dynamic>? data =
          e.response?.data as Map<String, dynamic>?;
      final Object? detail = data?['detail'];
      if (detail is Map<String, dynamic> &&
          detail['code'] == 'consent_required') {
        final List<dynamic>? missing = detail['missing'] as List<dynamic>?;
        throw ConsentRequiredException(
          missing == null
              ? const <String>[]
              : missing.map((Object? e) => e.toString()).toList(),
        );
      }
    }
    throw e;
  }
}

@riverpod
AuthRepository authRepository(AuthRepositoryRef ref) {
  return AuthRepository(ref.watch(dioProvider));
}
