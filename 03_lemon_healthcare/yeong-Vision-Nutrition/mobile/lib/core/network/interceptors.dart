/// Dio 인터셉터 — AuthInterceptor (Bearer + 401 refresh single-flight) +
/// ErrorInterceptor (로깅).
library;

import 'dart:async';

import 'package:dio/dio.dart';

import '../../features/auth/domain/auth_errors.dart';
import '../../features/auth/domain/auth_models.dart';
import '../storage/token_storage.dart';
import '../utils/logger.dart';

/// 인증 토큰 자동 첨부 + 401 시 single-flight refresh + 재시도.
///
/// 동시 401 다수 발생 시 ``_refreshCompleter`` 로 단일 refresh 호출 보장
/// (thundering herd 방지). refresh 실패 시 ``onLogoutRequested`` 콜백 호출.
class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required this.tokenStorage,
    required this.refresh,
    required this.onLogoutRequested,
    required this.retryDio,
  });

  final TokenStorage tokenStorage;
  final Future<TokenResponse> Function(String refreshToken) refresh;
  final Future<void> Function() onLogoutRequested;
  final Dio retryDio;

  /// in-flight refresh 추적 — null 이면 사전 진행 중인 refresh 없음.
  Completer<TokenResponse>? _refreshCompleter;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final String? accessToken = await tokenStorage.readAccess();
    if (accessToken != null && accessToken.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $accessToken';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final int? status = err.response?.statusCode;
    final String path = err.requestOptions.path;

    // refresh 자체 또는 /auth/* 경로의 401 은 재시도하지 않는다 (무한 루프 차단).
    if (status != 401 || path.contains('/auth/')) {
      handler.next(err);
      return;
    }

    final String? refreshToken = await tokenStorage.readRefresh();
    if (refreshToken == null || refreshToken.isEmpty) {
      await onLogoutRequested();
      handler.next(err);
      return;
    }

    try {
      final TokenResponse newTokens = await _singleFlightRefresh(refreshToken);
      await tokenStorage.save(
        accessToken: newTokens.accessToken,
        refreshToken: newTokens.refreshToken,
      );

      // 새 토큰으로 원본 요청 재시도.
      final RequestOptions clone = err.requestOptions.copyWith(
        headers: <String, dynamic>{
          ...err.requestOptions.headers,
          'Authorization': 'Bearer ${newTokens.accessToken}',
        },
      );
      final Response<dynamic> response = await retryDio.fetch<dynamic>(clone);
      handler.resolve(response);
    } on RefreshFailedException {
      await onLogoutRequested();
      handler.next(err);
    } on Object {
      await onLogoutRequested();
      handler.next(err);
    }
  }

  /// 단일 refresh 호출 보장 — 다른 401 들은 같은 future 공유.
  Future<TokenResponse> _singleFlightRefresh(String refreshToken) async {
    final Completer<TokenResponse>? existing = _refreshCompleter;
    if (existing != null) {
      return existing.future;
    }
    final Completer<TokenResponse> completer = Completer<TokenResponse>();
    _refreshCompleter = completer;
    try {
      final TokenResponse tokens = await refresh(refreshToken);
      completer.complete(tokens);
      return tokens;
    } on Object catch (e, st) {
      completer.completeError(e, st);
      rethrow;
    } finally {
      _refreshCompleter = null;
    }
  }
}

/// 공통 에러 로깅 인터셉터.
class ErrorInterceptor extends Interceptor {
  @override
  void onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) {
    appLogger.e(
      'API Error ${err.response?.statusCode ?? 0} ${err.requestOptions.uri}',
      error: err,
    );
    handler.next(err);
  }
}
