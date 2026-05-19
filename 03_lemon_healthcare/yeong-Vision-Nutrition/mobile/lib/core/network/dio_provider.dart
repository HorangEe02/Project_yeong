/// Dio Provider — 단일 인스턴스 + 인터셉터 (Auth / Error / Logger).
library;

import 'package:dio/dio.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

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
    AuthInterceptor(ref.watch(tokenStorageProvider)),
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
