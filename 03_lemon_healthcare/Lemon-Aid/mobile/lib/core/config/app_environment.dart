/// Deployment environment selected at build time.
///
/// The value is injected through `--dart-define=LEMON_APP_ENV=<name>` and is
/// kept in lock-step with the native build targets so a single selection
/// drives the backend base URL and release security posture:
///
///   * Android product flavors — `dev` / `staging` / `prod`
///     (`android/app/build.gradle.kts`).
///   * iOS environment xcconfig — `ios/config/{Dev,Staging,Prod}.xcconfig`.
///
/// `dev` is the safe, local-first default when no value is provided.
enum AppEnvironment {
  /// Local development against a loopback backend.
  dev,

  /// Pre-production staging backend (URL provisioned later).
  staging,

  /// Production backend (URL provisioned later).
  prod;

  /// Resolves an environment from a raw `--dart-define` string.
  ///
  /// Args:
  ///   raw: Value of `LEMON_APP_ENV`. Blank or unknown values fall back to
  ///     [AppEnvironment.dev] so misconfiguration never silently promotes a
  ///     build to a remote environment.
  ///
  /// Returns:
  ///   The matching [AppEnvironment].
  static AppEnvironment fromName(String raw) {
    switch (raw.trim().toLowerCase()) {
      case 'prod':
      case 'production':
        return AppEnvironment.prod;
      case 'staging':
      case 'stage':
        return AppEnvironment.staging;
      case 'dev':
      case 'development':
      case '':
        return AppEnvironment.dev;
      default:
        return AppEnvironment.dev;
    }
  }

  /// Whether this environment targets a non-local deployment.
  bool get isRemote => this != AppEnvironment.dev;
}
