import 'package:flutter/foundation.dart';

import 'app_environment.dart';

/// Runtime configuration loaded from Flutter compile-time definitions.
class AppConfig {
  /// Creates app configuration.
  ///
  /// Args:
  ///   environment: Selected deployment environment (dev/staging/prod).
  ///   apiBaseUrl: Backend API base URL ending at `/api/v1`.
  ///   apiToken: Optional bearer token. Local `AUTH_MODE=disabled` runs without it.
  const AppConfig({
    required this.environment,
    required this.apiBaseUrl,
    required this.apiToken,
    required this.devGatewayToken,
    required this.certificatePins,
  });

  /// Deployment environment selected via `--dart-define=LEMON_APP_ENV`.
  final AppEnvironment environment;

  /// Backend API base URL ending at `/api/v1`.
  final String apiBaseUrl;

  /// Optional bearer token for JWT-backed environments.
  final String? apiToken;

  /// Optional local development gateway token for ngrok smoke tests.
  final String? devGatewayToken;

  /// Release certificate pin configuration reserved for the hardened API client.
  final List<String> certificatePins;

  /// Builds configuration from `--dart-define` values.
  ///
  /// Returns:
  ///   AppConfig with a normalized base URL and optional token.
  factory AppConfig.fromEnvironment({
    bool releaseMode = kReleaseMode,
    TargetPlatform? platform,
  }) {
    const String rawEnv = String.fromEnvironment('LEMON_APP_ENV');
    const String rawBaseUrl = String.fromEnvironment('LEMON_API_BASE_URL');
    const String rawToken = String.fromEnvironment('LEMON_API_TOKEN');
    const String rawDevGatewayToken = String.fromEnvironment(
      'LEMON_DEV_GATEWAY_TOKEN',
    );
    const String rawCertificatePins = String.fromEnvironment(
      'LEMON_CERTIFICATE_PINS',
    );

    final AppEnvironment environment = AppEnvironment.fromName(rawEnv);
    return AppConfig.fromValues(
      environment: environment,
      apiBaseUrl: rawBaseUrl.trim().isEmpty
          ? defaultApiBaseUrlForEnvironment(
              environment,
              platform ?? defaultTargetPlatform,
            )
          : rawBaseUrl,
      apiToken: rawToken,
      devGatewayToken: rawDevGatewayToken,
      certificatePins: _splitCommaSeparated(rawCertificatePins),
      releaseMode: releaseMode,
    );
  }

  /// Reserved host suffix for environments without a provisioned backend.
  ///
  /// The `.invalid` top-level domain is reserved by RFC 2606, so it can never
  /// resolve to a real host. Staging/prod placeholders use it until real URLs
  /// land; release builds reject any base URL on this suffix (fail closed).
  static const String unprovisionedHostSuffix = '.invalid';

  /// Returns the default backend base URL for an environment.
  ///
  /// Args:
  ///   environment: Selected deployment environment.
  ///   platform: Target Flutter platform (only used for the local `dev` host).
  ///
  /// Returns:
  ///   For `dev`, the simulator-aware loopback URL. For `staging`/`prod`, a
  ///   provisioning placeholder on the reserved `.invalid` domain that must be
  ///   overridden with `--dart-define=LEMON_API_BASE_URL` before shipping.
  @visibleForTesting
  static String defaultApiBaseUrlForEnvironment(
    AppEnvironment environment,
    TargetPlatform platform,
  ) {
    return switch (environment) {
      AppEnvironment.dev => defaultApiBaseUrlForPlatform(platform),
      // TODO(env): replace with the provisioned staging URL once available.
      AppEnvironment.staging =>
        'https://staging.lemon-aid$unprovisionedHostSuffix/api/v1',
      // TODO(env): replace with the provisioned production URL once available.
      AppEnvironment.prod =>
        'https://api.lemon-aid$unprovisionedHostSuffix/api/v1',
    };
  }

  /// Returns the local backend URL that works for the current simulator host.
  ///
  /// Args:
  ///   platform: Target Flutter platform.
  ///
  /// Returns:
  ///   Android emulator host-loopback URL or localhost for Apple/desktop runs.
  @visibleForTesting
  static String defaultApiBaseUrlForPlatform(TargetPlatform platform) {
    return switch (platform) {
      TargetPlatform.android => 'http://10.0.2.2:8000/api/v1',
      _ => 'http://127.0.0.1:8000/api/v1',
    };
  }

  /// Builds configuration from explicit values.
  ///
  /// Args:
  ///   apiBaseUrl: Backend API base URL ending at `/api/v1`.
  ///   apiToken: Optional local-development bearer token.
  ///   devGatewayToken: Optional local-development gateway token.
  ///   certificatePins: Certificate pin config required for release builds.
  ///   releaseMode: Whether release binary restrictions should be enforced.
  ///
  /// Returns:
  ///   Validated app configuration.
  ///
  /// Raises:
  ///   StateError: If release configuration contains unsafe values.
  factory AppConfig.fromValues({
    required String apiBaseUrl,
    AppEnvironment environment = AppEnvironment.dev,
    String? apiToken,
    String? devGatewayToken,
    List<String> certificatePins = const <String>[],
    bool releaseMode = false,
  }) {
    final String normalizedBaseUrl = _withoutTrailingSlash(apiBaseUrl.trim());
    final String? normalizedToken = apiToken == null || apiToken.trim().isEmpty
        ? null
        : apiToken.trim();
    final String? normalizedDevGatewayToken =
        devGatewayToken == null || devGatewayToken.trim().isEmpty
        ? null
        : devGatewayToken.trim();
    final List<String> normalizedCertificatePins = certificatePins
        .map((String value) => value.trim())
        .where((String value) => value.isNotEmpty)
        .toList(growable: false);

    if (releaseMode && normalizedToken != null) {
      throw StateError(
        'LEMON_API_TOKEN must not be embedded in release builds.',
      );
    }
    if (releaseMode && normalizedDevGatewayToken != null) {
      throw StateError(
        'LEMON_DEV_GATEWAY_TOKEN must not be embedded in release builds.',
      );
    }
    if (releaseMode && !normalizedBaseUrl.startsWith('https://')) {
      throw StateError('LEMON_API_BASE_URL must use HTTPS in release builds.');
    }
    if (!normalizedBaseUrl.endsWith('/api/v1')) {
      throw StateError('LEMON_API_BASE_URL must end with /api/v1.');
    }
    if (releaseMode && normalizedCertificatePins.isEmpty) {
      throw StateError(
        'LEMON_CERTIFICATE_PINS must be provided in release builds.',
      );
    }
    final String host = Uri.tryParse(normalizedBaseUrl)?.host ?? '';
    if (releaseMode && host.endsWith(unprovisionedHostSuffix)) {
      throw StateError(
        'LEMON_API_BASE_URL is an unprovisioned ${environment.name} '
        'placeholder; pass a real --dart-define=LEMON_API_BASE_URL.',
      );
    }

    return AppConfig(
      environment: environment,
      apiBaseUrl: normalizedBaseUrl,
      apiToken: normalizedToken,
      devGatewayToken: normalizedDevGatewayToken,
      certificatePins: List<String>.unmodifiable(normalizedCertificatePins),
    );
  }

  static List<String> _splitCommaSeparated(String value) {
    if (value.trim().isEmpty) {
      return const <String>[];
    }
    return value
        .split(',')
        .map((String item) => item.trim())
        .where((String item) => item.isNotEmpty)
        .toList(growable: false);
  }

  static String _withoutTrailingSlash(String value) {
    if (value.endsWith('/')) {
      return value.substring(0, value.length - 1);
    }
    return value;
  }
}
