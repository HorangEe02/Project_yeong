// features/medical/medical_models.dart — 만성질환(의료) 레코드 모델
//
// 가이드 08 (b) · 백엔드 medical.py 계약. 만성질환은 record_type:"condition"
// 컬렉션이며, 각 컬렉션은 condition 행을 가진다.

/// 단일 만성질환 항목 (PatientConditionResponse).
class PatientCondition {
  /// 만성질환 항목을 생성한다.
  const PatientCondition({
    required this.id,
    required this.conditionText,
    this.clinicalStatus,
    this.onsetDateText,
  });

  /// condition 행 식별자.
  final String id;

  /// 사용자 입력 질환명.
  final String conditionText;

  /// 임상 상태 코드 (active/inactive/resolved/unknown).
  final String? clinicalStatus;

  /// 발병 시점 텍스트.
  final String? onsetDateText;

  /// 응답 항목을 파싱한다.
  factory PatientCondition.fromJson(Map<String, dynamic> json) {
    return PatientCondition(
      id: (json['id'] as Object?)?.toString() ?? '',
      conditionText: _text(json['condition_text']) ?? '',
      clinicalStatus: _text(json['clinical_status']),
      onsetDateText: _text(json['onset_date_text']),
    );
  }

  static String? _text(Object? value) {
    if (value is String && value.trim().isNotEmpty) return value.trim();
    return null;
  }
}

/// 의료 레코드 컬렉션 (MedicalRecordResponse).
class MedicalRecord {
  /// 의료 레코드를 생성한다.
  const MedicalRecord({
    required this.id,
    required this.recordType,
    required this.status,
    this.conditions = const <PatientCondition>[],
  });

  /// 컬렉션 식별자.
  final String id;

  /// 레코드 타입 (condition/medication/...).
  final String recordType;

  /// 라이프사이클 상태 (active/archived/...).
  final String status;

  /// condition 행 목록.
  final List<PatientCondition> conditions;

  /// 활성 condition 컬렉션 여부.
  bool get isActiveCondition =>
      recordType == 'condition' && status == 'active';

  /// 이 컬렉션의 첫 condition 텍스트 (없으면 null).
  String? get primaryConditionText =>
      conditions.isEmpty ? null : conditions.first.conditionText;

  /// 응답 컬렉션을 파싱한다.
  factory MedicalRecord.fromJson(Map<String, dynamic> json) {
    return MedicalRecord(
      id: (json['id'] as Object?)?.toString() ?? '',
      recordType: _text(json['record_type']) ?? '',
      status: _text(json['status']) ?? '',
      conditions: _objectList(json['conditions'])
          .map(PatientCondition.fromJson)
          .toList(growable: false),
    );
  }

  /// `GET /medical-records` 의 `records[]` 를 파싱한다.
  static List<MedicalRecord> listFromJson(Map<String, dynamic> json) {
    return _objectList(json['records'])
        .map(MedicalRecord.fromJson)
        .toList(growable: false);
  }

  static String? _text(Object? value) {
    if (value is String && value.trim().isNotEmpty) return value.trim();
    return null;
  }

  static List<Map<String, dynamic>> _objectList(Object? value) {
    if (value is! List<Object?>) return const <Map<String, dynamic>>[];
    return value.whereType<Map<String, dynamic>>().toList(growable: false);
  }
}
