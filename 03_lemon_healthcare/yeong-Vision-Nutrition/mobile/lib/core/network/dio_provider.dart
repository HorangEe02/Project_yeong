/// Dio Provider — 단일 인스턴스 + 인터셉터 3종 (Auth / Error / PrettyLogger).
///
/// AuthInterceptor 의 refresh / logout 콜백은 lazy ref.read 로 wiring 해
/// authRepositoryProvider / authNotifierProvider 와의 provider 순환 의존을 피한다.
library;

import 'package:dio/dio.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/auth/data/auth_repository.dart';
import '../../features/auth/presentation/providers/auth_notifier.dart';
import '../config/env.dart';
import '../storage/token_storage.dart';
import 'interceptors.dart';

part 'dio_provider.g.dart';

@riverpod
Dio dio(DioRef ref) {
  final Dio dio = Dio(
    BaseOptions(
      baseUrl: Env.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      sendTimeout: const Duration(seconds: 30),
      headers: <String, String>{
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    ),
  );

  dio.interceptors.addAll(<Interceptor>[
    AuthInterceptor(
      tokenStorage: ref.watch(tokenStorageProvider),
      refresh: (String refreshToken) async =>
          ref.read(authRepositoryProvider).refresh(refreshToken),
      onLogoutRequested: () async =>
          ref.read(authNotifierProvider.notifier).logout(),
      retryDio: dio,
    ),
    ErrorInterceptor(),
    if (Env.isDebug)
      PrettyDioLogger(
        requestHeader: true,
        requestBody: true,
        responseBody: true,
        compact: true,
      ),
  ]);

  return dio;
}
