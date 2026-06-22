class UserMedication {
  const UserMedication({
    required this.id,
    required this.displayName,
    required this.confirmationStatus,
    required this.isActive,
    required this.lastConfirmedAt,
    required this.createdAt,
    required this.updatedAt,
    this.normalizedName,
    this.medicationClass,
    this.conditionTags = const <String>[],
  });

  final String id;
  final String displayName;
  final String? normalizedName;
  final String? medicationClass;
  final List<String> conditionTags;
  final String confirmationStatus;
  final bool isActive;
  final DateTime lastConfirmedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory UserMedication.fromJson(Map<String, dynamic> json) {
    return UserMedication(
      id: json['id'] as String? ?? '',
      displayName: json['display_name'] as String? ?? '',
      normalizedName: json['normalized_name'] as String?,
      medicationClass: json['medication_class'] as String?,
      conditionTags: (json['condition_tags'] as List<dynamic>? ?? <dynamic>[])
          .whereType<String>()
          .toList(growable: false),
      confirmationStatus:
          json['confirmation_status'] as String? ?? 'user_confirmed',
      isActive: json['is_active'] as bool? ?? false,
      lastConfirmedAt: DateTime.tryParse(
            json['last_confirmed_at'] as String? ?? '',
          ) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
    );
  }
}

class UserMedicationDraft {
  const UserMedicationDraft({
    required this.displayName,
    this.normalizedName,
    this.medicationClass,
    this.conditionTags = const <String>[],
    this.isActive = true,
  });

  final String displayName;
  final String? normalizedName;
  final String? medicationClass;
  final List<String> conditionTags;
  final bool isActive;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'display_name': displayName,
      if (normalizedName != null && normalizedName!.isNotEmpty)
        'normalized_name': normalizedName,
      if (medicationClass != null && medicationClass!.isNotEmpty)
        'medication_class': medicationClass,
      'condition_tags': conditionTags,
      'is_active': isActive,
    };
  }
}

const Map<String, String> medicationClassLabels = <String, String>{
  'calcium_channel_blocker': '칼슘채널차단제',
  'ace_inhibitor': 'ACE 억제제',
  'arb': 'ARB',
  'beta_blocker': '베타차단제',
  'diuretic': '이뇨제',
  'statin': '스타틴',
  'warfarin': '와파린',
  'anticoagulant': '항응고제',
  'ssri': 'SSRI',
  'snri': 'SNRI',
  'thyroid_hormone': '갑상선약',
  'other': '기타',
};
