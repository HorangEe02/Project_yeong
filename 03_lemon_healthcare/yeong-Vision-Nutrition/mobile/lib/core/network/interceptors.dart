/// Dio 인터셉터 — AuthInterceptor / ErrorInterceptor.
///
/// M-1 골격:
///   - AuthInterceptor: TokenStorage 에 토큰이 있으면 Bearer 헤더 자동 첨부.
///     401 자동 refresh + 재시도 로직은 M-2 에서 AuthRepository.refresh
///     도입 후 채움 (TODO 마커 — M-2 commit 으로 채워질 것).
///   - ErrorInterceptor: DioException → 사용자 친화 한국어 메시지 로깅.
library;

import 'package:dio/dio.dart';

import '../storage/token_storage.dart';
import '../utils/logger.dart';

/// 인증 토큰 자동 첨부 인터셉터.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._tokenStorage);

  final TokenStorage _tokenStorage;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final String? accessToken = await _tokenStorage.readAccess();
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
    // M-2 TODO: 401 응답 시 refresh 토큰으로 자동 재발급 + 요청 재시도.
    //   현재는 호출처가 401 을 그대로 받음. AuthNotifier 가 state 를
    //   Unauthenticated 로 전환하면 go_router 가 /login 으로 redirect.
    handler.next(err);
  }
}

/// 공통 에러 로깅 인터셉터 — 운영 환경에선 민감 정보 마스킹 필요.
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
