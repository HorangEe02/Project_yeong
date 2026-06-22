import 'dart:convert';

/// Error surfaced by the Lemon Aid API client.
class ApiError implements Exception {
  /// Creates an API error.
  ///
  /// Args:
  ///   statusCode: HTTP response status code.
  ///   code: Sanitized backend error code when present.
  ///   message: User-safe error message.
  ///   requiredConsents: Consent names required by the failed request.
  const ApiError({
    required this.statusCode,
    required this.message,
    this.code,
    this.requiredConsents = const <String>[],
  });

  /// HTTP response status code.
  final int statusCode;

  /// Sanitized backend error code when present.
  final String? code;

  /// User-safe error message.
  final String message;

  /// Consent names required by the failed request.
  final List<String> requiredConsents;

  /// Parses an error from a completed HTTP response body.
  ///
  /// Args:
  ///   statusCode: HTTP response status code.
  ///   body: Response body text.
  ///
  /// Returns:
  ///   ApiError with best-effort backend detail extraction.
  factory ApiError.fromBody({required int statusCode, required String body}) {
    final Object? decoded = _tryDecodeJson(body);
    if (decoded is Map<String, dynamic>) {
      final Object? detail = decoded['detail'];
      if (detail is Map<String, dynamic>) {
        return ApiError(
          statusCode: statusCode,
          code: detail['code'] as String?,
          message: _detailMessage(detail, fallback: body),
          requiredConsents: _stringList(detail['required_consents']),
        );
      }
      if (detail is String) {
        return ApiError(statusCode: statusCode, message: detail);
      }
    }

    return ApiError(
      statusCode: statusCode,
      message: body.trim().isEmpty ? 'Request failed.' : body.trim(),
    );
  }

  static Object? _tryDecodeJson(String body) {
    try {
      return jsonDecode(body);
    } on FormatException {
      return null;
    }
  }

  static String _detailMessage(
    Map<String, dynamic> detail, {
    required String fallback,
  }) {
    final Object? message = detail['message'];
    if (message is String && message.trim().isNotEmpty) {
      return message.trim();
    }
    final Object? code = detail['code'];
    if (code is String && code.trim().isNotEmpty) {
      return code.trim();
    }
    return fallback.trim().isEmpty ? 'Request failed.' : fallback.trim();
  }

  static List<String> _stringList(Object? value) {
    if (value is! List<Object?>) {
      return const <String>[];
    }
    return value.whereType<String>().toList(growable: false);
  }

  @override
  String toString() {
    final String codePart = code == null ? '' : ' code=$code';
    return 'ApiError(status=$statusCode$codePart, message=$message)';
  }
}
