import 'package:dio/dio.dart';

import '../config/app_config.dart';

class LemonApiClient {
  LemonApiClient({
    required AppConfig config,
    Dio? dio,
  }) : _dio = dio ?? Dio(_baseOptions(config)) {
    if (config.hasAuthToken) {
      _dio.options.headers['Authorization'] = 'Bearer ${config.authToken}';
    }
    _dio.options.headers['Content-Type'] = 'application/json';
  }

  final Dio _dio;

  Future<Response<Map<String, dynamic>>> postJson(
    String path,
    Map<String, dynamic> body,
  ) {
    return _dio.post<Map<String, dynamic>>(path, data: body);
  }

  Future<Response<Map<String, dynamic>>> getJson(String path) {
    return _dio.get<Map<String, dynamic>>(path);
  }

  Future<Response<Map<String, dynamic>>> patchJson(
    String path,
    Map<String, dynamic> body,
  ) {
    return _dio.patch<Map<String, dynamic>>(path, data: body);
  }

  Future<Response<Map<String, dynamic>>> postMultipart(
    String path,
    FormData body,
  ) {
    return _dio.post<Map<String, dynamic>>(path, data: body);
  }

  static BaseOptions _baseOptions(AppConfig config) {
    return BaseOptions(
      baseUrl: config.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      validateStatus: (int? status) => status != null && status < 500,
    );
  }
}
