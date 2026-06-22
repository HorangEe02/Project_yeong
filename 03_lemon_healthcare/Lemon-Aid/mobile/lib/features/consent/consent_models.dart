import '../../shared/models/json_readers.dart';

/// Current consent state returned by `/me/privacy/consents`.
class ConsentState {
  /// Creates current consent state.
  ///
  /// Args:
  ///   consents: Consent rows returned by the backend.
  const ConsentState({required this.consents});

  /// Consent rows returned by the backend.
  final List<ConsentStatus> consents;

  /// Parses a backend consent-state response.
  ///
  /// Args:
  ///   json: Decoded backend JSON object.
  ///
  /// Returns:
  ///   Parsed consent state.
  factory ConsentState.fromJson(Map<String, dynamic> json) {
    return ConsentState(
      consents: readList(json, 'consents')
          .whereType<Map<String, dynamic>>()
          .map(ConsentStatus.fromJson)
          .toList(growable: false),
    );
  }

  /// Returns true when a consent bucket is currently granted.
  bool isGranted(String consentType) {
    return consents.any(
      (ConsentStatus consent) =>
          consent.consentType == consentType && consent.granted,
    );
  }
}

/// Single backend consent bucket state.
class ConsentStatus {
  /// Creates a consent status.
  ///
  /// Args:
  ///   consentType: Backend consent bucket identifier.
  ///   policyVersion: Active consent policy version.
  ///   title: Human-readable consent title.
  ///   required: Whether the consent gates a feature.
  ///   granted: Whether the active policy version is granted.
  ///   occurredAt: Latest consent event time.
  ///   revokedAt: Latest revocation time.
  const ConsentStatus({
    required this.consentType,
    required this.policyVersion,
    required this.title,
    required this.required,
    required this.granted,
    required this.occurredAt,
    required this.revokedAt,
  });

  /// Backend consent bucket identifier.
  final String consentType;

  /// Active consent policy version.
  final String policyVersion;

  /// Human-readable consent title.
  final String title;

  /// Whether the consent gates a feature.
  final bool required;

  /// Whether the active policy version is granted.
  final bool granted;

  /// Latest consent event time.
  final DateTime? occurredAt;

  /// Latest revocation time.
  final DateTime? revokedAt;

  /// Parses a single backend consent status.
  factory ConsentStatus.fromJson(Map<String, dynamic> json) {
    return ConsentStatus(
      consentType: readString(json, 'consent_type'),
      policyVersion: readString(json, 'policy_version'),
      title: readString(json, 'title'),
      required: json['required'] as bool? ?? false,
      granted: json['granted'] as bool? ?? false,
      occurredAt: _parseDateTime(json['occurred_at']),
      revokedAt: _parseDateTime(json['revoked_at']),
    );
  }
}

/// Consent grant or revoke action response.
class ConsentAction {
  /// Creates a consent action response.
  const ConsentAction({
    required this.consentType,
    required this.policyVersion,
    required this.granted,
    required this.occurredAt,
  });

  /// Backend consent bucket identifier.
  final String consentType;

  /// Policy version used for the action.
  final String policyVersion;

  /// Whether the consent is granted after the action.
  final bool granted;

  /// Time of the action.
  final DateTime occurredAt;

  /// Parses a backend consent action response.
  factory ConsentAction.fromJson(Map<String, dynamic> json) {
    return ConsentAction(
      consentType: readString(json, 'consent_type'),
      policyVersion: readString(json, 'policy_version'),
      granted: json['granted'] as bool? ?? false,
      occurredAt: _parseDateTime(json['occurred_at']) ?? DateTime.now(),
    );
  }
}

DateTime? _parseDateTime(Object? value) {
  if (value is String) {
    return DateTime.tryParse(value);
  }
  return null;
}
