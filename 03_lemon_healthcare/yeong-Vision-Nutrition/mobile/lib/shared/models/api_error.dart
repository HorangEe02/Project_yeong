/// 백엔드 에러 응답 모델 — Dio 응답 매핑용.
library;

import 'package:freezed_annotation/freezed_annotation.dart';

part 'api_error.freezed.dart';
part 'api_error.g.dart';

@freezed
class ApiError with _$ApiError {
  const factory ApiError({
    required int statusCode,
    String? code,
    String? message,
    Map<String, dynamic>? detail,
  }) = _ApiError;

  factory ApiError.fromJson(Map<String, dynamic> json) =>
      _$ApiErrorFromJson(json);
}
