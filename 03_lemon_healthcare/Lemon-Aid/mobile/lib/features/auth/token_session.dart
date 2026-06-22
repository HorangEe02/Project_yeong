import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Storage boundary for an externally issued JWT bearer token.
abstract class BearerTokenStore {
  /// Reads the currently stored bearer token.
  Future<String?> readBearerToken();

  /// Stores a bearer token for future API requests.
  Future<void> writeBearerToken(String token);

  /// Clears the stored bearer token.
  Future<void> clearBearerToken();
}

/// Secure platform storage for staging/production bearer-token testing.
class SecureBearerTokenStore implements BearerTokenStore {
  /// Creates secure token storage.
  SecureBearerTokenStore({
    FlutterSecureStorage storage = const FlutterSecureStorage(),
  }) : _storage = storage;

  static const String _tokenKey = 'lemon_external_bearer_token';

  final FlutterSecureStorage _storage;

  @override
  Future<String?> readBearerToken() {
    return _storage.read(key: _tokenKey);
  }

  @override
  Future<void> writeBearerToken(String token) {
    return _storage.write(key: _tokenKey, value: token);
  }

  @override
  Future<void> clearBearerToken() {
    return _storage.delete(key: _tokenKey);
  }
}

/// In-memory token store for widget tests and injected demos.
class MemoryBearerTokenStore implements BearerTokenStore {
  /// Creates an in-memory token store.
  MemoryBearerTokenStore({String? initialToken}) : _token = initialToken;

  String? _token;

  @override
  Future<String?> readBearerToken() async {
    return _token;
  }

  @override
  Future<void> writeBearerToken(String token) async {
    _token = token;
  }

  @override
  Future<void> clearBearerToken() async {
    _token = null;
  }
}

/// Local auth/session state for the resource-server mobile app.
class TokenSessionController extends ChangeNotifier {
  /// Creates a token session controller.
  ///
  /// Args:
  ///   store: Persistence boundary for an externally issued JWT.
  ///   releaseMode: Whether release-mode access restrictions apply.
  ///   bootstrapTimeout: Maximum wait for persisted token storage.
  TokenSessionController({
    required BearerTokenStore store,
    bool releaseMode = kReleaseMode,
    Duration bootstrapTimeout = const Duration(seconds: 2),
  }) : _store = store,
       _releaseMode = releaseMode,
       _bootstrapTimeout = bootstrapTimeout;

  final BearerTokenStore _store;
  final bool _releaseMode;
  final Duration _bootstrapTimeout;

  bool _bootstrapped = false;
  String? _bearerToken;

  /// Whether persisted state has been loaded.
  bool get bootstrapped => _bootstrapped;

  /// Stored externally issued bearer token, if any.
  String? get bearerToken => _bearerToken;

  /// Whether debug/dev mode can use backend AUTH_MODE=disabled without a token.
  bool get devBypassActive => !_releaseMode && _bearerToken == null;

  /// Whether the app may enter protected screens.
  bool get canEnterShell => _bearerToken != null || devBypassActive;

  /// Loads any persisted external bearer token.
  Future<void> bootstrap() async {
    try {
      _bearerToken = _normalizeToken(
        await _store.readBearerToken().timeout(
          _bootstrapTimeout,
          onTimeout: () => null,
        ),
      );
    } on Object {
      _bearerToken = null;
    }
    _bootstrapped = true;
    notifyListeners();
  }

  /// Saves a bearer token entered by an operator or tester.
  Future<void> saveBearerToken(String token) async {
    final String? normalized = _normalizeToken(token);
    if (normalized == null) {
      throw ArgumentError.value(token, 'token', 'Bearer token is empty');
    }
    await _store.writeBearerToken(normalized);
    _bearerToken = normalized;
    _bootstrapped = true;
    notifyListeners();
  }

  /// Clears the external bearer token and returns to dev bypass or login.
  Future<void> clearBearerToken() async {
    await _store.clearBearerToken();
    _bearerToken = null;
    _bootstrapped = true;
    notifyListeners();
  }

  static String? _normalizeToken(String? token) {
    final String? trimmed = token?.trim();
    if (trimmed == null || trimmed.isEmpty) {
      return null;
    }
    return trimmed.replaceFirst(
      RegExp(r'^Bearer\s+', caseSensitive: false),
      '',
    );
  }
}
