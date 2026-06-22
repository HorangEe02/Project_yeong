// features/profile/profile_models.dart — 신체 정보 스냅샷 모델
//
// 가이드 08 (a) · 백엔드 BodyProfileSnapshot* 계약(health.py).
// `GET /health/profile-snapshots/latest` 는 스냅샷 필드 또는
// `{"status":"not_ready"}` 를 돌려준다 — 후자는 null 로 매핑한다.
//
// 백엔드 공백: BodyProfileSnapshotCreate 에는 이름(닉네임) 필드가 없다.
// 이름은 로컬(shared_preferences `profile_display_name`)에만 저장한다.

/// 백엔드 BodyProfileSex 코드.
enum ProfileSex {
  /// 남성.
  male('male', '남성'),

  /// 여성.
  female('female', '여성');

  const ProfileSex(this.code, this.label);

  /// 백엔드 직렬화 코드.
  final String code;

  /// 한국어 표시명.
  final String label;

  /// 코드에서 [ProfileSex] 를 찾는다 (미지 코드는 null).
  static ProfileSex? fromCode(String? code) {
    if (code == null) return null;
    for (final ProfileSex value in ProfileSex.values) {
      if (value.code == code) return value;
    }
    return null;
  }
}

/// 신체 정보 스냅샷 (manual source).
///
/// 모든 필드는 nullable — 백엔드는 1개 이상의 값만 있으면 저장을 허용한다.
class BodyProfileSnapshot {
  /// 스냅샷을 생성한다.
  const BodyProfileSnapshot({
    this.sex,
    this.birthYear,
    this.heightCm,
    this.weightKg,
    this.waistCm,
    this.activityLevel,
    this.effectiveAt,
  });

  /// 성별 코드.
  final ProfileSex? sex;

  /// 출생 연도 (1900~2100).
  final int? birthYear;

  /// 키(cm, 30~260).
  final double? heightCm;

  /// 몸무게(kg, 1~500).
  final double? weightKg;

  /// 허리둘레(cm, 20~250).
  final double? waistCm;

  /// 활동 수준 코드 (sedentary/low_active/active/very_active).
  final String? activityLevel;

  /// 적용 시작 시각.
  final DateTime? effectiveAt;

  /// 표시할 값이 하나라도 있으면 true.
  bool get hasAnyValue =>
      sex != null ||
      birthYear != null ||
      heightCm != null ||
      weightKg != null ||
      waistCm != null ||
      activityLevel != null;

  /// `GET latest` 응답을 파싱한다.
  ///
  /// `{"status":"not_ready"}` 면 null 을 돌려준다(스냅샷 없음).
  static BodyProfileSnapshot? fromLatestJson(Map<String, dynamic> json) {
    if (json['status'] == 'not_ready') return null;
    return BodyProfileSnapshot(
      sex: ProfileSex.fromCode(_text(json['sex'])),
      birthYear: _intOrNull(json['birth_year']),
      heightCm: _doubleOrNull(json['height_cm']),
      weightKg: _doubleOrNull(json['weight_kg']),
      waistCm: _doubleOrNull(json['waist_cm']),
      activityLevel: _text(json['activity_level']),
      effectiveAt: _dateTimeOrNull(json['effective_at']),
    );
  }

  /// `POST /health/profile-snapshots` 요청 본문을 만든다.
  ///
  /// Decimal 필드(키/몸무게/허리)는 백엔드 Decimal 직렬화 안정성을 위해
  /// 소수 둘째 자리 문자열로 보낸다. null 필드는 본문에서 제외한다.
  Map<String, dynamic> toCreateJson() {
    final Map<String, dynamic> body = <String, dynamic>{'source': 'manual'};
    if (sex != null) body['sex'] = sex!.code;
    if (birthYear != null) body['birth_year'] = birthYear;
    if (heightCm != null) body['height_cm'] = _decimalString(heightCm!);
    if (weightKg != null) body['weight_kg'] = _decimalString(weightKg!);
    if (waistCm != null) body['waist_cm'] = _decimalString(waistCm!);
    if (activityLevel != null) body['activity_level'] = activityLevel;
    return body;
  }

  /// 헤더 요약 문자열 (예: "172cm · 68kg"). 값이 없으면 null.
  String? summaryLine() {
    final List<String> parts = <String>[];
    if (heightCm != null) parts.add('${_trimNum(heightCm!)}cm');
    if (weightKg != null) parts.add('${_trimNum(weightKg!)}kg');
    if (parts.isEmpty) return null;
    return parts.join(' · ');
  }

  static String _decimalString(double value) => value.toStringAsFixed(2);

  static String _trimNum(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(1);
  }

  static String? _text(Object? value) {
    if (value is String && value.trim().isNotEmpty) return value.trim();
    return null;
  }

  static int? _intOrNull(Object? value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value.trim());
    return null;
  }

  static double? _doubleOrNull(Object? value) {
    if (value is num) return value.toDouble();
    if (value is String) return double.tryParse(value.trim());
    return null;
  }

  static DateTime? _dateTimeOrNull(Object? value) {
    if (value is String && value.trim().isNotEmpty) {
      return DateTime.tryParse(value.trim());
    }
    return null;
  }
}
