import 'package:flutter/foundation.dart';

class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.authToken,
  });

  factory AppConfig.fromEnvironment() {
    return AppConfig(
      apiBaseUrl: defaultApiBaseUrl(),
      authToken: const String.fromEnvironment('LEMON_AUTH_TOKEN'),
    );
  }

  final String apiBaseUrl;
  final String authToken;

  bool get hasAuthToken => authToken.isNotEmpty;

  static String defaultApiBaseUrl() {
    const String configured = String.fromEnvironment('LEMON_API_BASE_URL');
    if (configured.isNotEmpty) {
      return configured;
    }
    if (kIsWeb) {
      return 'http://localhost:18080';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:18080';
    }
    return 'http://127.0.0.1:18080';
  }
}
