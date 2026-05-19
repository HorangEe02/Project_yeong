/// 영양제 사진 등록 — backend `models/schemas/supplement.py` + `nutrition.py` 1:1 매핑.
///
/// `fieldRename: FieldRename.snake` 으로 snake_case JSON ↔ camelCase Dart.
library;

// freezed factory 인자의 @JsonKey 는 freezed 매크로가 getter 로 옮겨주지만,
// 분석기는 일시 invalid_annotation_target 으로 경고함 (freezed README 권장 무시).
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

import '../../../shared/models/emergency_contact.dart';

part 'supplement_models.freezed.dart';
part 'supplement_models.g.dart';

/// 단일 성분 — backend ``IngredientResponse``.
@freezed
class Ingredient with _$Ingredient {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory Ingredient({
    required String code,
    @JsonKey(name: 'name_ko') required String nameKo,
    required double amount,
    required String unit,
  }) = _Ingredient;

  factory Ingredient.fromJson(Map<String, dynamic> json) =>
      _$IngredientFromJson(json);
}

/// 영양소 상태 — backend ``NutrientStatus`` (StrEnum, lowercase).
///
/// `ratio` 의미:
///   deficient < 0.35 ≤ low < 0.7 ≤ adequate ≤ 1.3 < excessive (UL 미만), risky > UL.
enum NutrientStatus {
  @JsonValue('deficient')
  deficient,
  @JsonValue('low')
  low,
  @JsonValue('adequate')
  adequate,
  @JsonValue('excessive')
  excessive,
  @JsonValue('risky')
  risky,
}

/// 단일 영양소 진단 — backend ``NutrientDiagnosis``.
@freezed
class NutrientDiagnosis with _$NutrientDiagnosis {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory NutrientDiagnosis({
    required String code,
    @JsonKey(name: 'name_ko') required String nameKo,
    double? rda,
    double? ai,
    double? ear,
    double? ul,
    required double actual,
    required String unit,
    required double ratio,
    required NutrientStatus status,
    @JsonKey(name: 'message_ko') required String messageKo,
  }) = _NutrientDiagnosis;

  factory NutrientDiagnosis.fromJson(Map<String, dynamic> json) =>
      _$NutrientDiagnosisFromJson(json);
}

/// 진단 결과 묶음 — backend ``DiagnosisResult``.
@freezed
class DiagnosisResult with _$DiagnosisResult {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory DiagnosisResult({
    required List<NutrientDiagnosis> diagnoses,
    @JsonKey(name: 'deficient_count') required int deficientCount,
    @JsonKey(name: 'risky_count') required int riskyCount,
    @JsonKey(name: 'adequate_count') required int adequateCount,
    @JsonKey(name: 'summary_message_ko') required String summaryMessageKo,
  }) = _DiagnosisResult;

  factory DiagnosisResult.fromJson(Map<String, dynamic> json) =>
      _$DiagnosisResultFromJson(json);
}

/// backend `list[dict[str, str]]` → `List<EmergencyContact>` 변환.
///
/// freezed/json_serializable 의 자동 변환은 nested object 만 지원 — 외부
/// 공유 모델인 EmergencyContact 로 매핑하려면 명시 헬퍼 필요.
List<EmergencyContact> emergencyContactsFromJson(List<dynamic>? raw) {
  if (raw == null) return const <EmergencyContact>[];
  return raw
      .whereType<Map<String, dynamic>>()
      .map(EmergencyContact.fromJson)
      .toList(growable: false);
}

/// 영양제 등록 응답 — backend ``SupplementRegisterResponse``.
///
/// `emergencyResources` 는 백엔드가 raw dict 리스트로 보내고, 공유 위젯
/// EmergencyResources 가 EmergencyContact 를 요구하므로
/// `emergencyContactsFromJson` 헬퍼로 변환한다 (위 함수 docstring 참조).
@freezed
class SupplementResponse with _$SupplementResponse {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory SupplementResponse({
    @JsonKey(name: 'supplement_id') required String supplementId,
    @JsonKey(name: 'product_name') String? productName,
    String? manufacturer,
    required List<Ingredient> ingredients,
    @JsonKey(name: 'unmatched_ingredient_names')
    required List<String> unmatchedIngredientNames,
    required DiagnosisResult diagnosis,
    @JsonKey(name: 'ocr_engine') required String ocrEngine,
    @JsonKey(name: 'llm_engine') required String llmEngine,
    @JsonKey(name: 'elapsed_ms') required double elapsedMs,
    required List<String> disclaimers,
    @JsonKey(
      name: 'emergency_resources',
      fromJson: emergencyContactsFromJson,
    )
    required List<EmergencyContact> emergencyResources,
    @JsonKey(name: 'consult_professional_message_ko')
    required String consultProfessionalMessageKo,
  }) = _SupplementResponse;

  factory SupplementResponse.fromJson(Map<String, dynamic> json) =>
      _$SupplementResponseFromJson(json);
}
